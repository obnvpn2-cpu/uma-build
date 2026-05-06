"""Local exploration: does EV-based betting beat top-1 on real JRA data?

Runs a walk-forward CV on the cached feature table, joins TanOdds /
FukuOdds from jravan.db, then sweeps strategies (top-1, EV-thresholded
single, top-1 by EV, place bets, etc.) and reports ROI.

Goal: prove (or refute) that there exists a positive-EV strategy
extractable from the model's predictions, before building product
features around it.

Usage:
    # Default: lambdarank + softmax per race (uncalibrated probability)
    cd backend && python scripts/explore_ev_strategy.py

    # Re-run with calibrated binary classifier (proper EV semantics)
    cd backend && python scripts/explore_ev_strategy.py --use-calibrated

    # Persist strategy results JSON for compare_ev_strategies.py
    cd backend && python scripts/explore_ev_strategy.py --use-calibrated \
        --save-results data/ev_strategy_calibrated.json
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ml.feature_selector import filter_available_columns, select_columns  # noqa: E402
from ml.pipeline import TrainConfig, _eval_classification_metrics  # noqa: E402
from ml.walk_forward import walk_forward_cv  # noqa: E402
from services.feature_catalog import get_default_feature_ids  # noqa: E402
from services.odds_features import (  # noqa: E402
    ODDS_DERIVED_COLUMNS,
    add_odds_derived_features,
)

DB_PATH = ROOT / "data" / "jravan.db"
PARQUET = ROOT / "data" / "feature_table_cache.parquet"

# Original "small" set (~11 features after filtering). Kept for parity
# with the first round of EV exploration. New runs default to "default"
# (catalog get_default_feature_ids — 34 IDs, no odds-derived leaks).
SMALL_FEATURES = [
    "popularity",        # 人気順位
    "win_odds_estimate",  # might be missing
    "horse_win_rate",
    "horse_in3_rate",
    "horse_recent5_avg_finish",
    "jockey_win_rate",
    "jockey_recent20_win_rate",
    "trainer_win_rate",
    "horse_surface_win_rate",
    "horse_distance_win_rate",
    "field_size",
    "weight_carried",
    "age",
    "body_weight",
]


def _resolve_features(mode: str) -> list[str]:
    if mode == "small":
        return SMALL_FEATURES
    if mode == "default":
        return get_default_feature_ids()
    raise ValueError(f"Unknown features mode: {mode}")


def load_predictions(
    use_calibrated: bool = False,
    features_mode: str = "small",
    per_size_calibration: bool = False,
    with_odds_aware: bool = False,
    seeds: list[int] | None = None,
) -> tuple[pd.DataFrame, dict]:
    """Run walk_forward_cv and return (predictions_df, cv_metrics).

    When ``use_calibrated`` is True, swaps lambdarank for binary +
    isotonic calibration so ``pred_prob`` is a calibrated probability
    in [0, 1] (no per-race softmax needed downstream).
    ``features_mode``: "small" (original 11-ish set) or "default"
    (catalog default ~34 IDs).
    ``per_size_calibration``: when True (and use_calibrated), swap the
    single global isotonic for one-per-field-size-bucket
    (8-12 / 13-16 / 17-18 head). field_size 列が cache に必要。
    ``with_odds_aware``: append log_win_odds / implied_prob / per-race
    log-odds gaps / fuku spread to the feature set. Filters cache to
    races where every horse has nonzero `win_odds` (~17K of ~29K races).
    Popularity is *not* added — the goal is partial market info, not
    rank leakage.
    ``seeds``: when provided as a list of >1 ints, runs walk_forward_cv
    once per seed and averages `pred_prob` per (race_key, horse_key).
    Reduces overfitting variance from feature/bagging sampling. Returns
    cv_metrics from the first seed (a representative single-model
    snapshot) plus an `ensemble.n_seeds` field.
    """
    df = pd.read_parquet(PARQUET, engine="pyarrow")
    # `select_columns` resolves selected feature IDs to column names via
    # the catalog, then filter_available_columns drops missing/sparse ones.
    selected = _resolve_features(features_mode)
    feature_cols = select_columns(selected)
    feature_cols = filter_available_columns(feature_cols, df)

    if with_odds_aware:
        # Drop races where any horse has missing odds (sentinel 0).
        valid_min = df.groupby("race_key")["win_odds"].transform("min")
        before = df["race_key"].nunique()
        df = df[valid_min > 0].copy()
        after = df["race_key"].nunique()
        print(f"odds-aware: filtered races with missing odds: {before} → {after}")
        df = add_odds_derived_features(df)
        added = [c for c in ODDS_DERIVED_COLUMNS if c in df.columns]
        feature_cols = list(dict.fromkeys(feature_cols + added))
        print(f"odds-aware: appended derived features {added}")
    print(f"Using {len(feature_cols)} features: {feature_cols[:8]}...")
    df = df.sort_values(["race_date", "race_key"]).reset_index(drop=True)

    if use_calibrated:
        kwargs: dict = {
            "objective_type": "binary",
            "calibration_method": "isotonic",
            "calibration_min_holdout_rows": 5000,
            "num_boost_round": 300,
            "early_stopping_rounds": 30,
        }
        if per_size_calibration:
            if "field_size" not in df.columns:
                raise SystemExit(
                    "per_size_calibration requested but feature cache lacks "
                    "field_size column"
                )
            kwargs["calibration_size_col"] = "field_size"
            kwargs["calibration_size_bins"] = [[1, 12], [13, 16], [17, 18]]
            kwargs["calibration_per_size_min_rows"] = 500
            print("Mode: BINARY + isotonic per field_size bucket (8-12 / 13-16 / 17-18)")
        else:
            print("Mode: BINARY + isotonic calibration (calibrated probability)")
    else:
        kwargs = {"num_boost_round": 300, "early_stopping_rounds": 30}
        print("Mode: LAMBDARANK (rank score, requires per-race softmax)")

    seeds_list = seeds or [42]
    if len(seeds_list) > 1:
        print(f"Ensemble mode: averaging predictions over {len(seeds_list)} "
              f"seeds {seeds_list}")
        per_seed_preds = []
        first_metrics = None
        for s in seeds_list:
            print(f"\n--- seed {s} ---")
            cfg = TrainConfig(**{**kwargs, "seed": s})
            cv = walk_forward_cv(df, feature_cols, config=cfg, n_folds=3)
            per_seed_preds.append(cv["predictions_df"][[
                "race_key", "horse_key", "pred_prob"
            ]].rename(columns={"pred_prob": f"pred_prob_seed_{s}"}))
            if first_metrics is None:
                first_metrics = cv.get("cv_metrics", {})
        merged = per_seed_preds[0]
        for p in per_seed_preds[1:]:
            merged = merged.merge(p, on=["race_key", "horse_key"], how="inner")
        prob_cols = [c for c in merged.columns if c.startswith("pred_prob_seed_")]
        merged["pred_prob"] = merged[prob_cols].mean(axis=1)
        # Re-attach aux cols (cv_fold, actual_win, etc.) from the
        # last-seed run. These are seed-invariant: walk_forward_cv splits
        # folds deterministically by sorted race_keys, so cv_fold is
        # identical across seeds; actual_win and other meta are just
        # row-level facts copied from val_df.
        last_seed_full = cv["predictions_df"][[
            c for c in cv["predictions_df"].columns
            if c not in ("pred_prob",)
        ]]
        predictions_df = merged.merge(
            last_seed_full, on=["race_key", "horse_key"], how="inner"
        )
        cv_metrics = dict(first_metrics or {})
        cv_metrics["ensemble"] = {"n_seeds": len(seeds_list), "seeds": seeds_list}
        # Recompute brier/auc/ece on the *ensemble* predictions.
        # First-seed metrics alone hide the bagging gain on extremes.
        # walk_forward_cv writes the binary label as `actual_win`
        # (1 if finish_order==1 else 0). target_win is a feature_builder
        # column, not part of the predictions output.
        label_col = "actual_win"
        if label_col in predictions_df.columns:
            ensemble_metrics = _eval_classification_metrics(
                predictions_df[label_col].values.astype(int),
                predictions_df["pred_prob"].values.astype(float),
            )
            cv_metrics["ensemble"]["pred_prob_brier"] = float(
                ensemble_metrics.get("val_brier", float("nan"))
            )
            cv_metrics["ensemble"]["pred_prob_auc"] = float(
                ensemble_metrics.get("val_auc", float("nan"))
            )
            cv_metrics["ensemble"]["pred_prob_ece"] = float(
                ensemble_metrics.get("val_ece", float("nan"))
            )
            cv_metrics["ensemble"]["pred_prob_logloss"] = float(
                ensemble_metrics.get("val_logloss", float("nan"))
            )
            print(
                f"Ensemble metrics: AUC={cv_metrics['ensemble']['pred_prob_auc']:.4f} "
                f"Brier={cv_metrics['ensemble']['pred_prob_brier']:.4f} "
                f"ECE={cv_metrics['ensemble']['pred_prob_ece']:.4f}"
            )
    else:
        config = TrainConfig(**{**kwargs, "seed": seeds_list[0]})
        cv = walk_forward_cv(df, feature_cols, config=config, n_folds=3)
        predictions_df = cv["predictions_df"]
        cv_metrics = cv.get("cv_metrics", {})
    print(f"Predictions: {len(predictions_df)} rows over "
          f"{predictions_df['race_key'].nunique()} races")
    return predictions_df, cv_metrics


def load_odds() -> pd.DataFrame:
    """Load TanOdds + FukuOdds keyed by (race_key, umaban) as float."""
    conn = sqlite3.connect(DB_PATH)
    odds = pd.read_sql(
        "SELECT RaceKey AS race_key, Umaban AS umaban, "
        "TanOdds AS tan_odds_raw, "
        "FukuOddsLow AS fuku_odds_low_raw, "
        "FukuOddsHigh AS fuku_odds_high_raw "
        "FROM N_ODDS_TANPUKU",
        conn,
    )
    conn.close()
    for c in ["tan_odds_raw", "fuku_odds_low_raw", "fuku_odds_high_raw"]:
        odds[c] = pd.to_numeric(odds[c], errors="coerce")
    odds["tan_odds"] = odds["tan_odds_raw"] / 10.0
    odds["fuku_odds_low"] = odds["fuku_odds_low_raw"] / 10.0
    odds["fuku_odds_high"] = odds["fuku_odds_high_raw"] / 10.0
    odds["umaban"] = pd.to_numeric(odds["umaban"], errors="coerce").astype("Int64")
    return odds[["race_key", "umaban", "tan_odds",
                 "fuku_odds_low", "fuku_odds_high"]]


def join_predictions_with_odds(preds: pd.DataFrame) -> pd.DataFrame:
    odds = load_odds()
    pq = pd.read_parquet(PARQUET, engine="pyarrow",
                          columns=["race_key", "horse_key", "umaban"])
    pq["umaban"] = pd.to_numeric(pq["umaban"], errors="coerce").astype("Int64")
    pq = pq.drop_duplicates(["race_key", "horse_key"])
    merged = preds.merge(pq, on=["race_key", "horse_key"], how="left")
    merged = merged.merge(odds, on=["race_key", "umaban"], how="left")
    matched = merged["tan_odds"].notna().sum()
    print(f"Odds matched: {matched}/{len(merged)} "
          f"({100 * matched / len(merged):.1f}%)")
    return merged


def softmax_per_race(df: pd.DataFrame) -> pd.DataFrame:
    """Convert raw lambdarank scores → probabilities per race via softmax.

    Note: lambdarank emits an unbounded rank score, NOT a calibrated
    probability. The softmax here is a heuristic to feed `pred_prob_norm`
    into EV-style filters. Use the calibrated binary path
    (`--use-calibrated`) for genuine probability semantics.
    """
    df = df.copy()
    df["pred_exp"] = (df.groupby("race_key")["pred_prob"]
                      .transform(lambda s: (s - s.max()).clip(-50)).pipe(
                          lambda s: s.values
                      ))
    df["pred_exp"] = np.exp(df["pred_exp"])
    df["pred_prob_norm"] = df["pred_exp"] / df.groupby("race_key")["pred_exp"].transform("sum")
    df["actual_in3"] = (df["finish_order"] <= 3).astype(int)
    return df


def passthrough_calibrated(df: pd.DataFrame) -> pd.DataFrame:
    """For calibrated binary output, pred_prob is already a calibrated
    probability — copy it into pred_prob_norm so downstream EV columns
    treat it as the per-horse win probability."""
    df = df.copy()
    df["pred_prob_norm"] = df["pred_prob"]
    df["actual_in3"] = (df["finish_order"] <= 3).astype(int)
    return df


def evaluate_strategy(df: pd.DataFrame, name: str, mask: pd.Series,
                      odds_col: str = "tan_odds",
                      win_col: str = "actual_win") -> dict:
    """Compute ROI / hit rate for the rows where `mask` is True."""
    bets = df.loc[mask].copy()
    n = len(bets)
    if n == 0:
        return {"strategy": name, "n_bets": 0, "n_hits": 0,
                "hit_rate": 0, "roi": 0}
    bets["payout"] = bets[win_col] * bets[odds_col] * 100  # JPY100 bet
    bets["payout"] = bets["payout"].fillna(0)
    bet_total = n * 100
    payout_total = bets["payout"].sum()
    n_hits = int(bets[win_col].fillna(0).sum())
    return {
        "strategy": name,
        "n_bets": n,
        "n_hits": n_hits,
        "hit_rate": round(100 * n_hits / n, 2),
        "roi_pct": round(100 * (payout_total - bet_total) / bet_total, 2),
        "avg_odds": round(bets[odds_col].mean(), 2),
    }


def _strategy_suffix(use_calibrated: bool) -> str:
    """Append 'c' to strategy IDs when running on calibrated probabilities
    so compare_ev_strategies.py can join calibrated vs uncalibrated rows.
    """
    return "c" if use_calibrated else ""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--use-calibrated",
        action="store_true",
        help="Use calibrated binary classifier instead of lambdarank+softmax",
    )
    parser.add_argument(
        "--save-results",
        type=str,
        default=None,
        help="Path to write strategy results JSON for compare_ev_strategies.py",
    )
    parser.add_argument(
        "--features",
        type=str,
        default="small",
        choices=("small", "default"),
        help="Feature preset: 'small' (~11 from first-round exploration) "
        "or 'default' (catalog default ~34, no odds-derived leak risk)",
    )
    parser.add_argument(
        "--per-size-calibration",
        action="store_true",
        help="Use one isotonic per field_size bucket (8-12 / 13-16 / "
        "17-18). Requires --use-calibrated and field_size in cache.",
    )
    parser.add_argument(
        "--with-odds-aware",
        action="store_true",
        help="Append odds-derived features (log_win_odds, implied_prob, "
        "log_odds_gap_to_fav/mean, fuku_odds_uncertainty). Filters cache "
        "to races with valid odds (~17K of ~29K). Popularity is NOT added.",
    )
    parser.add_argument(
        "--seeds",
        type=str,
        default="42",
        help="Comma-separated LightGBM seeds. >1 enables ensemble: each "
        "seed trains its own walk_forward_cv pass and pred_prob is "
        "averaged per (race_key, horse_key). Default '42' = single model.",
    )
    args = parser.parse_args()
    try:
        seeds_list = [int(s.strip()) for s in args.seeds.split(",") if s.strip()]
    except ValueError as e:
        parser.error(f"--seeds must be comma-separated integers: {e}")
    if not seeds_list:
        parser.error(
            "--seeds must contain at least one integer (got empty list)"
        )

    print(f"DB:     {DB_PATH}")
    print(f"Cache:  {PARQUET}\n")

    preds, cv_metrics = load_predictions(
        use_calibrated=args.use_calibrated,
        features_mode=args.features,
        per_size_calibration=args.per_size_calibration,
        with_odds_aware=args.with_odds_aware,
        seeds=seeds_list,
    )
    df = join_predictions_with_odds(preds)
    if args.use_calibrated:
        df = passthrough_calibrated(df)
    else:
        df = softmax_per_race(df)
    sfx = _strategy_suffix(args.use_calibrated)
    df["ev_tan"] = df["pred_prob_norm"] * df["tan_odds"]
    # Use mid of fuku odds range as approximation for place bet EV
    df["fuku_odds_mid"] = (df["fuku_odds_low"] + df["fuku_odds_high"]) / 2
    # Upper-bound proxy for "top-3 finish probability". Multiplying win
    # probability by 3 then clipping to 0.95 deliberately overestimates
    # for strong horses (≥0.32 win prob saturates at 0.95). Useful only
    # as a relative ranking signal for ev_fuku filters; do NOT interpret
    # the absolute value as a calibrated top-3 probability.
    df["pred_prob_top3_approx"] = (df["pred_prob_norm"] * 3).clip(upper=0.95)
    df["ev_fuku"] = df["pred_prob_top3_approx"] * df["fuku_odds_mid"]

    # Mark top-1 / top-by-EV per race
    df["rank_pred"] = df.groupby("race_key")["pred_prob"].rank(
        ascending=False, method="first")
    df["rank_ev_tan"] = df.groupby("race_key")["ev_tan"].rank(
        ascending=False, method="first")

    print("\n=== TANSHO strategies (JPY100/bet) ===")
    tansho_results = [
        evaluate_strategy(df, "T1: top-1 by pred (current)",
                          df["rank_pred"] == 1),
        evaluate_strategy(df, "T2: rank_pred<=2 AND tan_odds>=3",
                          (df["rank_pred"] <= 2) & (df["tan_odds"] >= 3)),
        evaluate_strategy(df, "T3: rank_pred<=2 AND tan_odds>=5",
                          (df["rank_pred"] <= 2) & (df["tan_odds"] >= 5)),
        evaluate_strategy(df, "T4: rank_pred<=3 AND tan_odds>=5",
                          (df["rank_pred"] <= 3) & (df["tan_odds"] >= 5)),
        evaluate_strategy(df, "T5: rank_pred<=3 AND tan_odds 5-15",
                          (df["rank_pred"] <= 3)
                          & (df["tan_odds"].between(5, 15))),
        evaluate_strategy(df, "T6: rank_pred<=5 AND tan_odds 7-20",
                          (df["rank_pred"] <= 5)
                          & (df["tan_odds"].between(7, 20))),
        evaluate_strategy(df, "T7: rank_pred<=3 AND tan_odds 5-30",
                          (df["rank_pred"] <= 3)
                          & (df["tan_odds"].between(5, 30))),
        evaluate_strategy(df, "T8: rank_pred<=2 AND tan_odds 4-12",
                          (df["rank_pred"] <= 2)
                          & (df["tan_odds"].between(4, 12))),
    ]

    out = pd.DataFrame(tansho_results)
    print(out.to_string(index=False))

    print("\n=== EV-filtered TANSHO strategies (find mid-prob high-EV) ===")
    # rank_pred is rank by raw lambdarank score → use as proxy for "predicted strength"
    # ev_tan = pred_prob_norm * tan_odds → only meaningful as relative ranking
    # The user's hypothesis: "予測勝率は悪くないのに期待値高い馬" = mid-rank + high-EV
    ev_results = [
        evaluate_strategy(df, f"E1{sfx}: ev_tan>=1.2 (any rank)",
                          df["ev_tan"] >= 1.2),
        evaluate_strategy(df, f"E2{sfx}: ev_tan>=1.5 (any rank)",
                          df["ev_tan"] >= 1.5),
        evaluate_strategy(df, f"E3{sfx}: ev_tan>=2.0 (any rank)",
                          df["ev_tan"] >= 2.0),
        # Mid-rank + high-EV (the user's "穴馬じゃないけど期待値高い"):
        evaluate_strategy(df, f"E4{sfx}: rank 2-4 AND ev_tan>=1.2",
                          (df["rank_pred"].between(2, 4)) & (df["ev_tan"] >= 1.2)),
        evaluate_strategy(df, f"E5{sfx}: rank 2-4 AND ev_tan>=1.5",
                          (df["rank_pred"].between(2, 4)) & (df["ev_tan"] >= 1.5)),
        evaluate_strategy(df, f"E6{sfx}: rank 2-3 AND ev_tan>=1.0",
                          (df["rank_pred"].between(2, 3)) & (df["ev_tan"] >= 1.0)),
        evaluate_strategy(df, f"E7{sfx}: rank 2-3 AND ev_tan>=1.3",
                          (df["rank_pred"].between(2, 3)) & (df["ev_tan"] >= 1.3)),
        # Anti-favorite: skip top-1, take next ev_tan winner
        evaluate_strategy(df, f"E8{sfx}: rank>=2 AND rank_ev_tan==1",
                          (df["rank_pred"] >= 2) & (df["rank_ev_tan"] == 1)),
    ]
    out_ev = pd.DataFrame(ev_results)
    print(out_ev.to_string(index=False))

    print("\n=== EV-filtered FUKUSHO strategies ===")
    ev_fuku_results = [
        evaluate_strategy(df, "EF1: ev_fuku>=1.0 AND rank<=3",
                          (df["ev_fuku"] >= 1.0) & (df["rank_pred"] <= 3),
                          odds_col="fuku_odds_low",
                          win_col="actual_in3"),
        evaluate_strategy(df, "EF2: ev_fuku>=1.2 AND rank<=3",
                          (df["ev_fuku"] >= 1.2) & (df["rank_pred"] <= 3),
                          odds_col="fuku_odds_low",
                          win_col="actual_in3"),
        evaluate_strategy(df, "EF3: rank 2-4 AND ev_fuku>=1.0",
                          (df["rank_pred"].between(2, 4)) & (df["ev_fuku"] >= 1.0),
                          odds_col="fuku_odds_low",
                          win_col="actual_in3"),
        evaluate_strategy(df, "EF4: rank 2-3 AND ev_fuku>=1.0",
                          (df["rank_pred"].between(2, 3)) & (df["ev_fuku"] >= 1.0),
                          odds_col="fuku_odds_low",
                          win_col="actual_in3"),
    ]
    out_ev_fuku = pd.DataFrame(ev_fuku_results)
    print(out_ev_fuku.to_string(index=False))

    print("\n=== FUKUSHO strategies (JPY100/bet, conservative payout=fuku_odds_low) ===")
    fukusho_results = [
        evaluate_strategy(df, "F1: top-1 by pred (place bet)",
                          df["rank_pred"] == 1,
                          odds_col="fuku_odds_low",
                          win_col="actual_in3"),
        evaluate_strategy(df, "F2: top-2 by pred (place bet)",
                          df["rank_pred"] <= 2,
                          odds_col="fuku_odds_low",
                          win_col="actual_in3"),
        evaluate_strategy(df, "F3: top-3 by pred (place bet)",
                          df["rank_pred"] <= 3,
                          odds_col="fuku_odds_low",
                          win_col="actual_in3"),
        evaluate_strategy(df, "F4: rank_pred<=2 AND fuku_low>=2",
                          (df["rank_pred"] <= 2)
                          & (df["fuku_odds_low"] >= 2.0),
                          odds_col="fuku_odds_low",
                          win_col="actual_in3"),
        evaluate_strategy(df, "F5: rank_pred<=3 AND fuku_low>=2",
                          (df["rank_pred"] <= 3)
                          & (df["fuku_odds_low"] >= 2.0),
                          odds_col="fuku_odds_low",
                          win_col="actual_in3"),
        evaluate_strategy(df, "F6: rank_pred<=3 AND fuku_low>=3",
                          (df["rank_pred"] <= 3)
                          & (df["fuku_odds_low"] >= 3.0),
                          odds_col="fuku_odds_low",
                          win_col="actual_in3"),
        evaluate_strategy(df, "F7: rank_pred<=5 AND fuku_low 2-10",
                          (df["rank_pred"] <= 5)
                          & (df["fuku_odds_low"].between(2, 10)),
                          odds_col="fuku_odds_low",
                          win_col="actual_in3"),
    ]
    out2 = pd.DataFrame(fukusho_results)
    print(out2.to_string(index=False))

    print("\n=== Key context ===")
    print(f"Total predictions with odds: {df['tan_odds'].notna().sum()}")
    print(f"Total predictions: {len(df)}")
    print(f"Top1 hit rate (overall): {df.loc[df['rank_pred']==1, 'actual_win'].mean()*100:.2f}%")
    print(f"Top1 in3 rate (overall): {df.loc[df['rank_pred']==1, 'actual_in3'].mean()*100:.2f}%")
    print(f"Top3 in3 rate (per horse): {df.loc[df['rank_pred']<=3, 'actual_in3'].mean()*100:.2f}%")

    if args.save_results:
        out_path = Path(args.save_results)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "mode": "calibrated_binary" if args.use_calibrated else "lambdarank_softmax",
            "calibration_method": "isotonic" if args.use_calibrated else None,
            "features_mode": args.features,
            "per_size_calibration": bool(args.per_size_calibration),
            "with_odds_aware": bool(args.with_odds_aware),
            "seeds": seeds_list,
            "n_seeds": len(seeds_list),
            "cv_metrics": cv_metrics,
            "n_predictions": int(len(df)),
            "n_with_odds": int(df["tan_odds"].notna().sum()),
            "n_races": int(df["race_key"].nunique()),
            "tansho": tansho_results,
            "ev_tansho": ev_results,
            "ev_fukusho": ev_fuku_results,
            "fukusho": fukusho_results,
        }
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
        print(f"\nResults saved to: {out_path}")


if __name__ == "__main__":
    main()

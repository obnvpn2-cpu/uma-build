"""Side-by-side comparison of EV strategies: lambdarank-softmax vs calibrated.

Loads two JSON files written by ``explore_ev_strategy.py --save-results``
and prints a comparison table per strategy bucket (tansho / ev_tansho /
fukusho / ev_fukusho).

Usage:
    cd backend && python scripts/compare_ev_strategies.py \\
        --baseline data/ev_strategy_lambdarank.json \\
        --candidate data/ev_strategy_calibrated.json
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def _strip_calibrated_suffix(name: str) -> str:
    """Remove the trailing 'c' added by explore_ev_strategy in calibrated
    mode so calibrated and uncalibrated strategy names line up.

    Example: "E1c: ev_tan>=1.2" → "E1: ev_tan>=1.2"
    """
    return re.sub(r"^([A-Z]+\d+)c:", r"\1:", name)


def _to_df(records: list, label: str) -> pd.DataFrame:
    df = pd.DataFrame(records)
    if df.empty:
        return df
    df["strategy"] = df["strategy"].map(_strip_calibrated_suffix)
    df = df.rename(columns={
        "n_bets": f"{label}_n_bets",
        "n_hits": f"{label}_n_hits",
        "hit_rate": f"{label}_hit_rate",
        "roi_pct": f"{label}_roi_pct",
        "avg_odds": f"{label}_avg_odds",
    })
    return df


def _compare_bucket(baseline: dict, candidate: dict, key: str) -> pd.DataFrame:
    base = _to_df(baseline.get(key, []), "base")
    cand = _to_df(candidate.get(key, []), "cand")
    if base.empty or cand.empty:
        return pd.DataFrame()
    merged = base.merge(cand, on="strategy", how="outer")
    # Compute ROI delta (candidate − baseline) in percentage points
    merged["roi_delta_pp"] = (
        merged["cand_roi_pct"] - merged["base_roi_pct"]
    ).round(2)
    cols = [
        "strategy",
        "base_n_bets", "cand_n_bets",
        "base_hit_rate", "cand_hit_rate",
        "base_roi_pct", "cand_roi_pct", "roi_delta_pp",
    ]
    return merged[cols]


def _summarise_cv(label: str, payload: dict) -> str:
    """One-line CV summary suitable for the header."""
    cv = payload.get("cv_metrics") or {}
    mode = payload.get("mode", "?")
    parts = [f"{label} ({mode})"]
    for k in ("auc_mean", "brier_mean", "ece_mean",
              "ndcg1_mean", "ndcg3_mean"):
        if k in cv:
            parts.append(f"{k}={cv[k]:.4f}")
    if "calibration_post_brier_mean" in cv:
        parts.append(
            "calibrated_brier "
            f"{cv['calibration_pre_brier_mean']:.4f}→"
            f"{cv['calibration_post_brier_mean']:.4f}"
        )
    return "  ".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--baseline",
        type=str,
        default=str(ROOT / "data" / "ev_strategy_lambdarank.json"),
        help="JSON from `explore_ev_strategy.py` (no --use-calibrated)",
    )
    parser.add_argument(
        "--candidate",
        type=str,
        default=str(ROOT / "data" / "ev_strategy_calibrated.json"),
        help="JSON from `explore_ev_strategy.py --use-calibrated`",
    )
    args = parser.parse_args()

    baseline_path = Path(args.baseline)
    candidate_path = Path(args.candidate)
    if not baseline_path.exists() or not candidate_path.exists():
        missing = [p for p in (baseline_path, candidate_path) if not p.exists()]
        raise SystemExit(f"Missing input files: {missing}")

    with open(baseline_path, "r", encoding="utf-8") as f:
        baseline = json.load(f)
    with open(candidate_path, "r", encoding="utf-8") as f:
        candidate = json.load(f)

    print("=== CV summary ===")
    print(_summarise_cv("baseline ", baseline))
    print(_summarise_cv("candidate", candidate))
    print()

    for bucket in ("tansho", "ev_tansho", "ev_fukusho", "fukusho"):
        df = _compare_bucket(baseline, candidate, bucket)
        if df.empty:
            continue
        print(f"=== {bucket} ===")
        print(df.to_string(index=False))
        print()

    # Surface biggest movers across buckets
    print("=== Top 5 ROI improvements (candidate − baseline) ===")
    all_rows = []
    for bucket in ("tansho", "ev_tansho", "ev_fukusho", "fukusho"):
        df = _compare_bucket(baseline, candidate, bucket)
        if df.empty:
            continue
        df = df.copy()
        df["bucket"] = bucket
        all_rows.append(df)
    if all_rows:
        combined = pd.concat(all_rows, ignore_index=True)
        top = combined.sort_values("roi_delta_pp", ascending=False).head(5)
        print(top[["bucket", "strategy", "base_roi_pct",
                   "cand_roi_pct", "roi_delta_pp"]].to_string(index=False))


if __name__ == "__main__":
    main()

"""Equivalence + boundary tests for the vectorised as-of feature path.

The vectorised `_compute_as_of_features` (production) is verified against
a slow O(N²) per-row reference implementation kept in this file. The
reference is the original pre-vectorisation code, retained as a test
oracle so any future regression in the vectorised path is caught.
"""

from __future__ import annotations

import os
import sys
import time
from datetime import date, timedelta
from typing import Dict, Optional

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from services.feature_builder import (  # noqa: E402
    _classify_running_style,
    _compute_as_of_features,
    _distance_category,
    _safe_float,
)

# All horse-block features the equivalence test is responsible for.
HORSE_FEATURES = [
    "horse_n_starts", "horse_n_wins", "horse_win_rate", "horse_in3_rate",
    "horse_avg_finish", "horse_dist_win_rate", "horse_dist_in3_rate",
    "horse_surface_win_rate", "horse_surface_in3_rate", "horse_course_win_rate",
    "horse_recent3_avg", "horse_recent5_avg", "horse_recent3_win_rate",
    "horse_days_since_last", "horse_last_finish",
    "horse_avg_weight", "weight_dev_from_avg", "weight_trend_3", "abs_weight_diff",
    "horse_avg_corner3", "horse_avg_corner4",
    "horse_avg_last3f", "horse_best_last3f",
    "horse_avg_position_change", "horse_running_style",
    "horse_last3f_rank_avg", "horse_recent3_last3f",
    "horse_total_prize", "horse_avg_prize",
    "horse_max_grade", "horse_grade_n_starts", "horse_grade_win_rate",
    "horse_class_change", "horse_prize_rank_in_field",
    "horse_earnings_per_start",
]

# Per-feature tolerances. Defaults are tight; cumsum-cancellation-prone
# columns get loosened. Integer-valued columns assert exact equality.
TOLERANCES: Dict[str, Dict[str, float]] = {
    "default": dict(rtol=1e-7, atol=1e-9),
    "horse_total_prize": dict(rtol=1e-5, atol=1e-3),
    "horse_avg_prize": dict(rtol=1e-5, atol=1e-3),
    "horse_earnings_per_start": dict(rtol=1e-5, atol=1e-3),
    "weight_trend_3": dict(rtol=1e-6, atol=1e-9),
    "horse_n_starts": dict(rtol=0.0, atol=0.0),
    "horse_n_wins": dict(rtol=0.0, atol=0.0),
    "horse_grade_n_starts": dict(rtol=0.0, atol=0.0),
}

CANONICAL_COL = {
    "race_key": "race_key",
    "horse_key": "horse_key",
    "race_date": "race_date",
    "finish_order": "finish_order",
    "distance": "distance",
    "track_type": "track_type",
    "track_condition": None,
    "grade": "grade",
    "race_class": None,
    "field_size": "field_size",
    "place": "place",
    "time": None,
    "last3f": "last3f",
    "passing_order": None,
    "corner3": "corner3",
    "corner4": "corner4",
    "win_odds": None,
    "popularity": None,
    "body_weight": "body_weight",
    "body_weight_diff": "body_weight_diff",
    "jockey_code": "jockey_code",
    "trainer_code": "trainer_code",
    "waku": None,
    "weight_carried": None,
    "age": None,
    "sex": None,
    "prize_money": "prize_money",
}


# ---------------------------------------------------------------------------
# Legacy reference implementation (slow O(N²); test oracle only)
# ---------------------------------------------------------------------------


def _legacy_horse_stats(df: pd.DataFrame, col: Dict[str, Optional[str]]) -> None:
    """Slow per-horse / per-row reference. Modifies df in place."""
    c_horse_key = col.get("horse_key")
    c_distance = col.get("distance")
    c_surface = col.get("track_type")
    c_place = col.get("place")
    c_finish = col.get("finish_order")
    c_body_weight = col.get("body_weight")
    c_body_weight_diff = col.get("body_weight_diff")
    c_field_size = col.get("field_size")
    c_grade = col.get("grade")

    for _horse_id, horse_df in df.groupby(c_horse_key):
        indices = horse_df.index.tolist()
        if len(indices) == 0:
            continue

        for pos, i in enumerate(indices):
            past = horse_df.iloc[:pos]
            if len(past) == 0:
                continue

            n_starts = len(past)
            n_wins = int(past["_is_win"].sum())
            df.at[i, "horse_n_starts"] = n_starts
            df.at[i, "horse_n_wins"] = n_wins
            df.at[i, "horse_win_rate"] = n_wins / n_starts if n_starts > 0 else 0.0
            df.at[i, "horse_in3_rate"] = past["_is_in3"].mean()
            df.at[i, "horse_avg_finish"] = past["_finish"].mean()

            if c_distance and "_dist_cat" in df.columns:
                current_dist_cat = df.at[i, "_dist_cat"]
                if current_dist_cat is not None:
                    dist_past = past[past["_dist_cat"] == current_dist_cat]
                    if len(dist_past) > 0:
                        df.at[i, "horse_dist_win_rate"] = dist_past["_is_win"].mean()
                        df.at[i, "horse_dist_in3_rate"] = dist_past["_is_in3"].mean()

            if c_surface:
                current_surface = df.at[i, c_surface]
                surface_past = past[past[c_surface] == current_surface]
                if len(surface_past) > 0:
                    df.at[i, "horse_surface_win_rate"] = surface_past["_is_win"].mean()
                    df.at[i, "horse_surface_in3_rate"] = surface_past["_is_in3"].mean()

            if c_place:
                current_place = df.at[i, c_place]
                course_past = past[past[c_place] == current_place]
                if len(course_past) > 0:
                    df.at[i, "horse_course_win_rate"] = course_past["_is_win"].mean()

            recent3 = past.tail(3)
            recent5 = past.tail(5)
            df.at[i, "horse_recent3_avg"] = recent3["_finish"].mean()
            df.at[i, "horse_recent5_avg"] = recent5["_finish"].mean()
            df.at[i, "horse_recent3_win_rate"] = recent3["_is_win"].mean()
            df.at[i, "horse_last_finish"] = past.iloc[-1]["_finish"]

            if "_race_date_dt" in df.columns:
                current_date = df.at[i, "_race_date_dt"]
                last_date = past.iloc[-1]["_race_date_dt"]
                if pd.notna(current_date) and pd.notna(last_date):
                    df.at[i, "horse_days_since_last"] = (current_date - last_date).days

            if c_body_weight and "_body_weight" in df.columns:
                past_weights = past["_body_weight"].dropna()
                if len(past_weights) > 0:
                    avg_w = past_weights.mean()
                    df.at[i, "horse_avg_weight"] = avg_w
                    current_w = df.at[i, "_body_weight"]
                    if pd.notna(current_w):
                        df.at[i, "weight_dev_from_avg"] = current_w - avg_w
                if len(past_weights) >= 3:
                    last3_weights = past_weights.tail(3)
                    x = np.arange(len(last3_weights), dtype=float)
                    y = last3_weights.values.astype(float)
                    if np.std(x) > 0:
                        slope = np.polyfit(x, y, 1)[0]
                        df.at[i, "weight_trend_3"] = slope

            if c_body_weight_diff and "_body_weight_diff" in df.columns:
                bwd = df.at[i, "_body_weight_diff"]
                if pd.notna(bwd):
                    df.at[i, "abs_weight_diff"] = abs(bwd)

            if "_corner3" in df.columns:
                past_c3 = past["_corner3"].dropna()
                if len(past_c3) > 0:
                    df.at[i, "horse_avg_corner3"] = past_c3.mean()

            if "_corner4" in df.columns:
                past_c4 = past["_corner4"].dropna()
                if len(past_c4) > 0:
                    df.at[i, "horse_avg_corner4"] = past_c4.mean()
                    if c_field_size and "_field_size" in df.columns:
                        avg_fs = past["_field_size"].dropna().mean()
                        if avg_fs > 0:
                            pct = past_c4.mean() / avg_fs
                            df.at[i, "horse_running_style"] = _classify_running_style(pct)

            if "_last3f" in df.columns:
                past_l3 = past["_last3f"].dropna()
                if len(past_l3) > 0:
                    df.at[i, "horse_avg_last3f"] = past_l3.mean()
                    df.at[i, "horse_best_last3f"] = past_l3.min()
                recent3_l3 = past.tail(3)["_last3f"].dropna()
                if len(recent3_l3) > 0:
                    df.at[i, "horse_recent3_last3f"] = recent3_l3.mean()

            if "_corner4" in df.columns:
                past_both = past[["_corner4", "_finish"]].dropna()
                if len(past_both) > 0:
                    changes = past_both["_corner4"] - past_both["_finish"]
                    df.at[i, "horse_avg_position_change"] = changes.mean()

            if "_prize" in df.columns:
                past_prize = past["_prize"].dropna()
                if len(past_prize) > 0:
                    df.at[i, "horse_total_prize"] = past_prize.sum()
                    df.at[i, "horse_avg_prize"] = past_prize.mean()
                    df.at[i, "horse_earnings_per_start"] = past_prize.sum() / n_starts

            if c_grade:
                past_grade = past[past[c_grade].notna()]
                grade_numeric = _safe_float(past_grade[c_grade])
                grade_valid = grade_numeric.dropna()
                if len(grade_valid) > 0:
                    df.at[i, "horse_max_grade"] = grade_valid.min()
                graded = past_grade[grade_numeric <= 3]
                df.at[i, "horse_grade_n_starts"] = len(graded)
                if len(graded) > 0:
                    graded_finish = _safe_float(graded[c_finish])
                    df.at[i, "horse_grade_win_rate"] = (graded_finish == 1).mean()


def _legacy_class_change(df: pd.DataFrame, col: Dict[str, Optional[str]]) -> None:
    """Reference class_change implementation. Modifies df in place."""
    c_horse_key = col.get("horse_key")
    c_grade = col.get("grade")
    if not c_grade:
        return
    for _horse_id, horse_df in df.groupby(c_horse_key):
        indices = horse_df.index.tolist()
        for pos, i in enumerate(indices):
            if pos == 0:
                continue
            prev_grade = _safe_float(pd.Series([horse_df.iloc[pos - 1][c_grade]])).iloc[0]
            curr_grade = _safe_float(pd.Series([df.at[i, c_grade]])).iloc[0]
            if pd.notna(prev_grade) and pd.notna(curr_grade):
                df.at[i, "horse_class_change"] = prev_grade - curr_grade


def _legacy_last3f_rank(df: pd.DataFrame, col: Dict[str, Optional[str]]) -> None:
    """Reference last3f rank implementation. Modifies df in place."""
    c_horse_key = col.get("horse_key")
    c_race_key = col.get("race_key")
    if not c_race_key or "_last3f" not in df.columns:
        return
    df["_last3f_rank"] = np.nan
    for _race_id, race_df in df.groupby(c_race_key):
        l3 = race_df["_last3f"].dropna()
        if len(l3) > 0:
            ranks = l3.rank(ascending=True, method="min")
            df.loc[ranks.index, "_last3f_rank"] = ranks

    for _horse_id, horse_df in df.groupby(c_horse_key):
        indices = horse_df.index.tolist()
        for pos, i in enumerate(indices):
            past = horse_df.iloc[:pos]
            if len(past) > 0:
                past_ranks = past["_last3f_rank"].dropna()
                if len(past_ranks) > 0:
                    df.at[i, "horse_last3f_rank_avg"] = past_ranks.mean()


def _compute_as_of_features_legacy(
    df_in: pd.DataFrame, col: Dict[str, Optional[str]]
) -> pd.DataFrame:
    """Test-only orchestrator that mirrors the production setup but routes
    horse-block / class-change / last3f-rank through the slow legacy helpers.

    Agent (jockey/trainer) stats are intentionally skipped — they don't
    influence horse_* features and aren't part of the equivalence contract.
    """
    df = df_in.copy()
    c_race_key = col.get("race_key")
    c_horse_key = col.get("horse_key")
    c_race_date = col.get("race_date")
    c_finish = col.get("finish_order")
    if not all([c_race_key, c_horse_key, c_race_date, c_finish]):
        return df

    sort_keys = [c_race_date]
    if c_race_key:
        sort_keys.append(c_race_key)
    df = df.sort_values(sort_keys, kind="mergesort").reset_index(drop=True)

    df["_finish"] = _safe_float(df[c_finish])
    df["_is_win"] = (df["_finish"] == 1).astype(float)
    df["_is_in3"] = (df["_finish"] <= 3).astype(float)

    c_distance = col.get("distance")
    c_last3f = col.get("last3f")
    c_corner3 = col.get("corner3")
    c_corner4 = col.get("corner4")
    c_body_weight = col.get("body_weight")
    c_body_weight_diff = col.get("body_weight_diff")
    c_prize = col.get("prize_money")
    c_field_size = col.get("field_size")
    c_grade = col.get("grade")

    if c_distance:
        df["_distance"] = _safe_float(df[c_distance])
        df["_dist_cat"] = df["_distance"].apply(
            lambda x: _distance_category(x) if pd.notna(x) else None
        )
    if c_last3f:
        df["_last3f"] = _safe_float(df[c_last3f])
    if c_corner3:
        df["_corner3"] = _safe_float(df[c_corner3])
    if c_corner4:
        df["_corner4"] = _safe_float(df[c_corner4])
    if c_body_weight:
        df["_body_weight"] = _safe_float(df[c_body_weight])
    if c_body_weight_diff:
        df["_body_weight_diff"] = _safe_float(df[c_body_weight_diff])
    if c_prize:
        df["_prize"] = _safe_float(df[c_prize])
    if c_field_size:
        df["_field_size"] = _safe_float(df[c_field_size])

    horse_result_cols = [
        "horse_n_starts", "horse_n_wins", "horse_win_rate", "horse_in3_rate",
        "horse_avg_finish",
        "horse_dist_win_rate", "horse_dist_in3_rate",
        "horse_surface_win_rate", "horse_surface_in3_rate",
        "horse_course_win_rate",
        "horse_recent3_avg", "horse_recent5_avg", "horse_recent3_win_rate",
        "horse_days_since_last", "horse_last_finish",
        "horse_avg_weight", "weight_dev_from_avg", "weight_trend_3", "abs_weight_diff",
        "horse_avg_corner3", "horse_avg_corner4",
        "horse_avg_last3f", "horse_best_last3f",
        "horse_avg_position_change", "horse_running_style",
        "horse_last3f_rank_avg", "horse_recent3_last3f",
        "horse_total_prize", "horse_avg_prize",
        "horse_max_grade", "horse_grade_n_starts", "horse_grade_win_rate",
        "horse_class_change", "horse_prize_rank_in_field",
        "horse_earnings_per_start",
    ]
    for rc in horse_result_cols:
        df[rc] = np.nan

    df["_race_date_dt"] = pd.to_datetime(df[c_race_date], errors="coerce")

    _legacy_horse_stats(df, col)

    if c_grade:
        _legacy_class_change(df, col)
    if "horse_total_prize" in df.columns and c_race_key:
        for _race_id, race_df in df.groupby(c_race_key):
            prizes = race_df["horse_total_prize"].dropna()
            if len(prizes) > 0:
                ranks = prizes.rank(ascending=False, method="min")
                df.loc[ranks.index, "horse_prize_rank_in_field"] = ranks
    if "_last3f" in df.columns and c_race_key:
        _legacy_last3f_rank(df, col)

    temp_cols = [c for c in df.columns if c.startswith("_")]
    df = df.drop(columns=temp_cols, errors="ignore")
    return df


# ---------------------------------------------------------------------------
# Synthetic data generator
# ---------------------------------------------------------------------------


def _make_synth_df(seed: int = 7) -> pd.DataFrame:
    """Build a stratified synthetic dataset that exercises every code path.

    Coverage:
      - starts ∈ {1, 2, 3, 4, 5, 7, 15} with ≥5 horses each
      - 30% of horses have a NaN distance (None _dist_cat)
      - same-race / same-day pairs (sort tiebreak)
      - last3f ties within races (rank tie-break)
      - string grade ('G1', 'G2') in 5% of rows
      - 3 horses with all-NaN body_weight (Cat G drop-out)
      - 1 horse with exactly 3 valid weights (Cat G boundary)
      - races with field_size 3 / 8 / 18 / 0
    """
    rng = np.random.RandomState(seed)
    horses: list[dict] = []
    horse_id = 0
    starts_strata = [1, 2, 3, 4, 5, 7, 15]
    horses_per_stratum = 6  # 7 * 6 = 42 horses
    for n_starts in starts_strata:
        for _ in range(horses_per_stratum):
            horses.append({"id": f"H{horse_id:04d}", "n_starts": n_starts})
            horse_id += 1

    # Add 3 all-NaN-weight horses, 1 exactly-3-weights horse
    horses.append({"id": f"H{horse_id:04d}", "n_starts": 5, "all_nan_weight": True})
    horse_id += 1
    horses.append({"id": f"H{horse_id:04d}", "n_starts": 5, "all_nan_weight": True})
    horse_id += 1
    horses.append({"id": f"H{horse_id:04d}", "n_starts": 5, "all_nan_weight": True})
    horse_id += 1
    horses.append({"id": f"H{horse_id:04d}", "n_starts": 4, "exactly_3_weights": True})
    horse_id += 1

    base_date = date(2024, 1, 1)
    rows: list[dict] = []
    surfaces = [1, 2]
    distances = [1200, 1400, 1600, 1800, 2000, 2400]
    places = ["05", "06", "07", "08", "09"]
    grades_int = [1, 2, 3, 4, 5, np.nan]
    grades_str = ["G1", "G2"]

    for h_idx, h in enumerate(horses):
        race_idx = 0
        # 30% of horses get all-NaN distance (None _dist_cat)
        nan_distance = (h_idx % 10) < 3
        for s in range(h["n_starts"]):
            race_date = base_date + timedelta(days=14 * race_idx + (h_idx % 7))
            race_idx += 1
            distance = float("nan") if nan_distance else int(rng.choice(distances))
            grade_val = (
                rng.choice(grades_str) if rng.random() < 0.05
                else rng.choice(grades_int)
            )
            body_weight = rng.uniform(440, 520)
            if h.get("all_nan_weight"):
                body_weight = np.nan
            elif h.get("exactly_3_weights") and s >= 3:
                body_weight = np.nan

            # Field size 3 / 8 / 18 mix; 0 reserved for one specific race
            field_size = int(rng.choice([3, 8, 8, 18]))

            rows.append({
                "race_key": f"R{h_idx:04d}_{s:02d}",
                "horse_key": h["id"],
                "race_date": race_date.strftime("%Y-%m-%d"),
                "finish_order": int(rng.choice(range(1, max(field_size, 2)))),
                "distance": distance,
                "track_type": int(rng.choice(surfaces)),
                "grade": grade_val,
                "field_size": field_size,
                "place": rng.choice(places),
                "last3f": rng.uniform(33.0, 38.0),
                "corner3": rng.uniform(1, max(field_size, 2)),
                "corner4": rng.uniform(1, max(field_size, 2)),
                "body_weight": body_weight,
                "body_weight_diff": rng.uniform(-8, 8),
                "jockey_code": f"J{(h_idx + s) % 30:02d}",
                "trainer_code": f"T{(h_idx + s) % 25:02d}",
                "prize_money": float(rng.choice([0, 0, 0, 100, 500, 2000, 10000])),
            })

    df = pd.DataFrame(rows)

    # Inject same-race shared horse pool (multi-horse race) for prize_rank ties:
    # take 10 horse rows on the same race_date and assign the same race_key
    # so 10 horses share one race. Also force last3f tie within that race.
    if len(df) > 50:
        same_race_idxs = df.sample(n=10, random_state=rng).index.tolist()
        df.loc[same_race_idxs, "race_key"] = "SHARED_RACE_001"
        df.loc[same_race_idxs, "race_date"] = "2024-06-15"
        df.loc[same_race_idxs, "field_size"] = 10
        # Force last3f ties: 5 horses get 35.0, 5 get 36.0
        tied_pairs = same_race_idxs[:5]
        df.loc[tied_pairs, "last3f"] = 35.0
        df.loc[same_race_idxs[5:], "last3f"] = 36.0

    # Inject one race with field_size = 0 (running_style boundary)
    if len(df) > 60:
        zero_fs_idx = df.sample(n=1, random_state=rng).index[0]
        df.loc[zero_fs_idx, "field_size"] = 0

    return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Equivalence test (core)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def synth_df() -> pd.DataFrame:
    df = _make_synth_df()
    # Sanity: synth must hit the variety we documented.
    assert df["horse_key"].nunique() >= 40, "expected >= 40 horses"
    assert df["distance"].isna().any(), "expected NaN-distance rows"
    assert (df["grade"] == "G1").any() or (df["grade"] == "G2").any(), \
        "expected string-grade rows"
    return df


def _assert_outputs_equivalent(out_a: pd.DataFrame, out_b: pd.DataFrame) -> None:
    """Assert that two outputs produce identical horse-block features."""
    assert set(HORSE_FEATURES).issubset(out_a.columns), \
        f"missing in out_a: {set(HORSE_FEATURES) - set(out_a.columns)}"
    assert set(HORSE_FEATURES).issubset(out_b.columns), \
        f"missing in out_b: {set(HORSE_FEATURES) - set(out_b.columns)}"

    for c in HORSE_FEATURES:
        a = out_a[c]
        b = out_b[c]
        assert (a.isna() == b.isna()).all(), \
            f"NaN-position mismatch in '{c}': " \
            f"a={a.isna().sum()} NaN, b={b.isna().sum()} NaN"
        if pd.api.types.is_numeric_dtype(a) and pd.api.types.is_numeric_dtype(b):
            tol = TOLERANCES.get(c, TOLERANCES["default"])
            mask = a.notna()
            if mask.sum() == 0:
                continue
            np.testing.assert_allclose(
                a[mask].values.astype(float),
                b[mask].values.astype(float),
                err_msg=f"value mismatch in '{c}'",
                **tol,
            )


def test_vectorized_matches_legacy(synth_df: pd.DataFrame) -> None:
    """Vectorised path must produce horse-block features equivalent to legacy.

    All 35 horse_* features are compared with per-feature tolerances
    (rtol=1e-7 default; loosened for prize sums, weight_trend_3 polyfit).
    NaN positions must match exactly.
    """
    out_legacy = _compute_as_of_features_legacy(synth_df.copy(), CANONICAL_COL.copy())
    out_vec = _compute_as_of_features(synth_df.copy(), CANONICAL_COL.copy())
    _assert_outputs_equivalent(out_legacy, out_vec)


def test_two_orchestrator_calls_are_idempotent(synth_df: pd.DataFrame) -> None:
    """Sanity: running the orchestrator twice on identical input must match.

    Guards against accidental state leakage in the cached groupby objects.
    """
    out1 = _compute_as_of_features(synth_df.copy(), CANONICAL_COL.copy())
    out2 = _compute_as_of_features(synth_df.copy(), CANONICAL_COL.copy())
    _assert_outputs_equivalent(out1, out2)


def test_synth_covers_every_strata(synth_df: pd.DataFrame) -> None:
    """Guard against future synth-fixture regressions hiding test coverage."""
    starts = synth_df.groupby("horse_key").size()
    for n in (1, 2, 3, 4, 5, 7):
        n_horses = (starts == n).sum()
        assert n_horses >= 1, f"need >=1 horse with exactly {n} starts (got {n_horses})"

    assert "SHARED_RACE_001" in synth_df["race_key"].values, \
        "shared-race injection lost"
    assert (synth_df["field_size"] == 0).any(), "field_size=0 row missing"


# ---------------------------------------------------------------------------
# Boundary tests
# ---------------------------------------------------------------------------


def test_first_race_per_horse_is_nan(synth_df: pd.DataFrame) -> None:
    """A horse's first race must have all as-of features as NaN."""
    out = _compute_as_of_features(synth_df.copy(), CANONICAL_COL.copy())
    out_sorted = out.sort_values(["horse_key", "race_date"]).reset_index(drop=True)
    first_rows = out_sorted.groupby("horse_key", as_index=False).head(1)
    for c in [
        "horse_n_starts", "horse_win_rate", "horse_avg_finish",
        "horse_recent3_avg", "horse_last_finish",
    ]:
        assert first_rows[c].isna().all(), \
            f"{c} should be NaN on first race; offenders: {first_rows.loc[first_rows[c].notna(), 'horse_key'].tolist()[:3]}"


def test_grade_n_starts_zero_value_present(synth_df: pd.DataFrame) -> None:
    """Regression guard: legacy writes 0 (not NaN) when no past graded race.

    The vectorised path must preserve this — `(cum / n).where(n>0)` would
    incorrectly produce NaN for n=0 cells. This test would catch the regression.
    """
    out = _compute_as_of_features(synth_df.copy(), CANONICAL_COL.copy())
    # At least some horse-rows should have grade_n_starts == 0 (i.e., past
    # races but no graded past races). If not, synth fixture lost coverage.
    assert (out["horse_grade_n_starts"] == 0).any(), \
        "synth fixture lost graded-races zero-coverage"


# ---------------------------------------------------------------------------
# Performance smoke (slow; run with -m slow)
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_vectorized_is_meaningfully_faster(synth_df: pd.DataFrame) -> None:
    """The vectorised path must be meaningfully faster than legacy on synth.

    Synth is too small (~250 rows) to expose the legacy O(N²) blow-up;
    the gap here is typically 3-5x. On production-scale 700K-row data the
    measured gap was ~300x. The 3x floor catches a real regression
    (e.g., accidentally re-introducing per-row pandas ops) while
    tolerating CI variance.
    """
    # Warm-up — eliminates JIT / import cost from the timing
    _compute_as_of_features(synth_df.copy(), CANONICAL_COL.copy())

    legacy_times = []
    vec_times = []
    for _ in range(3):
        t0 = time.perf_counter()
        _compute_as_of_features_legacy(synth_df.copy(), CANONICAL_COL.copy())
        legacy_times.append(time.perf_counter() - t0)

        t0 = time.perf_counter()
        _compute_as_of_features(synth_df.copy(), CANONICAL_COL.copy())
        vec_times.append(time.perf_counter() - t0)

    legacy_med = sorted(legacy_times)[1]
    vec_med = sorted(vec_times)[1]
    speedup = legacy_med / vec_med
    print(f"\n  legacy median={legacy_med:.2f}s, vec median={vec_med:.2f}s, "
          f"speedup={speedup:.1f}x")
    assert speedup >= 3.0, (
        f"vectorised path only {speedup:.1f}x faster than legacy "
        f"(legacy={legacy_med:.2f}s vec={vec_med:.2f}s); regression?"
    )

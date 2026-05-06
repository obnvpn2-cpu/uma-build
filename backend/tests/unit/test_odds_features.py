"""Tests for odds_features helpers."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import numpy as np
import pandas as pd

from services.odds_features import (
    ODDS_DERIVED_COLUMNS,
    add_fuku_odds_uncertainty,
    add_implied_prob,
    add_log_odds_gap_to_fav,
    add_log_odds_gap_to_mean,
    add_log_win_odds,
    add_odds_derived_features,
)

# EveryDB2 stores odds as actual_odds * 10. So win_odds=23 → real 2.3×.


def _df_two_races():
    return pd.DataFrame(
        {
            "race_key": ["A", "A", "A", "B", "B"],
            "win_odds": [23, 50, 800, 30, 60],  # real: 2.3, 5.0, 80.0, 3.0, 6.0
            "fuku_odds_low": [11, 18, 200, 12, 20],
            "fuku_odds_high": [15, 28, 350, 18, 30],
        }
    )


def test_log_win_odds_uses_real_scale():
    df = _df_two_races()
    out = add_log_win_odds(df)
    # Real odds = win_odds / 10
    expected = np.log(np.array([2.3, 5.0, 80.0, 3.0, 6.0]))
    np.testing.assert_allclose(out["log_win_odds"].values, expected, rtol=1e-6)


def test_implied_prob_is_inverse_of_real_odds():
    df = _df_two_races()
    out = add_implied_prob(df)
    expected = 1.0 / np.array([2.3, 5.0, 80.0, 3.0, 6.0])
    np.testing.assert_allclose(out["implied_prob"].values, expected, rtol=1e-6)
    # Each race-level sum should exceed 1.0 (takeout is implicit)
    race_sums = out.groupby("race_key")["implied_prob"].sum()
    # With only a subset of horses these may sum < 1; but per-row in (0,1).
    assert (out["implied_prob"] > 0).all()
    assert (out["implied_prob"] < 1).all()
    # smoke check: race A has 3 horses with probs 1/2.3 + 1/5 + 1/80
    assert abs(race_sums["A"] - (1 / 2.3 + 1 / 5 + 1 / 80)) < 1e-9


def test_log_odds_gap_to_fav_is_zero_for_favorite():
    df = _df_two_races()
    out = add_log_odds_gap_to_fav(df)
    # Favorite per race has gap 0
    favorites = out.loc[out.groupby("race_key")["win_odds"].idxmin()]
    np.testing.assert_allclose(favorites["log_odds_gap_to_fav"].values, [0.0, 0.0])
    # Non-favorites strictly positive
    non_fav = out.drop(favorites.index)
    assert (non_fav["log_odds_gap_to_fav"] > 0).all()


def test_log_odds_gap_to_mean_is_centered_per_race():
    df = _df_two_races()
    out = add_log_odds_gap_to_mean(df)
    race_means = out.groupby("race_key")["log_odds_gap_to_mean"].mean()
    # Should be ~0 for each race (centered)
    np.testing.assert_allclose(race_means.values, [0.0, 0.0], atol=1e-9)


def test_fuku_odds_uncertainty_relative_spread():
    df = _df_two_races()
    out = add_fuku_odds_uncertainty(df)
    # row 0: low=11→1.1, high=15→1.5; spread=(1.5-1.1)/1.1
    assert abs(out["fuku_odds_uncertainty"].iloc[0] - (0.4 / 1.1)) < 1e-9
    assert (out["fuku_odds_uncertainty"] >= 0).all()


def test_fuku_odds_uncertainty_handles_missing_columns():
    df = pd.DataFrame({"race_key": ["A", "A"], "win_odds": [20, 50]})
    out = add_fuku_odds_uncertainty(df)
    assert out["fuku_odds_uncertainty"].isna().all()


def test_log_win_odds_clipped_for_zero_input():
    """Stored win_odds=0 (sentinel for missing) should not produce -inf."""
    df = pd.DataFrame({"race_key": ["A", "A"], "win_odds": [0, 25]})
    out = add_log_win_odds(df)
    # 0 → real 0.0 → clipped to 1.05 → log(1.05) ≈ 0.0488
    assert np.isfinite(out["log_win_odds"]).all()
    assert out["log_win_odds"].iloc[0] < out["log_win_odds"].iloc[1]


def test_add_all_returns_expected_columns():
    df = _df_two_races()
    out = add_odds_derived_features(df)
    for col in ODDS_DERIVED_COLUMNS:
        assert col in out.columns, col
    # Source columns preserved
    assert "win_odds" in out.columns


def test_add_all_does_not_mutate_input():
    df = _df_two_races()
    snapshot = df.copy()
    _ = add_odds_derived_features(df)
    pd.testing.assert_frame_equal(df, snapshot)


def test_single_horse_race_zero_gaps():
    """Single-horse group: gap-to-fav and gap-to-mean are both 0."""
    df = pd.DataFrame({"race_key": ["X"], "win_odds": [42]})
    out = add_odds_derived_features(df)
    assert out["log_odds_gap_to_fav"].iloc[0] == 0.0
    assert out["log_odds_gap_to_mean"].iloc[0] == 0.0
    # log_win_odds and implied_prob are still meaningful
    assert out["log_win_odds"].iloc[0] > 0  # ln(4.2) > 0
    assert 0 < out["implied_prob"].iloc[0] < 1


def test_all_equal_odds_yields_zero_gaps():
    """All horses with identical odds: gaps are exactly 0 — no rank info."""
    df = pd.DataFrame({"race_key": ["A"] * 4, "win_odds": [50, 50, 50, 50]})
    out = add_odds_derived_features(df)
    assert (out["log_odds_gap_to_fav"] == 0.0).all()
    assert (out["log_odds_gap_to_mean"] == 0.0).all()


def test_fuku_odds_uncertainty_negative_spread_becomes_nan():
    """Corrupted high < low: result is NaN (not a negative 'uncertainty')."""
    df = pd.DataFrame(
        {
            "race_key": ["A", "A"],
            "win_odds": [20, 30],
            "fuku_odds_low": [30, 20],
            "fuku_odds_high": [25, 25],  # row 0: high < low → corrupted
        }
    )
    out = add_fuku_odds_uncertainty(df)
    assert pd.isna(out["fuku_odds_uncertainty"].iloc[0])
    assert out["fuku_odds_uncertainty"].iloc[1] >= 0


def test_implied_prob_strictly_below_one_via_jra_floor():
    """Document why `< 1` is guaranteed: real_odds is clipped to ≥ 1.05."""
    # win_odds=0 (sentinel) → real clipped to 1.05 → implied_prob = 1/1.05
    df = pd.DataFrame({"race_key": ["X", "X"], "win_odds": [0, 1000]})
    out = add_implied_prob(df)
    # max possible implied_prob ≈ 0.952
    assert out["implied_prob"].max() <= 1.0 / 1.05 + 1e-9
    assert (out["implied_prob"] > 0).all()


def test_add_all_groupby_alignment_with_unsorted_index():
    """groupby+transform must align by index, not by position."""
    df = pd.DataFrame(
        {
            "race_key": ["A", "B", "A", "B"],
            "win_odds": [20, 30, 100, 50],  # A: [20,100], B: [30,50]
        },
        index=[10, 20, 30, 40],
    )
    out = add_odds_derived_features(df)
    # Race A: min log_odds = log(2.0); rows at index 10 and 30
    # Race B: min log_odds = log(3.0); rows at index 20 and 40
    fav_a = out.loc[10, "log_odds_gap_to_fav"]
    fav_b = out.loc[20, "log_odds_gap_to_fav"]
    assert fav_a == 0.0  # A favorite (win_odds=20)
    assert fav_b == 0.0  # B favorite (win_odds=30)
    # Index preserved
    assert list(out.index) == [10, 20, 30, 40]

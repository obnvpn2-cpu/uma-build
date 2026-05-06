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

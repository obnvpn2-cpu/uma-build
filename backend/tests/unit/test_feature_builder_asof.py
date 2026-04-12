"""Tests for DEMO feature table generation — leak prevention.

These tests ensure that the synthetic demo data does NOT leak target
information through features like win_odds, popularity, umaban, etc.

If these tests fail, it means the DEMO data generator is creating features
that are directly correlated with the race outcome, which would produce
unrealistically high ROI in backtests and mislead users.
"""

import os
import sys

# Add backend to path so we can import services
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pandas as pd
import pytest

from services.feature_builder import generate_demo_feature_table


@pytest.fixture(scope="module")
def demo_df() -> pd.DataFrame:
    """Generate demo data once for all tests in this module."""
    return generate_demo_feature_table(n_races=200, avg_field_size=14)


def test_no_target_leak_win_odds(demo_df: pd.DataFrame):
    """win_odds should NOT be strongly correlated with target_win.

    A strong negative correlation (high odds for losers, low for winners)
    would indicate that odds are derived directly from the ability score
    that determines finish position.
    """
    corr = demo_df["win_odds"].corr(demo_df["target_win"])
    assert abs(corr) < 0.3, (
        f"win_odds × target_win correlation = {corr:.3f} (expected |corr| < 0.3). "
        "DEMO data may be leaking outcome through odds."
    )


def test_no_target_leak_popularity(demo_df: pd.DataFrame):
    """popularity should NOT be strongly correlated with target_win.

    If popularity == finish_pos, correlation with target_win would be
    extremely strong (the winner always has popularity=1).
    """
    corr = demo_df["popularity"].corr(demo_df["target_win"])
    assert abs(corr) < 0.3, (
        f"popularity × target_win correlation = {corr:.3f} (expected |corr| < 0.3). "
        "DEMO data may be leaking outcome through popularity."
    )


def test_no_target_leak_umaban(demo_df: pd.DataFrame):
    """umaban (gate number) should NOT be correlated with target_win.

    Gate numbers are assigned before the race and should be random.
    """
    corr = demo_df["umaban"].corr(demo_df["target_win"])
    assert abs(corr) < 0.15, (
        f"umaban × target_win correlation = {corr:.3f} (expected |corr| < 0.15). "
        "DEMO data may be leaking outcome through gate numbers."
    )


def test_no_target_leak_corner4(demo_df: pd.DataFrame):
    """corner4 position should NOT be strongly correlated with finish_order."""
    corr = demo_df["corner4"].corr(demo_df["finish_order"])
    assert abs(corr) < 0.3, (
        f"corner4 × finish_order correlation = {corr:.3f} (expected |corr| < 0.3). "
        "DEMO data may be leaking outcome through corner positions."
    )


def test_no_target_leak_last3f(demo_df: pd.DataFrame):
    """last3f time should NOT be strongly correlated with finish_order."""
    corr = demo_df["last3f"].corr(demo_df["finish_order"])
    assert abs(corr) < 0.3, (
        f"last3f × finish_order correlation = {corr:.3f} (expected |corr| < 0.3). "
        "DEMO data may be leaking outcome through last 3 furlong times."
    )


def test_demo_data_shape(demo_df: pd.DataFrame):
    """Basic sanity check on demo data dimensions."""
    assert len(demo_df) > 1000, f"Expected >1000 rows, got {len(demo_df)}"
    assert "target_win" in demo_df.columns
    assert "target_in3" in demo_df.columns
    assert "win_odds" in demo_df.columns
    assert "popularity" in demo_df.columns
    assert "umaban" in demo_df.columns


def test_demo_roi_realistic(demo_df: pd.DataFrame):
    """A naive 'bet on lowest odds' strategy should NOT produce extreme ROI.

    In realistic data, betting on the favorite yields ROI ~70-85%.
    If ROI > 150%, the data is likely leaking.
    """
    # For each race, pick the horse with lowest odds
    results = []
    for race_key, group in demo_df.groupby("race_key"):
        if group.empty:
            continue
        best_row = group.loc[group["win_odds"].idxmin()]
        won = best_row["target_win"] == 1
        payout = best_row["win_odds"] * 100 if won else 0
        results.append({"bet": 100, "payout": payout})

    if not results:
        pytest.skip("No race data")

    total_bet = sum(r["bet"] for r in results)
    total_payout = sum(r["payout"] for r in results)
    roi = (total_payout / total_bet) * 100

    assert roi < 150, (
        f"Lowest-odds strategy ROI = {roi:.1f}% (expected < 150%). "
        "DEMO data may be producing unrealistic results."
    )

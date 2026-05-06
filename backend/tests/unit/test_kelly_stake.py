"""Tests for Kelly-stake helpers in explore_ev_strategy.

Imports the script's helpers; these are pure functions so they unit-test
without spinning up walk_forward_cv.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import importlib.util

import numpy as np
import pandas as pd

# Load the script as a module (it lives in backend/scripts/)
_SCRIPT_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "scripts", "explore_ev_strategy.py"
)
_spec = importlib.util.spec_from_file_location("explore_ev_strategy", _SCRIPT_PATH)
ees = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ees)  # type: ignore[union-attr]


# ---- kelly_fraction --------------------------------------------------------


def test_kelly_fraction_zero_when_ev_negative():
    """p*o - 1 < 0 → Kelly fraction = 0 (skip the bet)."""
    p = pd.Series([0.1, 0.05, 0.2])
    odds = pd.Series([5.0, 3.0, 4.0])  # EV: 0.5 (skip), 0.15 (skip), 0.8 (skip)
    f = ees.kelly_fraction(p, odds, cap=1.0)
    assert (f == 0).all()


def test_kelly_fraction_correct_value_when_ev_positive():
    """Standard Kelly: p=0.3, o=5 → f* = (0.3*5-1)/(5-1) = 0.5/4 = 0.125."""
    p = pd.Series([0.3])
    odds = pd.Series([5.0])
    f = ees.kelly_fraction(p, odds, cap=1.0)
    assert abs(f.iloc[0] - 0.125) < 1e-9


def test_kelly_fraction_capped():
    """Strong-edge bet capped at the user's quarter-Kelly limit."""
    p = pd.Series([0.8])  # very high prob
    odds = pd.Series([5.0])  # moderate odds → f* = (0.8*5-1)/4 = 3/4 = 0.75
    f_full = ees.kelly_fraction(p, odds, cap=1.0)
    f_quarter = ees.kelly_fraction(p, odds, cap=0.25)
    assert abs(f_full.iloc[0] - 0.75) < 1e-9
    assert abs(f_quarter.iloc[0] - 0.25) < 1e-9


def test_kelly_fraction_zero_when_odds_invalid():
    """odds <= 1 (or NaN) → fraction 0 (no payout to extract)."""
    p = pd.Series([0.5, 0.5, 0.5])
    odds = pd.Series([1.0, 0.5, np.nan])
    f = ees.kelly_fraction(p, odds, cap=1.0)
    assert (f == 0).all()


def test_kelly_fraction_clips_prob_above_one():
    """p > 1 (numerical noise) is clipped before computing f*."""
    p = pd.Series([1.5])  # sentinel for floating-point overshoot
    odds = pd.Series([2.0])  # f* with p=1: (1*2-1)/(2-1) = 1.0
    f = ees.kelly_fraction(p, odds, cap=1.0)
    assert abs(f.iloc[0] - 1.0) < 1e-9


def test_kelly_fraction_handles_nan_prob():
    """NaN prob → fraction 0 (treated as missing input, not propagated)."""
    p = pd.Series([np.nan, 0.5])
    odds = pd.Series([3.0, 3.0])
    f = ees.kelly_fraction(p, odds, cap=1.0)
    assert f.iloc[0] == 0  # NaN handled
    assert f.iloc[1] > 0  # other row unaffected


def test_kelly_fraction_handles_zero_and_subunit_odds():
    """odds == 0 (sentinel) and odds < 1 both produce 0 fraction."""
    p = pd.Series([0.5, 0.5, 0.5])
    odds = pd.Series([0.0, 0.5, 0.99])
    f = ees.kelly_fraction(p, odds, cap=1.0)
    assert (f == 0).all()


# ---- evaluate_strategy_kelly ----------------------------------------------


def _make_kelly_df():
    """Build a small df with deterministic outcomes so Kelly ROI is exact.

    Two horses across two races. Both have positive Kelly EV but only
    horse A wins; we verify the Kelly-weighted ROI matches by hand.
    """
    return pd.DataFrame({
        "race_key": ["R1", "R1", "R2", "R2"],
        "pred_prob_norm": [0.4, 0.2, 0.3, 0.1],
        "tan_odds": [3.0, 6.0, 5.0, 12.0],
        "actual_win": [1, 0, 1, 0],
    })


def test_evaluate_strategy_kelly_handles_empty_mask():
    df = _make_kelly_df()
    out = ees.evaluate_strategy_kelly(df, "empty", df["actual_win"] < 0)
    assert out["n_bets"] == 0
    assert out["kelly_n_active"] == 0
    assert out["kelly_roi_pct"] == 0


def test_evaluate_strategy_kelly_zero_when_no_positive_ev():
    """Mask selects only bets where EV < 0 → no active Kelly bets."""
    df = pd.DataFrame({
        "race_key": ["R1"], "pred_prob_norm": [0.1],
        "tan_odds": [3.0], "actual_win": [0],  # EV = 0.3 < 1
    })
    out = ees.evaluate_strategy_kelly(df, "neg-ev", pd.Series([True]))
    assert out["n_bets"] == 1
    assert out["kelly_n_active"] == 0
    assert out["kelly_roi_pct"] == 0.0


def test_evaluate_strategy_kelly_roi_matches_manual():
    """Verify the math: Kelly ROI on a hand-computable scenario."""
    df = _make_kelly_df()
    # All 4 rows. Compute expected by hand for cap=1.0:
    # R1 horse A: p=0.4, o=3 → f* = (1.2-1)/2 = 0.1; wins → payout=0.1*3=0.3
    # R1 horse B: p=0.2, o=6 → f* = (1.2-1)/5 = 0.04; loses → payout=0
    # R2 horse A: p=0.3, o=5 → f* = (1.5-1)/4 = 0.125; wins → payout=0.625
    # R2 horse B: p=0.1, o=12 → f* = (1.2-1)/11 ≈ 0.01818; loses
    # stake_total = 0.1+0.04+0.125+0.01818 ≈ 0.28318
    # payout_total = 0.3+0+0.625+0 = 0.925
    # ROI = 100 * (0.925 - 0.28318) / 0.28318 ≈ 226.6%
    out = ees.evaluate_strategy_kelly(
        df, "all", pd.Series([True] * 4), kelly_cap=1.0,
    )
    assert out["n_bets"] == 4
    assert out["kelly_n_active"] == 4
    assert abs(out["kelly_roi_pct"] - 226.66) < 1.0  # rounding


def test_evaluate_strategy_kelly_caps_high_edge_bets():
    """High-edge bets respect kelly_cap (avoid concentration risk)."""
    df = pd.DataFrame({
        "race_key": ["R1"], "pred_prob_norm": [0.9],
        "tan_odds": [10.0], "actual_win": [1],
    })
    # f* = (0.9*10 - 1) / 9 = 8/9 ≈ 0.889 → capped to 0.25
    out_full = ees.evaluate_strategy_kelly(
        df, "full", pd.Series([True]), kelly_cap=1.0,
    )
    out_quarter = ees.evaluate_strategy_kelly(
        df, "quarter", pd.Series([True]), kelly_cap=0.25,
    )
    # Full Kelly: stake=0.889, payout=0.889*10=8.89, ROI=(8.89-0.889)/0.889 ≈ 900%
    # Quarter Kelly: stake=0.25, payout=2.5, ROI=(2.5-0.25)/0.25 = 900%
    # Both same ROI because outcome is favorable; cap only affects absolute stake
    assert out_full["kelly_avg_f"] > 0.85
    assert abs(out_quarter["kelly_avg_f"] - 0.25) < 1e-6
    # Both ROI = 900% (avg odds is the same)
    assert abs(out_full["kelly_roi_pct"] - out_quarter["kelly_roi_pct"]) < 1.0

"""Tests for backend/services/backtest.py.

Covers ROI calculation, hit rate, top-1 selection,
condition/yearly breakdowns, and empty-input safety.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import numpy as np
import pandas as pd
import pytest

from services.backtest import (
    _calc_hit_rate,
    _calc_roi,
    _condition_breakdown,
    _top1_per_race,
    _yearly_breakdown,
    run_backtest,
)


@pytest.fixture
def predictions_df():
    """Synthetic predictions: 3 races x 5 horses each."""
    rng = np.random.RandomState(123)
    rows = []
    for race_idx in range(3):
        race_key = f"R{race_idx:04d}"
        year = 2024 + race_idx  # 2024, 2025, 2026
        surface = 1 if race_idx < 2 else 2  # 芝, 芝, ダート
        track_cond = 1 if race_idx != 1 else 3  # 良, 重, 良
        for horse_idx in range(5):
            is_winner = horse_idx == 0
            rows.append({
                "race_key": race_key,
                "horse_key": f"H{race_idx}{horse_idx}",
                "pred_prob": 0.8 - horse_idx * 0.15 + rng.rand() * 0.01,
                "actual_win": 1 if is_winner else 0,
                "win_odds": 3.0 if is_winner else 10.0 + horse_idx,
                "tansho_payout": 300 if is_winner else 0,
                "finish_order": horse_idx + 1,
                "surface": surface,
                "track_condition": track_cond,
                "race_date": f"{year}-06-01",
                "distance": 1600,
            })
    return pd.DataFrame(rows)


# ---- _calc_roi ----

def test_calc_roi_basic(predictions_df):
    """Wins present -> positive ROI calculated correctly via win_odds."""
    # Use only win_odds (drop tansho_payout)
    picks = predictions_df[predictions_df["actual_win"] == 1].drop(columns=["tansho_payout"])
    result = _calc_roi(picks, bet_amount=100)
    assert result["total_bet"] == 300  # 3 winners, 100 each
    # Each winner has win_odds=3.0 -> return = 3*100 = 300 per winner -> total 900
    assert result["total_return"] == 900
    assert result["roi"] == 200.0  # (900-300)/300 * 100


def test_calc_roi_no_wins():
    """No winners -> ROI = -100%."""
    df = pd.DataFrame({
        "actual_win": [0, 0, 0],
        "win_odds": [5.0, 8.0, 12.0],
    })
    result = _calc_roi(df, bet_amount=100)
    assert result["total_return"] == 0
    assert result["roi"] == -100.0


def test_calc_roi_with_tansho_payout(predictions_df):
    """tansho_payout column takes priority over win_odds."""
    picks = predictions_df.head(5)  # first race: 1 winner with payout=300
    result = _calc_roi(picks, bet_amount=100)
    # tansho_payout=300 for winner, bet_amount/100=1.0, so return=300
    assert result["total_return"] == 300
    assert result["total_bet"] == 500  # 5 horses * 100


# ---- _calc_hit_rate ----

def test_calc_hit_rate(predictions_df):
    """Hit rate = n_hits / n_bets * 100."""
    picks = predictions_df.head(5)  # 1 winner out of 5
    result = _calc_hit_rate(picks)
    assert result["n_bets"] == 5
    assert result["n_hits"] == 1
    assert result["hit_rate"] == 20.0


# ---- _top1_per_race ----

def test_top1_per_race(predictions_df):
    """Selects horse with highest pred_prob per race."""
    top1 = _top1_per_race(predictions_df)
    assert len(top1) == 3  # 3 races
    for _, row in top1.iterrows():
        race_horses = predictions_df[predictions_df["race_key"] == row["race_key"]]
        assert row["pred_prob"] == race_horses["pred_prob"].max()


# ---- _condition_breakdown ----

def test_condition_breakdown(predictions_df):
    """Breakdown by surface x track_condition."""
    bd = _condition_breakdown(predictions_df, bet_amount=100)
    assert isinstance(bd, list)
    assert len(bd) >= 2  # at least 芝良, 芝重 or ダート良
    surfaces = {item["surface"] for item in bd}
    assert surfaces & {"芝", "ダート"}
    for item in bd:
        assert "roi" in item
        assert "hit_rate" in item


# ---- _yearly_breakdown ----

def test_yearly_breakdown(predictions_df):
    """Breakdown by year."""
    bd = _yearly_breakdown(predictions_df, bet_amount=100)
    assert isinstance(bd, list)
    years = [item["year"] for item in bd]
    assert sorted(years) == [2024, 2025, 2026]
    for item in bd:
        assert "roi" in item
        assert "n_bets" in item


# ---- run_backtest (empty) ----

def test_run_backtest_empty():
    """Empty DataFrame -> safe zero result."""
    result = run_backtest(pd.DataFrame(), bet_amount=100)
    assert result["summary"]["roi"] == 0.0
    assert result["summary"]["n_bets"] == 0
    assert result["summary"]["n_races"] == 0
    assert result["condition_breakdown"] == []
    assert result["yearly_breakdown"] == []

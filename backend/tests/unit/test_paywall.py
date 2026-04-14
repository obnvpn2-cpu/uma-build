"""Tests for backend/services/paywall.py.

Verifies free-tier masking hides breakdowns and pro-tier shows all.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from services.paywall import mask_results


def _make_full_results():
    """Create a realistic full results dict."""
    return {
        "model_id": "test123",
        "summary": {
            "roi": 12.5,
            "hit_rate": 25.0,
            "n_bets": 100,
            "n_races": 100,
            "reliability_stars": 3,
            "total_return": 11250,
            "total_bet": 10000,
            "profit": 1250,
            "n_hits": 25,
        },
        "feature_importance": [{"name": "distance", "importance": 0.15}],
        "condition_breakdown": [{"surface": "芝", "roi": 10.0}],
        "yearly_breakdown": [{"year": 2024, "roi": 12.5}],
        "distance_breakdown": [{"distance_category": "マイル", "roi": 8.0}],
        "calibration": [{"bin": "(0.0, 0.1]", "predicted_avg": 0.05}],
        "meta": {
            "n_features": 10,
            "data_years": 2,
            "elapsed_sec": 5.0,
            "n_train": 5000,
            "n_val": 1000,
            "feature_names": ["distance", "age"],
        },
    }


def test_mask_free_hides_breakdowns():
    """Free tier -> feature_importance/breakdown/calibration are null."""
    results = _make_full_results()
    masked = mask_results(results, is_pro=False)
    assert masked["feature_importance"] is None
    assert masked["condition_breakdown"] is None
    assert masked["yearly_breakdown"] is None
    assert masked["distance_breakdown"] is None
    assert masked["calibration"] is None


def test_mask_free_shows_summary():
    """Free tier -> roi/hit_rate/n_bets/n_races are visible."""
    results = _make_full_results()
    masked = mask_results(results, is_pro=False)
    summary = masked["summary"]
    assert summary["roi"] == 12.5
    assert summary["hit_rate"] == 25.0
    assert summary["n_bets"] == 100
    assert summary["n_races"] == 100


def test_mask_pro_shows_all():
    """Pro tier -> all fields visible, locked_features is empty."""
    results = _make_full_results()
    masked = mask_results(results, is_pro=True)
    assert masked["is_pro"] is True
    assert masked["locked_features"] == []
    assert masked["feature_importance"] is not None
    assert masked["condition_breakdown"] is not None
    assert masked["calibration"] is not None


def test_mask_free_locked_features():
    """Free tier -> locked_features contains 3 items."""
    results = _make_full_results()
    masked = mask_results(results, is_pro=False)
    assert masked["is_pro"] is False
    locked = masked["locked_features"]
    assert len(locked) == 3
    locked_ids = {item["id"] for item in locked}
    assert locked_ids == {"future_prediction", "overfitting_detection", "detailed_breakdown"}

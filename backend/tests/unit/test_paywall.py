"""Tests for backend/services/paywall.py.

Verifies free-tier preview masking and pro-tier full access.
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
        "feature_importance": [
            {"feature": "distance", "importance": 0.15, "rank": 1},
            {"feature": "age", "importance": 0.12, "rank": 2},
            {"feature": "weight", "importance": 0.10, "rank": 3},
            {"feature": "jockey", "importance": 0.08, "rank": 4},
            {"feature": "trainer", "importance": 0.06, "rank": 5},
        ],
        "condition_breakdown": [
            {"surface": "芝", "track_condition": "良", "n_bets": 60, "n_hits": 15, "hit_rate": 25.0, "roi": 10.0, "profit": 600},
            {"surface": "ダート", "track_condition": "良", "n_bets": 40, "n_hits": 10, "hit_rate": 25.0, "roi": 15.0, "profit": 600},
        ],
        "yearly_breakdown": [
            {"year": 2023, "n_bets": 50, "n_hits": 12, "hit_rate": 24.0, "roi": 8.0, "profit": 400},
            {"year": 2024, "n_bets": 50, "n_hits": 13, "hit_rate": 26.0, "roi": 17.0, "profit": 850},
        ],
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


# --- Free tier tests ---

def test_mask_free_shows_summary():
    """Free tier -> roi/hit_rate/n_bets/n_races visible; financials masked."""
    results = _make_full_results()
    masked = mask_results(results, is_pro=False)
    summary = masked["summary"]
    # Visible fields
    assert summary["roi"] == 12.5
    assert summary["hit_rate"] == 25.0
    assert summary["n_bets"] == 100
    assert summary["n_races"] == 100
    # Masked fields
    assert summary["total_return"] is None
    assert summary["total_bet"] is None
    assert summary["profit"] is None
    assert summary["n_hits"] is None


def test_mask_free_preview_yearly():
    """Free tier -> yearly_breakdown returns preview: latest 1 year visible, rest blurred."""
    results = _make_full_results()
    masked = mask_results(results, is_pro=False)
    yearly = masked["yearly_breakdown"]
    assert yearly is not None
    assert len(yearly) == 2
    # 2024 (latest) should be visible
    latest = [y for y in yearly if y["year"] == 2024][0]
    assert latest["is_blurred"] is False
    assert latest["roi"] == 17.0
    # 2023 should be blurred
    older = [y for y in yearly if y["year"] == 2023][0]
    assert older["is_blurred"] is True
    assert older["roi"] is None


def test_mask_free_preview_feature_importance():
    """Free tier -> feature_importance: top 3 visible, rest blurred."""
    results = _make_full_results()
    masked = mask_results(results, is_pro=False)
    fi = masked["feature_importance"]
    assert fi is not None
    assert len(fi) == 5
    # Top 3 visible
    visible = [f for f in fi if not f["is_blurred"]]
    blurred = [f for f in fi if f["is_blurred"]]
    assert len(visible) == 3
    assert len(blurred) == 2
    # Blurred items have None importance
    for item in blurred:
        assert item["importance"] is None


def test_mask_free_preview_condition():
    """Free tier -> condition_breakdown: first 1 row visible, rest blurred."""
    results = _make_full_results()
    masked = mask_results(results, is_pro=False)
    cond = masked["condition_breakdown"]
    assert cond is not None
    assert len(cond) == 2
    assert cond[0]["is_blurred"] is False
    assert cond[0]["roi"] == 10.0
    assert cond[1]["is_blurred"] is True
    assert cond[1]["roi"] is None


def test_mask_free_locks_distance_and_calibration():
    """Free tier -> distance_breakdown and calibration are still null."""
    results = _make_full_results()
    masked = mask_results(results, is_pro=False)
    assert masked["distance_breakdown"] is None
    assert masked["calibration"] is None


def test_mask_free_locked_features():
    """Free tier -> locked_features contains 3 items."""
    results = _make_full_results()
    masked = mask_results(results, is_pro=False)
    assert masked["is_pro"] is False
    locked = masked["locked_features"]
    assert len(locked) == 3
    locked_ids = {item["id"] for item in locked}
    assert locked_ids == {"future_prediction", "overfitting_detection", "detailed_breakdown"}


# --- Pro tier tests ---

def test_mask_pro_shows_all():
    """Pro tier -> all fields visible, locked_features is empty."""
    results = _make_full_results()
    masked = mask_results(results, is_pro=True)
    assert masked["is_pro"] is True
    assert masked["locked_features"] == []
    assert masked["feature_importance"] is not None
    assert masked["condition_breakdown"] is not None
    assert masked["yearly_breakdown"] is not None
    assert masked["distance_breakdown"] is not None
    assert masked["calibration"] is not None


# --- Edge cases ---

def test_mask_free_empty_breakdowns():
    """Free tier with empty breakdowns -> returns None for previews."""
    results = _make_full_results()
    results["yearly_breakdown"] = []
    results["feature_importance"] = []
    results["condition_breakdown"] = []
    masked = mask_results(results, is_pro=False)
    assert masked["yearly_breakdown"] is None
    assert masked["feature_importance"] is None
    assert masked["condition_breakdown"] is None

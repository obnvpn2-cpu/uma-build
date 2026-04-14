"""Tests for walk-forward cross-validation."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import numpy as np
import pandas as pd
import pytest

from ml.pipeline import TrainConfig
from ml.walk_forward import _compute_fold_boundaries, walk_forward_cv

# ---- fold boundary tests ----

def test_fold_boundaries_count():
    """Should produce exactly n_folds boundaries."""
    keys = np.arange(100)
    folds = _compute_fold_boundaries(keys, n_folds=3)
    assert len(folds) == 3


def test_fold_boundaries_cover_tail():
    """Last fold should end at the final race."""
    keys = np.arange(100)
    folds = _compute_fold_boundaries(keys, n_folds=3)
    assert folds[-1][1] == 100


def test_fold_boundaries_no_overlap():
    """Validation windows should not overlap."""
    keys = np.arange(200)
    folds = _compute_fold_boundaries(keys, n_folds=4)
    for i in range(1, len(folds)):
        assert folds[i][0] >= folds[i - 1][1] or folds[i][0] == folds[i - 1][0]


# ---- End-to-end walk-forward CV ----

@pytest.fixture(scope="module")
def synthetic_data():
    """Create minimal synthetic data for CV testing."""
    rng = np.random.RandomState(123)
    rows = []
    for race_id in range(120):
        n_horses = rng.randint(8, 14)
        abilities = rng.randn(n_horses)
        finish_order = np.argsort(-abilities) + 1
        for i in range(n_horses):
            rows.append({
                "race_key": f"R{race_id:04d}",
                "race_date": pd.Timestamp("2023-01-01") + pd.Timedelta(days=race_id * 3),
                "distance": rng.choice([1200, 1600, 2000]),
                "field_size": n_horses,
                "age": rng.randint(3, 7),
                "horse_win_rate": max(0, 0.1 + abilities[i] * 0.05 + rng.randn() * 0.03),
                "horse_avg_finish": max(1, 8 - abilities[i] * 1.5 + rng.randn()),
                "finish_order": finish_order[i],
                "target_win": 1 if finish_order[i] == 1 else 0,
                "horse_key": f"H{race_id:04d}{i:02d}",
                "win_odds": max(1.1, 10 - abilities[i] * 2 + rng.randn() * 4),
            })
    return pd.DataFrame(rows)


def test_walk_forward_lambdarank(synthetic_data: pd.DataFrame):
    """Walk-forward with lambdarank should return valid results."""
    feature_cols = ["distance", "field_size", "age", "horse_win_rate", "horse_avg_finish"]
    config = TrainConfig(objective_type="lambdarank", num_boost_round=30)

    result = walk_forward_cv(
        df=synthetic_data,
        feature_cols=feature_cols,
        config=config,
        n_folds=3,
    )

    assert result.get("error") is None
    assert result["model_id"] is not None
    assert len(result["predictions_df"]) > 0
    assert "cv_fold" in result["predictions_df"].columns
    # Should have predictions from multiple folds
    n_folds_seen = result["predictions_df"]["cv_fold"].nunique()
    assert n_folds_seen >= 2, f"Expected ≥2 folds, got {n_folds_seen}"
    assert "cv_metrics" in result
    assert result["cv_metrics"]["n_folds"] >= 2


def test_walk_forward_binary(synthetic_data: pd.DataFrame):
    """Walk-forward with binary objective should also work."""
    feature_cols = ["distance", "field_size", "age", "horse_win_rate", "horse_avg_finish"]
    config = TrainConfig(objective_type="binary", num_boost_round=30)

    result = walk_forward_cv(
        df=synthetic_data,
        feature_cols=feature_cols,
        config=config,
        n_folds=3,
    )

    assert result.get("error") is None
    assert len(result["predictions_df"]) > 0
    assert "logloss_mean" in result["cv_metrics"]

"""Tests for LambdaRank training pipeline.

Verifies that the lambdarank objective works end-to-end with demo data,
including group computation, relevance labeling, and model output.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import numpy as np
import pandas as pd
import pytest

from ml.pipeline import LGBMPipeline, TrainConfig, finish_to_relevance

# ---- finish_to_relevance tests ----

def test_finish_to_relevance_mapping():
    """Verify 1st→4, 2nd→3, 3rd→2, 4th-5th→1, 6th+→0."""
    finish = pd.Series([1, 2, 3, 4, 5, 6, 10, 18])
    rel = finish_to_relevance(finish)
    expected = [4, 3, 2, 1, 0, 0, 0, 0]
    assert rel.tolist() == expected


def test_finish_to_relevance_nan():
    """NaN finish_order should map to relevance 0."""
    finish = pd.Series([1, float("nan"), 3])
    rel = finish_to_relevance(finish)
    assert rel.iloc[1] == 0


# ---- TrainConfig tests ----

def test_lambdarank_config_params():
    """LambdaRank config should produce correct LightGBM params."""
    cfg = TrainConfig(objective_type="lambdarank")
    params = cfg.to_lgb_params()
    assert params["objective"] == "lambdarank"
    assert params["metric"] == "ndcg"
    assert "ndcg_eval_at" in params


def test_binary_config_params():
    """Binary config should still work for backward compatibility."""
    cfg = TrainConfig(objective_type="binary")
    params = cfg.to_lgb_params()
    assert params["objective"] == "binary"
    assert params["metric"] == "binary_logloss"


# ---- End-to-end lambdarank training with synthetic data ----

@pytest.fixture(scope="module")
def synthetic_rank_data():
    """Create minimal synthetic data for lambdarank training."""
    rng = np.random.RandomState(42)
    rows = []
    for race_id in range(80):
        n_horses = rng.randint(8, 16)
        abilities = rng.randn(n_horses)
        finish_order = np.argsort(-abilities) + 1
        for i in range(n_horses):
            rows.append({
                "race_key": f"R{race_id:04d}",
                "race_date": pd.Timestamp("2024-01-01") + pd.Timedelta(days=race_id),
                "distance": rng.choice([1200, 1600, 2000, 2400]),
                "field_size": n_horses,
                "age": rng.randint(3, 8),
                "weight_carried": 54.0 + rng.randn() * 2,
                "horse_win_rate": max(0, 0.1 + abilities[i] * 0.05 + rng.randn() * 0.02),
                "horse_avg_finish": max(1, 8 - abilities[i] * 2 + rng.randn()),
                "finish_order": finish_order[i],
                "target_win": 1 if finish_order[i] == 1 else 0,
                "horse_key": f"H{race_id:04d}{i:02d}",
                "win_odds": max(1.1, 10 - abilities[i] * 3 + rng.randn() * 5),
            })
    return pd.DataFrame(rows)


def test_lambdarank_training(synthetic_rank_data: pd.DataFrame):
    """LambdaRank training should produce valid predictions."""
    df = synthetic_rank_data.sort_values(["race_date", "race_key"]).reset_index(drop=True)
    split_idx = 60  # races
    race_keys = df["race_key"].unique()
    train_races = set(race_keys[:split_idx])

    train_df = df[df["race_key"].isin(train_races)]
    val_df = df[~df["race_key"].isin(train_races)]

    feature_cols = ["distance", "field_size", "age", "weight_carried",
                    "horse_win_rate", "horse_avg_finish"]
    X_train = train_df[feature_cols].copy()
    X_val = val_df[feature_cols].copy()

    y_train = finish_to_relevance(train_df["finish_order"])
    y_val = finish_to_relevance(val_df["finish_order"])

    group_train = train_df.groupby("race_key", sort=False).size().tolist()
    group_val = val_df.groupby("race_key", sort=False).size().tolist()

    config = TrainConfig(objective_type="lambdarank", num_boost_round=50)
    pipeline = LGBMPipeline(config=config)
    pipeline.train(X_train, y_train, X_val, y_val, group_train, group_val)

    preds = pipeline.predict(X_val)
    assert len(preds) == len(X_val)
    assert not np.isnan(preds).any()
    # Predictions should have some variance (not all the same)
    assert preds.std() > 0.01

    # Check metrics recorded
    assert "best_val_ndcg1" in pipeline.train_metrics
    assert pipeline.train_metrics["objective"] == "lambdarank"

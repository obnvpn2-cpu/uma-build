"""Tests for backend/services/future_prediction.py.

Verifies demo data generation, prediction structure, and error handling.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import numpy as np
import pandas as pd

from services.future_prediction import (
    _format_predictions,
    _generate_demo_future_races,
    generate_future_predictions,
)


def _make_training_df(n_races=50, n_horses=30):
    """Create a minimal training DataFrame for testing."""
    rng = np.random.RandomState(42)
    rows = []
    for race_idx in range(n_races):
        field_size = rng.randint(8, 15)
        horse_indices = rng.choice(n_horses, size=field_size, replace=False)
        for pos, h_idx in enumerate(horse_indices, 1):
            rows.append({
                "race_key": f"R{race_idx:04d}",
                "race_date": f"2024-{(race_idx % 12) + 1:02d}-{(race_idx % 28) + 1:02d}",
                "horse_key": f"H{h_idx:04d}",
                "distance": rng.choice([1200, 1600, 2000]),
                "surface": rng.choice([1, 2]),
                "finish_order": pos,
                "jockey_code": f"J{rng.randint(0, 20):03d}",
                "umaban": pos,
                "waku": min(8, (pos - 1) // 2 + 1),
                "horse_win_rate": rng.uniform(0, 0.3),
                "horse_in3_rate": rng.uniform(0, 0.6),
            })
    return pd.DataFrame(rows)


def test_generate_demo_future_races_shape():
    """Demo future races should produce entries with expected columns."""
    df = _make_training_df()
    future = _generate_demo_future_races(df, n_races=2)
    assert not future.empty
    assert "race_key" in future.columns
    assert "finish_order" in future.columns
    # finish_order should be NaN for future races
    assert future["finish_order"].isna().all()


def test_generate_demo_future_races_race_count():
    """Should generate the requested number of races."""
    df = _make_training_df()
    future = _generate_demo_future_races(df, n_races=3)
    race_keys = future["race_key"].unique()
    assert len(race_keys) == 3


def test_generate_demo_future_races_empty_input():
    """Empty training data should produce empty output."""
    future = _generate_demo_future_races(pd.DataFrame(), n_races=3)
    assert future.empty


def test_generate_demo_future_races_metadata():
    """Each row should have metadata columns for formatting."""
    df = _make_training_df()
    future = _generate_demo_future_races(df, n_races=1)
    assert "_race_name" in future.columns
    assert "_surface_label" in future.columns
    assert "_horse_name" in future.columns
    assert "_gate_number" in future.columns


def test_format_predictions_structure():
    """Formatted predictions should match the API response schema."""
    df = _make_training_df()
    future = _generate_demo_future_races(df, n_races=2)
    future["predicted_score"] = np.random.rand(len(future))

    results = _format_predictions(future)
    assert isinstance(results, list)
    assert len(results) == 2

    race = results[0]
    assert "race_key" in race
    assert "race_date" in race
    assert "race_name" in race
    assert "distance" in race
    assert "surface" in race
    assert "entries" in race

    entry = race["entries"][0]
    assert entry["rank"] == 1
    assert "horse_name" in entry
    assert "predicted_score" in entry
    assert entry["confidence"] in ("high", "medium", "low")
    assert "jockey" in entry
    assert "gate_number" in entry


def test_format_predictions_ranking():
    """Entries should be sorted by predicted_score descending."""
    df = _make_training_df()
    future = _generate_demo_future_races(df, n_races=1)
    future["predicted_score"] = np.random.rand(len(future))

    results = _format_predictions(future)
    entries = results[0]["entries"]
    scores = [e["predicted_score"] for e in entries]
    assert scores == sorted(scores, reverse=True)


def test_generate_future_predictions_with_missing_model(tmp_path):
    """Should return empty list when model file doesn't exist."""
    fake_path = str(tmp_path / "nonexistent.pkl")
    result = generate_future_predictions(
        model_path=fake_path,
        selected_features=["horse_win_rate"],
    )
    assert result == []

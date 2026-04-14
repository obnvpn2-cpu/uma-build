"""Tests for backend/services/trainer.py.

Tests cache round-trip and basic run_training behavior in DEMO mode.
Note: run_training tests are slow (~30-60s) because they train a real model.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import json

import pytest

from services.trainer import _cache_results, _results_cache, get_cached_results, run_training


def test_cache_and_retrieve(tmp_path, monkeypatch):
    """_cache_results -> get_cached_results round-trip."""
    # Redirect RESULTS_DIR and isolate in-memory cache
    import services.trainer as trainer_mod

    monkeypatch.setattr(trainer_mod, "RESULTS_DIR", str(tmp_path))
    monkeypatch.setattr(trainer_mod, "_results_cache", {})

    model_id = "test_round_trip_001"
    payload = {
        "model_id": model_id,
        "summary": {"roi": 10.0},
        "meta": {"data_years": 2},
    }

    _cache_results(model_id, payload)

    # Memory cache hit
    result = get_cached_results(model_id)
    assert result is not None
    assert result["summary"]["roi"] == 10.0

    # Clear memory cache -> disk fallback
    _results_cache.pop(model_id, None)
    result_disk = get_cached_results(model_id)
    assert result_disk is not None
    assert result_disk["summary"]["roi"] == 10.0

    # Verify JSON file on disk
    disk_file = tmp_path / f"{model_id}.json"
    assert disk_file.exists()
    data = json.loads(disk_file.read_text(encoding="utf-8"))
    assert data["model_id"] == model_id


@pytest.mark.slow
def test_run_training_returns_masked_results():
    """DEMO mode run_training -> returns is_pro=False masked result."""
    # Use default features that are always valid
    from services.feature_catalog import get_default_feature_ids

    features = get_default_feature_ids()[:5]  # take first 5 to keep it fast
    result = run_training(selected_feature_ids=features)

    assert "error" not in result or result.get("error") is None
    assert result.get("is_pro") is False
    assert "summary" in result
    assert "locked_features" in result


@pytest.mark.slow
def test_run_training_includes_cv_metrics():
    """run_training caches full results with cv_metrics before masking."""
    from services.feature_catalog import get_default_feature_ids

    features = get_default_feature_ids()[:5]
    result = run_training(selected_feature_ids=features)

    # The masked result has model_id; check the pre-mask cache has cv_metrics
    model_id = result.get("model_id")
    assert model_id is not None
    cached = get_cached_results(model_id)
    assert cached is not None
    assert "cv_metrics" in cached

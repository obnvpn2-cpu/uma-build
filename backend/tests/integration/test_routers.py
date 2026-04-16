"""Integration tests for API routers.

Tests FastAPI endpoints via TestClient: features, presets, learn, results, health, stripe.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


# ---- /api/features ----

def test_get_features():
    """GET /api/features -> returns 10 categories."""
    resp = client.get("/api/features")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 10


def test_get_features_defaults():
    """GET /api/features/defaults -> list of default feature IDs."""
    resp = client.get("/api/features/defaults")
    assert resp.status_code == 200
    data = resp.json()
    assert "default_features" in data
    assert isinstance(data["default_features"], list)
    assert len(data["default_features"]) > 0
    assert data["count"] == len(data["default_features"])


def test_get_presets():
    """GET /api/features/presets -> list of preset templates."""
    resp = client.get("/api/features/presets")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 4
    # Each preset has required fields
    for preset in data:
        assert "id" in preset
        assert "name" in preset
        assert "description" in preset
        assert "icon" in preset
        assert "features" in preset
        assert isinstance(preset["features"], list)
        assert len(preset["features"]) > 0


# ---- /api/learn ----

def test_get_limits():
    """GET /api/learn/limits -> max_attempts = 5 (free, no auth)."""
    resp = client.get("/api/learn/limits")
    assert resp.status_code == 200
    data = resp.json()
    assert data["max_attempts"] == 5
    assert data["is_pro"] is False


def test_learn_invalid_features():
    """POST /api/learn with all-invalid features -> 400."""
    resp = client.post("/api/learn", json={
        "selected_features": ["fake_feature_1", "fake_feature_2"],
    })
    assert resp.status_code == 400


def test_learn_too_few_features():
    """POST /api/learn with only 1 valid feature -> 400."""
    resp = client.post("/api/learn", json={
        "selected_features": ["distance"],
    })
    assert resp.status_code == 400


def test_job_status_not_found():
    """GET /api/learn/status/nonexistent -> 404."""
    resp = client.get("/api/learn/status/nonexistent_job_id")
    assert resp.status_code == 404


# ---- /api/results ----

def test_results_not_found():
    """GET /api/results/nonexistent -> 404."""
    resp = client.get("/api/results/nonexistent_model_id")
    assert resp.status_code == 404


# ---- /api/stripe ----

def test_stripe_checkout_requires_auth():
    """POST /api/stripe/checkout without auth -> 401."""
    resp = client.post("/api/stripe/checkout", json={"plan": "monthly"})
    assert resp.status_code == 401


def test_stripe_portal_requires_auth():
    """POST /api/stripe/portal without auth -> 401."""
    resp = client.post("/api/stripe/portal")
    assert resp.status_code == 401


# ---- /api/health ----

def test_health():
    """GET /api/health -> 200 ok."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

"""Preflight tests for POST /api/learn.

Verifies that a missing feature cache short-circuits to 503 before any
background job is created or daily quota is consumed.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from fastapi.testclient import TestClient

import routers.learn as learn_mod
from main import app

client = TestClient(app)


def _valid_payload():
    from services.feature_catalog import get_default_feature_ids

    return {
        "selected_features": get_default_feature_ids()[:3],
        "session_id": "test-preflight-session",
    }


def test_learn_returns_503_when_cache_missing(monkeypatch):
    """Cache unavailable → 503 with a clear operator message, no job created."""
    monkeypatch.setattr(learn_mod, "cache_is_available", lambda: False)

    # Ensure the counter starts clean for this session
    learn_mod._daily_attempts.pop("test-preflight-session", None)

    resp = client.post("/api/learn", json=_valid_payload())
    assert resp.status_code == 503
    assert "キャッシュ" in resp.json()["detail"]


def test_learn_does_not_increment_quota_on_503(monkeypatch):
    """A 503 from preflight must not consume the user's daily quota."""
    monkeypatch.setattr(learn_mod, "cache_is_available", lambda: False)

    learn_mod._daily_attempts.pop("quota-test-session", None)
    payload = {
        "selected_features": _valid_payload()["selected_features"],
        "session_id": "quota-test-session",
    }

    client.post("/api/learn", json=payload)

    # _daily_attempts is the source of truth for server-side rate limiting
    assert "quota-test-session" not in learn_mod._daily_attempts or \
        learn_mod._daily_attempts["quota-test-session"] == 0


def test_learn_proceeds_when_cache_available(monkeypatch):
    """Cache present → 202 and a job_id is returned."""
    monkeypatch.setattr(learn_mod, "cache_is_available", lambda: True)

    learn_mod._daily_attempts.pop("happy-path-session", None)
    payload = {
        "selected_features": _valid_payload()["selected_features"],
        "session_id": "happy-path-session",
    }

    resp = client.post("/api/learn", json=payload)
    assert resp.status_code == 202
    body = resp.json()
    assert "job_id" in body
    assert body["status"] == "training"

"""Preflight + rate-limit tests for POST /api/learn.

Verifies that a missing feature cache short-circuits to 503 before
the daily quota is consumed, and that the new Supabase-backed
job_store / rate_limit services are wired into the router.
"""

import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from fastapi.testclient import TestClient

import routers.learn as learn_mod
from main import app
from services import rate_limit

client = TestClient(app)


def _valid_payload(session_id: str = "test-preflight-session"):
    from services.feature_catalog import get_default_feature_ids

    return {
        "selected_features": get_default_feature_ids()[:3],
        "session_id": session_id,
    }


def test_learn_returns_503_when_cache_missing(monkeypatch):
    """Cache unavailable → 503 with a clear operator message, no job created."""
    monkeypatch.setattr(learn_mod, "cache_is_available", lambda: False)

    resp = client.post("/api/learn", json=_valid_payload())
    assert resp.status_code == 503
    assert "キャッシュ" in resp.json()["detail"]


def test_learn_does_not_increment_quota_on_503(monkeypatch):
    """A 503 from preflight must not consume the user's daily quota."""
    monkeypatch.setattr(learn_mod, "cache_is_available", lambda: False)

    rate_key = "session:quota-test-session"
    payload = _valid_payload("quota-test-session")

    with patch.object(rate_limit, "check_and_increment") as mocked:
        client.post("/api/learn", json=payload)
        mocked.assert_not_called()

    assert rate_limit.get_count(rate_key) == 0


def test_learn_proceeds_when_cache_available(monkeypatch):
    """Cache present → 202 and a job_id is returned."""
    monkeypatch.setattr(learn_mod, "cache_is_available", lambda: True)

    # Stub run_training so the background thread doesn't actually do
    # anything heavy / touch the DB during the test.
    with patch("routers.learn.run_training") as mocked_train:
        mocked_train.return_value = {"model_id": "m1"}

        resp = client.post("/api/learn", json=_valid_payload("happy-path-session"))
    assert resp.status_code == 202
    body = resp.json()
    assert "job_id" in body
    assert body["status"] == "training"


def test_learn_blocks_when_rate_limit_exhausted(monkeypatch):
    """6th anonymous attempt for the same session_id returns 429."""
    monkeypatch.setattr(learn_mod, "cache_is_available", lambda: True)

    # Force the in-memory counter to the limit
    rate_limit._reset_local_for_tests()
    payload = _valid_payload("rate-limit-session")
    rate_key = "session:rate-limit-session"

    import datetime as dt
    today = dt.datetime.now(dt.timezone.utc).date().isoformat()
    with rate_limit._local_lock:
        rate_limit._local_counts[(rate_key, today)] = learn_mod.MAX_FREE_DAILY_ATTEMPTS

    resp = client.post("/api/learn", json=payload)
    assert resp.status_code == 429
    assert "上限" in resp.json()["detail"]

"""Tests for services/job_store.py.

Covers both the in-memory fallback path (no Supabase env) and the
Supabase HTTP path (httpx.Client mocked at the module-shared
get_client level).
"""

import datetime as dt
import json
import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from services import _supabase_http, job_store

# ---------- in-memory fallback path ----------


def test_put_and_get_local_fallback():
    job_store.put(
        "j1",
        {"status": "completed", "result": {"a": 1}, "error": None},
        user_id="u1",
    )
    got = job_store.get("j1", requester_user_id="u1")
    assert got == {"status": "completed", "result": {"a": 1}, "error": None}


def test_local_lru_eviction():
    for i in range(job_store._MAX_LOCAL_JOBS + 5):
        job_store.put(f"j{i}", {"status": "completed"}, user_id="u1")
    # Earliest entries evicted
    assert job_store.get("j0", requester_user_id="u1") is None
    assert job_store.get(f"j{job_store._MAX_LOCAL_JOBS + 4}", requester_user_id="u1") is not None


def test_get_returns_none_when_not_found():
    assert job_store.get("missing", requester_user_id="u1") is None


def test_get_denies_access_when_user_mismatch():
    job_store.put("j1", {"status": "completed"}, user_id="alice")
    assert job_store.get("j1", requester_user_id="bob") is None


def test_get_denies_access_when_session_mismatch():
    job_store.put("j1", {"status": "completed"}, session_id="sess-A")
    assert job_store.get("j1", requester_session_id="sess-B") is None
    assert job_store.get("j1", requester_session_id="sess-A") is not None


def test_local_stale_running_marked_failed():
    job_store.put(
        "j1",
        {"status": "running", "result": None, "error": None},
        user_id="u1",
    )
    # Forcibly age the row past the stale threshold
    with job_store._local_lock:
        job_store._local_jobs["j1"]["updated_at"] = (
            dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=11)
        )
    out = job_store.get("j1", requester_user_id="u1")
    assert out["status"] == "failed"
    assert "タイムアウト" in (out["error"] or "")


# ---------- Supabase path (httpx mocked) ----------


def _configure_supabase(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-key")


def _mock_client(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(_supabase_http, "_client", client)
    return client


def test_put_uses_supabase_when_configured(monkeypatch):
    _configure_supabase(monkeypatch)
    client = _mock_client(monkeypatch)
    resp = MagicMock(status_code=201, text="")
    client.post.return_value = resp

    job_store.put(
        "abc",
        {"status": "running", "result": None, "error": None},
        user_id="u1",
        session_id=None,
    )

    assert client.post.called
    call = client.post.call_args
    assert call.args[0].endswith("/rest/v1/learn_jobs")
    body = json.loads(call.kwargs["content"])
    assert body["job_id"] == "abc"
    assert body["status"] == "running"


def test_get_calls_supabase_and_returns_row(monkeypatch):
    _configure_supabase(monkeypatch)
    client = _mock_client(monkeypatch)
    now_iso = dt.datetime.now(dt.timezone.utc).isoformat()
    client.get.return_value = MagicMock(
        status_code=200,
        json=MagicMock(
            return_value=[
                {
                    "job_id": "abc",
                    "user_id": "u1",
                    "session_id": None,
                    "status": "completed",
                    "result": {"x": 1},
                    "error": None,
                    "updated_at": now_iso,
                }
            ]
        ),
    )

    got = job_store.get("abc", requester_user_id="u1")
    assert got == {"status": "completed", "result": {"x": 1}, "error": None}


def test_stale_patch_includes_status_running_filter(monkeypatch):
    _configure_supabase(monkeypatch)
    client = _mock_client(monkeypatch)
    stale_iso = (
        dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=15)
    ).isoformat()
    client.get.return_value = MagicMock(
        status_code=200,
        json=MagicMock(
            return_value=[
                {
                    "job_id": "abc",
                    "user_id": "u1",
                    "status": "running",
                    "result": None,
                    "error": None,
                    "updated_at": stale_iso,
                }
            ]
        ),
    )
    client.patch.return_value = MagicMock(status_code=204, text="")

    out = job_store.get("abc", requester_user_id="u1")
    assert out["status"] == "failed"
    assert "タイムアウト" in (out["error"] or "")
    assert client.patch.called
    patch_call = client.patch.call_args
    params = patch_call.kwargs["params"]
    assert params["job_id"] == "eq.abc"
    assert params["status"] == "eq.running"


def test_supabase_get_returns_none_on_unauthorized(monkeypatch):
    _configure_supabase(monkeypatch)
    client = _mock_client(monkeypatch)
    client.get.return_value = MagicMock(
        status_code=200,
        json=MagicMock(
            return_value=[
                {
                    "job_id": "abc",
                    "user_id": "alice",
                    "session_id": None,
                    "status": "completed",
                    "result": {},
                    "error": None,
                    "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                }
            ]
        ),
    )
    assert job_store.get("abc", requester_user_id="bob") is None


def test_httpx_client_is_shared_module_global(monkeypatch):
    # Both modules read from _supabase_http.get_client(), so the
    # underlying singleton is the same object regardless of which
    # service initiates the call.
    _supabase_http._client = None  # force re-create
    monkeypatch.setattr(_supabase_http.httpx, "Client", MagicMock(return_value="fake-client"))
    c1 = _supabase_http.get_client()
    c2 = _supabase_http.get_client()
    assert c1 is c2

    # Reset for downstream tests so they get a real Client again
    _supabase_http._client = None

"""Tests for services/rate_limit.py.

Covers in-memory and Supabase RPC paths.
"""

import datetime as dt
import json
import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from services import _supabase_http, rate_limit

# ---------- in-memory fallback ----------


def test_local_increment_under_limit():
    a, c = rate_limit.check_and_increment("user:u1", 5)
    assert (a, c) == (True, 1)
    a, c = rate_limit.check_and_increment("user:u1", 5)
    assert (a, c) == (True, 2)


def test_local_blocks_at_limit():
    for _ in range(5):
        rate_limit.check_and_increment("user:u1", 5)
    a, c = rate_limit.check_and_increment("user:u1", 5)
    assert (a, c) == (False, 5)


def test_local_count_isolated_per_key():
    rate_limit.check_and_increment("user:alice", 5)
    rate_limit.check_and_increment("user:alice", 5)
    a, c = rate_limit.check_and_increment("user:bob", 5)
    assert (a, c) == (True, 1)


def test_local_resets_next_utc_day():
    """Sanity check that the day-boundary key splits the counter."""
    yesterday = (
        dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=1)
    ).isoformat()
    # Pretend 5 attempts happened yesterday
    with rate_limit._local_lock:
        rate_limit._local_counts[("user:u1", yesterday)] = 5
    # Today should still allow
    a, c = rate_limit.check_and_increment("user:u1", 5)
    assert (a, c) == (True, 1)


def test_get_count_in_memory():
    rate_limit.check_and_increment("user:u1", 5)
    rate_limit.check_and_increment("user:u1", 5)
    assert rate_limit.get_count("user:u1") == 2


# ---------- Supabase RPC path ----------


def _configure_supabase(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-key")


def _mock_client(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(_supabase_http, "_client", client)
    return client


def test_rpc_call_payload(monkeypatch):
    _configure_supabase(monkeypatch)
    client = _mock_client(monkeypatch)
    client.post.return_value = MagicMock(
        status_code=200,
        json=MagicMock(return_value=[{"allowed": True, "current_count": 1}]),
    )

    allowed, count = rate_limit.check_and_increment("user:u1", 5)
    assert (allowed, count) == (True, 1)

    call = client.post.call_args
    assert call.args[0].endswith("/rest/v1/rpc/increment_daily_attempt")
    body = json.loads(call.kwargs["content"])
    assert body == {"p_rate_key": "user:u1", "p_max": 5}


def test_rpc_blocked_response(monkeypatch):
    _configure_supabase(monkeypatch)
    client = _mock_client(monkeypatch)
    client.post.return_value = MagicMock(
        status_code=200,
        json=MagicMock(return_value=[{"allowed": False, "current_count": 5}]),
    )
    allowed, count = rate_limit.check_and_increment("user:u1", 5)
    assert (allowed, count) == (False, 5)


def test_get_count_supabase(monkeypatch):
    _configure_supabase(monkeypatch)
    client = _mock_client(monkeypatch)
    client.get.return_value = MagicMock(
        status_code=200,
        json=MagicMock(return_value=[{"count": 3}]),
    )
    assert rate_limit.get_count("user:u1") == 3

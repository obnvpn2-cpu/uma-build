"""Shared httpx.Client for Supabase REST calls.

A single keep-alive pool is reused across job_store and rate_limit so
Cloud Run cold-start TCP handshakes don't dominate request latency.
Read env at call time so tests can monkeypatch.setenv/delenv without
re-importing modules.
"""

import os
import threading
from typing import Optional

import httpx

_client: Optional[httpx.Client] = None
_client_lock = threading.Lock()


def get_client() -> httpx.Client:
    """Return a shared httpx.Client, creating it on first use."""
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                _client = httpx.Client(
                    timeout=10.0,
                    limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
                )
    return _client


def supabase_url() -> str:
    return os.environ.get("SUPABASE_URL", "").rstrip("/")


def service_role_key() -> str:
    return os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")


def is_configured() -> bool:
    return bool(supabase_url() and service_role_key())


def auth_headers(extra: Optional[dict] = None) -> dict:
    key = service_role_key()
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    if extra:
        headers.update(extra)
    return headers

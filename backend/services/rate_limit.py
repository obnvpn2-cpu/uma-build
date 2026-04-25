"""Daily attempt rate limiter backed by Supabase Postgres.

Replaces the in-memory _daily_attempts dict in routers/learn.py.
Increments are atomic via an INSERT ... ON CONFLICT DO UPDATE RPC,
so concurrent Cloud Run instances can't race past the limit.

Falls back to an in-memory implementation when Supabase isn't
configured (local dev / CI). Day boundary is UTC.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import threading
from typing import Dict, Tuple

from services._supabase_http import (
    auth_headers,
    get_client,
    is_configured,
    supabase_url,
)

logger = logging.getLogger(__name__)

_TABLE = "daily_attempts"
_RPC_NAME = "increment_daily_attempt"

# In-memory fallback: { (rate_key, utc_date_iso): count }
_local_counts: Dict[Tuple[str, str], int] = {}
_local_lock = threading.Lock()


def _utc_today() -> str:
    return dt.datetime.now(dt.timezone.utc).date().isoformat()


def check_and_increment(rate_key: str, max_per_day: int) -> Tuple[bool, int]:
    """Atomically check + increment the daily counter.

    Returns (allowed, current_count). On a denied call the count is
    not incremented and the existing count is returned.
    """
    if not is_configured():
        today = _utc_today()
        with _local_lock:
            key = (rate_key, today)
            current = _local_counts.get(key, 0)
            if current >= max_per_day:
                return False, current
            _local_counts[key] = current + 1
            return True, current + 1

    try:
        resp = get_client().post(
            f"{supabase_url()}/rest/v1/rpc/{_RPC_NAME}",
            headers=auth_headers(),
            content=json.dumps({"p_rate_key": rate_key, "p_max": max_per_day}),
        )
        if resp.status_code != 200:
            logger.warning(
                "rate_limit.check_and_increment unexpected status %d: %s",
                resp.status_code,
                resp.text,
            )
            # Fail open — better to allow training than to lock the user
            # out due to a transient Supabase blip.
            return True, 0
        data = resp.json()
    except Exception as e:
        logger.exception("rate_limit.check_and_increment failed: %s", e)
        return True, 0

    row = data[0] if isinstance(data, list) and data else (data if isinstance(data, dict) else {})
    return bool(row.get("allowed", True)), int(row.get("current_count", 0))


def get_count(rate_key: str) -> int:
    """Read-only lookup for the /learn/limits display endpoint."""
    if not is_configured():
        today = _utc_today()
        with _local_lock:
            return _local_counts.get((rate_key, today), 0)

    today = _utc_today()
    try:
        resp = get_client().get(
            f"{supabase_url()}/rest/v1/{_TABLE}",
            params={
                "rate_key": f"eq.{rate_key}",
                "attempt_date": f"eq.{today}",
                "select": "count",
            },
            headers=auth_headers(),
        )
        if resp.status_code != 200:
            logger.warning("rate_limit.get_count unexpected status %d: %s", resp.status_code, resp.text)
            return 0
        rows = resp.json()
    except Exception as e:
        logger.exception("rate_limit.get_count failed: %s", e)
        return 0

    return int(rows[0]["count"]) if rows else 0


def _reset_local_for_tests() -> None:
    with _local_lock:
        _local_counts.clear()

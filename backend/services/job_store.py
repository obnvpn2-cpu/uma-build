"""Persisted async-job store backed by Supabase Postgres.

Replaces the in-memory _jobs OrderedDict in routers/learn.py so that
training results survive container restarts and are visible across
Cloud Run instances. Falls back to an in-memory implementation when
Supabase isn't configured (local dev / CI).

Authorization:
    The Supabase RLS policies only allow auth.uid() = user_id reads,
    which excludes anonymous (user_id IS NULL) jobs from JWT-less
    clients. Since we read with the service_role key, the FastAPI
    layer must enforce ownership: get() compares the requester's
    user_id / session_id with the values stored at put() time.

Stale-job detection:
    Cloud Run can SIGTERM an instance mid-training, leaving rows
    forever in status='running'. On read we promote rows older than
    STALE_THRESHOLD to 'failed'. The PATCH includes status=eq.running
    so a concurrent completion isn't overwritten.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import threading
from collections import OrderedDict
from typing import Any, Dict, Optional

from services._supabase_http import (
    auth_headers,
    get_client,
    is_configured,
    supabase_url,
)

logger = logging.getLogger(__name__)

_TABLE = "learn_jobs"
_MAX_LOCAL_JOBS = 50
STALE_THRESHOLD = dt.timedelta(minutes=10)

# In-memory fallback (used when Supabase isn't configured)
_local_jobs: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
_local_lock = threading.Lock()


def _normalize_status(status: str) -> str:
    # Legacy router used "training"; the table CHECK accepts only
    # ('pending','running','completed','failed').
    if status == "training":
        return "running"
    return status


def put(
    job_id: str,
    data: Dict[str, Any],
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> None:
    """Insert or update a job row.

    `data` is the same dict shape used by the legacy in-memory store:
    {"status": ..., "result": ..., "error": ...}.
    """
    status = _normalize_status(data.get("status", "pending"))
    payload_local = {
        "status": status,
        "result": data.get("result"),
        "error": data.get("error"),
        "user_id": user_id,
        "session_id": session_id,
        "updated_at": dt.datetime.now(dt.timezone.utc),
    }

    if not is_configured():
        with _local_lock:
            if job_id in _local_jobs:
                _local_jobs.move_to_end(job_id)
            _local_jobs[job_id] = payload_local
            while len(_local_jobs) > _MAX_LOCAL_JOBS:
                _local_jobs.popitem(last=False)
        return

    payload = {
        "job_id": job_id,
        "user_id": user_id,
        "session_id": session_id,
        "status": status,
        "result": data.get("result"),
        "error": data.get("error"),
    }
    try:
        resp = get_client().post(
            f"{supabase_url()}/rest/v1/{_TABLE}",
            headers=auth_headers({"Prefer": "resolution=merge-duplicates,return=minimal"}),
            content=json.dumps(payload, default=str),
        )
        if resp.status_code not in (200, 201, 204):
            logger.warning("job_store.put unexpected status %d: %s", resp.status_code, resp.text)
    except Exception as e:
        logger.exception("job_store.put failed for job %s: %s", job_id, e)


def _is_authorized(
    row: Dict[str, Any],
    requester_user_id: Optional[str],
    requester_session_id: Optional[str],
) -> bool:
    row_user = row.get("user_id")
    row_session = row.get("session_id")
    if row_user:
        return bool(requester_user_id) and requester_user_id == row_user
    return bool(requester_session_id) and requester_session_id == row_session


def _to_response(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "status": row.get("status"),
        "result": row.get("result"),
        "error": row.get("error"),
    }


def _parse_updated_at(value: Any) -> Optional[dt.datetime]:
    if isinstance(value, dt.datetime):
        return value if value.tzinfo else value.replace(tzinfo=dt.timezone.utc)
    if isinstance(value, str):
        try:
            return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _is_stale(row: Dict[str, Any]) -> bool:
    if row.get("status") != "running":
        return False
    updated_at = _parse_updated_at(row.get("updated_at"))
    if updated_at is None:
        return False
    return dt.datetime.now(dt.timezone.utc) - updated_at > STALE_THRESHOLD


_STALE_ERROR = "タイムアウト（インスタンス終了の可能性）"


def _mark_stale_failed(job_id: str) -> None:
    """Promote a stale running job to failed.

    Includes status=eq.running so a concurrent completion isn't
    overwritten.
    """
    if not is_configured():
        return
    try:
        resp = get_client().patch(
            f"{supabase_url()}/rest/v1/{_TABLE}",
            params={"job_id": f"eq.{job_id}", "status": "eq.running"},
            headers=auth_headers({"Prefer": "return=minimal"}),
            content=json.dumps({"status": "failed", "error": _STALE_ERROR}),
        )
        if resp.status_code not in (200, 204):
            logger.warning(
                "job_store stale-mark unexpected status %d: %s",
                resp.status_code,
                resp.text,
            )
    except Exception as e:
        logger.exception("job_store.stale-mark failed for %s: %s", job_id, e)


def get(
    job_id: str,
    requester_user_id: Optional[str] = None,
    requester_session_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Fetch a job; returns None if missing or unauthorized.

    On read we also promote stale running jobs to failed (10-min
    threshold) so polling clients eventually see an error instead
    of polling forever.
    """
    if not is_configured():
        with _local_lock:
            row = _local_jobs.get(job_id)
        if row is None:
            return None
        if not _is_authorized(row, requester_user_id, requester_session_id):
            return None
        if _is_stale(row):
            row = {**row, "status": "failed", "error": _STALE_ERROR}
            with _local_lock:
                if job_id in _local_jobs:
                    _local_jobs[job_id] = row
        return _to_response(row)

    try:
        resp = get_client().get(
            f"{supabase_url()}/rest/v1/{_TABLE}",
            params={"job_id": f"eq.{job_id}", "select": "*"},
            headers=auth_headers(),
        )
        if resp.status_code != 200:
            logger.warning("job_store.get unexpected status %d: %s", resp.status_code, resp.text)
            return None
        rows = resp.json()
    except Exception as e:
        logger.exception("job_store.get failed for %s: %s", job_id, e)
        return None

    if not rows:
        return None
    row = rows[0]
    if not _is_authorized(row, requester_user_id, requester_session_id):
        return None
    if _is_stale(row):
        _mark_stale_failed(job_id)
        return {"status": "failed", "result": None, "error": _STALE_ERROR}
    return _to_response(row)


def _reset_local_for_tests() -> None:
    """Clear the in-memory store (test-only helper)."""
    with _local_lock:
        _local_jobs.clear()

"""Learn router for UmaBuild API.

Provides the POST /api/learn endpoint for triggering model training.
Uses an async job pattern: POST returns immediately with a job_id,
and clients poll GET /api/learn/status/{job_id} for results.
"""

import logging
import threading
import uuid
from collections import OrderedDict
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.feature_catalog import get_all_feature_ids
from services.trainer import run_training

logger = logging.getLogger(__name__)

router = APIRouter(tags=["learn"])

# Simple in-memory rate limiting (per-session, per-day)
# In production this would use Redis + proper auth
_daily_attempts: Dict[str, int] = {}
MAX_FREE_DAILY_ATTEMPTS = 5

# In-memory job store with size limit to prevent memory leaks
_MAX_JOBS = 50
_jobs: OrderedDict[str, Dict[str, Any]] = OrderedDict()
_jobs_lock = threading.Lock()


def _store_job(job_id: str, data: Dict[str, Any]) -> None:
    """Store a job, evicting oldest entries if over the limit."""
    with _jobs_lock:
        _jobs[job_id] = data
        while len(_jobs) > _MAX_JOBS:
            _jobs.popitem(last=False)


class LearnRequest(BaseModel):
    """Request model for the learn endpoint."""

    selected_features: List[str] = Field(
        ...,
        min_length=1,
        description="List of feature IDs to use for training",
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Session ID for rate limiting (optional)",
    )


class LearnResponse(BaseModel):
    """Response model for the learn endpoint."""

    model_id: Optional[str] = None
    is_pro: bool = False
    summary: Optional[Dict[str, Any]] = None
    feature_importance: Optional[List[Dict[str, Any]]] = None
    condition_breakdown: Optional[List[Dict[str, Any]]] = None
    yearly_breakdown: Optional[List[Dict[str, Any]]] = None
    distance_breakdown: Optional[List[Dict[str, Any]]] = None
    calibration: Optional[List[Dict[str, Any]]] = None
    meta: Optional[Dict[str, Any]] = None
    locked_features: Optional[List[Dict[str, Any]]] = None
    train_metrics: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@router.post("/learn", status_code=202)
def learn(request: LearnRequest) -> Dict[str, Any]:
    """Start model training asynchronously.

    Returns immediately with a job_id (HTTP 202).
    Clients poll GET /api/learn/status/{job_id} for results.

    Note: is_pro is always False until server-side auth is implemented.
    """
    logger.info(
        "POST /api/learn: %d features (always Free until auth)",
        len(request.selected_features),
    )

    # 1. Validate selected features
    all_valid = set(get_all_feature_ids())
    invalid = [f for f in request.selected_features if f not in all_valid]
    if invalid:
        logger.warning("Invalid feature IDs: %s", invalid)

    valid_features = [f for f in request.selected_features if f in all_valid]
    if not valid_features:
        raise HTTPException(
            status_code=400,
            detail="選択された特徴量が無効です。少なくとも1つの有効な特徴量を選択してください。",
        )

    if len(valid_features) < 2:
        raise HTTPException(
            status_code=400,
            detail="少なくとも2つの特徴量を選択してください。",
        )

    # 2. Check daily attempt limit (always Free until auth)
    session_id = request.session_id or "anonymous"
    current_attempts = _daily_attempts.get(session_id, 0)

    if current_attempts >= MAX_FREE_DAILY_ATTEMPTS:
        raise HTTPException(
            status_code=429,
            detail=f"本日の学習回数の上限（{MAX_FREE_DAILY_ATTEMPTS}回）に達しました。"
            " Proプランにアップグレードすると上限が緩和されます。",
        )

    # Increment attempt counter
    _daily_attempts[session_id] = current_attempts + 1

    # 3. Create job and run training in background thread
    job_id = uuid.uuid4().hex[:8]
    _store_job(job_id, {"status": "training", "result": None, "error": None})

    thread = threading.Thread(
        target=_run_job,
        args=(job_id, valid_features),
        daemon=True,
    )
    thread.start()

    return {"job_id": job_id, "status": "training"}


def _run_job(job_id: str, features: list) -> None:
    """Execute training in a background thread and update job status."""
    try:
        results = run_training(selected_feature_ids=features)
        if results.get("error"):
            _store_job(job_id, {"status": "failed", "result": None, "error": results["error"]})
        else:
            _store_job(job_id, {"status": "completed", "result": results, "error": None})
    except Exception as e:
        logger.exception("Training job %s failed: %s", job_id, str(e))
        _store_job(job_id, {"status": "failed", "result": None, "error": str(e)})


@router.get("/learn/status/{job_id}")
def job_status(job_id: str) -> Dict[str, Any]:
    """Poll the status of a training job."""
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="ジョブが見つかりません")
    return {"job_id": job_id, **job}


@router.get("/learn/limits")
def get_limits(session_id: str = "anonymous") -> Dict[str, Any]:
    """Get the current daily attempt limits and usage.

    Note: Always returns Free limits until server-side auth is implemented.

    Args:
        session_id: Session identifier.

    Returns:
        Dict with max_attempts, used_attempts, remaining_attempts.
    """
    used = _daily_attempts.get(session_id, 0)

    return {
        "max_attempts": MAX_FREE_DAILY_ATTEMPTS,
        "used_attempts": used,
        "remaining_attempts": max(0, MAX_FREE_DAILY_ATTEMPTS - used),
        "is_pro": False,
    }

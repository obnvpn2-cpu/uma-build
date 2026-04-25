"""Learn router for UmaBuild API.

Provides the POST /api/learn endpoint for triggering model training.
Uses an async job pattern: POST returns immediately with a job_id,
and clients poll GET /api/learn/status/{job_id} for results.

Job state and per-day rate limits are persisted in Supabase
(see backend/services/job_store.py and backend/services/rate_limit.py)
so that Cloud Run scale-out instances share a single source of truth.
"""

import logging
import threading
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from middleware.auth import AuthUser, get_optional_user
from ml.quick_train import cache_is_available
from services import job_store, rate_limit
from services.feature_catalog import get_all_feature_ids
from services.trainer import run_training

logger = logging.getLogger(__name__)

router = APIRouter(tags=["learn"])

MAX_FREE_DAILY_ATTEMPTS = 5
MAX_PRO_DAILY_ATTEMPTS = 50


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
    is_first_unlock: bool = False
    summary: Optional[Dict[str, Any]] = None
    feature_importance: Optional[List[Dict[str, Any]]] = None
    condition_breakdown: Optional[List[Dict[str, Any]]] = None
    yearly_breakdown: Optional[List[Dict[str, Any]]] = None
    distance_breakdown: Optional[List[Dict[str, Any]]] = None
    calibration: Optional[List[Dict[str, Any]]] = None
    future_prediction: Optional[List[Dict[str, Any]]] = None
    future_prediction_meta: Optional[Dict[str, Any]] = None
    meta: Optional[Dict[str, Any]] = None
    locked_features: Optional[List[Dict[str, Any]]] = None
    train_metrics: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


def _resolve_rate_key(user: Optional[AuthUser], session_id: Optional[str]) -> str:
    if user:
        return f"user:{user.user_id}"
    return f"session:{session_id or 'anonymous'}"


@router.post("/learn", status_code=202)
async def learn(
    request: LearnRequest,
    user: Optional[AuthUser] = Depends(get_optional_user),
) -> Dict[str, Any]:
    """Start model training asynchronously.

    Returns immediately with a job_id (HTTP 202).
    Clients poll GET /api/learn/status/{job_id} for results.

    Authenticated Pro users get higher limits and more data years.
    """
    is_pro = user.is_pro if user else False
    logger.info(
        "POST /api/learn: %d features (is_pro=%s)",
        len(request.selected_features), is_pro,
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

    # 2. Preflight: fail fast if the feature cache is missing rather than
    # starting a background job that will fail minutes later. Quota is not
    # consumed by a 503 response because the increment happens below.
    if not cache_is_available():
        logger.error("POST /learn blocked: feature cache missing")
        raise HTTPException(
            status_code=503,
            detail="特徴量キャッシュが未生成です。管理者にお問い合わせください。",
        )

    # 3. Atomic check + increment of daily attempt counter (UTC day).
    rate_key = _resolve_rate_key(user, request.session_id)
    max_attempts = MAX_PRO_DAILY_ATTEMPTS if is_pro else MAX_FREE_DAILY_ATTEMPTS
    allowed, current = rate_limit.check_and_increment(rate_key, max_attempts)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"本日の学習回数の上限（{max_attempts}回）に達しました。"
            + ("" if is_pro else " Proプランにアップグレードすると上限が緩和されます。"),
        )

    # 4. Create job and run training in background thread
    job_id = uuid.uuid4().hex
    user_id = user.user_id if user else None
    session_id = request.session_id if not user else None
    job_store.put(
        job_id,
        {"status": "running", "result": None, "error": None},
        user_id=user_id,
        session_id=session_id,
    )

    thread = threading.Thread(
        target=_run_job,
        args=(job_id, valid_features, is_pro, user_id, session_id),
        daemon=True,
    )
    thread.start()

    return {"job_id": job_id, "status": "training"}


def _run_job(
    job_id: str,
    features: list,
    is_pro: bool = False,
    user_id: str | None = None,
    session_id: str | None = None,
) -> None:
    """Execute training in a background thread and update job status."""
    try:
        results = run_training(selected_feature_ids=features, is_pro=is_pro, user_id=user_id)
        if results.get("error"):
            job_store.put(
                job_id,
                {"status": "failed", "result": None, "error": results["error"]},
                user_id=user_id,
                session_id=session_id,
            )
        else:
            job_store.put(
                job_id,
                {"status": "completed", "result": results, "error": None},
                user_id=user_id,
                session_id=session_id,
            )
    except Exception as e:
        logger.exception("Training job %s failed: %s", job_id, str(e))
        job_store.put(
            job_id,
            {"status": "failed", "result": None, "error": str(e)},
            user_id=user_id,
            session_id=session_id,
        )


@router.get("/learn/status/{job_id}")
def job_status(
    job_id: str,
    session_id: Optional[str] = None,
    user: Optional[AuthUser] = Depends(get_optional_user),
) -> Dict[str, Any]:
    """Poll the status of a training job.

    Authorization: the requester must own the job (matching user_id
    for authenticated users, or matching session_id for anonymous).
    """
    requester_user_id = user.user_id if user else None
    requester_session_id = session_id if not user else None
    job = job_store.get(
        job_id,
        requester_user_id=requester_user_id,
        requester_session_id=requester_session_id,
    )
    if not job:
        raise HTTPException(status_code=404, detail="ジョブが見つかりません")
    return {"job_id": job_id, **job}


@router.get("/learn/limits")
async def get_limits(
    session_id: str = "anonymous",
    user: Optional[AuthUser] = Depends(get_optional_user),
) -> Dict[str, Any]:
    """Get the current daily attempt limits and usage.

    Args:
        session_id: Session identifier (for anonymous users).

    Returns:
        Dict with max_attempts, used_attempts, remaining_attempts.
    """
    is_pro = user.is_pro if user else False
    rate_key = _resolve_rate_key(user, session_id)
    max_attempts = MAX_PRO_DAILY_ATTEMPTS if is_pro else MAX_FREE_DAILY_ATTEMPTS
    used = rate_limit.get_count(rate_key)

    return {
        "max_attempts": max_attempts,
        "used_attempts": used,
        "remaining_attempts": max(0, max_attempts - used),
        "is_pro": is_pro,
    }

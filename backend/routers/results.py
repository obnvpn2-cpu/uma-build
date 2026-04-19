"""Results router for UmaBuild API.

Provides endpoints for retrieving cached training results.
Pro status determined by JWT authentication.
"""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException

from middleware.auth import AuthUser, get_optional_user
from services.first_unlock import check_first_unlock_for_model
from services.paywall import mask_results
from services.trainer import get_cached_results

logger = logging.getLogger(__name__)

router = APIRouter(tags=["results"])


@router.get("/results/{model_id}")
async def get_results(
    model_id: str,
    user: Optional[AuthUser] = Depends(get_optional_user),
) -> Dict[str, Any]:
    """Retrieve cached training results for a model.

    Results are masked based on user's subscription status.
    If the user has a first-unlock record for this model, full results are shown.
    """
    is_pro = user.is_pro if user else False
    logger.info("GET /api/results/%s (is_pro=%s)", model_id, is_pro)

    results = get_cached_results(model_id)
    if results is None:
        raise HTTPException(
            status_code=404,
            detail=f"モデル {model_id} の結果が見つかりません。学習結果は一定期間後に削除されます。",
        )

    # Check first-unlock for non-pro authenticated users
    is_first_unlock = False
    if user and not is_pro:
        is_first_unlock = await check_first_unlock_for_model(user.user_id, model_id)

    masked = mask_results(results, is_pro=is_pro, is_first_unlock=is_first_unlock)
    return masked


@router.get("/results/{model_id}/feature-importance")
async def get_feature_importance(
    model_id: str,
    user: Optional[AuthUser] = Depends(get_optional_user),
) -> Dict[str, Any]:
    """Retrieve feature importance for a trained model."""
    is_pro = user.is_pro if user else False
    logger.info("GET /api/results/%s/feature-importance (is_pro=%s)", model_id, is_pro)

    results = get_cached_results(model_id)
    if results is None:
        raise HTTPException(
            status_code=404,
            detail=f"モデル {model_id} の結果が見つかりません。",
        )

    masked = mask_results(results, is_pro=is_pro)
    return {
        "model_id": model_id,
        "feature_importance": masked.get("feature_importance"),
        "is_pro": is_pro,
    }


@router.get("/results/{model_id}/summary")
async def get_summary(
    model_id: str,
    user: Optional[AuthUser] = Depends(get_optional_user),
) -> Dict[str, Any]:
    """Retrieve just the summary for a trained model."""
    is_pro = user.is_pro if user else False
    logger.info("GET /api/results/%s/summary (is_pro=%s)", model_id, is_pro)

    results = get_cached_results(model_id)
    if results is None:
        raise HTTPException(
            status_code=404,
            detail=f"モデル {model_id} の結果が見つかりません。",
        )

    masked = mask_results(results, is_pro=is_pro)
    return {
        "model_id": model_id,
        "summary": masked.get("summary", {}),
        "is_pro": is_pro,
    }

"""Results router for UmaBuild API.

Provides endpoints for retrieving cached training results.
Note: is_pro is always False until server-side auth (Phase 2) is implemented.
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from services.paywall import mask_results
from services.trainer import get_cached_results

logger = logging.getLogger(__name__)

router = APIRouter(tags=["results"])


@router.get("/results/{model_id}")
def get_results(model_id: str) -> Dict[str, Any]:
    """Retrieve cached training results for a model.

    Results are always masked as Free until server-side auth is implemented.
    """
    logger.info("GET /api/results/%s (always Free until auth)", model_id)

    results = get_cached_results(model_id)
    if results is None:
        raise HTTPException(
            status_code=404,
            detail=f"モデル {model_id} の結果が見つかりません。学習結果は一定期間後に削除されます。",
        )

    # Always Free until auth is implemented
    masked = mask_results(results, is_pro=False)
    return masked


@router.get("/results/{model_id}/feature-importance")
def get_feature_importance(model_id: str) -> Dict[str, Any]:
    """Retrieve feature importance for a trained model.

    Always returns masked (Free) data until auth is implemented.
    """
    logger.info("GET /api/results/%s/feature-importance (always Free)", model_id)

    results = get_cached_results(model_id)
    if results is None:
        raise HTTPException(
            status_code=404,
            detail=f"モデル {model_id} の結果が見つかりません。",
        )

    # Always Free until auth
    masked = mask_results(results, is_pro=False)
    return {
        "model_id": model_id,
        "feature_importance": masked.get("feature_importance"),
        "is_pro": False,
    }


@router.get("/results/{model_id}/summary")
def get_summary(model_id: str) -> Dict[str, Any]:
    """Retrieve just the summary for a trained model.

    Always returns Free-tier view until auth is implemented.
    """
    logger.info("GET /api/results/%s/summary (always Free)", model_id)

    results = get_cached_results(model_id)
    if results is None:
        raise HTTPException(
            status_code=404,
            detail=f"モデル {model_id} の結果が見つかりません。",
        )

    masked = mask_results(results, is_pro=False)
    return {
        "model_id": model_id,
        "summary": masked.get("summary", {}),
        "is_pro": False,
    }

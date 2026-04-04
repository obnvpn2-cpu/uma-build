"""Results router for UmaBuild API.

Provides endpoints for retrieving cached training results.
"""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException

from services.paywall import mask_results
from services.trainer import get_cached_results

logger = logging.getLogger(__name__)

router = APIRouter(tags=["results"])


@router.get("/results/{model_id}")
def get_results(model_id: str, is_pro: bool = False) -> Dict[str, Any]:
    """Retrieve cached training results for a model.

    Results are masked according to the user's subscription tier.

    Args:
        model_id: The model identifier returned from /api/learn.
        is_pro: Whether the user is a pro subscriber.

    Returns:
        Training results with appropriate paywall masking.
    """
    logger.info("GET /api/results/%s (is_pro=%s)", model_id, is_pro)

    results = get_cached_results(model_id)
    if results is None:
        raise HTTPException(
            status_code=404,
            detail=f"モデル {model_id} の結果が見つかりません。学習結果は一定期間後に削除されます。",
        )

    # Apply paywall masking
    masked = mask_results(results, is_pro=is_pro)
    return masked


@router.get("/results/{model_id}/feature-importance")
def get_feature_importance(model_id: str, is_pro: bool = False) -> Dict[str, Any]:
    """Retrieve feature importance for a trained model.

    Args:
        model_id: The model identifier.
        is_pro: Whether the user is a pro subscriber.

    Returns:
        Feature importance data (masked for free users).
    """
    logger.info("GET /api/results/%s/feature-importance (is_pro=%s)", model_id, is_pro)

    results = get_cached_results(model_id)
    if results is None:
        raise HTTPException(
            status_code=404,
            detail=f"モデル {model_id} の結果が見つかりません。",
        )

    if is_pro:
        return {
            "model_id": model_id,
            "feature_importance": results.get("feature_importance", []),
            "is_pro": True,
        }
    else:
        # For free users, return masked feature importance
        masked = mask_results(results, is_pro=False)
        return {
            "model_id": model_id,
            "feature_importance": masked.get("feature_importance", []),
            "is_pro": False,
        }


@router.get("/results/{model_id}/summary")
def get_summary(model_id: str, is_pro: bool = False) -> Dict[str, Any]:
    """Retrieve just the summary for a trained model.

    This is a lightweight endpoint that returns only the summary
    portion of the results.

    Args:
        model_id: The model identifier.
        is_pro: Whether the user is a pro subscriber.

    Returns:
        Summary metrics.
    """
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

"""Paywall masking service for UmaBuild.

For free-tier users, masks detailed results with null values.
Pro users see everything (determined server-side only).
"""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def mask_results(results: Dict[str, Any], is_pro: bool = False) -> Dict[str, Any]:
    """Apply paywall masking to training results.

    For free users:
    - summary: Partially visible (roi visible, hit_rate visible, reliability visible)
    - condition_breakdown: null (locked)
    - yearly_breakdown: null (locked)
    - distance_breakdown: null (locked)
    - calibration: null (locked)
    - feature_importance: null (locked)
    - future_prediction: Locked (unavailable)
    - overfitting_detection: Locked (unavailable)

    For pro users:
    - Everything visible

    Args:
        results: Full training results dict.
        is_pro: Whether the user is a pro subscriber (server-determined).

    Returns:
        Masked results dict.
    """
    if is_pro:
        # Pro users see everything
        return {
            **results,
            "is_pro": True,
            "locked_features": [],
        }

    # Free tier masking
    logger.info("Applying free-tier paywall masking")

    # Summary: partially visible
    summary = results.get("summary", {})
    masked_summary = {
        "roi": summary.get("roi"),
        "hit_rate": summary.get("hit_rate"),
        "n_bets": summary.get("n_bets"),
        "n_races": summary.get("n_races"),
        "reliability_stars": summary.get("reliability_stars"),
        # Mask detailed financials
        "total_return": None,
        "total_bet": None,
        "profit": None,
        "n_hits": None,
        "is_blurred": False,
    }

    # Determine data_years from meta
    meta = results.get("meta", {})
    data_years = meta.get("data_years", 2) if meta else 2

    masked = {
        "model_id": results.get("model_id"),
        "is_pro": False,
        "summary": masked_summary,
        # Return null for all breakdown fields — frontend shows lock UI
        "feature_importance": None,
        "condition_breakdown": None,
        "yearly_breakdown": None,
        "distance_breakdown": None,
        "calibration": None,
        "meta": {
            "n_features": meta.get("n_features"),
            "data_years": data_years,
            "elapsed_sec": meta.get("elapsed_sec"),
            # Mask detailed info
            "n_train": None,
            "n_val": None,
            "feature_names": None,
        },
        "locked_features": [
            {
                "id": "future_prediction",
                "name": "未来レース予測",
                "description": "次のレース開催の予測結果を確認できます",
            },
            {
                "id": "overfitting_detection",
                "name": "過学習検出",
                "description": "モデルの過学習リスクを分析します",
            },
            {
                "id": "detailed_breakdown",
                "name": "詳細分析",
                "description": "条件別・年別の詳細なROI分析を確認できます",
            },
        ],
    }

    return masked

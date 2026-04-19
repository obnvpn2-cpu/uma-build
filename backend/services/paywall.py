"""Paywall masking service for UmaBuild.

For free-tier users, masks detailed results with partial preview data.
Pro users see everything (determined server-side only).
"""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

# Free-tier preview limits (endowment effect: show just enough to want more)
FREE_YEARLY_PREVIEW = 1       # Latest 1 year of ROI
FREE_FEATURE_IMPORTANCE_PREVIEW = 3  # Top 3 features
FREE_CONDITION_PREVIEW = 1    # 1 row only


def mask_results(
    results: Dict[str, Any],
    is_pro: bool = False,
    is_first_unlock: bool = False,
) -> Dict[str, Any]:
    """Apply paywall masking to training results.

    For free users:
    - summary: Partially visible (roi visible, hit_rate visible, reliability visible)
    - yearly_breakdown: Latest 1 year shown, rest blurred
    - feature_importance: Top 3 shown, rest blurred
    - condition_breakdown: 1 row shown, rest blurred
    - distance_breakdown: null (locked)
    - calibration: null (locked)
    - future_prediction: Locked (unavailable)
    - overfitting_detection: Locked (unavailable)

    For first_unlock (one-time):
    - Everything visible (same as Pro)
    - is_first_unlock=True flag set
    - is_pro remains False

    For pro users:
    - Everything visible

    Args:
        results: Full training results dict.
        is_pro: Whether the user is a pro subscriber (server-determined).
        is_first_unlock: Whether this is the user's first-unlock experience.

    Returns:
        Masked results dict.
    """
    if is_pro:
        # Pro users see everything
        return {
            **results,
            "is_pro": True,
            "is_first_unlock": False,
            "locked_features": [],
        }

    if is_first_unlock:
        # First-unlock: show everything, but flag as non-pro
        return {
            **results,
            "is_pro": False,
            "is_first_unlock": True,
            "locked_features": [],
        }

    # Free tier masking
    logger.info("Applying free-tier paywall masking (with preview)")

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

    # --- Preview data (endowment effect) ---

    # Yearly breakdown: show latest N years, blur the rest
    yearly_raw = results.get("yearly_breakdown") or []
    yearly_preview = _preview_yearly(yearly_raw)

    # Feature importance: show top N, blur the rest
    fi_raw = results.get("feature_importance") or []
    fi_preview = _preview_feature_importance(fi_raw)

    # Condition breakdown: show first N rows, blur the rest
    cond_raw = results.get("condition_breakdown") or []
    cond_preview = _preview_condition(cond_raw)

    masked = {
        "model_id": results.get("model_id"),
        "is_pro": False,
        "is_first_unlock": False,
        # Partially visible previews
        "summary": masked_summary,
        "yearly_breakdown": yearly_preview if yearly_preview else None,
        "feature_importance": fi_preview if fi_preview else None,
        "condition_breakdown": cond_preview if cond_preview else None,
        # Still fully locked
        "distance_breakdown": None,
        "calibration": None,
        "future_prediction": None,
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


def _preview_yearly(yearly: list) -> list:
    """Return yearly breakdown with only latest N years visible."""
    if not yearly:
        return []
    # Sort by year descending to pick latest
    sorted_yearly = sorted(yearly, key=lambda x: x.get("year", 0), reverse=True)
    preview = []
    for i, item in enumerate(sorted_yearly):
        row = dict(item)
        if i < FREE_YEARLY_PREVIEW:
            row["is_blurred"] = False
        else:
            row["roi"] = None
            row["profit"] = None
            row["hit_rate"] = None
            row["is_blurred"] = True
        preview.append(row)
    # Return in original year order
    return sorted(preview, key=lambda x: x.get("year", 0))


def _preview_feature_importance(fi: list) -> list:
    """Return feature importance with only top N visible."""
    if not fi:
        return []
    # Sort by importance descending (or rank ascending)
    sorted_fi = sorted(fi, key=lambda x: x.get("importance", 0) or 0, reverse=True)
    preview = []
    for i, item in enumerate(sorted_fi):
        row = dict(item)
        row["rank"] = i + 1
        if i < FREE_FEATURE_IMPORTANCE_PREVIEW:
            row["is_blurred"] = False
        else:
            row["importance"] = None
            row["is_blurred"] = True
        preview.append(row)
    return preview


def _preview_condition(cond: list) -> list:
    """Return condition breakdown with only first N rows visible."""
    if not cond:
        return []
    preview = []
    for i, item in enumerate(cond):
        row = dict(item)
        if i < FREE_CONDITION_PREVIEW:
            row["is_blurred"] = False
        else:
            row["roi"] = None
            row["profit"] = None
            row["hit_rate"] = None
            row["is_blurred"] = True
        preview.append(row)
    return preview

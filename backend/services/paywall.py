"""Paywall masking service for UmaBuild.

For free-tier users, masks detailed results with randomized dummy values.
Pro users see everything.
"""

import logging
import random
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _generate_dummy_condition_breakdown(n_items: int = 6) -> List[Dict[str, Any]]:
    """Generate randomized dummy condition breakdown data."""
    surfaces = ["芝", "ダート"]
    conditions = ["良", "稍重", "重", "不良"]

    items = []
    for surface in surfaces:
        for condition in conditions:
            items.append({
                "surface": surface,
                "track_condition": condition,
                "n_bets": random.randint(10, 200),
                "n_hits": random.randint(1, 30),
                "hit_rate": round(random.uniform(5, 30), 1),
                "roi": None,  # Masked
                "profit": None,  # Masked
                "is_blurred": True,
            })
            if len(items) >= n_items:
                break
        if len(items) >= n_items:
            break

    return items


def _generate_dummy_yearly_breakdown(n_years: int = 2) -> List[Dict[str, Any]]:
    """Generate randomized dummy yearly breakdown data."""
    current_year = 2024
    items = []
    for i in range(n_years):
        items.append({
            "year": current_year - i,
            "n_bets": random.randint(50, 300),
            "n_hits": random.randint(5, 50),
            "hit_rate": round(random.uniform(5, 25), 1),
            "roi": None,  # Masked
            "profit": None,  # Masked
            "is_blurred": True,
        })
    return items


def _generate_dummy_distance_breakdown(n_items: int = 5) -> List[Dict[str, Any]]:
    """Generate randomized dummy distance breakdown data."""
    categories = [
        "短距離(~1200m)", "マイル(~1600m)", "中距離(~2000m)",
        "中長距離(~2400m)", "長距離(2500m~)",
    ]
    items = []
    for cat in categories[:n_items]:
        items.append({
            "distance_category": cat,
            "n_bets": random.randint(10, 150),
            "n_hits": random.randint(1, 25),
            "hit_rate": round(random.uniform(5, 25), 1),
            "roi": None,  # Masked
            "profit": None,  # Masked
            "is_blurred": True,
        })
    return items


def _generate_dummy_calibration(n_bins: int = 10) -> List[Dict[str, Any]]:
    """Generate randomized dummy calibration data."""
    items = []
    for i in range(n_bins):
        predicted = round(0.05 + i * 0.1, 2)
        items.append({
            "bin": f"({predicted - 0.05:.2f}, {predicted + 0.05:.2f}]",
            "predicted_avg": predicted,
            "actual_avg": None,  # Masked
            "count": random.randint(20, 200),
            "is_blurred": True,
        })
    return items


def _generate_dummy_feature_importance(
    feature_names: Optional[List[str]] = None,
    n_features: int = 10,
) -> List[Dict[str, Any]]:
    """Generate randomized dummy feature importance data."""
    if feature_names is None:
        feature_names = [
            "distance", "horse_win_rate", "jockey_win_rate",
            "horse_avg_finish", "body_weight", "horse_recent3_avg",
            "weight_carried", "horse_in3_rate", "field_size", "waku",
        ]

    items = []
    total = 100.0
    for i, name in enumerate(feature_names[:n_features]):
        importance = round(random.uniform(2, total / max(1, n_features - i)), 1)
        items.append({
            "feature": name,
            "importance": None,  # Masked
            "rank": i + 1,
            "is_blurred": True,
        })
        total -= importance

    return items


def mask_results(results: Dict[str, Any], is_pro: bool = False) -> Dict[str, Any]:
    """Apply paywall masking to training results.

    For free users:
    - summary: Partially visible (roi visible, hit_rate visible, reliability visible)
    - condition_breakdown: Replaced with dummy values, ROI masked
    - yearly_breakdown: Replaced with dummy values, ROI masked
    - distance_breakdown: Replaced with dummy values, ROI masked
    - calibration: Replaced with dummy values
    - feature_importance: Replaced with dummy values
    - future_prediction: Locked (unavailable)
    - overfitting_detection: Locked (unavailable)

    For pro users:
    - Everything visible

    Args:
        results: Full training results dict.
        is_pro: Whether the user is a pro subscriber.

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

    # Feature importance: mask with dummy
    feature_names = None
    meta = results.get("meta", {})
    if meta and "feature_names" in meta:
        feature_names = meta["feature_names"]
    dummy_fi = _generate_dummy_feature_importance(feature_names)

    # Determine data_years from meta
    data_years = meta.get("data_years", 2) if meta else 2

    masked = {
        "model_id": results.get("model_id"),
        "is_pro": False,
        "summary": masked_summary,
        "feature_importance": dummy_fi,
        "condition_breakdown": _generate_dummy_condition_breakdown(),
        "yearly_breakdown": _generate_dummy_yearly_breakdown(n_years=data_years),
        "distance_breakdown": _generate_dummy_distance_breakdown(),
        "calibration": _generate_dummy_calibration(),
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

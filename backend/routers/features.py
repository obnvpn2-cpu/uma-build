"""Features router for UmaBuild API.

Provides endpoints for retrieving the feature catalog and preset templates.
"""

import logging
from typing import Any, Dict, List

from fastapi import APIRouter

from services.feature_catalog import get_catalog, get_default_feature_ids

logger = logging.getLogger(__name__)

router = APIRouter(tags=["features"])

# Preset templates: curated feature sets for common strategies
PRESET_TEMPLATES: List[Dict[str, Any]] = [
    {
        "id": "anauma",
        "name": "穴馬発見型",
        "description": "人気薄の激走馬を見つける。高配当狙いの攻撃的モデル",
        "icon": "🎯",
        "features": [
            "distance", "surface", "track_condition", "field_size",
            "horse_win_rate", "horse_in3_rate", "horse_avg_finish",
            "horse_recent3_avg", "horse_days_since_last", "horse_last_finish",
            "body_weight", "weight_diff",
            "horse_avg_last3f", "horse_running_style",
            "horse_class_change", "horse_prize_rank_in_field",
            "jockey_win_rate", "jockey_recent20_win_rate",
            "trainer_win_rate",
            "win_odds", "popularity",
        ],
    },
    {
        "id": "kenjitsu_fukusho",
        "name": "堅実複勝型",
        "description": "的中率重視の安定モデル。複勝で堅実に回収",
        "icon": "🛡️",
        "features": [
            "distance", "surface", "track_condition", "field_size",
            "waku", "umaban", "age", "weight_carried",
            "horse_n_starts", "horse_win_rate", "horse_in3_rate",
            "horse_avg_finish", "horse_dist_win_rate", "horse_surface_win_rate",
            "horse_recent3_avg", "horse_last_finish",
            "body_weight", "weight_diff",
            "horse_avg_corner4", "horse_avg_last3f",
            "horse_total_prize",
            "jockey_win_rate", "jockey_recent20_win_rate",
            "trainer_win_rate", "trainer_recent20_win_rate",
        ],
    },
    {
        "id": "dirt_tokka",
        "name": "ダート特化型",
        "description": "ダートレースに特化。馬場・体重・パワー系指標を重視",
        "icon": "🏜️",
        "features": [
            "distance", "surface", "track_condition", "field_size",
            "waku", "umaban", "weight_carried",
            "horse_win_rate", "horse_in3_rate",
            "horse_dist_win_rate", "horse_surface_win_rate",
            "horse_recent3_avg", "horse_last_finish",
            "body_weight", "weight_diff", "horse_avg_weight",
            "horse_avg_corner4", "horse_avg_last3f", "horse_running_style",
            "horse_total_prize", "horse_class_change",
            "jockey_win_rate", "jockey_surface_win_rate",
            "trainer_win_rate", "trainer_surface_win_rate",
            "sire_group", "damsire_group",
        ],
    },
    {
        "id": "shiba_chukyo",
        "name": "芝中距離型",
        "description": "芝1600-2400mに最適化。血統・上がり3F・位置取りを重視",
        "icon": "🌿",
        "features": [
            "distance", "surface", "track_condition", "grade", "field_size",
            "waku", "umaban", "age", "weight_carried",
            "horse_win_rate", "horse_in3_rate",
            "horse_dist_win_rate", "horse_surface_win_rate",
            "horse_recent3_avg", "horse_last_finish",
            "body_weight", "weight_diff",
            "horse_avg_corner3", "horse_avg_corner4",
            "horse_avg_last3f", "horse_best_last3f", "horse_running_style",
            "horse_total_prize", "horse_avg_prize",
            "jockey_win_rate", "jockey_dist_win_rate",
            "trainer_win_rate",
            "sire_group", "damsire_group",
        ],
    },
]


@router.get("/features")
def get_features() -> List[Dict[str, Any]]:
    """Return the full feature catalog.

    Each category contains a list of selectable features with:
    - id: Unique feature identifier
    - label: Japanese display name
    - description: Japanese description
    - default_on: Whether the feature is enabled by default
    """
    logger.info("GET /api/features")
    return get_catalog()


@router.get("/features/defaults")
def get_defaults() -> Dict[str, Any]:
    """Return the list of feature IDs enabled by default.

    Useful for initializing the frontend UI.
    """
    logger.info("GET /api/features/defaults")
    default_ids = get_default_feature_ids()
    return {
        "default_features": default_ids,
        "count": len(default_ids),
    }


@router.get("/features/presets")
def get_presets() -> List[Dict[str, Any]]:
    """Return preset feature templates for common strategies."""
    logger.info("GET /api/features/presets")
    return PRESET_TEMPLATES

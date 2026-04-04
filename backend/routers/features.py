"""Features router for UmaBuild API.

Provides endpoints for retrieving the feature catalog.
"""

import logging
from typing import Any, Dict, List

from fastapi import APIRouter

from services.feature_catalog import get_catalog, get_default_feature_ids

logger = logging.getLogger(__name__)

router = APIRouter(tags=["features"])


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

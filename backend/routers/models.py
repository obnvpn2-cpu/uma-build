"""Models router for UmaBuild API.

Provides endpoints for saving, listing, comparing, and managing user models.
All endpoints require authentication.
"""

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from middleware.auth import AuthUser, get_required_user
from services.model_store import (
    FREE_MODEL_LIMIT,
    PRO_MODEL_LIMIT,
    count_models,
    delete_model,
    list_models,
    rename_model,
    save_model,
)
from services.paywall import mask_results
from services.trainer import get_cached_results

logger = logging.getLogger(__name__)

router = APIRouter(tags=["models"])


class SaveModelRequest(BaseModel):
    model_id: str
    name: str = Field(default="無題のモデル", max_length=100)
    feature_ids: List[str] = Field(default_factory=list)


class RenameModelRequest(BaseModel):
    name: str = Field(max_length=100)


class CompareRequest(BaseModel):
    model_ids: List[str] = Field(min_length=2, max_length=5)


@router.get("/models")
async def get_models(user: AuthUser = Depends(get_required_user)) -> Dict[str, Any]:
    """List saved models for the authenticated user."""
    logger.info("GET /api/models (user=%s)", user.user_id)
    models = await list_models(user.user_id)
    limit = PRO_MODEL_LIMIT if user.is_pro else FREE_MODEL_LIMIT
    return {"models": models, "limit": limit, "count": len(models)}


@router.post("/models")
async def post_model(
    body: SaveModelRequest,
    user: AuthUser = Depends(get_required_user),
) -> Dict[str, Any]:
    """Save a model with snapshot metrics."""
    logger.info("POST /api/models (user=%s, model=%s)", user.user_id, body.model_id)

    # Check limit
    limit = PRO_MODEL_LIMIT if user.is_pro else FREE_MODEL_LIMIT
    current_count = await count_models(user.user_id)
    if current_count >= limit:
        raise HTTPException(
            status_code=403,
            detail=f"保存上限に達しました（{limit}モデルまで）。{'不要なモデルを削除してください。' if user.is_pro else 'Proプランにアップグレードすると最大20モデルまで保存できます。'}",
        )

    # Extract metrics from cached results
    roi = None
    hit_rate = None
    reliability_stars = None
    n_features = None
    data_years = 2

    cached = get_cached_results(body.model_id)
    if cached:
        summary = cached.get("summary", {})
        roi = summary.get("roi")
        hit_rate = summary.get("hit_rate")
        reliability_stars = summary.get("reliability_stars")
        meta = cached.get("meta", {})
        if meta:
            n_features = meta.get("n_features")
            data_years = meta.get("data_years", 2)

    saved = await save_model(
        user_id=user.user_id,
        model_id=body.model_id,
        name=body.name,
        roi=roi,
        hit_rate=hit_rate,
        reliability_stars=reliability_stars,
        n_features=n_features,
        feature_ids=body.feature_ids,
        data_years=data_years,
    )
    if saved is None:
        raise HTTPException(
            status_code=409,
            detail="このモデルは既に保存されています。",
        )
    return {"saved": saved}


@router.delete("/models/{model_id}")
async def remove_model(
    model_id: str,
    user: AuthUser = Depends(get_required_user),
) -> Dict[str, Any]:
    """Delete a saved model."""
    logger.info("DELETE /api/models/%s (user=%s)", model_id, user.user_id)
    ok = await delete_model(user.user_id, model_id)
    if not ok:
        raise HTTPException(status_code=404, detail="モデルが見つかりません。")
    return {"deleted": True}


@router.patch("/models/{model_id}")
async def patch_model(
    model_id: str,
    body: RenameModelRequest,
    user: AuthUser = Depends(get_required_user),
) -> Dict[str, Any]:
    """Rename a saved model."""
    logger.info("PATCH /api/models/%s (user=%s, name=%s)", model_id, user.user_id, body.name)
    ok = await rename_model(user.user_id, model_id, body.name)
    if not ok:
        raise HTTPException(status_code=404, detail="モデルが見つかりません。")
    return {"renamed": True}


@router.post("/models/compare")
async def compare_models(
    body: CompareRequest,
    user: AuthUser = Depends(get_required_user),
) -> Dict[str, Any]:
    """Compare 2-5 models side by side.

    Returns masked results for free users, full for Pro.
    Includes feature_diff showing common and unique features.
    """
    logger.info("POST /api/models/compare (user=%s, models=%s)", user.user_id, body.model_ids)

    # Fetch saved models to get feature_ids and names
    saved_models = await list_models(user.user_id)
    saved_map: Dict[str, Dict[str, Any]] = {m["model_id"]: m for m in saved_models}

    models_data = []
    all_feature_sets: Dict[str, set] = {}

    for mid in body.model_ids:
        saved = saved_map.get(mid)
        if not saved:
            raise HTTPException(status_code=404, detail=f"モデル {mid} が見つかりません。")

        cached = get_cached_results(mid)
        if cached:
            masked = mask_results(cached, is_pro=user.is_pro)
        else:
            # Use snapshot metrics from saved model
            masked = {
                "model_id": mid,
                "is_pro": user.is_pro,
                "summary": {
                    "roi": saved.get("roi"),
                    "hit_rate": saved.get("hit_rate"),
                    "reliability_stars": saved.get("reliability_stars"),
                },
            }

        masked["name"] = saved.get("name", "無題のモデル")
        masked["feature_ids"] = saved.get("feature_ids", [])
        models_data.append(masked)

        feature_set = set(saved.get("feature_ids", []))
        all_feature_sets[mid] = feature_set

    # Calculate feature diff
    if all_feature_sets:
        all_sets = list(all_feature_sets.values())
        common = set.intersection(*all_sets) if all_sets else set()
        unique = {mid: list(fs - common) for mid, fs in all_feature_sets.items()}
    else:
        common = set()
        unique = {}

    return {
        "models": models_data,
        "feature_diff": {
            "common": sorted(common),
            "unique": unique,
        },
    }

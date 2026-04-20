"""Model store service for UmaBuild.

Manages saved models for users via Supabase REST API.
Follows the same pattern as first_unlock.py (httpx async + graceful fallback).
"""

import logging
import os
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

_TABLE = "user_models"

# Save limits per plan
FREE_MODEL_LIMIT = 3
PRO_MODEL_LIMIT = 20


def _is_configured() -> bool:
    return bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY)


def _headers() -> dict:
    return {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


async def count_models(user_id: str) -> int:
    """Count how many models a user has saved."""
    if not _is_configured() or not user_id:
        return 0
    try:
        url = f"{SUPABASE_URL}/rest/v1/{_TABLE}?user_id=eq.{user_id}&select=id"
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url, headers=_headers())
            if resp.status_code == 200:
                return len(resp.json())
    except Exception as e:
        logger.warning("count_models failed: %s", e)
    return 0


async def save_model(
    user_id: str,
    model_id: str,
    name: str,
    roi: Optional[float] = None,
    hit_rate: Optional[float] = None,
    reliability_stars: Optional[int] = None,
    n_features: Optional[int] = None,
    feature_ids: Optional[List[str]] = None,
    data_years: int = 2,
) -> Optional[Dict[str, Any]]:
    """Save a model. Returns the saved record or None on failure.

    Returns None with 409-like handling if the model_id already exists for this user.
    """
    if not _is_configured() or not user_id or not model_id:
        return None
    try:
        url = f"{SUPABASE_URL}/rest/v1/{_TABLE}"
        payload = {
            "user_id": user_id,
            "model_id": model_id,
            "name": name or "無題のモデル",
            "roi": roi,
            "hit_rate": hit_rate,
            "reliability_stars": reliability_stars,
            "n_features": n_features,
            "feature_ids": feature_ids or [],
            "data_years": data_years,
        }
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(url, json=payload, headers=_headers())
            if resp.status_code in (200, 201):
                data = resp.json()
                logger.info("Model saved: user=%s model=%s", user_id, model_id)
                return data[0] if isinstance(data, list) and data else data
            elif resp.status_code == 409 or (resp.status_code == 400 and "duplicate" in resp.text.lower()):
                logger.info("Model already saved: user=%s model=%s (duplicate)", user_id, model_id)
                return None
            else:
                logger.warning("save_model unexpected status %d: %s", resp.status_code, resp.text)
    except Exception as e:
        logger.warning("save_model failed: %s", e)
    return None


async def list_models(user_id: str) -> List[Dict[str, Any]]:
    """List all saved models for a user, newest first."""
    if not _is_configured() or not user_id:
        return []
    try:
        url = f"{SUPABASE_URL}/rest/v1/{_TABLE}?user_id=eq.{user_id}&order=created_at.desc"
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url, headers=_headers())
            if resp.status_code == 200:
                return resp.json()
    except Exception as e:
        logger.warning("list_models failed: %s", e)
    return []


async def delete_model(user_id: str, model_id: str) -> bool:
    """Delete a saved model. Returns True on success."""
    if not _is_configured() or not user_id or not model_id:
        return False
    try:
        url = f"{SUPABASE_URL}/rest/v1/{_TABLE}?user_id=eq.{user_id}&model_id=eq.{model_id}"
        headers = {**_headers(), "Prefer": "return=minimal"}
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.delete(url, headers=headers)
            if resp.status_code in (200, 204):
                logger.info("Model deleted: user=%s model=%s", user_id, model_id)
                return True
            else:
                logger.warning("delete_model unexpected status %d: %s", resp.status_code, resp.text)
    except Exception as e:
        logger.warning("delete_model failed: %s", e)
    return False


async def rename_model(user_id: str, model_id: str, new_name: str) -> bool:
    """Rename a saved model. Returns True on success."""
    if not _is_configured() or not user_id or not model_id or not new_name:
        return False
    try:
        url = f"{SUPABASE_URL}/rest/v1/{_TABLE}?user_id=eq.{user_id}&model_id=eq.{model_id}"
        headers = {**_headers(), "Prefer": "return=minimal"}
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.patch(url, json={"name": new_name}, headers=headers)
            if resp.status_code in (200, 204):
                logger.info("Model renamed: user=%s model=%s -> %s", user_id, model_id, new_name)
                return True
            else:
                logger.warning("rename_model unexpected status %d: %s", resp.status_code, resp.text)
    except Exception as e:
        logger.warning("rename_model failed: %s", e)
    return False

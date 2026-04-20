"""First-unlock service for UmaBuild.

Manages the one-time full-results reveal for new users.
Uses synchronous HTTP client because this runs from background threads.
"""

import logging
import os

import httpx

logger = logging.getLogger(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

_TABLE = "user_first_unlock"


def _is_configured() -> bool:
    """Return True if Supabase is configured."""
    return bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY)


def _headers() -> dict:
    return {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }


def check_first_unlock_available(user_id: str) -> bool:
    """Check if the user has NOT yet used their first unlock.

    Returns True if the user can still receive a first unlock.
    Returns False if Supabase is not configured or already used.
    """
    if not _is_configured():
        return False
    if not user_id:
        return False

    try:
        url = (
            f"{SUPABASE_URL}/rest/v1/{_TABLE}"
            f"?user_id=eq.{user_id}"
            f"&select=id"
            f"&limit=1"
        )
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(url, headers=_headers())
            if resp.status_code == 200:
                return len(resp.json()) == 0
    except Exception as e:
        logger.warning("check_first_unlock_available failed: %s", e)
    return False


def mark_first_unlock_used(user_id: str, model_id: str) -> None:
    """Record that the user has consumed their first unlock.

    Silently ignores UNIQUE constraint violations (= already used).
    """
    if not _is_configured():
        return
    if not user_id:
        return

    try:
        url = f"{SUPABASE_URL}/rest/v1/{_TABLE}"
        payload = {"user_id": user_id, "model_id": model_id}
        with httpx.Client(timeout=5.0) as client:
            resp = client.post(url, json=payload, headers=_headers())
            if resp.status_code in (201, 200):
                logger.info("First unlock marked for user %s, model %s", user_id, model_id)
            elif resp.status_code == 409 or (resp.status_code == 400 and "duplicate" in resp.text.lower()):
                logger.info("First unlock already used for user %s (duplicate)", user_id)
            else:
                logger.warning("mark_first_unlock_used unexpected status %d: %s", resp.status_code, resp.text)
    except Exception as e:
        logger.warning("mark_first_unlock_used failed: %s", e)


async def check_first_unlock_for_model(user_id: str, model_id: str) -> bool:
    """Check if this model_id was the user's first-unlock model (async version).

    Used by the results endpoint to determine if a non-Pro user should
    see full results for this specific model.
    """
    if not _is_configured():
        return False
    if not user_id or not model_id:
        return False

    try:
        url = (
            f"{SUPABASE_URL}/rest/v1/{_TABLE}"
            f"?user_id=eq.{user_id}"
            f"&model_id=eq.{model_id}"
            f"&select=id"
            f"&limit=1"
        )
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url, headers=_headers())
            if resp.status_code == 200:
                return len(resp.json()) > 0
    except Exception as e:
        logger.warning("check_first_unlock_for_model failed: %s", e)
    return False

"""Supabase JWT authentication middleware for UmaBuild.

Provides optional authentication: endpoints work for both anonymous
and authenticated users. Pro status is determined by checking the
subscriptions table in Supabase PostgreSQL.
"""

import logging
import os
from typing import Optional

import httpx
import jwt
from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)

# Supabase config (set via environment variables)
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_JWT_SECRET = os.environ.get("SUPABASE_JWT_SECRET", "")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")


class AuthUser:
    """Authenticated user context."""

    def __init__(self, user_id: str, email: str, is_pro: bool = False):
        self.user_id = user_id
        self.email = email
        self.is_pro = is_pro


def _decode_jwt(token: str) -> Optional[dict]:
    """Decode and verify a Supabase JWT token."""
    if not SUPABASE_JWT_SECRET:
        logger.debug("SUPABASE_JWT_SECRET not set, skipping JWT verification")
        return None
    try:
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
        )
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("JWT token expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning("Invalid JWT token: %s", e)
        return None


async def _check_subscription(user_id: str) -> bool:
    """Check if a user has an active Pro subscription via Supabase REST API."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        return False
    try:
        url = (
            f"{SUPABASE_URL}/rest/v1/subscriptions"
            f"?user_id=eq.{user_id}"
            f"&plan=eq.pro"
            f"&status=in.(active,trialing)"
            f"&select=id"
            f"&limit=1"
        )
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url,
                headers={
                    "apikey": SUPABASE_SERVICE_ROLE_KEY,
                    "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
                },
                timeout=5.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                return len(data) > 0
    except Exception as e:
        logger.warning("Subscription check failed: %s", e)
    return False


def _extract_token(request: Request) -> Optional[str]:
    """Extract Bearer token from Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return None


async def get_optional_user(request: Request) -> Optional[AuthUser]:
    """Dependency: returns AuthUser if valid JWT present, None otherwise.

    This allows endpoints to work for both anonymous and authenticated users.
    """
    token = _extract_token(request)
    if not token:
        return None

    payload = _decode_jwt(token)
    if not payload:
        return None

    user_id = payload.get("sub")
    email = payload.get("email", "")
    if not user_id:
        return None

    is_pro = await _check_subscription(user_id)
    return AuthUser(user_id=user_id, email=email, is_pro=is_pro)


async def get_required_user(request: Request) -> AuthUser:
    """Dependency: requires valid JWT. Raises 401 if not authenticated."""
    user = await get_optional_user(request)
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="認証が必要です。ログインしてください。",
        )
    return user

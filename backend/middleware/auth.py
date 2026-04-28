"""Supabase JWT authentication middleware for UmaBuild.

Provides optional authentication: endpoints work for both anonymous
and authenticated users. Pro status is determined by checking the
subscriptions table in Supabase PostgreSQL.
"""

import logging
import os
import re
import time
from typing import Optional
from urllib.parse import quote

import httpx
import jwt
from fastapi import HTTPException, Request
from jwt import PyJWKClient

logger = logging.getLogger(__name__)

# Supabase config (set via environment variables)
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_JWT_SECRET = os.environ.get("SUPABASE_JWT_SECRET", "")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

# JWKS client for asymmetric (ES256/RS256) JWT verification.
# Supabase issues new tokens with ES256 by default; legacy projects use HS256.
_JWKS_CLIENT: Optional[PyJWKClient] = (
    PyJWKClient(f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json", cache_keys=True, lifespan=3600)
    if SUPABASE_URL
    else None
)

# UUID pattern for user_id validation
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I
)

# In-memory subscription cache: { user_id: (is_pro, expires_at) }
_SUB_CACHE: dict[str, tuple[bool, float]] = {}
_SUB_CACHE_TTL = 60  # seconds


class AuthUser:
    """Authenticated user context."""

    def __init__(self, user_id: str, email: str, is_pro: bool = False):
        self.user_id = user_id
        self.email = email
        self.is_pro = is_pro


def _decode_jwt(token: str) -> Optional[dict]:
    """Decode and verify a Supabase JWT token.

    Supports both legacy HS256 (symmetric, JWT_SECRET) and current ES256/RS256
    (asymmetric, JWKS-fetched). Algorithm is selected from the token header.
    """
    try:
        header = jwt.get_unverified_header(token)
    except jwt.InvalidTokenError as e:
        logger.warning("Invalid JWT token header: %s", e)
        return None

    alg = header.get("alg", "HS256")

    try:
        if alg == "HS256":
            if not SUPABASE_JWT_SECRET:
                logger.debug("HS256 token but SUPABASE_JWT_SECRET not set")
                return None
            return jwt.decode(
                token,
                SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                audience="authenticated",
            )

        if _JWKS_CLIENT is None:
            logger.warning("Asymmetric JWT (%s) but JWKS client not initialized", alg)
            return None
        signing_key = _JWKS_CLIENT.get_signing_key_from_jwt(token).key
        return jwt.decode(
            token,
            signing_key,
            algorithms=[alg],
            audience="authenticated",
        )
    except jwt.ExpiredSignatureError:
        logger.warning("JWT token expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning("Invalid JWT token: %s", e)
        return None
    except Exception as e:
        logger.warning("JWT verification error (%s): %s", alg, e)
        return None


def _validate_uuid(value: str) -> bool:
    """Check if a string is a valid UUID."""
    return bool(_UUID_RE.match(value))


async def _check_subscription(user_id: str) -> bool:
    """Check if a user has an active Pro subscription via Supabase REST API.

    Results are cached in-memory for _SUB_CACHE_TTL seconds to avoid
    hitting Supabase on every request.
    """
    # Check cache first
    cached = _SUB_CACHE.get(user_id)
    if cached is not None:
        is_pro, expires_at = cached
        if time.monotonic() < expires_at:
            return is_pro

    is_pro = await _fetch_subscription(user_id)

    # Cache the result
    _SUB_CACHE[user_id] = (is_pro, time.monotonic() + _SUB_CACHE_TTL)
    return is_pro


async def _fetch_subscription(user_id: str) -> bool:
    """Fetch subscription status from Supabase."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        return False
    if not _validate_uuid(user_id):
        logger.warning("Invalid user_id format: %s", user_id)
        return False
    try:
        url = (
            f"{SUPABASE_URL}/rest/v1/subscriptions"
            f"?user_id=eq.{quote(user_id, safe='')}"
            f"&plan=eq.pro"
            f"&status=in.(active,trialing)"
            f"&or=(current_period_end.is.null,current_period_end.gt.now())"
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

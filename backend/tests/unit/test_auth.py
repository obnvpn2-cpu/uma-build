"""Tests for backend/middleware/auth.py.

Tests JWT decoding and token extraction logic.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import jwt as pyjwt

from middleware.auth import AuthUser, _decode_jwt


def test_decode_jwt_no_secret(monkeypatch):
    """When SUPABASE_JWT_SECRET is empty, returns None."""
    monkeypatch.setattr("middleware.auth.SUPABASE_JWT_SECRET", "")
    result = _decode_jwt("some.token.here")
    assert result is None


def test_decode_jwt_valid(monkeypatch):
    """Valid JWT decodes successfully."""
    secret = "test-secret-key-for-jwt-decoding"
    monkeypatch.setattr("middleware.auth.SUPABASE_JWT_SECRET", secret)
    payload = {"sub": "user-123", "email": "test@example.com", "aud": "authenticated"}
    token = pyjwt.encode(payload, secret, algorithm="HS256")
    result = _decode_jwt(token)
    assert result is not None
    assert result["sub"] == "user-123"
    assert result["email"] == "test@example.com"


def test_decode_jwt_invalid_token(monkeypatch):
    """Invalid JWT returns None."""
    monkeypatch.setattr("middleware.auth.SUPABASE_JWT_SECRET", "secret")
    result = _decode_jwt("not.a.valid.token")
    assert result is None


def test_decode_jwt_wrong_secret(monkeypatch):
    """JWT signed with wrong secret returns None."""
    monkeypatch.setattr("middleware.auth.SUPABASE_JWT_SECRET", "correct-secret")
    payload = {"sub": "user-123", "aud": "authenticated"}
    token = pyjwt.encode(payload, "wrong-secret", algorithm="HS256")
    result = _decode_jwt(token)
    assert result is None


def test_auth_user_properties():
    """AuthUser stores user_id, email, is_pro."""
    user = AuthUser(user_id="abc", email="test@test.com", is_pro=True)
    assert user.user_id == "abc"
    assert user.email == "test@test.com"
    assert user.is_pro is True

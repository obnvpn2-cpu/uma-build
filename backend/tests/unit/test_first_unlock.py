"""Tests for backend/services/first_unlock.py.

Verifies check/mark/duplicate logic and Supabase-unconfigured fallback.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import asyncio

import services.first_unlock as fu_mod
from services.first_unlock import (
    check_first_unlock_available,
    check_first_unlock_for_model,
    mark_first_unlock_used,
)


def test_check_available_returns_false_when_not_configured(monkeypatch):
    """Without Supabase config, check_first_unlock_available returns False."""
    monkeypatch.setattr(fu_mod, "SUPABASE_URL", "")
    monkeypatch.setattr(fu_mod, "SUPABASE_SERVICE_ROLE_KEY", "")
    assert check_first_unlock_available("user-123") is False


def test_check_available_returns_false_for_empty_user(monkeypatch):
    """Empty user_id should return False."""
    monkeypatch.setattr(fu_mod, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(fu_mod, "SUPABASE_SERVICE_ROLE_KEY", "key123")
    assert check_first_unlock_available("") is False


def test_mark_noop_when_not_configured(monkeypatch):
    """mark_first_unlock_used should silently no-op without Supabase."""
    monkeypatch.setattr(fu_mod, "SUPABASE_URL", "")
    monkeypatch.setattr(fu_mod, "SUPABASE_SERVICE_ROLE_KEY", "")
    # Should not raise
    mark_first_unlock_used("user-123", "model-456")


def test_mark_noop_for_empty_user(monkeypatch):
    """mark_first_unlock_used should no-op for empty user_id."""
    monkeypatch.setattr(fu_mod, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(fu_mod, "SUPABASE_SERVICE_ROLE_KEY", "key123")
    mark_first_unlock_used("", "model-456")


def test_check_for_model_returns_false_when_not_configured(monkeypatch):
    """check_first_unlock_for_model returns False without Supabase config."""
    monkeypatch.setattr(fu_mod, "SUPABASE_URL", "")
    monkeypatch.setattr(fu_mod, "SUPABASE_SERVICE_ROLE_KEY", "")
    result = asyncio.get_event_loop().run_until_complete(
        check_first_unlock_for_model("user-123", "model-456")
    )
    assert result is False


def test_check_for_model_returns_false_for_empty_params(monkeypatch):
    """check_first_unlock_for_model returns False for empty user/model."""
    monkeypatch.setattr(fu_mod, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(fu_mod, "SUPABASE_SERVICE_ROLE_KEY", "key123")
    loop = asyncio.get_event_loop()
    assert loop.run_until_complete(check_first_unlock_for_model("", "model-456")) is False
    assert loop.run_until_complete(check_first_unlock_for_model("user-123", "")) is False

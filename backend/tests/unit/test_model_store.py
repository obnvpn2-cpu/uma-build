"""Tests for backend/services/model_store.py.

Verifies graceful fallback when Supabase is not configured,
and parameter validation (empty user_id, empty model_id).
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import services.model_store as ms_mod
from services.model_store import (
    count_models,
    delete_model,
    list_models,
    rename_model,
    save_model,
)


def _run(coro):
    """Helper to run async functions in tests."""
    return asyncio.get_event_loop().run_until_complete(coro)


def test_count_returns_zero_when_not_configured(monkeypatch):
    """Without Supabase config, count_models returns 0."""
    monkeypatch.setattr(ms_mod, "SUPABASE_URL", "")
    monkeypatch.setattr(ms_mod, "SUPABASE_SERVICE_ROLE_KEY", "")
    assert _run(count_models("user-123")) == 0


def test_count_returns_zero_for_empty_user(monkeypatch):
    """Empty user_id should return 0."""
    monkeypatch.setattr(ms_mod, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(ms_mod, "SUPABASE_SERVICE_ROLE_KEY", "key123")
    assert _run(count_models("")) == 0


def test_save_returns_none_when_not_configured(monkeypatch):
    """Without Supabase config, save_model returns None."""
    monkeypatch.setattr(ms_mod, "SUPABASE_URL", "")
    monkeypatch.setattr(ms_mod, "SUPABASE_SERVICE_ROLE_KEY", "")
    result = _run(save_model("user-123", "model-456", "テストモデル"))
    assert result is None


def test_save_returns_none_for_empty_user(monkeypatch):
    """Empty user_id should return None."""
    monkeypatch.setattr(ms_mod, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(ms_mod, "SUPABASE_SERVICE_ROLE_KEY", "key123")
    result = _run(save_model("", "model-456", "テストモデル"))
    assert result is None


def test_save_returns_none_for_empty_model_id(monkeypatch):
    """Empty model_id should return None."""
    monkeypatch.setattr(ms_mod, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(ms_mod, "SUPABASE_SERVICE_ROLE_KEY", "key123")
    result = _run(save_model("user-123", "", "テストモデル"))
    assert result is None


def test_list_returns_empty_when_not_configured(monkeypatch):
    """Without Supabase config, list_models returns empty list."""
    monkeypatch.setattr(ms_mod, "SUPABASE_URL", "")
    monkeypatch.setattr(ms_mod, "SUPABASE_SERVICE_ROLE_KEY", "")
    result = _run(list_models("user-123"))
    assert result == []


def test_list_returns_empty_for_empty_user(monkeypatch):
    """Empty user_id should return empty list."""
    monkeypatch.setattr(ms_mod, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(ms_mod, "SUPABASE_SERVICE_ROLE_KEY", "key123")
    result = _run(list_models(""))
    assert result == []


def test_delete_returns_false_when_not_configured(monkeypatch):
    """Without Supabase config, delete_model returns False."""
    monkeypatch.setattr(ms_mod, "SUPABASE_URL", "")
    monkeypatch.setattr(ms_mod, "SUPABASE_SERVICE_ROLE_KEY", "")
    assert _run(delete_model("user-123", "model-456")) is False


def test_delete_returns_false_for_empty_params(monkeypatch):
    """Empty user_id or model_id should return False."""
    monkeypatch.setattr(ms_mod, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(ms_mod, "SUPABASE_SERVICE_ROLE_KEY", "key123")
    assert _run(delete_model("", "model-456")) is False
    assert _run(delete_model("user-123", "")) is False


def test_rename_returns_false_when_not_configured(monkeypatch):
    """Without Supabase config, rename_model returns False."""
    monkeypatch.setattr(ms_mod, "SUPABASE_URL", "")
    monkeypatch.setattr(ms_mod, "SUPABASE_SERVICE_ROLE_KEY", "")
    assert _run(rename_model("user-123", "model-456", "新しい名前")) is False


def test_rename_returns_false_for_empty_params(monkeypatch):
    """Empty user_id, model_id, or name should return False."""
    monkeypatch.setattr(ms_mod, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(ms_mod, "SUPABASE_SERVICE_ROLE_KEY", "key123")
    assert _run(rename_model("", "model-456", "新しい名前")) is False
    assert _run(rename_model("user-123", "", "新しい名前")) is False
    assert _run(rename_model("user-123", "model-456", "")) is False

"""Shared test configuration and fixtures."""

import os
import sys

import pytest

# Ensure backend is on the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')")


@pytest.fixture(autouse=True)
def _force_in_memory_supabase_services(monkeypatch):
    """Default all tests to the in-memory job_store / rate_limit path.

    Tests that exercise the Supabase code paths set SUPABASE_URL and
    SUPABASE_SERVICE_ROLE_KEY explicitly via monkeypatch.setenv.
    """
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    from services import job_store, rate_limit
    job_store._reset_local_for_tests()
    rate_limit._reset_local_for_tests()

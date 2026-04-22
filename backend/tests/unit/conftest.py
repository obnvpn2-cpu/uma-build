"""Shared fixtures for unit tests.

Default FUTURE_PREDICTION_MODE to demo so legacy tests that rely on
synthetic data keep passing. Tests that exercise the real-data path
override with monkeypatch.setenv("FUTURE_PREDICTION_MODE", "real").
"""

import pytest


@pytest.fixture(autouse=True)
def _default_future_prediction_mode(monkeypatch):
    monkeypatch.setenv("FUTURE_PREDICTION_MODE", "demo")

"""Shared test configuration and fixtures."""

import os
import sys

# Ensure backend is on the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')")

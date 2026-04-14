"""Tests for backend/ml/feature_selector.py.

Covers column selection, invalid ID handling, and available column filtering.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pandas as pd
import pytest

from ml.feature_selector import filter_available_columns, select_columns


def test_select_columns_valid():
    """Valid feature IDs -> list of column names."""
    cols = select_columns(["distance", "age", "horse_win_rate"])
    assert isinstance(cols, list)
    assert "distance" in cols
    assert "age" in cols
    assert "horse_win_rate" in cols
    assert len(cols) == 3


def test_select_columns_invalid_raises():
    """Only invalid IDs -> ValueError."""
    with pytest.raises(ValueError, match="No valid features"):
        select_columns(["totally_fake_feature", "another_fake"])


def test_filter_available_columns():
    """Columns not in DataFrame are skipped."""
    df = pd.DataFrame({
        "distance": [1200, 1600, 2000],
        "age": [3, 4, 5],
    })
    result = filter_available_columns(["distance", "age", "nonexistent_col"], df)
    assert "distance" in result
    assert "age" in result
    assert "nonexistent_col" not in result
    assert len(result) == 2

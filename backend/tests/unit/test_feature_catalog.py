"""Tests for feature catalog — verify all features have column mappings."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from services.feature_catalog import (
    FEATURE_CATALOG,
    get_all_feature_ids,
    get_default_feature_ids,
    get_feature_columns,
)


def test_all_features_have_column_mapping():
    """Every feature ID in the catalog must have a column mapping."""
    all_ids = get_all_feature_ids()
    for fid in all_ids:
        cols = get_feature_columns([fid])
        assert len(cols) > 0, f"Feature '{fid}' has no column mapping"


def test_win_odds_and_popularity_in_catalog():
    """win_odds and popularity should be exposed in the catalog."""
    all_ids = get_all_feature_ids()
    assert "win_odds" in all_ids
    assert "popularity" in all_ids


def test_odds_popularity_category_exists():
    """The odds_popularity category should exist."""
    cat_ids = [c["id"] for c in FEATURE_CATALOG]
    assert "odds_popularity" in cat_ids


def test_win_odds_not_default():
    """Market features should not be on by default (user opt-in)."""
    defaults = get_default_feature_ids()
    assert "win_odds" not in defaults
    assert "popularity" not in defaults


def test_no_duplicate_feature_ids():
    """All feature IDs must be unique across all categories."""
    all_ids = get_all_feature_ids()
    assert len(all_ids) == len(set(all_ids)), "Duplicate feature IDs found"

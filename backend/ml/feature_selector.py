"""Feature selector for UmaBuild.

Maps user-selected feature IDs from the catalog to actual column names
in the feature_table, and handles filtering/validation.
"""

import logging
from typing import List, Optional

import pandas as pd

from services.feature_catalog import get_all_feature_ids, get_feature_columns

logger = logging.getLogger(__name__)


def select_columns(selected_ids: List[str]) -> List[str]:
    """Map UI feature IDs to actual feature_table column names.

    Args:
        selected_ids: Feature IDs selected by the user in the UI.

    Returns:
        List of column names to use for training.

    Raises:
        ValueError: If no valid features are selected.
    """
    all_valid = set(get_all_feature_ids())

    # Validate IDs
    invalid = [fid for fid in selected_ids if fid not in all_valid]
    if invalid:
        logger.warning("Ignoring unknown feature IDs: %s", invalid)

    valid_ids = [fid for fid in selected_ids if fid in all_valid]
    if not valid_ids:
        raise ValueError("No valid features selected. Please select at least one feature.")

    columns = get_feature_columns(valid_ids)
    logger.info("Selected %d features -> %d columns: %s", len(valid_ids), len(columns), columns)
    return columns


def filter_available_columns(
    columns: List[str],
    df: pd.DataFrame,
    min_non_null_frac: float = 0.01,
) -> List[str]:
    """Filter columns to those actually present and non-empty in the DataFrame.

    Args:
        columns: Desired column names.
        df: The feature DataFrame.
        min_non_null_frac: Minimum fraction of non-null values required.

    Returns:
        Filtered list of columns that exist and have sufficient data.
    """
    available = []
    for col in columns:
        if col not in df.columns:
            logger.warning("Column '%s' not found in feature table -- skipping", col)
            continue
        non_null_frac = df[col].notna().mean()
        if non_null_frac < min_non_null_frac:
            logger.warning(
                "Column '%s' has only %.1f%% non-null values -- skipping",
                col, non_null_frac * 100,
            )
            continue
        available.append(col)

    if not available:
        logger.error("No available columns after filtering!")
    else:
        logger.info("Available columns after filtering: %d / %d", len(available), len(columns))

    return available


def prepare_features(
    df: pd.DataFrame,
    selected_ids: List[str],
    target_col: str = "target_win",
) -> Optional[pd.DataFrame]:
    """Prepare a feature DataFrame for ML training.

    Args:
        df: Full feature table.
        selected_ids: Feature IDs selected by the user.
        target_col: Name of the target column.

    Returns:
        DataFrame with selected feature columns + target, rows with NaN target dropped.
    """
    columns = select_columns(selected_ids)
    columns = filter_available_columns(columns, df)

    if not columns:
        logger.error("No usable columns available for training.")
        return None

    # Include target column
    if target_col not in df.columns:
        logger.error("Target column '%s' not found in feature table.", target_col)
        return None

    keep_cols = columns + [target_col]
    # Also keep race_date for time-series split, and identifiers for backtest
    for extra in ["race_date", "race_key", "horse_key", "win_odds", "finish_order"]:
        if extra in df.columns and extra not in keep_cols:
            keep_cols.append(extra)

    result = df[keep_cols].copy()
    result = result.dropna(subset=[target_col])

    logger.info(
        "Prepared feature DataFrame: %d rows, %d feature columns + target",
        len(result), len(columns),
    )
    return result

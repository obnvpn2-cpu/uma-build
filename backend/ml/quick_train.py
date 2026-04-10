"""Quick training module for UmaBuild.

Provides a fast training pipeline (~30 sec) using 2 years of data
with time-series split validation.
"""

import logging
import os
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from ml.feature_selector import select_columns, filter_available_columns
from ml.pipeline import LGBMPipeline, TrainConfig
from services.feature_builder import build_feature_table, generate_demo_feature_table

logger = logging.getLogger(__name__)

# Flag to use synthetic data when no real DB is available
DEMO_MODE = True

# Default DB path
DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "jravan.db"
)


def _load_feature_table(
    db_path: str,
    data_years: int = 2,
) -> pd.DataFrame:
    """Load or build the feature table, filtered to the last N years.

    Args:
        db_path: Path to the JRA-VAN EveryDB2 SQLite file.
        data_years: Number of years of data to use.

    Returns:
        Feature table DataFrame.
    """
    # Check if a cached feature table exists
    cache_path = os.path.join(
        os.path.dirname(db_path) if os.path.exists(os.path.dirname(db_path)) else "data",
        "feature_table_cache.csv",
    )

    if os.path.exists(cache_path):
        logger.info("Loading cached feature table from: %s", cache_path)
        df = pd.read_csv(cache_path, low_memory=False)
    elif os.path.exists(db_path):
        logger.info("Building feature table from DB: %s", db_path)
        df = build_feature_table(db_path, output_path=cache_path)
    elif DEMO_MODE:
        logger.warning("DB not found at %s. Using DEMO MODE with synthetic data.", db_path)
        # Scale demo data based on data_years
        n_races = data_years * 250  # ~250 races per year (simplified)
        df = generate_demo_feature_table(n_races=n_races)
    else:
        raise FileNotFoundError(
            f"Database not found: {db_path}. Set DEMO_MODE=True for synthetic data."
        )

    # Filter to last N years
    if "race_date" in df.columns:
        df["race_date"] = pd.to_datetime(df["race_date"], errors="coerce")
        cutoff = df["race_date"].max() - pd.Timedelta(days=data_years * 365)
        before = len(df)
        df = df[df["race_date"] >= cutoff].copy()
        logger.info(
            "Filtered to last %d years: %d -> %d rows (cutoff: %s)",
            data_years, before, len(df), cutoff,
        )
    else:
        logger.warning("No race_date column found; using all data.")

    return df


def _time_series_split(
    df: pd.DataFrame,
    train_frac: float = 0.8,
) -> tuple:
    """Split data chronologically (no shuffling for time-series data).

    Args:
        df: Feature table sorted by date.
        train_frac: Fraction of data for training.

    Returns:
        Tuple of (train_df, val_df).
    """
    if "race_date" in df.columns:
        df = df.sort_values("race_date").reset_index(drop=True)

    split_idx = int(len(df) * train_frac)
    train_df = df.iloc[:split_idx].copy()
    val_df = df.iloc[split_idx:].copy()

    logger.info(
        "Time-series split: %d train, %d val (%.0f%% / %.0f%%)",
        len(train_df), len(val_df),
        100 * len(train_df) / len(df), 100 * len(val_df) / len(df),
    )

    return train_df, val_df


def quick_train(
    selected_features: List[str],
    db_path: str = DEFAULT_DB_PATH,
    data_years: int = 2,
    target_col: str = "target_win",
    config: Optional[TrainConfig] = None,
) -> Dict[str, Any]:
    """Quick training pipeline.

    Steps:
    1. Load feature_table filtered to last N years
    2. Select columns based on user's feature selection
    3. Time-series split (80% train, 20% test by date)
    4. Train LightGBM
    5. Evaluate on validation set
    6. Return model_id + results

    Args:
        selected_features: Feature IDs selected by the user.
        db_path: Path to the JRA-VAN database.
        data_years: Number of years of data.
        target_col: Target column name.
        config: Optional LightGBM config.

    Returns:
        Dict with model_id, summary stats, predictions, and feature importance.
    """
    start_time = time.time()

    logger.info(
        "Starting quick_train: %d features, %d years, target=%s",
        len(selected_features), data_years, target_col,
    )

    # 1. Load data
    df = _load_feature_table(db_path, data_years=data_years)

    # 2. Select columns
    feature_cols = select_columns(selected_features)
    feature_cols = filter_available_columns(feature_cols, df)

    if not feature_cols:
        return {
            "error": "No valid feature columns available after filtering.",
            "model_id": None,
        }

    # Ensure target exists
    if target_col not in df.columns:
        return {
            "error": f"Target column '{target_col}' not found.",
            "model_id": None,
        }

    # Drop rows with missing target
    df = df.dropna(subset=[target_col])

    # 3. Time-series split
    train_df, val_df = _time_series_split(df, train_frac=0.8)

    X_train = train_df[feature_cols].copy()
    y_train = train_df[target_col].copy()
    X_val = val_df[feature_cols].copy()
    y_val = val_df[target_col].copy()

    # Fill NaN with median for numeric columns
    for col in feature_cols:
        if X_train[col].dtype in [np.float64, np.float32, np.int64, np.int32, float, int]:
            median_val = X_train[col].median()
            X_train[col] = X_train[col].fillna(median_val)
            X_val[col] = X_val[col].fillna(median_val)
        else:
            # Categorical: fill with mode or "unknown"
            mode_val = X_train[col].mode()
            fill_val = mode_val.iloc[0] if len(mode_val) > 0 else "unknown"
            X_train[col] = X_train[col].fillna(fill_val)
            X_val[col] = X_val[col].fillna(fill_val)

    # 4. Train
    if config is None:
        config = TrainConfig(target_col=target_col)
    pipeline = LGBMPipeline(config=config)
    pipeline.train(X_train, y_train, X_val, y_val)

    # 5. Evaluate
    val_preds = pipeline.predict(X_val)

    # Build predictions DataFrame for backtest
    predictions_df = val_df[["race_key", "horse_key", "finish_order"]].copy()
    if "race_date" in val_df.columns:
        predictions_df["race_date"] = val_df["race_date"]
    if "win_odds" in val_df.columns:
        predictions_df["win_odds"] = val_df["win_odds"]
    if "surface" in val_df.columns:
        predictions_df["surface"] = val_df["surface"]
    if "track_condition" in val_df.columns:
        predictions_df["track_condition"] = val_df["track_condition"]
    if "distance" in val_df.columns:
        predictions_df["distance"] = val_df["distance"]
    if "tansho_payout" in val_df.columns:
        predictions_df["tansho_payout"] = val_df["tansho_payout"]
    predictions_df["pred_prob"] = val_preds
    predictions_df["actual_win"] = y_val.values

    # Feature importance
    fi_df = pipeline.feature_importance()
    feature_importance = fi_df.head(20).to_dict(orient="records")

    # Save model
    model_path = pipeline.save()

    elapsed = time.time() - start_time
    logger.info("quick_train completed in %.1f seconds", elapsed)

    # 6. Return results
    return {
        "model_id": pipeline.model_id,
        "model_path": model_path,
        "predictions_df": predictions_df,
        "feature_importance": feature_importance,
        "train_metrics": pipeline.train_metrics,
        "meta": {
            "n_features": len(feature_cols),
            "feature_names": feature_cols,
            "n_train": len(X_train),
            "n_val": len(X_val),
            "data_years": data_years,
            "target_col": target_col,
            "elapsed_sec": round(elapsed, 1),
        },
    }

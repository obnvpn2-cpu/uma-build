"""Quick training module for UmaBuild.

Provides a fast training pipeline (~30 sec) using 2 years of data
with time-series split validation.
"""

import logging
import os
import time
from typing import Any, Dict, List, Optional

import pandas as pd

from ml.feature_selector import filter_available_columns, select_columns
from ml.pipeline import TrainConfig
from ml.walk_forward import walk_forward_cv
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
    # Check if a cached feature table exists (prefer parquet over CSV)
    data_dir = os.path.dirname(db_path) if os.path.exists(os.path.dirname(db_path)) else "data"
    cache_parquet = os.path.join(data_dir, "feature_table_cache.parquet")
    cache_csv = os.path.join(data_dir, "feature_table_cache.csv")

    if os.path.exists(cache_parquet):
        logger.info("Loading cached feature table (parquet): %s", cache_parquet)
        df = pd.read_parquet(cache_parquet, engine="pyarrow")
    elif os.path.exists(cache_csv):
        logger.info("Loading cached feature table (CSV): %s", cache_csv)
        df = pd.read_csv(cache_csv, low_memory=False)
    elif os.path.exists(db_path):
        logger.info("Building feature table from DB: %s", db_path)
        df = build_feature_table(db_path, output_path=cache_parquet)
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

    # Sort by date + race_key for time-series integrity
    sort_cols = [c for c in ["race_date", "race_key"] if c in df.columns]
    if sort_cols:
        df = df.sort_values(sort_cols).reset_index(drop=True)

    # 3. Train with walk-forward CV (3 folds)
    if config is None:
        config = TrainConfig(target_col=target_col)

    # Fallback to binary if lambdarank prerequisites missing
    if config.objective_type == "lambdarank":
        if "race_key" not in df.columns or "finish_order" not in df.columns:
            logger.warning(
                "race_key or finish_order missing — falling back to binary objective"
            )
            config.objective_type = "binary"

    cv_result = walk_forward_cv(
        df=df,
        feature_cols=feature_cols,
        target_col=target_col,
        config=config,
        n_folds=3,
    )

    if cv_result.get("error"):
        return {
            "error": cv_result["error"],
            "model_id": None,
        }

    elapsed = time.time() - start_time
    logger.info("quick_train completed in %.1f seconds", elapsed)

    predictions_df = cv_result["predictions_df"]
    n_val = len(predictions_df)
    n_total = len(df)

    # 4. Return results
    return {
        "model_id": cv_result["model_id"],
        "model_path": cv_result["model_path"],
        "predictions_df": predictions_df,
        "feature_importance": cv_result["feature_importance"],
        "train_metrics": cv_result["train_metrics"],
        "cv_metrics": cv_result.get("cv_metrics", {}),
        "meta": {
            "n_features": len(feature_cols),
            "feature_names": feature_cols,
            "n_train": n_total - n_val,
            "n_val": n_val,
            "data_years": data_years,
            "target_col": target_col,
            "cv_folds": 3,
            "elapsed_sec": round(elapsed, 1),
        },
    }

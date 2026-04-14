"""Walk-forward cross-validation for UmaBuild.

Splits time-series data into expanding windows and trains/validates
on each fold. Returns aggregated predictions across all validation
windows for more robust backtest evaluation.

Example with n_folds=3 and 12 months of race data:
  Fold 1: Train [month 1-6]   → Val [month 7-8]
  Fold 2: Train [month 1-8]   → Val [month 9-10]
  Fold 3: Train [month 1-10]  → Val [month 11-12]

The final model (from the last fold) is kept for feature importance.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from ml.pipeline import LGBMPipeline, TrainConfig, finish_to_relevance

logger = logging.getLogger(__name__)


def _compute_fold_boundaries(
    race_keys: np.ndarray,
    n_folds: int = 3,
    min_train_frac: float = 0.4,
) -> List[Tuple[int, int]]:
    """Compute expanding-window fold boundaries on race-level.

    Returns list of (train_end_idx, val_end_idx) where indices refer
    to positions in the sorted race_keys array.
    """
    n_races = len(race_keys)
    # Reserve space: min_train_frac for initial train, rest split into n_folds val windows
    val_total = int(n_races * (1 - min_train_frac))
    val_per_fold = max(1, val_total // n_folds)

    folds = []
    for i in range(n_folds):
        val_start = n_races - val_total + i * val_per_fold
        val_end = val_start + val_per_fold if i < n_folds - 1 else n_races
        folds.append((val_start, val_end))

    return folds


def walk_forward_cv(
    df: pd.DataFrame,
    feature_cols: List[str],
    target_col: str = "target_win",
    config: Optional[TrainConfig] = None,
    n_folds: int = 3,
) -> Dict[str, Any]:
    """Run walk-forward cross-validation.

    Args:
        df: Full feature table, sorted by race_date + race_key.
        feature_cols: Column names to use as features.
        target_col: Target column name.
        config: LightGBM training config.
        n_folds: Number of CV folds.

    Returns:
        Dict with aggregated predictions_df, final model's feature_importance,
        per-fold metrics, and the final trained pipeline.
    """
    if config is None:
        config = TrainConfig(target_col=target_col)

    is_rank = config.objective_type == "lambdarank"

    # Sort and get race keys in chronological order
    sort_cols = [c for c in ["race_date", "race_key"] if c in df.columns]
    if sort_cols:
        df = df.sort_values(sort_cols).reset_index(drop=True)

    has_race_key = "race_key" in df.columns
    if has_race_key:
        race_keys = df["race_key"].unique()
    else:
        # Fallback: treat each row as its own "race"
        df = df.copy()
        df["_row_id"] = np.arange(len(df))
        race_keys = df["_row_id"].unique()
    group_col = "race_key" if has_race_key else "_row_id"

    folds = _compute_fold_boundaries(race_keys, n_folds=n_folds)

    all_val_predictions = []
    fold_metrics = []
    final_pipeline = None

    for fold_i, (val_start_idx, val_end_idx) in enumerate(folds):
        train_race_set = set(race_keys[:val_start_idx])
        val_race_set = set(race_keys[val_start_idx:val_end_idx])

        train_mask = df[group_col].isin(train_race_set)
        val_mask = df[group_col].isin(val_race_set)

        train_df = df[train_mask]
        val_df = df[val_mask]

        if len(train_df) < 50 or len(val_df) < 10:
            logger.warning("Fold %d: insufficient data (train=%d, val=%d) — skipping",
                           fold_i, len(train_df), len(val_df))
            continue

        X_train = train_df[feature_cols].copy()
        X_val = val_df[feature_cols].copy()

        # Fill NaN
        for col in feature_cols:
            if X_train[col].dtype in [np.float64, np.float32, np.int64, np.int32, float, int]:
                median_val = X_train[col].median()
                X_train[col] = X_train[col].fillna(median_val)
                X_val[col] = X_val[col].fillna(median_val)
            else:
                mode_val = X_train[col].mode()
                fill_val = mode_val.iloc[0] if len(mode_val) > 0 else "unknown"
                X_train[col] = X_train[col].fillna(fill_val)
                X_val[col] = X_val[col].fillna(fill_val)

        # Prepare labels and groups
        if is_rank and has_race_key and "finish_order" in train_df.columns:
            y_train = finish_to_relevance(train_df["finish_order"])
            y_val = finish_to_relevance(val_df["finish_order"])
            group_train = train_df.groupby("race_key", sort=False).size().tolist()
            group_val = val_df.groupby("race_key", sort=False).size().tolist()
        else:
            y_train = train_df[target_col].copy()
            y_val = val_df[target_col].copy()
            group_train = None
            group_val = None

        # Train
        pipeline = LGBMPipeline(config=config)
        pipeline.train(X_train, y_train, X_val, y_val, group_train, group_val)

        # Predict
        val_preds = pipeline.predict(X_val)

        # Collect validation predictions
        base_cols = [c for c in ["race_key", "horse_key", "finish_order"]
                     if c in val_df.columns]
        pred_df = val_df[base_cols].copy()
        for extra in ["race_date", "win_odds", "surface", "track_condition",
                       "distance", "tansho_payout"]:
            if extra in val_df.columns:
                pred_df[extra] = val_df[extra].values
        pred_df["pred_prob"] = val_preds
        pred_df["actual_win"] = (val_df["finish_order"] == 1).astype(int).values
        pred_df["cv_fold"] = fold_i
        all_val_predictions.append(pred_df)

        fold_metrics.append({
            "fold": fold_i,
            "n_train": len(X_train),
            "n_val": len(X_val),
            **pipeline.train_metrics,
        })

        logger.info(
            "Fold %d: train=%d, val=%d, metrics=%s",
            fold_i, len(X_train), len(X_val), pipeline.train_metrics,
        )

        # Keep last fold's pipeline as the final model
        final_pipeline = pipeline

    if not all_val_predictions:
        return {"error": "All CV folds skipped — insufficient data.", "model_id": None}

    # Aggregate predictions
    predictions_df = pd.concat(all_val_predictions, ignore_index=True)

    # Feature importance from the final model
    fi_df = final_pipeline.feature_importance()
    feature_importance = fi_df.head(20).to_dict(orient="records")

    # Save final model
    model_path = final_pipeline.save()

    # Aggregate CV metrics
    cv_summary = _aggregate_cv_metrics(fold_metrics, is_rank)

    return {
        "model_id": final_pipeline.model_id,
        "model_path": model_path,
        "predictions_df": predictions_df,
        "feature_importance": feature_importance,
        "train_metrics": final_pipeline.train_metrics,
        "cv_metrics": cv_summary,
        "fold_metrics": fold_metrics,
    }


def _aggregate_cv_metrics(
    fold_metrics: List[Dict[str, Any]],
    is_rank: bool,
) -> Dict[str, Any]:
    """Aggregate per-fold metrics into a CV summary."""
    if not fold_metrics:
        return {}

    if is_rank:
        ndcg1_vals = [m.get("best_val_ndcg1", np.nan) for m in fold_metrics]
        ndcg3_vals = [m.get("best_val_ndcg3", np.nan) for m in fold_metrics]
        return {
            "n_folds": len(fold_metrics),
            "ndcg1_mean": float(np.nanmean(ndcg1_vals)),
            "ndcg1_std": float(np.nanstd(ndcg1_vals)),
            "ndcg3_mean": float(np.nanmean(ndcg3_vals)),
            "ndcg3_std": float(np.nanstd(ndcg3_vals)),
        }
    else:
        logloss_vals = [m.get("best_val_logloss", np.nan) for m in fold_metrics]
        return {
            "n_folds": len(fold_metrics),
            "logloss_mean": float(np.nanmean(logloss_vals)),
            "logloss_std": float(np.nanstd(logloss_vals)),
        }

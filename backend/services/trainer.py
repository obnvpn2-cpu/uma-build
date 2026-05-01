"""Training orchestration service for UmaBuild.

Coordinates the full training pipeline from feature selection through
backtest and paywall masking.
"""

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

from ml.quick_train import DEFAULT_DB_PATH, quick_train
from services.backtest import run_backtest
from services.first_unlock import check_first_unlock_available, mark_first_unlock_used
from services.future_prediction import generate_future_predictions
from services.paywall import mask_results

logger = logging.getLogger(__name__)

# In-memory cache for results (keyed by model_id)
# In production, this would be Redis or similar.
_results_cache: Dict[str, Dict[str, Any]] = {}

# Directory for persisting results
RESULTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "results")
os.makedirs(RESULTS_DIR, exist_ok=True)


def _cache_results(model_id: str, results: Dict[str, Any]) -> None:
    """Cache results in memory and on disk."""
    _results_cache[model_id] = results

    # Also persist to disk
    try:
        # Remove non-serializable items (like DataFrames)
        serializable = {k: v for k, v in results.items() if k != "predictions_df"}
        path = os.path.join(RESULTS_DIR, f"{model_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(serializable, f, ensure_ascii=False, indent=2, default=str)
        logger.info("Results cached to: %s", path)
    except Exception as e:
        logger.warning("Failed to persist results to disk: %s", e)


def get_cached_results(model_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve cached results by model_id.

    Args:
        model_id: The model identifier.

    Returns:
        Cached results dict, or None if not found.
    """
    # Check memory cache first
    if model_id in _results_cache:
        return _results_cache[model_id]

    # Check disk
    path = os.path.join(RESULTS_DIR, f"{model_id}.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                results = json.load(f)
            _results_cache[model_id] = results
            return results
        except Exception as e:
            logger.warning("Failed to load results from disk: %s", e)

    return None


def run_training(
    selected_feature_ids: List[str],
    db_path: str = DEFAULT_DB_PATH,
    is_pro: bool = False,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Orchestrate the full training pipeline.

    Steps:
    1. Run quick_train with selected features
    2. Run backtest on validation predictions
    3. Generate future race predictions
    4. Apply paywall masking based on subscription status
    5. Cache and return results

    Args:
        selected_feature_ids: Feature IDs selected by the user.
        db_path: Path to the JRA-VAN database.
        is_pro: Whether the user has a Pro subscription.
        user_id: Authenticated user ID (for first-unlock tracking).

    Returns:
        Dict with training results (masked based on plan).
    """
    start_time = time.time()

    data_years = 5 if is_pro else 2
    logger.info(
        "Starting training: %d features, %d years (is_pro=%s)",
        len(selected_feature_ids), data_years, is_pro,
    )

    # 2. Run quick training
    train_result = quick_train(
        selected_features=selected_feature_ids,
        db_path=db_path,
        data_years=data_years,
    )

    if train_result.get("error"):
        return {
            "error": train_result["error"],
            "model_id": None,
        }

    model_id = train_result["model_id"]

    # 3. Run backtest
    predictions_df = train_result.get("predictions_df")
    if predictions_df is not None and not predictions_df.empty:
        backtest_result = run_backtest(predictions_df, bet_amount=100)
    else:
        backtest_result = {
            "summary": {
                "roi": 0.0,
                "hit_rate": 0.0,
                "n_races": 0,
                "n_bets": 0,
                "reliability_stars": 1,
            },
            "condition_breakdown": [],
            "yearly_breakdown": [],
            "distance_breakdown": [],
            "calibration": [],
        }

    # Generate future race predictions
    try:
        fp_result = generate_future_predictions(
            model_path=train_result["model_path"],
            selected_features=selected_feature_ids,
            db_path=db_path,
        )
        future_preds = fp_result.get("predictions", [])
        future_pred_meta = fp_result.get("meta", {"status": "unavailable"})
    except Exception as e:
        logger.warning("Future prediction failed: %s", e)
        future_preds = []
        future_pred_meta = {"status": "unavailable", "error": str(e)}

    # Combine results
    elapsed = time.time() - start_time
    full_results = {
        "model_id": model_id,
        "summary": backtest_result["summary"],
        "feature_importance": train_result.get("feature_importance", []),
        "condition_breakdown": backtest_result.get("condition_breakdown", []),
        "yearly_breakdown": backtest_result.get("yearly_breakdown", []),
        "distance_breakdown": backtest_result.get("distance_breakdown", []),
        "calibration": backtest_result.get("calibration", []),
        "future_prediction": future_preds,
        "future_prediction_meta": future_pred_meta,
        "train_metrics": train_result.get("train_metrics", {}),
        "cv_metrics": train_result.get("cv_metrics", {}),
        "meta": {
            **train_result.get("meta", {}),
            "total_elapsed_sec": round(elapsed, 1),
        },
    }

    # Cache full results (before masking)
    _cache_results(model_id, full_results)

    # Check first-unlock eligibility for non-pro authenticated users
    is_first_unlock = False
    if not is_pro and user_id:
        is_first_unlock = check_first_unlock_available(user_id)
        if is_first_unlock:
            mark_first_unlock_used(user_id, model_id)

    # Apply paywall masking based on subscription status
    masked_results = mask_results(full_results, is_pro=is_pro, is_first_unlock=is_first_unlock)

    logger.info(
        "Training pipeline complete: model_id=%s, elapsed=%.1fs, roi=%.2f%%, first_unlock=%s",
        model_id, elapsed, backtest_result["summary"].get("roi", 0), is_first_unlock,
    )

    return masked_results

"""Future race prediction service for UmaBuild.

Uses a trained model to predict outcomes for upcoming (or demo) races.
"""

import logging
from datetime import timedelta
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from ml.pipeline import LGBMPipeline
from services.feature_builder import generate_demo_feature_table

logger = logging.getLogger(__name__)

# Always use demo mode for now (no live JRA-VAN feed)
DEMO_MODE = True


def generate_future_predictions(
    model_path: str,
    selected_features: List[str],
    db_path: str = "",
) -> List[Dict[str, Any]]:
    """Generate predictions for upcoming races using a trained model.

    In DEMO_MODE, synthesises a plausible entry list from the training
    data's horse pool so predictions remain meaningful.

    Args:
        model_path: Path to the saved .pkl model file.
        selected_features: Feature IDs used during training.
        db_path: Path to the JRA-VAN DB (unused in DEMO_MODE).

    Returns:
        List of race dicts, each containing ranked entries with scores.
    """
    try:
        pipeline = LGBMPipeline.load(model_path)
    except Exception as e:
        logger.warning("Failed to load model for future prediction: %s", e)
        return []

    # Build the feature table (reuse demo generator for consistency)
    training_df = generate_demo_feature_table(n_races=500)

    future_df = _generate_demo_future_races(training_df, n_races=3)

    if future_df.empty:
        logger.warning("No future race entries generated")
        return []

    # Build feature matrix from the columns the model expects
    feature_cols = pipeline.feature_names
    available = [c for c in feature_cols if c in future_df.columns]

    if not available:
        logger.warning("No matching features for future prediction")
        return []

    X = future_df[available].copy()

    # predict() handles missing columns internally (fills NaN)
    try:
        scores = pipeline.predict(X)
    except Exception as e:
        logger.warning("Future prediction predict() failed: %s", e)
        return []

    future_df = future_df.copy()
    future_df["predicted_score"] = scores

    return _format_predictions(future_df)


def _generate_demo_future_races(
    training_df: pd.DataFrame,
    n_races: int = 3,
) -> pd.DataFrame:
    """Create synthetic future race entries from the training horse pool.

    Uses horses that appeared in training so as-of features already exist,
    making the predictions realistic.

    Args:
        training_df: The training feature table DataFrame.
        n_races: Number of future races to generate.

    Returns:
        DataFrame with future race entries (finish_order = NaN).
    """
    rng = np.random.RandomState(99)

    if training_df.empty:
        return pd.DataFrame()

    # Determine the latest training date and set future date
    if "race_date" in training_df.columns:
        max_date = pd.to_datetime(training_df["race_date"]).max()
        future_base = max_date + timedelta(days=7)
    else:
        future_base = pd.Timestamp("2024-07-01")

    # Get unique horses with their latest feature values
    horse_col = "horse_key" if "horse_key" in training_df.columns else None
    if horse_col is None:
        logger.warning("No horse_key column in training data")
        return pd.DataFrame()

    # Get horses with enough history (at least 3 races)
    horse_counts = training_df[horse_col].value_counts()
    experienced_horses = horse_counts[horse_counts >= 3].index.tolist()

    if len(experienced_horses) < 8:
        experienced_horses = horse_counts.index.tolist()

    race_names = ["東京11R", "中山10R", "阪神12R", "京都11R", "中京9R"]
    surfaces = ["芝", "ダート"]
    distances = [1200, 1400, 1600, 1800, 2000, 2400]

    rows = []
    for race_idx in range(n_races):
        field_size = rng.randint(10, 17)
        chosen_horses = rng.choice(
            experienced_horses, size=min(field_size, len(experienced_horses)), replace=False
        )

        race_key = f"FUTURE_{race_idx:04d}"
        race_date = (future_base + timedelta(days=race_idx)).strftime("%Y-%m-%d")
        race_name = race_names[race_idx % len(race_names)]
        distance = int(rng.choice(distances))
        surface_val = int(rng.choice([1, 2]))

        for gate_num, horse_key in enumerate(chosen_horses, 1):
            # Get the latest record for this horse
            horse_history = training_df[training_df[horse_col] == horse_key]
            if horse_history.empty:
                continue

            latest = horse_history.iloc[-1]

            row = latest.to_dict()
            # Override race-level fields for the future race
            row["race_key"] = race_key
            row["race_date"] = race_date
            row["distance"] = distance
            row["surface"] = surface_val
            row["finish_order"] = np.nan  # Unknown — this is the future
            row["umaban"] = gate_num
            row["waku"] = min(8, (gate_num - 1) // 2 + 1)

            # Store metadata for formatting
            row["_race_name"] = race_name
            row["_surface_label"] = surfaces[surface_val - 1]
            row["_horse_name"] = horse_key
            row["_gate_number"] = gate_num
            row["_jockey"] = str(latest.get("jockey_code", ""))

            rows.append(row)

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows)


def _format_predictions(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Format raw predictions into the API response structure.

    Groups entries by race, ranks by predicted score, and assigns
    confidence levels.
    """
    results = []
    for race_key, group in df.groupby("race_key"):
        group_sorted = group.sort_values("predicted_score", ascending=False).reset_index(drop=True)

        first = group_sorted.iloc[0]
        race_date = str(first.get("race_date", ""))
        race_name = str(first.get("_race_name", race_key))
        distance = int(first.get("distance", 0))
        surface = str(first.get("_surface_label", ""))

        entries = []
        scores = group_sorted["predicted_score"].values
        score_range = scores.max() - scores.min() if len(scores) > 1 else 1.0

        for rank, (_, row) in enumerate(group_sorted.iterrows(), 1):
            score = float(row["predicted_score"])

            # Confidence based on relative position in score distribution
            if score_range > 0:
                relative = (score - scores.min()) / score_range
            else:
                relative = 0.5

            if relative >= 0.7:
                confidence = "high"
            elif relative >= 0.4:
                confidence = "medium"
            else:
                confidence = "low"

            entries.append({
                "rank": rank,
                "horse_name": str(row.get("_horse_name", f"Horse-{rank}")),
                "predicted_score": round(score, 4),
                "confidence": confidence,
                "jockey": str(row.get("_jockey", "")),
                "gate_number": int(row.get("_gate_number", rank)),
            })

        results.append({
            "race_key": str(race_key),
            "race_date": race_date,
            "race_name": race_name,
            "distance": distance,
            "surface": surface,
            "entries": entries,
        })

    # Sort by race_key for consistent ordering
    results.sort(key=lambda r: r["race_key"])
    return results

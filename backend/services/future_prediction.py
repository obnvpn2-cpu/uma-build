"""Future race prediction service for UmaBuild.

Uses a trained model to predict outcomes for this week's upcoming JRA
races. Falls back to a synthetic demo when requested explicitly via
FUTURE_PREDICTION_MODE=demo. Real-data path pulls from the local
EveryDB2 SQLite (N_RACE / N_UMA_RACE) populated by "今週データ種別 B".
"""

import logging
import os
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from ml.pipeline import LGBMPipeline
from services.feature_builder import generate_demo_feature_table

logger = logging.getLogger(__name__)

_MODE_ENV = "FUTURE_PREDICTION_MODE"
_DEBUG_ENV = "FUTURE_PREDICTION_DEBUG"

# EveryDB2 TrackCD → (日本語ラベル, 内部 surface int)
# 10-22: 芝, 23-29: ダート, 51-59: 障害 (EveryDB5 spec)
_TRACK_CD_TO_SURFACE: Dict[str, Any] = {}
for _code in range(10, 23):
    _TRACK_CD_TO_SURFACE[f"{_code:02d}"] = ("芝", 1)
for _code in range(23, 30):
    _TRACK_CD_TO_SURFACE[f"{_code:02d}"] = ("ダート", 2)
for _code in range(51, 60):
    _TRACK_CD_TO_SURFACE[f"{_code:02d}"] = ("障害", 3)


def _track_cd_to_label(track_cd: Any) -> str:
    s = str(track_cd).strip() if track_cd is not None else ""
    return _TRACK_CD_TO_SURFACE.get(s, ("その他", 0))[0]


def _track_cd_to_surface_int(track_cd: Any) -> int:
    s = str(track_cd).strip() if track_cd is not None else ""
    return int(_TRACK_CD_TO_SURFACE.get(s, ("その他", 0))[1])


def generate_future_predictions(
    model_path: str,
    selected_features: List[str],
    db_path: str = "",
) -> Dict[str, Any]:
    """Generate predictions for upcoming JRA races using a trained model.

    Args:
        model_path: Path to the saved .pkl model file.
        selected_features: Feature IDs selected by the user (kept for
            API compatibility; the authoritative feature list comes from
            the saved pipeline's feature_names).
        db_path: Path to the JRA-VAN EveryDB2 SQLite.

    Returns:
        Dict with:
          - predictions: List[Dict] race entries (possibly empty)
          - meta: {status: "ok"|"no_upcoming"|"demo"|"unavailable",
                   upcoming_count: int, latest_race_date?: str, ...}
    """
    del selected_features  # kept for signature stability, not used
    mode = os.getenv(_MODE_ENV, "real").lower()
    if mode not in ("real", "demo", "auto"):
        logger.warning("Unknown %s=%s; defaulting to real", _MODE_ENV, mode)
        mode = "real"

    try:
        pipeline = LGBMPipeline.load(model_path)
    except Exception as e:
        logger.warning("Failed to load model for future prediction: %s", e)
        return {
            "predictions": [],
            "meta": {"status": "unavailable", "upcoming_count": 0, "error": str(e)},
        }

    if mode == "demo":
        return _run_demo_mode(pipeline)

    real_result = _run_real_mode(pipeline, db_path)
    if real_result["meta"].get("status") == "ok":
        return real_result

    if mode == "auto":
        logger.info("auto mode: no upcoming races found, falling back to demo")
        fallback = _run_demo_mode(pipeline)
        fallback["meta"]["fell_back_from"] = real_result["meta"].get("status")
        return fallback

    return real_result


def _run_demo_mode(pipeline: LGBMPipeline) -> Dict[str, Any]:
    """Synthetic demo path — keeps legacy tests passing."""
    training_df = generate_demo_feature_table(n_races=500)
    future_df = _generate_demo_future_races(training_df, n_races=3)
    if future_df.empty:
        return {"predictions": [], "meta": {"status": "demo", "upcoming_count": 0}}

    feature_cols = pipeline.feature_names
    available = [c for c in feature_cols if c in future_df.columns]
    if not available:
        logger.warning("Demo future df has no overlap with pipeline.feature_names")
        return {"predictions": [], "meta": {"status": "demo", "upcoming_count": 0}}

    X = future_df[available].copy()
    try:
        scores = pipeline.predict(X)
    except Exception as e:
        logger.warning("Demo future prediction predict() failed: %s", e)
        return {"predictions": [], "meta": {"status": "demo", "upcoming_count": 0}}

    future_df = future_df.copy()
    future_df["predicted_score"] = scores
    predictions = _format_predictions(future_df)
    return {
        "predictions": predictions,
        "meta": {"status": "demo", "upcoming_count": len(predictions)},
    }


def _run_real_mode(pipeline: LGBMPipeline, db_path: str) -> Dict[str, Any]:
    """Real data path — prefers shipped parquet, falls back to N_RACE / N_UMA_RACE.

    Cloud Run image excludes the 13 GB jravan.db. The weekly ETL writes a
    small upcoming_races.parquet that ships with the image; in production
    we read that. Locally with the full DB present we still use sqlite so
    devs see freshest data without re-running the extract.
    """
    parquet_path = _resolve_upcoming_parquet(db_path)
    upcoming_df = pd.DataFrame()
    parquet_used = False
    latest_race_date = ""

    if parquet_path and os.path.exists(parquet_path):
        try:
            df = pd.read_parquet(parquet_path, engine="pyarrow")
            today = datetime.now().strftime("%Y-%m-%d")
            if "race_date" in df.columns:
                df = df[df["race_date"].astype(str) >= today].copy()
                if not df.empty:
                    latest_race_date = str(df["race_date"].max())
            upcoming_df = df
            parquet_used = True
            logger.info(
                "Loaded %d upcoming entries from parquet %s (latest=%s)",
                len(upcoming_df), parquet_path, latest_race_date,
            )
        except Exception as e:
            logger.warning("Failed reading upcoming parquet %s: %s", parquet_path, e)

    if not parquet_used:
        if not db_path or not os.path.exists(db_path):
            logger.warning("Real mode: no parquet and db_path not found (%s)", db_path)
            return {
                "predictions": [],
                "meta": {"status": "no_upcoming", "upcoming_count": 0, "reason": "db_missing"},
            }
        latest_race_date = _get_latest_race_date(db_path)
        upcoming_df = load_upcoming_race_entries(db_path)

    if upcoming_df.empty:
        today = datetime.now().strftime("%Y-%m-%d")
        logger.warning(
            "No upcoming races in DB. Latest RaceDate=%s, today=%s. "
            "Run EveryDB2 今週データ(B) first.",
            latest_race_date, today,
        )
        return {
            "predictions": [],
            "meta": {
                "status": "no_upcoming",
                "upcoming_count": 0,
                "latest_race_date": latest_race_date,
            },
        }

    training_df = _load_training_features_cache(db_path)
    feature_matrix = _build_upcoming_feature_matrix(
        upcoming_df, training_df, pipeline.feature_names,
    )

    try:
        scores = pipeline.predict(feature_matrix)
    except Exception as e:
        logger.warning("Real future prediction predict() failed: %s", e)
        return {
            "predictions": [],
            "meta": {"status": "unavailable", "upcoming_count": 0, "error": str(e)},
        }

    upcoming_df = upcoming_df.copy()
    upcoming_df["predicted_score"] = scores
    predictions = _format_predictions(upcoming_df)
    return {
        "predictions": predictions,
        "meta": {
            "status": "ok",
            "upcoming_count": len(predictions),
            "latest_race_date": latest_race_date,
        },
    }


def _resolve_upcoming_parquet(db_path: str) -> str:
    """Locate upcoming_races.parquet next to db_path, or under data/."""
    explicit = os.getenv("UPCOMING_PARQUET_PATH", "").strip()
    if explicit:
        return explicit
    data_dir = os.path.dirname(db_path) if db_path and os.path.dirname(db_path) else "data"
    return os.path.join(data_dir, "upcoming_races.parquet")


def _get_latest_race_date(db_path: str) -> str:
    try:
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            row = cur.execute("SELECT MAX(RaceDate) FROM N_RACE").fetchone()
            return row[0] if row and row[0] else ""
    except Exception as e:
        logger.debug("Could not read MAX(RaceDate): %s", e)
        return ""


def load_upcoming_race_entries(
    db_path: str,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> pd.DataFrame:
    """Return a DataFrame of this week's upcoming races (not yet finished).

    Upcoming = race_date in [from_date, to_date] AND KakuteiJyuni unset.
    Defaults: from_date = today, to_date = today + 7 days.
    """
    if from_date is None:
        from_date = datetime.now().strftime("%Y-%m-%d")
    if to_date is None:
        to_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")

    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {r[0] for r in cur.fetchall()}
        for required in ("N_RACE", "N_UMA_RACE"):
            if required not in tables:
                logger.warning("Required table %s missing from DB", required)
                return pd.DataFrame()

        cur.execute("PRAGMA table_info(N_UMA_RACE)")
        uma_cols = {r[1] for r in cur.fetchall()}

        base_uma_cols = [
            "RaceKey", "KettoNum", "Umaban", "Wakuban", "Bamei",
            "KisyuCode", "KisyuRyakusyo", "ChokyosiCode",
            "Futan", "Barei", "SexCD", "BaTaijyu", "KakuteiJyuni",
        ]
        optional_uma_cols = [
            "SireCode", "DamsireCode",
            "train_days_since_last", "train_last_hanro_time",
            "train_last_hanro_finish", "train_hanro_accel",
            "train_best_hanro_time_30d", "train_wood_avg_pace",
            "train_total_count_30d", "train_hanro_ratio",
            "fuku_odds_low", "fuku_odds_high", "fuku_odds_range",
        ]
        uma_select = [f"ur.{c}" for c in base_uma_cols if c in uma_cols]
        uma_select += [f"ur.{c}" for c in optional_uma_cols if c in uma_cols]

        race_select = [
            "r.RaceDate", "r.Kyori AS distance", "r.TrackCD",
            "r.JyoCD", "r.GradeCD", "r.Hondai AS race_name",
            "r.SyussoTosu", "r.TorokuTosu", "r.RaceNum",
        ]

        select_sql = ",\n       ".join(uma_select + race_select)
        query = f"""
SELECT {select_sql}
FROM N_UMA_RACE ur
JOIN N_RACE r ON ur.RaceKey = r.RaceKey
WHERE r.RaceDate BETWEEN ? AND ?
  AND (ur.KakuteiJyuni IS NULL OR TRIM(ur.KakuteiJyuni) = '' OR ur.KakuteiJyuni = '00')
ORDER BY r.RaceDate, r.JyoCD, r.RaceNum, ur.Umaban
"""
        df = pd.read_sql(query, conn, params=(from_date, to_date))

    if df.empty:
        return df

    rename_map = {
        "RaceKey": "race_key",
        "RaceDate": "race_date",
        "KettoNum": "horse_key",
        "Umaban": "umaban",
        "Wakuban": "waku",
        "Bamei": "_horse_name",
        "KisyuCode": "jockey_code",
        "KisyuRyakusyo": "_jockey",
        "ChokyosiCode": "trainer_code",
        "Futan": "weight_carried",
        "Barei": "age",
        "SexCD": "sex",
        "BaTaijyu": "body_weight",
        "SireCode": "sire_code",
        "DamsireCode": "damsire_code",
        "TrackCD": "_track_cd",
        "JyoCD": "place",
        "GradeCD": "grade",
        "race_name": "_race_name",
        "SyussoTosu": "field_size",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    for num_col in (
        "distance", "umaban", "waku", "weight_carried", "age",
        "body_weight", "field_size", "TorokuTosu", "RaceNum",
    ):
        if num_col in df.columns:
            df[num_col] = pd.to_numeric(df[num_col], errors="coerce")

    if "horse_key" in df.columns:
        df["horse_key"] = df["horse_key"].astype(str)

    if "_track_cd" in df.columns:
        df["_surface_label"] = df["_track_cd"].apply(_track_cd_to_label)
        df["surface"] = df["_track_cd"].apply(_track_cd_to_surface_int)
    else:
        df["_surface_label"] = ""
        df["surface"] = 0

    if "umaban" in df.columns:
        df["_gate_number"] = df["umaban"]

    # race_name may arrive with trailing spaces in JRA-VAN fixed-width format
    if "_race_name" in df.columns:
        df["_race_name"] = df["_race_name"].astype(str).str.strip()

    return df


def _load_training_features_cache(db_path: str) -> pd.DataFrame:
    """Load the feature_table_cache that training was fit on.

    Returns empty DataFrame if cache not present — the feature matrix
    will then rely on upcoming row values + NaN fills.
    """
    data_dir = os.path.dirname(db_path) if db_path and os.path.dirname(db_path) else "data"
    cache_parquet = os.path.join(data_dir, "feature_table_cache.parquet")
    cache_csv = os.path.join(data_dir, "feature_table_cache.csv")
    try:
        if os.path.exists(cache_parquet):
            logger.info("Loading training feature cache (parquet): %s", cache_parquet)
            return pd.read_parquet(cache_parquet, engine="pyarrow")
        if os.path.exists(cache_csv):
            logger.info("Loading training feature cache (csv): %s", cache_csv)
            return pd.read_csv(cache_csv, low_memory=False)
    except Exception as e:
        logger.warning("Failed to load training feature cache: %s", e)
    return pd.DataFrame()


def _build_upcoming_feature_matrix(
    upcoming_df: pd.DataFrame,
    training_df: pd.DataFrame,
    feature_names: List[str],
) -> pd.DataFrame:
    """Assemble the feature matrix so every pipeline.feature_name is covered.

    For each required column:
    - If the upcoming row carries it → use that value (race-day meta).
    - Else if the training cache has it → take the latest row per horse.
    - Else → NaN (pipeline.predict fills these).
    """
    if upcoming_df.empty:
        return pd.DataFrame(columns=feature_names)

    latest_by_horse = pd.DataFrame()
    if not training_df.empty and "horse_key" in training_df.columns:
        tdf = training_df.copy()
        tdf["horse_key"] = tdf["horse_key"].astype(str)
        sort_cols = [c for c in ["horse_key", "race_date"] if c in tdf.columns]
        if sort_cols:
            tdf = tdf.sort_values(sort_cols)
        latest_by_horse = (
            tdf.groupby("horse_key", as_index=False).tail(1).set_index("horse_key")
        )

    if not latest_by_horse.empty and "horse_key" in upcoming_df.columns:
        horse_keys = upcoming_df["horse_key"].astype(str).values
        reindexed = latest_by_horse.reindex(horse_keys).reset_index(drop=True)
    else:
        reindexed = pd.DataFrame(index=range(len(upcoming_df)))

    matrix = pd.DataFrame(index=range(len(upcoming_df)))
    coverage = {"upcoming": 0, "cache": 0, "nan": 0}
    sources: Dict[str, str] = {}
    for col in feature_names:
        if col in upcoming_df.columns:
            matrix[col] = upcoming_df[col].values
            coverage["upcoming"] += 1
            sources[col] = "upcoming"
        elif col in reindexed.columns:
            matrix[col] = reindexed[col].values
            coverage["cache"] += 1
            sources[col] = "cache"
        else:
            matrix[col] = np.nan
            coverage["nan"] += 1
            sources[col] = "nan"

    total = len(feature_names) or 1
    logger.info(
        "Feature matrix coverage: %d/%d upcoming (%.0f%%), %d/%d cache (%.0f%%), %d NaN",
        coverage["upcoming"], total, 100 * coverage["upcoming"] / total,
        coverage["cache"], total, 100 * coverage["cache"] / total,
        coverage["nan"],
    )
    if os.getenv(_DEBUG_ENV):
        for col, src in sources.items():
            logger.debug("  %s ← %s", col, src)
    return matrix


def _generate_demo_future_races(
    training_df: pd.DataFrame,
    n_races: int = 3,
) -> pd.DataFrame:
    """Create synthetic future race entries from the training horse pool.

    Uses horses that appeared in training so as-of features already exist,
    making the predictions realistic. Kept for the demo path and tests.
    """
    rng = np.random.RandomState(99)

    if training_df.empty:
        return pd.DataFrame()

    if "race_date" in training_df.columns:
        max_date = pd.to_datetime(training_df["race_date"]).max()
        future_base = max_date + timedelta(days=7)
    else:
        future_base = pd.Timestamp("2024-07-01")

    horse_col = "horse_key" if "horse_key" in training_df.columns else None
    if horse_col is None:
        logger.warning("No horse_key column in training data")
        return pd.DataFrame()

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
            horse_history = training_df[training_df[horse_col] == horse_key]
            if horse_history.empty:
                continue

            latest = horse_history.iloc[-1]

            row = latest.to_dict()
            row["race_key"] = race_key
            row["race_date"] = race_date
            row["distance"] = distance
            row["surface"] = surface_val
            row["finish_order"] = np.nan
            row["umaban"] = gate_num
            row["waku"] = min(8, (gate_num - 1) // 2 + 1)

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
    """Format raw predictions into the API response structure."""
    results = []
    for race_key, group in df.groupby("race_key"):
        group_sorted = group.sort_values("predicted_score", ascending=False).reset_index(drop=True)

        first = group_sorted.iloc[0]
        race_date = str(first.get("race_date", ""))
        race_name = str(first.get("_race_name", race_key))
        distance_val = first.get("distance", 0)
        try:
            distance = int(distance_val) if pd.notna(distance_val) else 0
        except (TypeError, ValueError):
            distance = 0
        surface = str(first.get("_surface_label", ""))

        entries = []
        scores = group_sorted["predicted_score"].values
        score_range = scores.max() - scores.min() if len(scores) > 1 else 1.0

        for rank, (_, row) in enumerate(group_sorted.iterrows(), 1):
            score = float(row["predicted_score"])

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

            gate_val = row.get("_gate_number", rank)
            try:
                gate_number = int(gate_val) if pd.notna(gate_val) else rank
            except (TypeError, ValueError):
                gate_number = rank

            entries.append({
                "rank": rank,
                "horse_name": str(row.get("_horse_name", f"Horse-{rank}")),
                "predicted_score": round(score, 4),
                "confidence": confidence,
                "jockey": str(row.get("_jockey", "")),
                "gate_number": gate_number,
            })

        results.append({
            "race_key": str(race_key),
            "race_date": race_date,
            "race_name": race_name,
            "distance": distance,
            "surface": surface,
            "entries": entries,
        })

    results.sort(key=lambda r: r["race_key"])
    return results

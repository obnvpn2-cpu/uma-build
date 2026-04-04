"""Feature builder for UmaBuild.

Reads JRA-VAN EveryDB2 SQLite data and builds a feature table with
as-of (point-in-time) statistics for each horse in each race.

The code is flexible about column names -- it tries multiple possible
patterns and logs warnings for missing columns.
"""

import logging
import os
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Column name mapping -- EveryDB2 column names can vary.
# Each key is our canonical name; the value is a list of possible DB names.
# The builder tries each in order and uses the first match found.
# ---------------------------------------------------------------------------

COLUMN_CANDIDATES: Dict[str, List[str]] = {
    # N_RACE columns
    "race_key": ["RaceKey", "RACE_KEY", "racekey", "race_key", "レースキー"],
    "race_date": ["RaceDate", "RACE_DATE", "racedate", "race_date", "Year"],
    "place": ["Place", "PLACE", "place", "JyoCD", "Jyo"],
    "distance": ["Distance", "DISTANCE", "distance", "Kyori"],
    "track_type": ["TrackType", "TRACK_TYPE", "tracktype", "track_type", "TrackCD", "SibaBaba"],
    "track_condition": ["TrackCondition", "TRACK_CONDITION", "trackcondition",
                        "track_condition", "BabaCD", "BabaSt"],
    "grade": ["Grade", "GRADE", "grade", "GradeCD", "JyuryoCD"],
    "race_class": ["RaceClass", "RACE_CLASS", "raceclass", "race_class", "ClassCD"],
    "field_size": ["FieldSize", "FIELD_SIZE", "fieldsize", "field_size", "TorokuTosu", "SyussoTosu"],
    # N_UMA_RACE columns
    "horse_key": ["HorseKey", "HORSE_KEY", "horsekey", "horse_key", "KettoNum", "UmaKey"],
    "finish_order": ["FinishOrder", "FINISH_ORDER", "finishorder", "finish_order",
                     "KakuteiJyuni", "ChakuJyuni", "Tyaku"],
    "time": ["Time", "TIME", "time", "HaronTimeL3", "RaceTime"],
    "last3f": ["Last3F", "LAST3F", "last3f", "HaronTimeL3", "L3F", "AgariSanten"],
    "passing_order": ["PassingOrder", "PASSING_ORDER", "passingorder", "passing_order",
                      "Corner1", "CornerJyuni"],
    "corner3": ["Corner3", "corner3", "CornerJyuni3"],
    "corner4": ["Corner4", "corner4", "CornerJyuni4"],
    "win_odds": ["WinOdds", "WIN_ODDS", "winodds", "win_odds", "Odds", "TansyoOdds"],
    "popularity": ["Popularity", "POPULARITY", "popularity", "Ninki", "NinkiJyuni"],
    "body_weight": ["BodyWeight", "BODY_WEIGHT", "bodyweight", "body_weight",
                    "Bataiju", "ZogenFugo"],
    "body_weight_diff": ["BodyWeightDiff", "BODY_WEIGHT_DIFF", "bodyweightdiff",
                         "body_weight_diff", "BataijuZougen", "Zogen"],
    "jockey_code": ["JockeyCode", "JOCKEY_CODE", "jockeycode", "jockey_code",
                    "KisyuCode", "Kisyu"],
    "trainer_code": ["TrainerCode", "TRAINER_CODE", "trainercode", "trainer_code",
                     "ChokyosiCode", "Chokyosi"],
    "waku": ["Waku", "WAKU", "waku", "Wakuban"],
    "umaban": ["Umaban", "UMABAN", "umaban", "UmabanCD", "UmaBan"],
    "sex": ["Sex", "SEX", "sex", "SexCD", "Seibetsu"],
    "age": ["Age", "AGE", "age", "Barei"],
    "weight_carried": ["WeightCarried", "WEIGHT_CARRIED", "weightcarried",
                       "weight_carried", "Futan", "FutanJuryo"],
    "prize_money": ["PrizeMoney", "PRIZE_MONEY", "prizemoney", "prize_money",
                    "Honsyokin", "Syokin"],
}


def _resolve_column(df: pd.DataFrame, canonical: str) -> Optional[str]:
    """Find the actual column name in df for a canonical name."""
    candidates = COLUMN_CANDIDATES.get(canonical, [canonical])
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _resolve_columns(df: pd.DataFrame) -> Dict[str, Optional[str]]:
    """Resolve all canonical column names against a DataFrame."""
    mapping: Dict[str, Optional[str]] = {}
    for canonical in COLUMN_CANDIDATES:
        mapping[canonical] = _resolve_column(df, canonical)
    return mapping


def _safe_float(series: pd.Series) -> pd.Series:
    """Convert series to float, coercing errors to NaN."""
    return pd.to_numeric(series, errors="coerce")


def _distance_category(dist: float) -> str:
    """Categorise distance into sprint/mile/intermediate/long/extended."""
    if dist <= 1200:
        return "sprint"
    elif dist <= 1600:
        return "mile"
    elif dist <= 2000:
        return "intermediate"
    elif dist <= 2400:
        return "long"
    else:
        return "extended"


def _classify_running_style(avg_corner4_pct: float) -> int:
    """Classify running style from avg 4-corner position percentile.

    Returns 1=逃げ, 2=先行, 3=差し, 4=追込.
    """
    if avg_corner4_pct <= 0.15:
        return 1
    elif avg_corner4_pct <= 0.40:
        return 2
    elif avg_corner4_pct <= 0.70:
        return 3
    else:
        return 4


# ---------------------------------------------------------------------------
# Core builder
# ---------------------------------------------------------------------------

def _load_race_table(conn: sqlite3.Connection) -> Optional[pd.DataFrame]:
    """Attempt to load the race master table."""
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    logger.info("Available tables: %s", tables)

    # Try common table names
    race_table_candidates = ["N_RACE", "n_race", "RACE", "race"]
    for t in race_table_candidates:
        if t in tables:
            logger.info("Using race table: %s", t)
            return pd.read_sql(f"SELECT * FROM [{t}]", conn)

    logger.warning("No race table found among: %s", tables)
    return None


def _load_uma_race_table(conn: sqlite3.Connection) -> Optional[pd.DataFrame]:
    """Attempt to load the horse-race result table."""
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]

    uma_race_candidates = ["N_UMA_RACE", "n_uma_race", "UMA_RACE", "uma_race",
                           "HORSE_RACE", "horse_race"]
    for t in uma_race_candidates:
        if t in tables:
            logger.info("Using uma_race table: %s", t)
            return pd.read_sql(f"SELECT * FROM [{t}]", conn)

    logger.warning("No uma_race table found among: %s", tables)
    return None


def _compute_as_of_features(df: pd.DataFrame, col: Dict[str, Optional[str]]) -> pd.DataFrame:
    """Compute as-of (point-in-time) features for each row.

    All statistics are calculated using only races BEFORE the current
    race_date, never including the current race.
    """
    # Ensure required columns exist
    c_race_key = col.get("race_key")
    c_horse_key = col.get("horse_key")
    c_race_date = col.get("race_date")
    c_finish = col.get("finish_order")

    if not all([c_race_key, c_horse_key, c_race_date, c_finish]):
        logger.error(
            "Missing required columns. race_key=%s, horse_key=%s, race_date=%s, finish_order=%s",
            c_race_key, c_horse_key, c_race_date, c_finish,
        )
        return df

    # Sort by date for chronological processing
    df = df.sort_values(c_race_date).reset_index(drop=True)

    # Prepare numeric columns
    df["_finish"] = _safe_float(df[c_finish])
    df["_is_win"] = (df["_finish"] == 1).astype(float)
    df["_is_in3"] = (df["_finish"] <= 3).astype(float)

    c_distance = col.get("distance")
    c_surface = col.get("track_type")
    c_place = col.get("place")
    c_last3f = col.get("last3f")
    c_corner3 = col.get("corner3")
    c_corner4 = col.get("corner4")
    c_body_weight = col.get("body_weight")
    c_body_weight_diff = col.get("body_weight_diff")
    c_prize = col.get("prize_money")
    c_jockey = col.get("jockey_code")
    c_trainer = col.get("trainer_code")
    c_field_size = col.get("field_size")
    c_grade = col.get("grade")

    # Prepare optional numeric columns
    if c_distance:
        df["_distance"] = _safe_float(df[c_distance])
        df["_dist_cat"] = df["_distance"].apply(
            lambda x: _distance_category(x) if pd.notna(x) else None
        )
    if c_last3f:
        df["_last3f"] = _safe_float(df[c_last3f])
    if c_corner3:
        df["_corner3"] = _safe_float(df[c_corner3])
    if c_corner4:
        df["_corner4"] = _safe_float(df[c_corner4])
    if c_body_weight:
        df["_body_weight"] = _safe_float(df[c_body_weight])
    if c_body_weight_diff:
        df["_body_weight_diff"] = _safe_float(df[c_body_weight_diff])
    if c_prize:
        df["_prize"] = _safe_float(df[c_prize])
    if c_field_size:
        df["_field_size"] = _safe_float(df[c_field_size])

    # -----------------------------------------------------------------------
    # Group-by horse for as-of computation
    # -----------------------------------------------------------------------
    logger.info("Computing as-of features for %d rows...", len(df))

    # Pre-allocate result columns
    result_cols = [
        "horse_n_starts", "horse_n_wins", "horse_win_rate", "horse_in3_rate",
        "horse_avg_finish",
        "horse_dist_win_rate", "horse_dist_in3_rate",
        "horse_surface_win_rate", "horse_surface_in3_rate",
        "horse_course_win_rate",
        "horse_recent3_avg", "horse_recent5_avg", "horse_recent3_win_rate",
        "horse_days_since_last", "horse_last_finish",
        "horse_avg_weight", "weight_dev_from_avg", "weight_trend_3", "abs_weight_diff",
        "horse_avg_corner3", "horse_avg_corner4",
        "horse_avg_last3f", "horse_best_last3f",
        "horse_avg_position_change", "horse_running_style",
        "horse_last3f_rank_avg", "horse_recent3_last3f",
        "horse_total_prize", "horse_avg_prize",
        "horse_max_grade", "horse_grade_n_starts", "horse_grade_win_rate",
        "horse_class_change", "horse_prize_rank_in_field",
        "horse_earnings_per_start",
        "jockey_win_rate", "jockey_in3_rate",
        "jockey_dist_win_rate", "jockey_surface_win_rate",
        "jockey_recent20_win_rate", "jockey_course_win_rate",
        "jockey_horse_combo_n", "jockey_horse_combo_win_rate",
        "trainer_win_rate", "trainer_in3_rate",
        "trainer_dist_win_rate", "trainer_surface_win_rate",
        "trainer_recent20_win_rate", "trainer_course_win_rate",
        "trainer_horse_combo_n", "trainer_horse_combo_win_rate",
    ]
    for rc in result_cols:
        df[rc] = np.nan

    # Convert race_date to datetime for chronological filtering
    df["_race_date_dt"] = pd.to_datetime(df[c_race_date], errors="coerce")

    # We process horse-by-horse to keep as-of correctness.
    # For large datasets, this is vectorised within each horse group.
    horse_groups = df.groupby(c_horse_key)
    total_groups = len(horse_groups)
    log_interval = max(1, total_groups // 20)

    for idx, (horse_id, horse_df) in enumerate(horse_groups):
        if idx % log_interval == 0:
            logger.info("  Horse progress: %d / %d (%.0f%%)", idx, total_groups,
                        100.0 * idx / total_groups)

        indices = horse_df.index.tolist()
        if len(indices) == 0:
            continue

        for pos, i in enumerate(indices):
            # "as-of" data: all rows for this horse BEFORE the current row
            past = horse_df.iloc[:pos]
            if len(past) == 0:
                continue

            n_starts = len(past)
            n_wins = int(past["_is_win"].sum())
            df.at[i, "horse_n_starts"] = n_starts
            df.at[i, "horse_n_wins"] = n_wins
            df.at[i, "horse_win_rate"] = n_wins / n_starts if n_starts > 0 else 0.0
            df.at[i, "horse_in3_rate"] = past["_is_in3"].mean()
            df.at[i, "horse_avg_finish"] = past["_finish"].mean()

            # Distance-specific stats
            if c_distance and "_dist_cat" in df.columns:
                current_dist_cat = df.at[i, "_dist_cat"]
                if current_dist_cat is not None:
                    dist_past = past[past["_dist_cat"] == current_dist_cat]
                    if len(dist_past) > 0:
                        df.at[i, "horse_dist_win_rate"] = dist_past["_is_win"].mean()
                        df.at[i, "horse_dist_in3_rate"] = dist_past["_is_in3"].mean()

            # Surface-specific stats
            if c_surface:
                current_surface = df.at[i, c_surface]
                surface_past = past[past[c_surface] == current_surface]
                if len(surface_past) > 0:
                    df.at[i, "horse_surface_win_rate"] = surface_past["_is_win"].mean()
                    df.at[i, "horse_surface_in3_rate"] = surface_past["_is_in3"].mean()

            # Course-specific stats
            if c_place:
                current_place = df.at[i, c_place]
                course_past = past[past[c_place] == current_place]
                if len(course_past) > 0:
                    df.at[i, "horse_course_win_rate"] = course_past["_is_win"].mean()

            # Recent form
            recent3 = past.tail(3)
            recent5 = past.tail(5)
            df.at[i, "horse_recent3_avg"] = recent3["_finish"].mean()
            df.at[i, "horse_recent5_avg"] = recent5["_finish"].mean()
            df.at[i, "horse_recent3_win_rate"] = recent3["_is_win"].mean()
            df.at[i, "horse_last_finish"] = past.iloc[-1]["_finish"]

            # Days since last race
            if "_race_date_dt" in df.columns:
                current_date = df.at[i, "_race_date_dt"]
                last_date = past.iloc[-1]["_race_date_dt"]
                if pd.notna(current_date) and pd.notna(last_date):
                    df.at[i, "horse_days_since_last"] = (current_date - last_date).days

            # Weight features
            if c_body_weight and "_body_weight" in df.columns:
                past_weights = past["_body_weight"].dropna()
                if len(past_weights) > 0:
                    avg_w = past_weights.mean()
                    df.at[i, "horse_avg_weight"] = avg_w
                    current_w = df.at[i, "_body_weight"]
                    if pd.notna(current_w):
                        df.at[i, "weight_dev_from_avg"] = current_w - avg_w
                if len(past_weights) >= 3:
                    last3_weights = past_weights.tail(3)
                    # Weight trend: slope of last 3 weights
                    x = np.arange(len(last3_weights), dtype=float)
                    y = last3_weights.values.astype(float)
                    if np.std(x) > 0:
                        slope = np.polyfit(x, y, 1)[0]
                        df.at[i, "weight_trend_3"] = slope

            if c_body_weight_diff and "_body_weight_diff" in df.columns:
                bwd = df.at[i, "_body_weight_diff"]
                if pd.notna(bwd):
                    df.at[i, "abs_weight_diff"] = abs(bwd)

            # Corner / pace features
            if "_corner3" in df.columns:
                past_c3 = past["_corner3"].dropna()
                if len(past_c3) > 0:
                    df.at[i, "horse_avg_corner3"] = past_c3.mean()

            if "_corner4" in df.columns:
                past_c4 = past["_corner4"].dropna()
                if len(past_c4) > 0:
                    df.at[i, "horse_avg_corner4"] = past_c4.mean()
                    # Running style based on avg corner4 percentile
                    if c_field_size and "_field_size" in df.columns:
                        avg_fs = past["_field_size"].dropna().mean()
                        if avg_fs > 0:
                            pct = past_c4.mean() / avg_fs
                            df.at[i, "horse_running_style"] = _classify_running_style(pct)

            if "_last3f" in df.columns:
                past_l3 = past["_last3f"].dropna()
                if len(past_l3) > 0:
                    df.at[i, "horse_avg_last3f"] = past_l3.mean()
                    df.at[i, "horse_best_last3f"] = past_l3.min()
                recent3_l3 = past.tail(3)["_last3f"].dropna()
                if len(recent3_l3) > 0:
                    df.at[i, "horse_recent3_last3f"] = recent3_l3.mean()

            # Position change (corner4 -> finish)
            if "_corner4" in df.columns:
                past_both = past[["_corner4", "_finish"]].dropna()
                if len(past_both) > 0:
                    changes = past_both["_corner4"] - past_both["_finish"]
                    df.at[i, "horse_avg_position_change"] = changes.mean()

            # Prize features
            if "_prize" in df.columns:
                past_prize = past["_prize"].dropna()
                if len(past_prize) > 0:
                    df.at[i, "horse_total_prize"] = past_prize.sum()
                    df.at[i, "horse_avg_prize"] = past_prize.mean()
                    df.at[i, "horse_earnings_per_start"] = past_prize.sum() / n_starts

            # Grade features
            if c_grade:
                past_grade = past[past[c_grade].notna()]
                # Assume grade codes: 1=G1, 2=G2, 3=G3, lower numbers = higher grade
                grade_numeric = _safe_float(past_grade[c_grade])
                grade_valid = grade_numeric.dropna()
                if len(grade_valid) > 0:
                    df.at[i, "horse_max_grade"] = grade_valid.min()
                # Graded races: consider grade <= 3 as graded
                graded = past_grade[grade_numeric <= 3]
                df.at[i, "horse_grade_n_starts"] = len(graded)
                if len(graded) > 0:
                    graded_finish = _safe_float(graded[c_finish])
                    df.at[i, "horse_grade_win_rate"] = (graded_finish == 1).mean()

    # -----------------------------------------------------------------------
    # Jockey as-of stats (computed per jockey across all horses)
    # -----------------------------------------------------------------------
    if c_jockey:
        logger.info("Computing jockey as-of features...")
        _compute_agent_stats(
            df, c_jockey, c_finish, c_race_date,
            prefix="jockey",
            c_horse_key=c_horse_key,
            c_distance_cat="_dist_cat" if c_distance else None,
            c_surface=c_surface,
            c_place=c_place,
        )

    # -----------------------------------------------------------------------
    # Trainer as-of stats
    # -----------------------------------------------------------------------
    if c_trainer:
        logger.info("Computing trainer as-of features...")
        _compute_agent_stats(
            df, c_trainer, c_finish, c_race_date,
            prefix="trainer",
            c_horse_key=c_horse_key,
            c_distance_cat="_dist_cat" if c_distance else None,
            c_surface=c_surface,
            c_place=c_place,
        )

    # -----------------------------------------------------------------------
    # Class change (compared to previous race)
    # -----------------------------------------------------------------------
    if c_grade:
        for horse_id, horse_df in df.groupby(c_horse_key):
            indices = horse_df.index.tolist()
            for pos, i in enumerate(indices):
                if pos == 0:
                    continue
                prev_grade = _safe_float(pd.Series([horse_df.iloc[pos - 1][c_grade]])).iloc[0]
                curr_grade = _safe_float(pd.Series([df.at[i, c_grade]])).iloc[0]
                if pd.notna(prev_grade) and pd.notna(curr_grade):
                    # Lower number = higher grade, so decrease = upgrade
                    df.at[i, "horse_class_change"] = prev_grade - curr_grade

    # -----------------------------------------------------------------------
    # Prize rank within field (per race)
    # -----------------------------------------------------------------------
    if "horse_total_prize" in df.columns:
        logger.info("Computing prize rank within field...")
        if c_race_key:
            for race_id, race_df in df.groupby(c_race_key):
                prizes = race_df["horse_total_prize"].dropna()
                if len(prizes) > 0:
                    ranks = prizes.rank(ascending=False, method="min")
                    df.loc[ranks.index, "horse_prize_rank_in_field"] = ranks

    # -----------------------------------------------------------------------
    # Last3F rank average (per race, then averaged over past races)
    # -----------------------------------------------------------------------
    if "_last3f" in df.columns and c_race_key:
        logger.info("Computing last3f rank within each race...")
        df["_last3f_rank"] = np.nan
        for race_id, race_df in df.groupby(c_race_key):
            l3 = race_df["_last3f"].dropna()
            if len(l3) > 0:
                ranks = l3.rank(ascending=True, method="min")
                df.loc[ranks.index, "_last3f_rank"] = ranks

        # Now compute horse average of last3f_rank
        for horse_id, horse_df in df.groupby(c_horse_key):
            indices = horse_df.index.tolist()
            for pos, i in enumerate(indices):
                past = horse_df.iloc[:pos]
                if len(past) > 0:
                    past_ranks = past["_last3f_rank"].dropna()
                    if len(past_ranks) > 0:
                        df.at[i, "horse_last3f_rank_avg"] = past_ranks.mean()

    # Clean up temporary columns
    temp_cols = [c for c in df.columns if c.startswith("_")]
    df = df.drop(columns=temp_cols, errors="ignore")

    logger.info("Feature computation complete. Shape: %s", df.shape)
    return df


def _compute_agent_stats(
    df: pd.DataFrame,
    agent_col: str,
    finish_col: str,
    date_col: str,
    prefix: str,
    c_horse_key: Optional[str] = None,
    c_distance_cat: Optional[str] = None,
    c_surface: Optional[str] = None,
    c_place: Optional[str] = None,
) -> None:
    """Compute as-of stats for an agent (jockey or trainer) in-place.

    This modifies df in-place, adding columns like {prefix}_win_rate, etc.
    """
    finish_numeric = _safe_float(df[finish_col])
    is_win = (finish_numeric == 1).astype(float)
    is_in3 = (finish_numeric <= 3).astype(float)

    agent_groups = df.groupby(agent_col)
    total_agents = len(agent_groups)
    log_interval = max(1, total_agents // 10)

    for idx, (agent_id, agent_df) in enumerate(agent_groups):
        if idx % log_interval == 0:
            logger.info("  %s progress: %d / %d", prefix, idx, total_agents)

        indices = agent_df.index.tolist()

        for pos, i in enumerate(indices):
            past = agent_df.iloc[:pos]
            if len(past) == 0:
                continue

            n = len(past)
            past_finish = _safe_float(past[finish_col])
            past_win = (past_finish == 1).astype(float)
            past_in3 = (past_finish <= 3).astype(float)

            df.at[i, f"{prefix}_win_rate"] = past_win.mean()
            df.at[i, f"{prefix}_in3_rate"] = past_in3.mean()

            # Distance-specific
            if c_distance_cat and c_distance_cat in df.columns:
                cur_dist = df.at[i, c_distance_cat]
                if cur_dist is not None:
                    dist_past = past[past[c_distance_cat] == cur_dist]
                    if len(dist_past) > 0:
                        dp_finish = _safe_float(dist_past[finish_col])
                        df.at[i, f"{prefix}_dist_win_rate"] = (dp_finish == 1).mean()

            # Surface-specific
            if c_surface and c_surface in df.columns:
                cur_surface = df.at[i, c_surface]
                surf_past = past[past[c_surface] == cur_surface]
                if len(surf_past) > 0:
                    sp_finish = _safe_float(surf_past[finish_col])
                    df.at[i, f"{prefix}_surface_win_rate"] = (sp_finish == 1).mean()

            # Recent 20
            recent20 = past.tail(20)
            r20_finish = _safe_float(recent20[finish_col])
            df.at[i, f"{prefix}_recent20_win_rate"] = (r20_finish == 1).mean()

            # Course-specific
            if c_place and c_place in df.columns:
                cur_place = df.at[i, c_place]
                place_past = past[past[c_place] == cur_place]
                if len(place_past) > 0:
                    pp_finish = _safe_float(place_past[finish_col])
                    df.at[i, f"{prefix}_course_win_rate"] = (pp_finish == 1).mean()

            # Horse combo stats
            if c_horse_key and c_horse_key in df.columns:
                cur_horse = df.at[i, c_horse_key]
                combo_past = past[past[c_horse_key] == cur_horse]
                df.at[i, f"{prefix}_horse_combo_n"] = len(combo_past)
                if len(combo_past) > 0:
                    cp_finish = _safe_float(combo_past[finish_col])
                    df.at[i, f"{prefix}_horse_combo_win_rate"] = (cp_finish == 1).mean()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_feature_table(db_path: str, output_path: Optional[str] = None) -> pd.DataFrame:
    """Build the feature table from JRA-VAN EveryDB2 SQLite database.

    Args:
        db_path: Path to the EveryDB2 SQLite file.
        output_path: Optional path to save the feature table as CSV.

    Returns:
        DataFrame with computed features.
    """
    logger.info("Building feature table from: %s", db_path)

    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database not found: {db_path}")

    conn = sqlite3.connect(db_path)
    try:
        # Load tables
        race_df = _load_race_table(conn)
        uma_race_df = _load_uma_race_table(conn)

        if race_df is None or uma_race_df is None:
            raise ValueError("Could not load required tables from the database.")

        logger.info("Race table shape: %s, UmaRace table shape: %s",
                     race_df.shape, uma_race_df.shape)

        # Resolve column names
        race_col = _resolve_columns(race_df)
        uma_col = _resolve_columns(uma_race_df)

        # Determine the join key
        race_key_in_race = race_col.get("race_key")
        race_key_in_uma = uma_col.get("race_key")

        if not race_key_in_race or not race_key_in_uma:
            # Try to find a common column
            common = set(race_df.columns) & set(uma_race_df.columns)
            logger.warning("No race_key found. Common columns: %s", common)
            if common:
                join_key = list(common)[0]
                logger.info("Using common column as join key: %s", join_key)
            else:
                raise ValueError("No common column found to join race and uma_race tables.")
        else:
            join_key = race_key_in_race
            if race_key_in_race != race_key_in_uma:
                uma_race_df = uma_race_df.rename(columns={race_key_in_uma: race_key_in_race})

        # Join
        logger.info("Joining race + uma_race on: %s", join_key)
        # Avoid column name conflicts with suffixes
        df = pd.merge(uma_race_df, race_df, on=join_key, how="left", suffixes=("", "_race"))

        logger.info("Joined table shape: %s", df.shape)
        logger.info("Columns: %s", list(df.columns[:30]))

        # Re-resolve columns on the joined table
        col = _resolve_columns(df)
        missing = [k for k, v in col.items() if v is None]
        if missing:
            logger.warning("Missing columns after join: %s", missing)

        # Compute features
        df = _compute_as_of_features(df, col)

        # Add target columns
        c_finish = col.get("finish_order")
        if c_finish:
            finish = _safe_float(df[c_finish])
            df["target_win"] = (finish == 1).astype(int)
            df["target_in3"] = (finish <= 3).astype(int)

        # Rename raw columns to canonical names for the feature table
        rename_map = {}
        for canonical, actual in col.items():
            if actual and actual in df.columns and actual != canonical:
                # Only rename if the canonical name isn't already taken
                if canonical not in df.columns:
                    rename_map[actual] = canonical
        if rename_map:
            df = df.rename(columns=rename_map)

        if output_path:
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            df.to_csv(output_path, index=False)
            logger.info("Feature table saved to: %s", output_path)

        return df

    finally:
        conn.close()


def generate_demo_feature_table(n_races: int = 500, avg_field_size: int = 14) -> pd.DataFrame:
    """Generate a synthetic feature table for demo/testing.

    Creates realistic-looking horse racing data without requiring a real DB.

    Args:
        n_races: Number of races to simulate.
        avg_field_size: Average number of horses per race.

    Returns:
        DataFrame matching the feature_table schema.
    """
    logger.info("Generating demo feature table: %d races, avg %d horses/race",
                n_races, avg_field_size)

    rng = np.random.RandomState(42)

    rows = []
    base_date = datetime(2024, 1, 1)

    # Simulate horse pool
    n_horses = 800
    horse_abilities = rng.normal(0, 1, n_horses)  # latent ability
    n_jockeys = 50
    jockey_abilities = rng.normal(0, 0.3, n_jockeys)
    n_trainers = 40
    trainer_abilities = rng.normal(0, 0.2, n_trainers)

    courses = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]  # 10 courses
    distances = [1000, 1200, 1400, 1600, 1800, 2000, 2200, 2400, 2600, 3000, 3200]
    surfaces = [1, 2]  # 1=turf, 2=dirt
    conditions = [1, 2, 3, 4]  # good, slightly_heavy, heavy, bad
    grades = [1, 2, 3, 4, 5]  # G1, G2, G3, OP, conditions

    for race_idx in range(n_races):
        race_key = f"R{race_idx:06d}"
        race_date = base_date + timedelta(days=race_idx // 3)  # ~3 races per day
        course_id = rng.choice(courses)
        distance = rng.choice(distances)
        surface = rng.choice(surfaces)
        condition = rng.choice(conditions)
        grade = rng.choice(grades, p=[0.02, 0.03, 0.05, 0.15, 0.75])
        field_size = rng.randint(max(6, avg_field_size - 4), avg_field_size + 5)

        # Select horses for this race
        horse_indices = rng.choice(n_horses, size=field_size, replace=False)

        # Simulate race outcome
        abilities = []
        for h_idx in horse_indices:
            jockey_idx = rng.randint(0, n_jockeys)
            trainer_idx = rng.randint(0, n_trainers)
            noise = rng.normal(0, 1.5)
            total_ability = (horse_abilities[h_idx] + jockey_abilities[jockey_idx]
                             + trainer_abilities[trainer_idx] + noise)
            abilities.append((h_idx, jockey_idx, trainer_idx, total_ability))

        # Sort by ability (descending) to get finish order
        abilities.sort(key=lambda x: -x[3])

        for finish_pos, (h_idx, j_idx, t_idx, ability) in enumerate(abilities, 1):
            waku = min(8, (finish_pos - 1) // 2 + 1)
            umaban = finish_pos  # simplified
            sex_val = rng.choice([1, 2, 3], p=[0.55, 0.40, 0.05])
            age_val = rng.choice([2, 3, 4, 5, 6, 7], p=[0.10, 0.25, 0.25, 0.20, 0.12, 0.08])
            weight_carried = 55.0 + rng.normal(0, 2)
            body_weight = 460 + rng.normal(0, 30)
            weight_diff_val = rng.normal(0, 4)
            last3f_time = 33.0 + rng.normal(0, 1.5) + finish_pos * 0.15
            corner4_pos = max(1, min(field_size, int(finish_pos + rng.normal(0, 3))))
            corner3_pos = max(1, min(field_size, int(corner4_pos + rng.normal(0, 2))))

            # Win odds (roughly inversely correlated with ability)
            raw_odds = max(1.1, 10.0 - ability * 2.0 + rng.exponential(3))
            popularity = finish_pos  # simplified, correlated with outcome

            # Prize money (for winners more)
            if finish_pos == 1:
                prize = rng.uniform(500, 5000) * (6 - grade)
            elif finish_pos <= 3:
                prize = rng.uniform(100, 1000) * (6 - grade)
            elif finish_pos <= 5:
                prize = rng.uniform(50, 300)
            else:
                prize = 0

            rows.append({
                "race_key": race_key,
                "race_date": race_date.strftime("%Y-%m-%d"),
                "course_id": course_id,
                "distance": distance,
                "surface": surface,
                "track_condition": condition,
                "grade": grade,
                "race_class": grade,
                "field_size": field_size,
                "horse_key": f"H{h_idx:04d}",
                "finish_order": finish_pos,
                "waku": waku,
                "umaban": umaban,
                "sex": sex_val,
                "age": age_val,
                "weight_carried": round(weight_carried, 1),
                "body_weight": round(body_weight, 0),
                "weight_diff": round(weight_diff_val, 0),
                "last3f": round(last3f_time, 1),
                "corner3": corner3_pos,
                "corner4": corner4_pos,
                "win_odds": round(raw_odds, 1),
                "popularity": popularity,
                "jockey_code": f"J{j_idx:03d}",
                "trainer_code": f"T{t_idx:03d}",
                "prize_money": round(prize, 0),
            })

    df = pd.DataFrame(rows)
    logger.info("Generated base table with %d rows", len(df))

    # Now compute as-of features on this synthetic data
    col = {
        "race_key": "race_key",
        "horse_key": "horse_key",
        "race_date": "race_date",
        "finish_order": "finish_order",
        "distance": "distance",
        "track_type": "surface",
        "track_condition": "track_condition",
        "place": "course_id",
        "last3f": "last3f",
        "corner3": "corner3",
        "corner4": "corner4",
        "body_weight": "body_weight",
        "body_weight_diff": "weight_diff",
        "prize_money": "prize_money",
        "jockey_code": "jockey_code",
        "trainer_code": "trainer_code",
        "field_size": "field_size",
        "grade": "grade",
    }

    df = _compute_as_of_features(df, col)

    # Add targets
    df["target_win"] = (df["finish_order"] == 1).astype(int)
    df["target_in3"] = (df["finish_order"] <= 3).astype(int)

    # Add pedigree features (synthetic)
    sire_groups = rng.randint(1, 16, size=n_horses)  # 15 sire groups
    damsire_groups = rng.randint(1, 11, size=n_horses)  # 10 damsire groups

    def extract_horse_idx(hkey: str) -> int:
        return int(hkey[1:])

    df["sire_group"] = df["horse_key"].apply(lambda x: sire_groups[extract_horse_idx(x)])
    df["damsire_group"] = df["horse_key"].apply(lambda x: damsire_groups[extract_horse_idx(x)])
    df["sire_id"] = df["sire_group"]  # simplified
    df["damsire_id"] = df["damsire_group"]
    df["pedigree_hash"] = df["sire_group"] * 100 + df["damsire_group"]

    logger.info("Demo feature table complete. Shape: %s", df.shape)
    return df

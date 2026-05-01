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
    "track_type": ["TrackType", "TRACK_TYPE", "tracktype", "track_type",
                   "TrackCD", "SibaBabaCD", "SibaBaba"],
    "track_condition": ["TrackCondition", "TRACK_CONDITION", "trackcondition",
                        "track_condition", "BabaCD", "BabaSt", "DirtBabaCD"],
    "grade": ["Grade", "GRADE", "grade", "GradeCD", "JyuryoCD"],
    "race_class": ["RaceClass", "RACE_CLASS", "raceclass", "race_class", "ClassCD"],
    "field_size": ["FieldSize", "FIELD_SIZE", "fieldsize", "field_size", "TorokuTosu", "SyussoTosu"],
    # N_UMA_RACE columns
    "horse_key": ["HorseKey", "HORSE_KEY", "horsekey", "horse_key", "KettoNum", "UmaKey"],
    "finish_order": ["FinishOrder", "FINISH_ORDER", "finishorder", "finish_order",
                     "KakuteiJyuni", "ChakuJyuni", "Tyaku"],
    "time": ["Time", "TIME", "time", "RaceTime"],
    "last3f": ["Last3F", "LAST3F", "last3f", "HaronTimeL3", "L3F", "AgariSanten"],
    "passing_order": ["PassingOrder", "PASSING_ORDER", "passingorder", "passing_order",
                      "Corner1", "CornerJyuni"],
    "corner3": ["Corner3", "corner3", "CornerJyuni3"],
    "corner4": ["Corner4", "corner4", "CornerJyuni4"],
    "win_odds": ["WinOdds", "WIN_ODDS", "winodds", "win_odds", "Odds", "TansyoOdds"],
    "popularity": ["Popularity", "POPULARITY", "popularity", "Ninki", "NinkiJyuni"],
    "body_weight": ["BodyWeight", "BODY_WEIGHT", "bodyweight", "body_weight",
                    "BaTaijyu", "Bataiju", "ZogenFugo"],
    "body_weight_diff": ["BodyWeightDiff", "BODY_WEIGHT_DIFF", "bodyweightdiff",
                         "body_weight_diff", "BaTaijyuZougen", "BataijuZougen", "Zogen"],
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
    # Pedigree columns (joined from N_UMA by postprocess script)
    "sire_code": ["SireCode", "sire_code", "Ketto3InfoHansyokuNum1"],
    "damsire_code": ["DamsireCode", "damsire_code", "Ketto3InfoHansyokuNum5"],
    # Training features (pre-aggregated by postprocess script)
    "train_days_since_last": ["train_days_since_last"],
    "train_last_hanro_time": ["train_last_hanro_time"],
    "train_last_hanro_finish": ["train_last_hanro_finish"],
    "train_hanro_accel": ["train_hanro_accel"],
    "train_best_hanro_time_30d": ["train_best_hanro_time_30d"],
    "train_wood_avg_pace": ["train_wood_avg_pace"],
    "train_total_count_30d": ["train_total_count_30d"],
    "train_hanro_ratio": ["train_hanro_ratio"],
    # Place odds (joined by postprocess script)
    "fuku_odds_low": ["fuku_odds_low", "FukuOddsLow"],
    "fuku_odds_high": ["fuku_odds_high", "FukuOddsHigh"],
    "fuku_odds_range": ["fuku_odds_range"],
    # Payout data (for backtest, not training features)
    "tansho_payout": ["tansho_payout"],
    "fukusho_payout": ["fukusho_payout"],
}


# Canonical columns that must be numeric downstream (LightGBM, backtest,
# walk_forward). Raw EveryDB2 stores many of these as zero-padded strings
# (e.g. KakuteiJyuni -> "03"), so we coerce them before writing the cache.
NUMERIC_CANONICAL_COLUMNS: List[str] = [
    "distance", "finish_order", "time", "last3f",
    "corner3", "corner4", "passing_order",
    "win_odds", "popularity",
    "body_weight", "body_weight_diff",
    "weight_carried", "prize_money",
    "waku", "umaban", "sex", "age", "field_size",
    "grade", "race_class",
    "fuku_odds_low", "fuku_odds_high", "fuku_odds_range",
    "tansho_payout", "fukusho_payout",
]


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

def _resolve_date_column(
    cursor: sqlite3.Cursor, table: str
) -> Tuple[Optional[str], Optional[str]]:
    """Resolve the date column for the given table.

    Returns (mode, column_name) where mode is 'RaceDate' (YYYY-MM-DD),
    'Year' (YYYY fallback), or (None, None) if neither exists.
    """
    try:
        cursor.execute(f"PRAGMA table_info([{table}])")
        columns = {row[1] for row in cursor.fetchall()}
    except sqlite3.Error as e:
        logger.warning("PRAGMA failed for %s: %s", table, e)
        return None, None

    for cand in ["RaceDate", "RACE_DATE", "racedate", "race_date"]:
        if cand in columns:
            return "RaceDate", cand
    for cand in ["Year", "YEAR", "year"]:
        if cand in columns:
            return "Year", cand
    return None, None


def _get_max_race_date(
    cursor: sqlite3.Cursor, table: str, date_col: str, mode: str
) -> Optional[str]:
    """Return the maximum date in the table as a string.

    RaceDate mode → 'YYYY-MM-DD', Year mode → 'YYYY'. None on failure.
    """
    try:
        cursor.execute(f"SELECT MAX([{date_col}]) FROM [{table}]")
        row = cursor.fetchone()
    except sqlite3.Error as e:
        logger.warning("Failed to get MAX(%s) from %s: %s", date_col, table, e)
        return None
    if not row or row[0] is None:
        return None
    val = str(row[0])
    if mode == "Year":
        return val[:4]
    return val


def _compute_cutoff(max_date: str, mode: str, years: int) -> Optional[str]:
    """Subtract `years` from `max_date`. Returns string in same format as input."""
    try:
        if mode == "RaceDate":
            dt = datetime.strptime(max_date[:10], "%Y-%m-%d")
            return (dt - timedelta(days=years * 365)).strftime("%Y-%m-%d")
        if mode == "Year":
            return str(int(max_date) - years)
    except (ValueError, TypeError) as e:
        logger.warning("Failed to compute cutoff from max=%s mode=%s: %s", max_date, mode, e)
    return None


def _load_race_table(
    conn: sqlite3.Connection,
    cutoff: Optional[str] = None,
    date_col: Optional[str] = None,
) -> Optional[pd.DataFrame]:
    """Attempt to load the race master table, optionally filtered by date."""
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    logger.info("Available tables: %s", tables)

    race_table_candidates = ["N_RACE", "n_race", "RACE", "race"]
    for t in race_table_candidates:
        if t in tables:
            logger.info("Using race table: %s", t)
            if cutoff and date_col:
                logger.info("N_RACE filter: [%s] >= %s", date_col, cutoff)
                return pd.read_sql(
                    f"SELECT * FROM [{t}] WHERE [{date_col}] >= ?",
                    conn,
                    params=(cutoff,),
                )
            return pd.read_sql(f"SELECT * FROM [{t}]", conn)

    logger.warning("No race table found among: %s", tables)
    return None


def _load_uma_race_table(
    conn: sqlite3.Connection,
    cutoff: Optional[str] = None,
    date_col: Optional[str] = None,
    n_race_table: str = "N_RACE",
    race_key_col: str = "RaceKey",
) -> Optional[pd.DataFrame]:
    """Attempt to load the horse-race result table, filtered by RaceKey
    derived from the date cutoff on the race master table.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]

    uma_race_candidates = ["N_UMA_RACE", "n_uma_race", "UMA_RACE", "uma_race",
                           "HORSE_RACE", "horse_race"]
    for t in uma_race_candidates:
        if t in tables:
            logger.info("Using uma_race table: %s", t)
            if cutoff and date_col:
                cursor.execute(f"PRAGMA table_info([{t}])")
                uma_cols = {row[1] for row in cursor.fetchall()}
                cursor.execute(f"PRAGMA table_info([{n_race_table}])")
                race_cols = {row[1] for row in cursor.fetchall()}
                if race_key_col in uma_cols and race_key_col in race_cols:
                    logger.info(
                        "N_UMA_RACE filter: %s IN (SELECT %s FROM %s WHERE [%s] >= %s)",
                        race_key_col, race_key_col, n_race_table, date_col, cutoff,
                    )
                    return pd.read_sql(
                        f"SELECT * FROM [{t}] WHERE [{race_key_col}] IN "
                        f"(SELECT [{race_key_col}] FROM [{n_race_table}] "
                        f"WHERE [{date_col}] >= ?)",
                        conn,
                        params=(cutoff,),
                    )
                logger.warning(
                    "%s column missing in N_RACE or N_UMA_RACE; loading full %s",
                    race_key_col, t,
                )
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

    # Sort by date for chronological processing.
    # mergesort + (date, race_key) tiebreak は run-to-run / 旧 vs 新実装の
    # 同日同馬の処理順を確定的にするため必須。as-of 集計の冪等性を保証する。
    sort_keys = [c_race_date]
    if c_race_key:
        sort_keys.append(c_race_key)
    df = df.sort_values(sort_keys, kind="mergesort").reset_index(drop=True)

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

    # Pre-compute numeric grade once (shared by class_change / max_grade /
    # grade_n_starts / grade_win_rate). Originally these blocks each ran
    # _safe_float on c_grade, costing the same parse multiple times.
    if c_grade:
        df["_grade_num"] = _safe_float(df[c_grade])

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

    _compute_horse_stats_legacy(df, col)

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

    if c_grade:
        _compute_class_change_legacy(df, col)

    if "horse_total_prize" in df.columns and c_race_key:
        logger.info("Computing prize rank within field...")
        for race_id, race_df in df.groupby(c_race_key):
            prizes = race_df["horse_total_prize"].dropna()
            if len(prizes) > 0:
                ranks = prizes.rank(ascending=False, method="min")
                df.loc[ranks.index, "horse_prize_rank_in_field"] = ranks

    if "_last3f" in df.columns and c_race_key:
        _compute_last3f_rank_legacy(df, col)

    # Clean up temporary columns
    temp_cols = [c for c in df.columns if c.startswith("_")]
    df = df.drop(columns=temp_cols, errors="ignore")

    logger.info("Feature computation complete. Shape: %s", df.shape)
    return df


def _compute_horse_stats_legacy(df: pd.DataFrame, col: Dict[str, Optional[str]]) -> None:
    """Original per-horse / per-row as-of feature computation (slow, O(N²) on tail).

    Kept verbatim from the pre-vectorisation implementation as a reference for
    equivalence tests against the vectorised path. Modifies df in place.
    """
    c_race_key = col.get("race_key")  # noqa: F841 — kept for parity with new path
    c_horse_key = col.get("horse_key")
    c_distance = col.get("distance")
    c_surface = col.get("track_type")
    c_place = col.get("place")
    c_finish = col.get("finish_order")
    c_body_weight = col.get("body_weight")
    c_body_weight_diff = col.get("body_weight_diff")
    c_field_size = col.get("field_size")
    c_grade = col.get("grade")

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

            if c_distance and "_dist_cat" in df.columns:
                current_dist_cat = df.at[i, "_dist_cat"]
                if current_dist_cat is not None:
                    dist_past = past[past["_dist_cat"] == current_dist_cat]
                    if len(dist_past) > 0:
                        df.at[i, "horse_dist_win_rate"] = dist_past["_is_win"].mean()
                        df.at[i, "horse_dist_in3_rate"] = dist_past["_is_in3"].mean()

            if c_surface:
                current_surface = df.at[i, c_surface]
                surface_past = past[past[c_surface] == current_surface]
                if len(surface_past) > 0:
                    df.at[i, "horse_surface_win_rate"] = surface_past["_is_win"].mean()
                    df.at[i, "horse_surface_in3_rate"] = surface_past["_is_in3"].mean()

            if c_place:
                current_place = df.at[i, c_place]
                course_past = past[past[c_place] == current_place]
                if len(course_past) > 0:
                    df.at[i, "horse_course_win_rate"] = course_past["_is_win"].mean()

            recent3 = past.tail(3)
            recent5 = past.tail(5)
            df.at[i, "horse_recent3_avg"] = recent3["_finish"].mean()
            df.at[i, "horse_recent5_avg"] = recent5["_finish"].mean()
            df.at[i, "horse_recent3_win_rate"] = recent3["_is_win"].mean()
            df.at[i, "horse_last_finish"] = past.iloc[-1]["_finish"]

            if "_race_date_dt" in df.columns:
                current_date = df.at[i, "_race_date_dt"]
                last_date = past.iloc[-1]["_race_date_dt"]
                if pd.notna(current_date) and pd.notna(last_date):
                    df.at[i, "horse_days_since_last"] = (current_date - last_date).days

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
                    x = np.arange(len(last3_weights), dtype=float)
                    y = last3_weights.values.astype(float)
                    if np.std(x) > 0:
                        slope = np.polyfit(x, y, 1)[0]
                        df.at[i, "weight_trend_3"] = slope

            if c_body_weight_diff and "_body_weight_diff" in df.columns:
                bwd = df.at[i, "_body_weight_diff"]
                if pd.notna(bwd):
                    df.at[i, "abs_weight_diff"] = abs(bwd)

            if "_corner3" in df.columns:
                past_c3 = past["_corner3"].dropna()
                if len(past_c3) > 0:
                    df.at[i, "horse_avg_corner3"] = past_c3.mean()

            if "_corner4" in df.columns:
                past_c4 = past["_corner4"].dropna()
                if len(past_c4) > 0:
                    df.at[i, "horse_avg_corner4"] = past_c4.mean()
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

            if "_corner4" in df.columns:
                past_both = past[["_corner4", "_finish"]].dropna()
                if len(past_both) > 0:
                    changes = past_both["_corner4"] - past_both["_finish"]
                    df.at[i, "horse_avg_position_change"] = changes.mean()

            if "_prize" in df.columns:
                past_prize = past["_prize"].dropna()
                if len(past_prize) > 0:
                    df.at[i, "horse_total_prize"] = past_prize.sum()
                    df.at[i, "horse_avg_prize"] = past_prize.mean()
                    df.at[i, "horse_earnings_per_start"] = past_prize.sum() / n_starts

            if c_grade:
                past_grade = past[past[c_grade].notna()]
                grade_numeric = _safe_float(past_grade[c_grade])
                grade_valid = grade_numeric.dropna()
                if len(grade_valid) > 0:
                    df.at[i, "horse_max_grade"] = grade_valid.min()
                graded = past_grade[grade_numeric <= 3]
                df.at[i, "horse_grade_n_starts"] = len(graded)
                if len(graded) > 0:
                    graded_finish = _safe_float(graded[c_finish])
                    df.at[i, "horse_grade_win_rate"] = (graded_finish == 1).mean()


def _compute_class_change_legacy(df: pd.DataFrame, col: Dict[str, Optional[str]]) -> None:
    """Original class_change implementation. Modifies df in place."""
    c_horse_key = col.get("horse_key")
    c_grade = col.get("grade")
    if not c_grade:
        return
    for horse_id, horse_df in df.groupby(c_horse_key):
        indices = horse_df.index.tolist()
        for pos, i in enumerate(indices):
            if pos == 0:
                continue
            prev_grade = _safe_float(pd.Series([horse_df.iloc[pos - 1][c_grade]])).iloc[0]
            curr_grade = _safe_float(pd.Series([df.at[i, c_grade]])).iloc[0]
            if pd.notna(prev_grade) and pd.notna(curr_grade):
                df.at[i, "horse_class_change"] = prev_grade - curr_grade


def _compute_last3f_rank_legacy(df: pd.DataFrame, col: Dict[str, Optional[str]]) -> None:
    """Original per-race rank → per-horse cumulative average for last3f.

    Modifies df in place. Adds a temp column `_last3f_rank` (cleaned up by
    the orchestrator's temp-column drop step).
    """
    c_horse_key = col.get("horse_key")
    c_race_key = col.get("race_key")
    if not c_race_key or "_last3f" not in df.columns:
        return
    logger.info("Computing last3f rank within each race...")
    df["_last3f_rank"] = np.nan
    for race_id, race_df in df.groupby(c_race_key):
        l3 = race_df["_last3f"].dropna()
        if len(l3) > 0:
            ranks = l3.rank(ascending=True, method="min")
            df.loc[ranks.index, "_last3f_rank"] = ranks

    for horse_id, horse_df in df.groupby(c_horse_key):
        indices = horse_df.index.tolist()
        for pos, i in enumerate(indices):
            past = horse_df.iloc[:pos]
            if len(past) > 0:
                past_ranks = past["_last3f_rank"].dropna()
                if len(past_ranks) > 0:
                    df.at[i, "horse_last3f_rank_avg"] = past_ranks.mean()


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

    Vectorized per agent using cumulative sums on groupby output. For each
    agent the per-row "past" aggregates (mean win rate over prior races,
    per-distance/surface/course/horse breakdowns, recent-20 window) are
    derived from cumulative sums that exclude the current row, which is
    O(n) per agent vs. O(n²) for the earlier scalar implementation.
    """
    agent_groups = df.groupby(agent_col, sort=False)
    total_agents = len(agent_groups)
    log_interval = max(1, total_agents // 20)

    def _past_ratio(is_flag: pd.Series, ones: pd.Series, grp: pd.Series):
        """Past rate of is_flag within each group, excluding current row."""
        gw = is_flag.groupby(grp, sort=False).cumsum() - is_flag
        gn = ones.groupby(grp, sort=False).cumsum() - 1.0
        with np.errstate(invalid="ignore", divide="ignore"):
            return np.where(gn > 0, gw / gn, np.nan), gn

    for idx, (_, agent_df) in enumerate(agent_groups):
        if idx % log_interval == 0:
            logger.info("  %s progress: %d / %d", prefix, idx, total_agents)

        n = len(agent_df)
        if n <= 1:
            continue

        finish = _safe_float(agent_df[finish_col])
        is_win = (finish == 1).astype(float)
        is_in3 = (finish <= 3).astype(float)
        ones = pd.Series(1.0, index=agent_df.index)

        # Agent-wide as-of (cumulative over prior races, excluding current)
        past_n = ones.cumsum() - 1.0
        past_win = is_win.cumsum() - is_win
        past_in3 = is_in3.cumsum() - is_in3
        with np.errstate(invalid="ignore", divide="ignore"):
            win_rate = np.where(past_n > 0, past_win / past_n, np.nan)
            in3_rate = np.where(past_n > 0, past_in3 / past_n, np.nan)
        df.loc[agent_df.index, f"{prefix}_win_rate"] = win_rate
        df.loc[agent_df.index, f"{prefix}_in3_rate"] = in3_rate

        # Recent 20: rolling mean of is_win over up to 20 prior races
        r20 = is_win.shift(1).rolling(20, min_periods=1).mean()
        df.loc[agent_df.index, f"{prefix}_recent20_win_rate"] = r20.values

        # Distance-specific win rate (per distance category within agent)
        if c_distance_cat and c_distance_cat in agent_df.columns:
            rate, _ = _past_ratio(is_win, ones, agent_df[c_distance_cat])
            df.loc[agent_df.index, f"{prefix}_dist_win_rate"] = rate

        # Surface-specific win rate
        if c_surface and c_surface in agent_df.columns:
            rate, _ = _past_ratio(is_win, ones, agent_df[c_surface])
            df.loc[agent_df.index, f"{prefix}_surface_win_rate"] = rate

        # Course-specific win rate (per track)
        if c_place and c_place in agent_df.columns:
            rate, _ = _past_ratio(is_win, ones, agent_df[c_place])
            df.loc[agent_df.index, f"{prefix}_course_win_rate"] = rate

        # Horse-combo stats (per agent × horse)
        if c_horse_key and c_horse_key in agent_df.columns:
            rate, combo_n = _past_ratio(is_win, ones, agent_df[c_horse_key])
            df.loc[agent_df.index, f"{prefix}_horse_combo_n"] = combo_n.values
            df.loc[agent_df.index, f"{prefix}_horse_combo_win_rate"] = rate


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_feature_table(
    db_path: str,
    output_path: Optional[str] = None,
    output_years: Optional[int] = None,
    history_buffer_years: int = 5,
) -> pd.DataFrame:
    """Build the feature table from JRA-VAN EveryDB2 SQLite database.

    Args:
        db_path: Path to the EveryDB2 SQLite file.
        output_path: Optional path to save the feature table (parquet or CSV).
        output_years: If set, the final saved feature table is trimmed to the
            last N years relative to MAX(RaceDate). The SQL load still reads
            (output_years + history_buffer_years) years so as-of statistics
            have sufficient history. None = load and save everything.
        history_buffer_years: Extra years loaded beyond output_years, used as
            as-of history. Ignored when output_years is None.

    Returns:
        DataFrame with computed features.
    """
    logger.info(
        "Building feature table from: %s (output_years=%s, history_buffer=%d)",
        db_path, output_years, history_buffer_years,
    )

    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database not found: {db_path}")

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()

        # Determine the date column and cutoffs
        date_mode, date_col = _resolve_date_column(cursor, "N_RACE")
        cutoff_load: Optional[str] = None
        cutoff_output: Optional[str] = None
        if output_years is not None:
            if date_mode and date_col:
                max_date = _get_max_race_date(cursor, "N_RACE", date_col, date_mode)
                if max_date:
                    cutoff_load = _compute_cutoff(
                        max_date, date_mode, output_years + history_buffer_years
                    )
                    cutoff_output = _compute_cutoff(max_date, date_mode, output_years)
                    logger.info(
                        "Date filter mode=%s col=%s max=%s cutoff_load=%s cutoff_output=%s",
                        date_mode, date_col, max_date, cutoff_load, cutoff_output,
                    )
                else:
                    logger.warning(
                        "MAX(%s) returned None; loading all data", date_col,
                    )
            else:
                logger.warning(
                    "No date column resolved on N_RACE; loading all data "
                    "(output_years=%d ignored)",
                    output_years,
                )

        # Load tables (filtered if cutoff_load is set)
        race_df = _load_race_table(conn, cutoff_load, date_col)
        uma_race_df = _load_uma_race_table(conn, cutoff_load, date_col)

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

        # Coerce canonical numeric columns to numbers. EveryDB2 often stores
        # these as zero-padded strings ("03"), which breaks downstream
        # consumers like walk_forward.finish_to_relevance (clip/comparison).
        for c in NUMERIC_CANONICAL_COLUMNS:
            if c in df.columns and df[c].dtype == object:
                df[c] = pd.to_numeric(df[c], errors="coerce")

        # Trim the output to the last `output_years` while as-of features
        # were computed using the full loaded history.
        if cutoff_output and "race_date" in df.columns:
            before = len(df)
            dt_series = pd.to_datetime(df["race_date"], errors="coerce")
            cutoff_ts = pd.to_datetime(cutoff_output, errors="coerce")
            if pd.notna(cutoff_ts):
                df = df[dt_series >= cutoff_ts].copy()
                logger.info(
                    "Output trim: %d -> %d rows (cutoff=%s)",
                    before, len(df), cutoff_output,
                )
            else:
                logger.warning(
                    "Could not parse cutoff_output=%s; keeping all rows", cutoff_output,
                )

        if output_path:
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            # Prefer parquet if path ends with .parquet, otherwise CSV
            if output_path.endswith(".parquet"):
                df.to_parquet(output_path, index=False, engine="pyarrow")
            else:
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

        # Pre-race assignments: gate numbers are random, not correlated with outcome
        gate_order = rng.permutation(field_size) + 1  # 1-indexed random gate assignment

        # Market estimate: ability + very large noise (market is highly imperfect)
        market_estimates = [(ability, idx) for idx, (h_idx, j_idx, t_idx, ability) in enumerate(abilities)]
        noisy_market = [(est + rng.normal(0, 3.0), idx) for est, idx in market_estimates]
        noisy_market.sort(key=lambda x: -x[0])
        popularity_map = {}
        for rank, (_, idx) in enumerate(noisy_market, 1):
            popularity_map[idx] = rank

        for finish_pos, (h_idx, j_idx, t_idx, ability) in enumerate(abilities, 1):
            waku = min(8, (gate_order[finish_pos - 1] - 1) // 2 + 1)
            umaban = int(gate_order[finish_pos - 1])
            sex_val = rng.choice([1, 2, 3], p=[0.55, 0.40, 0.05])
            age_val = rng.choice([2, 3, 4, 5, 6, 7], p=[0.10, 0.25, 0.25, 0.20, 0.12, 0.08])
            weight_carried = 55.0 + rng.normal(0, 2)
            body_weight = 460 + rng.normal(0, 30)
            weight_diff_val = rng.normal(0, 4)
            # last3f: mostly noise, weak relationship with finish position
            last3f_time = 33.0 + rng.normal(0, 2.0) + finish_pos * 0.03
            # Corner positions: mostly random with slight trend
            corner4_pos = max(1, min(field_size, int(rng.uniform(1, field_size + 1))))
            corner3_pos = max(1, min(field_size, int(rng.uniform(1, field_size + 1))))

            # Win odds: market-implied probability + heavy noise (not directly from ability)
            market_pop = popularity_map[finish_pos - 1]
            implied_prob = max(0.02, 1.0 / (market_pop + rng.exponential(2)))
            raw_odds = max(1.1, (1.0 / implied_prob) * (0.8 + rng.uniform(0, 0.4)))
            popularity = market_pop

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

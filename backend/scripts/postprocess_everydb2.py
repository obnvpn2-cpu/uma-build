"""Post-process EveryDB2 SQLite output for UmaBuild.

EveryDB2 exports data into SQLite with composite keys and separate tables.
This script:
  1. Synthesises a single RaceKey column from composite key parts
  2. Synthesises a RaceDate column for chronological sorting
  3. Joins pedigree info (sire/damsire) from N_UMA into N_UMA_RACE
  4. Creates indexes for performance
  5. Aggregates training data (N_HANRO/N_WOOD_CHIP) into N_UMA_RACE
  6. Joins payout data (N_HARAI) into N_UMA_RACE
  7. Joins place odds (N_ODDS_TANPUKU) into N_UMA_RACE
  8. Optionally builds feature_table_cache.csv

Usage:
    cd uma-build/backend
    python scripts/postprocess_everydb2.py [--db data/jravan.db] [--build-cache]
"""

import argparse
import logging
import os
import sqlite3
import sys
from datetime import timedelta

import numpy as np
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# Composite key parts that form RaceKey
RACE_KEY_PARTS = ["Year", "MonthDay", "JyoCD", "Kaiji", "Nichiji", "RaceNum"]


def _table_exists(cursor: sqlite3.Cursor, table_name: str) -> bool:
    cursor.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    )
    return cursor.fetchone()[0] > 0


def _column_exists(cursor: sqlite3.Cursor, table_name: str, column_name: str) -> bool:
    cursor.execute(f"PRAGMA table_info([{table_name}])")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns


def _has_all_key_parts(cursor: sqlite3.Cursor, table_name: str) -> bool:
    cursor.execute(f"PRAGMA table_info([{table_name}])")
    columns = {row[1] for row in cursor.fetchall()}
    missing = [p for p in RACE_KEY_PARTS if p not in columns]
    if missing:
        logger.warning("Table %s missing key parts: %s", table_name, missing)
        return False
    return True


def step1_synthesise_race_key(cursor: sqlite3.Cursor) -> None:
    """Add RaceKey column to N_RACE, N_UMA_RACE, N_HARAI, N_ODDS_TANPUKU."""
    concat_expr = " || ".join(RACE_KEY_PARTS)

    for table in ["N_RACE", "N_UMA_RACE", "N_HARAI", "N_ODDS_TANPUKU"]:
        if not _table_exists(cursor, table):
            logger.warning("Table %s not found, skipping RaceKey synthesis", table)
            continue

        if not _has_all_key_parts(cursor, table):
            logger.error("Cannot synthesise RaceKey for %s — missing key parts", table)
            continue

        if _column_exists(cursor, table, "RaceKey"):
            logger.info("RaceKey already exists in %s, updating values", table)
            cursor.execute(f"UPDATE [{table}] SET RaceKey = {concat_expr}")
        else:
            logger.info("Adding RaceKey to %s", table)
            cursor.execute(f"ALTER TABLE [{table}] ADD COLUMN RaceKey TEXT")
            cursor.execute(f"UPDATE [{table}] SET RaceKey = {concat_expr}")

        count = cursor.execute(f"SELECT COUNT(*) FROM [{table}] WHERE RaceKey IS NOT NULL").fetchone()[0]
        logger.info("  %s: %d rows with RaceKey", table, count)


def step2_synthesise_race_date(cursor: sqlite3.Cursor) -> None:
    """Add RaceDate column (YYYY-MM-DD) to N_RACE."""
    table = "N_RACE"
    if not _table_exists(cursor, table):
        logger.warning("Table %s not found, skipping RaceDate synthesis", table)
        return

    # RaceDate = Year(4) + '-' + MonthDay(1-2) + '-' + MonthDay(3-4)
    date_expr = "substr(Year, 1, 4) || '-' || substr(MonthDay, 1, 2) || '-' || substr(MonthDay, 3, 2)"

    if _column_exists(cursor, table, "RaceDate"):
        logger.info("RaceDate already exists in %s, updating values", table)
        cursor.execute(f"UPDATE [{table}] SET RaceDate = {date_expr}")
    else:
        logger.info("Adding RaceDate to %s", table)
        cursor.execute(f"ALTER TABLE [{table}] ADD COLUMN RaceDate TEXT")
        cursor.execute(f"UPDATE [{table}] SET RaceDate = {date_expr}")

    sample = cursor.execute(f"SELECT RaceDate FROM [{table}] WHERE RaceDate IS NOT NULL LIMIT 3").fetchall()
    logger.info("  Sample RaceDate values: %s", [r[0] for r in sample])


def step3_join_pedigree(cursor: sqlite3.Cursor) -> None:
    """Join sire/damsire codes from N_UMA into N_UMA_RACE."""
    if not _table_exists(cursor, "N_UMA"):
        logger.warning("N_UMA table not found, skipping pedigree join")
        return

    if not _table_exists(cursor, "N_UMA_RACE"):
        logger.warning("N_UMA_RACE table not found, skipping pedigree join")
        return

    # Check N_UMA has the required columns
    cursor.execute("PRAGMA table_info([N_UMA])")
    uma_columns = {row[1] for row in cursor.fetchall()}

    sire_col = None
    damsire_col = None

    # Ketto3InfoHansyokuNum1 = father (sire)
    # Ketto3InfoHansyokuNum5 = maternal grandfather (damsire)
    for candidate in ["Ketto3InfoHansyokuNum1", "HansyokuNum1", "SireCode"]:
        if candidate in uma_columns:
            sire_col = candidate
            break

    for candidate in ["Ketto3InfoHansyokuNum5", "HansyokuNum5", "DamsireCode"]:
        if candidate in uma_columns:
            damsire_col = candidate
            break

    if not sire_col and not damsire_col:
        logger.warning("No pedigree columns found in N_UMA. Available: %s",
                       sorted(uma_columns)[:20])
        return

    # Check KettoNum exists in both tables
    if not _column_exists(cursor, "N_UMA_RACE", "KettoNum"):
        logger.warning("KettoNum not found in N_UMA_RACE, skipping pedigree join")
        return

    if not _column_exists(cursor, "N_UMA", "KettoNum"):
        logger.warning("KettoNum not found in N_UMA, skipping pedigree join")
        return

    if sire_col:
        if not _column_exists(cursor, "N_UMA_RACE", "SireCode"):
            cursor.execute("ALTER TABLE [N_UMA_RACE] ADD COLUMN SireCode TEXT")
        cursor.execute(f"""
            UPDATE [N_UMA_RACE] SET SireCode = (
                SELECT [{sire_col}] FROM [N_UMA]
                WHERE [N_UMA].KettoNum = [N_UMA_RACE].KettoNum
            )
        """)
        filled = cursor.execute(
            "SELECT COUNT(*) FROM [N_UMA_RACE] WHERE SireCode IS NOT NULL AND SireCode != ''"
        ).fetchone()[0]
        logger.info("  SireCode filled: %d rows (from N_UMA.%s)", filled, sire_col)

    if damsire_col:
        if not _column_exists(cursor, "N_UMA_RACE", "DamsireCode"):
            cursor.execute("ALTER TABLE [N_UMA_RACE] ADD COLUMN DamsireCode TEXT")
        cursor.execute(f"""
            UPDATE [N_UMA_RACE] SET DamsireCode = (
                SELECT [{damsire_col}] FROM [N_UMA]
                WHERE [N_UMA].KettoNum = [N_UMA_RACE].KettoNum
            )
        """)
        filled = cursor.execute(
            "SELECT COUNT(*) FROM [N_UMA_RACE] WHERE DamsireCode IS NOT NULL AND DamsireCode != ''"
        ).fetchone()[0]
        logger.info("  DamsireCode filled: %d rows (from N_UMA.%s)", filled, damsire_col)


def step4_create_indexes(cursor: sqlite3.Cursor) -> None:
    """Create indexes for query performance."""
    indexes = [
        ("idx_race_racekey", "N_RACE", "RaceKey"),
        ("idx_race_racedate", "N_RACE", "RaceDate"),
        ("idx_umarace_racekey", "N_UMA_RACE", "RaceKey"),
        ("idx_umarace_kettonum", "N_UMA_RACE", "KettoNum"),
        ("idx_hanro_kettonum", "N_HANRO", "KettoNum"),
        ("idx_hanro_date", "N_HANRO", "ChokyoDate"),
        ("idx_woodchip_kettonum", "N_WOOD_CHIP", "KettoNum"),
        ("idx_harai_racekey", "N_HARAI", "RaceKey"),
    ]

    for idx_name, table, column in indexes:
        if not _table_exists(cursor, table):
            continue
        if not _column_exists(cursor, table, column):
            continue
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS [{idx_name}] ON [{table}]([{column}])"
        )
        logger.info("  Index %s on %s(%s) — OK", idx_name, table, column)

    # Composite index for N_ODDS_TANPUKU
    if (_table_exists(cursor, "N_ODDS_TANPUKU")
            and _column_exists(cursor, "N_ODDS_TANPUKU", "RaceKey")
            and _column_exists(cursor, "N_ODDS_TANPUKU", "Umaban")):
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS [idx_odds_tanpuku_rk_ub] "
            "ON [N_ODDS_TANPUKU]([RaceKey], [Umaban])"
        )
        logger.info("  Index idx_odds_tanpuku_rk_ub on N_ODDS_TANPUKU(RaceKey, Umaban) — OK")


def step5_training_aggregate(conn: sqlite3.Connection) -> None:
    """Aggregate training data (N_HANRO / N_WOOD_CHIP) into N_UMA_RACE.

    Adds 8 training feature columns by matching each horse's most recent
    training sessions before each race using merge_asof.
    """
    cursor = conn.cursor()

    if not _table_exists(cursor, "N_UMA_RACE"):
        logger.warning("N_UMA_RACE not found, skipping training aggregate")
        return

    has_hanro = _table_exists(cursor, "N_HANRO")
    has_wood = _table_exists(cursor, "N_WOOD_CHIP")

    if not has_hanro and not has_wood:
        logger.warning("No training tables (N_HANRO / N_WOOD_CHIP) found, skipping")
        return

    # Load N_UMA_RACE key columns + RaceDate from N_RACE
    logger.info("Loading N_UMA_RACE for training merge...")
    uma = pd.read_sql(
        "SELECT rowid, KettoNum, RaceKey FROM N_UMA_RACE WHERE KettoNum IS NOT NULL",
        conn,
    )
    # Get RaceDate from N_RACE
    race_dates = pd.read_sql("SELECT RaceKey, RaceDate FROM N_RACE WHERE RaceDate IS NOT NULL", conn)
    uma = uma.merge(race_dates, on="RaceKey", how="left")
    uma["RaceDate"] = pd.to_datetime(uma["RaceDate"], errors="coerce")
    uma = uma.dropna(subset=["RaceDate"]).sort_values(["KettoNum", "RaceDate"]).reset_index(drop=True)
    logger.info("  N_UMA_RACE rows with valid date: %d", len(uma))

    # --- Hanro (坂路) ---
    hanro_df = None
    if has_hanro:
        logger.info("Loading N_HANRO...")
        hanro_cols = ["KettoNum", "ChokyoDate", "HaronTime4", "LapTime1"]
        # Check which columns exist
        cursor.execute("PRAGMA table_info([N_HANRO])")
        hanro_available = {row[1] for row in cursor.fetchall()}
        hanro_cols = [c for c in hanro_cols if c in hanro_available]
        if "KettoNum" in hanro_available and "ChokyoDate" in hanro_available:
            hanro_df = pd.read_sql(
                f"SELECT {', '.join(hanro_cols)} FROM N_HANRO WHERE KettoNum IS NOT NULL AND ChokyoDate IS NOT NULL",
                conn,
            )
            hanro_df["ChokyoDate"] = pd.to_datetime(hanro_df["ChokyoDate"], format="%Y%m%d", errors="coerce")
            hanro_df = hanro_df.dropna(subset=["ChokyoDate"])
            for c in ["HaronTime4", "LapTime1"]:
                if c in hanro_df.columns:
                    hanro_df[c] = pd.to_numeric(hanro_df[c], errors="coerce")
            hanro_df = hanro_df.sort_values(["KettoNum", "ChokyoDate"]).reset_index(drop=True)
            logger.info("  N_HANRO loaded: %d rows", len(hanro_df))
        else:
            logger.warning("  N_HANRO missing KettoNum or ChokyoDate columns")

    # --- Wood/Chip (ウッドチップ) ---
    wood_df = None
    if has_wood:
        logger.info("Loading N_WOOD_CHIP...")
        cursor.execute("PRAGMA table_info([N_WOOD_CHIP])")
        wood_available = {row[1] for row in cursor.fetchall()}
        # HaronTime columns: HaronTime1..HaronTime10 (variable distance)
        haron_cols = [f"HaronTime{i}" for i in range(1, 11) if f"HaronTime{i}" in wood_available]
        base_cols = ["KettoNum", "ChokyoDate"]
        if "KettoNum" in wood_available and "ChokyoDate" in wood_available:
            wood_cols = base_cols + haron_cols
            wood_df = pd.read_sql(
                f"SELECT {', '.join(wood_cols)} FROM N_WOOD_CHIP WHERE KettoNum IS NOT NULL AND ChokyoDate IS NOT NULL",
                conn,
            )
            wood_df["ChokyoDate"] = pd.to_datetime(wood_df["ChokyoDate"], format="%Y%m%d", errors="coerce")
            wood_df = wood_df.dropna(subset=["ChokyoDate"])
            for c in haron_cols:
                wood_df[c] = pd.to_numeric(wood_df[c], errors="coerce")
            # Compute 1F average pace: total time / number of furlongs used
            # Find the last non-null HaronTime column per row to determine distance
            if haron_cols:
                haron_data = wood_df[haron_cols]
                # Count non-null furlongs per row
                wood_df["_n_furlongs"] = haron_data.notna().sum(axis=1)
                wood_df["_total_time"] = haron_data.sum(axis=1, skipna=True)
                wood_df["wood_avg_pace"] = wood_df["_total_time"] / wood_df["_n_furlongs"].replace(0, np.nan)
                wood_df = wood_df[["KettoNum", "ChokyoDate", "wood_avg_pace"]].copy()
            else:
                wood_df["wood_avg_pace"] = np.nan
                wood_df = wood_df[["KettoNum", "ChokyoDate", "wood_avg_pace"]].copy()
            wood_df = wood_df.sort_values(["KettoNum", "ChokyoDate"]).reset_index(drop=True)
            logger.info("  N_WOOD_CHIP loaded: %d rows", len(wood_df))
        else:
            logger.warning("  N_WOOD_CHIP missing KettoNum or ChokyoDate columns")

    # --- Merge training data per horse per race ---
    logger.info("Computing training features per horse per race...")

    # Pre-allocate columns
    new_cols = [
        "train_days_since_last", "train_last_hanro_time", "train_last_hanro_finish",
        "train_hanro_accel", "train_best_hanro_time_30d", "train_wood_avg_pace",
        "train_total_count_30d", "train_hanro_ratio",
    ]
    for c in new_cols:
        uma[c] = np.nan

    # Process horse-by-horse using merge_asof for efficiency
    horse_groups = uma.groupby("KettoNum")
    total = len(horse_groups)
    log_interval = max(1, total // 20)

    for idx, (ketto, group) in enumerate(horse_groups):
        if idx % log_interval == 0:
            logger.info("  Training merge progress: %d / %d (%.0f%%)", idx, total, 100.0 * idx / total)

        race_dates_list = group["RaceDate"].values
        row_indices = group.index.values

        # Get hanro records for this horse
        h_records = None
        if hanro_df is not None:
            h_records = hanro_df[hanro_df["KettoNum"] == ketto].copy()
            if len(h_records) == 0:
                h_records = None

        # Get wood records for this horse
        w_records = None
        if wood_df is not None:
            w_records = wood_df[wood_df["KettoNum"] == ketto].copy()
            if len(w_records) == 0:
                w_records = None

        if h_records is None and w_records is None:
            continue

        for ri, rd in zip(row_indices, race_dates_list):
            rd_ts = pd.Timestamp(rd)
            cutoff_30d = rd_ts - pd.Timedelta(days=30)

            last_train_date = pd.NaT

            # Hanro features
            if h_records is not None:
                before = h_records[h_records["ChokyoDate"] < rd_ts]
                if len(before) > 0:
                    latest = before.iloc[-1]
                    last_train_date = latest["ChokyoDate"]

                    if "HaronTime4" in before.columns and pd.notna(latest.get("HaronTime4")):
                        uma.at[ri, "train_last_hanro_time"] = latest["HaronTime4"]
                    if "LapTime1" in before.columns and pd.notna(latest.get("LapTime1")):
                        uma.at[ri, "train_last_hanro_finish"] = latest["LapTime1"]
                        # Acceleration rate
                        ht4 = latest.get("HaronTime4")
                        if pd.notna(ht4) and ht4 > 0:
                            avg_1f = ht4 / 4.0
                            if avg_1f > 0:
                                uma.at[ri, "train_hanro_accel"] = latest["LapTime1"] / avg_1f

                    # 30-day best and count
                    in_30d = before[before["ChokyoDate"] >= cutoff_30d]
                    hanro_30d_count = len(in_30d)
                    if hanro_30d_count > 0 and "HaronTime4" in in_30d.columns:
                        best = in_30d["HaronTime4"].dropna().min()
                        if pd.notna(best):
                            uma.at[ri, "train_best_hanro_time_30d"] = best
                else:
                    hanro_30d_count = 0
            else:
                hanro_30d_count = 0

            # Wood features
            if w_records is not None:
                w_before = w_records[w_records["ChokyoDate"] < rd_ts]
                if len(w_before) > 0:
                    w_latest = w_before.iloc[-1]
                    if pd.isna(last_train_date) or w_latest["ChokyoDate"] > last_train_date:
                        last_train_date = w_latest["ChokyoDate"]
                    if pd.notna(w_latest.get("wood_avg_pace")):
                        uma.at[ri, "train_wood_avg_pace"] = w_latest["wood_avg_pace"]

                    w_in_30d = w_before[w_before["ChokyoDate"] >= cutoff_30d]
                    wood_30d_count = len(w_in_30d)
                else:
                    wood_30d_count = 0
            else:
                wood_30d_count = 0

            # Combined counts
            total_30d = hanro_30d_count + wood_30d_count
            if total_30d > 0:
                uma.at[ri, "train_total_count_30d"] = total_30d
                uma.at[ri, "train_hanro_ratio"] = hanro_30d_count / total_30d

            # Days since last training
            if pd.notna(last_train_date):
                uma.at[ri, "train_days_since_last"] = (rd_ts - last_train_date).days

    # Write back to DB
    logger.info("Writing training features back to N_UMA_RACE...")
    for col_name in new_cols:
        if not _column_exists(cursor, "N_UMA_RACE", col_name):
            cursor.execute(f"ALTER TABLE [N_UMA_RACE] ADD COLUMN [{col_name}] REAL")

    # Batch update using rowid
    for col_name in new_cols:
        valid = uma[uma[col_name].notna()][["rowid", col_name]]
        if len(valid) == 0:
            continue
        cursor.executemany(
            f"UPDATE [N_UMA_RACE] SET [{col_name}] = ? WHERE rowid = ?",
            list(zip(valid[col_name].values, valid["rowid"].values)),
        )
        logger.info("  %s: updated %d rows", col_name, len(valid))

    filled = cursor.execute(
        "SELECT COUNT(*) FROM N_UMA_RACE WHERE train_last_hanro_finish IS NOT NULL"
    ).fetchone()[0]
    total_rows = cursor.execute("SELECT COUNT(*) FROM N_UMA_RACE").fetchone()[0]
    logger.info("  Training coverage: %d / %d (%.1f%%)", filled, total_rows,
                100.0 * filled / total_rows if total_rows > 0 else 0)


def step6_join_payout(conn: sqlite3.Connection) -> None:
    """Join payout data (N_HARAI) into N_UMA_RACE.

    Adds tansho_payout and fukusho_payout columns.
    """
    cursor = conn.cursor()

    if not _table_exists(cursor, "N_HARAI"):
        logger.warning("N_HARAI not found, skipping payout join")
        return
    if not _table_exists(cursor, "N_UMA_RACE"):
        logger.warning("N_UMA_RACE not found, skipping payout join")
        return
    if not _column_exists(cursor, "N_HARAI", "RaceKey"):
        logger.warning("N_HARAI missing RaceKey (run step1 first), skipping")
        return

    logger.info("Loading N_HARAI for payout join...")

    # Detect available payout columns
    cursor.execute("PRAGMA table_info([N_HARAI])")
    harai_cols = {row[1] for row in cursor.fetchall()}

    # Tansho: TansyoKumi1-3 / TansyoPay1-3
    tansho_pairs = []
    for i in range(1, 4):
        kumi = f"TansyoKumi{i}"
        pay = f"TansyoPay{i}"
        if kumi in harai_cols and pay in harai_cols:
            tansho_pairs.append((kumi, pay))

    # Fukusho: FukusyoKumi1-3 / FukusyoPay1-3
    fukusho_pairs = []
    for i in range(1, 4):
        kumi = f"FukusyoKumi{i}"
        pay = f"FukusyoPay{i}"
        if kumi in harai_cols and pay in harai_cols:
            fukusho_pairs.append((kumi, pay))

    if not tansho_pairs and not fukusho_pairs:
        logger.warning("No payout columns found in N_HARAI. Available: %s", sorted(harai_cols))
        return

    # Load harai data
    select_cols = ["RaceKey"]
    for kumi, pay in tansho_pairs + fukusho_pairs:
        select_cols.extend([kumi, pay])
    harai = pd.read_sql(
        f"SELECT {', '.join(select_cols)} FROM N_HARAI WHERE RaceKey IS NOT NULL",
        conn,
    )

    # Load UMA_RACE Umaban + RaceKey
    uma = pd.read_sql(
        "SELECT rowid, RaceKey, Umaban FROM N_UMA_RACE WHERE RaceKey IS NOT NULL AND Umaban IS NOT NULL",
        conn,
    )
    uma["Umaban"] = uma["Umaban"].astype(str).str.strip()

    # Build payout lookup: {(RaceKey, Umaban_str) -> payout}
    tansho_map = {}
    fukusho_map = {}

    for _, row in harai.iterrows():
        rk = row["RaceKey"]
        for kumi, pay in tansho_pairs:
            kumi_val = str(row.get(kumi, "")).strip()
            pay_val = row.get(pay)
            if kumi_val and kumi_val != "" and kumi_val != "0" and pd.notna(pay_val):
                try:
                    tansho_map[(rk, kumi_val)] = int(pay_val)
                except (ValueError, TypeError):
                    pass
        for kumi, pay in fukusho_pairs:
            kumi_val = str(row.get(kumi, "")).strip()
            pay_val = row.get(pay)
            if kumi_val and kumi_val != "" and kumi_val != "0" and pd.notna(pay_val):
                try:
                    fukusho_map[(rk, kumi_val)] = int(pay_val)
                except (ValueError, TypeError):
                    pass

    logger.info("  Tansho payout entries: %d, Fukusho: %d", len(tansho_map), len(fukusho_map))

    # Match to UMA_RACE rows
    uma["tansho_payout"] = uma.apply(
        lambda r: tansho_map.get((r["RaceKey"], r["Umaban"])), axis=1
    )
    uma["fukusho_payout"] = uma.apply(
        lambda r: fukusho_map.get((r["RaceKey"], r["Umaban"])), axis=1
    )

    # Write back
    for col_name in ["tansho_payout", "fukusho_payout"]:
        if not _column_exists(cursor, "N_UMA_RACE", col_name):
            cursor.execute(f"ALTER TABLE [N_UMA_RACE] ADD COLUMN [{col_name}] INTEGER")

        valid = uma[uma[col_name].notna()][["rowid", col_name]]
        if len(valid) == 0:
            continue
        cursor.executemany(
            f"UPDATE [N_UMA_RACE] SET [{col_name}] = ? WHERE rowid = ?",
            list(zip(valid[col_name].astype(int).values, valid["rowid"].values)),
        )
        logger.info("  %s: updated %d rows", col_name, len(valid))


def step7_join_place_odds(conn: sqlite3.Connection) -> None:
    """Join place odds (N_ODDS_TANPUKU) into N_UMA_RACE.

    Adds fuku_odds_low, fuku_odds_high, fuku_odds_range columns.
    """
    cursor = conn.cursor()

    if not _table_exists(cursor, "N_ODDS_TANPUKU"):
        logger.warning("N_ODDS_TANPUKU not found, skipping place odds join")
        return
    if not _table_exists(cursor, "N_UMA_RACE"):
        logger.warning("N_UMA_RACE not found, skipping place odds join")
        return
    if not _column_exists(cursor, "N_ODDS_TANPUKU", "RaceKey"):
        logger.warning("N_ODDS_TANPUKU missing RaceKey (run step1 first), skipping")
        return

    # Check available columns
    cursor.execute("PRAGMA table_info([N_ODDS_TANPUKU])")
    odds_cols = {row[1] for row in cursor.fetchall()}

    fuku_low_col = None
    fuku_high_col = None
    for c in ["FukuOddsLow", "FukusyoOddsLow", "FukuOdds1"]:
        if c in odds_cols:
            fuku_low_col = c
            break
    for c in ["FukuOddsHigh", "FukusyoOddsHigh", "FukuOdds2"]:
        if c in odds_cols:
            fuku_high_col = c
            break

    umaban_col = None
    for c in ["Umaban", "UmaBan", "UmabanCD"]:
        if c in odds_cols:
            umaban_col = c
            break

    if not umaban_col:
        logger.warning("N_ODDS_TANPUKU missing Umaban column, skipping")
        return

    if not fuku_low_col and not fuku_high_col:
        logger.warning("N_ODDS_TANPUKU has no place odds columns. Available: %s", sorted(odds_cols))
        return

    logger.info("Loading N_ODDS_TANPUKU for place odds join...")
    select_cols = ["RaceKey", umaban_col]
    if fuku_low_col:
        select_cols.append(fuku_low_col)
    if fuku_high_col:
        select_cols.append(fuku_high_col)

    odds = pd.read_sql(
        f"SELECT {', '.join(select_cols)} FROM N_ODDS_TANPUKU WHERE RaceKey IS NOT NULL AND {umaban_col} IS NOT NULL",
        conn,
    )
    odds = odds.rename(columns={umaban_col: "Umaban"})
    odds["Umaban"] = odds["Umaban"].astype(str).str.strip()
    if fuku_low_col:
        odds["fuku_odds_low"] = pd.to_numeric(odds[fuku_low_col], errors="coerce")
    if fuku_high_col:
        odds["fuku_odds_high"] = pd.to_numeric(odds[fuku_high_col], errors="coerce")

    # Load UMA_RACE
    uma = pd.read_sql(
        "SELECT rowid, RaceKey, Umaban FROM N_UMA_RACE WHERE RaceKey IS NOT NULL AND Umaban IS NOT NULL",
        conn,
    )
    uma["Umaban"] = uma["Umaban"].astype(str).str.strip()

    # Merge
    merged = uma.merge(
        odds[["RaceKey", "Umaban"] + [c for c in ["fuku_odds_low", "fuku_odds_high"] if c in odds.columns]],
        on=["RaceKey", "Umaban"],
        how="left",
    )

    # Compute range
    if "fuku_odds_low" in merged.columns and "fuku_odds_high" in merged.columns:
        merged["fuku_odds_range"] = merged["fuku_odds_high"] - merged["fuku_odds_low"]

    # Write back
    for col_name in ["fuku_odds_low", "fuku_odds_high", "fuku_odds_range"]:
        if col_name not in merged.columns:
            continue
        if not _column_exists(cursor, "N_UMA_RACE", col_name):
            cursor.execute(f"ALTER TABLE [N_UMA_RACE] ADD COLUMN [{col_name}] REAL")

        valid = merged[merged[col_name].notna()][["rowid", col_name]]
        if len(valid) == 0:
            continue
        cursor.executemany(
            f"UPDATE [N_UMA_RACE] SET [{col_name}] = ? WHERE rowid = ?",
            list(zip(valid[col_name].values, valid["rowid"].values)),
        )
        logger.info("  %s: updated %d rows", col_name, len(valid))


def step8_build_cache(db_path: str) -> None:
    """Build feature_table_cache.csv using the feature builder."""
    # Add backend root to path so we can import services
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)

    from services.feature_builder import build_feature_table

    output_path = os.path.join(os.path.dirname(db_path), "feature_table_cache.csv")
    df = build_feature_table(db_path, output_path=output_path)
    logger.info("Feature table cache: %d rows, %d columns → %s",
                df.shape[0], df.shape[1], output_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Post-process EveryDB2 SQLite for UmaBuild")
    parser.add_argument(
        "--db",
        default=os.path.join(os.path.dirname(__file__), "..", "data", "jravan.db"),
        help="Path to jravan.db (default: data/jravan.db)",
    )
    parser.add_argument(
        "--build-cache",
        action="store_true",
        default=True,
        help="Build feature_table_cache.csv after post-processing (default: True)",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Skip building feature_table_cache.csv",
    )
    args = parser.parse_args()

    db_path = os.path.abspath(args.db)

    if not os.path.exists(db_path):
        logger.error("Database not found: %s", db_path)
        logger.error("Please run EveryDB2 first to create jravan.db. See README_JRAVAN.md.")
        sys.exit(1)

    logger.info("=== EveryDB2 Post-Processing ===")
    logger.info("Database: %s", db_path)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Show current tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        logger.info("Available tables: %s", tables)

        for table in ["N_RACE", "N_UMA_RACE", "N_UMA", "N_HANRO", "N_WOOD_CHIP", "N_HARAI", "N_ODDS_TANPUKU"]:
            if table in tables:
                count = cursor.execute(f"SELECT COUNT(*) FROM [{table}]").fetchone()[0]
                logger.info("  %s: %d rows", table, count)

        logger.info("--- Step 1: Synthesise RaceKey ---")
        step1_synthesise_race_key(cursor)

        logger.info("--- Step 2: Synthesise RaceDate ---")
        step2_synthesise_race_date(cursor)

        logger.info("--- Step 3: Join Pedigree Info ---")
        step3_join_pedigree(cursor)

        logger.info("--- Step 4: Create Indexes ---")
        step4_create_indexes(cursor)

        conn.commit()
        logger.info("Steps 1-4 committed.")

        logger.info("--- Step 5: Aggregate Training Data ---")
        step5_training_aggregate(conn)
        conn.commit()
        logger.info("Step 5 committed.")

        logger.info("--- Step 6: Join Payout Data ---")
        step6_join_payout(conn)
        conn.commit()
        logger.info("Step 6 committed.")

        logger.info("--- Step 7: Join Place Odds ---")
        step7_join_place_odds(conn)
        conn.commit()
        logger.info("Step 7 committed.")

        if args.build_cache and not args.no_cache:
            logger.info("--- Step 8: Build Feature Cache ---")
            step8_build_cache(db_path)

    except Exception:
        conn.rollback()
        logger.exception("Post-processing failed, changes rolled back.")
        sys.exit(1)
    finally:
        conn.close()

    logger.info("=== Done ===")


if __name__ == "__main__":
    main()

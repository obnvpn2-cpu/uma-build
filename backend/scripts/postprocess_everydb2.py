"""Post-process EveryDB2 SQLite output for UmaBuild.

EveryDB2 exports data into SQLite with composite keys and separate tables.
This script:
  1. Synthesises a single RaceKey column from composite key parts
  2. Synthesises a RaceDate column for chronological sorting
  3. Joins pedigree info (sire/damsire) from N_UMA into N_UMA_RACE
  4. Creates indexes for performance
  5. Optionally builds feature_table_cache.csv

Usage:
    cd uma-build/backend
    python scripts/postprocess_everydb2.py [--db data/jravan.db] [--build-cache]
"""

import argparse
import logging
import os
import sqlite3
import sys

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
    """Add RaceKey column to N_RACE and N_UMA_RACE."""
    concat_expr = " || ".join(RACE_KEY_PARTS)

    for table in ["N_RACE", "N_UMA_RACE"]:
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


def step5_build_cache(db_path: str) -> None:
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

        for table in ["N_RACE", "N_UMA_RACE", "N_UMA"]:
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
        logger.info("All post-processing committed.")

        if args.build_cache and not args.no_cache:
            logger.info("--- Step 5: Build Feature Cache ---")
            step5_build_cache(db_path)

    except Exception:
        conn.rollback()
        logger.exception("Post-processing failed, changes rolled back.")
        sys.exit(1)
    finally:
        conn.close()

    logger.info("=== Done ===")


if __name__ == "__main__":
    main()

"""Tests for the SQL-level year filter and history buffer logic in feature_builder.

The goal is to verify that:
  - RaceDate / Year column resolution picks the right fallback
  - MAX(RaceDate) and cutoff arithmetic is correct
  - _load_race_table / _load_uma_race_table honour the cutoff
  - build_feature_table keeps as-of history from the buffer years while
    trimming the output to the requested window
"""

import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest

from services.feature_builder import (  # noqa: E402
    _compute_cutoff,
    _get_max_race_date,
    _load_race_table,
    _load_uma_race_table,
    _resolve_date_column,
    build_feature_table,
)


def _make_db_with_racedate(path: str) -> None:
    """Create a synthetic DB with N_RACE.RaceDate and a minimal N_UMA_RACE."""
    conn = sqlite3.connect(path)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE N_RACE (
            RaceKey TEXT PRIMARY KEY,
            RaceDate TEXT,
            Year TEXT,
            Kyori INTEGER,
            TrackCD INTEGER,
            JyoCD TEXT,
            SyussoTosu INTEGER,
            GradeCD INTEGER
        )
    """)
    c.execute("""
        CREATE TABLE N_UMA_RACE (
            RaceKey TEXT,
            KettoNum TEXT,
            KakuteiJyuni INTEGER,
            HaronTimeL3 INTEGER,
            Corner3 INTEGER,
            Corner4 INTEGER,
            TansyoOdds INTEGER,
            Ninki INTEGER,
            BaTaijyu INTEGER,
            BaTaijyuZougen INTEGER,
            KisyuCode TEXT,
            ChokyosiCode TEXT,
            Wakuban INTEGER,
            Umaban INTEGER,
            SexCD INTEGER,
            Barei INTEGER,
            Futan INTEGER,
            Honsyokin INTEGER
        )
    """)
    # 5 years of races: 2020..2024
    races = []
    uma_races = []
    for year in range(2020, 2025):
        for i in range(10):
            race_key = f"{year}{i:03d}"
            races.append((
                race_key, f"{year}-06-{(i % 28) + 1:02d}", str(year),
                1800, 10, "05", 14, 0,
            ))
            for h in range(5):
                uma_races.append((
                    race_key, f"horse_{h:03d}", (h % 14) + 1,
                    340 + h, 3 + h, 3 + h, 50 + h * 10, h + 1,
                    450 + h, 0, f"J{h:03d}", f"T{h:03d}",
                    (h % 8) + 1, h + 1, 1, 4, 55, 1000,
                ))
    c.executemany(
        "INSERT INTO N_RACE VALUES (?,?,?,?,?,?,?,?)", races,
    )
    c.executemany(
        "INSERT INTO N_UMA_RACE VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        uma_races,
    )
    conn.commit()
    conn.close()


def _make_db_with_year_only(path: str) -> None:
    """Create a DB that has Year but no RaceDate column."""
    conn = sqlite3.connect(path)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE N_RACE (
            RaceKey TEXT PRIMARY KEY,
            Year TEXT,
            Kyori INTEGER,
            TrackCD INTEGER,
            JyoCD TEXT,
            SyussoTosu INTEGER,
            GradeCD INTEGER
        )
    """)
    c.execute("""
        CREATE TABLE N_UMA_RACE (
            RaceKey TEXT,
            KettoNum TEXT,
            KakuteiJyuni INTEGER
        )
    """)
    rows = []
    uma_rows = []
    for year in [2020, 2021, 2022, 2023, 2024]:
        for i in range(5):
            key = f"{year}{i:03d}"
            rows.append((key, str(year), 1800, 10, "05", 14, 0))
            uma_rows.append((key, f"horse_{i:03d}", i + 1))
    c.executemany("INSERT INTO N_RACE VALUES (?,?,?,?,?,?,?)", rows)
    c.executemany("INSERT INTO N_UMA_RACE VALUES (?,?,?)", uma_rows)
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def test_resolve_date_column_racedate_mode(tmp_path):
    db = tmp_path / "a.db"
    _make_db_with_racedate(str(db))
    conn = sqlite3.connect(str(db))
    mode, col = _resolve_date_column(conn.cursor(), "N_RACE")
    conn.close()
    assert mode == "RaceDate"
    assert col == "RaceDate"


def test_resolve_date_column_year_fallback(tmp_path):
    db = tmp_path / "b.db"
    _make_db_with_year_only(str(db))
    conn = sqlite3.connect(str(db))
    mode, col = _resolve_date_column(conn.cursor(), "N_RACE")
    conn.close()
    assert mode == "Year"
    assert col == "Year"


def test_resolve_date_column_none(tmp_path):
    db = tmp_path / "c.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE N_RACE (RaceKey TEXT)")
    conn.commit()
    mode, col = _resolve_date_column(conn.cursor(), "N_RACE")
    conn.close()
    assert mode is None
    assert col is None


def test_get_max_race_date_racedate(tmp_path):
    db = tmp_path / "a.db"
    _make_db_with_racedate(str(db))
    conn = sqlite3.connect(str(db))
    max_date = _get_max_race_date(conn.cursor(), "N_RACE", "RaceDate", "RaceDate")
    conn.close()
    assert max_date is not None
    assert max_date.startswith("2024-")


def test_get_max_race_date_year(tmp_path):
    db = tmp_path / "b.db"
    _make_db_with_year_only(str(db))
    conn = sqlite3.connect(str(db))
    max_date = _get_max_race_date(conn.cursor(), "N_RACE", "Year", "Year")
    conn.close()
    assert max_date == "2024"


def test_compute_cutoff_racedate():
    cutoff = _compute_cutoff("2024-12-31", "RaceDate", 2)
    # 365 * 2 days before 2024-12-31 lands near end of 2022 or early 2023
    # (depends on leap years). Just verify it's ~2 years earlier.
    assert cutoff is not None
    assert cutoff[:4] in {"2022", "2023"}


def test_compute_cutoff_year():
    assert _compute_cutoff("2024", "Year", 3) == "2021"


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def test_load_race_table_filter_by_racedate(tmp_path):
    db = tmp_path / "a.db"
    _make_db_with_racedate(str(db))
    conn = sqlite3.connect(str(db))
    df_all = _load_race_table(conn)
    df_2023 = _load_race_table(conn, cutoff="2023-01-01", date_col="RaceDate")
    conn.close()
    assert df_all is not None and df_2023 is not None
    assert len(df_all) > len(df_2023)
    assert df_2023["RaceDate"].min() >= "2023-01-01"


def test_load_race_table_filter_by_year(tmp_path):
    db = tmp_path / "b.db"
    _make_db_with_year_only(str(db))
    conn = sqlite3.connect(str(db))
    df_all = _load_race_table(conn)
    df_2023 = _load_race_table(conn, cutoff="2023", date_col="Year")
    conn.close()
    assert df_all is not None and df_2023 is not None
    assert len(df_all) > len(df_2023)
    assert df_2023["Year"].min() >= "2023"


def test_load_uma_race_table_follows_racekey_filter(tmp_path):
    db = tmp_path / "a.db"
    _make_db_with_racedate(str(db))
    conn = sqlite3.connect(str(db))
    race_df = _load_race_table(conn, cutoff="2023-01-01", date_col="RaceDate")
    uma_df = _load_uma_race_table(conn, cutoff="2023-01-01", date_col="RaceDate")
    conn.close()
    assert race_df is not None and uma_df is not None
    # Every RaceKey in uma_df must exist in the filtered race_df set
    assert set(uma_df["RaceKey"].unique()) <= set(race_df["RaceKey"].unique())


# ---------------------------------------------------------------------------
# End-to-end build with output trim + history buffer
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_build_feature_table_output_trim_racedate(tmp_path):
    db = tmp_path / "a.db"
    _make_db_with_racedate(str(db))
    out = tmp_path / "cache.parquet"
    df = build_feature_table(
        str(db),
        output_path=str(out),
        output_years=2,
        history_buffer_years=1,
    )
    assert "race_date" in df.columns
    dates = df["race_date"].astype(str)
    # Output rows should all be within the last 2 years window (around 2023+)
    assert (dates.min()[:4] in {"2022", "2023"})
    assert (dates.max()[:4] == "2024")
    assert out.exists()

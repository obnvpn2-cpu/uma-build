"""Tests for backend/services/future_prediction.py.

Verifies demo data generation, real-data upcoming-race loading,
feature matrix assembly, and the dispatch logic driven by the
FUTURE_PREDICTION_MODE env var.
"""

import os
import sqlite3
import sys
from datetime import datetime, timedelta
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import numpy as np
import pandas as pd

from services.future_prediction import (
    _build_upcoming_feature_matrix,
    _format_predictions,
    _generate_demo_future_races,
    generate_future_predictions,
    load_upcoming_race_entries,
)


def _make_training_df(n_races=50, n_horses=30):
    """Create a minimal training DataFrame for testing."""
    rng = np.random.RandomState(42)
    rows = []
    for race_idx in range(n_races):
        field_size = rng.randint(8, 15)
        horse_indices = rng.choice(n_horses, size=field_size, replace=False)
        for pos, h_idx in enumerate(horse_indices, 1):
            rows.append({
                "race_key": f"R{race_idx:04d}",
                "race_date": f"2024-{(race_idx % 12) + 1:02d}-{(race_idx % 28) + 1:02d}",
                "horse_key": f"H{h_idx:04d}",
                "distance": rng.choice([1200, 1600, 2000]),
                "surface": rng.choice([1, 2]),
                "finish_order": pos,
                "jockey_code": f"J{rng.randint(0, 20):03d}",
                "umaban": pos,
                "waku": min(8, (pos - 1) // 2 + 1),
                "horse_win_rate": rng.uniform(0, 0.3),
                "horse_in3_rate": rng.uniform(0, 0.6),
            })
    return pd.DataFrame(rows)


def _create_minimal_jravan_db(db_path: str, future_rows=True, today=None) -> None:
    """Build a tiny SQLite with the columns load_upcoming_race_entries needs."""
    if today is None:
        today = datetime.now()
    future_day = today + timedelta(days=2)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.executescript("""
CREATE TABLE N_RACE (
    RaceKey TEXT, RaceDate TEXT, Kyori TEXT, TrackCD TEXT,
    JyoCD TEXT, GradeCD TEXT, Hondai TEXT,
    SyussoTosu TEXT, TorokuTosu TEXT, RaceNum TEXT
);
CREATE TABLE N_UMA_RACE (
    RaceKey TEXT, KettoNum TEXT, Umaban TEXT, Wakuban TEXT,
    Bamei TEXT, KisyuCode TEXT, KisyuRyakusyo TEXT,
    ChokyosiCode TEXT, Futan TEXT, Barei TEXT, SexCD TEXT,
    BaTaijyu TEXT, KakuteiJyuni TEXT
);
""")

    # Always insert one past race (already settled)
    past_date = (today - timedelta(days=14)).strftime("%Y-%m-%d")
    cur.execute(
        "INSERT INTO N_RACE VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("PAST001", past_date, "1600", "10", "05", "", "過去レース",
         "10", "10", "11"),
    )
    cur.execute(
        "INSERT INTO N_UMA_RACE VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("PAST001", "HORSE0001", "01", "1", "過去馬", "J001", "過去騎手",
         "C001", "56", "5", "1", "480", "03"),
    )

    if future_rows:
        future_date = future_day.strftime("%Y-%m-%d")
        cur.execute(
            "INSERT INTO N_RACE VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("FUT001", future_date, "1800", "10", "05", "A", "皐月賞",
             "16", "16", "11"),
        )
        for i in range(1, 4):
            cur.execute(
                "INSERT INTO N_UMA_RACE VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("FUT001", f"HORSE{i:04d}", f"{i:02d}", str(i), f"Horse{i}",
                 f"J{i:03d}", f"騎手{i}", f"C{i:03d}", "56", "4", "1", "480", ""),
            )

    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Legacy demo-path tests — conftest.py sets FUTURE_PREDICTION_MODE=demo
# ---------------------------------------------------------------------------


def test_generate_demo_future_races_shape():
    df = _make_training_df()
    future = _generate_demo_future_races(df, n_races=2)
    assert not future.empty
    assert "race_key" in future.columns
    assert "finish_order" in future.columns
    assert future["finish_order"].isna().all()


def test_generate_demo_future_races_race_count():
    df = _make_training_df()
    future = _generate_demo_future_races(df, n_races=3)
    race_keys = future["race_key"].unique()
    assert len(race_keys) == 3


def test_generate_demo_future_races_empty_input():
    future = _generate_demo_future_races(pd.DataFrame(), n_races=3)
    assert future.empty


def test_generate_demo_future_races_metadata():
    df = _make_training_df()
    future = _generate_demo_future_races(df, n_races=1)
    assert "_race_name" in future.columns
    assert "_surface_label" in future.columns
    assert "_horse_name" in future.columns
    assert "_gate_number" in future.columns


def test_format_predictions_structure():
    df = _make_training_df()
    future = _generate_demo_future_races(df, n_races=2)
    future["predicted_score"] = np.random.rand(len(future))

    results = _format_predictions(future)
    assert isinstance(results, list)
    assert len(results) == 2

    race = results[0]
    assert "race_key" in race
    assert "race_date" in race
    assert "race_name" in race
    assert "distance" in race
    assert "surface" in race
    assert "entries" in race

    entry = race["entries"][0]
    assert entry["rank"] == 1
    assert "horse_name" in entry
    assert "predicted_score" in entry
    assert entry["confidence"] in ("high", "medium", "low")
    assert "jockey" in entry
    assert "gate_number" in entry


def test_format_predictions_ranking():
    df = _make_training_df()
    future = _generate_demo_future_races(df, n_races=1)
    future["predicted_score"] = np.random.rand(len(future))

    results = _format_predictions(future)
    entries = results[0]["entries"]
    scores = [e["predicted_score"] for e in entries]
    assert scores == sorted(scores, reverse=True)


def test_generate_future_predictions_with_missing_model(tmp_path):
    """Missing model file → status=unavailable, predictions empty."""
    fake_path = str(tmp_path / "nonexistent.pkl")
    result = generate_future_predictions(
        model_path=fake_path,
        selected_features=["horse_win_rate"],
    )
    assert result["predictions"] == []
    assert result["meta"]["status"] == "unavailable"


# ---------------------------------------------------------------------------
# Real-data path tests
# ---------------------------------------------------------------------------


def testload_upcoming_race_entries_empty_db(tmp_path):
    """When DB has no upcoming rows, the loader returns an empty DataFrame."""
    db_path = str(tmp_path / "empty.db")
    _create_minimal_jravan_db(db_path, future_rows=False)

    df = load_upcoming_race_entries(db_path)
    assert df.empty


def testload_upcoming_race_entries_finds_upcoming(tmp_path):
    """Future rows (KakuteiJyuni='', race_date > today) are returned."""
    db_path = str(tmp_path / "with_future.db")
    _create_minimal_jravan_db(db_path, future_rows=True)

    df = load_upcoming_race_entries(db_path)
    assert not df.empty
    assert df["race_key"].iloc[0] == "FUT001"
    # 3 horses entered for the future race
    assert len(df) == 3
    assert set(df.columns) >= {
        "race_key", "race_date", "horse_key", "umaban", "_horse_name",
        "_race_name", "_surface_label", "surface", "distance", "_gate_number",
    }


def test_build_upcoming_feature_matrix_fills_from_cache():
    """Columns in the training cache propagate onto upcoming rows."""
    upcoming = pd.DataFrame({
        "horse_key": ["H0001", "H0002"],
        "distance": [1600, 2000],
        "_race_name": ["R1", "R1"],
    })
    training = pd.DataFrame({
        "horse_key": ["H0001", "H0001", "H0002"],
        "race_date": ["2024-01-01", "2024-03-01", "2024-02-01"],
        "horse_win_rate": [0.1, 0.4, 0.25],
    })

    matrix = _build_upcoming_feature_matrix(
        upcoming, training, feature_names=["distance", "horse_win_rate"],
    )
    assert list(matrix.columns) == ["distance", "horse_win_rate"]
    assert list(matrix["distance"]) == [1600, 2000]
    # H0001's latest row (2024-03-01) has win_rate 0.4
    assert matrix["horse_win_rate"].iloc[0] == 0.4
    assert matrix["horse_win_rate"].iloc[1] == 0.25


def test_build_upcoming_feature_matrix_unknown_column_is_nan():
    """Columns absent from both sources become NaN columns of matching length."""
    upcoming = pd.DataFrame({
        "horse_key": ["H0001", "H0002"],
        "distance": [1600, 1800],
    })
    training = pd.DataFrame({
        "horse_key": ["H0001"],
        "race_date": ["2024-01-01"],
        "horse_win_rate": [0.3],
    })
    matrix = _build_upcoming_feature_matrix(
        upcoming, training,
        feature_names=["distance", "horse_win_rate", "completely_unknown"],
    )
    assert len(matrix) == 2
    assert matrix["completely_unknown"].isna().all()


def test_generate_future_predictions_real_mode_no_upcoming(tmp_path, monkeypatch):
    """real mode + empty DB → predictions=[], meta.status=no_upcoming."""
    db_path = str(tmp_path / "no_future.db")
    _create_minimal_jravan_db(db_path, future_rows=False)

    monkeypatch.setenv("FUTURE_PREDICTION_MODE", "real")

    # Mock pipeline.load so we don't need a real model artefact
    class _FakePipeline:
        feature_names = ["distance", "horse_win_rate"]

        def predict(self, X):
            return np.zeros(len(X))

    with patch("services.future_prediction.LGBMPipeline.load", return_value=_FakePipeline()):
        result = generate_future_predictions(
            model_path="ignored.pkl",
            selected_features=[],
            db_path=db_path,
        )

    assert result["predictions"] == []
    assert result["meta"]["status"] == "no_upcoming"
    assert result["meta"]["upcoming_count"] == 0


def test_generate_future_predictions_prefers_parquet_over_sqlite(tmp_path, monkeypatch):
    """When upcoming_races.parquet is present, it wins over the sqlite query.

    Cloud Run image ships the parquet but no jravan.db; this is the prod path.
    """
    db_path = str(tmp_path / "stale.db")
    # Stub a DB whose 'future_rows' wouldn't be picked up so we can verify
    # that the parquet is the source of truth in this run.
    _create_minimal_jravan_db(db_path, future_rows=False)

    # Build a parquet with one upcoming race ~3 days from today.
    future_date = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
    parquet_df = pd.DataFrame({
        "race_key": ["PQ001", "PQ001"],
        "race_date": [future_date, future_date],
        "horse_key": ["H_A", "H_B"],
        "umaban": [1, 2],
        "_horse_name": ["パケットA", "パケットB"],
        "_race_name": ["パーケット記念", "パーケット記念"],
        "_surface_label": ["芝", "芝"],
        "surface": [1, 1],
        "distance": [1600, 1600],
        "_gate_number": [1, 2],
        "_jockey": ["J1", "J2"],
    })
    parquet_path = tmp_path / "upcoming_races.parquet"
    parquet_df.to_parquet(parquet_path, engine="pyarrow", index=False)

    monkeypatch.setenv("FUTURE_PREDICTION_MODE", "real")
    monkeypatch.setenv("UPCOMING_PARQUET_PATH", str(parquet_path))

    class _FakePipeline:
        feature_names = ["distance"]

        def predict(self, X):
            return np.arange(len(X), dtype=float)

    with patch("services.future_prediction.LGBMPipeline.load", return_value=_FakePipeline()):
        result = generate_future_predictions(
            model_path="ignored.pkl",
            selected_features=[],
            db_path=db_path,
        )

    assert result["meta"]["status"] == "ok"
    assert result["meta"]["upcoming_count"] == 1
    race = result["predictions"][0]
    assert race["race_key"] == "PQ001"
    assert race["race_name"] == "パーケット記念"


def test_generate_future_predictions_skips_stale_parquet_dates(tmp_path, monkeypatch):
    """Parquet entries whose race_date is in the past are filtered out."""
    db_path = str(tmp_path / "no_future.db")
    _create_minimal_jravan_db(db_path, future_rows=False)

    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    parquet_df = pd.DataFrame({
        "race_key": ["PAST"],
        "race_date": [yesterday],
        "horse_key": ["H_A"],
        "umaban": [1],
        "_horse_name": ["A"],
        "_race_name": ["過去レース"],
        "_surface_label": ["芝"],
        "surface": [1],
        "distance": [1600],
        "_gate_number": [1],
    })
    parquet_path = tmp_path / "upcoming_races.parquet"
    parquet_df.to_parquet(parquet_path, engine="pyarrow", index=False)

    monkeypatch.setenv("FUTURE_PREDICTION_MODE", "real")
    monkeypatch.setenv("UPCOMING_PARQUET_PATH", str(parquet_path))

    class _FakePipeline:
        feature_names = ["distance"]
        def predict(self, X):
            return np.zeros(len(X))

    with patch("services.future_prediction.LGBMPipeline.load", return_value=_FakePipeline()):
        result = generate_future_predictions(
            model_path="ignored.pkl",
            selected_features=[],
            db_path=db_path,
        )

    assert result["meta"]["status"] == "no_upcoming"
    assert result["meta"]["upcoming_count"] == 0


def test_generate_future_predictions_real_mode_with_upcoming(tmp_path, monkeypatch):
    """real mode + DB with future rows → predictions returned, meta.status=ok."""
    db_path = str(tmp_path / "with_future.db")
    _create_minimal_jravan_db(db_path, future_rows=True)

    monkeypatch.setenv("FUTURE_PREDICTION_MODE", "real")

    class _FakePipeline:
        feature_names = ["distance"]

        def predict(self, X):
            # Deterministic rank: later rows get higher scores
            return np.arange(len(X), dtype=float)

    with patch("services.future_prediction.LGBMPipeline.load", return_value=_FakePipeline()):
        result = generate_future_predictions(
            model_path="ignored.pkl",
            selected_features=[],
            db_path=db_path,
        )

    assert result["meta"]["status"] == "ok"
    assert result["meta"]["upcoming_count"] == 1
    assert len(result["predictions"]) == 1
    race = result["predictions"][0]
    assert race["race_name"] == "皐月賞"
    assert len(race["entries"]) == 3
    # Ranked descending by predicted_score
    scores = [e["predicted_score"] for e in race["entries"]]
    assert scores == sorted(scores, reverse=True)

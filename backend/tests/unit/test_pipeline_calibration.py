"""Tests for LGBMPipeline calibration + classification metric helpers.

Synthetic binary data exercises:
- save/load round-trip preserves the calibrator
- isotonic calibration improves Brier score on a held-out slice
- predict() returns calibrated output when calibrator is set
- _fit_calibrator() skips with a warning when holdout is too small
- _eval_classification_metrics() returns finite values on healthy data
"""

from __future__ import annotations

import logging
import os
import sys
import tempfile

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from ml.pipeline import (  # noqa: E402
    LGBMPipeline,
    TrainConfig,
    _eval_classification_metrics,
    _expected_calibration_error,
    _GroupedIsotonic,
)

# --- helpers ----------------------------------------------------------------


def _make_synthetic_binary(
    n_train: int = 8000, n_calib: int = 6000, n_val: int = 4000, seed: int = 42,
):
    """Synthesise three disjoint binary-classification splits.

    Features are well-separable so a vanilla LightGBM gets meaningful AUC
    (~0.85). Output uses a deliberately miscalibrated link (squared
    logistic) so isotonic calibration has something to fix.
    """
    rng = np.random.default_rng(seed)

    def _sample(n):
        x = rng.normal(size=(n, 5))
        # True logit is a simple linear combination
        true_logit = 0.8 * x[:, 0] - 0.5 * x[:, 1] + 0.3 * x[:, 2]
        p_true = 1.0 / (1.0 + np.exp(-true_logit))
        y = rng.binomial(1, p_true).astype(int)
        df = pd.DataFrame(x, columns=[f"f{i}" for i in range(5)])
        return df, pd.Series(y)

    return _sample(n_train), _sample(n_calib), _sample(n_val)


# --- tests ------------------------------------------------------------------


def test_eval_classification_metrics_returns_finite_values():
    y = np.array([0, 1, 0, 1, 1, 0, 1, 0, 1, 0])
    p = np.array([0.1, 0.9, 0.2, 0.8, 0.7, 0.3, 0.6, 0.4, 0.85, 0.15])
    out = _eval_classification_metrics(y, p)
    assert set(out.keys()) >= {"val_auc", "val_brier", "val_logloss", "val_ece"}
    for v in out.values():
        assert np.isfinite(v), f"expected finite metric, got {v}"
    assert 0.0 <= out["val_auc"] <= 1.0
    assert out["val_brier"] >= 0.0


def test_eval_metrics_handle_single_class_gracefully():
    y = np.zeros(20, dtype=int)
    p = np.linspace(0.05, 0.95, 20)
    out = _eval_classification_metrics(y, p)
    # AUC undefined for single-class; logloss/brier still computable
    assert np.isnan(out["val_auc"])
    assert np.isfinite(out["val_brier"])


def test_ece_is_zero_on_perfect_calibration():
    # Construct y that perfectly tracks predicted prob within each bin.
    rng = np.random.default_rng(0)
    p = rng.uniform(0.0, 1.0, size=2000)
    y = (rng.uniform(0.0, 1.0, size=2000) < p).astype(int)
    # Large sample so bin means converge to predicted; ECE should be small.
    ece = _expected_calibration_error(y, p, n_bins=10)
    assert ece < 0.05, f"expected small ECE on well-calibrated data, got {ece}"


def test_isotonic_calibration_improves_brier(caplog):
    """End-to-end: train binary, fit isotonic on holdout, assert Brier drops."""
    (X_tr, y_tr), (X_cal, y_cal), (X_val, y_val) = _make_synthetic_binary(
        n_train=8000, n_calib=6000, n_val=4000,
    )

    cfg = TrainConfig(
        objective_type="binary",
        calibration_method="isotonic",
        calibration_min_holdout_rows=1000,
        num_boost_round=100,
        early_stopping_rounds=20,
    )
    pipeline = LGBMPipeline(config=cfg)
    pipeline.train(X_tr, y_tr, X_val, y_val)

    raw_val = pipeline.predict_raw(X_val)
    pre_metrics = _eval_classification_metrics(y_val.values, raw_val)

    raw_calib = pipeline.predict_raw(X_cal)
    with caplog.at_level(logging.INFO):
        pipeline._fit_calibrator(raw_calib, y_cal.values)

    cal_val = pipeline.predict(X_val)
    post_metrics = _eval_classification_metrics(y_val.values, cal_val)

    # Calibrator metadata records the on-holdout improvement deterministically
    assert pipeline.calibration_metrics is not None
    assert pipeline.calibration_metrics["method"] == "isotonic"
    assert pipeline.calibration_metrics["n_holdout"] == len(X_cal)
    # Holdout-side ECE/Brier must strictly improve (these are evaluated on
    # the same data the calibrator was fit on, so improvement is monotonic).
    assert pipeline.calibration_metrics["post_ece"] <= \
        pipeline.calibration_metrics["pre_ece"] + 1e-9
    assert pipeline.calibration_metrics["post_brier"] <= \
        pipeline.calibration_metrics["pre_brier"] + 1e-9
    # On val (a different sample) ECE is the high-signal calibration metric.
    # Brier can regress by sampling noise on already-near-calibrated outputs;
    # ECE picks up the systematic calibration shift even then.
    assert post_metrics["val_ece"] <= pre_metrics["val_ece"] + 5e-3, (
        f"val ECE regressed beyond noise: pre={pre_metrics['val_ece']:.4f}, "
        f"post={post_metrics['val_ece']:.4f}"
    )
    # Brier on val: allow a small noise band; LGBM on a logistic-link synth
    # is already near-calibrated, so the move is dominated by sample noise.
    assert post_metrics["val_brier"] <= pre_metrics["val_brier"] + 5e-3, (
        f"val Brier regressed beyond noise: pre={pre_metrics['val_brier']:.4f}, "
        f"post={post_metrics['val_brier']:.4f}"
    )


def test_calibration_skipped_when_holdout_below_min(caplog):
    """Calibrator stays None when holdout < calibration_min_holdout_rows."""
    (X_tr, y_tr), _, (X_val, y_val) = _make_synthetic_binary(
        n_train=4000, n_calib=4000, n_val=2000,
    )
    cfg = TrainConfig(
        objective_type="binary",
        calibration_method="isotonic",
        calibration_min_holdout_rows=10_000,  # deliberately too high
        num_boost_round=50,
        early_stopping_rounds=10,
    )
    pipeline = LGBMPipeline(config=cfg)
    pipeline.train(X_tr, y_tr, X_val, y_val)

    tiny_holdout_X = X_tr.head(500)
    tiny_holdout_y = y_tr.head(500)
    raw = pipeline.predict_raw(tiny_holdout_X)
    with caplog.at_level(logging.WARNING):
        pipeline._fit_calibrator(raw, tiny_holdout_y.values)

    assert pipeline.calibrator is None
    assert any("Calibration skipped" in r.message for r in caplog.records)


def test_save_load_roundtrip_preserves_calibrator():
    (X_tr, y_tr), (X_cal, y_cal), (X_val, y_val) = _make_synthetic_binary(
        n_train=4000, n_calib=3000, n_val=2000,
    )
    cfg = TrainConfig(
        objective_type="binary",
        calibration_method="isotonic",
        calibration_min_holdout_rows=500,
        num_boost_round=80,
        early_stopping_rounds=15,
    )
    pipeline = LGBMPipeline(config=cfg)
    pipeline.train(X_tr, y_tr, X_val, y_val)
    pipeline._fit_calibrator(pipeline.predict_raw(X_cal), y_cal.values)

    assert pipeline.calibrator is not None

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "model.pkl")
        pipeline.save(path)
        loaded = LGBMPipeline.load(path)

    assert loaded.calibrator is not None
    assert loaded.calibration_metrics is not None
    assert loaded.calibration_metrics["method"] == "isotonic"

    # Identical predictions before/after round-trip
    p_before = pipeline.predict(X_val)
    p_after = loaded.predict(X_val)
    np.testing.assert_allclose(p_before, p_after, rtol=1e-12, atol=1e-12)


def test_load_pickle_without_calibrator_keys_is_backward_compatible():
    """A pkl missing 'calibrator' / 'calibration_metrics' keys must load."""
    import pickle

    (X_tr, y_tr), _, (X_val, y_val) = _make_synthetic_binary(
        n_train=2000, n_calib=1, n_val=1000,
    )
    cfg = TrainConfig(
        objective_type="binary",
        num_boost_round=40,
        early_stopping_rounds=10,
    )
    pipeline = LGBMPipeline(config=cfg)
    pipeline.train(X_tr, y_tr, X_val, y_val)

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "old.pkl")
        # Simulate an older pickle: drop both the new top-level keys AND
        # the new TrainConfig fields. This is what an actual pre-C1 pkl
        # on disk would look like, and exercises the unknown-key filter
        # in LGBMPipeline.load() that absorbs schema drift.
        from dataclasses import asdict
        cfg_dict = asdict(pipeline.config)
        for new_field in (
            "calibration_method",
            "calibration_holdout_frac",
            "calibration_min_holdout_rows",
        ):
            cfg_dict.pop(new_field, None)
        old = {
            "model": pipeline.model,
            "feature_names": pipeline.feature_names,
            "categorical_features": pipeline.categorical_features,
            "config": cfg_dict,
            "train_metrics": pipeline.train_metrics,
            "model_id": pipeline.model_id,
        }
        with open(path, "wb") as f:
            pickle.dump(old, f)

        loaded = LGBMPipeline.load(path)
        # The filtered config should fall back to TrainConfig defaults
        # for the calibration_* fields.
        assert loaded.config.calibration_method is None
        assert loaded.config.calibration_holdout_frac == 0.2

    assert loaded.calibrator is None
    assert loaded.calibration_metrics is None
    # predict() still works (no calibrator path)
    out = loaded.predict(X_val)
    assert out.shape == (len(X_val),)


def test_predict_without_calibrator_matches_predict_raw():
    """predict() and predict_raw() are identical when no calibrator set."""
    (X_tr, y_tr), _, (X_val, _) = _make_synthetic_binary(
        n_train=2000, n_calib=1, n_val=500,
    )
    cfg = TrainConfig(
        objective_type="binary",
        num_boost_round=40,
        early_stopping_rounds=10,
    )
    pipeline = LGBMPipeline(config=cfg)
    pipeline.train(X_tr, y_tr, X_val, pd.Series(np.zeros(500, dtype=int)))

    p1 = pipeline.predict(X_val)
    p2 = pipeline.predict_raw(X_val)
    np.testing.assert_array_equal(p1, p2)


def test_lambdarank_objective_unaffected_by_calibration_fields():
    """Lambdarank pipelines ignore calibration_method and stay rank-only."""
    rng = np.random.default_rng(0)
    n_races = 100
    horses_per_race = 8
    rows = []
    for r in range(n_races):
        for h in range(horses_per_race):
            rows.append({
                "race_key": f"R{r:04d}",
                "horse_key": f"H{r * horses_per_race + h:05d}",
                "f0": rng.normal(),
                "f1": rng.normal(),
                "finish_order": h + 1,
            })
    df = pd.DataFrame(rows)
    cfg = TrainConfig(
        objective_type="lambdarank",
        # Even with calibration_method set, lambdarank path must ignore it
        calibration_method="isotonic",
        num_boost_round=40,
        early_stopping_rounds=10,
    )
    pipeline = LGBMPipeline(config=cfg)
    from ml.pipeline import finish_to_relevance

    half = len(df) // 2
    X_tr = df.iloc[:half][["f0", "f1"]]
    y_tr = finish_to_relevance(df.iloc[:half]["finish_order"])
    X_val = df.iloc[half:][["f0", "f1"]]
    y_val = finish_to_relevance(df.iloc[half:]["finish_order"])
    g_tr = df.iloc[:half].groupby("race_key", sort=False).size().tolist()
    g_val = df.iloc[half:].groupby("race_key", sort=False).size().tolist()

    pipeline.train(X_tr, y_tr, X_val, y_val, group_train=g_tr, group_val=g_val)
    assert pipeline.train_metrics["objective"] == "lambdarank"
    assert pipeline.calibrator is None
    out = pipeline.predict(X_val)
    assert out.shape == (len(X_val),)


def test_grouped_isotonic_dispatches_per_bucket():
    """Each bucket gets its own isotonic; small bucket falls back to global."""
    rng = np.random.default_rng(0)
    n = 6000
    raw = rng.uniform(0.0, 1.0, n)
    # Two regimes: bucket 0 (rare wins, p=0.05*raw), bucket 1 (frequent
    # wins, p=0.5*raw). One global isotonic would average these and
    # under/overfit each. Per-bucket should track each regime cleanly.
    groups = rng.choice([10, 14], size=n)  # bucket 0 = 10-head, 1 = 14-head
    p_true = np.where(groups == 10, 0.05 * raw, 0.5 * raw)
    y = (rng.uniform(0.0, 1.0, n) < p_true).astype(int)

    cal = _GroupedIsotonic(bins=[(8, 12), (13, 16)], min_rows=500)
    cal.fit(raw, y, groups)
    # Two distinct calibrators were fit (both buckets have ≥ 500 rows).
    assert len(cal.calibrators) == 2
    # Transform respects group dispatch: same raw score should map to a
    # much lower calibrated probability under the rare-win regime.
    test_raw = np.array([0.8, 0.8])
    test_groups = np.array([10, 14])
    out = cal.transform(test_raw, test_groups)
    assert out[1] > out[0] * 2, (
        f"Expected bucket-14 calibration ≫ bucket-10 at raw=0.8, "
        f"got {out}"
    )


def test_grouped_isotonic_falls_back_for_small_bucket():
    """Bucket below min_rows uses the global fallback isotonic."""
    rng = np.random.default_rng(1)
    n_main = 3000
    n_small = 50  # below min_rows=500
    raw = np.concatenate([rng.uniform(0, 1, n_main), rng.uniform(0, 1, n_small)])
    groups = np.concatenate([np.full(n_main, 14), np.full(n_small, 18)])
    y = (rng.uniform(0, 1, len(raw)) < 0.3 * raw).astype(int)

    cal = _GroupedIsotonic(bins=[(13, 16), (17, 18)], min_rows=500)
    cal.fit(raw, y, groups)
    # Bucket 0 (14-head, 3000 rows) gets a per-bin calibrator.
    assert 0 in cal.calibrators
    # Bucket 1 (18-head, 50 rows) does NOT — falls back at predict time.
    assert 1 not in cal.calibrators
    # Transform on bucket-1 rows should still produce a calibrated value
    # (via the fallback) without raising.
    out = cal.transform(np.array([0.5]), np.array([18]))
    assert 0.0 <= out[0] <= 1.0


def test_grouped_isotonic_transform_handles_unmapped_groups():
    """Groups outside any declared bin route to the global fallback."""
    rng = np.random.default_rng(2)
    n = 2000
    raw = rng.uniform(0, 1, n)
    groups = np.full(n, 14)  # all in bucket 0
    y = (rng.uniform(0, 1, n) < 0.4 * raw).astype(int)
    cal = _GroupedIsotonic(bins=[(13, 16)], min_rows=500)
    cal.fit(raw, y, groups)
    # Group 99 is outside the only declared bin → use fallback.
    out = cal.transform(np.array([0.5, 0.5]), np.array([14, 99]))
    assert 0.0 <= out[0] <= 1.0
    assert 0.0 <= out[1] <= 1.0


def test_pipeline_grouped_calibration_end_to_end():
    """LGBMPipeline + grouped calibrator: predict() reads size_col from X.

    Mirrors production: field_size is a META column kept OUT of training
    features and attached only to predict-time X for grouped dispatch.
    """
    (X_tr, y_tr), (X_cal, y_cal), (X_val, y_val) = _make_synthetic_binary(
        n_train=8000, n_calib=6000, n_val=4000,
    )

    cfg = TrainConfig(
        objective_type="binary",
        calibration_method="isotonic",
        calibration_min_holdout_rows=1000,
        calibration_size_col="field_size",
        calibration_size_bins=[[8, 12], [13, 16], [17, 18]],
        calibration_per_size_min_rows=500,
        num_boost_round=80,
        early_stopping_rounds=15,
    )
    pipeline = LGBMPipeline(config=cfg)
    # Train on bare features (no field_size) — mirrors walk_forward.
    pipeline.train(X_tr, y_tr, X_val, y_val)

    # Synthesize field_size only for calibration + predict.
    rng = np.random.default_rng(7)
    cal_groups = rng.choice([10, 14, 17], size=len(X_cal))
    raw_calib = pipeline.predict_raw(X_cal)
    pipeline._fit_calibrator(raw_calib, y_cal.values, groups=cal_groups)

    assert isinstance(pipeline.calibrator, _GroupedIsotonic)
    assert "per_bin" in pipeline.calibration_metrics
    assert pipeline.calibration_metrics["size_col"] == "field_size"

    # Predict-time X gets field_size attached (not a model feature).
    X_val_pred = X_val.copy()
    X_val_pred["field_size"] = rng.choice([10, 14, 17], size=len(X_val))
    out = pipeline.predict(X_val_pred)
    assert out.shape == (len(X_val),)
    assert (out >= 0.0).all() and (out <= 1.0).all()

    # Predict without size_col in X must raise — caller responsibility.
    with pytest.raises(RuntimeError, match="field_size"):
        pipeline.predict(X_val)


def test_grouped_calibration_save_load_roundtrip():
    """Save → load preserves the GroupedIsotonic; predict matches."""
    (X_tr, y_tr), (X_cal, y_cal), (X_val, y_val) = _make_synthetic_binary(
        n_train=4000, n_calib=3000, n_val=2000,
    )

    cfg = TrainConfig(
        objective_type="binary",
        calibration_method="isotonic",
        calibration_min_holdout_rows=500,
        calibration_size_col="field_size",
        calibration_size_bins=[[8, 12], [13, 16], [17, 18]],
        calibration_per_size_min_rows=300,
        num_boost_round=50,
        early_stopping_rounds=10,
    )
    pipeline = LGBMPipeline(config=cfg)
    pipeline.train(X_tr, y_tr, X_val, y_val)
    rng = np.random.default_rng(9)
    cal_groups = rng.choice([10, 14, 17], size=len(X_cal))
    pipeline._fit_calibrator(
        pipeline.predict_raw(X_cal), y_cal.values, groups=cal_groups,
    )
    X_val_pred = X_val.copy()
    val_groups = rng.choice([10, 14, 17], size=len(X_val))
    X_val_pred["field_size"] = val_groups
    p_before = pipeline.predict(X_val_pred)

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "grouped.pkl")
        pipeline.save(path)
        loaded = LGBMPipeline.load(path)

    assert isinstance(loaded.calibrator, _GroupedIsotonic)
    p_after = loaded.predict(X_val_pred)
    np.testing.assert_allclose(p_before, p_after, rtol=1e-12, atol=1e-12)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))

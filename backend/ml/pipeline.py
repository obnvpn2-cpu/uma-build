"""LightGBM training pipeline for UmaBuild.

Provides a configurable LightGBM binary classifier for horse racing
prediction (win / top-3 finish).
"""

import logging
import os
import pickle
import uuid
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score

logger = logging.getLogger(__name__)

# Directory to store trained models
MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "trained_models")
os.makedirs(MODELS_DIR, exist_ok=True)


def finish_to_relevance(finish_order: pd.Series) -> pd.Series:
    """Convert finish position to LambdaRank relevance labels.

    Mapping: 1st→4, 2nd→3, 3rd→2, 4th→1, 5th+→0
    """
    return (
        finish_order
        .clip(lower=1)
        .map(lambda f: max(0, 5 - int(f)) if f <= 5 else 0)
        .fillna(0)
        .astype(int)
    )


@dataclass
class TrainConfig:
    """Configuration for LightGBM training."""

    target_col: str = "target_win"
    objective_type: str = "lambdarank"  # "lambdarank" or "binary"
    learning_rate: float = 0.05
    num_leaves: int = 63
    max_depth: int = 8
    num_boost_round: int = 1000
    early_stopping_rounds: int = 50
    lambda_l2: float = 0.1
    feature_fraction: float = 0.9
    bagging_fraction: float = 0.8
    bagging_freq: int = 5
    min_child_samples: int = 20
    verbose: int = -1
    # Probability calibration (binary objective only). None disables.
    # Caller (walk_forward_cv) is responsible for fitting via
    # LGBMPipeline._fit_calibrator() on a held-out slice of train data.
    calibration_method: Optional[str] = None  # "isotonic" | "platt" | None
    calibration_holdout_frac: float = 0.2
    calibration_min_holdout_rows: int = 5000
    # Optional per-group calibration. When ``calibration_size_col`` is set,
    # _fit_calibrator() requires a ``groups`` array and fits one isotonic
    # per bin in ``calibration_size_bins`` (inclusive ranges). predict()
    # reads X[calibration_size_col] to dispatch the right calibrator at
    # inference time. Bins that fall under
    # ``calibration_per_size_min_rows`` are not fit; rows that hit them
    # use the global fallback isotonic. None disables grouping.
    # Note: bins are stored as List[List[int]] (not List[Tuple[int,int]])
    # so the dataclass is JSON-serializable for pickle save/load and so
    # callers can pass plain literals like [[1,12],[13,16]]. Internally
    # _fit_calibrator coerces each pair to a tuple at fit time.
    calibration_size_col: Optional[str] = None
    calibration_size_bins: Optional[List[List[int]]] = None
    calibration_per_size_min_rows: int = 500

    def to_lgb_params(self) -> Dict[str, Any]:
        """Convert to LightGBM parameter dict."""
        if self.objective_type == "lambdarank":
            return {
                "objective": "lambdarank",
                "metric": "ndcg",
                "ndcg_eval_at": [1, 3, 5],
                "learning_rate": self.learning_rate,
                "num_leaves": self.num_leaves,
                "max_depth": self.max_depth,
                "lambda_l2": self.lambda_l2,
                "feature_fraction": self.feature_fraction,
                "bagging_fraction": self.bagging_fraction,
                "bagging_freq": self.bagging_freq,
                "min_child_samples": self.min_child_samples,
                "verbose": self.verbose,
                "force_col_wise": True,
                "seed": 42,
            }
        return {
            "objective": "binary",
            "metric": "binary_logloss",
            "learning_rate": self.learning_rate,
            "num_leaves": self.num_leaves,
            "max_depth": self.max_depth,
            "lambda_l2": self.lambda_l2,
            "feature_fraction": self.feature_fraction,
            "bagging_fraction": self.bagging_fraction,
            "bagging_freq": self.bagging_freq,
            "min_child_samples": self.min_child_samples,
            "verbose": self.verbose,
            "force_col_wise": True,
            "seed": 42,
        }


class LGBMPipeline:
    """LightGBM pipeline for horse racing prediction."""

    def __init__(self, config: Optional[TrainConfig] = None):
        self.config = config or TrainConfig()
        self.model: Optional[lgb.Booster] = None
        self.feature_names: List[str] = []
        # Categorical columns the model was trained with. Saved/loaded so
        # that predict() can re-cast inference data to the same dtype.
        # LightGBM otherwise raises "categorical_feature do not match".
        self.categorical_features: List[str] = []
        self.model_id: str = ""
        self.train_metrics: Dict[str, Any] = {}
        # Probability calibrator. None until _fit_calibrator() is called.
        # When non-None, predict() applies it to raw model output.
        self.calibrator: Optional[Any] = None
        self.calibration_metrics: Optional[Dict[str, float]] = None

    def train(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: pd.DataFrame,
        y_val: pd.Series,
        group_train: Optional[List[int]] = None,
        group_val: Optional[List[int]] = None,
    ) -> lgb.Booster:
        """Train a LightGBM model with early stopping.

        Args:
            X_train: Training features.
            y_train: Training labels (binary) or relevance (lambdarank).
            X_val: Validation features.
            y_val: Validation labels or relevance.
            group_train: Group sizes for lambdarank (horses per race).
            group_val: Group sizes for lambdarank validation.

        Returns:
            Trained LightGBM Booster.
        """
        is_rank = self.config.objective_type == "lambdarank"
        logger.info(
            "Training LightGBM (%s): %d train rows, %d val rows, %d features",
            self.config.objective_type,
            len(X_train), len(X_val), X_train.shape[1],
        )

        self.feature_names = list(X_train.columns)
        self.model_id = str(uuid.uuid4())[:8]

        # Handle categorical columns
        categorical_cols = X_train.select_dtypes(include=["category", "object"]).columns.tolist()
        for col in categorical_cols:
            X_train[col] = X_train[col].astype("category")
            X_val[col] = X_val[col].astype("category")
        self.categorical_features = list(categorical_cols)

        train_data = lgb.Dataset(
            X_train, label=y_train,
            group=group_train if is_rank else None,
            categorical_feature=categorical_cols if categorical_cols else "auto",
            free_raw_data=False,
        )
        val_data = lgb.Dataset(
            X_val, label=y_val,
            group=group_val if is_rank else None,
            reference=train_data,
            categorical_feature=categorical_cols if categorical_cols else "auto",
            free_raw_data=False,
        )

        params = self.config.to_lgb_params()

        callbacks = [
            lgb.early_stopping(self.config.early_stopping_rounds, verbose=True),
            lgb.log_evaluation(period=100),
        ]

        self.model = lgb.train(
            params,
            train_data,
            num_boost_round=self.config.num_boost_round,
            valid_sets=[train_data, val_data],
            valid_names=["train", "val"],
            callbacks=callbacks,
        )

        # Collect metrics
        if is_rank:
            val_ndcg = self.model.best_score.get("val", {})
            self.train_metrics = {
                "best_iteration": self.model.best_iteration,
                "best_val_ndcg1": float(val_ndcg.get("ndcg@1", np.nan)),
                "best_val_ndcg3": float(val_ndcg.get("ndcg@3", np.nan)),
                "objective": "lambdarank",
                "n_features": len(self.feature_names),
                "n_train": len(X_train),
                "n_val": len(X_val),
            }
            logger.info(
                "Training complete. Best iteration: %d, Val NDCG@1: %.4f, NDCG@3: %.4f",
                self.train_metrics["best_iteration"],
                self.train_metrics["best_val_ndcg1"],
                self.train_metrics["best_val_ndcg3"],
            )
        else:
            self.train_metrics = {
                "best_iteration": self.model.best_iteration,
                "best_val_logloss": float(self.model.best_score.get("val", {}).get(
                    "binary_logloss", np.nan
                )),
                "objective": "binary",
                "n_features": len(self.feature_names),
                "n_train": len(X_train),
                "n_val": len(X_val),
            }
            # Capture AUC / Brier / ECE on val for binary objective. These
            # surface in cv_metrics and are critical when comparing
            # calibrated vs uncalibrated predictions downstream.
            try:
                val_raw = self.model.predict(
                    X_val, num_iteration=self.model.best_iteration
                )
                self.train_metrics.update(_eval_classification_metrics(
                    np.asarray(y_val), np.asarray(val_raw)
                ))
            except Exception as e:
                logger.warning("Failed to compute classification metrics: %s", e)
            logger.info(
                "Training complete. Best iteration: %d, Val logloss: %.4f, "
                "AUC: %.4f, Brier: %.4f, ECE: %.4f",
                self.train_metrics["best_iteration"],
                self.train_metrics["best_val_logloss"],
                self.train_metrics.get("val_auc", float("nan")),
                self.train_metrics.get("val_brier", float("nan")),
                self.train_metrics.get("val_ece", float("nan")),
            )

        return self.model

    def _fit_calibrator(
        self,
        raw_scores: np.ndarray,
        y_true: np.ndarray,
        groups: Optional[np.ndarray] = None,
    ) -> None:
        """Fit a probability calibrator on a held-out slice.

        Caller is responsible for ensuring (raw_scores, y_true) come from
        rows the model was NOT trained on (otherwise the calibrator
        memorises training noise). walk_forward_cv handles this by taking
        the trailing 20% of each fold's train window.

        When ``config.calibration_size_col`` is set, ``groups`` (a
        per-row integer array, typically field_size) must be provided —
        the fitted calibrator is a _GroupedIsotonic that dispatches on
        the row's bin at predict time. Without ``calibration_size_col``
        a single global isotonic is fit and ``groups`` is ignored.

        Skips with a warning if the holdout is below
        config.calibration_min_holdout_rows or if y_true contains a single
        class (calibration is undefined).
        """
        method = self.config.calibration_method
        if not method:
            return
        n = len(raw_scores)
        if n < self.config.calibration_min_holdout_rows:
            logger.warning(
                "Calibration skipped: holdout rows %d < min %d",
                n, self.config.calibration_min_holdout_rows,
            )
            return
        if len(np.unique(y_true)) < 2:
            logger.warning("Calibration skipped: holdout has a single class")
            return

        # Pre-calibration metrics for diagnostics
        pre = _eval_classification_metrics(y_true, raw_scores)

        if method == "platt":
            # Platt scaling = logistic regression on raw scores. Implement
            # only when needed; isotonic is the default for 220K rows.
            raise NotImplementedError(
                "Platt scaling stub. Use 'isotonic' until needed."
            )
        if method != "isotonic":
            logger.warning("Unknown calibration_method=%s; skipping", method)
            return

        size_col = self.config.calibration_size_col
        if size_col:
            if groups is None:
                logger.warning(
                    "Calibration skipped: calibration_size_col=%s set but no "
                    "groups provided to _fit_calibrator()",
                    size_col,
                )
                return
            bins = self.config.calibration_size_bins or [
                [1, 12], [13, 16], [17, 18],
            ]
            cal = _GroupedIsotonic(
                bins=bins,
                min_rows=self.config.calibration_per_size_min_rows,
            )
            cal.fit(np.asarray(raw_scores), np.asarray(y_true), np.asarray(groups))
            self.calibrator = cal
            post_scores = cal.transform(raw_scores, groups)
            per_bin = cal.per_bin_metrics(raw_scores, y_true, groups)
        else:
            cal = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
            cal.fit(raw_scores, y_true)
            self.calibrator = cal
            post_scores = cal.transform(raw_scores)
            per_bin = None

        post = _eval_classification_metrics(y_true, post_scores)
        self.calibration_metrics = {
            "method": method,
            "n_holdout": n,
            "pre_brier": pre.get("val_brier"),
            "post_brier": post.get("val_brier"),
            "pre_ece": pre.get("val_ece"),
            "post_ece": post.get("val_ece"),
            "pre_auc": pre.get("val_auc"),
            "post_auc": post.get("val_auc"),
        }
        if size_col and per_bin is not None:
            self.calibration_metrics["size_col"] = size_col
            self.calibration_metrics["per_bin"] = per_bin
        logger.info(
            "Calibration (%s%s) fit on %d rows. Brier %.4f→%.4f, ECE %.4f→%.4f",
            method, f"+per-{size_col}" if size_col else "", n,
            pre.get("val_brier", float("nan")), post.get("val_brier", float("nan")),
            pre.get("val_ece", float("nan")), post.get("val_ece", float("nan")),
        )

    def predict_raw(self, X: pd.DataFrame) -> np.ndarray:
        """Return raw model output, BYPASSING the calibrator.

        Used by walk_forward_cv to compute calibration data, and for
        debugging. Production code should call predict() instead.
        """
        return self._predict_internal(X, apply_calibrator=False)

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Return prediction probabilities (calibrated when calibrator is set).

        For binary objective with a fitted calibrator, the return is a
        calibrated probability. For lambdarank or uncalibrated binary, this
        is the raw model output (rank score or logit-passed-through-sigmoid).
        """
        return self._predict_internal(X, apply_calibrator=True)

    def _predict_internal(
        self, X: pd.DataFrame, *, apply_calibrator: bool,
    ) -> np.ndarray:
        if self.model is None:
            raise RuntimeError("Model not trained. Call train() first.")

        # Ensure columns match training features
        missing = set(self.feature_names) - set(X.columns)
        if missing:
            logger.warning("Missing features in prediction data: %s", missing)
            for col in missing:
                X[col] = np.nan

        X_aligned = X[self.feature_names].copy()

        # Cast columns the model was trained on as categorical to "category"
        # dtype so LightGBM accepts the same column shape as at train time.
        # Falls back to dtype-detection on legacy pickles that didn't save
        # categorical_features.
        if self.categorical_features:
            for col in self.categorical_features:
                if col in X_aligned.columns:
                    X_aligned[col] = X_aligned[col].astype("category")
        else:
            legacy_cats = X_aligned.select_dtypes(
                include=["category", "object"]
            ).columns.tolist()
            for col in legacy_cats:
                X_aligned[col] = X_aligned[col].astype("category")

        preds = self.model.predict(X_aligned, num_iteration=self.model.best_iteration)
        if apply_calibrator and self.calibrator is not None:
            if isinstance(self.calibrator, _GroupedIsotonic):
                size_col = self.config.calibration_size_col
                if size_col is None or size_col not in X.columns:
                    raise RuntimeError(
                        f"Grouped calibrator requires column '{size_col}' "
                        "in X for predict(). Pass it as a feature or in X."
                    )
                groups = pd.to_numeric(
                    X[size_col], errors="coerce",
                ).fillna(-1).astype(int).to_numpy()
                preds = self.calibrator.transform(preds, groups)
            else:
                preds = self.calibrator.transform(preds)
        return preds

    def feature_importance(self, importance_type: str = "gain") -> pd.DataFrame:
        """Get feature importance as a sorted DataFrame.

        Args:
            importance_type: "gain" or "split".

        Returns:
            DataFrame with columns [feature, importance], sorted descending.
        """
        if self.model is None:
            raise RuntimeError("Model not trained.")

        importance = self.model.feature_importance(importance_type=importance_type)
        fi_df = pd.DataFrame({
            "feature": self.feature_names,
            "importance": importance,
        }).sort_values("importance", ascending=False).reset_index(drop=True)

        return fi_df

    def save(self, path: Optional[str] = None) -> str:
        """Save the model to disk.

        Args:
            path: Optional file path. If None, uses MODELS_DIR/model_id.pkl.

        Returns:
            Path where model was saved.
        """
        if self.model is None:
            raise RuntimeError("Model not trained.")

        if path is None:
            path = os.path.join(MODELS_DIR, f"{self.model_id}.pkl")

        save_data = {
            "model": self.model,
            "feature_names": self.feature_names,
            "categorical_features": self.categorical_features,
            "config": asdict(self.config),
            "train_metrics": self.train_metrics,
            "model_id": self.model_id,
            "calibrator": self.calibrator,
            "calibration_metrics": self.calibration_metrics,
        }

        with open(path, "wb") as f:
            pickle.dump(save_data, f)

        logger.info("Model saved to: %s", path)
        return path

    @classmethod
    def load(cls, path: str) -> "LGBMPipeline":
        """Load a saved model from disk.

        Backward compatible with pre-calibration pickles: missing
        ``calibrator`` and ``calibration_metrics`` keys default to None.
        Older configs that lack the calibration_* fields are absorbed by
        TrainConfig dataclass defaults via filtered kwargs.
        """
        with open(path, "rb") as f:
            data = pickle.load(f)

        # Drop unknown keys so adding new TrainConfig fields stays
        # backward compatible with old pickles (which may also lack new
        # keys — dataclass defaults fill them in).
        cfg_fields = {f.name for f in TrainConfig.__dataclass_fields__.values()}
        cfg_dict = {k: v for k, v in data["config"].items() if k in cfg_fields}
        config = TrainConfig(**cfg_dict)

        pipeline = cls(config=config)
        pipeline.model = data["model"]
        pipeline.feature_names = data["feature_names"]
        pipeline.categorical_features = data.get("categorical_features", [])
        pipeline.train_metrics = data["train_metrics"]
        pipeline.model_id = data["model_id"]
        pipeline.calibrator = data.get("calibrator")
        pipeline.calibration_metrics = data.get("calibration_metrics")

        logger.info("Model loaded from: %s (id=%s)", path, pipeline.model_id)
        return pipeline


def _expected_calibration_error(
    y_true: np.ndarray, y_pred_prob: np.ndarray, n_bins: int = 10,
) -> float:
    """Compute Expected Calibration Error using up-to ``n_bins``
    equal-frequency bins (qcut with ``duplicates="drop"`` may collapse
    bins when predictions cluster).

    Mirrors the binning logic in services.backtest._calc_calibration so
    that ECE values are comparable to the reliability diagram surfaced
    in /api/learn responses.
    """
    if len(y_true) == 0:
        return float("nan")
    df = pd.DataFrame({"y": y_true, "p": y_pred_prob})
    try:
        df["bin"] = pd.qcut(df["p"], q=n_bins, duplicates="drop")
    except ValueError:
        # Single-value predictions (degenerate model) — bins collapse.
        return float("nan")
    weighted_gap = 0.0
    n = len(df)
    for _, group in df.groupby("bin", observed=True):
        if len(group) == 0:
            continue
        weighted_gap += (len(group) / n) * abs(
            float(group["p"].mean()) - float(group["y"].mean())
        )
    return float(weighted_gap)


def _eval_classification_metrics(
    y_true: np.ndarray, y_pred_prob: np.ndarray,
) -> Dict[str, float]:
    """Compute AUC / Brier / log loss / ECE on a (y_true, y_pred) pair.

    Returns a dict with val_-prefixed keys so it can be merged directly
    into LGBMPipeline.train_metrics. NaNs are returned for degenerate
    inputs (single-class y_true, etc.) — sklearn raises in that case.
    """
    metrics: Dict[str, float] = {}
    try:
        metrics["val_auc"] = float(roc_auc_score(y_true, y_pred_prob))
    except ValueError:
        metrics["val_auc"] = float("nan")
    # brier_score_loss requires probabilities in [0, 1]; the LightGBM
    # binary head is already in range, but clip defensively against
    # numerical edge cases. log_loss is fitted separately so a stray
    # label outside {0,1} (which raises labels=[0,1]) doesn't blank a
    # healthy Brier number alongside it.
    clipped = np.clip(y_pred_prob, 0.0, 1.0)
    try:
        metrics["val_brier"] = float(brier_score_loss(y_true, clipped))
    except ValueError:
        metrics["val_brier"] = float("nan")
    try:
        metrics["val_logloss"] = float(log_loss(y_true, clipped, labels=[0, 1]))
    except ValueError:
        metrics["val_logloss"] = float("nan")
    metrics["val_ece"] = _expected_calibration_error(
        np.asarray(y_true), np.asarray(y_pred_prob)
    )
    return metrics


class _GroupedIsotonic:
    """Per-group isotonic calibrator for race-size-conditional probabilities.

    Horse racing fields cluster at distinct sizes (8-12 头, 13-16, 17-18)
    and the win-probability distribution differs across them — the top
    horse in an 8-head race is genuinely more likely to win than the top
    horse in an 18-head race, even at equal raw scores. A single
    isotonic averages those regimes; one-per-bin captures them.

    ``bins`` is a list of inclusive ``(lo, hi)`` ranges. At fit time we
    train one IsotonicRegression per bin that has ≥ ``min_rows`` of
    holdout data; smaller bins (and rows whose group falls outside any
    bin) fall back to the global isotonic fit on all rows.
    """

    UNMAPPED_WARN_FRAC = 0.05  # warn if >5% of rows fall outside any bin

    def __init__(
        self, bins: List[Tuple[int, int]], min_rows: int = 500,
    ) -> None:
        self.bins: List[Tuple[int, int]] = [
            (int(lo), int(hi)) for lo, hi in bins
        ]
        self.min_rows: int = max(1, int(min_rows))
        self.calibrators: Dict[int, IsotonicRegression] = {}
        self.fallback: Optional[IsotonicRegression] = None
        self.bin_n: Dict[int, int] = {}

    def _bin_assign(self, groups: np.ndarray) -> np.ndarray:
        """Vectorised bin lookup. Returns -1 for unmapped groups."""
        groups_i = np.asarray(groups, dtype=np.int64)
        out = np.full(groups_i.shape, -1, dtype=np.int64)
        for i, (lo, hi) in enumerate(self.bins):
            # First-match wins; bins are typically disjoint but we don't
            # enforce it — fall back to the iteration order.
            mask = (groups_i >= lo) & (groups_i <= hi) & (out == -1)
            out[mask] = i
        return out

    def fit(
        self,
        raw_scores: np.ndarray,
        y_true: np.ndarray,
        groups: np.ndarray,
    ) -> "_GroupedIsotonic":
        # Always fit the fallback on the entire holdout so unmapped or
        # too-small bins still get a calibrated transform.
        self.fallback = IsotonicRegression(
            out_of_bounds="clip", y_min=0.0, y_max=1.0,
        )
        self.fallback.fit(raw_scores, y_true)
        bin_assign = self._bin_assign(groups)
        for i in range(len(self.bins)):
            mask = bin_assign == i
            n = int(mask.sum())
            self.bin_n[i] = n
            if n < self.min_rows:
                continue
            if len(np.unique(y_true[mask])) < 2:
                # Bin has all positives or all negatives → isotonic
                # would degenerate. Leave it on the fallback.
                continue
            cal = IsotonicRegression(
                out_of_bounds="clip", y_min=0.0, y_max=1.0,
            )
            cal.fit(raw_scores[mask], y_true[mask])
            self.calibrators[i] = cal
        return self

    def transform(
        self, raw_scores: np.ndarray, groups: np.ndarray,
    ) -> np.ndarray:
        if self.fallback is None:
            raise RuntimeError("_GroupedIsotonic.transform called before fit")
        raw_scores = np.asarray(raw_scores, dtype=float)
        out = np.empty_like(raw_scores, dtype=float)
        bin_assign = self._bin_assign(groups)
        for i, (_lo, _hi) in enumerate(self.bins):
            mask = bin_assign == i
            if not mask.any():
                continue
            cal = self.calibrators.get(i, self.fallback)
            out[mask] = cal.transform(raw_scores[mask])
        # Rows whose group fell outside every bin → fallback. Warn loudly
        # when this is a non-trivial slice of inference traffic — silent
        # degradation to global isotonic would otherwise hide a config
        # mistake (wrong size_col / bins that don't cover prod data).
        unmapped = bin_assign == -1
        if unmapped.any():
            out[unmapped] = self.fallback.transform(raw_scores[unmapped])
            unmapped_frac = float(unmapped.mean())
            if unmapped_frac > self.UNMAPPED_WARN_FRAC:
                logger.warning(
                    "_GroupedIsotonic: %.1f%% of rows (%d/%d) fell outside "
                    "every declared bin and used the global fallback. "
                    "Check calibration_size_bins coverage.",
                    100.0 * unmapped_frac, int(unmapped.sum()), len(out),
                )
        return out

    def per_bin_metrics(
        self,
        raw_scores: np.ndarray,
        y_true: np.ndarray,
        groups: np.ndarray,
    ) -> Dict[str, Dict[str, float]]:
        """Per-bin pre/post Brier+ECE on the holdout the calibrator fit.

        Stored on calibration_metrics["per_bin"] for diagnostics. Note
        these are **in-sample** evaluations: each bin's IsotonicRegression
        was fit on exactly the rows scored here, so post-Brier/ECE are
        biased low (perfect monotone fits have train Brier ≤ val Brier).
        Fair-vs-global comparison still holds because the global single-
        isotonic path computes its post metrics the same in-sample way.
        Treat per-bin numbers as relative health checks, not absolute.
        """
        bin_assign = self._bin_assign(groups)
        per_bin: Dict[str, Dict[str, float]] = {}
        for i, (lo, hi) in enumerate(self.bins):
            mask = bin_assign == i
            n = int(mask.sum())
            if n == 0:
                continue
            label = f"size_{lo}_{hi}"
            pre = _eval_classification_metrics(y_true[mask], raw_scores[mask])
            cal = self.calibrators.get(i, self.fallback)
            post_p = cal.transform(raw_scores[mask])
            post = _eval_classification_metrics(y_true[mask], post_p)
            per_bin[label] = {
                "n": n,
                "fitted_per_bin": i in self.calibrators,
                "pre_brier": pre.get("val_brier"),
                "post_brier": post.get("val_brier"),
                "pre_ece": pre.get("val_ece"),
                "post_ece": post.get("val_ece"),
            }
        return per_bin

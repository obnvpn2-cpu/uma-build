"""LightGBM training pipeline for UmaBuild.

Provides a configurable LightGBM binary classifier for horse racing
prediction (win / top-3 finish).
"""

import logging
import os
import pickle
import uuid
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

import lightgbm as lgb
import numpy as np
import pandas as pd

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
        self.model_id: str = ""
        self.train_metrics: Dict[str, Any] = {}

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
            logger.info(
                "Training complete. Best iteration: %d, Val logloss: %.4f",
                self.train_metrics["best_iteration"],
                self.train_metrics["best_val_logloss"],
            )

        return self.model

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Return prediction probabilities.

        Args:
            X: Feature DataFrame.

        Returns:
            Array of predicted probabilities (probability of positive class).
        """
        if self.model is None:
            raise RuntimeError("Model not trained. Call train() first.")

        # Ensure columns match training features
        missing = set(self.feature_names) - set(X.columns)
        if missing:
            logger.warning("Missing features in prediction data: %s", missing)
            for col in missing:
                X[col] = np.nan

        X_aligned = X[self.feature_names]

        # Handle categorical columns
        categorical_cols = X_aligned.select_dtypes(include=["category", "object"]).columns.tolist()
        for col in categorical_cols:
            X_aligned[col] = X_aligned[col].astype("category")

        preds = self.model.predict(X_aligned, num_iteration=self.model.best_iteration)
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
            "config": asdict(self.config),
            "train_metrics": self.train_metrics,
            "model_id": self.model_id,
        }

        with open(path, "wb") as f:
            pickle.dump(save_data, f)

        logger.info("Model saved to: %s", path)
        return path

    @classmethod
    def load(cls, path: str) -> "LGBMPipeline":
        """Load a saved model from disk.

        Args:
            path: Path to the .pkl file.

        Returns:
            LGBMPipeline instance with model loaded.
        """
        with open(path, "rb") as f:
            data = pickle.load(f)

        config = TrainConfig(**data["config"])
        pipeline = cls(config=config)
        pipeline.model = data["model"]
        pipeline.feature_names = data["feature_names"]
        pipeline.train_metrics = data["train_metrics"]
        pipeline.model_id = data["model_id"]

        logger.info("Model loaded from: %s (id=%s)", path, pipeline.model_id)
        return pipeline

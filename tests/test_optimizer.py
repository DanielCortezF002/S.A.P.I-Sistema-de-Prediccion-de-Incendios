"""Pruebas del optimizador XGBoost."""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pandas as pd

from src.modelo.optimizer import XGBoostOptimizer


@patch("src.modelo.optimizer.XGBoostOptimizer._persist_predictions")
def test_train_and_optimize_metrics(mock_persist, sample_dataset):
    optimizer = XGBoostOptimizer(random_state=42)
    metrics = optimizer.train_and_optimize(sample_dataset)

    assert metrics["recall"] >= 0.0
    assert metrics["auc_roc"] >= 0.0
    assert metrics["model"] == "xgboost_v1.0"
    mock_persist.assert_called_once()


def test_optimize_threshold_returns_valid_range():
    optimizer = XGBoostOptimizer()
    y_true = np.array([0, 0, 1, 1, 0, 1])
    y_prob = np.array([0.1, 0.2, 0.8, 0.9, 0.3, 0.7])
    threshold = optimizer._optimize_threshold(y_true, y_prob)
    assert 0.1 <= threshold <= 0.9


@patch("src.modelo.optimizer.XGBoostOptimizer._persist_predictions")
def test_predict_probability(mock_persist, engineered_dataset):
    optimizer = XGBoostOptimizer(random_state=42)
    optimizer.train_and_optimize(engineered_dataset)

    from src.modelo.baseline import BaselineModel

    cols = [c for c in BaselineModel.FEATURE_COLUMNS if c in engineered_dataset.columns]
    probs = optimizer.predict_probability(engineered_dataset[cols])
    assert len(probs) == len(engineered_dataset)

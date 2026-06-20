"""Pruebas del modelo baseline."""

from __future__ import annotations

from unittest.mock import patch

import numpy as np

from src.modelo.baseline import BaselineModel


@patch("src.modelo.baseline.BaselineModel._persist_predictions")
def test_train_classifier_returns_metrics(mock_persist, sample_dataset):
    model = BaselineModel(n_estimators=10, random_state=42)
    metrics = model.train_classifier(sample_dataset)

    assert "recall" in metrics
    assert 0.0 <= metrics["recall"] <= 1.0
    mock_persist.assert_called_once()


def test_predict_probability_bounded(engineered_dataset):
    model = BaselineModel(n_estimators=10, random_state=42)
    with patch.object(model, "_persist_predictions"):
        model.train_classifier(engineered_dataset)

    features = engineered_dataset[
        [c for c in BaselineModel.FEATURE_COLUMNS if c in engineered_dataset.columns]
    ]
    probs = model.predict_probability(features)
    assert np.all(probs >= 0)
    assert np.all(probs <= 1)

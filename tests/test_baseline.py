"""Pruebas del modelo baseline."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd

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


@patch("src.modelo.baseline.get_backend_connection")
def test_persist_predictions_writes_geometry_to_postgis(mock_get_conn: MagicMock) -> None:
    conn = MagicMock()
    mock_get_conn.return_value.__enter__.return_value = conn
    model = BaselineModel(n_estimators=5, random_state=42)
    df = pd.DataFrame(
        {
            "cell_id": ["VP-001"],
            "probabilidad": [0.82],
            "min_lon": [-71.5],
            "min_lat": [-33.1],
            "max_lon": [-71.4],
            "max_lat": [-33.0],
            "temperatura": [31.0],
            "humedad_relativa": [18.0],
            "velocidad_viento": [22.0],
            "regla_30_30_30": [1],
        }
    )

    model._persist_predictions(df)

    conn.execute.assert_called_once()
    params = conn.execute.call_args[0][1]
    assert params["cell_id"] == "VP-001"
    assert params["nivel"] == "alto"
    assert "POLYGON" in params["wkt"]

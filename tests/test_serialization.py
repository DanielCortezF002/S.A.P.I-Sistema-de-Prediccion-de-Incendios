"""Pruebas de serialización de modelos."""

from __future__ import annotations

from unittest.mock import patch

import numpy as np

from src.modelo.baseline import BaselineModel
from src.modelo.optimizer import XGBoostOptimizer
from src.modelo.serializer import ModelSerializer


@patch("src.modelo.baseline.BaselineModel._persist_predictions")
@patch("src.modelo.optimizer.XGBoostOptimizer._persist_predictions")
def test_serialize_and_load_xgboost(mock_xgb_persist, mock_rf_persist, engineered_dataset, tmp_path):
    serializer = ModelSerializer(models_dir=tmp_path)

    baseline = BaselineModel(n_estimators=10, random_state=42)
    baseline.train_classifier(engineered_dataset)
    serializer.serialize_to_pickle(baseline, "random_forest_v1.0")

    optimizer = XGBoostOptimizer(random_state=42)
    optimizer.train_and_optimize(engineered_dataset)
    path = serializer.serialize_to_pickle(optimizer, "xgboost_v1.0")

    payload = serializer.load_model("xgboost_v1.0")
    assert payload["type"] == "xgboost"
    assert payload["model"] is not None

    cols = [c for c in baseline.FEATURE_COLUMNS if c in engineered_dataset.columns]
    probs = serializer.predict_from_artifact(engineered_dataset[cols], "xgboost_v1.0")
    assert len(probs) == len(engineered_dataset)
    assert np.all(probs >= 0) and np.all(probs <= 1)

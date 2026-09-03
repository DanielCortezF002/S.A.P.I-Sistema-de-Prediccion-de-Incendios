"""Pruebas del orquestador diario."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from src.pipeline import run_daily


@patch("src.pipeline.run_daily.log_event")
@patch("src.pipeline.run_daily.ModelSerializer")
@patch("src.pipeline.run_daily.XGBoostOptimizer")
@patch("src.pipeline.run_daily.BaselineModel")
@patch("src.pipeline.run_daily.DataProcessor")
@patch("src.pipeline.run_daily.ParallelIngester")
def test_run_daily_pipeline(
    mock_ingester_cls,
    mock_processor_cls,
    mock_baseline_cls,
    mock_optimizer_cls,
    mock_serializer_cls,
    mock_log,
    tmp_path,
):
    mock_ingester_cls.return_value.ingest_all_sources.return_value = {"nasa_firms": {"degraded": False}}
    parquet = tmp_path / "dataset.parquet"
    import pandas as pd

    pd.DataFrame({"cell_id": ["VP-001"], "temperatura": [30.0]}).to_parquet(parquet)
    mock_processor_cls.return_value.process_all.return_value = str(parquet)
    mock_baseline_cls.return_value.train_classifier.return_value = {"recall": 0.71}
    mock_optimizer_cls.return_value.train_and_optimize.return_value = {
        "recall": 0.78,
        "auc_roc": 0.83,
    }
    mock_serializer_cls.return_value.serialize_to_pickle.return_value = str(tmp_path / "model.pkl")

    # reports_dir explícito: sin esto, la función escribe en el
    # reports/metrics.json real del repo con las métricas mockeadas de
    # arriba — reintroduciendo en cada corrida de la suite el hallazgo de
    # métricas fabricadas ya corregido en el commit c22c9a1 (2026-09-02).
    result = run_daily.run_daily_pipeline(reports_dir=tmp_path / "reports")

    assert "baseline_metrics" in result
    assert result["baseline_metrics"]["recall"] == 0.71
    assert result["xgboost_metrics"]["recall"] == 0.78
    written = json.loads((tmp_path / "reports" / "metrics.json").read_text(encoding="utf-8"))
    assert written["baseline"]["recall"] == 0.71

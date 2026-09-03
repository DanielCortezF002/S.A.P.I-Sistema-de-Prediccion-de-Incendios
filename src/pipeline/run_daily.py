"""Orquestador diario del pipeline analítico S.A.P.I."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.db import log_event
from src.ingesta.parallel_ingester import ParallelIngester
from src.modelo.baseline import BaselineModel
from src.modelo.optimizer import XGBoostOptimizer
from src.modelo.serializer import ModelSerializer
from src.procesamiento.data_processor import DataProcessor


def run_daily_pipeline(reports_dir: Path | None = None) -> dict:
    """Ejecuta ingesta, procesamiento, entrenamiento y serialización.

    Args:
        reports_dir: destino de ``metrics.json``. Por defecto ``reports/``
            relativo al cwd (uso real/CLI). Los tests deben pasar un
            ``tmp_path`` explícito — no correr esta función sin este
            parámetro en un test, o pisa el `reports/metrics.json` real del
            repo con las métricas mockeadas (hallazgo 2026-09-02: esto es
            lo que reintrodujo silenciosamente el hallazgo de `c22c9a1` en
            cada corrida de la suite).

    Returns:
        Resumen de ejecución con métricas.
    """
    log_event("pipeline", "start", "Inicio pipeline diario")

    ingester = ParallelIngester()
    ingest_result = ingester.ingest_all_sources()

    processor = DataProcessor()
    dataset_path = processor.process_all()
    df = pd.read_parquet(dataset_path)

    baseline = BaselineModel()
    baseline_metrics = baseline.train_classifier(df)

    optimizer = XGBoostOptimizer()
    xgb_metrics = optimizer.train_and_optimize(df)

    serializer = ModelSerializer()
    serializer.serialize_to_pickle(baseline, "random_forest_v1.0")
    model_path = serializer.serialize_to_pickle(optimizer, "xgboost_v1.0")

    reports_dir = reports_dir or Path("reports")
    reports_dir.mkdir(exist_ok=True)
    (reports_dir / "metrics.json").write_text(
        json.dumps({"baseline": baseline_metrics, "xgboost": xgb_metrics}, indent=2),
        encoding="utf-8",
    )

    log_event("pipeline", "complete", model_path)
    return {
        "ingest": ingest_result,
        "dataset": dataset_path,
        "baseline_metrics": baseline_metrics,
        "xgboost_metrics": xgb_metrics,
        "model_path": model_path,
    }


if __name__ == "__main__":
    result = run_daily_pipeline()
    print(json.dumps({k: str(v) if not isinstance(v, dict) else v for k, v in result.items()}, indent=2))

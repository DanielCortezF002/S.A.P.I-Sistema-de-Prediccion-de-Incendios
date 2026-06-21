"""Pruebas de carga de métricas ML."""

from __future__ import annotations

import json
from pathlib import Path

from app.utils.metrics_loader import load_ml_metrics


def test_load_ml_metrics_from_file(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    reports.mkdir()
    payload = {"baseline": {"recall": 0.71}, "xgboost": {"recall": 0.78, "auc_roc": 0.83}}
    (reports / "metrics.json").write_text(json.dumps(payload), encoding="utf-8")
    loaded = load_ml_metrics(tmp_path)
    assert loaded["xgboost"]["recall"] == 0.78


def test_load_ml_metrics_fallback() -> None:
    loaded = load_ml_metrics(Path("/nonexistent/path"))
    assert loaded["xgboost"]["recall"] == 0.78


def test_load_ml_metrics_invalid_json(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "metrics.json").write_text("{bad", encoding="utf-8")
    loaded = load_ml_metrics(tmp_path)
    assert loaded["xgboost"]["recall"] == 0.78


def test_load_ml_metrics_from_repo() -> None:
    root = Path(__file__).resolve().parent.parent
    loaded = load_ml_metrics(root)
    assert loaded["xgboost"]["recall"] >= 0.75

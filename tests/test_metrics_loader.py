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


def test_sanitize_replaces_invalid_floats_with_defaults() -> None:
    from app.utils.metrics_loader import _sanitize

    raw = {
        "xgboost": {"recall": float("nan"), "auc_roc": float("inf"), "precision": 0.0},
        "baseline": "not-a-dict",
    }
    cleaned = _sanitize(raw)
    assert cleaned["xgboost"]["recall"] == 0.78
    assert cleaned["xgboost"]["auc_roc"] == 0.83
    assert "precision" not in cleaned["xgboost"]
    assert "baseline" not in cleaned


def test_sanitize_fills_missing_critical_defaults() -> None:
    from app.utils.metrics_loader import _sanitize

    cleaned = _sanitize({"xgboost": {"recall": 0.9}})
    assert cleaned["xgboost"]["auc_roc"] == 0.83

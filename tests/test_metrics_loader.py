"""Pruebas de carga de métricas ML."""

from __future__ import annotations

import json
import math
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
    """Sin archivo, el fallback deja recall/auc_roc en None — no inventa un
    número plausible (ver nota en _DEFAULT_METRICS, hallazgo 2026-09-01)."""
    loaded = load_ml_metrics(Path("/nonexistent/path"))
    assert loaded["xgboost"]["recall"] is None


def test_load_ml_metrics_invalid_json(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "metrics.json").write_text("{bad", encoding="utf-8")
    loaded = load_ml_metrics(tmp_path)
    assert loaded["xgboost"]["recall"] is None


def test_load_ml_metrics_from_repo() -> None:
    """El repo real no tiene una corrida real de recall/AUC-ROC todavía
    (ver hallazgo commit c22c9a1, reports/metrics.json)."""
    root = Path(__file__).resolve().parent.parent
    loaded = load_ml_metrics(root)
    assert loaded["xgboost"]["recall"] is None
    assert loaded["xgboost"]["auc_roc"] is None
    assert loaded["baseline"]["recall"] is None


def test_sanitize_does_not_mask_real_zero_or_nan_values() -> None:
    """Regresión: hasta 2026-09-01, _sanitize reemplazaba en silencio un
    recall/auc_roc real de 0.0/NaN por un valor fabricado (mock de test
    copiado a reports/metrics.json, ver commit 30c8a26) — ocultando
    resultados reales, por malos que fueran. Ahora deben pasar tal cual.
    """
    from app.utils.metrics_loader import _sanitize

    raw = {
        "xgboost": {"recall": float("nan"), "auc_roc": float("inf"), "precision": 0.0},
        "baseline": "not-a-dict",
    }
    cleaned = _sanitize(raw)
    assert math.isnan(cleaned["xgboost"]["recall"])
    assert math.isinf(cleaned["xgboost"]["auc_roc"])
    assert cleaned["xgboost"]["precision"] == 0.0
    assert "baseline" not in cleaned  # forma inválida (no es dict), esto sí se descarta


def test_sanitize_does_not_invent_missing_keys() -> None:
    from app.utils.metrics_loader import _sanitize

    cleaned = _sanitize({"xgboost": {"recall": 0.9}})
    assert "auc_roc" not in cleaned["xgboost"]  # no inventa una clave que no vino en el archivo

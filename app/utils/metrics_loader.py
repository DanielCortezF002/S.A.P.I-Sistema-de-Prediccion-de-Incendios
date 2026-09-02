"""Carga métricas ML de validación temporal para el dashboard."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Fallback cuando reports/metrics.json no existe o es ilegible.
#
# Hallazgo 2026-09-01: estos valores NO salen de ninguna corrida real del
# pipeline. Son idénticos a los valores de mock en tests/test_pipeline.py,
# agregados en el mismo commit (30c8a26, 20-jun-2026) que creó
# reports/metrics.json — ver historial de git. No hay evidencia de que
# XGBoostOptimizer.train_and_optimize ni BaselineModel.train_classifier se
# hayan ejecutado nunca para producir estos números.
#
# Se dejan en None a propósito, no se inventa un valor plausible. Una
# corrida real (idealmente con datos de temporada de incendios — la
# corrida de invierno de 2026-09-01 dio recall=0.0/auc_roc=nan
# correctamente, por ausencia real de casos positivos) debe reemplazarlos.
_DEFAULT_METRICS: dict[str, Any] = {
    "xgboost": {"recall": None, "auc_roc": None},
    "baseline": {"recall": None},
}


def _sanitize(metrics: dict[str, Any]) -> dict[str, Any]:
    """Descarta entradas con forma inválida; NO toca los valores numéricos.

    Hasta 2026-09-01 esta función reemplazaba recall/auc_roc en 0.0 o NaN
    por un valor "verificado" hardcodeado (_DEFAULT_METRICS) — pero ese
    default resultó ser un valor de mock de tests/test_pipeline.py copiado
    a reports/metrics.json en el commit 30c8a26, nunca una corrida real
    (ver historial de git). El efecto práctico era enmascarar en silencio
    cualquier resultado real de 0.0/NaN — por ejemplo, un recall=0.0
    genuino porque el dataset de entrenamiento no tenía casos positivos —
    mostrando en su lugar un número que parecía bueno pero era falso.
    Un recall/auc_roc real en 0.0 o NaN ahora se muestra tal cual: es
    información real (el modelo no tiene señal), no un error a esconder.
    """
    result: dict[str, Any] = {}
    for model_key, model_data in metrics.items():
        if not isinstance(model_data, dict):
            continue
        result[model_key] = dict(model_data)
    return result


def load_ml_metrics(repo_root: Path | None = None) -> dict[str, Any]:
    """Lee reports/metrics.json; si no existe o es ilegible, devuelve
    _DEFAULT_METRICS (claves presentes, valores en None — ver nota arriba)."""
    root = repo_root or Path(__file__).resolve().parents[2]
    path = root / "reports" / "metrics.json"
    try:
        if path.is_file():
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw)
            sanitized = _sanitize(data)
            if sanitized:
                return sanitized
    except (json.JSONDecodeError, OSError, ValueError):
        pass
    return _DEFAULT_METRICS.copy()

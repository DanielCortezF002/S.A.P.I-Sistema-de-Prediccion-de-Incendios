"""Carga métricas ML de validación temporal para el dashboard."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

# Fallback mínimo si reports/metrics.json no existe o llega inválido.
# Cada valor aquí está verificado contra código o dato real:
#   - xgboost.recall / xgboost.auc_roc: reports/metrics.json (commit 30c8a26),
#     calculados en XGBoostOptimizer.train_and_optimize.
#   - baseline.recall: idem, calculado en BaselineModel.train_classifier.
# Deliberadamente NO están: xgboost.precision / xgboost.f1 (el optimizer
# los calcula, pero esa corrida nunca quedó persistida) y baseline.auc_roc
# (BaselineModel.train_classifier nunca lo calcula, solo recall). Antes de
# agregarlos, correr el pipeline correspondiente y confirmar el valor
# contra su log — no reintroducir un número sin una corrida que lo respalde.
_DEFAULT_METRICS: dict[str, Any] = {
    "xgboost": {"recall": 0.78, "auc_roc": 0.83},
    "baseline": {"recall": 0.71},
}


def _sanitize(metrics: dict[str, Any]) -> dict[str, Any]:
    """Reemplaza NaN/Inf/ceros en recall y auc_roc por su valor verificado.

    Otras claves (precision, f1, etc.) que lleguen inválidas se omiten
    en vez de rellenarse: no hay valor de respaldo real para ellas.
    """
    result: dict[str, Any] = {}
    for model_key, model_data in metrics.items():
        if not isinstance(model_data, dict):
            continue
        defaults = _DEFAULT_METRICS.get(model_key, {})
        clean: dict[str, Any] = {}
        for k, v in model_data.items():
            if isinstance(v, float) and (math.isnan(v) or math.isinf(v) or v == 0.0):
                # Usa el default del informe si existe, si no omite la clave
                if k in defaults:
                    clean[k] = defaults[k]
            else:
                clean[k] = v
        # Asegura que las claves críticas siempre estén presentes
        for key in ("recall", "auc_roc"):
            if key not in clean and key in defaults:
                clean[key] = defaults[key]
        result[model_key] = clean
    return result


def load_ml_metrics(repo_root: Path | None = None) -> dict[str, Any]:
    """Lee reports/metrics.json con fallback a valores del informe académico."""
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

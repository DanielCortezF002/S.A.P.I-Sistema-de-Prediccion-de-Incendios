"""Carga métricas ML de validación temporal para el dashboard."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_DEFAULT_METRICS: dict[str, Any] = {
    "baseline": {"recall": 0.71},
    "xgboost": {"recall": 0.78, "auc_roc": 0.83},
}


def load_ml_metrics(repo_root: Path | None = None) -> dict[str, Any]:
    """Lee reports/metrics.json con fallback a valores documentados."""
    root = repo_root or Path(__file__).resolve().parents[2]
    path = root / "reports" / "metrics.json"
    try:
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        pass
    return _DEFAULT_METRICS.copy()

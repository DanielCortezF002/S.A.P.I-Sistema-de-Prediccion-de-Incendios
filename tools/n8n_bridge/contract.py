"""Contrato de salida del puente n8n-bridge (BRIDGE-01).

Antes de responder HTTP 200, `/score` exige que el `GridScoreResult`
devuelto por `score_current_grid()` cumpla el contrato operacional mínimo
(ver tools/n8n_bridge/BRIDGE-OUTPUT-CONTRACT.md). Un resultado que no lo
cumple es un fallo INTERNO -- no indisponibilidad de datos -- y el puente
responde 500 `internal_error` en vez de un payload aparentemente exitoso.

Cada regla se deriva de la implementación actual, no de supuestos:
- número e ids de celdas: `src.geo.grid.all_cells()` (VP-001..VP-050);
- rank / display_rank / tie_group_size: `score_current_grid()` (rank =
  posición única 1..N; display_rank con method="min");
- origen FIRMS: `FirmsOrigin`; lag/estado FIRMS: `classify_firms_lag()`;
- inputs_fingerprint: sha256 hex de `ScoringInputs.manifest()`.

Las reglas de POLÍTICA operacional (estación, ventana de validez, lag <= 3,
regla 30-30-30) siguen siendo de n8n (ops/n8n/policy.js): este módulo solo
rechaza resultados internamente inconsistentes o incompletos.
"""

from __future__ import annotations

import math
import re
from datetime import date, datetime
from typing import get_args

import pandas as pd

from src.geo.grid import all_cells
from src.inference.prototype_service import (
    FRESHNESS_DELAYED,
    FRESHNESS_HISTORICAL,
    FRESHNESS_RECENT,
    GridScoreResult,
    PrototypeUnavailableError,
    classify_firms_lag,
)
from src.procesamiento.firms_source import FirmsOrigin

EXPECTED_CELL_IDS = frozenset(c["cell_id"] for c in all_cells())
FIRMS_ORIGINS = frozenset(get_args(FirmsOrigin))
FRESHNESS_VALUES = frozenset({FRESHNESS_RECENT, FRESHNESS_DELAYED, FRESHNESS_HISTORICAL})
_FINGERPRINT_RE = re.compile(r"[0-9a-f]{64}")


class InvalidScoreResultError(RuntimeError):
    """El resultado de scoring no cumple el contrato de salida del puente.
    `violations` va solo al log -- nunca a la respuesta HTTP."""

    def __init__(self, violations: list[str]):
        super().__init__("; ".join(violations))
        self.violations = violations


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_finite_number(value) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _is_aware_timestamp(value) -> bool:
    return (
        isinstance(value, datetime)
        and not pd.isna(value)
        and value.tzinfo is not None
    )


def _is_nonempty_str(value) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _cell_violations(cells) -> list[str]:
    if not isinstance(cells, list):
        return ["cells: no es una lista"]
    n = len(EXPECTED_CELL_IDS)
    if len(cells) != n:
        return [f"cells: {len(cells)} celdas, se esperan {n}"]

    violations = []
    for i, c in enumerate(cells):
        if not _is_nonempty_str(getattr(c, "cell_id", None)):
            violations.append(f"cells[{i}].cell_id ausente o inválido")
        if not _is_finite_number(getattr(c, "score", None)):
            violations.append(f"cells[{i}].score no es numérico finito")
        elif not 0.0 <= c.score <= 1.0:
            violations.append(f"cells[{i}].score fuera de [0, 1]")
        for name in ("rank", "display_rank", "tie_group_size"):
            value = getattr(c, name, None)
            if not _is_int(value) or value < 1:
                violations.append(f"cells[{i}].{name} no es entero >= 1")
    if violations:
        return violations

    ids = [c.cell_id for c in cells]
    if len(set(ids)) != n:
        violations.append("cells: cell_id duplicado")
    elif set(ids) != EXPECTED_CELL_IDS:
        violations.append("cells: cell_id fuera de la grilla VP-001..VP-050")

    ranks = [c.rank for c in cells]
    if sorted(ranks) != list(range(1, n + 1)):
        violations.append(
            f"cells: rank no forma exactamente 1..{n} "
            f"(rank 1 aparece {ranks.count(1)} veces)"
        )
        return violations

    # Invariantes de `score_current_grid()`: rank ordena por score
    # descendente; display_rank = 1 + #celdas con score mayor
    # (method="min"); tie_group_size = #celdas con el mismo score exacto.
    by_rank = sorted(cells, key=lambda c: c.rank)
    if any(a.score < b.score for a, b in zip(by_rank, by_rank[1:])):
        violations.append("cells: rank no respeta el orden descendente de score")
    scores = [c.score for c in cells]
    for c in cells:
        if c.display_rank != 1 + sum(s > c.score for s in scores):
            violations.append(f"cells[{c.cell_id}].display_rank inconsistente con score")
        if c.tie_group_size != scores.count(c.score):
            violations.append(f"cells[{c.cell_id}].tie_group_size inconsistente con score")
    return violations


def _firms_violations(result: GridScoreResult) -> list[str]:
    violations = []
    if result.firms_origin not in FIRMS_ORIGINS:
        violations.append("firms_origin ausente o fuera de FirmsOrigin")
    coverage_end = result.firms_coverage_end
    # `datetime` es subclase de `date`: se exige una fecha de calendario.
    if not isinstance(coverage_end, date) or isinstance(coverage_end, datetime):
        violations.append("firms_coverage_end ausente o no es fecha")
        return violations
    if not _is_int(result.firms_lag_days):
        violations.append("firms_lag_days ausente o no entero")
        return violations
    if not _is_aware_timestamp(result.forecast_time):
        return violations  # ya reportado por el chequeo de forecast_time
    try:
        lag, status = classify_firms_lag(pd.Timestamp(result.forecast_time), coverage_end)
    except PrototypeUnavailableError:
        violations.append("firms_coverage_end supera el desfase FIRMS máximo")
        return violations
    if result.firms_lag_days != lag:
        violations.append("firms_lag_days inconsistente con forecast_time y firms_coverage_end")
    if result.firms_status != status:
        violations.append("firms_status ausente o inconsistente con firms_lag_days")
    return violations


def validate_grid_result(result) -> None:
    """Lanza `InvalidScoreResultError` si `result` no cumple el contrato
    de salida; no devuelve nada si lo cumple. Nunca corrige ni rellena."""
    if not isinstance(result, GridScoreResult):
        raise InvalidScoreResultError([f"resultado ausente o de tipo {type(result).__name__}"])

    violations = []
    for name in ("model_version", "model_status", "station_id"):
        if not _is_nonempty_str(getattr(result, name)):
            violations.append(f"{name} ausente o vacío")
    for name in ("forecast_time", "weather_timestamp"):
        if not _is_aware_timestamp(getattr(result, name)):
            violations.append(f"{name} ausente o sin zona horaria")
    if not _is_int(result.horizon_hours) or result.horizon_hours < 1:
        violations.append("horizon_hours no es entero >= 1")
    if not _is_finite_number(result.age_hours):
        violations.append("age_hours no es numérico finito")
    if result.freshness not in FRESHNESS_VALUES:
        violations.append("freshness fuera de los valores soportados")

    meteo = result.meteo_actual
    if not isinstance(meteo, dict):
        violations.append("meteo_actual ausente")
    else:
        if not isinstance(meteo.get("regla_30_30_30"), bool):
            violations.append("meteo_actual.regla_30_30_30 no es booleano")
        if not _is_aware_timestamp(meteo.get("momento_observacion")):
            violations.append("meteo_actual.momento_observacion ausente o sin zona horaria")

    fingerprint = result.inputs_fingerprint
    if not isinstance(fingerprint, str) or not _FINGERPRINT_RE.fullmatch(fingerprint):
        violations.append("inputs_fingerprint ausente o no es sha256 hex")

    violations += _firms_violations(result)
    violations += _cell_violations(result.cells)
    if violations:
        raise InvalidScoreResultError(violations)

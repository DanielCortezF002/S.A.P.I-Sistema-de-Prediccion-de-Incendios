"""Validador de causalidad temporal — obligatorio antes de entrenar.

Para cada fila de un dataset de entrenamiento temporal debe cumplirse:

    max(timestamp de cada feature) <= forecast_time
    min(timestamp del target)       >  forecast_time

Si una fila viola esto, se considera fuga y el validador debe fallar (o,
en el modo de filtrado, descartar la fila) — nunca dejarla pasar en
silencio.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


class TemporalLeakageError(Exception):
    """Se lanza cuando `validate_temporal_causality` encuentra una fila que
    usa información posterior a `forecast_time`."""


@dataclass(frozen=True)
class CausalityReport:
    n_rows: int
    n_violations: int
    violation_indices: list[int]

    @property
    def is_valid(self) -> bool:
        return self.n_violations == 0


def validate_temporal_causality(
    dataset: pd.DataFrame,
    *,
    forecast_time_col: str = "forecast_time",
    feature_timestamp_cols: list[str],
    target_timestamp_col: str | None = None,
    raise_on_violation: bool = True,
) -> CausalityReport:
    """Verifica que ninguna columna de timestamp de feature supere
    `forecast_time`, y que el timestamp del target (si se provee) sea
    estrictamente posterior.

    `feature_timestamp_cols`: columnas de timestamp que respaldan features
    (p. ej. `meteo_actual_momento`, `meteo_lag_24h_momento`,
    `historial_firms_ultimo_evento_momento`). No son las features
    numéricas en sí (`temperatura`, `historial_firms_count`) — son los
    timestamps de las observaciones reales que las originaron, que es lo
    que hay que comparar contra `forecast_time`.

    Con `raise_on_violation=True` (default), lanza `TemporalLeakageError`
    en la primera violación detectada — pensado para CI/tests. Con
    `False`, devuelve el reporte completo sin lanzar, para poder inspeccionar
    o filtrar antes de decidir.
    """
    # Normalizar a UTC tz-aware antes de comparar: una columna de puros
    # `NaT` (p. ej. cuando `meteo_before` no encontró lectura dentro de
    # tolerancia) queda con dtype naive, y pandas rechaza comparar eso
    # contra una columna tz-aware con un TypeError en vez de una máscara —
    # normalizar evita que una feature ausente tumbe el validador.
    forecast_time = pd.to_datetime(dataset[forecast_time_col], utc=True)
    violation_mask = pd.Series(False, index=dataset.index)

    for col in feature_timestamp_cols:
        if col not in dataset.columns:
            continue
        ts = pd.to_datetime(dataset[col], utc=True)
        violation_mask |= ts.notna() & (ts > forecast_time)

    if target_timestamp_col is not None and target_timestamp_col in dataset.columns:
        target_ts = pd.to_datetime(dataset[target_timestamp_col], utc=True)
        violation_mask |= target_ts.notna() & (target_ts <= forecast_time)

    violation_indices = dataset.index[violation_mask].tolist()
    report = CausalityReport(
        n_rows=len(dataset),
        n_violations=len(violation_indices),
        violation_indices=violation_indices,
    )

    if raise_on_violation and not report.is_valid:
        raise TemporalLeakageError(
            f"{report.n_violations} de {report.n_rows} filas usan información "
            f"posterior a forecast_time (o un target no estrictamente futuro). "
            f"Índices: {report.violation_indices[:10]}"
            + (" ..." if report.n_violations > 10 else "")
        )

    return report

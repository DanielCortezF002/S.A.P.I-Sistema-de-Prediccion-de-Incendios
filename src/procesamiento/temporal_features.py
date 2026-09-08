"""Features temporales reales — reemplazo de `_add_lag_features`.

Los `lag_temp_24h`/`lag_temp_48h` antiguos eran `temperatura.shift(1)/(2)`
sobre un DataFrame sin agrupar por celda ni ordenar por tiempo: mezclaban
la celda o la fecha equivocada (ver `scripts/auditoria_integridad_datos.py`,
ejemplos concretos en docs/matriz-riesgo.md). Este módulo reconstruye los
lags desde la serie real de `regional_meteo`, buscando por tiempo, nunca
por posición de fila; y construye el historial FIRMS estrictamente
truncado en `T` (nunca cuenta un evento que todavía no había ocurrido).
"""

from __future__ import annotations

from datetime import timedelta

import pandas as pd

from src.procesamiento.regional_meteo import MeteoMatch, meteo_before

LAG_HOURS: tuple[int, ...] = (0, 6, 12, 24, 48)
LAG_TOLERANCE = timedelta(minutes=30)


def _lag_label(hours: int) -> str:
    return "meteo_actual" if hours == 0 else f"meteo_lag_{hours}h"


def build_regional_meteo_features(
    forecast_times: list[pd.Timestamp],
    series: pd.DataFrame,
    lag_hours: tuple[int, ...] = LAG_HOURS,
) -> pd.DataFrame:
    """Una fila por `forecast_time`, con meteo actual + lags reales.

    Cada lag guarda también su propio `_momento` (el timestamp real de la
    lectura usada) — necesario para `validate_temporal_causality`, que
    compara timestamps de features contra `forecast_time`, no valores
    numéricos. Un lag sin lectura real dentro de tolerancia queda en `NaN`
    explícito (`_momento` también `NaT`) — nunca se imputa.
    """
    rows: list[dict] = []
    for T in forecast_times:
        row: dict = {"forecast_time": T}
        for h in lag_hours:
            label = _lag_label(h)
            match: MeteoMatch | None = meteo_before(
                series,
                T,
                max_lookback=timedelta(hours=h) + LAG_TOLERANCE,
                min_lookback=timedelta(hours=h),
                tolerance=LAG_TOLERANCE,
            )
            if match is None:
                row[f"{label}_temp"] = None
                row[f"{label}_hr"] = None
                row[f"{label}_viento"] = None
                row[f"{label}_regla_30_30_30"] = None
                row[f"{label}_momento"] = pd.NaT
                row[f"{label}_delta_minutos"] = None
                # Flag explícito de ausencia (auditoría 06-09-2026): antes,
                # el consumidor del dataset (`experiment_abcd.py::_prep_xy`)
                # rellenaba este NaN con 0.0 antes de entrenar — un
                # "0.0 °C" no es "sin dato", es un valor plausible que un
                # modelo puede confundir con una observación real. Con este
                # flag, "sin dato" queda marcado de forma que no se puede
                # confundir con ninguna lectura real.
                row[f"{label}_missing"] = True
            else:
                row[f"{label}_temp"] = match.temperatura
                row[f"{label}_hr"] = match.humedad_relativa
                row[f"{label}_viento"] = match.velocidad_viento_kmh
                row[f"{label}_regla_30_30_30"] = match.regla_30_30_30
                row[f"{label}_momento"] = match.momento
                row[f"{label}_delta_minutos"] = match.delta_minutos
                row[f"{label}_missing"] = False
        rows.append(row)
    return pd.DataFrame(rows)


def historial_firms_features(
    cell_id: str,
    forecast_time: pd.Timestamp,
    arrivals_for_cell: pd.Series,
) -> dict:
    """Historial FIRMS de una celda, truncado estrictamente en `forecast_time`.

    `arrivals_for_cell`: serie de timestamps `first_arrival` (ver
    `episodes.first_arrival_by_cell`) para ESA celda únicamente. Cualquier
    arribo con timestamp `>= forecast_time` se ignora acá — es exactamente
    la garantía "as of T" que pide la auditoría.

    `dias_desde_ultimo_evento_missing=True` cuando no hay ningún arribo
    previo. A diferencia de la meteorología (donde "sin dato" es un hueco
    de cobertura), acá "sin dato" es información real: "esta celda no
    registra ningún arribo antes de T" — se marca igual por consistencia
    con `validate_missing_data_handling`, pero el significado es distinto
    y se documenta acá para que no se confundan.
    """
    past = arrivals_for_cell[arrivals_for_cell < forecast_time]
    if past.empty:
        return {
            "cell_id": cell_id,
            "forecast_time": forecast_time,
            "historial_firms_count": 0,
            "dias_desde_ultimo_evento": None,
            "dias_desde_ultimo_evento_missing": True,
            "historial_ultimo_evento_momento": pd.NaT,
        }
    ultimo = past.max()
    return {
        "cell_id": cell_id,
        "forecast_time": forecast_time,
        "historial_firms_count": int(len(past)),
        "dias_desde_ultimo_evento": (forecast_time - ultimo).total_seconds() / 86400.0,
        "dias_desde_ultimo_evento_missing": False,
        "historial_ultimo_evento_momento": ultimo,
    }

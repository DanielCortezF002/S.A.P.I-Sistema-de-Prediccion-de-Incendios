"""Meteorología regional real — reemplazo de `DataProcessor._load_meteo()`.

Regla de oro de este módulo (auditoría 06-09-2026, ver docs/matriz-riesgo.md):
una observación de una estación DMC sigue siendo una observación de esa
estación. Nunca se reetiqueta como si fuera una medición de una celda
distinta. `_load_meteo()` hacía exactamente eso —
`df["cell_id"] = grid["cell_id"].values[:len(df)]`, asignación por posición
de fila— y el diagnóstico (`scripts/auditoria_integridad_datos.py`) demostró
que el resultado eran ~50 minutos consecutivos de UNA estación disfrazados
de 50 ubicaciones distintas.

Este módulo produce una única serie temporal por estación
(`station_id`, `momento`, variables), sin ningún `cell_id`. La relación con
las celdas se resuelve después, en el dataset de entrenamiento (ver
`src/procesamiento/temporal_features.py`), como "la misma observación
regional aplica a las 50 celdas de ese instante" — nunca como 50
observaciones independientes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Optional

import pandas as pd

from src.config import DATA_RAW_DIR
from src.procesamiento.features import (
    RULE_30_30_30_HUMIDITY_THRESHOLD,
    RULE_30_30_30_TEMP_THRESHOLD,
    RULE_30_30_30_WIND_THRESHOLD,
)
from src.procesamiento.raw_parser import parse_dmc_json

DEFAULT_SYMMETRIC_TOLERANCE = timedelta(minutes=15)
DEFAULT_LOOKBACK_TOLERANCE = timedelta(minutes=30)


@dataclass(frozen=True)
class MeteoMatch:
    """Una lectura regional real, con la trazabilidad completa que
    `_load_meteo()` descartaba."""

    station_id: str
    momento: pd.Timestamp
    temperatura: float
    humedad_relativa: float
    velocidad_viento_kmh: float
    delta_minutos: float  # con signo: + = la lectura es POSTERIOR a t

    @property
    def regla_30_30_30(self) -> int:
        return int(
            self.temperatura > RULE_30_30_30_TEMP_THRESHOLD
            and self.humedad_relativa < RULE_30_30_30_HUMIDITY_THRESHOLD
            and self.velocidad_viento_kmh > RULE_30_30_30_WIND_THRESHOLD
        )


def load_regional_meteo_series(
    station_id: str,
    raw_dir: Optional[Path] = None,
) -> pd.DataFrame:
    """Serie temporal real de una estación, deduplicada y ordenada por tiempo.

    Lee tanto los históricos mensuales (`dmc_historico_{station}_{YYYY-MM}.json`)
    como los archivos de ingesta diaria "recientes" (`dmc_meteo_*.json`, que
    incluyen la estación si tuvo datos ese día). Conserva `station_id` y
    `momento` en todo momento — es la propiedad que `_load_meteo()` violaba.
    """
    base = raw_dir or DATA_RAW_DIR
    frames: list[pd.DataFrame] = []

    for path in base.glob(f"dmc_historico_{station_id}_*.json"):
        parsed = parse_dmc_json(path)
        if not parsed.empty:
            frames.append(parsed[parsed["codigo_estacion"] == station_id])

    for path in base.glob("dmc_meteo_*.json"):
        parsed = parse_dmc_json(path)
        if not parsed.empty:
            frames.append(parsed[parsed["codigo_estacion"] == station_id])

    if not frames:
        return pd.DataFrame(
            columns=["station_id", "momento", "temperatura", "humedad_relativa", "velocidad_viento_kmh"]
        )

    combined = pd.concat(frames, ignore_index=True)
    combined["momento"] = pd.to_datetime(combined["momento"], utc=True)
    combined = combined.rename(columns={"codigo_estacion": "station_id"})
    combined = combined.dropna(subset=["momento"])
    combined = combined.drop_duplicates(subset=["station_id", "momento"], keep="first")
    combined = combined.sort_values("momento").reset_index(drop=True)
    return combined[["station_id", "momento", "temperatura", "humedad_relativa", "velocidad_viento_kmh"]]


def _to_match(row: pd.Series, delta_minutos: float) -> MeteoMatch:
    return MeteoMatch(
        station_id=str(row["station_id"]),
        momento=row["momento"],
        temperatura=float(row["temperatura"]),
        humedad_relativa=float(row["humedad_relativa"]),
        velocidad_viento_kmh=float(row["velocidad_viento_kmh"]),
        delta_minutos=delta_minutos,
    )


def nearest_meteo_around(
    series: pd.DataFrame,
    t: pd.Timestamp,
    tolerance: timedelta = DEFAULT_SYMMETRIC_TOLERANCE,
) -> Optional[MeteoMatch]:
    """Uso EXPLICATIVO: lectura más cercana a `t`, antes o después.

    Responde "¿qué condiciones había alrededor de este instante?". NUNCA usar
    para construir una feature que alimente una predicción — puede devolver
    una lectura posterior a `t` (ver auditoría de leakage, 65% de los casos
    en el evento 2024-02-03 quedaban del lado posterior).
    """
    if series.empty:
        return None
    deltas = (series["momento"] - t).dt.total_seconds() / 60.0
    idx = deltas.abs().idxmin()
    delta = float(deltas.loc[idx])
    if abs(delta) > tolerance.total_seconds() / 60.0:
        return None
    return _to_match(series.loc[idx], delta)


def meteo_before(
    series: pd.DataFrame,
    t: pd.Timestamp,
    max_lookback: timedelta,
    min_lookback: timedelta = timedelta(0),
    tolerance: timedelta = DEFAULT_LOOKBACK_TOLERANCE,
) -> Optional[MeteoMatch]:
    """Uso PREDICTIVO: lectura real más cercana a `t - min_lookback`, sin
    mirar jamás hacia adelante de `t`.

    Busca dentro de la ventana `[t - min_lookback - tolerance, t - min_lookback]`
    (nunca después de `t - min_lookback`, y nunca después de `t`) la lectura
    real más cercana al objetivo `t - min_lookback`. Si no hay ninguna
    lectura real dentro de tolerancia, devuelve `None` — nunca inventa un
    valor ni cae a la mediana global.

    `max_lookback` acota cuánto se permite retroceder en el peor caso (p.ej.
    para `lag_temp_48h`, min_lookback=48h, max_lookback` puede ser igual a
    min_lookback + tolerance); se deja explícito por claridad de la llamada,
    no se usa para expandir la búsqueda más allá de `tolerance`.
    """
    del max_lookback  # documental: el límite real de búsqueda es `tolerance`
    if series.empty:
        return None
    target = t - min_lookback
    cutoff = target - tolerance
    window = series[(series["momento"] <= target) & (series["momento"] >= cutoff)]
    if window.empty:
        return None
    deltas = (window["momento"] - target).dt.total_seconds() / 60.0
    idx = deltas.abs().idxmin()
    # delta_minutos respecto a `t` (no a `target`), para que el signo sea
    # siempre negativo o cero cuando se usa meteo_before correctamente.
    delta_vs_t = float((window.loc[idx, "momento"] - t).total_seconds() / 60.0)
    return _to_match(window.loc[idx], delta_vs_t)

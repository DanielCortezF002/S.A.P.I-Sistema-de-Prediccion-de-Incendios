"""Join igniciones NASA FIRMS ↔ telemetría DMC (SAPI-28 opción B)."""

from __future__ import annotations

import re
from datetime import timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from src.config import DATA_RAW_DIR
from src.procesamiento.raw_parser import parse_dmc_json
from src.procesamiento.station_catalog import DmcStation, default_station_catalog, select_nearest_station

JOIN_STATUS_MATCHED = "matched"
JOIN_STATUS_OUT_OF_TOLERANCE = "out_of_tolerance"
JOIN_STATUS_NO_DMC_COVERAGE = "no_dmc_coverage"

TEMPORAL_TOLERANCE = timedelta(minutes=15)
DMC_HISTORICO_PATTERN = re.compile(
    r"^dmc_historico_(?P<codigo>\d+)_(?P<year>\d{4})-(?P<month>\d{2})\.json$"
)


def ignition_timestamp(acq_date: str, acq_time: int | str) -> pd.Timestamp:
    """Construye instante UTC desde acq_date (YYYY-MM-DD) y acq_time (HHMM)."""
    time_int = int(acq_time)
    hours, minutes = divmod(time_int, 100)
    return pd.Timestamp(f"{acq_date} {hours:02d}:{minutes:02d}:00", tz="UTC")


def discover_dmc_monthly_files(raw_dir: Path | None = None) -> dict[tuple[str, int, int], Path]:
    """Índice (codigo, año, mes) → archivo JSON histórico mensual en data/raw."""
    base = raw_dir or DATA_RAW_DIR
    index: dict[tuple[str, int, int], Path] = {}
    for path in base.glob("dmc_historico_*.json"):
        match = DMC_HISTORICO_PATTERN.match(path.name)
        if not match:
            continue
        key = (match.group("codigo"), int(match.group("year")), int(match.group("month")))
        index[key] = path
    return index


def stations_with_coverage(year: int, month: int, index: dict[tuple[str, int, int], Path]) -> list[str]:
    """Códigos de estación con archivo DMC cargado para el mes dado."""
    return sorted({codigo for (codigo, y, m) in index if y == year and m == month})


def _load_meteo_dataframe(path: Path, cache: dict[Path, pd.DataFrame]) -> pd.DataFrame:
    if path not in cache:
        cache[path] = parse_dmc_json(path)
    return cache[path]


def _nearest_temporal_match(
    ignition_ts: pd.Timestamp,
    meteo: pd.DataFrame,
) -> tuple[pd.Series | None, float | None]:
    """Devuelve (fila más cercana, delta_minutos) o (None, delta al más cercano)."""
    if meteo.empty or ignition_ts is pd.NaT:
        return None, None

    meteo = meteo.copy()
    meteo["momento"] = pd.to_datetime(meteo["momento"], utc=True)
    deltas = (meteo["momento"] - ignition_ts).dt.total_seconds().abs() / 60.0
    nearest_delta = float(deltas.min())
    within = meteo.loc[deltas <= TEMPORAL_TOLERANCE.total_seconds() / 60.0].copy()
    if within.empty:
        return None, nearest_delta

    within["_delta_min"] = deltas.loc[within.index]
    within = within.sort_values(["_delta_min", "momento"])
    return within.iloc[0], float(within.iloc[0]["_delta_min"])


def join_fires_to_meteo(
    fires: pd.DataFrame,
    *,
    dmc_index: dict[tuple[str, int, int], Path] | None = None,
    catalog: dict[str, DmcStation] | None = None,
    raw_dir: Path | None = None,
) -> pd.DataFrame:
    """Enriquece igniciones NASA con meteo DMC; conserva todas las filas de entrada."""
    index = dmc_index if dmc_index is not None else discover_dmc_monthly_files(raw_dir)
    stations = catalog if catalog is not None else default_station_catalog()
    meteo_cache: dict[Path, pd.DataFrame] = {}

    rows: list[dict[str, Any]] = []
    for _, fire in fires.iterrows():
        row = fire.to_dict()
        ts = ignition_timestamp(str(fire["acq_date"]), fire["acq_time"])
        row["ignition_ts"] = ts
        year, month = ts.year, ts.month

        candidates = stations_with_coverage(year, month, index)
        if not candidates:
            row.update(
                {
                    "join_status": JOIN_STATUS_NO_DMC_COVERAGE,
                    "estacion_codigo": None,
                    "distancia_estacion_km": None,
                    "delta_minutos": None,
                    "temperatura": None,
                    "humedad_relativa": None,
                    "velocidad_viento_kmh": None,
                }
            )
            rows.append(row)
            continue

        codigo, dist_km = select_nearest_station(
            float(fire["latitude"]),
            float(fire["longitude"]),
            candidates,
            stations,
        )
        meteo_path = index[(codigo, year, month)]
        meteo_df = _load_meteo_dataframe(meteo_path, meteo_cache)
        match, nearest_delta = _nearest_temporal_match(ts, meteo_df)

        if match is None:
            row.update(
                {
                    "join_status": JOIN_STATUS_OUT_OF_TOLERANCE,
                    "estacion_codigo": codigo,
                    "distancia_estacion_km": dist_km,
                    "delta_minutos": nearest_delta,
                    "temperatura": None,
                    "humedad_relativa": None,
                    "velocidad_viento_kmh": None,
                }
            )
        else:
            row.update(
                {
                    "join_status": JOIN_STATUS_MATCHED,
                    "estacion_codigo": codigo,
                    "distancia_estacion_km": dist_km,
                    "delta_minutos": nearest_delta,
                    "temperatura": float(match["temperatura"]),
                    "humedad_relativa": float(match["humedad_relativa"]),
                    "velocidad_viento_kmh": float(match["velocidad_viento_kmh"]),
                }
            )
        rows.append(row)

    return pd.DataFrame(rows)


def summarize_join(result: pd.DataFrame) -> dict[str, Any]:
    """Agregados por join_status para manifest / logging."""
    counts = result["join_status"].value_counts().to_dict()
    total = len(result)
    with_coverage = total - counts.get(JOIN_STATUS_NO_DMC_COVERAGE, 0)
    matched = counts.get(JOIN_STATUS_MATCHED, 0)
    return {
        "total_fires": total,
        "by_status": counts,
        "match_rate_overall": round(matched / total, 4) if total else 0.0,
        "match_rate_where_dmc_available": round(matched / with_coverage, 4) if with_coverage else 0.0,
    }

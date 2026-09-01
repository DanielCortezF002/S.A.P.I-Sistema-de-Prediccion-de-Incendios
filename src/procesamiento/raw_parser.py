"""Normalización de payloads crudos NASA FIRMS y DMC a tipos analíticos."""

from __future__ import annotations

import json
import re
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point


def _clean_float(val) -> float | None:
    if val is None or val == "":
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if not isinstance(val, str):
        return None
    match = re.search(r"[-+]?\d*\.?\d+", val.replace(",", "."))
    return float(match.group()) if match else None


def _extract_dmc_records(contenido: dict) -> list[dict]:
    """Extrae filas horarias desde la estructura real de getDatosRecientesEma."""
    if "error" in contenido:
        return []
    datos_estaciones = contenido.get("datosEstaciones", {})
    if isinstance(datos_estaciones, dict):
        registros = datos_estaciones.get("datos", [])
        if isinstance(registros, list):
            return registros
    # Fallback por si alguna respuesta viene en formato distinto
    registros = contenido.get("registros")
    if isinstance(registros, list):
        return registros
    return []


def parse_dmc_json(json_path: str | Path) -> pd.DataFrame:
    """Extrae y limpia telemetría horaria desde el JSON de DMC (ej. Rodelillo 330007)."""
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    filas: list[dict] = []
    for cod_estacion, contenido in data.items():
        if not isinstance(contenido, dict):
            continue

        for reg in _extract_dmc_records(contenido):
            viento_kt = _clean_float(reg.get("fuerzaDelViento"))
            viento_kmh = round(viento_kt * 1.852, 2) if viento_kt is not None else None

            filas.append(
                {
                    "codigo_estacion": cod_estacion,
                    "momento": reg.get("momento"),
                    "temperatura": _clean_float(reg.get("temperatura")),
                    "humedad_relativa": _clean_float(reg.get("humedadRelativa")),
                    "direccion_viento": _clean_float(reg.get("direccionDelViento")),
                    "velocidad_viento_kmh": viento_kmh,
                }
            )

    df = pd.DataFrame(filas)
    if not df.empty:
        df["momento"] = pd.to_datetime(df["momento"], errors="coerce")
        df = df.dropna(subset=["temperatura", "humedad_relativa"]).sort_values("momento")
    return df


def parse_nasa_csv(csv_path: str | Path) -> gpd.GeoDataFrame:
    """Parsea focos VIIRS y genera un GeoDataFrame WGS84."""
    df = pd.read_csv(csv_path)
    if df.empty:
        return gpd.GeoDataFrame()

    geometry = [Point(xy) for xy in zip(df["longitude"], df["latitude"])]
    gdf = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")
    gdf["acq_datetime"] = pd.to_datetime(
        gdf["acq_date"].astype(str) + " " + gdf["acq_time"].astype(str).str.zfill(4),
        format="%Y-%m-%d %H%M",
        errors="coerce",
    )
    return gdf

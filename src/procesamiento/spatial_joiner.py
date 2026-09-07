"""Cruce espacial de telemetría DMC y focos NASA sobre la grilla territorial."""

from __future__ import annotations

from typing import Any

import geopandas as gpd
import pandas as pd
from shapely.geometry import box

from src.geo.grid import BASE_LAT, BASE_LON, COLS, ROWS, STEP_LAT, STEP_LON


def aggregate_dmc_daily(df_dmc: pd.DataFrame) -> dict[str, Any]:
    """Calcula métricas críticas intradiarias y evalúa la Regla 30-30-30.

    `regla_30_30_30` se evalúa por lectura individual (misma fila: mismo
    instante, mismas tres variables) antes de agregar, no sobre
    temp_max_daily/rh_min_daily/wind_speed_max ya agregados (fix 06-09-2026,
    ver reverificación de VP-025 en docs/matriz-riesgo.md). El agregado por
    día puede mezclar el pico de temperatura de una hora con el pico de
    viento de otra como si fueran simultáneos — eso fue exactamente lo que
    convirtió un hallazgo en artefacto en `scripts/reverificar_hallazgo_2022_12_11.py`.
    """
    if df_dmc.empty:
        return {
            "temp_max_daily": None,
            "rh_min_daily": None,
            "wind_speed_max": None,
            "regla_30_30_30": 0,
        }

    t_max = float(df_dmc["temperatura"].max())
    rh_min = float(df_dmc["humedad_relativa"].min())
    wind_max = float(df_dmc["velocidad_viento_kmh"].max())

    regla_por_lectura = (
        (df_dmc["temperatura"] > 30.0)
        & (df_dmc["humedad_relativa"] < 30.0)
        & (df_dmc["velocidad_viento_kmh"] > 30.0)
    )
    regla_activa = int(bool(regla_por_lectura.any()))

    return {
        "temp_max_daily": round(t_max, 2),
        "rh_min_daily": round(rh_min, 2),
        "wind_speed_max": round(wind_max, 2),
        "regla_30_30_30": regla_activa,
    }


def build_local_grid_gdf() -> gpd.GeoDataFrame:
    """Construye la grilla 10×5 local con polígonos, alineada a `src/geo/grid.py`
    (la misma geometría que usa el dashboard y `scripts/generate_seed.py`)."""
    records: list[dict[str, Any]] = []
    idx = 1
    for row in range(ROWS):
        for col in range(COLS):
            min_lon = round(BASE_LON + col * STEP_LON, 5)
            min_lat = round(BASE_LAT + row * STEP_LAT, 5)
            max_lon = round(min_lon + STEP_LON, 5)
            max_lat = round(min_lat + STEP_LAT, 5)
            records.append(
                {
                    "cell_id": f"VP-{idx:03d}",
                    "comuna": "corredor_vp",
                    "geometry": box(min_lon, min_lat, max_lon, max_lat),
                }
            )
            idx += 1

    return gpd.GeoDataFrame(records, geometry="geometry", crs="EPSG:4326")


def join_features_to_grid(
    gdf_grid: gpd.GeoDataFrame,
    gdf_nasa: gpd.GeoDataFrame,
    df_dmc: pd.DataFrame,
) -> gpd.GeoDataFrame:
    """Cruza focos satelitales y telemetría climática con las celdas de 1 km²."""
    df_features = gdf_grid.copy()

    meteo_kpis = aggregate_dmc_daily(df_dmc)
    for kpi, val in meteo_kpis.items():
        df_features[kpi] = val

    if not gdf_nasa.empty and "geometry" in gdf_nasa.columns:
        nasa_layer = gdf_nasa.to_crs(df_features.crs)
        joined = gpd.sjoin(
            nasa_layer,
            df_features[["cell_id", "geometry"]],
            how="inner",
            predicate="within",
        )

        focos_por_celda = joined.groupby("cell_id").size().rename("conteo_focos_activos")
        max_frp_por_celda = (
            joined.groupby("cell_id")["frp"].max().rename("max_frp") if "frp" in joined.columns else None
        )

        df_features = df_features.merge(focos_por_celda, on="cell_id", how="left")
        if max_frp_por_celda is not None:
            df_features = df_features.merge(max_frp_por_celda, on="cell_id", how="left")

        df_features["conteo_focos_activos"] = df_features["conteo_focos_activos"].fillna(0).astype(int)
        if "max_frp" in df_features.columns:
            df_features["max_frp"] = df_features["max_frp"].fillna(0.0)
    else:
        df_features["conteo_focos_activos"] = 0
        df_features["max_frp"] = 0.0

    return df_features

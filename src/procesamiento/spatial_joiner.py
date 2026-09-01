"""Cruce espacial de telemetría DMC y focos NASA sobre la grilla territorial."""

from __future__ import annotations

from typing import Any

import geopandas as gpd
import pandas as pd
from shapely.geometry import box


def aggregate_dmc_daily(df_dmc: pd.DataFrame) -> dict[str, Any]:
    """Calcula métricas críticas intradiarias y evalúa la Regla 30-30-30."""
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

    regla_activa = int((t_max > 30.0) and (rh_min < 30.0) and (wind_max > 30.0))

    return {
        "temp_max_daily": round(t_max, 2),
        "rh_min_daily": round(rh_min, 2),
        "wind_speed_max": round(wind_max, 2),
        "regla_30_30_30": regla_activa,
    }


def build_local_grid_gdf() -> gpd.GeoDataFrame:
    """Construye la grilla 10×5 local con polígonos (~1 km²), alineada al seed demo."""
    base_lon = -71.535
    base_lat = -33.062
    cols = 10
    rows = 5
    step_lon = 0.010
    step_lat = 0.009

    records: list[dict[str, Any]] = []
    idx = 1
    for row in range(rows):
        for col in range(cols):
            min_lon = round(base_lon + col * step_lon, 5)
            min_lat = round(base_lat + row * step_lat, 5)
            max_lon = round(min_lon + step_lon, 5)
            max_lat = round(min_lat + step_lat, 5)
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

"""Persistencia de la matriz de características en PostGIS."""

from __future__ import annotations

from datetime import datetime, timezone

import geopandas as gpd
import pandas as pd
from sqlalchemy import text

from src.db import get_backend_engine

_SCHEMA_COLUMNS = [
    "cell_id",
    "fecha",
    "temperatura",
    "humedad_relativa",
    "velocidad_viento",
    "altitud",
    "pendiente",
    "ndvi",
    "regla_30_30_30",
    "lag_temp_24h",
    "lag_temp_48h",
    "ignicion",
    "geom",
    "created_at",
]


def _prepare_features_frame(gdf_features: gpd.GeoDataFrame, fecha_proceso: str) -> gpd.GeoDataFrame:
    """Mapea columnas del join espacial al esquema matriz_features."""
    df = gdf_features.copy()

    if df.crs is None:
        df = df.set_crs(epsg=4326)
    elif df.crs.to_epsg() != 4326:
        df = df.to_crs(epsg=4326)

    rename_map = {
        "temp_max_daily": "temperatura",
        "rh_min_daily": "humedad_relativa",
        "wind_speed_max": "velocidad_viento",
        "geometry": "geom",
    }
    df = df.rename(columns=rename_map)

    if "geom" not in df.columns and "geometry" in df.columns:
        df = df.rename(columns={"geometry": "geom"})

    df["fecha"] = pd.to_datetime(fecha_proceso).date()
    df["created_at"] = datetime.now(timezone.utc)

    for col in ("altitud", "pendiente", "ndvi", "lag_temp_24h", "lag_temp_48h", "ignicion"):
        if col not in df.columns:
            df[col] = None

    if "regla_30_30_30" in df.columns:
        df["regla_30_30_30"] = df["regla_30_30_30"].fillna(0).astype(int)

    keep = [c for c in _SCHEMA_COLUMNS if c in df.columns]
    gdf = gpd.GeoDataFrame(df[keep], geometry="geom", crs="EPSG:4326")
    return gdf


def persist_features_to_postgis(
    gdf_features: gpd.GeoDataFrame,
    fecha_proceso: str,
    table_name: str = "matriz_features",
) -> int:
    """Persiste la matriz de features geoespacial en PostGIS asegurando tipos y SRID 4326."""
    if gdf_features.empty:
        print("GeoDataFrame vacío. No hay registros para persistir.")
        return 0

    if table_name != "matriz_features":
        raise ValueError("Solo se permite persistir en matriz_features")

    engine = get_backend_engine()
    df_to_save = _prepare_features_frame(gdf_features, fecha_proceso)

    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM matriz_features WHERE fecha = :fecha"),
            {"fecha": fecha_proceso},
        )

    df_to_save.to_postgis(
        name=table_name,
        con=engine,
        if_exists="append",
        index=False,
    )

    print(f"Persistidos {len(df_to_save)} registros en '{table_name}' para la fecha {fecha_proceso}.")
    return len(df_to_save)

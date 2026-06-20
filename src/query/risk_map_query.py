"""Consulta espacial de riesgo — versión demo 50 celdas."""

from __future__ import annotations

from datetime import date
from typing import Optional

import geopandas as gpd
from sqlalchemy import text

from src.config import GRID_MAX_CELLS
from src.db import get_connection, log_event

QUERY_ENGINE_VERSION = "distinct-on-v2"

_SPATIAL_RISK_SQL = f"""
SELECT * FROM (
    SELECT DISTINCT ON (p.cell_id)
        p.cell_id,
        p.fecha,
        p.probabilidad,
        p.nivel_riesgo,
        p.temperatura,
        p.humedad_relativa,
        p.velocidad_viento,
        p.regla_30_30_30,
        p.modelo_version,
        p.geom
    FROM predicciones_riesgo p
    WHERE p.fecha <= :fecha
    ORDER BY p.cell_id, p.fecha DESC
) ultimo_por_celda
ORDER BY cell_id
LIMIT {int(GRID_MAX_CELLS)}
"""


def fetch_spatial_risk_map(fecha: Optional[date] = None) -> gpd.GeoDataFrame:
    """Obtiene último snapshot por celda hasta la fecha consultada.

    Args:
        fecha: Fecha límite de consulta.

    Returns:
        GeoDataFrame con hasta GRID_MAX_CELLS celdas.
    """
    target_date = fecha or date.today()
    query = text(_SPATIAL_RISK_SQL)
    try:
        with get_connection() as conn:
            df = gpd.read_postgis(
                query,
                conn,
                geom_col="geom",
                params={"fecha": target_date},
            )
    except Exception as exc:
        log_event(
            "RiskMapQuery",
            "query_error",
            f"{QUERY_ENGINE_VERSION} fallo: {exc}",
            "ERROR",
        )
        raise

    if df.empty:
        log_event("RiskMapQuery", "empty_map", f"Sin datos para {target_date}", "WARN")
        return gpd.GeoDataFrame(
            columns=[
                "cell_id",
                "fecha",
                "probabilidad",
                "nivel_riesgo",
                "temperatura",
                "humedad_relativa",
                "velocidad_viento",
                "regla_30_30_30",
                "modelo_version",
                "geometry",
            ],
            geometry="geometry",
            crs="EPSG:4326",
        )

    log_event(
        "RiskMapQuery",
        "map_loaded",
        f"{QUERY_ENGINE_VERSION} filas={len(df)} fecha<={target_date}",
        "INFO",
    )
    gdf = gpd.GeoDataFrame(df, geometry="geom", crs="EPSG:4326")
    return gdf.rename_geometry("geometry")

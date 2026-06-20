"""Consulta espacial de riesgo — demo 50 celdas, fecha exacta."""

from __future__ import annotations

from datetime import date
from typing import Optional

import geopandas as gpd
import pandas as pd
from sqlalchemy import text

from src.config import GRID_MAX_CELLS
from src.db import get_connection, log_event

QUERY_ENGINE_VERSION = "exact-date-v1"

_SPATIAL_RISK_SQL = f"""
SELECT
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
WHERE p.fecha = :fecha
ORDER BY p.cell_id
LIMIT {int(GRID_MAX_CELLS)}
"""

_DATE_RANGE_SQL = """
SELECT MIN(fecha) AS min_fecha, MAX(fecha) AS max_fecha
FROM predicciones_riesgo
"""

_AVAILABLE_DATES_SQL = """
SELECT DISTINCT fecha
FROM predicciones_riesgo
ORDER BY fecha
"""

_EMPTY_COLUMNS = [
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
]


def _empty_gdf() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        columns=_EMPTY_COLUMNS,
        geometry="geometry",
        crs="EPSG:4326",
    )


def fetch_available_date_range() -> tuple[Optional[date], Optional[date]]:
    """Retorna rango de fechas disponibles en predicciones_riesgo."""
    try:
        with get_connection() as conn:
            row = conn.execute(text(_DATE_RANGE_SQL)).mappings().first()
        if not row or row["min_fecha"] is None:
            return None, None
        return row["min_fecha"], row["max_fecha"]
    except Exception as exc:
        log_event("RiskMapQuery", "date_range_error", str(exc), "WARN")
        return None, None


def fetch_available_dates() -> list[date]:
    """Lista fechas con predicciones cargadas."""
    try:
        with get_connection() as conn:
            df = pd.read_sql(text(_AVAILABLE_DATES_SQL), conn)
        if df.empty:
            return []
        return [d.date() if hasattr(d, "date") else d for d in df["fecha"].tolist()]
    except Exception as exc:
        log_event("RiskMapQuery", "dates_list_error", str(exc), "WARN")
        return []


def fetch_spatial_risk_map(fecha: Optional[date] = None) -> gpd.GeoDataFrame:
    """Obtiene mapa de riesgo para una fecha exacta.

    Args:
        fecha: Fecha de consulta (debe existir en predicciones_riesgo).

    Returns:
        GeoDataFrame con hasta GRID_MAX_CELLS celdas.
    """
    _, max_fecha = fetch_available_date_range()
    target_date = fecha or max_fecha or date.today()
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
        return _empty_gdf()

    log_event(
        "RiskMapQuery",
        "map_loaded",
        f"{QUERY_ENGINE_VERSION} filas={len(df)} fecha={target_date}",
        "INFO",
    )
    gdf = gpd.GeoDataFrame(df, geometry="geom", crs="EPSG:4326")
    return gdf.rename_geometry("geometry")

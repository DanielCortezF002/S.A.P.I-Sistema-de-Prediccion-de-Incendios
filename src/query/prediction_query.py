"""Capa de consulta - Data Contract entre frontend y PostGIS."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Optional

import geopandas as gpd
import pandas as pd
from sqlalchemy import text

from src.config import GRID_MAX_CELLS, RISK_THRESHOLDS
from src.db import get_connection, log_event

QUERY_ENGINE_VERSION = "exact-date-v1"

_DATE_RANGE_SQL = """
SELECT MIN(fecha) AS min_fecha, MAX(fecha) AS max_fecha
FROM predicciones_riesgo
"""

_AVAILABLE_DATES_SQL = """
SELECT DISTINCT fecha
FROM predicciones_riesgo
ORDER BY fecha
"""

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

_EMPTY_MAP_COLUMNS = [
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
        columns=_EMPTY_MAP_COLUMNS,
        geometry="geometry",
        crs="EPSG:4326",
    )


def fetch_available_date_range() -> tuple[Optional[date], Optional[date]]:
    """Rango de fechas con predicciones en PostGIS."""
    try:
        with get_connection() as conn:
            row = conn.execute(text(_DATE_RANGE_SQL)).mappings().first()
        if not row or row["min_fecha"] is None:
            return None, None
        return row["min_fecha"], row["max_fecha"]
    except Exception as exc:
        log_event("PredictionQuery", "date_range_error", str(exc), "WARN")
        return None, None


def fetch_available_dates() -> list[date]:
    """Lista de fechas con predicciones cargadas."""
    try:
        with get_connection() as conn:
            df = pd.read_sql(text(_AVAILABLE_DATES_SQL), conn)
        if df.empty:
            return []
        return [d.date() if hasattr(d, "date") else d for d in df["fecha"].tolist()]
    except Exception as exc:
        log_event("PredictionQuery", "dates_list_error", str(exc), "WARN")
        return []


def fetch_spatial_risk_map(fecha: Optional[date] = None) -> gpd.GeoDataFrame:
    """Mapa de riesgo por fecha exacta (implementación serving layer)."""
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
            "PredictionQuery",
            "query_error",
            f"{QUERY_ENGINE_VERSION} fallo: {exc}",
            "ERROR",
        )
        raise

    if df.empty:
        log_event("PredictionQuery", "empty_map", f"Sin datos para {target_date}", "WARN")
        return _empty_gdf()

    log_event(
        "PredictionQuery",
        "map_loaded",
        f"{QUERY_ENGINE_VERSION} filas={len(df)} fecha={target_date}",
        "INFO",
    )
    gdf = gpd.GeoDataFrame(df, geometry="geom", crs="EPSG:4326")
    return gdf.rename_geometry("geometry")


class PredictionQuery:
    """Interfaz de acceso a predicciones espaciales indexadas en PostGIS."""

    def get_spatial_risk_map(self, fecha: Optional[date] = None) -> gpd.GeoDataFrame:
        """Extrae mapa de riesgo territorial para una fecha."""
        return fetch_spatial_risk_map(fecha)

    def get_available_date_range(self) -> tuple[Optional[date], Optional[date]]:
        """Rango de fechas con predicciones en PostGIS."""
        return fetch_available_date_range()

    def get_available_dates(self) -> list[date]:
        """Lista de fechas con predicciones cargadas."""
        return fetch_available_dates()

    def get_cell_detail(self, cell_id: str, fecha: Optional[date] = None) -> dict[str, Any]:
        """Obtiene detalle de una celda específica."""
        target_date = fecha or date.today()
        query = text(
            """
            SELECT * FROM predicciones_riesgo
            WHERE cell_id = :cell_id AND fecha = :fecha
            LIMIT 1
            """
        )
        with get_connection() as conn:
            row = conn.execute(
                query, {"cell_id": cell_id, "fecha": target_date}
            ).mappings().first()
        return dict(row) if row else {}

    def get_observability_logs(self, limit: int = 50) -> pd.DataFrame:
        """Audita comportamiento del sistema."""
        query = text(
            """
            SELECT componente, evento, detalle, nivel, created_at
            FROM observability_logs
            ORDER BY created_at DESC
            LIMIT :limit
            """
        )
        with get_connection() as conn:
            return pd.read_sql(query, conn, params={"limit": limit})

    def get_contingency_cache(self, days: int = 7) -> gpd.GeoDataFrame:
        """Recupera último estado espacial válido (degradación controlada R-03)."""
        cutoff = date.today() - timedelta(days=days)
        query = text(
            """
            SELECT DISTINCT ON (cell_id)
                   cell_id, fecha, probabilidad, nivel_riesgo,
                   temperatura, humedad_relativa, velocidad_viento,
                   regla_30_30_30, modelo_version, geom
            FROM predicciones_riesgo
            WHERE fecha >= :cutoff
            ORDER BY cell_id, fecha DESC
            """
        )
        try:
            with get_connection() as conn:
                df = gpd.read_postgis(query, conn, geom_col="geom", params={"cutoff": cutoff})
        except Exception as exc:
            log_event(
                "PredictionQuery",
                "contingency_error",
                f"Fallo caché contingencia: {exc}",
                "ERROR",
            )
            return _empty_gdf()
        if df.empty:
            return _empty_gdf()
        gdf = gpd.GeoDataFrame(df, geometry="geom", crs="EPSG:4326")
        return gdf.rename_geometry("geometry")

    @staticmethod
    def classify_risk(probability: float) -> str:
        """Clasifica probabilidad en nivel semafórico."""
        if probability < RISK_THRESHOLDS["bajo"]:
            return "bajo"
        if probability < RISK_THRESHOLDS["medio"]:
            return "medio"
        return "alto"

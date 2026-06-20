"""Capa de consulta - Data Contract entre frontend y PostGIS."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Optional

import geopandas as gpd
import pandas as pd
from sqlalchemy import text

from src.config import RISK_THRESHOLDS
from src.db import get_connection, log_event

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


class PredictionQuery:
    """Interfaz de acceso a predicciones espaciales indexadas en PostGIS."""

    def get_spatial_risk_map(self, fecha: Optional[date] = None) -> gpd.GeoDataFrame:
        """Extrae mapa de riesgo territorial para una fecha.

        Usa una CTE para resolver el frente temporal más reciente y explotar
        el índice compuesto (fecha DESC, cell_id) sobre predicciones_riesgo.

        Args:
            fecha: Fecha de consulta. Usa la más reciente disponible si es None.

        Returns:
            GeoDataFrame con celdas, probabilidad y nivel de riesgo.
        """
        target_date = fecha or date.today()
        query = text(
            """
            WITH ultimo_frente_temporal AS (
                SELECT MAX(fecha) AS max_fecha
                FROM predicciones_riesgo
                WHERE fecha <= :fecha
            )
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
            INNER JOIN ultimo_frente_temporal u ON p.fecha = u.max_fecha
            """
        )
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
                f"Fallo consulta mapa espacial: {exc}",
                "ERROR",
            )
            return self.get_contingency_cache()

        if df.empty:
            log_event("PredictionQuery", "empty_map", f"Sin datos para {target_date}", "WARN")
            return gpd.GeoDataFrame(
                columns=_EMPTY_MAP_COLUMNS,
                geometry="geometry",
                crs="EPSG:4326",
            )
        gdf = gpd.GeoDataFrame(df, geometry="geom", crs="EPSG:4326")
        return gdf.rename_geometry("geometry")

    def get_cell_detail(self, cell_id: str, fecha: Optional[date] = None) -> dict[str, Any]:
        """Obtiene detalle de una celda específica.

        Args:
            cell_id: Identificador de celda.
            fecha: Fecha de consulta.

        Returns:
            Diccionario con atributos de la celda.
        """
        target_date = fecha or date.today()
        query = text(
            """
            SELECT * FROM predicciones_riesgo
            WHERE cell_id = :cell_id
              AND fecha = (
                  SELECT MAX(fecha) FROM predicciones_riesgo
                  WHERE cell_id = :cell_id AND fecha <= :fecha
              )
            LIMIT 1
            """
        )
        with get_connection() as conn:
            row = conn.execute(
                query, {"cell_id": cell_id, "fecha": target_date}
            ).mappings().first()
        return dict(row) if row else {}

    def get_observability_logs(self, limit: int = 50) -> pd.DataFrame:
        """Audita comportamiento del sistema.

        Args:
            limit: Máximo de registros a retornar.

        Returns:
            DataFrame con logs recientes.
        """
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
        """Recupera último estado espacial válido (degradación controlada R-03).

        Args:
            days: Ventana de resguardo en días.

        Returns:
            GeoDataFrame con predicciones de contingencia.
        """
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
            return gpd.GeoDataFrame(
                columns=_EMPTY_MAP_COLUMNS,
                geometry="geometry",
                crs="EPSG:4326",
            )
        if df.empty:
            return gpd.GeoDataFrame(
                columns=_EMPTY_MAP_COLUMNS,
                geometry="geometry",
                crs="EPSG:4326",
            )
        gdf = gpd.GeoDataFrame(df, geometry="geom", crs="EPSG:4326")
        return gdf.rename_geometry("geometry")

    @staticmethod
    def classify_risk(probability: float) -> str:
        """Clasifica probabilidad en nivel semafórico.

        Args:
            probability: Valor entre 0 y 1.

        Returns:
            Nivel: bajo, medio o alto.
        """
        if probability < RISK_THRESHOLDS["bajo"]:
            return "bajo"
        if probability < RISK_THRESHOLDS["medio"]:
            return "medio"
        return "alto"

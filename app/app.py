"""Dashboard principal S.A.P.I. - Streamlit."""

from __future__ import annotations

import sys
from pathlib import Path

# Streamlit Cloud ejecuta app/app.py; la raíz del repo debe estar en sys.path.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from datetime import date, datetime, timedelta
from typing import Any, Optional

import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from app.utils.map_renderer import render_folium_map
from src.query.prediction_query import PredictionQuery


class SapiDashboard:
    """Interfaz gráfica para analistas de emergencias."""

    def __init__(self) -> None:
        """Inicializa dashboard con contrato de datos."""
        self.query = PredictionQuery()

    @st.cache_resource
    def load_cached_resources(_self) -> PredictionQuery:
        """Singleton de conexión a serving layer."""
        return PredictionQuery()

    @st.cache_data(ttl=3600)
    def _load_risk_data(_self, fecha_str: str) -> pd.DataFrame:
        """Carga dataframe de riesgo con TTL de 1 hora."""
        query = PredictionQuery()
        fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
        gdf = query.get_spatial_risk_map(fecha)
        if gdf.empty:
            return pd.DataFrame()
        return pd.DataFrame(gdf.drop(columns="geometry", errors="ignore"))

    def render_folium_map(self, fecha: Optional[date] = None) -> None:
        """Inyecta mapa Folium en el navegador."""
        fecha = fecha or date.today()
        query = self.load_cached_resources()
        gdf = query.get_spatial_risk_map(fecha)
        folium_map = render_folium_map(gdf)
        st_folium(folium_map, width=900, height=500, returned_objects=[])

    def export_report_pdf(self, fecha: Optional[date] = None) -> bytes:
        """Genera reporte simple en texto para exportación.

        Args:
            fecha: Fecha del reporte.

        Returns:
            Contenido del reporte en bytes.
        """
        fecha = fecha or date.today()
        gdf = self.query.get_spatial_risk_map(fecha)
        lines = [
            "S.A.P.I. - Reporte de Riesgo de Ignición",
            f"Fecha: {fecha.isoformat()}",
            f"Celdas analizadas: {len(gdf)}",
            "",
        ]
        if not gdf.empty:
            alto = (gdf["nivel_riesgo"] == "alto").sum()
            medio = (gdf["nivel_riesgo"] == "medio").sum()
            bajo = (gdf["nivel_riesgo"] == "bajo").sum()
            lines.extend(
                [
                    f"Riesgo alto: {alto}",
                    f"Riesgo medio: {medio}",
                    f"Riesgo bajo: {bajo}",
                    f"Probabilidad máxima: {gdf['probabilidad'].max():.2%}",
                ]
            )
        return "\n".join(lines).encode("utf-8")


def main() -> None:
    """Punto de entrada de la aplicación Streamlit."""
    st.set_page_config(
        page_title="S.A.P.I. - Sistema de Alerta y Predicción de Incendios",
        page_icon="🔥",
        layout="wide",
    )

    dashboard = SapiDashboard()

    st.title("S.A.P.I.")
    st.subheader("Sistema de Alerta y Predicción de Incendios - Región de Valparaíso")

    col1, col2, col3 = st.columns(3)
    selected_date = st.sidebar.date_input(
        "Fecha de consulta",
        value=date.today(),
        min_value=date.today() - timedelta(days=30),
        max_value=date.today(),
    )

    query = dashboard.load_cached_resources()
    gdf = query.get_spatial_risk_map(selected_date)

    with col1:
        st.metric("Celdas monitoreadas", len(gdf))
    with col2:
        alto = int((gdf["nivel_riesgo"] == "alto").sum()) if not gdf.empty else 0
        st.metric("Zonas riesgo alto", alto)
    with col3:
        max_prob = f"{gdf['probabilidad'].max():.1%}" if not gdf.empty else "N/A"
        st.metric("Probabilidad máxima", max_prob)

    st.markdown("### Mapa de riesgo probabilístico (grilla 1 km²)")
    dashboard.render_folium_map(selected_date)

    if not gdf.empty:
        st.markdown("### Detalle por celda")
        display_df = gdf.drop(columns="geometry", errors="ignore")[
            [
                "cell_id",
                "probabilidad",
                "nivel_riesgo",
                "temperatura",
                "humedad_relativa",
                "velocidad_viento",
                "regla_30_30_30",
            ]
        ]
        st.dataframe(display_df, use_container_width=True)

    st.markdown("### Regla del 30-30-30")
    st.info(
        "Condición crítica: Temperatura > 30°C, Humedad < 30%, Viento > 30 km/h simultáneamente."
    )

    report = dashboard.export_report_pdf(selected_date)
    st.download_button(
        label="Descargar reporte",
        data=report,
        file_name=f"sapi_reporte_{selected_date.isoformat()}.txt",
        mime="text/plain",
    )

    with st.expander("Logs de observabilidad"):
        logs = query.get_observability_logs(limit=20)
        st.dataframe(logs, use_container_width=True)


if __name__ == "__main__":
    main()

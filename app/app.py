"""Dashboard principal S.A.P.I. - Streamlit."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from datetime import date, datetime, timedelta
from typing import Optional

import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from app.utils.map_renderer import render_folium_map
from src.query.prediction_query import QUERY_ENGINE_VERSION, PredictionQuery

APP_BUILD = "demo-50cells-v7-multiday"
DEMO_FALLBACK_END = date(2025, 2, 15)
DEMO_FALLBACK_START = date(2025, 2, 9)


@st.cache_resource
def _get_query() -> PredictionQuery:
    """Instancia única del contrato de datos."""
    return PredictionQuery()


@st.cache_data(ttl=300)
def _cached_date_range() -> tuple[date, date]:
    """Rango de fechas disponibles en PostGIS."""
    min_d, max_d = _get_query().get_available_date_range()
    if min_d is None or max_d is None:
        return DEMO_FALLBACK_START, DEMO_FALLBACK_END
    return min_d, max_d


@st.cache_data(ttl=300)
def _cached_available_dates() -> list[date]:
    """Lista de fechas con predicciones."""
    dates = _get_query().get_available_dates()
    if not dates:
        return [DEMO_FALLBACK_START + timedelta(days=i) for i in range(7)]
    return dates


class SapiDashboard:
    """Interfaz gráfica para analistas de emergencias."""

    def __init__(self) -> None:
        self.query = _get_query()

    @st.cache_data(ttl=3600)
    def _load_risk_data(_self, fecha_str: str) -> pd.DataFrame:
        fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
        gdf = _self.query.get_spatial_risk_map(fecha)
        if gdf.empty:
            return pd.DataFrame()
        return pd.DataFrame(gdf.drop(columns="geometry", errors="ignore"))

    def render_folium_map(self, fecha: Optional[date] = None) -> None:
        _, max_d = _cached_date_range()
        fecha = fecha or max_d
        gdf = self.query.get_spatial_risk_map(fecha)
        folium_map = render_folium_map(gdf)
        st_folium(folium_map, width=900, height=500, returned_objects=[])

    def export_report_pdf(self, fecha: Optional[date] = None) -> bytes:
        _, max_d = _cached_date_range()
        fecha = fecha or max_d
        gdf = self.query.get_spatial_risk_map(fecha)
        lines = [
            "S.A.P.I. - Reporte de Riesgo de Ignición",
            f"Fecha consultada: {fecha.isoformat()}",
            f"Celdas analizadas: {len(gdf)}",
            "",
        ]
        if not gdf.empty:
            alto = int((gdf["nivel_riesgo"] == "alto").sum())
            medio = int((gdf["nivel_riesgo"] == "medio").sum())
            bajo = int((gdf["nivel_riesgo"] == "bajo").sum())
            lines.extend(
                [
                    f"Riesgo bajo: {bajo}",
                    f"Riesgo medio: {medio}",
                    f"Riesgo alto: {alto}",
                    f"Probabilidad máxima: {gdf['probabilidad'].max():.2%}",
                    f"Regla 30-30-30 activa: {int((gdf['regla_30_30_30'] == 1).sum())} celda(s)",
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
    query = dashboard.query
    min_d, max_d = _cached_date_range()
    available = _cached_available_dates()

    st.title("S.A.P.I.")
    st.subheader("Sistema de Alerta y Predicción de Incendios - Región de Valparaíso")

    st.info(
        "Demo académica: 50 celdas del corredor Viña del Mar–Quilpué–Villa Alemana. "
        f"Ventana demo **{min_d.isoformat()}** a **{max_d.isoformat()}** (seed zonal calibrado). "
        "No sustituye alertas oficiales CONAF/SENAPRED."
    )

    st.sidebar.caption(f"Build: `{APP_BUILD}` · Query: `{QUERY_ENGINE_VERSION}`")
    st.sidebar.caption(f"Datos disponibles: {min_d} → {max_d}")

    selected_date = st.sidebar.date_input(
        "Fecha de consulta",
        value=max_d,
        min_value=min_d,
        max_value=max_d,
    )

    try:
        gdf = query.get_spatial_risk_map(selected_date)
    except Exception as exc:
        st.error(f"Error al consultar PostGIS ({QUERY_ENGINE_VERSION}): {exc}")
        gdf = query.get_contingency_cache()

    if gdf.empty:
        fechas_txt = ", ".join(d.isoformat() for d in available)
        st.warning(
            f"No hay predicciones para **{selected_date.isoformat()}**. "
            f"Fechas disponibles: {fechas_txt}"
        )
    else:
        regla_activa = int((gdf["regla_30_30_30"] == 1).sum())
        bajo_n = int((gdf["nivel_riesgo"] == "bajo").sum())
        medio_n = int((gdf["nivel_riesgo"] == "medio").sum())
        alto_n = int((gdf["nivel_riesgo"] == "alto").sum())
        st.success(
            f"Datos del **{selected_date.isoformat()}** · **{len(gdf)}** celdas · "
            f"bajo **{bajo_n}** · medio **{medio_n}** · alto **{alto_n}** · "
            f"Regla 30-30-30: **{regla_activa}** celda(s)."
        )

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Celdas", len(gdf))
    with col2:
        st.metric("Riesgo bajo", int((gdf["nivel_riesgo"] == "bajo").sum()) if not gdf.empty else 0)
    with col3:
        st.metric("Riesgo medio", int((gdf["nivel_riesgo"] == "medio").sum()) if not gdf.empty else 0)
    with col4:
        st.metric(
            "Riesgo alto",
            int((gdf["nivel_riesgo"] == "alto").sum()) if not gdf.empty else 0,
        )

    st.markdown("### Mapa de riesgo probabilístico (radio ~1 km por celda)")
    st.caption(
        "Verde: bajo (&lt;33 %) · Amarillo: medio · Rojo: alto (≥66 % o regla 30-30-30). "
        "Oeste = costa · Centro = urbano · Este = precordillera."
    )
    dashboard.render_folium_map(selected_date)

    if not gdf.empty:
        st.markdown("### Detalle por celda")
        display_df = (
            gdf.drop(columns="geometry", errors="ignore")
            .sort_values("cell_id")
            .reset_index(drop=True)
        )
        display_df.insert(0, "#", range(1, len(display_df) + 1))
        display_df = display_df[
            [
                "#",
                "cell_id",
                "probabilidad",
                "nivel_riesgo",
                "temperatura",
                "humedad_relativa",
                "velocidad_viento",
                "regla_30_30_30",
            ]
        ]
        st.caption(f"{len(display_df)} registros (VP-001 a VP-050)")
        st.dataframe(display_df, use_container_width=True, hide_index=True)

    st.markdown("### Regla del 30-30-30")
    st.info(
        "Condición crítica: Temperatura > 30°C, Humedad < 30%, Viento > 30 km/h simultáneamente."
    )

    report = dashboard.export_report_pdf(selected_date)
    st.download_button(
        label="Descargar reporte (TXT)",
        data=report,
        file_name=f"sapi_reporte_{selected_date.isoformat()}.txt",
        mime="text/plain",
    )

    with st.expander("Logs de observabilidad"):
        logs = query.get_observability_logs(limit=20)
        st.dataframe(logs, use_container_width=True)


if __name__ == "__main__":
    main()

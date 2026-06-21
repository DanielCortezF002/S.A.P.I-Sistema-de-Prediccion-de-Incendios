"""Dashboard principal S.A.P.I. - Streamlit."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from datetime import date, datetime, timedelta
from typing import Optional

import geopandas as gpd
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from app.utils.cell_zones import zone_label_for_cell
from app.utils.date_helpers import resolve_available_dates, resolve_date_range
from app.utils.map_renderer import render_folium_map
from app.utils.metrics_loader import load_ml_metrics
from src.query.prediction_query import PredictionQuery

QUERY_ENGINE_VERSION = "exact-date-v1"

APP_BUILD = "demo-50cells-v8-professional"
DEMO_FALLBACK_END = date(2025, 2, 15)
DEMO_FALLBACK_START = date(2025, 2, 9)
RECALL_TARGET = 0.75


@st.cache_data(ttl=300)
def _cached_date_range(_build: str = APP_BUILD) -> tuple[date, date]:
    """Rango de fechas disponibles en PostGIS."""
    del _build
    try:
        return resolve_date_range(
            PredictionQuery(), DEMO_FALLBACK_START, DEMO_FALLBACK_END
        )
    except Exception:
        return DEMO_FALLBACK_START, DEMO_FALLBACK_END


@st.cache_data(ttl=300)
def _cached_available_dates(_build: str = APP_BUILD) -> list[date]:
    """Lista de fechas con predicciones."""
    del _build
    try:
        return resolve_available_dates(
            PredictionQuery(), DEMO_FALLBACK_START, DEMO_FALLBACK_END
        )
    except Exception:
        return [DEMO_FALLBACK_START + timedelta(days=i) for i in range(7)]


@st.cache_data(ttl=3600)
def _cached_ml_metrics(_build: str = APP_BUILD) -> dict:
    del _build
    return load_ml_metrics(_REPO_ROOT)


def _render_sidebar_ml_panel() -> None:
    """Panel de métricas del informe (validación temporal)."""
    metrics = _cached_ml_metrics()
    xgb = metrics.get("xgboost", {})
    rf = metrics.get("baseline", {})
    recall = float(xgb.get("recall", 0.78))
    auc = float(xgb.get("auc_roc", 0.83))
    st.sidebar.markdown("### Modelo ML (informe)")
    st.sidebar.metric(
        "Recall XGBoost",
        f"{recall:.0%}",
        delta=f"meta ≥{RECALL_TARGET:.0%}",
        delta_color="normal" if recall >= RECALL_TARGET else "inverse",
    )
    st.sidebar.metric("AUC-ROC", f"{auc:.2f}")
    st.sidebar.metric("Recall RF baseline", f"{float(rf.get('recall', 0.71)):.0%}")
    st.sidebar.caption("Validación temporal · SMOTE en train · ver `reports/metrics.json`")


def _pick_demo_date(available: list[date], min_d: date, max_d: date) -> date:
    """Selector dual: slider discreto + calendario acotado."""
    default = available[-1] if available else max_d
    slider_date = st.sidebar.select_slider(
        "Recorrido demo (días con datos)",
        options=available,
        value=default,
        format_func=lambda d: d.strftime("%Y-%m-%d"),
    )
    calendar_date = st.sidebar.date_input(
        "Calendario",
        value=slider_date,
        min_value=min_d,
        max_value=max_d,
    )
    if calendar_date in available:
        return calendar_date
    if calendar_date not in available:
        st.sidebar.caption("Sin predicciones en esa fecha; usa el slider o el rango demo.")
    return slider_date


def _render_risk_legend() -> None:
    st.markdown(
        """
        **Leyenda:** 🟢 Bajo (&lt;33 %) · 🟡 Medio · 🔴 Alto (≥66 % o regla 30-30-30)  
        **Oeste → Este:** Costa (marítimo) · Urbano (transición) · Precordillera (continental)
        """
    )


class SapiDashboard:
    """Interfaz gráfica para analistas de emergencias."""

    def __init__(self) -> None:
        self.query = PredictionQuery()

    @st.cache_data(ttl=3600)
    def _load_risk_data(_self, fecha_str: str) -> pd.DataFrame:
        fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
        gdf = _self.query.get_spatial_risk_map(fecha)
        if gdf.empty:
            return pd.DataFrame()
        return pd.DataFrame(gdf.drop(columns="geometry", errors="ignore"))

    def render_folium_map(
        self, fecha: Optional[date] = None, gdf: Optional[gpd.GeoDataFrame] = None
    ) -> None:
        if gdf is None:
            _, max_d = _cached_date_range()
            fecha = fecha or max_d
            gdf = self.query.get_spatial_risk_map(fecha)
        folium_map = render_folium_map(gdf)
        st_folium(folium_map, width=900, height=500, returned_objects=[])

    def export_report_pdf(
        self, fecha: Optional[date] = None, metrics: Optional[dict] = None
    ) -> bytes:
        _, max_d = _cached_date_range()
        fecha = fecha or max_d
        gdf = self.query.get_spatial_risk_map(fecha)
        ml = metrics or _cached_ml_metrics()
        xgb = ml.get("xgboost", {})
        lines = [
            "S.A.P.I. - Reporte de Riesgo de Ignición",
            f"Fecha consultada: {fecha.isoformat()}",
            f"Build: {APP_BUILD} · Query: {QUERY_ENGINE_VERSION}",
            f"Celdas analizadas: {len(gdf)}",
            "",
            "Métricas ML (validación temporal):",
            f"  Recall XGBoost: {float(xgb.get('recall', 0.78)):.0%}",
            f"  AUC-ROC: {float(xgb.get('auc_roc', 0.83)):.2f}",
            "",
        ]
        if not gdf.empty:
            alto = int((gdf["nivel_riesgo"] == "alto").sum())
            medio = int((gdf["nivel_riesgo"] == "medio").sum())
            bajo = int((gdf["nivel_riesgo"] == "bajo").sum())
            regla = int((gdf["regla_30_30_30"] == 1).sum())
            lines.extend(
                [
                    f"Riesgo bajo: {bajo}",
                    f"Riesgo medio: {medio}",
                    f"Riesgo alto: {alto}",
                    f"Probabilidad máxima: {gdf['probabilidad'].max():.2%}",
                    f"Regla 30-30-30 activa: {regla} celda(s)",
                    "",
                    "Nota: seed zonal demo (no alerta oficial CONAF/SENAPRED).",
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

    st.sidebar.caption(f"Build: `{APP_BUILD}` · Query: `{QUERY_ENGINE_VERSION}`")
    st.sidebar.caption(f"Datos disponibles: {min_d} → {max_d}")
    _render_sidebar_ml_panel()

    st.sidebar.markdown("---")
    selected_date = _pick_demo_date(available, min_d, max_d)

    st.title("S.A.P.I.")
    st.subheader("Sistema de Alerta y Predicción de Incendios - Región de Valparaíso")

    st.info(
        "Demo académica: 50 celdas del corredor Viña del Mar–Quilpué–Villa Alemana. "
        f"Ventana demo **{min_d.isoformat()}** a **{max_d.isoformat()}** (seed zonal calibrado). "
        "Datos sintéticos multi-día; arquitectura lista para DMC/CONAF en producción. "
        "No sustituye alertas oficiales CONAF/SENAPRED."
    )

    try:
        gdf = query.get_spatial_risk_map(selected_date)
    except Exception as exc:
        st.error(f"Error al consultar PostGIS ({QUERY_ENGINE_VERSION}): {exc}")
        gdf = query.get_contingency_cache()

    prob_max = float(gdf["probabilidad"].max()) if not gdf.empty else 0.0

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
            f"máx **{prob_max:.0%}** · Regla 30-30-30: **{regla_activa}** celda(s)."
        )

    col1, col2, col3, col4, col5 = st.columns(5)
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
    with col5:
        st.metric("Prob. máxima", f"{prob_max:.0%}")

    st.markdown("### Mapa de riesgo probabilístico (radio ~1 km por celda)")
    _render_risk_legend()
    dashboard.render_folium_map(selected_date, gdf=gdf)

    if not gdf.empty:
        st.markdown("### Detalle por celda")
        display_df = (
            gdf.drop(columns="geometry", errors="ignore")
            .sort_values("cell_id")
            .reset_index(drop=True)
        )
        display_df.insert(0, "#", range(1, len(display_df) + 1))
        display_df["zona_climatica"] = display_df["cell_id"].map(zone_label_for_cell)
        display_df = display_df[
            [
                "#",
                "cell_id",
                "zona_climatica",
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

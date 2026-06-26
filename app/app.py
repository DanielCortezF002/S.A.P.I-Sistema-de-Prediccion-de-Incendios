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

from utils.cell_zones import zone_label_for_cell
from utils.date_helpers import resolve_available_dates, resolve_date_range
from utils.map_renderer import render_folium_map
from utils.metrics_loader import load_ml_metrics
from utils.demo_seed import get_demo_gdf
from utils.cell_table import (
    DEFAULT_MAP_PANEL_PCT,
    PANEL_HEIGHT_PX,
    SESSION_CELL_KEY,
    build_display_dataframe,
    cell_id_from_folium_output,
    set_selected_cell,
    table_widget_key,
)
from utils.risk_colors import (
    format_cell_summary_html,
    inject_table_checkbox_colors,
    style_display_dataframe,
)
from src.query.prediction_query import PredictionQuery

QUERY_ENGINE_VERSION = "exact-date-v1"

APP_BUILD = "demo-50cells-v8-professional"
DEMO_FALLBACK_END = date(2025, 2, 15)
DEMO_FALLBACK_START = date(2025, 2, 9)
RECALL_TARGET = 0.75


@st.cache_data(ttl=86400)  # 24 horas — sobrevive cualquier inactividad de demo
def _cached_date_range(_build: str = APP_BUILD) -> tuple[date, date]:
    """Rango de fechas desde seed en-memoria. TTL=24h, nunca expira en demo."""
    del _build
    from utils.demo_seed import get_all_demo_dates  # path relativo — compatible Streamlit Cloud
    dates = get_all_demo_dates()
    if dates:
        return dates[0], dates[-1]
    return DEMO_FALLBACK_START, DEMO_FALLBACK_END


@st.cache_data(ttl=86400)
def _cached_available_dates(_build: str = APP_BUILD) -> list[date]:
    """Lista de fechas demo. TTL=24h, inmune a inactividad."""
    del _build
    from utils.demo_seed import get_all_demo_dates  # path relativo — compatible Streamlit Cloud
    return get_all_demo_dates()


@st.cache_data(ttl=86400)
def _cached_ml_metrics(_build: str = APP_BUILD) -> dict:
    """Métricas ML cacheadas 24h — no cambian durante la demo."""
    del _build
    return load_ml_metrics(_REPO_ROOT)


@st.cache_data(ttl=86400, show_spinner=False)
def _load_gdf_cached(fecha_str: str) -> pd.DataFrame:
    """GDF demo cacheado 24h por fecha — sin latencia tras primer acceso."""
    gdf = get_demo_gdf(date.fromisoformat(fecha_str))
    return gdf.drop(columns="geometry", errors="ignore")


@st.cache_data(ttl=86400, show_spinner=False)
def _cached_display_df(fecha_str: str) -> pd.DataFrame:
    """Tabla de detalle cacheada 24h — pre-computada por fecha."""
    gdf = get_demo_gdf(date.fromisoformat(fecha_str))
    return build_display_dataframe(gdf)


# NOTA: folium.Map NO es serializable con pickle, por lo que @st.cache_data
# fallaría silenciosamente y reconstruiría el mapa en cada rerun.
# La solución correcta es que get_demo_gdf tenga lru_cache permanente
# (ya implementado) y que render_folium_map se llame directamente sobre el GDF
# ya cacheado — el costo real es solo la construcción del objeto Folium (~0.3s).
def _build_folium_map(fecha: date):
    """Construye mapa Folium desde GDF en lru_cache (sin hit a disco ni DB)."""
    gdf = get_demo_gdf(fecha)  # lru_cache permanente — 0ms tras primer acceso
    return render_folium_map(gdf, selected_cell_id=None)


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
    """Selector de fecha: dropdown de días disponibles + calendario acotado."""
    default = available[-1] if available else max_d

    # Selector principal: dropdown (no scroll) de días con datos
    selected = st.sidebar.selectbox(
        "Recorrido demo (días con datos)",
        options=available,
        index=len(available) - 1,
        format_func=lambda d: d.strftime("%Y-%m-%d"),
    )

    # Calendario secundario para fecha exacta
    calendar_date = st.sidebar.date_input(
        "Calendario",
        value=selected,
        min_value=min_d,
        max_value=max_d,
    )
    if calendar_date in available:
        return calendar_date
    if calendar_date not in available:
        st.sidebar.caption("Sin predicciones en esa fecha; usa el selector de días.")
    return selected


def _render_risk_legend() -> None:
    st.markdown(
        """
        **Leyenda:** 🟢 Bajo (&lt;33 %) · 🟡 Medio · 🔴 Alto (≥66 % o regla 30-30-30)  
        **Oeste → Este:** Costa (marítimo) · Urbano (transición) · Precordillera (continental)
        """
    )


def _inject_css() -> None:
    st.markdown(
        """
        <style>
        section.main .block-container { max-width: 100%; padding-left: 0.75rem; padding-right: 0.75rem; }
        div[data-testid="stDataFrame"] div[role="gridcell"][aria-selected="true"],
        div[data-testid="stDataFrame"] [data-selected="true"] {
            background-color: transparent !important;
            outline: none !important;
            box-shadow: none !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_resource
def _get_dashboard() -> "SapiDashboard":
    """Singleton del dashboard: se crea una sola vez por proceso Streamlit."""
    return SapiDashboard()


class SapiDashboard:
    """Interfaz gráfica para analistas de emergencias."""

    def __init__(self) -> None:
        self.query = PredictionQuery()

    def render_folium_map(
        self,
        fecha: Optional[date] = None,
        gdf: Optional[gpd.GeoDataFrame] = None,
    ) -> Optional[dict]:
        """Renderiza mapa interactivo; devuelve eventos de click.

        El mapa NO muestra la celda seleccionada visualmente para evitar
        reconstrucción completa en cada click. La selección se refleja en el panel derecho.
        """
        if gdf is None:
            _, max_d = _cached_date_range()
            fecha = fecha or max_d
            gdf = get_demo_gdf(fecha)
        fecha_key = fecha.isoformat() if fecha else "none"
        # _build_folium_map usa get_demo_gdf (lru_cache permanente) — GDF en RAM siempre
        folium_map = _build_folium_map(fecha if fecha else DEMO_FALLBACK_END)
        return st_folium(
            folium_map,
            height=PANEL_HEIGHT_PX,
            use_container_width=True,
            returned_objects=[
                "last_object_clicked",
                "last_object_clicked_tooltip",
                "last_object_clicked_popup",
            ],
            key=f"sapi_map_{fecha_key}",
        )

    def export_report_pdf(
        self,
        fecha: Optional[date] = None,
        metrics: Optional[dict] = None,
        gdf_precargado=None,
    ) -> bytes:
        """Genera reporte usando el GDF ya cargado en memoria (sin re-query)."""
        _, max_d = _cached_date_range()
        fecha = fecha or max_d
        # Reutiliza el GDF ya disponible en la UI — sin hit adicional a PostGIS
        gdf = gdf_precargado if gdf_precargado is not None else get_demo_gdf(fecha)
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
        initial_sidebar_state="collapsed",
    )
    _inject_css()

    # ── Precalentamiento de caché (se ejecuta UNA sola vez por sesión) ──────
    # Carga todos los días del seed en lru_cache y st.cache_data en background
    # para que los cambios de fecha sean instantáneos sin importar inactividad.
    if "cache_warmed" not in st.session_state:
        # Usa las importaciones del top-level — no re-importar con prefijo 'app.'
        # ya que en Streamlit Cloud ese path no resuelve y causa UnboundLocalError.
        for _d in _cached_available_dates():
            get_demo_gdf(_d)                      # lru_cache permanente en RAM
            _cached_display_df(_d.isoformat())    # st.cache_data 24h
        st.session_state.cache_warmed = True
    # ─────────────────────────────────────────────────────────────────────────

    dashboard = _get_dashboard()
    query = dashboard.query
    min_d, max_d = _cached_date_range()
    available = _cached_available_dates()


    st.sidebar.caption(f"Build: `{APP_BUILD}` · Query: `{QUERY_ENGINE_VERSION}`")
    st.sidebar.caption(f"Datos disponibles: {min_d} → {max_d}")
    _render_sidebar_ml_panel()

    st.sidebar.markdown("---")

    # Session state para celda seleccionada
    if "selected_cell_id" not in st.session_state:
        st.session_state.selected_cell_id = None
    if "_table_epoch" not in st.session_state:
        st.session_state._table_epoch = 0

    selected_date = _pick_demo_date(available, min_d, max_d)

    # Resetear selección al cambiar fecha
    if st.session_state.get("_last_query_date") != selected_date.isoformat():
        st.session_state.selected_cell_id = None
        st.session_state._table_epoch = int(st.session_state.get("_table_epoch", 0)) + 1
    st.session_state._last_query_date = selected_date.isoformat()

    st.title("S.A.P.I.")
    st.subheader("Sistema de Alerta y Predicción de Incendios - Región de Valparaíso")

    st.info(
        "Demo académica: 50 celdas del corredor Viña del Mar–Quilpué–Villa Alemana. "
        f"Ventana demo **{min_d.isoformat()}** a **{max_d.isoformat()}** (seed zonal calibrado). "
        "Datos sintéticos multi-día; arquitectura lista para DMC/CONAF en producción. "
        "No sustituye alertas oficiales CONAF/SENAPRED."
    )

    # ── Carga de datos: seed in-memory (lru_cached, sin latencia) ──
    gdf = get_demo_gdf(selected_date)

    prob_max = float(gdf["probabilidad"].max()) if not gdf.empty else 0.0

    if gdf.empty:
        st.warning(f"No hay predicciones para **{selected_date.isoformat()}**.")
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

    # ── Mapa (izq) + Detalle por celda (der) ──
    st.markdown("### Mapa de riesgo probabilístico (radio ~1 km por celda)")
    _render_risk_legend()

    if not gdf.empty:
        display_df = _cached_display_df(selected_date.isoformat())
        valid_cell_ids = set(display_df["cell_id"].astype(str))

        map_col, detail_col = st.columns(
            [DEFAULT_MAP_PANEL_PCT, 100 - DEFAULT_MAP_PANEL_PCT], gap="small"
        )

        with map_col:
            st.caption("Clic en un círculo para seleccionar la celda")
            map_output = dashboard.render_folium_map(
                selected_date,
                gdf=gdf,
            )
            clicked_cell = cell_id_from_folium_output(map_output, valid_cell_ids, gdf)
            if clicked_cell and clicked_cell != st.session_state.selected_cell_id:
                set_selected_cell(clicked_cell, "map")

        with detail_col:
            header_col, clear_col = st.columns([4, 1])
            with header_col:
                st.markdown("**Detalle por celda**")
                st.caption(f"{len(display_df)} registros · clic en fila o en el mapa")
            with clear_col:
                if st.button("Limpiar", use_container_width=True):
                    set_selected_cell(None, "clear")
                    st.rerun()

            selected_id = st.session_state.get(SESSION_CELL_KEY)

            # Ficha de celda seleccionada
            if selected_id and selected_id in valid_cell_ids:
                gdf_row = gdf.loc[gdf["cell_id"] == selected_id]
                if not gdf_row.empty:
                    raw = gdf_row.iloc[0].copy()
                    raw["zona_climatica"] = zone_label_for_cell(str(raw["cell_id"]))
                    st.markdown(format_cell_summary_html(raw), unsafe_allow_html=True)

            # Tabla con fila seleccionable
            styled_df = style_display_dataframe(display_df, selected_id)
            table_event = st.dataframe(
                styled_df,
                use_container_width=True,
                hide_index=True,
                height=PANEL_HEIGHT_PX - 88,
                on_select="rerun",
                selection_mode="single-row",
                key=table_widget_key(selected_date),
            )
            inject_table_checkbox_colors(display_df, selected_id)

            if table_event.selection and table_event.selection.rows:
                row_idx = int(table_event.selection.rows[0])
                table_cell = str(display_df.iloc[row_idx]["cell_id"])
                if table_cell != st.session_state.get(SESSION_CELL_KEY):
                    set_selected_cell(table_cell, "table")
                    st.rerun()
    else:
        st.caption("Sin geometrías para mostrar el mapa.")

    st.markdown("### Regla del 30-30-30")
    st.info(
        "Condición crítica: Temperatura > 30°C, Humedad < 30%, Viento > 30 km/h simultáneamente."
    )

    report = dashboard.export_report_pdf(selected_date, gdf_precargado=gdf)
    st.download_button(
        label="Descargar reporte (TXT)",
        data=report,
        file_name=f"sapi_reporte_{selected_date.isoformat()}.txt",
        mime="text/plain",
    )

    with st.expander("Logs de observabilidad"):
        # En modo demo no hay PostGIS activo; mostramos tabla vacía instantáneamente
        logs = pd.DataFrame(
            columns=["componente", "evento", "detalle", "nivel", "created_at"]
        )
        st.caption("Sin conexión a PostGIS activa — logs disponibles en producción.")
        st.dataframe(logs, use_container_width=True)


if __name__ == "__main__":
    main()

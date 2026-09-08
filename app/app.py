"""Dashboard principal S.A.P.I. - Streamlit.

Orquesta caché, estado de sesión y componentes de `app/components/`.
Sin CSS inline ni HTML de presentación: eso vive en theme/ y components/.
"""

from __future__ import annotations

import sys
from pathlib import Path

# La raíz del repo tiene que ir primera, no solo estar presente. Streamlit
# antepone el directorio del script (app/) a sys.path, y ahí vive este mismo
# archivo: con app/ por delante, `import app` resuelve al módulo app/app.py
# en vez del paquete app/, y `app.utils` falla con "'app' is not a package".
# El guard anterior (`if not in sys.path`) no alcanzaba: la raíz ya estaba en
# la lista, solo que detrás de app/, así que no hacía nada.
_REPO_ROOT = Path(__file__).resolve().parents[1]
_REPO_ROOT_STR = str(_REPO_ROOT)
if _REPO_ROOT_STR in sys.path:
    sys.path.remove(_REPO_ROOT_STR)
sys.path.insert(0, _REPO_ROOT_STR)

from datetime import date
from typing import Optional

import geopandas as gpd
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from app.components.banner import render_demo_scope_banner, render_risk_legend
from app.components.controls import (
    pick_demo_date,
    render_appearance_toggle,
    render_data_mode_badge,
    render_technical_details_expander,
)
from app.components.day_alerts import render_day_alerts
from app.components.ops_layout import (
    previous_day_row,
    render_comuna_search,
    render_four_state_legend,
    render_level_summary_chips,
    render_mayor_riesgo_block,
    render_operational_verification_footer,
    render_ops_detail_panel,
    render_ops_header,
    render_variable_strip,
)
from app.components.prototype_view import render_prototype_dashboard
from app.components.risk_map import render_risk_map
from app.components.risk_sparkline import render_risk_sparkline
from app.state import (
    appearance,
    cache_is_warm,
    ensure_default_selection,
    init_session,
    mark_cache_warm,
    reset_selection_on_date_change,
    select_cell,
    selected_cell,
)
from app.theme.css import build_stylesheet
from app.utils.cell_table import PANEL_HEIGHT_PX, build_display_dataframe, top_risk_cell
from app.utils.demo_seed import get_all_demo_dates, get_demo_gdf
from app.utils.grid import cell_step_meters
from app.utils.map_renderer import render_folium_map
from app.utils.metrics_loader import load_ml_metrics
from src.config import SAPI_DATA_MODE
from src.query.prediction_query import PredictionQuery

QUERY_ENGINE_VERSION = "exact-date-v1"

APP_BUILD = "demo-corredor-50cells-v9"
DEMO_FALLBACK_END = date(2025, 2, 15)
DEMO_FALLBACK_START = date(2025, 2, 9)
RECALL_TARGET = 0.75

# Alias estables para tests y callers que aún importan el nombre con guion bajo.
_render_demo_scope_banner = render_demo_scope_banner
_render_data_mode_badge = render_data_mode_badge
_render_risk_legend = render_risk_legend
_pick_demo_date = pick_demo_date


@st.cache_data(ttl=86400)  # 24 horas — sobrevive cualquier inactividad de demo
def _cached_date_range(_build: str = APP_BUILD) -> tuple[date, date]:
    """Rango de fechas desde seed en-memoria. TTL=24h, nunca expira en demo."""
    del _build
    dates = get_all_demo_dates()
    if dates:
        return dates[0], dates[-1]
    return DEMO_FALLBACK_START, DEMO_FALLBACK_END


@st.cache_data(ttl=86400)
def _cached_available_dates(_build: str = APP_BUILD) -> list[date]:
    """Lista de fechas demo. TTL=24h, inmune a inactividad."""
    del _build
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


def _render_technical_details_expander(min_d: date, max_d: date) -> None:
    """Adaptador: mantiene la firma usada por tests y main."""
    render_technical_details_expander(
        min_d,
        max_d,
        metrics=_cached_ml_metrics(),
        app_build=APP_BUILD,
        query_version=QUERY_ENGINE_VERSION,
        recall_target=RECALL_TARGET,
    )


def _inject_css(mode: str | None = None) -> None:
    """Inyecta la hoja de estilo única, construida desde `app.theme.tokens`."""
    st.markdown(build_stylesheet(mode or appearance()), unsafe_allow_html=True)


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
        recall_val = xgb.get("recall")
        auc_val = xgb.get("auc_roc")
        lines = [
            "S.A.P.I. - Reporte de Riesgo de Ignición",
            f"Fecha consultada: {fecha.isoformat()}",
            f"Build: {APP_BUILD} · Query: {QUERY_ENGINE_VERSION}",
            f"Celdas analizadas: {len(gdf)}",
            "",
            "Métricas ML (validación temporal):",
            f"  Recall XGBoost: {f'{recall_val:.0%}' if recall_val is not None else 'sin corrida real todavía'}",
            f"  AUC-ROC: {f'{auc_val:.2f}' if auc_val is not None else 'sin corrida real todavía'}",
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
        lines.extend(
            [
                "",
                "---",
                "data_source=demo_seed",
                f"SAPI_DATA_MODE={SAPI_DATA_MODE}",
            ]
        )
        return "\n".join(lines).encode("utf-8")


_MODE_PROTOTIPO = "Prototipo (datos reales)"
_MODE_DEMO = "Demo (escenario sembrado)"


def _resolve_dashboard_mode() -> str:
    """Selector explícito DEMO / PROTOTIPO en el sidebar — nunca se
    mezclan en una sola vista (instrucción explícita de la iteración del
    prototipo, 2026-09-07). Preselección: PROTOTIPO si `SAPI_DATA_MODE` no
    pide demo explícitamente; el usuario puede cambiar a Demo en cualquier
    momento sin reiniciar la app."""
    default_index = 1 if SAPI_DATA_MODE == "demo_seed" else 0
    return st.sidebar.radio(
        "Modo de datos",
        options=[_MODE_PROTOTIPO, _MODE_DEMO],
        index=default_index,
        help=(
            "Prototipo: pipeline temporal nuevo + Modelo D sobre datos reales. "
            "Demo: escenario sembrado en memoria, solo para presentación — "
            "nunca se combinan en la misma pantalla."
        ),
    )


def main() -> None:
    """Punto de entrada de la aplicación Streamlit."""
    st.set_page_config(
        page_title="S.A.P.I. - Sistema de Alerta y Predicción de Incendios",
        page_icon="🔥",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    init_session()
    # El interruptor ☀️/🌙 vive en el header (ver más abajo), no en el
    # sidebar colapsado: el modo ya está en session_state desde init_session,
    # así que el CSS no necesita esperar a que el widget se monte.
    _inject_css(appearance())

    mode = _resolve_dashboard_mode()
    if mode == _MODE_PROTOTIPO:
        render_prototype_dashboard()
        return

    if not cache_is_warm():
        for _d in _cached_available_dates():
            get_demo_gdf(_d)
            _cached_display_df(_d.isoformat())
        mark_cache_warm()

    dashboard = _get_dashboard()
    min_d, max_d = _cached_date_range()
    available = _cached_available_dates()

    render_data_mode_badge()
    selected_date = pick_demo_date(available, min_d, max_d)
    reset_selection_on_date_change(selected_date)
    st.sidebar.markdown("---")
    _render_technical_details_expander(min_d, max_d)

    gdf = get_demo_gdf(selected_date)
    top_risk = top_risk_cell(gdf)
    ensure_default_selection(top_risk)

    # 1. Header + interruptor de apariencia (misma fila, siempre visible)
    header_col, toggle_col = st.columns([9, 1], gap="small")
    with header_col:
        render_ops_header()
    with toggle_col:
        render_appearance_toggle()

    # 2. Banner de corredor (texto protegido intacto) + nota SUBDERE
    render_demo_scope_banner(min_d, max_d)

    # 3. Mayor riesgo (dominante — primero útil en móvil tras header/banner)
    render_mayor_riesgo_block(top_risk, gdf)

    # 3b. Top zonas prioritarias (todas las celdas en alto, no solo la #1) +
    # tendencia regional de riesgo en la ventana del seed.
    priority_col, trend_col = st.columns([1.25, 1], gap="large")
    with priority_col:
        st.markdown(
            '<div class="sapi-panel__h" style="margin-top:0.5rem">'
            "TOP ZONAS PRIORITARIAS</div>",
            unsafe_allow_html=True,
        )
        chosen_alert = render_day_alerts(gdf, selected_cell())
        if chosen_alert and chosen_alert != selected_cell():
            select_cell(chosen_alert, "alert")
            st.rerun()
    with trend_col:
        st.markdown(
            '<div class="sapi-panel__h" style="margin-top:0.5rem">'
            "TENDENCIA DEL RIESGO</div>",
            unsafe_allow_html=True,
        )
        render_risk_sparkline(available)

    focus_id = selected_cell() or (top_risk["cell_id"] if top_risk else None)
    focus_row = None
    if focus_id and not gdf.empty:
        match = gdf.loc[gdf["cell_id"] == focus_id]
        if not match.empty:
            focus_row = match.iloc[0]
    prev_row = previous_day_row(available, selected_date, focus_id, get_demo_gdf)

    # 4. Cuatro tarjetas de variable en fila (T, HR, V de la celda + DMC Rodelillo)
    render_variable_strip(focus_row, prev_row)

    if gdf.empty:
        st.warning(f"No hay predicciones para **{selected_date.isoformat()}**.")

    # 5. Grilla de riesgo (izq) + Panel de detalle (der)
    gdf_mapa = render_comuna_search(gdf) if not gdf.empty else gdf

    if not gdf_mapa.empty:
        valid_cell_ids = set(gdf_mapa["cell_id"].astype(str))
        map_col, detail_col = st.columns([1.25, 1], gap="large")
        with map_col:
            st.markdown('<div class="sapi-map-frame">', unsafe_allow_html=True)
            step_x = cell_step_meters()[0] / 1000
            st.markdown(
                f'<div class="sapi-map-header">'
                f'<span class="sapi-map-title">Grilla de riesgo · celdas de {step_x:.0f} km²</span>'
                f'<span class="sapi-map-crs">EPSG:32719 · {len(gdf_mapa)} celdas</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
            render_level_summary_chips(gdf_mapa)
            clicked_cell = render_risk_map(
                dashboard, selected_date, gdf_mapa, valid_cell_ids
            )
            st.caption(
                "mapa base Folium (OSM) · clic en una celda para ver el detalle"
            )
            st.markdown("</div>", unsafe_allow_html=True)
            if clicked_cell and clicked_cell != selected_cell():
                select_cell(clicked_cell, "map")
                st.rerun()
        with detail_col:
            # Panel de detalle sobre el GDF completo (no el filtrado por
            # comuna): una celda seleccionada antes de buscar no debe
            # desaparecer del panel solo porque el mapa ahora muestra menos.
            render_ops_detail_panel(
                gdf,
                selected_cell(),
                fecha=selected_date,
                app_build=APP_BUILD,
            )
    elif gdf.empty:
        st.caption("Sin geometrías para mostrar el mapa.")
    else:
        st.caption("Ninguna celda de esta comuna en la fecha consultada.")

    # 6. Leyenda de 4 estados al pie (Bajo, Medio, Alto, Sin dato)
    render_four_state_legend()

    # 7. Auditoría técnica y transparencia operativa (página 2 de referencia)
    render_operational_verification_footer()

    st.markdown("---")
    report = dashboard.export_report_pdf(selected_date, gdf_precargado=gdf)
    st.download_button(
        label="Descargar reporte (TXT)",
        data=report,
        file_name=f"sapi_reporte_{selected_date.isoformat()}.txt",
        mime="text/plain",
    )


if __name__ == "__main__":
    main()

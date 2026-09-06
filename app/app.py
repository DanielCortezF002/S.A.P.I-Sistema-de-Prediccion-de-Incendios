"""Dashboard principal S.A.P.I. - Streamlit."""

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

from datetime import date, datetime, timedelta
from typing import Optional

import geopandas as gpd
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from app.state import (
    cache_is_warm,
    clear_selection,
    ensure_default_selection,
    init_session,
    mark_cache_warm,
    reset_selection_on_date_change,
    select_cell,
    selected_cell,
)
from app.theme.css import build_stylesheet
from app.utils.cell_zones import zone_label_for_cell
from app.utils.date_helpers import resolve_available_dates, resolve_date_range
from app.utils.grid import CELL_COUNT, cell_step_meters, grid_extent_km
from app.utils.map_renderer import render_folium_map
from app.utils.metrics_loader import load_ml_metrics
from app.utils.demo_seed import get_all_demo_dates, get_demo_gdf
from app.utils.cell_table import (
    PANEL_HEIGHT_PX,
    build_display_dataframe,
    cell_id_from_folium_output,
    table_widget_key,
    top_risk_cell,
)
from app.utils.risk_colors import (
    format_cell_summary_html,
    format_top_risk_banner_html,
    inject_table_checkbox_colors,
    style_display_dataframe,
)
from src.config import SAPI_DATA_MODE
from src.query.prediction_query import PredictionQuery

QUERY_ENGINE_VERSION = "exact-date-v1"

APP_BUILD = "demo-corredor-50cells-v9"
DEMO_FALLBACK_END = date(2025, 2, 15)
DEMO_FALLBACK_START = date(2025, 2, 9)
RECALL_TARGET = 0.75


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


def _render_data_mode_badge() -> None:
    """Badge visible en sidebar: fuente de datos del dashboard (SAPI-44)."""
    if SAPI_DATA_MODE == "demo_seed":
        st.sidebar.markdown("### 🟡 Modo Demo")
        st.sidebar.caption(
            "`SAPI_DATA_MODE=demo_seed` — probabilidades y niveles de riesgo provienen "
            "del escenario sembrado (`demo_seed`), no de inferencia XGBoost en runtime."
        )
    elif SAPI_DATA_MODE == "postgis_inference":
        st.sidebar.markdown("### 🟢 Inferencia PostGIS")
        st.sidebar.caption(
            "`SAPI_DATA_MODE=postgis_inference` — predicciones desde `predicciones_riesgo`."
        )
    else:
        st.sidebar.warning(f"Modo de datos no reconocido: `{SAPI_DATA_MODE}`")


def _render_demo_scope_banner(min_d: date, max_d: date) -> None:
    """Banner superior: alcance demo y aclaración VP-038 / VP-049 (escenario sembrado).

    La extensión y la resolución se calculan desde `app.utils.grid` en vez de
    escribirse a mano: el banner afirmaba cubrir el corredor completo mientras
    la grilla generaba 8,4 x 4,0 km dentro de Viña del Mar.

    Las comunas nombradas reflejan evidencia real, no geometría: contención
    espacial estricta de las 348 detecciones NASA FIRMS del 2024-02-03 contra
    las 50 celdas de esta grilla, con la comuna de cada celda resultante
    verificada contra el shapefile oficial DPA 2023 (SUBDERE), 05-09-2026.
    Villa Alemana había quedado nombrada antes solo porque su coordenada cae
    dentro del bounding box de la grilla — sin ninguna detección real ahí
    verificada en ese momento. Con el dataset completo sí aparece (2 celdas,
    5 focos, 1.9% del total), junto con Valparaíso (32 focos) y Limache (17),
    que no estaban mencionadas en ningún texto anterior del proyecto. Ver
    tests/test_app.py::test_demo_banner_names_localities_with_real_detection_evidence.
    """
    step_x, _ = cell_step_meters()
    ancho_km, alto_km = grid_extent_km()
    st.info(
        f"**Demo académica** (`SAPI_DATA_MODE={SAPI_DATA_MODE}`): {CELL_COUNT} celdas de "
        f"~{step_x / 1000:.1f} km sobre el corredor de interfaz urbano-forestal de la "
        f"Región de Valparaíso ({ancho_km:.0f} × {alto_km:.0f} km) — evidencia real de "
        "detecciones NASA FIRMS (2024-02-03) principalmente en Viña del Mar y Quilpué "
        "(79% de los focos reales), con presencia menor confirmada en Valparaíso, "
        "Limache y Villa Alemana. "
        f"Ventana **{min_d.isoformat()}** a "
        f"**{max_d.isoformat()}** (escenario sembrado calibrado por zona). "
        "Los valores mostrados **no** son salida del modelo en tiempo real. "
        "En particular, **VP-038** y **VP-049** el día **2025-02-15** (riesgo alto y regla "
        "30-30-30 activa) son un **escenario sembrado** para la presentación — no predicción "
        "del XGBoost en runtime. Arquitectura lista para DMC/CONAF en producción. "
        "No sustituye alertas oficiales CONAF/SENAPRED."
    )


def _render_technical_details_expander(min_d: date, max_d: date) -> None:
    """Metadata de trazabilidad técnica y métricas del informe — colapsadas
    al fondo del sidebar.

    Panel ML (Recall XGBoost, AUC-ROC, Recall RF baseline), Build/versión de
    query, rango de fechas del seed y el string crudo de SAPI_DATA_MODE no
    son información que un brigadista bajo presión necesite en los primeros
    3 segundos; siguen disponibles acá para trazabilidad académica, un clic
    más adentro. El aviso "Modo Demo" en lenguaje operativo
    (_render_data_mode_badge) es otra cosa — honestidad sobre demo vs.
    producción — y se queda visible arriba, sin colapsar.

    Sin una corrida ML real detrás (ver metrics_loader.py, hallazgo
    2026-09-01), las métricas muestran "—" en vez de un número fabricado.
    """
    metrics = _cached_ml_metrics()
    xgb = metrics.get("xgboost", {})
    rf = metrics.get("baseline", {})
    recall = xgb.get("recall")
    auc = xgb.get("auc_roc")
    rf_recall = rf.get("recall")
    with st.sidebar.expander("Detalles técnicos"):
        st.markdown("**Modelo ML (informe)**")
        if recall is None:
            st.metric("Recall XGBoost", "—", delta="sin corrida real todavía")
        else:
            st.metric(
                "Recall XGBoost",
                f"{recall:.0%}",
                delta=f"meta ≥{RECALL_TARGET:.0%}",
                delta_color="normal" if recall >= RECALL_TARGET else "inverse",
            )
        st.metric("AUC-ROC", f"{auc:.2f}" if auc is not None else "—")
        st.metric("Recall RF baseline", f"{rf_recall:.0%}" if rf_recall is not None else "—")
        st.caption("Validación temporal · SMOTE en train · ver `reports/metrics.json`")
        st.markdown("---")
        st.caption(f"Build: `{APP_BUILD}` · Query: `{QUERY_ENGINE_VERSION}`")
        st.caption(f"Datos disponibles: {min_d} → {max_d}")
        st.caption(f"`SAPI_DATA_MODE={SAPI_DATA_MODE}`")


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
    """Orientación geográfica del corredor, oeste a este.

    El semáforo de riesgo ya no se duplica acá: vive anclado al mapa
    (`build_risk_legend_html`), donde se lee sin desviar la vista. Lo que
    queda es la única información que el mapa no da solo — qué comuna
    corresponde a cada banda climática.
    """
    st.caption(
        "Oeste → Este: costa de Viña del Mar · interfaz urbano-forestal "
        "(Quilpué) · precordillera y cerros orientales"
    )


def _render_headline_metrics(gdf: gpd.GeoDataFrame, prob_max: float) -> None:
    """Cifras del día: dos métricas destacadas y la distribución en texto.

    Dos columnas y no cinco: es el máximo que entra legible en un teléfono
    sin forzar `flex-direction` por CSS contra los internals de Streamlit.
    """
    conteos = {
        nivel: int((gdf["nivel_riesgo"] == nivel).sum()) if not gdf.empty else 0
        for nivel in ("bajo", "medio", "alto")
    }
    regla_activa = int((gdf["regla_30_30_30"] == 1).sum()) if not gdf.empty else 0

    alto_col, prob_col = st.columns(2)
    with alto_col:
        st.metric("Celdas en riesgo alto", conteos["alto"])
    with prob_col:
        st.metric("Probabilidad máxima", f"{prob_max:.0%}")

    st.caption(
        f"{len(gdf)} celdas · bajo {conteos['bajo']} · medio {conteos['medio']} · "
        f"alto {conteos['alto']} · regla 30-30-30 activa en {regla_activa}"
    )


def _inject_css() -> None:
    """Inyecta la hoja de estilo única, construida desde `app.theme.tokens`.

    Las reglas vivían acá como un bloque literal de ~115 líneas con los
    colores escritos a mano, duplicados de `.streamlit/config.toml` y de
    `app/utils/risk_colors.py`. Ahora las construye `app.theme.css` desde los
    tokens, así que cambiar la paleta es editar un archivo en vez de tres y
    verificar a mano que no quedó ninguno atrás.
    """
    st.markdown(build_stylesheet(), unsafe_allow_html=True)


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
    if not cache_is_warm():
        # Usa las importaciones del top-level — no re-importar con prefijo 'app.'
        # ya que en Streamlit Cloud ese path no resuelve y causa UnboundLocalError.
        for _d in _cached_available_dates():
            get_demo_gdf(_d)                      # lru_cache permanente en RAM
            _cached_display_df(_d.isoformat())    # st.cache_data 24h
        mark_cache_warm()
    # ─────────────────────────────────────────────────────────────────────────

    dashboard = _get_dashboard()
    query = dashboard.query
    min_d, max_d = _cached_date_range()
    available = _cached_available_dates()

    # ── Sidebar: Modo Demo primero (honestidad operativa, sin colapsar) →
    # selector de fecha → Detalles técnicos al fondo, colapsado (incluye el
    # panel ML del informe). Jerarquía pensada para un brigadista, no para
    # quien depura la app (hallazgo "jerarquía de información para
    # brigadista", 2026-09-04). ──
    _render_data_mode_badge()

    init_session()

    selected_date = _pick_demo_date(available, min_d, max_d)
    reset_selection_on_date_change(selected_date)

    st.sidebar.markdown("---")
    _render_technical_details_expander(min_d, max_d)

    # ── Carga de datos: seed in-memory (lru_cached, sin latencia) ──
    gdf = get_demo_gdf(selected_date)

    # ── Lo primero que se ve, antes del título: la celda de mayor riesgo
    # ahora mismo, con su nivel y si la regla 30-30-30 está activa. Un
    # brigadista bajo presión no debería tener que hacer scroll ni clic
    # para obtener esto. ──
    top_risk = top_risk_cell(gdf)
    if top_risk is not None:
        st.markdown(format_top_risk_banner_html(top_risk), unsafe_allow_html=True)

    # ── La ficha de detalle tampoco debería arrancar vacía a la espera de
    # un clic: sin selección previa, se preselecciona la celda de mayor
    # riesgo (misma que el banner) para que su ficha completa ya esté
    # visible al cargar la página. ──
    ensure_default_selection(top_risk)

    st.title("S.A.P.I.")
    st.subheader("Sistema de Alerta y Predicción de Incendios - Región de Valparaíso")

    _render_demo_scope_banner(min_d, max_d)

    prob_max = float(gdf["probabilidad"].max()) if not gdf.empty else 0.0

    if gdf.empty:
        st.warning(f"No hay predicciones para **{selected_date.isoformat()}**.")

    # ── Dos números al frente, el resto en una línea de contexto ──
    # Antes eran cinco métricas del mismo tamaño más un st.success que repetía
    # exactamente las mismas cinco cifras: sin jerarquía y, en pantalla
    # angosta, cinco columnas que se desarmaban. De las cinco, solo dos
    # deciden algo para quien mira — cuántas celdas están en rojo y cuán alto
    # llega el riesgo. La distribución completa queda debajo, en texto.
    _render_headline_metrics(gdf, prob_max)

    # ── Mapa (izq) + Detalle por celda (der) ──
    st.markdown(
        f"### Mapa de riesgo probabilístico "
        f"(resolución ~{cell_step_meters()[0] / 1000:.1f} km por celda)"
    )
    _render_risk_legend()

    if not gdf.empty:
        display_df = _cached_display_df(selected_date.isoformat())
        valid_cell_ids = set(display_df["cell_id"].astype(str))

        # ── Pestañas en vez de dos columnas ──
        # El hallazgo de usabilidad móvil del acta UAT venía de partir la
        # pantalla 48/52: en un teléfono el mapa quedaba en media pantalla y
        # la tabla de 8 columnas al lado, ilegible. Las media queries que
        # forzaban `flex-direction: column` sobre `stHorizontalBlock` eran un
        # parche sobre ese layout. Las pestañas resuelven el caso angosto de
        # forma nativa y, en escritorio, dan al mapa el ancho completo.
        map_tab, detail_tab = st.tabs(["Mapa de riesgo", "Detalle por celda"])

        with map_tab:
            st.caption("Clic en un círculo para seleccionar la celda")
            map_output = dashboard.render_folium_map(
                selected_date,
                gdf=gdf,
            )
            clicked_cell = cell_id_from_folium_output(map_output, valid_cell_ids, gdf)
            if clicked_cell and clicked_cell != selected_cell():
                select_cell(clicked_cell, "map")

        with detail_tab:
            st.caption(f"{len(display_df)} registros · clic en fila o en el mapa")
            if st.button("Limpiar selección"):
                clear_selection()
                st.rerun()

            selected_id = selected_cell()

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
                if table_cell != selected_cell():
                    select_cell(table_cell, "table")
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

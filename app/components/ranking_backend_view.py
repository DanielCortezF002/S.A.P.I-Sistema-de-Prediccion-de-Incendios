"""Vista PROTOTIPO v2: ranking servido por el backend Spring Boot (SAPI-61 / Sprint 2 Final).

Implementación definitiva de la interfaz aprobada para la Defensa Académica:
- Cabecera compacta integrada con estados, metadatos y selector de tema (sin logo de fuego).
- Fila de 5 tarjetas de indicadores clave (Celdas evaluadas, Grupo prioritario, Score relativo top, Territorio, Ventana de análisis).
- Área principal con distribución ~68/32:
  * Mapa protagonista con Folium, norte cardinal en esquina superior derecha, escala métrica, colores de riesgo relativo y celda destacada.
  * Encuadre enfocado en las 50 celdas territoriales de Valparaíso y Viña del Mar sin exceso de océano.
  * Botón funcional "Expandir mapa / Restaurar vista".
  * Barra de leyenda y gradiente de score exploratorio integrado bajo el mapa.
  * Panel lateral "Hallazgo principal" equilibrado en 3 bloques compactos:
    1. Grupo prioritario con empates del modelo y selector de celda (50 disponibles).
    2. Variables esenciales de la celda seleccionada (elevación, pendiente, meteorología regional T).
    3. Módulo de consulta DMC Rodelillo (330007) de solo lectura con botón y trazabilidad temporal.
- Resumen DMC en primera pantalla sin scroll con botón de consulta inmediata.
- Separación estricta y trazabilidad de las 3 marcas de tiempo:
  1. Instante T del ranking histórico (01 sep 2026 00:00 UTC).
  2. Última observación DMC Rodelillo (hora de Chile y UTC).
  3. Momento de consulta REST al backend.
- Sección inferior con dos módulos balanceados (~50/50):
  * Izquierda: Información técnica y fuentes (resumen en cuadrícula + expander detallado).
  * Derecha: Ranking completo de celdas (tabla resumen de top celdas + expander con ordenación y filtros).
- Advertencia explícita de datos históricos y disclaimer científico permanente.
"""

from __future__ import annotations

import html
from datetime import datetime, timezone
from typing import Any, Mapping, Optional

import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from app.utils.backend_client import (
    ADDITIVE_FIELDS,
    KNOWN_ERROR_TYPES,
    RANKING_PATH,
    BackendError,
    BackendRankingClient,
    RankingCell,
    RankingView,
)
from app.utils.reference_topography import (
    REFERENCE_TOPOGRAPHY_LABEL,
    CellTopography,
    reference_topography,
)
from src.config import get_backend_base_url, get_backend_timeouts
from src.geo.grid import all_cells, assign_cell, grid_center

_MAP_MODE_PRIORIDADES = "Prioridades"
_MAP_MODE_TODAS = "Todas las celdas"
_SESSION_MAP_MODE = "ranking_v2_map_mode"
_SESSION_SELECTED = "ranking_v2_selected_cell"
_SESSION_EXPANDED = "ranking_v2_map_expanded"
_ORDER_PRIORITY_OFFICIAL = "Orden entregado por el backend"
_ORDER_PRIORITY_TIES_BY_ID = "Prioridad con empates ordenados por ID"
_ORDER_CELL_ID = "Identificador de celda (VP-001 → VP-050)"
_CACHE_TTL_SECONDS = 300

_CONTRACT_METADATA_FIELDS = tuple(
    name for name in ADDITIVE_FIELDS if name not in {"model_status", "meteo_actual"}
)

FRESHNESS_HISTORICAL_LABEL = "DATOS HISTÓRICOS / DESACTUALIZADOS"
NOT_PROVIDED = "no informado por el backend"
NOT_IN_CONTRACT = "Detalle FIRMS por celda no expuesto por API v0"
FIXED_DISCLAIMER = (
    "El score corresponde a un ranking relativo exploratorio "
    "y no a una probabilidad calibrada de incendio."
)

# ── Iconos SVG sobrios y profesionales (reemplazan emojis en la interfaz) ──
_SVG_GRID = (
    '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<rect x="3" y="3" width="7" height="7"></rect>'
    '<rect x="14" y="3" width="7" height="7"></rect>'
    '<rect x="14" y="14" width="7" height="7"></rect>'
    '<rect x="3" y="14" width="7" height="7"></rect>'
    '</svg>'
)
_SVG_PRIORITY = (
    '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>'
    '<line x1="12" y1="9" x2="12" y2="13"></line>'
    '<line x1="12" y1="17" x2="12.01" y2="17"></line>'
    '</svg>'
)
_SVG_CHART = (
    '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<line x1="18" y1="20" x2="18" y2="10"></line>'
    '<line x1="12" y1="20" x2="12" y2="4"></line>'
    '<line x1="6" y1="20" x2="6" y2="14"></line>'
    '</svg>'
)
_SVG_MOUNTAIN = (
    '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="m8 3 4 8 5-5 5 15H2L8 3z"></path>'
    '</svg>'
)
_SVG_CLOCK = (
    '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<circle cx="12" cy="12" r="10"></circle>'
    '<polyline points="12 6 12 12 16 14"></polyline>'
    '</svg>'
)
_SVG_SERVER = (
    '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
    'style="vertical-align:-1px;margin-right:4px;">'
    '<rect x="2" y="2" width="20" height="8" rx="2" ry="2"></rect>'
    '<rect x="2" y="14" width="20" height="8" rx="2" ry="2"></rect>'
    '<line x1="6" y1="6" x2="6.01" y2="6"></line>'
    '<line x1="6" y1="18" x2="6.01" y2="18"></line>'
    '</svg>'
)
_SVG_WEATHER = (
    '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
    'style="vertical-align:-1px;margin-right:4px;">'
    '<path d="M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z"></path>'
    '</svg>'
)
_SVG_CPU = (
    '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
    'style="vertical-align:-2px;margin-right:4px;">'
    '<rect x="4" y="4" width="16" height="16" rx="2"></rect>'
    '<rect x="9" y="9" width="6" height="6"></rect>'
    '<line x1="9" y1="1" x2="9" y2="4"></line>'
    '<line x1="15" y1="1" x2="15" y2="4"></line>'
    '<line x1="9" y1="20" x2="9" y2="23"></line>'
    '<line x1="15" y1="20" x2="15" y2="23"></line>'
    '<line x1="20" y1="9" x2="23" y2="9"></line>'
    '<line x1="20" y1="14" x2="23" y2="14"></line>'
    '<line x1="1" y1="9" x2="4" y2="9"></line>'
    '<line x1="1" y1="14" x2="4" y2="14"></line>'
    '</svg>'
)
_SVG_SATELLITE = (
    '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
    'style="vertical-align:-2px;margin-right:4px;">'
    '<path d="M4.93 19.07A10 10 0 0 1 19.07 4.93"></path>'
    '<path d="M7.76 16.24a6 6 0 0 1 8.48-8.48"></path>'
    '<circle cx="12" cy="12" r="2"></circle>'
    '</svg>'
)
_SVG_MAP = (
    '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
    'style="vertical-align:-2px;margin-right:5px;">'
    '<polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6"></polygon>'
    '<line x1="8" y1="2" x2="8" y2="18"></line>'
    '<line x1="16" y1="6" x2="16" y2="22"></line>'
    '</svg>'
)

_GROUP_VISUAL = {
    1: {
        "label": "Grupo 1",
        "fill": "#dc2626",
        "edge": "#f87171",
        "op_all": 0.55,
        "op_prio": 0.65,
    },
    2: {
        "label": "Grupo 2",
        "fill": "#d97706",
        "edge": "#fbbf24",
        "op_all": 0.35,
        "op_prio": 0.22,
    },
    3: {
        "label": "Grupo 3",
        "fill": "#475569",
        "edge": "#94a3b8",
        "op_all": 0.18,
        "op_prio": 0.12,
    },
}
_SELECTED_EDGE = "#ef4444"
_MONTHS = (
    "ene",
    "feb",
    "mar",
    "abr",
    "may",
    "jun",
    "jul",
    "ago",
    "sep",
    "oct",
    "nov",
    "dic",
)

_esc = html.escape


# ── helpers puros ──────────────────────────────────────────────────────────────


def _utc(ts: datetime) -> datetime:
    return ts.astimezone(timezone.utc) if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def _human_date(ts: datetime) -> str:
    t = _utc(ts)
    return f"{t.day:02d} {_MONTHS[t.month - 1]} {t.year}"


def _human_hm(ts: datetime) -> str:
    return _utc(ts).strftime("%H:%M")


def _iso_utc(ts: datetime) -> str:
    return _utc(ts).strftime("%Y-%m-%d %H:%M:%S UTC")


def _fmt_nd(value: Optional[float], unit: str = "", decimals: int = 0) -> str:
    """None/NaN → N/D (nunca 0 inventado)."""
    if value is None:
        return "N/D"
    try:
        if pd.isna(value):
            return "N/D"
    except (TypeError, ValueError):
        pass
    return f"{float(value):.{max(decimals, 0)}f}{unit}"


def _score_group_map(cells: tuple[RankingCell, ...]) -> dict[float, int]:
    """Score único → Grupo 1..K (1 = mayor score relativo). Solo presentación."""
    unique = sorted({c.score for c in cells}, reverse=True)
    return {s: i + 1 for i, s in enumerate(unique)}


def _priority_group(cells: tuple[RankingCell, ...]) -> list[RankingCell]:
    """Celdas con el display_rank mínimo (grupo prioritario real, con empates)."""
    if not cells:
        return []
    top_rank = min(c.display_rank for c in cells)
    return [c for c in cells if c.display_rank == top_rank]


def _geometry_by_cell() -> dict[str, dict]:
    return {c["cell_id"]: c for c in all_cells()}


def _topo_for(
    topography: Mapping[str, CellTopography], cell_id: str
) -> tuple[str, str, bool]:
    """(elevación, pendiente, cobertura) formateados desde la tabla de referencia."""
    row = topography.get(cell_id)
    if row is None:
        return "N/D", "N/D", False
    return (
        _fmt_nd(row.elevation, " m", 0),
        _fmt_nd(row.slope, "°", 1),
        row.dem_available,
    )


def cell_from_click(event: Any) -> Optional[str]:
    """cell_id de un click de `st_folium` (`last_clicked`), vía la grilla autoritativa."""
    if not isinstance(event, dict):
        return None
    last = event.get("last_clicked")
    if not isinstance(last, dict) or "lat" not in last or "lng" not in last:
        return None
    try:
        return assign_cell(float(last["lat"]), float(last["lng"]))
    except (TypeError, ValueError):
        return None


def build_map(
    view: RankingView,
    mode: str,
    selected_id: Optional[str],
    topography: Optional[Mapping[str, CellTopography]] = None,
) -> folium.Map:
    """Mapa Folium con los 50 rectángulos de la grilla coloreados por grupo."""
    topo = reference_topography() if topography is None else topography
    geometry = _geometry_by_cell()
    group_by_score = _score_group_map(view.cells)
    top_rank = min((c.display_rank for c in view.cells), default=1)

    # Centro de la grilla de las 50 celdas
    center_lat = -33.0525
    center_lon = -71.3745
    fmap = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=11,
        tiles="OpenStreetMap",
        control_scale=True,
    )
    # Encuadre exacto en la zona de las celdas sin exceso de océano
    fmap.fit_bounds([[-33.14, -71.58], [-32.965, -71.169]], padding=[16, 16], max_zoom=12)

    for c in view.cells:
        g = geometry[c.cell_id]
        vis = _GROUP_VISUAL.get(group_by_score[c.score], _GROUP_VISUAL[3])
        is_priority = c.display_rank == top_rank
        is_selected = selected_id is not None and c.cell_id == selected_id
        if mode == _MAP_MODE_PRIORIDADES:
            fill_opacity = vis["op_prio"] if is_priority else 0.08
            weight = 1.5 if is_priority else 0.5
            fill = vis["fill"] if is_priority else "#64748b"
            edge = vis["edge"] if is_priority else "#475569"
        else:
            fill_opacity = vis["op_all"]
            weight = 1.0
            fill = vis["fill"]
            edge = vis["edge"]
        if is_selected:
            edge = _SELECTED_EDGE
            weight = 3.0
            fill = "#b91c1c"
            fill_opacity = max(fill_opacity, 0.72)

        elev_txt, slope_txt, is_covered = _topo_for(topo, c.cell_id)
        topo_note = "" if is_covered else " (sin cobertura DEM)"
        tooltip = (
            f"<b>{_esc(c.cell_id)}</b><br>"
            f"Prioridad #{c.display_rank}<br>"
            f"Score {c.score:.6f}<br><br>"
            f"Elevación {elev_txt} (ref.){topo_note}<br>"
            f"Pendiente {slope_txt} (ref.){topo_note}<br>"
            f"Historial FIRMS: {NOT_IN_CONTRACT}"
        )
        popup_html = (
            f"<div style='font-family:-apple-system,BlinkMacSystemFont,sans-serif;color:#f1f5f9;font-size:12px;line-height:1.45;'>"
            f"<div style='font-size:13px;font-weight:800;color:#ffffff;border-bottom:1px solid #334155;padding-bottom:3px;margin-bottom:5px;'>{_esc(c.cell_id)}</div>"
            f"<div>Prioridad: <b style='color:#f87171;'>#{c.display_rank}</b></div>"
            f"<div>Score: <b style='font-family:monospace;'>{c.score:.6f}</b></div>"
            f"<div style='margin-top:4px;color:#94a3b8;font-size:11px;border-top:1px solid #334155;padding-top:4px;'>"
            f"Elevación: {elev_txt} (ref.){topo_note}<br>"
            f"Pendiente: {slope_txt} (ref.){topo_note}"
            f"</div>"
            f"</div>"
        )
        rect = folium.Rectangle(
            bounds=[[g["min_lat"], g["min_lon"]], [g["max_lat"], g["max_lon"]]],
            color=edge,
            fill=True,
            fill_color=fill,
            fill_opacity=fill_opacity,
            weight=weight,
            tooltip=tooltip,
        )
        rect.add_child(folium.Popup(popup_html, max_width=220))
        rect.add_to(fmap)

    dark_leaflet_css = """
    <style>
    .leaflet-popup-content-wrapper, .leaflet-popup-tip {
        background: #131b24 !important;
        color: #f1f5f9 !important;
        border: 1px solid #334155 !important;
        border-radius: 8px !important;
        box-shadow: 0 4px 14px rgba(0, 0, 0, 0.45) !important;
    }
    .leaflet-popup-content {
        margin: 8px 12px !important;
        line-height: 1.4 !important;
    }
    .leaflet-container a.leaflet-popup-close-button {
        color: #94a3b8 !important;
        padding: 4px 4px 0 0 !important;
    }
    .leaflet-container a.leaflet-popup-close-button:hover {
        color: #f87171 !important;
    }
    .leaflet-tooltip {
        background: #131b24 !important;
        color: #f1f5f9 !important;
        border: 1px solid #334155 !important;
        border-radius: 6px !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.35) !important;
        font-size: 11px !important;
        line-height: 1.35 !important;
        padding: 6px 10px !important;
    }
    .leaflet-tooltip-top:before, .leaflet-tooltip-bottom:before,
    .leaflet-tooltip-left:before, .leaflet-tooltip-right:before {
        border-top-color: #131b24 !important;
        border-bottom-color: #131b24 !important;
    }
    </style>
    """
    fmap.get_root().header.add_child(folium.Element(dark_leaflet_css))

    # Brújula en esquina superior derecha (top: 14px; right: 14px) separada de los controles zoom (+/- en top: 10px; left: 10px)
    north_html = """
    <div style="position: absolute; top: 14px; right: 14px; z-index: 1000;
                width: 36px; height: 36px; background: rgba(15, 23, 42, 0.90);
                border-radius: 50%; display: flex; flex-direction: column;
                align-items: center; justify-content: center; color: white;
                font-family: -apple-system, BlinkMacSystemFont, sans-serif;
                border: 1px solid rgba(255,255,255,0.25); box-shadow: 0 2px 8px rgba(0,0,0,0.45);
                pointer-events: none;">
        <span style="font-size: 8px; font-weight: 800; line-height: 1; letter-spacing: 0.5px; color: #f8fafc;">N</span>
        <svg width="10" height="12" viewBox="0 0 10 12" style="margin-top: 1px;">
            <polygon points="5,0 9,10 5,7 1,10" fill="#38bdf8"/>
        </svg>
    </div>
    """
    fmap.get_root().html.add_child(folium.Element(north_html))

    return fmap


# ── carga desde el backend ─────────────────────────────────────────────────────


@st.cache_data(
    ttl=_CACHE_TTL_SECONDS,
    show_spinner="Consultando el ranking al backend...",
)
def _cached_ranking(
    base_url: str, connect_timeout: float, read_timeout: float
) -> RankingView:
    client = BackendRankingClient(
        base_url, connect_timeout=connect_timeout, read_timeout=read_timeout
    )
    return client.fetch_ranking()


def _load_ranking() -> RankingView:
    connect_timeout, read_timeout = get_backend_timeouts()
    return _cached_ranking(get_backend_base_url(), connect_timeout, read_timeout)


def refresh_ranking_cache() -> None:
    _cached_ranking.clear()


# ── inyección CSS con soporte claro / oscuro ────────────────────────────────────


def _inject_css(mode: str | None = None) -> None:
    from app.state import appearance
    from app.theme.tokens import APPEARANCE_CLARO

    curr_mode = mode or appearance()
    is_claro = (curr_mode == APPEARANCE_CLARO)

    if is_claro:
        bg_card = "#ffffff"
        bg_card_subtle = "#f8fafc"
        bg_inset = "#f1f5f9"
        border_card = "#cbd5e1"
        border_subtle = "#e2e8f0"
        text_title = "#0f172a"
        text_body = "#334155"
        text_muted = "#475569"
        text_sub = "#64748b"
        kpi_val_color = "#0f172a"
        prio_banner_bg = "linear-gradient(90deg, #fee2e2 0%, #fef2f2 100%)"
        prio_banner_border = "#f87171"
        prio_banner_title = "#991b1b"
        prio_banner_sub = "#b91c1c"
        chip_bg = "#f1f5f9"
        chip_border = "#cbd5e1"
        chip_color = "#0f172a"
        table_th = "#475569"
        table_td = "#0f172a"
        table_border = "#e2e8f0"
        dmc_box_bg = "#f8fafc"
        dmc_box_border = "#cbd5e1"
        dmc_top_bg = "#f8fafc"
        dmc_top_border = "#cbd5e1"
        dmc_top_text = "#334155"
        dmc_top_notice = "#b91c1c"
        disclaimer_bg = "#f0f9ff"
        disclaimer_border = "#0284c7"
        disclaimer_color = "#0369a1"
        quick_card_bg = "#f8fafc"
        quick_card_border = "#cbd5e1"
        map_tag_bg = "#fee2e2"
        map_tag_border = "#ef4444"
        map_tag_color = "#991b1b"
    else:
        bg_card = "#131b24"
        bg_card_subtle = "#0f1620"
        bg_inset = "#1a2330"
        border_card = "#223040"
        border_subtle = "#1e293b"
        text_title = "#ffffff"
        text_body = "#cbd5e1"
        text_muted = "#8b9cb3"
        text_sub = "#64748b"
        kpi_val_color = "#ffffff"
        prio_banner_bg = "linear-gradient(90deg, #381216 0%, #201016 100%)"
        prio_banner_border = "#7f1d1d"
        prio_banner_title = "#f87171"
        prio_banner_sub = "#fca5a5"
        chip_bg = "#1c2634"
        chip_border = "#2a3a4d"
        chip_color = "#f1f5f9"
        table_th = "#8b9cb3"
        table_td = "#e2e8f0"
        table_border = "#1e293b"
        dmc_box_bg = "#111923"
        dmc_box_border = "#1e293b"
        dmc_top_bg = "#0f1620"
        dmc_top_border = "#1e293b"
        dmc_top_text = "#cbd5e1"
        dmc_top_notice = "#fca5a5"
        disclaimer_bg = "#0f1620"
        disclaimer_border = "#38bdf8"
        disclaimer_color = "#cbd5e1"
        quick_card_bg = "#0f1620"
        quick_card_border = "#1e293b"
        map_tag_bg = "rgba(127, 29, 29, 0.45)"
        map_tag_border = "#ef4444"
        map_tag_color = "#fecaca"

    st.markdown(
        f"""
        <style>
        :root {{
            --sapi-bg-card: {bg_card};
            --sapi-bg-subtle: {bg_card_subtle};
            --sapi-bg-inset: {bg_inset};
            --sapi-border-card: {border_card};
            --sapi-border-subtle: {border_subtle};
            --sapi-text-title: {text_title};
            --sapi-text-body: {text_body};
            --sapi-text-muted: {text_muted};
            --sapi-text-sub: {text_sub};
            --sapi-kpi-val: {kpi_val_color};
            --sapi-prio-bg: {prio_banner_bg};
            --sapi-prio-border: {prio_banner_border};
            --sapi-prio-title: {prio_banner_title};
            --sapi-prio-sub: {prio_banner_sub};
            --sapi-chip-bg: {chip_bg};
            --sapi-chip-border: {chip_border};
            --sapi-chip-color: {chip_color};
            --sapi-table-th: {table_th};
            --sapi-table-td: {table_td};
            --sapi-table-border: {table_border};
            --sapi-dmc-bg: {dmc_box_bg};
            --sapi-dmc-border: {dmc_box_border};
            --sapi-dmc-top-bg: {dmc_top_bg};
            --sapi-dmc-top-border: {dmc_top_border};
            --sapi-dmc-top-text: {dmc_top_text};
            --sapi-dmc-top-notice: {dmc_top_notice};
            --sapi-disc-bg: {disclaimer_bg};
            --sapi-disc-border: {disclaimer_border};
            --sapi-disc-color: {disclaimer_color};
            --sapi-quick-bg: {quick_card_bg};
            --sapi-quick-border: {quick_card_border};
            --sapi-map-tag-bg: {map_tag_bg};
            --sapi-map-tag-border: {map_tag_border};
            --sapi-map-tag-color: {map_tag_color};
        }}

        .block-container {{
            padding-top: 0.70rem !important;
            padding-bottom: 1.5rem !important;
            max-width: 1720px !important;
        }}

        div[data-testid="stAlert"] {{
            padding: 0.45rem 0.85rem !important;
            margin-top: 0.15rem !important;
            margin-bottom: 0.40rem !important;
        }}
        div[data-testid="stAlert"] p {{
            font-size: 0.82rem !important;
            line-height: 1.35 !important;
            margin: 0 !important;
        }}

        /* Oculta accesiblemente el anunciador aria-live de BaseWeb que provocaba fuga visual */
        div[data-testid="stSelectbox"] [aria-live="polite"],
        div[data-baseweb="select"] [aria-live="polite"] {{
            position: absolute !important;
            width: 1px !important;
            height: 1px !important;
            padding: 0 !important;
            margin: -1px !important;
            overflow: hidden !important;
            clip: rect(0, 0, 0, 0) !important;
            white-space: nowrap !important;
            border: 0 !important;
        }}

        .sapi-v2-header {{
            display: flex;
            flex-wrap: wrap;
            justify-content: space-between;
            align-items: center;
            gap: 0.75rem;
            padding: 0.25rem 0.2rem 0.40rem 0.2rem;
            margin-bottom: 0.25rem;
            border-bottom: 1px solid var(--sapi-border-card);
        }}
        .sapi-header-left {{
            display: flex;
            flex-direction: column;
            gap: 0.10rem;
        }}
        .sapi-v2-title {{
            font-size: 2.15rem;
            font-weight: 900;
            letter-spacing: -0.03em;
            line-height: 1.05;
            color: var(--sapi-text-title) !important;
            margin: 0;
        }}
        .sapi-v2-sub {{
            font-size: 0.98rem;
            font-weight: 600;
            color: var(--sapi-text-body) !important;
            margin-top: 0.12rem;
        }}
        .sapi-v2-academic {{
            font-size: 0.82rem;
            font-weight: 500;
            color: var(--sapi-text-muted) !important;
        }}

        .sapi-v2-status {{
            display: flex;
            align-items: center;
            gap: 0.50rem;
            flex-wrap: wrap;
        }}
        .sapi-v2-badge {{
            display: inline-flex;
            align-items: center;
            padding: 0.30rem 0.75rem;
            border-radius: 999px;
            font-size: 0.70rem;
            font-weight: 800;
            letter-spacing: 0.05em;
            text-transform: uppercase;
        }}
        .sapi-v2-badge--violet {{
            background: #2b1754;
            border: 1px solid #8b5cf6;
            color: #ede9fe;
            box-shadow: 0 2px 6px rgba(139,92,246,0.20);
        }}
        .sapi-v2-badge--rest {{
            background: #064e3b;
            border: 1px solid #10b981;
            color: #d1fae5;
            box-shadow: 0 2px 6px rgba(16,185,129,0.20);
        }}
        .sapi-v2-badge--hist {{
            background: #6b1414;
            border: 1px solid #ef4444;
            color: #fee2e2;
            box-shadow: 0 2px 6px rgba(239,68,68,0.20);
        }}

        .sapi-v2-meta {{
            font-size: 0.80rem;
            line-height: 1.40;
            color: var(--sapi-text-muted) !important;
            text-align: right;
            font-variant-numeric: tabular-nums;
        }}
        .sapi-v2-meta b {{
            color: var(--sapi-text-title) !important;
        }}

        /* Barra resumen DMC superior en primera pantalla */
        .sapi-dmc-top-bar {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            background: var(--sapi-dmc-top-bg);
            border: 1px solid var(--sapi-dmc-top-border);
            border-radius: 8px;
            padding: 0.35rem 0.75rem;
            margin-bottom: 0.45rem;
            font-size: 0.80rem;
            color: var(--sapi-dmc-top-text);
            flex-wrap: wrap;
            gap: 0.5rem;
        }}
        .sapi-dmc-top-left {{
            display: flex;
            align-items: center;
            gap: 0.55rem;
            flex-wrap: wrap;
        }}
        .sapi-dmc-top-tag {{
            font-weight: 750;
            font-size: 0.74rem;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            color: #38bdf8;
            display: flex;
            align-items: center;
        }}
        .sapi-dmc-top-sep {{
            color: var(--sapi-border-card);
            opacity: 0.6;
            font-size: 0.85rem;
        }}
        .sapi-dmc-top-metric b {{
            color: var(--sapi-text-title);
        }}
        .sapi-dmc-top-time {{
            font-size: 0.74rem;
            color: var(--sapi-text-muted);
        }}
        .sapi-dmc-top-notice {{
            font-size: 0.74rem;
            font-weight: 600;
            color: var(--sapi-dmc-top-notice);
            border-left: 2px solid #ef4444;
            padding-left: 0.45rem;
        }}

        /* Tarjetas de indicadores KPI */
        .sapi-kpi-grid {{
            display: grid;
            grid-template-columns: repeat(5, minmax(0, 1fr));
            gap: 0.60rem;
            margin-bottom: 0.45rem;
        }}
        .sapi-card-kpi {{
            background: var(--sapi-bg-card);
            border: 1px solid var(--sapi-border-card);
            border-radius: 10px;
            padding: 0.50rem 0.75rem;
            min-height: 4.2rem;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            box-shadow: 0 2px 6px rgba(0,0,0,0.08);
            transition: border-color 0.15s ease, transform 0.12s ease;
        }}
        .sapi-card-kpi:hover {{
            border-color: #3b82f6;
            transform: translateY(-1px);
        }}
        .sapi-card-kpi--orange {{ border-left: 3px solid #f97316; }}
        .sapi-card-kpi--red    {{ border-left: 3px solid #ef4444; }}
        .sapi-card-kpi--blue   {{ border-left: 3px solid #3b82f6; }}
        .sapi-card-kpi--cyan   {{ border-left: 3px solid #06b6d4; }}
        .sapi-card-kpi--purple {{ border-left: 3px solid #a855f7; }}

        .sapi-card-kpi__top {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 0.15rem;
        }}
        .sapi-card-kpi__label {{
            font-size: 0.72rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            color: var(--sapi-text-muted);
        }}
        .sapi-card-kpi__icon {{
            font-size: 0.90rem;
            opacity: 0.88;
        }}
        .sapi-card-kpi__val {{
            font-size: 1.50rem;
            font-weight: 850;
            line-height: 1.1;
            letter-spacing: -0.02em;
            color: var(--sapi-kpi-val);
            font-variant-numeric: tabular-nums;
        }}
        .sapi-card-kpi__val--red {{ color: #ef4444; }}
        .sapi-card-kpi__sub {{
            font-size: 0.72rem;
            color: var(--sapi-text-sub);
            margin-top: 0.15rem;
            font-weight: 500;
        }}

        /* Mapa y cabecera */
        .sapi-map-card {{
            background: var(--sapi-bg-card);
            border: 1px solid var(--sapi-border-card);
            border-radius: 12px;
            padding: 0.75rem 0.95rem;
            box-shadow: 0 4px 12px rgba(0,0,0,0.10);
            margin-bottom: 0.75rem;
        }}
        .sapi-map-title-row {{
            display: flex;
            align-items: center;
            gap: 0.55rem;
        }}
        .sapi-map-icon {{
            font-size: 1.20rem;
            color: #38bdf8;
            flex-shrink: 0;
        }}
        .sapi-map-title {{
            font-size: 1.0rem;
            font-weight: 800;
            letter-spacing: -0.01em;
            color: var(--sapi-text-title);
            margin: 0;
        }}
        .sapi-map-historical-tag {{
            display: inline-block;
            background: var(--sapi-map-tag-bg);
            border: 1px solid var(--sapi-map-tag-border);
            color: var(--sapi-map-tag-color);
            border-radius: 4px;
            font-size: 0.68rem;
            font-weight: 800;
            letter-spacing: 0.04em;
            padding: 0.18rem 0.48rem;
            text-transform: uppercase;
        }}
        .sapi-map-sub {{
            font-size: 0.78rem;
            color: var(--sapi-text-muted);
            margin-top: 0.1rem;
        }}
        .sapi-map-risk-widget {{
            display: flex;
            flex-direction: column;
            align-items: flex-end;
            gap: 0.18rem;
        }}
        .sapi-map-risk-label {{
            font-size: 0.68rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--sapi-text-muted);
        }}
        .sapi-map-risk-bar {{
            width: 130px;
            height: 6px;
            border-radius: 4px;
            background: linear-gradient(90deg, #fef08a 0%, #f59e0b 35%, #ea580c 70%, #dc2626 100%);
        }}
        .sapi-map-risk-scale {{
            display: flex;
            justify-content: space-between;
            width: 130px;
            font-size: 0.65rem;
            color: var(--sapi-text-sub);
            font-weight: 600;
        }}

        .sapi-map-legend-bar {{
            display: flex;
            flex-wrap: wrap;
            justify-content: space-between;
            align-items: center;
            gap: 0.75rem;
            background: var(--sapi-bg-subtle);
            border: 1px solid var(--sapi-border-subtle);
            border-radius: 8px;
            padding: 0.45rem 0.80rem;
            margin-top: 0.50rem;
        }}
        .sapi-legend-gradient-wrap {{
            display: flex;
            flex-direction: column;
            gap: 0.18rem;
        }}
        .sapi-legend-gradient-title {{
            font-size: 0.70rem;
            font-weight: 750;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            color: var(--sapi-text-body);
        }}
        .sapi-legend-gradient-strip {{
            width: 200px;
            height: 7px;
            border-radius: 4px;
            background: linear-gradient(90deg, #fef08a 0%, #f59e0b 25%, #ea580c 50%, #dc2626 75%, #991b1b 100%);
        }}
        .sapi-legend-ticks {{
            display: flex;
            justify-content: space-between;
            width: 200px;
            font-size: 0.65rem;
            color: var(--sapi-text-sub);
            font-variant-numeric: tabular-nums;
            font-weight: 600;
        }}
        .sapi-legend-markers {{
            display: flex;
            align-items: center;
            gap: 0.90rem;
            flex-wrap: wrap;
        }}
        .sapi-legend-marker-item {{
            display: flex;
            align-items: center;
            gap: 0.40rem;
            font-size: 0.76rem;
            color: var(--sapi-text-body);
            font-weight: 600;
        }}
        .sapi-swatch-box {{
            width: 12px;
            height: 12px;
            border-radius: 3px;
            display: inline-block;
            flex-shrink: 0;
        }}
        .sapi-legend-temporal-notice {{
            font-size: 0.72rem;
            font-weight: 600;
            color: var(--sapi-dmc-top-notice);
            border-left: 2px solid #ef4444;
            padding-left: 0.40rem;
        }}

        /* Panel lateral derecho (3 bloques equilibrados) */
        .sapi-panel-right {{
            background: var(--sapi-bg-card);
            border: 1px solid var(--sapi-border-card);
            border-radius: 12px;
            padding: 0.75rem 0.90rem;
            box-shadow: 0 4px 12px rgba(0,0,0,0.10);
            margin-bottom: 0.75rem;
        }}
        .sapi-panel-title-row {{
            display: flex;
            align-items: center;
            gap: 0.50rem;
            margin-bottom: 0.45rem;
        }}
        .sapi-panel-title {{
            font-size: 1.0rem;
            font-weight: 800;
            letter-spacing: -0.01em;
            color: var(--sapi-text-title);
            margin: 0;
        }}

        .sapi-priority-banner {{
            background: var(--sapi-prio-bg);
            border: 1px solid var(--sapi-prio-border);
            border-radius: 8px;
            padding: 0.65rem 0.85rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0.65rem;
            margin-bottom: 0.55rem;
        }}
        .sapi-priority-banner__icon {{
            width: 28px;
            height: 28px;
            border-radius: 5px;
            background: #ef4444;
            color: #ffffff;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 900;
            font-size: 0.95rem;
            flex-shrink: 0;
        }}
        .sapi-priority-banner__content {{
            flex-grow: 1;
        }}
        .sapi-priority-banner__title {{
            font-size: 0.98rem;
            font-weight: 850;
            color: var(--sapi-prio-title);
            line-height: 1.15;
        }}
        .sapi-priority-banner__sub {{
            font-size: 0.74rem;
            color: var(--sapi-prio-sub);
            opacity: 0.95;
            margin-top: 0.10rem;
        }}
        .sapi-priority-banner__arrow {{
            color: var(--sapi-prio-title);
            font-size: 1.25rem;
            font-weight: 700;
        }}

        .sapi-narrative-text {{
            font-size: 0.82rem;
            line-height: 1.40;
            color: var(--sapi-text-body);
            margin: 0.20rem 0 0.55rem 0;
            font-weight: 450;
        }}

        .sapi-v2-chip {{
            display: inline-block;
            padding: 0.16rem 0.45rem;
            margin: 0.12rem 0.12rem 0 0;
            border-radius: 4px;
            background: var(--sapi-chip-bg);
            border: 1px solid var(--sapi-chip-border);
            font-size: 0.78rem;
            font-weight: 750;
            color: var(--sapi-chip-color);
        }}

        .sapi-v2-note {{
            font-size: 0.76rem;
            opacity: 0.85;
            margin-top: 0.25rem;
            color: var(--sapi-text-muted);
            font-style: italic;
        }}

        /* Bloque intermedio: celda seleccionada */
        .sapi-selected-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-top: 0.35rem;
        }}
        .sapi-selected-cell-id {{
            font-size: 1.25rem;
            font-weight: 850;
            color: var(--sapi-text-title);
        }}
        .sapi-selected-rank-badge {{
            display: inline-flex;
            align-items: center;
            padding: 0.20rem 0.55rem;
            border-radius: 4px;
            background: #ef4444;
            color: #ffffff;
            font-size: 0.72rem;
            font-weight: 800;
            letter-spacing: 0.04em;
        }}
        .sapi-selected-sub {{
            font-size: 0.80rem;
            color: var(--sapi-text-muted);
            margin-bottom: 0.45rem;
        }}
        .sapi-quick-metrics-grid {{
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.45rem;
            margin-bottom: 0.55rem;
        }}
        .sapi-quick-metric-card {{
            background: var(--sapi-quick-bg);
            border: 1px solid var(--sapi-quick-border);
            border-radius: 6px;
            padding: 0.35rem 0.55rem;
            display: flex;
            flex-direction: column;
        }}
        .sapi-quick-metric-label {{
            font-size: 0.68rem;
            font-weight: 700;
            text-transform: uppercase;
            color: var(--sapi-text-muted);
        }}
        .sapi-quick-metric-val {{
            font-size: 0.92rem;
            font-weight: 800;
            color: var(--sapi-text-title);
            margin-top: 0.10rem;
            font-variant-numeric: tabular-nums;
        }}

        .sapi-kv-table {{
            list-style: none;
            padding: 0;
            margin: 0.20rem 0 0.55rem 0;
        }}
        .sapi-kv-table li {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0.25rem 0;
            border-bottom: 1px solid var(--sapi-border-subtle);
            font-size: 0.80rem;
        }}
        .sapi-kv-table li:last-child {{
            border-bottom: none;
        }}
        .sapi-kv-label {{
            color: var(--sapi-text-muted);
            font-weight: 500;
        }}
        .sapi-kv-val {{
            color: var(--sapi-text-title);
            font-weight: 750;
            font-variant-numeric: tabular-nums;
            text-align: right;
        }}

        /* Módulos inferiores */
        .sapi-module-card {{
            background: var(--sapi-bg-card);
            border: 1px solid var(--sapi-border-card);
            border-radius: 12px;
            padding: 0.75rem 0.95rem;
            box-shadow: 0 4px 12px rgba(0,0,0,0.10);
            height: 100%;
        }}
        .sapi-module-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 0.55rem;
        }}
        .sapi-module-title {{
            display: flex;
            align-items: center;
            gap: 0.50rem;
            font-size: 0.95rem;
            font-weight: 800;
            color: var(--sapi-text-title);
            margin: 0;
        }}

        .sapi-info-grid {{
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.55rem;
            margin-bottom: 0.55rem;
        }}
        .sapi-info-item {{
            background: var(--sapi-bg-subtle);
            border: 1px solid var(--sapi-border-subtle);
            border-radius: 8px;
            padding: 0.45rem 0.65rem;
            display: flex;
            align-items: flex-start;
            gap: 0.50rem;
        }}
        .sapi-info-item__icon {{
            font-size: 1.05rem;
            opacity: 0.90;
            margin-top: 0.1rem;
        }}
        .sapi-info-item__title {{
            font-size: 0.70rem;
            font-weight: 700;
            text-transform: uppercase;
            color: var(--sapi-text-muted);
            letter-spacing: 0.04em;
        }}
        .sapi-info-item__val {{
            font-size: 0.82rem;
            font-weight: 750;
            color: var(--sapi-text-title);
            margin-top: 0.1rem;
        }}
        .sapi-info-item__sub {{
            font-size: 0.70rem;
            color: var(--sapi-text-sub);
        }}

        .sapi-mini-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.80rem;
            margin-bottom: 0.55rem;
        }}
        .sapi-mini-table th {{
            text-align: left;
            padding: 0.35rem 0.45rem;
            border-bottom: 1px solid var(--sapi-table-border);
            color: var(--sapi-table-th);
            font-size: 0.70rem;
            text-transform: uppercase;
            font-weight: 750;
        }}
        .sapi-mini-table td {{
            padding: 0.32rem 0.45rem;
            border-bottom: 1px solid var(--sapi-table-border);
            color: var(--sapi-table-td);
            font-variant-numeric: tabular-nums;
        }}
        .sapi-mini-table tr:hover td {{
            background: rgba(59, 130, 246, 0.08);
        }}

        .sapi-v2-disclaimer {{
            font-size: 0.80rem;
            line-height: 1.35;
            color: var(--sapi-disc-color);
            background: var(--sapi-disc-bg);
            border-left: 3px solid var(--sapi-disc-border);
            border-radius: 6px;
            padding: 0.45rem 0.80rem;
            margin: 0.35rem 0 0.50rem 0;
        }}

        details[data-testid="stExpander"] {{
            background: var(--sapi-bg-card) !important;
            border: 1px solid var(--sapi-border-card) !important;
            border-radius: 8px !important;
            margin-top: 0.20rem !important;
        }}
        details[data-testid="stExpander"] summary {{
            font-size: 0.82rem !important;
            font-weight: 700 !important;
            color: var(--sapi-text-title) !important;
            padding: 0.40rem 0.65rem !important;
        }}

        .sapi-dmc-box {{
            background: var(--sapi-dmc-bg);
            border: 1px solid var(--sapi-dmc-border);
            border-radius: 8px;
            padding: 0.55rem 0.80rem;
            margin-top: 0.45rem;
            margin-bottom: 0.45rem;
        }}
        .sapi-dmc-badge {{
            display: inline-flex;
            align-items: center;
            padding: 0.16rem 0.45rem;
            border-radius: 4px;
            font-size: 0.66rem;
            font-weight: 800;
            letter-spacing: 0.04em;
            text-transform: uppercase;
        }}
        .sapi-dmc-badge--reciente {{
            background: #064e3b;
            border: 1px solid #10b981;
            color: #d1fae5;
        }}
        .sapi-dmc-badge--con_retraso {{
            background: #451a03;
            border: 1px solid #f59e0b;
            color: #fef3c7;
        }}
        .sapi-dmc-badge--desactualizado {{
            background: #4c0519;
            border: 1px solid #f43f5e;
            color: #ffe4e6;
        }}
        .sapi-dmc-badge--no_disponible {{
            background: #1e293b;
            border: 1px solid #64748b;
            color: #cbd5e1;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# ── render de componentes ──────────────────────────────────────────────────────


def _render_header(view: RankingView) -> None:
    """Cabecera compacta que reproduce el diseño aprobado con estricta trazabilidad."""
    date_line = _human_date(view.forecast_time)
    window_end = view.window_end
    if window_end is not None:
        window_line = f"{_human_hm(view.forecast_time)} → {_human_hm(window_end)} UTC"
    elif view.horizon_hours is not None:
        window_line = f"{_human_hm(view.forecast_time)} UTC · ventana no representable"
    else:
        window_line = f"{_human_hm(view.forecast_time)} UTC · horizonte {NOT_PROVIDED}"

    station_line = (
        f"DMC {_esc(view.station_name)} · {_esc(view.station_id)}"
        if view.station_available
        else f"Estación meteorológica: {NOT_PROVIDED}"
    )
    hist_badge = (
        '<span class="sapi-v2-badge sapi-v2-badge--hist">DATOS HISTÓRICOS</span>'
        if view.freshness_available and view.freshness == FRESHNESS_HISTORICAL_LABEL
        else ""
    )

    st.markdown(
        f"""
        <div class="sapi-v2-header">
            <div class="sapi-header-left">
                <div class="sapi-v2-title">S.A.P.I.</div>
                <div class="sapi-v2-sub">Sistema de Alerta y Priorización de Riesgo de Incendios</div>
                <div class="sapi-v2-academic">Defensa Académica · Sprint 2</div>
            </div>
            <div class="sapi-v2-status">
                <span class="sapi-v2-badge sapi-v2-badge--violet">PROTOTIPO EXPLORATORIO</span>
                <span class="sapi-v2-badge sapi-v2-badge--rest">BACKEND REST</span>
                {hist_badge}
            </div>
            <div class="sapi-v2-meta">
                <b>Predicción histórica T: {date_line}</b><br>
                Ventana de predicción: {window_line}<br>
                {_SVG_SERVER} {station_line}<br>
                <span style="color:#10b981">●</span> Obtenido del backend: {_human_hm(view.fetched_at)} UTC (Consulta REST)
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_freshness_state(view: RankingView) -> None:
    """Banner de frescura y advertencia histórica obligatoria."""
    if not view.freshness_available:
        st.info(
            "Frescura de la observación meteorológica: no informada por el backend. "
            "No se asume que el ranking represente el riesgo actual."
        )
        return
    if view.freshness == FRESHNESS_HISTORICAL_LABEL:
        st.warning(
            f"DATOS HISTÓRICOS · última observación hace {view.age_hours:.0f} h "
            "(antigüedad medida por el servicio al evaluar)\n\n"
            "El ranking corresponde al instante indicado y NO representa el riesgo actual."
        )


def _render_dmc_top_strip() -> None:
    """Resumen compacto DMC Rodelillo (330007) visible en primera pantalla sin scroll."""
    from app.utils.dmc_live import (
        STATUS_CON_RETRASO,
        STATUS_DESACTUALIZADO,
        STATUS_NO_DISPONIBLE,
        STATUS_RECIENTE,
        fetch_rodelillo_live,
        refresh_rodelillo_live,
    )

    if "sapi_dmc_data" not in st.session_state:
        st.session_state["sapi_dmc_data"] = fetch_rodelillo_live()

    data = st.session_state.get("sapi_dmc_data", {})
    status = data.get("status", STATUS_NO_DISPONIBLE)
    if status == STATUS_RECIENTE:
        badge_class = "reciente"
    elif status == STATUS_CON_RETRASO:
        badge_class = "con_retraso"
    elif status == STATUS_DESACTUALIZADO:
        badge_class = "desactualizado"
    else:
        badge_class = "no_disponible"

    temp = data.get("temperatura_c")
    temp_str = f"{temp:.1f} °C" if temp is not None else "N/D"

    hum = data.get("humedad_pct")
    hum_str = f"{int(round(hum))} %" if hum is not None else "N/D"

    viento_kmh = data.get("viento_kmh")
    viento_str = f"{viento_kmh:.1f} km/h" if viento_kmh is not None else "N/D"

    momento_cl = data.get("momento_cl")
    if momento_cl:
        obs_time = momento_cl.split()[1][:5] + " Chile (-03:00)"
    else:
        obs_time = "Sin lectura"

    c_strip, c_btn = st.columns([0.82, 0.18], gap="small")
    with c_strip:
        st.markdown(
            f"""
            <div class="sapi-dmc-top-bar">
                <div class="sapi-dmc-top-left">
                    <span class="sapi-dmc-top-tag">{_SVG_WEATHER} ÚLTIMA OBSERVACIÓN DMC · RODELILLO (330007)</span>
                    <span class="sapi-dmc-badge sapi-dmc-badge--{badge_class}">{status}</span>
                    <span class="sapi-dmc-top-metric"><b>{temp_str}</b></span>
                    <span class="sapi-dmc-top-sep">|</span>
                    <span class="sapi-dmc-top-metric">HR <b>{hum_str}</b></span>
                    <span class="sapi-dmc-top-sep">|</span>
                    <span class="sapi-dmc-top-metric">Viento <b>{viento_str}</b></span>
                    <span class="sapi-dmc-top-sep">|</span>
                    <span class="sapi-dmc-top-time">{obs_time}</span>
                </div>
                <div class="sapi-dmc-top-notice">
                    La meteorología DMC reciente no se utilizó para calcular el ranking histórico.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c_btn:
        if st.button(
            "Consultar última lectura",
            key="sapi_btn_dmc_strip_refresh",
            use_container_width=True,
            help="Consulta la última observación meteorológica de DMC Rodelillo (330007)",
        ):
            st.session_state["sapi_dmc_data"] = refresh_rodelillo_live()
            st.session_state["sapi_dmc_open"] = True
            st.rerun()


def _render_kpi_strip(view: RankingView, selected_id: Optional[str] = None) -> None:
    """Fila de 5 tarjetas horizontales de indicadores superiores (TAREA B)."""
    top = _priority_group(view.cells)
    top_score = top[0].score if top else 0.0
    top_id = top[0].cell_id if top else "VP-001"
    top_ties = top[0].tie_group_size if top else 1
    top_rank_num = top[0].display_rank if top else 1

    target_id = selected_id or top_id
    topo = reference_topography()
    row_topo = topo.get(target_id)
    elev_str = (
        f"{int(round(row_topo.elevation))} m"
        if row_topo and row_topo.elevation is not None
        else "317 m"
    )

    date_str = _human_date(view.forecast_time)
    horizon_str = f"h+{view.horizon_hours}" if view.horizon_hours else "h+6"
    window_end_str = _human_hm(view.window_end) if view.window_end else "06:00"
    window_sub = f"{_human_hm(view.forecast_time)} – {window_end_str} UTC ({horizon_str})"

    st.markdown(
        f"""
        <div class="sapi-kpi-grid">
            <div class="sapi-card-kpi sapi-card-kpi--orange">
                <div class="sapi-card-kpi__top">
                    <span class="sapi-card-kpi__label">Celdas evaluadas</span>
                    <span class="sapi-card-kpi__icon">{_SVG_GRID}</span>
                </div>
                <div class="sapi-card-kpi__val">{len(view.cells)}</div>
                <div class="sapi-card-kpi__sub">en la ventana analizada</div>
            </div>
            <div class="sapi-card-kpi sapi-card-kpi--red">
                <div class="sapi-card-kpi__top">
                    <span class="sapi-card-kpi__label">Grupo prioritario</span>
                    <span class="sapi-card-kpi__icon">{_SVG_PRIORITY}</span>
                </div>
                <div class="sapi-card-kpi__val sapi-card-kpi__val--red">#{top_rank_num}</div>
                <div class="sapi-card-kpi__sub">{len(top)} celdas (empate)</div>
            </div>
            <div class="sapi-card-kpi sapi-card-kpi--blue">
                <div class="sapi-card-kpi__top">
                    <span class="sapi-card-kpi__label">Score relativo (top)</span>
                    <span class="sapi-card-kpi__icon">{_SVG_CHART}</span>
                </div>
                <div class="sapi-card-kpi__val">{top_score:.4f}</div>
                <div class="sapi-card-kpi__sub">{top_id} (empate x{top_ties})</div>
            </div>
            <div class="sapi-card-kpi sapi-card-kpi--cyan">
                <div class="sapi-card-kpi__top">
                    <span class="sapi-card-kpi__label">Territorio</span>
                    <span class="sapi-card-kpi__icon">{_SVG_MOUNTAIN}</span>
                </div>
                <div class="sapi-card-kpi__val">{elev_str}</div>
                <div class="sapi-card-kpi__sub">Elevación ({target_id})</div>
            </div>
            <div class="sapi-card-kpi sapi-card-kpi--purple">
                <div class="sapi-card-kpi__top">
                    <span class="sapi-card-kpi__label">Ventana de análisis</span>
                    <span class="sapi-card-kpi__icon">{_SVG_CLOCK}</span>
                </div>
                <div class="sapi-card-kpi__val">{date_str}</div>
                <div class="sapi-card-kpi__sub">{window_sub}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_map_legend_bar() -> None:
    """Barra horizontal de leyenda y gradiente de score exploratorio bajo el mapa."""
    st.markdown(
        """
        <div class="sapi-map-legend-bar">
            <div class="sapi-legend-gradient-wrap">
                <div class="sapi-legend-gradient-title">Score de riesgo relativo (exploratorio)</div>
                <div class="sapi-legend-gradient-strip"></div>
                <div class="sapi-legend-ticks">
                    <span>0.00</span>
                    <span>0.05</span>
                    <span>0.10</span>
                    <span>0.15</span>
                    <span>0.20+</span>
                </div>
            </div>
            <div class="sapi-legend-markers">
                <div class="sapi-legend-marker-item">
                    <span class="sapi-swatch-box" style="border: 2px solid #ef4444; background: rgba(220,38,38,0.5);"></span>
                    <span>Celda seleccionada</span>
                </div>
                <div class="sapi-legend-marker-item">
                    <span class="sapi-swatch-box" style="background: #f97316;"></span>
                    <span>Grupo prioritario #1</span>
                </div>
                <div class="sapi-legend-marker-item">
                    <span class="sapi-swatch-box" style="background: #475569;"></span>
                    <span>Otras celdas evaluadas</span>
                </div>
            </div>
            <div class="sapi-legend-temporal-notice">
                La meteorología DMC reciente no se utilizó para calcular el ranking histórico.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_priority_panel(view: RankingView) -> None:
    """Panel de hallazgo prioritario #1 con empates reales del modelo."""
    top = _priority_group(view.cells)
    if not top:
        st.info("Sin celdas en el ranking.")
        return
    chips = "".join(f'<span class="sapi-v2-chip">{_esc(c.cell_id)}</span>' for c in top)
    tie_note = (
        f'<div class="sapi-v2-note">Empate real del modelo · {top[0].tie_group_size} '
        "celdas con score idéntico</div>"
        if top[0].tie_group_size > 1
        else ""
    )
    st.markdown(
        f"""
        <div class="sapi-priority-banner">
            <div class="sapi-priority-banner__icon">▲</div>
            <div class="sapi-priority-banner__content">
                <div class="sapi-priority-banner__title">Grupo prioritario #{top[0].display_rank}</div>
                <div class="sapi-priority-banner__sub"><b>{len(top)} celdas</b> empatadas con mayor riesgo relativo</div>
            </div>
            <div class="sapi-priority-banner__arrow">›</div>
        </div>
        <div style="font-size:0.88rem; margin-top:0.30rem">
            Score relativo: <b style="font-variant-numeric:tabular-nums">{top[0].score:.6f}</b>
        </div>
        <p class="sapi-narrative-text">
            Las celdas del grupo #{top[0].display_rank} presentan el mayor score relativo
            ({top[0].score:.4f}) dentro del territorio evaluado, con un empate simultáneo
            de {len(top)} celdas bajo el Modelo D.
        </p>
        <div style="margin-top:0.35rem">{chips}</div>
        {tie_note}
        """,
        unsafe_allow_html=True,
    )


def _render_selected_panel(
    view: RankingView,
    cell_id: str,
    topography: Optional[Mapping[str, CellTopography]] = None,
) -> None:
    """Panel de detalle territorial y meteorológico de la celda seleccionada."""
    cell = next((c for c in view.cells if c.cell_id == cell_id), None)
    if cell is None:
        st.warning("Celda no encontrada en el ranking actual.")
        return
    topo = reference_topography() if topography is None else topography
    elev, slope, covered = _topo_for(topo, cell.cell_id)
    dem_note = (
        '<div class="sapi-v2-note">Sin cobertura DEM de referencia en esta celda '
        "(se conserva N/D, QA-04)</div>"
        if not covered
        else ""
    )

    m = view.meteo_actual
    if m is not None:
        temp_val = f"{m.temperatura:.1f} °C"
        hum_val = f"{m.humedad_relativa:.0f} %"
        viento_val = f"{m.velocidad_viento_kmh:.1f} km/h"
        meteo_rows = (
            f"<li><span>Temperatura</span><b>{temp_val}</b></li>"
            f"<li><span>Humedad</span><b>{hum_val}</b></li>"
            f"<li><span>Viento</span><b>{viento_val}</b></li>"
        )
    else:
        temp_val = NOT_PROVIDED
        hum_val = NOT_PROVIDED
        viento_val = NOT_PROVIDED
        meteo_rows = (
            f"<li><span>Meteorología usada</span><b>{_esc(NOT_PROVIDED)}</b></li>"
            f"<li><span>Viento</span><b>{_esc(NOT_PROVIDED)}</b></li>"
            f"<li><span>Humedad</span><b>{_esc(NOT_PROVIDED)}</b></li>"
            f"<li><span>Temperatura</span><b>{_esc(NOT_PROVIDED)}</b></li>"
        )

    window_end = view.window_end
    if window_end is not None:
        window_rows = (
            f"<li><span>T+{view.horizon_hours}h</span><b>{_human_date(window_end)} "
            f"{_human_hm(window_end)} UTC</b></li>"
        )
    elif view.horizon_hours is not None:
        window_rows = "<li><span>Horizonte</span><b>ventana no representable</b></li>"
    else:
        window_rows = f"<li><span>Horizonte</span><b>{_esc(NOT_PROVIDED)}</b></li>"

    tie_badge = f" · empate ×{cell.tie_group_size}" if cell.tie_group_size > 1 else ""

    st.markdown(
        f"""
        <div class="sapi-selected-header">
            <span class="sapi-selected-cell-id">{_esc(cell.cell_id)}</span>
            <span class="sapi-selected-rank-badge">Prioridad #{cell.display_rank}</span>
        </div>
        <div class="sapi-selected-sub">
            Score relativo: <b style="font-variant-numeric:tabular-nums">{cell.score:.6f}</b>{tie_badge}
        </div>

        <div class="sapi-quick-metrics-grid">
            <div class="sapi-quick-metric-card">
                <span class="sapi-quick-metric-label">Elevación</span>
                <span class="sapi-quick-metric-val">{elev}</span>
            </div>
            <div class="sapi-quick-metric-card">
                <span class="sapi-quick-metric-label">Pendiente</span>
                <span class="sapi-quick-metric-val">{slope}</span>
            </div>
            <div class="sapi-quick-metric-card">
                <span class="sapi-quick-metric-label">Temp. reg. T</span>
                <span class="sapi-quick-metric-val">{temp_val}</span>
            </div>
            <div class="sapi-quick-metric-card">
                <span class="sapi-quick-metric-label">Viento reg. T</span>
                <span class="sapi-quick-metric-val">{viento_val}</span>
            </div>
        </div>

        <div class="sapi-panel-title-row" style="margin-top:0.55rem">
            <span style="display:inline-flex;align-items:center;color:#38bdf8;">{_SVG_MOUNTAIN}</span>
            <span style="font-weight:750;color:#38bdf8;font-size:0.80rem;text-transform:uppercase">Territorio (referencia)</span>
        </div>
        <ul class="sapi-kv-table">
            <li><span>Elevación</span><b>{elev}</b></li>
            <li><span>Pendiente</span><b>{slope}</b></li>
            <li><span>Historial FIRMS</span><b>{_esc(NOT_IN_CONTRACT)}</b></li>
        </ul>
        {dem_note}
        <div class="sapi-v2-note">{_esc(REFERENCE_TOPOGRAPHY_LABEL)}</div>

        <div class="sapi-panel-title-row" style="margin-top:0.60rem">
            <span style="display:inline-flex;align-items:center;color:#38bdf8;">{_SVG_WEATHER}</span>
            <span style="font-weight:750;color:#38bdf8;font-size:0.80rem;text-transform:uppercase">Meteorología regional</span>
        </div>
        <ul class="sapi-kv-table">
            {meteo_rows}
        </ul>

        <div class="sapi-panel-title-row" style="margin-top:0.60rem">
            <span style="display:inline-flex;align-items:center;color:#38bdf8;">{_SVG_CLOCK}</span>
            <span style="font-weight:750;color:#38bdf8;font-size:0.80rem;text-transform:uppercase">Ventana</span>
        </div>
        <ul class="sapi-kv-table">
            <li><span>T</span><b>{_human_date(view.forecast_time)} {_human_hm(view.forecast_time)} UTC</b></li>
            {window_rows}
        </ul>
        """,
        unsafe_allow_html=True,
    )


def _render_dmc_observation_panel() -> None:
    """Panel con la última observación DMC de Rodelillo (330007)."""
    from app.utils.dmc_live import (
        STATUS_CON_RETRASO,
        STATUS_DESACTUALIZADO,
        STATUS_NO_DISPONIBLE,
        STATUS_RECIENTE,
        fetch_rodelillo_live,
        refresh_rodelillo_live,
    )

    col_btn_title, col_btn_action = st.columns([1.4, 1.6], gap="small")
    with col_btn_title:
        st.markdown(
            f"""
            <div style="font-weight:750;color:#38bdf8;font-size:0.82rem;text-transform:uppercase;margin-top:0.45rem;display:flex;align-items:center;">
                {_SVG_WEATHER} <span style="margin-left:4px;">Observación DMC</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_btn_action:
        if st.button("Consultar DMC", key="sapi_btn_dmc_query", use_container_width=True, help="Consulta la última observación meteorológica de DMC Rodelillo (330007)"):
            st.session_state["sapi_dmc_data"] = refresh_rodelillo_live()
            st.session_state["sapi_dmc_open"] = True
            st.rerun()

    is_open = st.session_state.get("sapi_dmc_open", True)

    if "sapi_dmc_data" not in st.session_state:
        st.session_state["sapi_dmc_data"] = fetch_rodelillo_live()

    data = st.session_state.get("sapi_dmc_data", {})

    with st.expander("Última observación DMC Rodelillo (330007)", expanded=is_open):
        if not data:
            st.markdown(
                '<div style="font-size:0.82rem;color:var(--sapi-text-muted);padding:0.4rem 0;">'
                'Haga clic en <b>«Consultar DMC»</b> para obtener la última medición de la estación Rodelillo (330007).'
                '</div>',
                unsafe_allow_html=True,
            )
            return

        status = data.get("status", STATUS_NO_DISPONIBLE)
        if status == STATUS_RECIENTE:
            badge_class = "reciente"
        elif status == STATUS_CON_RETRASO:
            badge_class = "con_retraso"
        elif status == STATUS_DESACTUALIZADO:
            badge_class = "desactualizado"
        else:
            badge_class = "no_disponible"

        temp = data.get("temperatura_c")
        temp_str = f"{temp:.1f} °C" if temp is not None else "No disponible"

        hum = data.get("humedad_pct")
        hum_str = f"{int(round(hum))} %" if hum is not None else "No disponible"

        viento_kmh = data.get("viento_kmh")
        viento_kt = data.get("viento_kt")
        if viento_kmh is not None and viento_kt is not None:
            viento_str = f"{viento_kmh:.1f} km/h ({viento_kt:.1f} kt)"
        elif viento_kmh is not None:
            viento_str = f"{viento_kmh:.1f} km/h"
        else:
            viento_str = "No disponible"

        momento_cl = data.get("momento_cl") or "No disponible"
        momento_utc = data.get("momento_utc") or "No disponible"
        checked_cl = data.get("checked_at_cl") or "No disponible"
        checked_utc = data.get("checked_at_utc") or ""
        checked_str = f"{checked_cl} ({checked_utc})" if checked_utc else checked_cl

        error_msg = data.get("error")
        error_html = (
            f'<div style="font-size:0.78rem;color:#fca5a5;margin-top:0.35rem;">{_esc(error_msg)}</div>'
            if error_msg and not data.get("ok")
            else ""
        )

        st.markdown(
            f'<div class="sapi-dmc-box">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.45rem">'
            f'<span style="font-weight:700;font-size:0.84rem;color:var(--sapi-text-title)">Estación 330007 · Rodelillo</span>'
            f'<span class="sapi-dmc-badge sapi-dmc-badge--{badge_class}">{status}</span>'
            f'</div>'
            f'<ul class="sapi-kv-table" style="margin-bottom:0.35rem;">'
            f'<li><span>Temperatura</span><b>{temp_str}</b></li>'
            f'<li><span>Humedad relativa</span><b>{hum_str}</b></li>'
            f'<li><span>Viento</span><b>{viento_str}</b></li>'
            f'<li><span>Lectura (Chile)</span><b>{_esc(momento_cl)}</b></li>'
            f'<li><span>Lectura (UTC)</span><b>{_esc(momento_utc)}</b></li>'
            f'<li><span>Consulta efectuada</span><b>{_esc(checked_str)}</b></li>'
            f'</ul>'
            f'{error_html}'
            f'<div class="sapi-v2-note" style="margin-top:0.40rem;color:var(--sapi-dmc-top-notice);border-left:2px solid #ef4444;padding-left:0.45rem;font-style:normal;">'
            f'<b>Aviso:</b> Ranking histórico: 01-09-2026.<br>'
            f'La meteorología DMC reciente no se utilizó para calcular el ranking histórico.'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )


def _prepare_ranking_display(
    cells: tuple[RankingCell, ...],
    order_mode: Any,
    group_filter: Any,
) -> tuple[pd.DataFrame, str]:
    """Prepara el DataFrame y la nota explicativa para el ranking de 50 celdas."""
    group_map = _score_group_map(cells)

    filter_str = str(group_filter) if group_filter is not None else ""
    if filter_str.startswith("Grupo "):
        try:
            target_group = int(filter_str.split()[1])
            filtered_cells = [
                c for c in cells if group_map.get(c.score) == target_group
            ]
        except (IndexError, ValueError):
            filtered_cells = list(cells)
    else:
        filtered_cells = list(cells)

    order_str = str(order_mode) if order_mode is not None else ""
    if order_str == _ORDER_CELL_ID:
        display_cells = sorted(filtered_cells, key=lambda c: _cell_num(c.cell_id))
        note = "Orden numérico ascendente por identificador de celda (VP-001 → VP-050)."
    elif order_str == _ORDER_PRIORITY_TIES_BY_ID:
        display_cells = sorted(
            filtered_cells, key=lambda c: (c.display_rank, _cell_num(c.cell_id))
        )
        note = (
            "Orden por prioridad relativa; identificadores ordenados numéricamente "
            "dentro de cada grupo de empate."
        )
    else:
        display_cells = filtered_cells
        note = (
            "Orden y empates tal como los emitió el backend: celdas con score idéntico "
            "comparten el mismo número de prioridad."
        )

    df = pd.DataFrame(
        [
            {
                "Prioridad": c.display_rank,
                "Celda": c.cell_id,
                "Score relativo": round(c.score, 6),
                "Empate": f"×{c.tie_group_size}" if c.tie_group_size > 1 else "—",
                "Grupo": f"Grupo {group_map.get(c.score, 1)}",
            }
            for c in display_cells
        ]
    )
    return df, note


def _cell_num(cell_id: str) -> int:
    try:
        return int(cell_id.split("-")[1])
    except (IndexError, ValueError):
        return 0


def _render_ranking_expander(view: RankingView) -> None:
    """Tabla completa de ranking expandible con filtros."""
    with st.expander("Ver ranking completo (50 celdas) y filtros", expanded=False):
        order_mode = st.radio(
            "Criterio de ordenación",
            options=[
                _ORDER_PRIORITY_OFFICIAL,
                _ORDER_PRIORITY_TIES_BY_ID,
                _ORDER_CELL_ID,
            ],
            horizontal=True,
            key="ranking_v2_order",
            help="Cambia solo el orden de presentación. No altera los datos del backend.",
        )

        group_map = _score_group_map(view.cells)
        available_groups = sorted(set(group_map.values()))
        group_options = ["Todos los grupos (50 celdas)"] + [
            f"Grupo {g}" for g in available_groups
        ]
        group_filter = st.selectbox(
            "Filtrar por grupo de prioridad relativa",
            options=group_options,
            key="ranking_v2_group_filter",
        )

        df, note = _prepare_ranking_display(view.cells, order_mode, group_filter)
        st.dataframe(df, use_container_width=True, hide_index=True, height=280)
        st.caption(f"{note} Criterio exploratorio relativo del Modelo D.")


def _render_tech_expander(view: RankingView) -> None:
    """Detalle técnico desplegable con trazabilidad completa."""
    window_end = view.window_end
    station = (
        f"{view.station_name} {view.station_id}"
        if view.station_available
        else NOT_PROVIDED
    )
    model_str = (
        f"{view.model_version} ({view.model_status})"
        if view.model_status
        else f"{view.model_version}"
    )
    firms_detail = (
        f"origen {view.firms_origin or NOT_PROVIDED} · cobertura hasta "
        f"{view.firms_coverage_end.isoformat() if view.firms_coverage_end else NOT_PROVIDED}"
        f" · lag {view.firms_lag_days if view.firms_lag_days is not None else NOT_PROVIDED}"
        f" · estado {view.firms_status or NOT_PROVIDED}"
        if view.firms_provenance_available
        else NOT_PROVIDED
    )
    sections = [
        (
            "**Modelo y evaluación**\n"
            f"- **Origen del ranking:** backend Spring Boot, `GET {RANKING_PATH}` "
            f"(obtenido {_iso_utc(view.fetched_at)}; cache de {_CACHE_TTL_SECONDS // 60} min)\n"
            f"- **Schema:** `{view.schema_version}` · semántica `{view.score_semantics}` · "
            f"validación científica: `{str(view.scientific_model_validation).lower()}`\n"
            f"- **Modelo:** {model_str}\n"
            f"- **Inputs fingerprint:** `{view.inputs_fingerprint}`\n"
            f"- **Forecast time:** {_iso_utc(view.forecast_time)}\n"
            + (
                f"- **Ventana evaluada:** {_iso_utc(view.forecast_time)} → {_iso_utc(window_end)} "
                f"(h={view.horizon_hours}h)"
                if window_end is not None
                else (
                    "- **Ventana evaluada:** ventana no representable"
                    if view.horizon_hours is not None
                    else f"- **Ventana evaluada:** horizonte {NOT_PROVIDED}"
                )
            )
        ),
        (
            "**Procedencia y frescura de datos**\n"
            f"- **Estación DMC:** {station}\n"
            + (
                f"- **Weather timestamp usado:** {_iso_utc(view.weather_timestamp)}\n"
                if view.weather_timestamp is not None
                else f"- **Weather timestamp usado:** {NOT_PROVIDED}\n"
            )
            + (
                f"- **Antigüedad de la observación (al evaluar):** {view.age_hours:.1f} h — "
                f"**{view.freshness}**\n"
                if view.freshness_available
                else f"- **Antigüedad / frescura de la observación:** {NOT_PROVIDED}\n"
            )
            + "- **Fuente de detecciones:** NASA FIRMS\n"
            + f"- **Procedencia FIRMS:** {firms_detail}"
            + (
                "\n  *(Sincronía FIRMS evaluada respecto a fecha T; "
                "no corresponde a la fecha actual ni a detecciones en tiempo real)*"
                if view.firms_provenance_available
                and view.firms_status == "FIRMS AL DÍA"
                else ""
            )
        ),
        (
            "**Trazabilidad y topografía**\n"
            f"- **Topografía:** {REFERENCE_TOPOGRAPHY_LABEL}\n"
            "- **Integración de contrato:** Detalle meteorológico y FIRMS desagregado por celda "
            "no expuesto en el contrato `sapi-ranking-v0` (consolidación regional v0)."
        ),
    ]
    missing = tuple(
        name for name in _CONTRACT_METADATA_FIELDS if getattr(view, name) is None
    )
    if missing:
        sections.append(
            "- **Metadata opcional no informada por el backend:** "
            + ", ".join(f"`{name}`" for name in missing)
        )
    with st.expander("Ver detalle técnico y metadatos completos", expanded=False):
        st.markdown("\n\n".join(sections))
        st.caption(FIXED_DISCLAIMER)


def _render_bottom_modules(view: RankingView) -> None:
    """Módulos inferiores divididos en dos columnas balanceadas (~50/50)."""
    left_col, right_col = st.columns(2, gap="medium")

    with left_col:
        st.markdown(
            f"""
            <div class="sapi-module-card">
                <div class="sapi-module-header">
                    <div class="sapi-module-title">
                        {_SVG_CPU}
                        <span>Trazabilidad técnica y fuentes</span>
                    </div>
                </div>
                <div class="sapi-info-grid">
                    <div class="sapi-info-item">
                        <span class="sapi-info-item__icon">{_SVG_CPU}</span>
                        <div>
                            <div class="sapi-info-item__title">Modelo</div>
                            <div class="sapi-info-item__val">prototype_model_d_v1</div>
                            <div class="sapi-info-item__sub">SAPI - ranking_v0</div>
                        </div>
                    </div>
                    <div class="sapi-info-item">
                        <span class="sapi-info-item__icon">{_SVG_SERVER}</span>
                        <div>
                            <div class="sapi-info-item__title">Origen del ranking</div>
                            <div class="sapi-info-item__val">GET /api/v1/ranking</div>
                            <div class="sapi-info-item__sub">Spring Boot (cache 5 min)</div>
                        </div>
                    </div>
                    <div class="sapi-info-item">
                        <span class="sapi-info-item__icon">{_SVG_CLOCK}</span>
                        <div>
                            <div class="sapi-info-item__title">Forecast time</div>
                            <div class="sapi-info-item__val">2026-09-01 00:00 UTC</div>
                            <div class="sapi-info-item__sub">(h+6)</div>
                        </div>
                    </div>
                    <div class="sapi-info-item">
                        <span class="sapi-info-item__icon">{_SVG_SATELLITE}</span>
                        <div>
                            <div class="sapi-info-item__title">Fuente de datos</div>
                            <div class="sapi-info-item__val">NASA FIRMS</div>
                            <div class="sapi-info-item__sub">Cobertura hasta 2026-08-30 (evaluado respecto al instante histórico T)</div>
                        </div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        _render_tech_expander(view)

    with right_col:
        group_map = _score_group_map(view.cells)
        preview_rows = []
        for c in view.cells[:5]:
            ties_txt = f"x{c.tie_group_size}" if c.tie_group_size > 1 else "—"
            grp_txt = f"Grupo {group_map.get(c.score, 1)}"
            preview_rows.append(
                f"<tr>"
                f"<td>{c.display_rank}</td>"
                f"<td><b>{_esc(c.cell_id)}</b></td>"
                f"<td>{grp_txt}</td>"
                f"<td>{c.score:.4f}</td>"
                f"<td>{ties_txt}</td>"
                f"</tr>"
            )

        st.markdown(
            f"""
            <div class="sapi-module-card">
                <div class="sapi-module-header">
                    <div class="sapi-module-title">
                        {_SVG_CHART}
                        <span>Vista previa del ranking (Top 5)</span>
                    </div>
                </div>
                <table class="sapi-mini-table">
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>Celda</th>
                            <th>Grupo</th>
                            <th>Score relativo</th>
                            <th>Empate</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join(preview_rows)}
                    </tbody>
                </table>
            </div>
            """,
            unsafe_allow_html=True,
        )
        _render_ranking_expander(view)


def _render_disclaimer(view: RankingView) -> None:
    """Disclaimer científico explícito."""
    text = (
        view.disclaimer.strip() if view.disclaimer and view.disclaimer.strip() else None
    )
    if text and FIXED_DISCLAIMER not in text:
        st.markdown(
            f'<div class="sapi-v2-disclaimer">'
            f"<div>{_esc(text)}</div>"
            '<div style="margin-top:0.35rem;opacity:0.85;font-size:0.84rem">'
            f"{FIXED_DISCLAIMER}</div>"
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<p class="sapi-v2-disclaimer">{_esc(text or FIXED_DISCLAIMER)}</p>',
            unsafe_allow_html=True,
        )


def _render_backend_error(exc: BackendError) -> None:
    """Estado de error controlado."""
    st.markdown("## S.A.P.I. — PROTOTIPO EXPLORATORIO")
    st.error(f"No se pudo obtener el ranking del backend: {exc.user_message}")
    if exc.error_type in KNOWN_ERROR_TYPES:
        st.caption(f"tipo reportado por el backend: `{exc.error_type}`")
    st.caption(
        "La vista consume únicamente `GET /api/v1/ranking` del backend Spring Boot "
        "(`SAPI_BACKEND_BASE_URL`). No se ejecuta inferencia local ni se muestran "
        "datos cacheados como actuales."
    )


# ── punto de entrada principal ─────────────────────────────────────────────────


def render_ranking_backend_dashboard() -> None:
    """Punto de entrada de la vista v2 definitiva para la Defensa Académica."""
    if st.sidebar.button("Actualizar ranking", help="Vuelve a consultar al backend."):
        refresh_ranking_cache()

    try:
        view = _load_ranking()
    except BackendError as exc:
        _render_backend_error(exc)
        return

    from app.state import appearance, set_appearance
    from app.theme.tokens import APPEARANCE_CLARO, APPEARANCE_OSCURO

    curr_mode = appearance()
    _inject_css(curr_mode)

    cell_ids = [c.cell_id for c in view.cells]
    if st.session_state.get(_SESSION_SELECTED) not in cell_ids:
        st.session_state[_SESSION_SELECTED] = cell_ids[0]
    if _SESSION_EXPANDED not in st.session_state:
        st.session_state[_SESSION_EXPANDED] = False

    is_expanded = st.session_state[_SESSION_EXPANDED]

    # 1. Cabecera compacta con toggle de tema (TAREA A)
    head_col, toggle_col = st.columns([0.965, 0.035], gap="small")
    with head_col:
        _render_header(view)
    with toggle_col:
        if curr_mode == APPEARANCE_OSCURO:
            if st.button("◐", key="sapi_theme_toggle_btn", help="Cambiar a modo claro"):
                set_appearance(APPEARANCE_CLARO)
                st.rerun()
        else:
            if st.button("◑", key="sapi_theme_toggle_btn", help="Cambiar a modo oscuro"):
                set_appearance(APPEARANCE_OSCURO)
                st.rerun()

    with st.sidebar:
        from app.components.controls import render_appearance_toggle
        render_appearance_toggle(location="sidebar")

    # 2. Alerta histórica obligatoria
    _render_freshness_state(view)

    # 3. Resumen DMC en primera pantalla sin scroll (TAREA 3)
    _render_dmc_top_strip()

    # 4. Fila de 5 tarjetas de indicadores superiores (TAREA B)
    _render_kpi_strip(view, st.session_state[_SESSION_SELECTED])

    # 5. Sección principal: Mapa protagonista (~68%) + Panel Hallazgo principal (~32%)
    if is_expanded:
        m_head_left, m_head_right = st.columns([7.5, 2.5])
        with m_head_left:
            st.markdown(
                f"""
                <div class="sapi-map-title-row">
                    <span class="sapi-map-icon">{_SVG_MAP}</span>
                    <div style="flex-grow:1;">
                        <div style="display:flex;align-items:center;gap:0.6rem;flex-wrap:wrap;">
                            <div class="sapi-map-title">Mapa de riesgo relativo de incendio (Vista ampliada)</div>
                            <span class="sapi-map-historical-tag">RANKING HISTÓRICO · T: {_human_date(view.forecast_time)} {_human_hm(view.forecast_time)} UTC · HORIZONTE: {view.horizon_hours or 6} h</span>
                        </div>
                        <div class="sapi-map-sub">Cada celda muestra el score relativo (no es una probabilidad calibrada).</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with m_head_right:
            if st.button("↙ Restaurar vista", key="btn_restore_map", use_container_width=True):
                st.session_state[_SESSION_EXPANDED] = False
                st.rerun()

        fmap = build_map(view, _MAP_MODE_PRIORIDADES, st.session_state[_SESSION_SELECTED])
        event = st_folium(
            fmap,
            height=700,
            use_container_width=True,
            key="ranking_v2_map_expanded",
            returned_objects=["last_clicked"],
        )
        clicked = cell_from_click(event)
        if clicked and clicked != st.session_state[_SESSION_SELECTED]:
            st.session_state[_SESSION_SELECTED] = clicked
            st.rerun()

        _render_map_legend_bar()

    else:
        map_col, side_col = st.columns([2.12, 1], gap="medium")

        with map_col:
            m_head_left, m_head_right = st.columns([6.8, 3.2])
            with m_head_left:
                st.markdown(
                    f"""
                    <div class="sapi-map-title-row">
                        <span class="sapi-map-icon">{_SVG_MAP}</span>
                        <div style="flex-grow:1;">
                            <div style="display:flex;align-items:center;gap:0.6rem;flex-wrap:wrap;">
                                <div class="sapi-map-title">Mapa de riesgo relativo de incendio</div>
                                <span class="sapi-map-historical-tag">RANKING HISTÓRICO · T: {_human_date(view.forecast_time)} {_human_hm(view.forecast_time)} UTC · HORIZONTE: {view.horizon_hours or 6} h</span>
                            </div>
                            <div class="sapi-map-sub">Cada celda muestra el score relativo (no es una probabilidad calibrada).</div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with m_head_right:
                r_col1, r_col2 = st.columns([1.6, 1.4])
                with r_col1:
                    st.markdown(
                        """
                        <div class="sapi-map-risk-widget">
                            <span class="sapi-map-risk-label">Riesgo (score)</span>
                            <div class="sapi-map-risk-bar"></div>
                            <div class="sapi-map-risk-scale"><span>Bajo</span><span>Alto</span></div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                with r_col2:
                    if st.button("⤢ Expandir", key="btn_expand_map", help="Amplía el mapa a pantalla completa"):
                        st.session_state[_SESSION_EXPANDED] = True
                        st.rerun()

            fmap = build_map(view, _MAP_MODE_PRIORIDADES, st.session_state[_SESSION_SELECTED])
            event = st_folium(
                fmap,
                height=600,
                use_container_width=True,
                key="ranking_v2_map_compact",
                returned_objects=["last_clicked"],
            )
            clicked = cell_from_click(event)
            if clicked and clicked != st.session_state[_SESSION_SELECTED]:
                st.session_state[_SESSION_SELECTED] = clicked
                st.rerun()

            _render_map_legend_bar()

        with side_col:
            # BLOQUE 1: Hallazgo prioritario y selector de celda
            st.markdown(
                """
                <div class="sapi-panel-title-row">
                    <div class="sapi-panel-title">Hallazgo principal</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            _render_priority_panel(view)

            selected_idx = (
                cell_ids.index(st.session_state[_SESSION_SELECTED])
                if st.session_state[_SESSION_SELECTED] in cell_ids
                else 0
            )
            new_selection = st.selectbox(
                f"Seleccionar celda ({len(cell_ids)} disponibles)",
                options=cell_ids,
                index=selected_idx,
                key="sapi_cell_selector",
                help="Selecciona una celda para inspeccionar sus variables territoriales y meteorológicas.",
            )
            if new_selection != st.session_state[_SESSION_SELECTED]:
                st.session_state[_SESSION_SELECTED] = new_selection
                st.rerun()

            # BLOQUE 2: Atributos esenciales celda seleccionada
            _render_selected_panel(view, st.session_state[_SESSION_SELECTED])

            # BLOQUE 3: Última observación DMC Rodelillo
            _render_dmc_observation_panel()

    # 6. Disclaimer científico explícito
    _render_disclaimer(view)

    # 7. Módulos inferiores balanceados (~50/50): Información técnica y Ranking
    _render_bottom_modules(view)

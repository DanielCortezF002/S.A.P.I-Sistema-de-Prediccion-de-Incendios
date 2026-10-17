"""Vista PROTOTIPO v2: ranking servido por el backend Spring Boot (SAPI-61).

Reemplaza en el flujo principal a `prototype_view.py` (congelado, Hito 1),
que puntuaba en proceso con `score_current_grid()`. Esta vista no ejecuta
inferencia: recibe un `RankingView` ya validado por
`app.utils.backend_client` y lo presenta. Flujo:

    app/app.py → render_ranking_backend_dashboard()
        → BackendRankingClient.fetch_ranking()  (HTTP GET /api/v1/ranking)
        → RankingView → mapa / grupo prioritario / ranking / trazabilidad

Reglas:
- Scores, rank, display_rank, tie_group_size y el orden de las celdas se
  muestran tal cual llegan. No se reordena ni se recalcula nada.
- La geometría de las 50 celdas viene de la fuente estática autoritativa
  `src/geo/grid.py` (la misma que usa el servicio). Elevación y pendiente,
  de la tabla congelada del Hito 1 (`app.utils.reference_topography`),
  etiquetadas como referencia.
- La metadata opcional del contrato (frescura, estación, procedencia
  FIRMS) se muestra solo si el backend la envía. Si falta, se declara
  "no informado por el backend". Nunca se deriva ni se inventa.
  `model_status`, `meteo_actual` y el historial FIRMS por celda no forman
  parte del contrato.
- Texto remoto que entra en HTML se escapa siempre.
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
from src.geo.grid import CELL_COUNT, all_cells, assign_cell, cell_center, grid_center

_MAP_MODE_PRIORIDADES = "Prioridades"
_MAP_MODE_TODAS = "Todas las celdas"
_SESSION_MAP_MODE = "ranking_v2_map_mode"
_SESSION_SELECTED = "ranking_v2_selected_cell"
_SESSION_PENDING_SELECTION = "ranking_v2_pending_cell"
_SESSION_LAST_PROCESSED_CLICK = "ranking_v2_last_processed_click"
_SESSION_TABLE = "ranking_v2_table"
_SESSION_TABLE_SYNCED_CELL = "ranking_v2_table_synced_cell"
_SESSION_TABLE_LAST_FILTER = "ranking_v2_table_last_filter"
_SESSION_TABLE_LAST_ROWS = "ranking_v2_table_last_rows"
_SESSION_TABLE_LAST_CELLS = "ranking_v2_table_last_cells"
_ORDER_PRIORITY_OFFICIAL = "Orden entregado por el backend"
_ORDER_PRIORITY_TIES_BY_ID = "Prioridad con empates ordenados por ID"
_ORDER_CELL_ID = "Identificador de celda (VP-001 → VP-050)"
_CACHE_TTL_SECONDS = 300
# Metadata opcional de sapi-ranking-v0. model_status y meteo_actual se toleran
# si un payload los trae, pero no son campos del contrato y no se listan como
# pendientes de él.
_CONTRACT_METADATA_FIELDS = tuple(
    name for name in ADDITIVE_FIELDS if name not in {"model_status", "meteo_actual"}
)

# Etiqueta de frescura que el servicio de inferencia asigna a observaciones
# de más de 24 h (misma cadena que `prototype_service.FRESHNESS_HISTORICAL`).
# Solo se compara contra lo que el backend envíe; nunca se calcula aquí.
FRESHNESS_HISTORICAL_LABEL = "DATOS HISTÓRICOS / DESACTUALIZADOS"
NOT_PROVIDED = "no informado por el backend"
NOT_IN_CONTRACT = "Detalle FIRMS por celda no expuesto por API v0"
FIXED_DISCLAIMER = (
    "El score corresponde a un ranking relativo exploratorio "
    "y no a una probabilidad calibrada de incendio."
)

# Paleta por grupo de score único (misma semántica que la vista Hito 1):
# posición relativa en un ranking exploratorio, nunca alerta oficial.
_GROUP_VISUAL = {
    1: {
        "label": "Grupo 1",
        "fill": "#c45c26",
        "edge": "#f0a070",
        "op_all": 0.42,
        "op_prio": 0.48,
    },
    2: {
        "label": "Grupo 2",
        "fill": "#a67c2a",
        "edge": "#c9a35a",
        "op_all": 0.20,
        "op_prio": 0.10,
    },
    3: {
        "label": "Grupo 3",
        "fill": "#5a6570",
        "edge": "#7a8694",
        "op_all": 0.11,
        "op_prio": 0.08,
    },
}
_SELECTED_EDGE = "#38bdf8"
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
    """Mapa Folium con los 50 rectángulos de la grilla coloreados por grupo.

    Args:
        view: Ranking validado.
        mode: `Prioridades` (solo resalta el grupo prioritario) o `Todas las celdas`.
        selected_id: Celda a resaltar con borde de selección.
        topography: Tabla de referencia; por defecto la congelada del Hito 1.

    Returns:
        `folium.Map` con exactamente una `folium.Rectangle` por celda.
    """
    topo = reference_topography() if topography is None else topography
    geometry = _geometry_by_cell()
    group_by_score = _score_group_map(view.cells)
    top_rank = min((c.display_rank for c in view.cells), default=1)

    if selected_id:
        cell_idx = _cell_num(selected_id)
        if 1 <= cell_idx <= CELL_COUNT:
            center_lat, center_lon = cell_center(cell_idx)
            zoom_start = 12
        else:
            center_lat, center_lon = grid_center()
            zoom_start = 11
    else:
        center_lat, center_lon = grid_center()
        zoom_start = 11

    fmap = folium.Map(
        location=[center_lat, center_lon], zoom_start=zoom_start, tiles="OpenStreetMap"
    )

    for c in view.cells:
        g = geometry[c.cell_id]
        vis = _GROUP_VISUAL.get(group_by_score[c.score], _GROUP_VISUAL[3])
        is_priority = c.display_rank == top_rank
        is_selected = selected_id is not None and c.cell_id == selected_id
        if mode == _MAP_MODE_PRIORIDADES:
            fill_opacity = vis["op_prio"] if is_priority else 0.08
            weight = 1.5 if is_priority else 0.5
            fill = vis["fill"] if is_priority else "#6b7280"
            edge = vis["edge"] if is_priority else "#6b7280"
        else:
            fill_opacity = vis["op_all"]
            weight = 1.0
            fill = vis["fill"]
            edge = vis["edge"]
        if is_selected:
            edge = _SELECTED_EDGE
            weight = 3.0
            fill = vis["fill"]
            fill_opacity = max(fill_opacity, 0.40)

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
        folium.Rectangle(
            bounds=[[g["min_lat"], g["min_lon"]], [g["max_lat"], g["max_lon"]]],
            color=edge,
            fill=True,
            fill_color=fill,
            fill_opacity=fill_opacity,
            weight=weight,
            tooltip=tooltip,
        ).add_to(fmap)
    return fmap


# ── carga desde el backend ─────────────────────────────────────────────────────


@st.cache_data(
    ttl=_CACHE_TTL_SECONDS,
    show_spinner="Consultando el ranking al backend...",
)
def _cached_ranking(
    base_url: str, connect_timeout: float, read_timeout: float
) -> RankingView:
    """Cache de 5 min del ranking YA validado (los errores no se cachean)."""
    client = BackendRankingClient(
        base_url, connect_timeout=connect_timeout, read_timeout=read_timeout
    )
    return client.fetch_ranking()


def _load_ranking() -> RankingView:
    connect_timeout, read_timeout = get_backend_timeouts()
    return _cached_ranking(get_backend_base_url(), connect_timeout, read_timeout)


def refresh_ranking_cache() -> None:
    """Invalida la cache para forzar una nueva consulta al backend."""
    _cached_ranking.clear()


# ── render ─────────────────────────────────────────────────────────────────────


def _inject_css() -> None:
    st.markdown(
        """
        <style>
        .sapi-v2-header {
            display: flex; flex-wrap: wrap; justify-content: space-between;
            gap: 1.25rem; align-items: flex-start; margin: 0 0 1rem 0;
            font-family: var(--sapi-font-stack, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif);
        }
        .sapi-v2-title {
            font-size: 2.1rem; font-weight: 850; letter-spacing: -0.03em;
            line-height: 1.1; margin: 0; color: var(--sapi-text-primary);
        }
        .sapi-v2-sub {
            font-size: 1.02rem; opacity: 0.88; margin-top: 0.35rem; max-width: 42rem;
            color: var(--sapi-text-primary); font-weight: 500;
        }
        .sapi-v2-status {
            display: flex; flex-wrap: wrap; gap: 0.55rem; justify-content: flex-end; align-items: center;
        }
        .sapi-v2-badge {
            display: inline-flex; align-items: center; padding: 0.38rem 0.85rem;
            border-radius: 999px; font-size: 0.74rem; font-weight: 800; letter-spacing: 0.06em;
            text-transform: uppercase; border: 1px solid rgba(127,127,127,0.35);
        }
        .sapi-v2-badge--violet { background: #3b2a6d; border-color: #8b5cf6; color: #ede9fe; box-shadow: 0 2px 6px rgba(139,92,246,0.25); }
        .sapi-v2-badge--hist { background: #7f1d1d; border-color: #ef4444; color: #fee2e2; box-shadow: 0 2px 6px rgba(239,68,68,0.25); }
        .sapi-v2-badge--rest { background: #064e3b; border-color: #10b981; color: #d1fae5; box-shadow: 0 2px 6px rgba(16,185,129,0.25); }
        .sapi-v2-badge--postgis { background: #0c4a6e; border-color: #38bdf8; color: #e0f2fe; }
        .sapi-v2-badge--model { background: #262626; border-color: #737373; color: #f5f5f5; }
        
        .sapi-v2-meta {
            margin-top: 0.6rem; font-size: 0.95rem; opacity: 0.95;
            text-align: right; line-height: 1.6; color: var(--sapi-text-primary);
            font-variant-numeric: tabular-nums;
        }
        
        .sapi-v2-kpi-row {
            display: grid; grid-template-columns: repeat(5, minmax(0, 1fr));
            gap: 0.65rem; margin: 0.4rem 0 0.65rem 0;
        }
        .sapi-v2-kpi {
            background: var(--sapi-surface-card);
            border: 1px solid var(--sapi-border-card);
            border-radius: 10px;
            padding: 0.65rem 0.85rem; min-height: 4.4rem;
            display: flex; flex-direction: column; justify-content: center;
            box-shadow: 0 2px 6px rgba(0,0,0,0.14);
            transition: transform 0.15s ease, border-color 0.15s ease;
        }
        .sapi-v2-kpi:hover {
            border-color: var(--sapi-accent);
        }
        .sapi-v2-kpi__value {
            font-size: 1.40rem; font-weight: 850; letter-spacing: -0.02em;
            line-height: 1.15; font-variant-numeric: tabular-nums;
            color: var(--sapi-text-primary);
        }
        .sapi-v2-kpi__value--na {
            font-size: 0.85rem; font-weight: 600; opacity: 0.82;
            color: var(--sapi-text-primary); font-style: italic;
        }
        .sapi-v2-kpi__label {
            font-size: 0.78rem; opacity: 0.85; margin-top: 0.25rem; font-weight: 700;
            text-transform: uppercase; letter-spacing: 0.04em;
            color: var(--sapi-text-primary);
        }
        
        .sapi-v2-panel {
            background: var(--sapi-surface-card);
            border: 1px solid var(--sapi-border-card);
            border-radius: 10px;
            padding: 0.85rem 1.05rem; margin-bottom: 0.75rem;
            color: var(--sapi-text-primary);
            box-shadow: 0 2px 8px rgba(0,0,0,0.14);
        }
        .sapi-v2-panel__h {
            font-size: 0.80rem; font-weight: 850; letter-spacing: 0.09em;
            text-transform: uppercase; color: var(--sapi-accent); margin: 0 0 0.45rem 0;
            display: flex; align-items: center; gap: 0.45rem;
        }
        .sapi-v2-prio-num {
            font-size: 2.05rem; font-weight: 900; letter-spacing: -0.04em;
            line-height: 1; color: #f0a070;
            text-shadow: 0 2px 8px rgba(240, 160, 112, 0.25);
        }
        .sapi-v2-chip {
            display: inline-block; padding: 0.22rem 0.55rem; margin: 0.18rem 0.18rem 0 0;
            border-radius: 5px; background: var(--sapi-surface-muted);
            border: 1px solid var(--sapi-border-card); font-size: 0.85rem;
            font-weight: 750; font-variant-numeric: tabular-nums;
            color: var(--sapi-text-primary);
        }
        .sapi-v2-kv { list-style: none; padding: 0; margin: 0.35rem 0 0 0; }
        .sapi-v2-kv li {
            display: flex; justify-content: space-between; gap: 0.75rem;
            padding: 0.32rem 0; border-bottom: 1px solid var(--sapi-border-subtle);
            font-size: 0.90rem; color: var(--sapi-text-primary);
        }
        .sapi-v2-kv li:last-child { border-bottom: none; }
        .sapi-v2-kv span { opacity: 0.75; font-weight: 550; }
        .sapi-v2-kv b { font-weight: 750; }
        
        .sapi-v2-legend {
            margin: 0.45rem 0 0.65rem 0;
            background: var(--sapi-surface-card);
            border: 1px solid var(--sapi-border-card);
            border-radius: 10px; padding: 0.55rem 0.95rem;
            color: var(--sapi-text-primary);
            box-shadow: 0 2px 6px rgba(0,0,0,0.14);
            display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 0.5rem;
        }
        .sapi-v2-legend__header {
            display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap;
        }
        .sapi-v2-legend__title {
            font-weight: 850; letter-spacing: 0.08em; text-transform: uppercase;
            font-size: 0.80rem; color: var(--sapi-accent); margin: 0;
        }
        .sapi-v2-legend__note {
            font-size: 0.80rem; opacity: 0.72; font-style: italic;
        }
        .sapi-v2-legend__items {
            display: flex; align-items: center; gap: 1rem; flex-wrap: wrap;
        }
        .sapi-v2-legend__row {
            display: flex; align-items: center; gap: 0.45rem;
            font-weight: 650; font-size: 0.86rem;
        }
        .sapi-v2-dot {
            width: 13px; height: 13px; border-radius: 50%; display: inline-block;
            border: 2px solid rgba(255,255,255,0.45); flex-shrink: 0;
        }
        
        .sapi-v2-disclaimer {
            font-size: 0.88rem; opacity: 0.95; margin: 0.45rem 0 0.65rem 0;
            padding: 0.65rem 1rem; border-radius: 8px;
            background: var(--sapi-surface-muted);
            border-left: 4px solid var(--sapi-accent);
            color: var(--sapi-text-primary);
            line-height: 1.45; font-weight: 550;
        }
        .sapi-v2-note {
            font-size: 0.82rem; opacity: 0.82; margin-top: 0.35rem;
            color: var(--sapi-text-primary); font-style: italic;
        }
        @media (max-width:1100px) {
            .sapi-v2-kpi-row { grid-template-columns: repeat(3, minmax(0, 1fr)); }
        }
        @media (max-width:700px) {
            .sapi-v2-kpi-row { grid-template-columns: repeat(2, minmax(0, 1fr)); }
            .sapi-v2-meta { text-align: left; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_header(view: RankingView) -> None:
    date_line = _human_date(view.forecast_time)
    window_end = view.window_end
    if window_end is not None:
        window_line = f"{_human_hm(view.forecast_time)} → {_human_hm(window_end)} UTC"
    elif view.horizon_hours is not None:
        # Horizonte informado pero T+h no representable: ausencia explícita,
        # sin recortar a una fecha inventada.
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
        '<div class="sapi-v2-header"><div>'
        '<div class="sapi-v2-title">S.A.P.I.</div>'
        '<div class="sapi-v2-sub">Sistema de Alerta y Priorización de Riesgo de Incendios · Defensa Académica Sprint 2</div>'
        "</div>"
        '<div class="sapi-v2-status">'
        '<span class="sapi-v2-badge sapi-v2-badge--violet">PROTOTIPO EXPLORATORIO</span>'
        '<span class="sapi-v2-badge sapi-v2-badge--rest">BACKEND REST</span>'
        f"{hist_badge}</div></div>"
        f'<div class="sapi-v2-meta">{date_line}<br>{window_line}<br>{station_line}<br>'
        f"Obtenido del backend: {_human_hm(view.fetched_at)} UTC</div>",
        unsafe_allow_html=True,
    )


def _render_freshness_state(view: RankingView) -> None:
    """Banner de frescura solo con datos del backend; estado explícito si faltan."""
    if not view.freshness_available:
        st.info(
            "Frescura de la observación meteorológica: no informada por el backend. "
            "No se asume que el ranking represente el riesgo actual."
        )
        return
    if view.freshness == FRESHNESS_HISTORICAL_LABEL:
        st.warning(
            f"⚠ DATOS HISTÓRICOS · última observación hace {view.age_hours:.0f} h "
            "(antigüedad medida por el servicio al evaluar)\n\n"
            "El ranking corresponde al instante indicado y NO representa el riesgo actual."
        )


def _kpi(value: str, label: str, available: bool = True) -> str:
    cls = (
        "sapi-v2-kpi__value"
        if available
        else "sapi-v2-kpi__value sapi-v2-kpi__value--na"
    )
    return (
        f'<div class="sapi-v2-kpi"><div class="{cls}">{value}</div>'
        f'<div class="sapi-v2-kpi__label">{label}</div></div>'
    )


def _render_kpi_strip(view: RankingView) -> None:
    m = view.meteo_actual
    if m is not None:
        cards = [
            _kpi(f"{m.temperatura:.1f} °C", "Temperatura"),
            _kpi(f"{m.humedad_relativa:.0f} %", "Humedad"),
            _kpi(f"{m.velocidad_viento_kmh:.1f} km/h", "Viento"),
            _kpi("Activa" if m.regla_30_30_30 else "Inactiva", "Regla 30-30-30"),
        ]
    else:
        na = _esc(NOT_PROVIDED)
        cards = [
            _kpi(na, "Temperatura", available=False),
            _kpi(na, "Humedad", available=False),
            _kpi(na, "Viento", available=False),
            _kpi(na, "Regla 30-30-30", available=False),
        ]
    cards.append(_kpi(str(len(view.cells)), "Celdas evaluadas"))
    st.markdown(
        f'<div class="sapi-v2-kpi-row">{"".join(cards)}</div>', unsafe_allow_html=True
    )
    if m is None:
        st.caption(
            "ℹ **Variables meteorológicas:** Procesadas por el Modelo D en inferencia (`temperatura`, `humedad`, `viento`). "
            "El endpoint v0 proyecta el ranking relativo de celdas; la exposición de telemetría instantánea está catalogada como mejora aditiva para el contrato v1."
        )


def _render_disclaimer(view: RankingView) -> None:
    text = (
        view.disclaimer.strip() if view.disclaimer and view.disclaimer.strip() else None
    )
    if text and FIXED_DISCLAIMER not in text:
        st.markdown(
            f'<div class="sapi-v2-disclaimer">'
            f'<div>{_esc(text)}</div>'
            f'<div style="margin-top:0.35rem;opacity:0.85;font-size:0.84rem">{FIXED_DISCLAIMER}</div>'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<p class="sapi-v2-disclaimer">{_esc(text or FIXED_DISCLAIMER)}</p>',
            unsafe_allow_html=True,
        )


def _render_map_legend(group_by_score: dict[float, int]) -> None:
    rows = []
    for g in sorted(set(group_by_score.values())):
        vis = _GROUP_VISUAL.get(g, _GROUP_VISUAL[3])
        rows.append(
            f'<div class="sapi-v2-legend__row">'
            f'<span class="sapi-v2-dot" style="background:{vis["fill"]}"></span>'
            f'{vis["label"]}</div>'
        )
    st.markdown(
        '<div class="sapi-v2-legend">'
        '<div class="sapi-v2-legend__header">'
        '<div class="sapi-v2-legend__title">Prioridad relativa</div>'
        '<div class="sapi-v2-legend__note">Score relativo (no representa alertas oficiales).</div>'
        '</div>'
        f'<div class="sapi-v2-legend__items">{"".join(rows)}</div>'
        '</div>',
        unsafe_allow_html=True,
    )


def _render_map(view: RankingView, selected_id: Optional[str]) -> Optional[str]:
    """Mapa protagonista. Devuelve cell_id si hubo click dentro de una celda."""
    mode = st.radio(
        "Vista del mapa",
        options=[_MAP_MODE_PRIORIDADES, _MAP_MODE_TODAS],
        horizontal=True,
        key=_SESSION_MAP_MODE,
        help="Solo cambia la representación visual. No consulta ni recalcula nada.",
    )
    fmap = build_map(view, mode, selected_id)

    target_center = None
    target_zoom = 11
    if selected_id:
        cell_idx = _cell_num(selected_id)
        if 1 <= cell_idx <= CELL_COUNT:
            target_center = cell_center(cell_idx)
            target_zoom = 12

    event = st_folium(
        fmap,
        height=560,
        use_container_width=True,
        key="ranking_v2_map",
        center=target_center,
        zoom=target_zoom,
        returned_objects=["last_clicked"],
    )
    _render_map_legend(_score_group_map(view.cells))

    # Protección ante eventos anteriores de st_folium:
    # Solo procesar el clic si las coordenadas del evento son genuinamente nuevas.
    raw_click = event.get("last_clicked") if isinstance(event, dict) else None
    if raw_click is not None:
        last_processed = st.session_state.get(_SESSION_LAST_PROCESSED_CLICK)
        if raw_click != last_processed:
            st.session_state[_SESSION_LAST_PROCESSED_CLICK] = raw_click
            return cell_from_click(event)
    return None


def _render_priority_panel(view: RankingView) -> None:
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
        '<div class="sapi-v2-panel"><div class="sapi-v2-panel__h">Grupo prioritario</div>'
        f'<div class="sapi-v2-prio-num">#{top[0].display_rank}</div>'
        f'<div style="margin-top:0.35rem;font-size:0.9rem"><b>{len(top)} celdas</b> empatadas<br>'
        f'Score relativo: <b style="font-variant-numeric:tabular-nums">{top[0].score:.6f}</b></div>'
        f'<div style="margin-top:0.65rem">{chips}</div>{tie_note}</div>',
        unsafe_allow_html=True,
    )


def _render_selected_panel(
    view: RankingView,
    cell_id: str,
    topography: Optional[Mapping[str, CellTopography]] = None,
) -> None:
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
        meteo_rows = (
            f"<li><span>Temperatura</span><b>{m.temperatura:.1f} °C</b></li>"
            f"<li><span>Humedad</span><b>{m.humedad_relativa:.0f} %</b></li>"
            f"<li><span>Viento</span><b>{m.velocidad_viento_kmh:.1f} km/h</b></li>"
        )
    else:
        meteo_rows = (
            f"<li><span>Meteorología usada</span><b>{_esc(NOT_PROVIDED)}</b></li>"
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
    st.markdown(
        '<div class="sapi-v2-panel"><div class="sapi-v2-panel__h">Celda seleccionada</div>'
        f'<div style="font-size:1.35rem;font-weight:800">{_esc(cell.cell_id)}</div>'
        f'<div style="opacity:0.8;margin:0.2rem 0 0.65rem">Prioridad #{cell.display_rank} · '
        f'Score relativo: <b style="font-variant-numeric:tabular-nums">{cell.score:.6f}</b>'
        f"{' · empate ×' + str(cell.tie_group_size) if cell.tie_group_size > 1 else ''}</div>"
        '<div class="sapi-v2-panel__h">Territorio (referencia)</div>'
        '<ul class="sapi-v2-kv">'
        f"<li><span>Elevación</span><b>{elev}</b></li>"
        f"<li><span>Pendiente</span><b>{slope}</b></li>"
        f"<li><span>Historial FIRMS</span><b>{_esc(NOT_IN_CONTRACT)}</b></li>"
        f"</ul>{dem_note}"
        f'<div class="sapi-v2-note">{_esc(REFERENCE_TOPOGRAPHY_LABEL)}</div>'
        '<div class="sapi-v2-panel__h" style="margin-top:0.75rem">Meteorología regional</div>'
        f'<ul class="sapi-v2-kv">{meteo_rows}</ul>'
        '<div class="sapi-v2-panel__h" style="margin-top:0.75rem">Ventana</div>'
        '<ul class="sapi-v2-kv">'
        f"<li><span>T</span><b>{_human_date(view.forecast_time)} "
        f"{_human_hm(view.forecast_time)} UTC</b></li>"
        f"{window_rows}</ul></div>",
        unsafe_allow_html=True,
    )


def _cell_num(cell_id: str) -> int:
    """Extrae el número de celda ('VP-012' -> 12) para ordenación numérica."""
    try:
        return int(cell_id.split("-")[1])
    except (IndexError, ValueError):
        return 0


def _prepare_ranking_display(
    cells: tuple[RankingCell, ...],
    order_mode: Any,
    group_filter: Any,
) -> tuple[pd.DataFrame, str]:
    """Prepara el DataFrame y la leyenda explicativa para el ranking expandido.

    Asegura:
    - Conservación del contrato del backend (scores, display_rank y empates intactos).
    - Visualización predeterminada por prioridad contractual.
    - Orden numérico opcional por celda (VP-001 -> VP-050).
    - Orden numérico de identificadores dentro de empates cuando se solicite.
    - Filtro por grupo de prioridad relativa exploratoria.
    """
    group_map = _score_group_map(cells)

    # 1. Filtro por grupo de prioridad relativa
    filter_str = str(group_filter) if group_filter is not None else ""
    if filter_str.startswith("Grupo "):
        try:
            target_group = int(filter_str.split()[1])
            filtered_cells = [c for c in cells if group_map.get(c.score) == target_group]
        except (IndexError, ValueError):
            filtered_cells = list(cells)
    else:
        filtered_cells = list(cells)

    # 2. Ordenación según el criterio seleccionado
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
        # Default: orden y empates contractuales directos del backend
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


def _render_ranking_expander(
    view: RankingView, selected_id: Optional[str] = None
) -> None:
    with st.expander("Ver ranking completo", expanded=False):
        order_mode = st.radio(
            "Criterio de ordenación",
            options=[
                _ORDER_PRIORITY_OFFICIAL,
                _ORDER_PRIORITY_TIES_BY_ID,
                _ORDER_CELL_ID,
            ],
            horizontal=True,
            key="ranking_v2_order",
            help=(
                "Cambia solo el orden de presentación en esta tabla. "
                "No altera el ranking ni los scores emitidos por el backend."
            ),
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
            help="Filtra la visualización por grupo relativo de score exploratorio.",
        )

        df, note = _prepare_ranking_display(view.cells, order_mode, group_filter)

        # Detectar cambio de filtro u orden para reajustar los índices de fila
        current_filter_key = (str(order_mode), str(group_filter))
        if st.session_state.get(_SESSION_TABLE_LAST_FILTER) != current_filter_key:
            st.session_state[_SESSION_TABLE_LAST_FILTER] = current_filter_key
            st.session_state[_SESSION_TABLE_SYNCED_CELL] = None

        # Sincronización programática de la selección de tabla
        if st.session_state.get(_SESSION_TABLE_SYNCED_CELL) != selected_id:
            matching = (
                df.index[df["Celda"] == selected_id].tolist()
                if isinstance(selected_id, str) and "Celda" in df.columns
                else []
            )
            target_rows = [int(matching[0])] if matching else []
            target_cells = [[int(matching[0]), "Celda"]] if matching else []
            st.session_state[_SESSION_TABLE] = {
                "selection": {"rows": target_rows, "columns": [], "cells": target_cells}
            }
            st.session_state[_SESSION_TABLE_SYNCED_CELL] = selected_id
            st.session_state[_SESSION_TABLE_LAST_ROWS] = target_rows
            st.session_state[_SESSION_TABLE_LAST_CELLS] = target_cells

        table_event = st.dataframe(
            df,
            width="stretch",
            hide_index=True,
            height=340,
            on_select="rerun",
            selection_mode=["single-cell", "single-row"],
            key=_SESSION_TABLE,
        )

        # Procesar selección de celda o fila del usuario
        raw_cells = []
        raw_rows = []
        if isinstance(table_event, dict):
            selection_dict = table_event.get("selection", {})
            raw_cells = selection_dict.get("cells", [])
            raw_rows = selection_dict.get("rows", [])
        elif hasattr(table_event, "selection"):
            raw_cells = getattr(table_event.selection, "cells", [])
            raw_rows = getattr(table_event.selection, "rows", [])

        current_cells = [list(c) if isinstance(c, (list, tuple)) else c for c in raw_cells]
        current_rows = list(raw_rows) if isinstance(raw_rows, (list, tuple)) else []

        last_cells = st.session_state.get(_SESSION_TABLE_LAST_CELLS)
        last_rows = st.session_state.get(_SESSION_TABLE_LAST_ROWS)

        target_row_idx: Optional[int] = None

        # 1. Clic directo sobre el contenido de cualquier celda
        if current_cells != last_cells and current_cells:
            first_c = current_cells[0]
            if isinstance(first_c, (list, tuple)) and len(first_c) >= 1:
                c_idx = first_c[0]
                if isinstance(c_idx, int) and 0 <= c_idx < len(df):
                    target_row_idx = c_idx

        # 2. Clic sobre la casilla de selección de fila (checkbox izquierdo)
        if target_row_idx is None and current_rows != last_rows and current_rows:
            r_idx = current_rows[0]
            if isinstance(r_idx, int) and 0 <= r_idx < len(df):
                target_row_idx = r_idx

        # 3. Fallback de consistencia en primera interacción
        if target_row_idx is None and last_cells is None and last_rows is None:
            if current_cells:
                first_c = current_cells[0]
                if isinstance(first_c, (list, tuple)) and len(first_c) >= 1 and isinstance(first_c[0], int) and 0 <= first_c[0] < len(df):
                    target_row_idx = first_c[0]
            elif current_rows:
                r_idx = current_rows[0]
                if isinstance(r_idx, int) and 0 <= r_idx < len(df):
                    target_row_idx = r_idx

        if target_row_idx is not None:
            table_cell = str(df.iloc[target_row_idx]["Celda"])
            if isinstance(selected_id, str) and table_cell != selected_id:
                st.session_state[_SESSION_PENDING_SELECTION] = table_cell
                st.session_state[_SESSION_TABLE_SYNCED_CELL] = table_cell
                st.session_state[_SESSION_TABLE_LAST_CELLS] = current_cells
                st.session_state[_SESSION_TABLE_LAST_ROWS] = current_rows
                st.rerun()
            else:
                st.session_state[_SESSION_TABLE_LAST_CELLS] = current_cells
                st.session_state[_SESSION_TABLE_LAST_ROWS] = current_rows
        else:
            st.session_state[_SESSION_TABLE_LAST_CELLS] = current_cells
            st.session_state[_SESSION_TABLE_LAST_ROWS] = current_rows

        focus_caption = (
            f" · Celda enfocada: **{selected_id}**"
            if isinstance(selected_id, str) and selected_id
            else ""
        )
        st.caption(
            f"{note}{focus_caption} — Criterio exploratorio relativo del Modelo D "
            "(no constituye alerta ni nivel oficial de riesgo)."
        )


def _render_tech_expander(view: RankingView) -> None:
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
                "\n  *(Sincronía FIRMS evaluada respecto a fecha T; cumple umbral operacional ≤3 días)*"
                if view.firms_provenance_available and view.firms_status == "FIRMS AL DÍA"
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
    with st.expander("Información técnica y fuentes", expanded=False):
        st.markdown("\n\n".join(sections))
        st.caption(FIXED_DISCLAIMER)


def _render_backend_error(exc: BackendError) -> None:
    """Estado de error controlado (CA4): mensaje genérico, sin host ni stack."""
    st.markdown("## S.A.P.I. — PROTOTIPO EXPLORATORIO")
    st.error(f"No se pudo obtener el ranking del backend: {exc.user_message}")
    # Solo texto local. El `message` remoto no existe en BackendError y el
    # `error_type` se vuelve a filtrar contra el enum del contrato por defensa.
    if exc.error_type in KNOWN_ERROR_TYPES:
        st.caption(f"tipo reportado por el backend: `{exc.error_type}`")
    st.caption(
        "La vista consume únicamente `GET /api/v1/ranking` del backend Spring Boot "
        "(`SAPI_BACKEND_BASE_URL`). No se ejecuta inferencia local ni se muestran "
        "datos cacheados como actuales."
    )


def render_ranking_backend_dashboard() -> None:
    """Punto de entrada de la vista v2 (modo Prototipo).

    Obtiene el ranking del backend (cache de 5 min) y lo presenta. Cualquier
    `BackendError` termina en un estado de error visible y controlado.
    """
    if st.sidebar.button("Actualizar ranking", help="Vuelve a consultar al backend."):
        refresh_ranking_cache()
    try:
        view = _load_ranking()
    except BackendError as exc:
        _render_backend_error(exc)
        return

    _inject_css()
    header_col, toggle_col = st.columns([8.8, 1.2], gap="small")
    with header_col:
        _render_header(view)
    with toggle_col:
        from app.components.controls import render_appearance_toggle

        render_appearance_toggle()
    _render_freshness_state(view)
    _render_kpi_strip(view)
    _render_disclaimer(view)

    cell_ids = [c.cell_id for c in view.cells]
    pending_selected = (
        st.session_state.pop(_SESSION_PENDING_SELECTION, None)
        if hasattr(st.session_state, "pop")
        else None
    )
    if isinstance(pending_selected, str) and pending_selected in cell_ids:
        st.session_state[_SESSION_SELECTED] = pending_selected
    elif st.session_state.get(_SESSION_SELECTED) not in cell_ids:
        st.session_state[_SESSION_SELECTED] = cell_ids[0]

    map_col, side_col = st.columns([1.85, 1], gap="medium")
    with map_col:
        clicked = _render_map(view, selected_id=st.session_state.get(_SESSION_SELECTED))
        if clicked and clicked != st.session_state.get(_SESSION_SELECTED):
            st.session_state[_SESSION_SELECTED] = clicked
            st.session_state[_SESSION_TABLE_SYNCED_CELL] = None
            st.rerun()
        _render_tech_expander(view)
    with side_col:
        _render_priority_panel(view)
        selected = st.selectbox("Celda", options=cell_ids, key=_SESSION_SELECTED)
        _render_selected_panel(view, selected)
        _render_ranking_expander(view, selected_id=selected)

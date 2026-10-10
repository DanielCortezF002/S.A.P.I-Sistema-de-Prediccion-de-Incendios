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
- Lo que el contrato v0 no transporta (frescura, estación, meteorología
  usada, procedencia FIRMS, historial FIRMS por celda) se declara como
  "no informado por el backend". Nunca se deriva ni se inventa.
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
_CACHE_TTL_SECONDS = 300

# Etiqueta de frescura que el servicio de inferencia asigna a observaciones
# de más de 24 h (misma cadena que `prototype_service.FRESHNESS_HISTORICAL`).
# Solo se compara contra lo que el backend envíe; nunca se calcula aquí.
FRESHNESS_HISTORICAL_LABEL = "DATOS HISTÓRICOS / DESACTUALIZADOS"
NOT_PROVIDED = "no informado por el backend"
NOT_IN_CONTRACT = "no disponible en la respuesta del backend"
FIXED_DISCLAIMER = (
    "El score corresponde a un ranking relativo exploratorio "
    "y no a una probabilidad calibrada de incendio."
)

# Paleta por grupo de score único (misma semántica que la vista Hito 1):
# posición relativa en un ranking exploratorio, nunca alerta oficial.
_GROUP_VISUAL = {
    1: {"label": "Grupo 1", "fill": "#c45c26", "edge": "#f0a070", "op_all": 0.42, "op_prio": 0.48},
    2: {"label": "Grupo 2", "fill": "#a67c2a", "edge": "#c9a35a", "op_all": 0.20, "op_prio": 0.10},
    3: {"label": "Grupo 3", "fill": "#5a6570", "edge": "#7a8694", "op_all": 0.11, "op_prio": 0.08},
}
_SELECTED_EDGE = "#38bdf8"
_MONTHS = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")

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


def _topo_for(topography: Mapping[str, CellTopography], cell_id: str) -> tuple[str, str, bool]:
    """(elevación, pendiente, cobertura) formateados desde la tabla de referencia."""
    row = topography.get(cell_id)
    if row is None:
        return "N/D", "N/D", False
    return _fmt_nd(row.elevation, " m", 0), _fmt_nd(row.slope, "°", 1), row.dem_available


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
    center_lat, center_lon = grid_center()
    fmap = folium.Map(location=[center_lat, center_lon], zoom_start=11, tiles="OpenStreetMap")

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
            fill_opacity = max(fill_opacity, 0.35)

        elev_txt, slope_txt, _ = _topo_for(topo, c.cell_id)
        tooltip = (
            f"<b>{_esc(c.cell_id)}</b><br>"
            f"Prioridad #{c.display_rank}<br>"
            f"Score {c.score:.6f}<br><br>"
            f"Elevación {elev_txt} (ref.)<br>"
            f"Pendiente {slope_txt} (ref.)<br>"
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
def _cached_ranking(base_url: str, connect_timeout: float, read_timeout: float) -> RankingView:
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
        .sapi-v2-header { display:flex; flex-wrap:wrap; justify-content:space-between;
            gap:1rem; align-items:flex-start; margin:0 0 0.6rem 0; }
        .sapi-v2-title { font-size:1.65rem; font-weight:750; letter-spacing:-0.02em;
            line-height:1.15; margin:0; }
        .sapi-v2-sub { font-size:0.92rem; opacity:0.78; margin-top:0.2rem; max-width:36rem; }
        .sapi-v2-status { display:flex; flex-wrap:wrap; gap:0.45rem; justify-content:flex-end; }
        .sapi-v2-badge { display:inline-flex; align-items:center; padding:0.28rem 0.65rem;
            border-radius:999px; font-size:0.68rem; font-weight:700; letter-spacing:0.06em;
            text-transform:uppercase; border:1px solid rgba(127,127,127,0.35); }
        .sapi-v2-badge--violet { background:#3b2a6d; border-color:#7c3aed; color:#ede9fe; }
        .sapi-v2-badge--hist { background:#7f1d1d; border-color:#dc2626; color:#fee2e2; }
        .sapi-v2-badge--rest { background:#0f3b2e; border-color:#10b981; color:#d1fae5; }
        .sapi-v2-meta { margin-top:0.45rem; font-size:0.92rem; opacity:0.92;
            text-align:right; line-height:1.5; }
        .sapi-v2-kpi-row { display:grid; grid-template-columns:repeat(5, minmax(0, 1fr));
            gap:0.55rem; margin:0.35rem 0 0.85rem 0; }
        .sapi-v2-kpi { border:1px solid rgba(127,127,127,0.35); border-radius:10px;
            padding:0.55rem 0.7rem; min-height:4.4rem; }
        .sapi-v2-kpi__value { font-size:1.2rem; font-weight:750; letter-spacing:-0.02em;
            line-height:1.1; }
        .sapi-v2-kpi__value--na { font-size:0.82rem; font-weight:600; opacity:0.7; }
        .sapi-v2-kpi__label { font-size:0.72rem; opacity:0.7; margin-top:0.25rem; font-weight:600; }
        .sapi-v2-panel { border:1px solid rgba(127,127,127,0.35); border-radius:12px;
            padding:0.85rem 0.95rem; margin-bottom:0.75rem; }
        .sapi-v2-panel__h { font-size:0.7rem; font-weight:800; letter-spacing:0.1em;
            text-transform:uppercase; opacity:0.65; margin:0 0 0.55rem 0; }
        .sapi-v2-prio-num { font-size:2rem; font-weight:800; letter-spacing:-0.03em;
            line-height:1; color:#f0a070; }
        .sapi-v2-chip { display:inline-block; padding:0.22rem 0.5rem; margin:0.18rem 0.18rem 0 0;
            border-radius:6px; border:1px solid rgba(127,127,127,0.45); font-size:0.78rem;
            font-weight:650; font-variant-numeric:tabular-nums; }
        .sapi-v2-kv { list-style:none; padding:0; margin:0; }
        .sapi-v2-kv li { display:flex; justify-content:space-between; gap:0.75rem;
            padding:0.28rem 0; border-bottom:1px solid rgba(127,127,127,0.2); font-size:0.84rem; }
        .sapi-v2-kv li:last-child { border-bottom:none; }
        .sapi-v2-kv span { opacity:0.65; }
        .sapi-v2-legend { position:relative; z-index:2; margin:-0.35rem 0 0.5rem 0;
            border:1px solid rgba(127,127,127,0.35); border-radius:10px; padding:0.55rem 0.75rem;
            max-width:18rem; font-size:0.75rem; }
        .sapi-v2-legend__title { font-weight:800; letter-spacing:0.08em; text-transform:uppercase;
            font-size:0.68rem; opacity:0.7; margin-bottom:0.35rem; }
        .sapi-v2-legend__row { display:flex; align-items:center; gap:0.45rem; margin:0.18rem 0; }
        .sapi-v2-dot { width:10px; height:10px; border-radius:50%; display:inline-block;
            border:1px solid rgba(127,127,127,0.5); }
        .sapi-v2-disclaimer { font-size:0.75rem; opacity:0.72; margin:0.5rem 0 0 0; }
        .sapi-v2-note { font-size:0.75rem; opacity:0.7; margin-top:0.35rem; }
        @media (max-width:1100px) {
            .sapi-v2-kpi-row { grid-template-columns:repeat(3, minmax(0, 1fr)); }
        }
        @media (max-width:700px) {
            .sapi-v2-kpi-row { grid-template-columns:repeat(2, minmax(0, 1fr)); }
            .sapi-v2-meta { text-align:left; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_header(view: RankingView) -> None:
    date_line = _human_date(view.forecast_time)
    window_end = view.window_end
    window_line = (
        f"{_human_hm(view.forecast_time)} → {_human_hm(window_end)} UTC"
        if window_end is not None
        else f"{_human_hm(view.forecast_time)} UTC · horizonte {NOT_PROVIDED}"
    )
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
        '<div class="sapi-v2-sub">Sistema de Alerta y Priorización de Riesgo de Incendios</div>'
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
            "Frescura de la observación meteorológica: no informada por el backend "
            "(contrato v0; la extensión aditiva está pendiente). "
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
    cls = "sapi-v2-kpi__value" if available else "sapi-v2-kpi__value sapi-v2-kpi__value--na"
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
    st.markdown(f'<div class="sapi-v2-kpi-row">{"".join(cards)}</div>', unsafe_allow_html=True)


def _render_disclaimer(view: RankingView) -> None:
    text = view.disclaimer.strip() if view.disclaimer and view.disclaimer.strip() else None
    st.markdown(
        f'<p class="sapi-v2-disclaimer">{_esc(text or FIXED_DISCLAIMER)}</p>',
        unsafe_allow_html=True,
    )
    if text and FIXED_DISCLAIMER not in text:
        st.markdown(f'<p class="sapi-v2-disclaimer">{FIXED_DISCLAIMER}</p>', unsafe_allow_html=True)


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
        '<div class="sapi-v2-legend"><div class="sapi-v2-legend__title">Prioridad relativa</div>'
        f'{"".join(rows)}'
        '<div style="margin-top:0.4rem;opacity:0.7;line-height:1.35">Basado en score relativo.'
        "<br>No representa niveles oficiales de alerta.</div></div>",
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
    event = st_folium(
        fmap,
        height=560,
        use_container_width=True,
        key="ranking_v2_map",
        returned_objects=["last_clicked"],
    )
    _render_map_legend(_score_group_map(view.cells))
    return cell_from_click(event)


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
        '<div class="sapi-v2-note">Sin cobertura DEM de referencia en esta celda</div>'
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
        meteo_rows = f"<li><span>Meteorología usada</span><b>{_esc(NOT_PROVIDED)}</b></li>"
    window_end = view.window_end
    if window_end is not None:
        window_rows = (
            f"<li><span>T+{view.horizon_hours}h</span><b>{_human_date(window_end)} "
            f"{_human_hm(window_end)} UTC</b></li>"
        )
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


def _render_ranking_expander(view: RankingView) -> None:
    with st.expander("Ver ranking completo", expanded=False):
        df = pd.DataFrame(
            [
                {
                    "Prioridad": c.display_rank,
                    "Celda": c.cell_id,
                    "Score relativo": round(c.score, 6),
                    "Empate": f"×{c.tie_group_size}" if c.tie_group_size > 1 else "—",
                }
                for c in view.cells
            ]
        )
        st.dataframe(df, width="stretch", hide_index=True, height=320)
        st.caption(
            "Orden y empates tal como los emitió el backend: celdas con score idéntico "
            "comparten el mismo número de prioridad."
        )


def _render_tech_expander(view: RankingView) -> None:
    window_end = view.window_end
    station = f"{view.station_name} {view.station_id}" if view.station_available else NOT_PROVIDED
    lines = [
        f"- **Origen del ranking:** backend Spring Boot, `GET {RANKING_PATH}` "
        f"(obtenido {_iso_utc(view.fetched_at)}; cache de {_CACHE_TTL_SECONDS // 60} min)",
        f"- **Schema:** `{view.schema_version}` · semántica `{view.score_semantics}` · "
        f"validación científica: `{str(view.scientific_model_validation).lower()}`",
        f"- **Modelo:** {view.model_version} — **{view.model_status or NOT_PROVIDED}**",
        f"- **Inputs fingerprint:** `{view.inputs_fingerprint}`",
        f"- **Forecast time:** {_iso_utc(view.forecast_time)}",
        (
            f"- **Ventana evaluada:** {_iso_utc(view.forecast_time)} → {_iso_utc(window_end)} "
            f"(h={view.horizon_hours}h)"
            if window_end is not None
            else f"- **Ventana evaluada:** horizonte {NOT_PROVIDED}"
        ),
        f"- **Estación DMC:** {station}",
        (
            f"- **Weather timestamp usado:** {_iso_utc(view.weather_timestamp)}"
            if view.weather_timestamp is not None
            else f"- **Weather timestamp usado:** {NOT_PROVIDED}"
        ),
        (
            f"- **Antigüedad de la observación (al evaluar):** {view.age_hours:.1f} h — "
            f"**{view.freshness}**"
            if view.freshness_available
            else f"- **Antigüedad / frescura de la observación:** {NOT_PROVIDED}"
        ),
        "- **Fuente de detecciones:** NASA FIRMS",
        (
            "- **Procedencia FIRMS:** "
            f"origen {view.firms_origin or NOT_PROVIDED} · cobertura hasta "
            f"{view.firms_coverage_end.isoformat() if view.firms_coverage_end else NOT_PROVIDED}"
            f" · lag {view.firms_lag_days if view.firms_lag_days is not None else NOT_PROVIDED}"
            f" · estado {view.firms_status or NOT_PROVIDED}"
            if view.firms_provenance_available
            else f"- **Procedencia FIRMS:** {NOT_PROVIDED}"
        ),
        f"- **Topografía:** {REFERENCE_TOPOGRAPHY_LABEL}",
    ]
    missing = view.missing_additive_fields
    if missing:
        lines.append(
            "- **Metadata pendiente de la extensión aditiva del contrato:** "
            + ", ".join(f"`{name}`" for name in missing)
        )
    with st.expander("Información técnica y fuentes", expanded=False):
        st.markdown("\n".join(lines))
        st.caption(FIXED_DISCLAIMER)


def _render_backend_error(exc: BackendError) -> None:
    """Estado de error controlado (CA4): mensaje genérico, sin host ni stack."""
    st.markdown("## S.A.P.I. — PROTOTIPO EXPLORATORIO")
    st.error(f"No se pudo obtener el ranking del backend: {exc.user_message}")
    details = []
    if exc.error_type:
        details.append(f"tipo reportado por el backend: `{exc.error_type}`")
    if exc.backend_message:
        details.append(f"mensaje del backend: {exc.backend_message}")
    if details:
        st.caption(" · ".join(details))
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
    _render_header(view)
    _render_freshness_state(view)
    _render_kpi_strip(view)
    _render_disclaimer(view)

    cell_ids = [c.cell_id for c in view.cells]
    if st.session_state.get(_SESSION_SELECTED) not in cell_ids:
        st.session_state[_SESSION_SELECTED] = cell_ids[0]

    map_col, side_col = st.columns([2.1, 1], gap="large")
    with map_col:
        clicked = _render_map(view, selected_id=st.session_state.get(_SESSION_SELECTED))
        if clicked and clicked != st.session_state.get(_SESSION_SELECTED):
            st.session_state[_SESSION_SELECTED] = clicked
            st.rerun()
    with side_col:
        _render_priority_panel(view)
        selected = st.selectbox("Celda", options=cell_ids, key=_SESSION_SELECTED)
        _render_selected_panel(view, selected)
        _render_ranking_expander(view)

    _render_tech_expander(view)

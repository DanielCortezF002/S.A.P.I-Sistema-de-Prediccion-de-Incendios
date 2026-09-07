"""Vista PROTOTIPO / DATOS REALES del dashboard S.A.P.I.

Usa EXCLUSIVAMENTE `src.inference.prototype_service.score_current_grid`
(pipeline temporal nuevo: regional_meteo + episodes + dem_features +
Modelo D). Nunca importa nada del generador de datos sintéticos de la UI
ni del pipeline legacy — es un módulo separado a propósito, para que
DEMO y PROTOTIPO nunca se mezclen en el mismo código.

Rediseño visual (2026-09-07): capa de presentación únicamente. No altera
scores, ranks, empates, meteorología ni inferencia.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from src.inference.prototype_service import (
    FRESHNESS_HISTORICAL,
    GridScoreResult,
    PrototypeUnavailableError,
    score_current_grid,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_METADATA_PATH = _REPO_ROOT / "models" / "prototype_model_d_metadata.json"

_MAP_MODE_PRIORIDADES = "Prioridades"
_MAP_MODE_TODAS = "Todas las celdas"
_SESSION_MAP_MODE = "proto_map_mode"
_SESSION_SELECTED = "proto_selected_cell"

# Tres grupos reales de score único (no degradado continuo).
# Colores = posición relativa en ranking exploratorio — nunca alerta oficial.
_GROUP_VISUAL = {
    1: {
        "label": "Grupo 1",
        "fill": "#c45c26",
        "edge": "#f0a070",
        "swatch": "#c45c26",
        "op_all": 0.42,
        "op_prio": 0.48,
        "w_all": 1.5,
        "w_prio": 1.5,
    },
    2: {
        "label": "Grupo 2",
        "fill": "#a67c2a",
        "edge": "#c9a35a",
        "swatch": "#a67c2a",
        "op_all": 0.20,
        "op_prio": 0.10,
        "w_all": 0.8,
        "w_prio": 0.5,
    },
    3: {
        "label": "Grupo 3",
        "fill": "#5a6570",
        "edge": "#7a8694",
        "swatch": "#5a6570",
        "op_all": 0.11,
        "op_prio": 0.08,
        "w_all": 0.5,
        "w_prio": 0.5,
    },
}

_SELECTED_EDGE = "#38bdf8"


@st.cache_data(ttl=300, show_spinner="Calculando ranking de riesgo exploratorio...")
def _cached_score_current_grid() -> GridScoreResult:
    """Cache de 5 min: evita recalcular episodios/DEM en cada rerun de
    Streamlit, sin dejar el ranking desactualizado por horas."""
    return score_current_grid()


def _fmt_nd(value: Optional[float], unit: str = "", decimals: int = 0) -> str:
    """Formatea DEM/numéricos: NaN/None → N/D (nunca 0 inventado)."""
    if value is None:
        return "N/D"
    try:
        if pd.isna(value):
            return "N/D"
    except (TypeError, ValueError):
        pass
    if decimals <= 0:
        return f"{float(value):.0f}{unit}"
    return f"{float(value):.{decimals}f}{unit}"


def _score_group_map(cells: list) -> dict[float, int]:
    """Mapea cada score único → Grupo 1..K (1 = mayor score relativo)."""
    unique = sorted({float(c.score) for c in cells}, reverse=True)
    return {s: i + 1 for i, s in enumerate(unique)}


def _group_of(cell: Any, group_by_score: dict[float, int]) -> int:
    return int(group_by_score[float(cell.score)])


def _priority_group(cells: list) -> list:
    """Celdas del display_rank mínimo (grupo prioritario real, con empates)."""
    if not cells:
        return []
    top_rank = min(c.display_rank for c in cells)
    return [c for c in cells if c.display_rank == top_rank]


def _human_date(ts: pd.Timestamp) -> str:
    months = (
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
    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        t = t.tz_localize("UTC")
    else:
        t = t.tz_convert("UTC")
    return f"{t.day:02d} {months[t.month - 1]} {t.year}"


def _human_hm(ts: pd.Timestamp) -> str:
    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        t = t.tz_localize("UTC")
    else:
        t = t.tz_convert("UTC")
    return t.strftime("%H:%M")


def _inject_prototype_css() -> None:
    st.markdown(
        """
        <style>
        .sapi-proto-wrap { font-family: "IBM Plex Sans", "Segoe UI", sans-serif; color: #e8edf2; }
        .sapi-proto-header {
            display: flex; flex-wrap: wrap; justify-content: space-between;
            gap: 1rem; align-items: flex-start; margin: 0 0 0.75rem 0;
        }
        .sapi-proto-title {
            font-size: 1.65rem; font-weight: 750; letter-spacing: -0.02em;
            line-height: 1.15; margin: 0; color: #f4f7fa;
        }
        .sapi-proto-sub {
            font-size: 0.92rem; opacity: 0.78; margin-top: 0.2rem; max-width: 36rem;
        }
        .sapi-proto-status { display: flex; flex-wrap: wrap; gap: 0.45rem; justify-content: flex-end; }
        .sapi-proto-badge {
            display: inline-flex; align-items: center; padding: 0.28rem 0.65rem;
            border-radius: 999px; font-size: 0.68rem; font-weight: 700;
            letter-spacing: 0.06em; text-transform: uppercase;
            border: 1px solid rgba(255,255,255,0.14); background: #1c2430;
        }
        .sapi-proto-badge--violet { background: #3b2a6d; border-color: #7c3aed; color: #ede9fe; }
        .sapi-proto-badge--hist {
            background: #7f1d1d; border-color: #dc2626; color: #fee2e2;
        }
        .sapi-proto-meta {
            margin-top: 0.45rem; font-size: 0.82rem; opacity: 0.82;
            text-align: right; line-height: 1.45;
        }
        .sapi-proto-kpi-row {
            display: grid; grid-template-columns: repeat(5, minmax(0, 1fr));
            gap: 0.55rem; margin: 0.35rem 0 0.85rem 0;
        }
        .sapi-proto-kpi {
            background: #1a222d; border: 1px solid #2c3644; border-radius: 10px;
            padding: 0.55rem 0.7rem; min-height: 4.4rem;
        }
        .sapi-proto-kpi__value {
            font-size: 1.35rem; font-weight: 750; letter-spacing: -0.02em;
            color: #f5f8fb; line-height: 1.1;
        }
        .sapi-proto-kpi__label {
            font-size: 0.72rem; opacity: 0.7; margin-top: 0.25rem; font-weight: 600;
        }
        .sapi-proto-panel {
            background: #161d27; border: 1px solid #2a3442; border-radius: 12px;
            padding: 0.85rem 0.95rem; margin-bottom: 0.75rem;
        }
        .sapi-proto-panel__h {
            font-size: 0.7rem; font-weight: 800; letter-spacing: 0.1em;
            text-transform: uppercase; opacity: 0.65; margin: 0 0 0.55rem 0;
        }
        .sapi-proto-prio-num {
            font-size: 2rem; font-weight: 800; letter-spacing: -0.03em; line-height: 1;
            color: #f0a070;
        }
        .sapi-proto-cell-chip {
            display: inline-block; padding: 0.22rem 0.5rem; margin: 0.18rem 0.18rem 0 0;
            border-radius: 6px; background: #243041; border: 1px solid #3a4a5c;
            font-size: 0.78rem; font-weight: 650; font-variant-numeric: tabular-nums;
        }
        .sapi-proto-kv { list-style: none; padding: 0; margin: 0; }
        .sapi-proto-kv li {
            display: flex; justify-content: space-between; gap: 0.75rem;
            padding: 0.28rem 0; border-bottom: 1px solid rgba(255,255,255,0.06);
            font-size: 0.84rem;
        }
        .sapi-proto-kv li:last-child { border-bottom: none; }
        .sapi-proto-kv span { opacity: 0.65; }
        .sapi-proto-legend {
            position: relative; z-index: 2; margin: -0.35rem 0 0.5rem 0;
            background: rgba(18, 24, 32, 0.92); border: 1px solid #2c3644;
            border-radius: 10px; padding: 0.55rem 0.75rem; max-width: 18rem;
            font-size: 0.75rem;
        }
        .sapi-proto-legend__title {
            font-weight: 800; letter-spacing: 0.08em; text-transform: uppercase;
            font-size: 0.68rem; opacity: 0.7; margin-bottom: 0.35rem;
        }
        .sapi-proto-legend__row { display: flex; align-items: center; gap: 0.45rem; margin: 0.18rem 0; }
        .sapi-proto-dot {
            width: 10px; height: 10px; border-radius: 50%; display: inline-block;
            border: 1px solid rgba(255,255,255,0.25);
        }
        .sapi-proto-disclaimer {
            font-size: 0.75rem; opacity: 0.72; margin: 0.5rem 0 0 0;
        }
        /* Contraste del selector Prioridades | Todas las celdas (dark mode). */
        section.main [data-testid="stRadio"] label,
        section.main [data-testid="stRadio"] p,
        section.main [data-testid="stRadio"] span,
        section.main [data-testid="stWidgetLabel"] p,
        section.main [data-baseweb="radio"] {
            color: #e8edf2 !important;
            opacity: 1 !important;
            -webkit-text-fill-color: #e8edf2 !important;
        }
        @media (max-width: 1100px) {
            .sapi-proto-kpi-row { grid-template-columns: repeat(3, minmax(0, 1fr)); }
        }
        @media (max-width: 700px) {
            .sapi-proto-kpi-row { grid-template-columns: repeat(2, minmax(0, 1fr)); }
            .sapi-proto-meta { text-align: left; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _score_to_color(rank: int, n_cells: int) -> str:
    """Compatibilidad: degradado legacy por rank (tests de import / legado).

    El mapa rediseñado usa `_GROUP_VISUAL` (3 scores únicos), no este
    degradado continuo — se conserva solo para no romper imports externos.
    """
    fraction = (rank - 1) / max(n_cells - 1, 1)
    red = int(255 * (1 - fraction))
    green = int(255 * fraction)
    return f"#{red:02x}{green:02x}40"


def _render_stale_data_banner(result: GridScoreResult) -> None:
    """Corrección UX/semántica (2026-09-07): si la meteorología real usada
    tiene más de 24h de antigüedad respecto al momento en que se abre el
    dashboard, la UI debe decirlo explícitamente — nunca insinuar que el
    ranking es un pronóstico vigente de "las próximas 6 horas de hoy"."""
    if result.freshness != FRESHNESS_HISTORICAL:
        return
    st.warning(
        f"⚠ DATOS HISTÓRICOS · última observación hace {result.age_hours:.0f} h\n\n"
        "El ranking corresponde al instante indicado "
        "y NO representa el riesgo actual."
    )


def _render_header(result: GridScoreResult) -> None:
    window_end = result.forecast_time + pd.Timedelta(hours=result.horizon_hours)
    date_line = _human_date(result.forecast_time)
    window_line = (
        f"{_human_hm(result.forecast_time)} → {_human_hm(window_end)} UTC"
    )
    station_line = f"DMC {result.station_name} · {result.station_id}"

    hist_badge = (
        '<span class="sapi-proto-badge sapi-proto-badge--hist">DATOS HISTÓRICOS</span>'
        if result.freshness == FRESHNESS_HISTORICAL
        else ""
    )
    st.markdown(
        f'<div class="sapi-proto-wrap sapi-proto-header">'
        f"<div>"
        f'<div class="sapi-proto-title">S.A.P.I.</div>'
        f'<div class="sapi-proto-sub">Sistema de Alerta y Priorización de '
        f"Riesgo de Incendios</div>"
        f"</div>"
        f'<div class="sapi-proto-status">'
        f'<span class="sapi-proto-badge sapi-proto-badge--violet">'
        f"PROTOTIPO EXPLORATORIO</span>"
        f"{hist_badge}"
        f"</div></div>"
        f'<div class="sapi-proto-meta">{date_line}<br>{window_line}<br>'
        f"{station_line}</div>",
        unsafe_allow_html=True,
    )


def _render_kpi_strip(result: GridScoreResult) -> None:
    m = result.meteo_actual
    regla = "Activa" if m["regla_30_30_30"] else "Inactiva"
    cards = [
        (f"{m['temperatura']:.1f} °C", "Temperatura"),
        (f"{m['humedad_relativa']:.0f} %", "Humedad"),
        (f"{m['velocidad_viento_kmh']:.1f} km/h", "Viento"),
        (regla, "Regla 30-30-30"),
        (str(len(result.cells)), "Celdas evaluadas"),
    ]
    html = ['<div class="sapi-proto-kpi-row">']
    for value, label in cards:
        html.append(
            f'<div class="sapi-proto-kpi">'
            f'<div class="sapi-proto-kpi__value">{value}</div>'
            f'<div class="sapi-proto-kpi__label">{label}</div>'
            f"</div>"
        )
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)


def _cell_contains(cell: Any, lat: float, lon: float) -> bool:
    g = cell.geometry
    return (
        g["min_lat"] <= lat <= g["max_lat"]
        and g["min_lon"] <= lon <= g["max_lon"]
    )


def _render_map_legend(group_by_score: dict[float, int]) -> None:
    groups = sorted(set(group_by_score.values()))
    rows = []
    for g in groups:
        vis = _GROUP_VISUAL.get(g, _GROUP_VISUAL[3])
        rows.append(
            f'<div class="sapi-proto-legend__row">'
            f'<span class="sapi-proto-dot" style="background:{vis["swatch"]}"></span>'
            f'{vis["label"]}</div>'
        )
    st.markdown(
        f'<div class="sapi-proto-legend">'
        f'<div class="sapi-proto-legend__title">Prioridad relativa</div>'
        f'{"".join(rows)}'
        f'<div style="margin-top:0.4rem;opacity:0.7;line-height:1.35">'
        f"Basado en score relativo.<br>"
        f"No representa niveles oficiales de alerta.</div></div>",
        unsafe_allow_html=True,
    )


def _render_map(result: GridScoreResult, selected_id: Optional[str]) -> Optional[str]:
    """Mapa protagonista. Devuelve cell_id si hubo click útil."""
    group_by_score = _score_group_map(result.cells)
    top_rank = min((c.display_rank for c in result.cells), default=1)

    mode = st.radio(
        "Vista del mapa",
        options=[_MAP_MODE_PRIORIDADES, _MAP_MODE_TODAS],
        horizontal=True,
        key=_SESSION_MAP_MODE,
        help="Solo cambia la representación visual. No recalcula inferencia.",
    )

    lats = [c.geometry["min_lat"] for c in result.cells] + [
        c.geometry["max_lat"] for c in result.cells
    ]
    lons = [c.geometry["min_lon"] for c in result.cells] + [
        c.geometry["max_lon"] for c in result.cells
    ]
    center = [sum(lats) / len(lats), sum(lons) / len(lons)]

    # OpenStreetMap estándar — sin API key (regresión auditada 2026-09-07).
    fmap = folium.Map(location=center, zoom_start=11, tiles="OpenStreetMap")

    for c in result.cells:
        g = c.geometry
        group = _group_of(c, group_by_score)
        vis = _GROUP_VISUAL.get(group, _GROUP_VISUAL[3])
        is_priority = c.display_rank == top_rank
        is_selected = selected_id is not None and c.cell_id == selected_id

        if mode == _MAP_MODE_PRIORIDADES:
            fill_opacity = vis["op_prio"] if is_priority else 0.08
            weight = vis["w_prio"] if is_priority else 0.5
            fill = vis["fill"] if is_priority else "#6b7280"
            edge = vis["edge"] if is_priority else "#6b7280"
        else:
            fill_opacity = vis["op_all"]
            weight = vis["w_all"]
            fill = vis["fill"]
            edge = vis["edge"]

        if is_selected:
            edge = _SELECTED_EDGE
            weight = 3.0
            fill_opacity = max(fill_opacity, 0.35)

        elev_txt = _fmt_nd(c.elevation, " m", 0)
        slope_txt = _fmt_nd(c.slope, "°", 1)
        tooltip = (
            f"<b>{c.cell_id}</b><br>"
            f"Prioridad #{c.display_rank}<br>"
            f"Score {c.score:.6f}<br><br>"
            f"Elevación {elev_txt}<br>"
            f"Pendiente {slope_txt}<br>"
            f"Historial FIRMS {c.historical_count}"
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

    event = st_folium(
        fmap,
        height=560,
        use_container_width=True,
        key="prototype_map",
        returned_objects=["last_clicked"],
    )
    _render_map_legend(group_by_score)

    clicked = None
    if isinstance(event, dict):
        last = event.get("last_clicked")
        if isinstance(last, dict) and "lat" in last and "lng" in last:
            lat, lon = float(last["lat"]), float(last["lng"])
            for c in result.cells:
                if _cell_contains(c, lat, lon):
                    clicked = c.cell_id
                    break
    return clicked


def _render_priority_panel(result: GridScoreResult) -> None:
    top = _priority_group(result.cells)
    if not top:
        st.info("Sin celdas en el ranking.")
        return
    score = top[0].score
    rank = top[0].display_rank
    chips = "".join(f'<span class="sapi-proto-cell-chip">{c.cell_id}</span>' for c in top)
    tie_note = (
        f'<div style="margin-top:0.55rem;font-size:0.78rem;opacity:0.75">'
        f"Empate real del modelo · {top[0].tie_group_size} celdas con score idéntico"
        f"</div>"
        if top[0].tie_group_size > 1
        else ""
    )
    st.markdown(
        f'<div class="sapi-proto-panel">'
        f'<div class="sapi-proto-panel__h">Grupo prioritario</div>'
        f'<div class="sapi-proto-prio-num">#{rank}</div>'
        f'<div style="margin-top:0.35rem;font-size:0.9rem">'
        f"<b>{len(top)} celdas</b> empatadas<br>"
        f'Score relativo: <b style="font-variant-numeric:tabular-nums">'
        f"{score:.6f}</b></div>"
        f'<div style="margin-top:0.65rem">{chips}</div>'
        f"{tie_note}</div>",
        unsafe_allow_html=True,
    )


def _render_selected_panel(result: GridScoreResult, cell_id: str) -> None:
    cell = next((c for c in result.cells if c.cell_id == cell_id), None)
    if cell is None:
        st.warning("Celda no encontrada en el ranking actual.")
        return
    m = result.meteo_actual
    window_end = result.forecast_time + pd.Timedelta(hours=result.horizon_hours)
    elev = _fmt_nd(cell.elevation, " m", 0)
    slope = _fmt_nd(cell.slope, "°", 1)
    dem_note = ""
    if elev == "N/D" or slope == "N/D":
        dem_note = (
            '<div style="font-size:0.75rem;opacity:0.7;margin-top:0.35rem">'
            "Sin cobertura DEM en esta celda</div>"
        )
    st.markdown(
        f'<div class="sapi-proto-panel">'
        f'<div class="sapi-proto-panel__h">Celda seleccionada</div>'
        f'<div style="font-size:1.35rem;font-weight:800">{cell.cell_id}</div>'
        f'<div style="opacity:0.8;margin:0.2rem 0 0.65rem">'
        f"Prioridad #{cell.display_rank} · Score relativo: "
        f"<b style=\"font-variant-numeric:tabular-nums\">{cell.score:.6f}</b>"
        f"</div>"
        f'<div class="sapi-proto-panel__h">Territorio</div>'
        f'<ul class="sapi-proto-kv">'
        f"<li><span>Elevación</span><b>{elev}</b></li>"
        f"<li><span>Pendiente</span><b>{slope}</b></li>"
        f"<li><span>Historial FIRMS</span><b>{cell.historical_count}</b></li>"
        f"</ul>{dem_note}"
        f'<div class="sapi-proto-panel__h" style="margin-top:0.75rem">'
        f"Meteorología regional</div>"
        f'<ul class="sapi-proto-kv">'
        f"<li><span>Temperatura</span><b>{m['temperatura']:.1f} °C</b></li>"
        f"<li><span>Humedad</span><b>{m['humedad_relativa']:.0f} %</b></li>"
        f"<li><span>Viento</span><b>{m['velocidad_viento_kmh']:.1f} km/h</b></li>"
        f"</ul>"
        f'<div class="sapi-proto-panel__h" style="margin-top:0.75rem">Ventana</div>'
        f'<ul class="sapi-proto-kv">'
        f"<li><span>T</span><b>{_human_date(result.forecast_time)} "
        f"{_human_hm(result.forecast_time)} UTC</b></li>"
        f"<li><span>T+{result.horizon_hours}h</span><b>"
        f"{_human_date(window_end)} {_human_hm(window_end)} UTC</b></li>"
        f"</ul></div>",
        unsafe_allow_html=True,
    )


def _render_ranking_expander(result: GridScoreResult) -> None:
    with st.expander("Ver ranking completo", expanded=False):
        df = pd.DataFrame(
            [
                {
                    "Prioridad": c.display_rank,
                    "Celda": c.cell_id,
                    "Score relativo": round(c.score, 6),
                    "Empate": f"×{c.tie_group_size}" if c.tie_group_size > 1 else "—",
                }
                for c in result.cells
            ]
        )
        st.dataframe(df, use_container_width=True, hide_index=True, height=320)
        st.caption(
            "La prioridad es honesta ante empates: celdas con score idéntico "
            "comparten el mismo número. Empate indica cuántas celdas comparten "
            "ese score exacto."
        )


def _dataset_hash_from_metadata() -> str:
    if not _METADATA_PATH.exists():
        return "no disponible"
    try:
        meta = json.loads(_METADATA_PATH.read_text(encoding="utf-8"))
        return str(meta.get("dataset_hash", "no disponible"))
    except (OSError, json.JSONDecodeError):
        return "no disponible"


def _render_tech_expander(result: GridScoreResult) -> None:
    window_end = result.forecast_time + pd.Timedelta(hours=result.horizon_hours)
    with st.expander("Información técnica y fuentes", expanded=False):
        st.markdown(
            f"- **Fuente meteorológica:** DMC {result.station_id} ({result.station_name})\n"
            "- **Fuente de detecciones:** NASA FIRMS\n"
            "- **Topografía:** DEM (Copernicus GLO-30)\n"
            f"- **Dataset:** temporal h={result.horizon_hours}h\n"
            f"- **Modelo:** {result.model_version} — **{result.model_status}**\n"
            f"- **Forecast time:** {result.forecast_time}\n"
            f"- **Ventana evaluada:** {result.forecast_time} → {window_end}\n"
            f"- **Estación DMC:** {result.station_name} {result.station_id}\n"
            f"- **Weather timestamp usado:** {result.weather_timestamp}\n"
            f"- **Dataset hash:** `{_dataset_hash_from_metadata()}`\n"
            f"- **Antigüedad de la observación:** {result.age_hours:.1f} h — "
            f"**{result.freshness}**"
        )
        st.caption(
            "El score corresponde a un ranking relativo exploratorio "
            "y no a una probabilidad calibrada de incendio."
        )


def render_prototype_dashboard() -> None:
    """Punto de entrada de la vista de datos reales. Captura
    `PrototypeUnavailableError` y muestra un mensaje claro — nunca deja
    pasar un stacktrace al usuario."""
    try:
        result = _cached_score_current_grid()
    except PrototypeUnavailableError as exc:
        st.markdown("## S.A.P.I. — PROTOTIPO EXPLORATORIO")
        st.error(f"No se pudo generar el ranking: {exc}")
        st.caption(
            "Revisa que existan: el modelo del prototipo "
            "(`python scripts/build_prototype_model.py`), el dataset temporal "
            "(`python scripts/build_temporal_dataset.py`), meteorología DMC "
            "reciente en `data/raw/`, y el histórico FIRMS."
        )
        return

    _inject_prototype_css()
    _render_header(result)
    _render_stale_data_banner(result)
    _render_kpi_strip(result)

    st.markdown(
        '<p class="sapi-proto-disclaimer">El score corresponde a un ranking '
        "relativo exploratorio y no a una probabilidad calibrada de incendio.</p>",
        unsafe_allow_html=True,
    )

    cell_ids = [c.cell_id for c in result.cells]
    if cell_ids and st.session_state.get(_SESSION_SELECTED) not in cell_ids:
        st.session_state[_SESSION_SELECTED] = cell_ids[0]

    map_col, side_col = st.columns([2.1, 1], gap="large")

    with map_col:
        clicked = _render_map(
            result,
            selected_id=st.session_state.get(_SESSION_SELECTED),
        )
        if clicked and clicked != st.session_state.get(_SESSION_SELECTED):
            st.session_state[_SESSION_SELECTED] = clicked
            st.rerun()

    with side_col:
        _render_priority_panel(result)
        selected = st.selectbox(
            "Celda",
            options=cell_ids,
            key=_SESSION_SELECTED,
        )
        _render_selected_panel(result, selected)
        _render_ranking_expander(result)

    _render_tech_expander(result)

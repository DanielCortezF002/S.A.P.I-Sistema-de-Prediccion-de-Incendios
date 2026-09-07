"""Vista PROTOTIPO / DATOS REALES del dashboard S.A.P.I.

Usa EXCLUSIVAMENTE `src.inference.prototype_service.score_current_grid`
(pipeline temporal nuevo: regional_meteo + episodes + dem_features +
Modelo D). Nunca importa nada del generador de datos sintéticos de la UI
ni del pipeline legacy — es un módulo separado a propósito, para que
DEMO y PROTOTIPO nunca se mezclen en el mismo código.
"""

from __future__ import annotations

import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from app.state import appearance
from src.inference.prototype_service import (
    FRESHNESS_DELAYED,
    FRESHNESS_HISTORICAL,
    FRESHNESS_RECENT,
    GridScoreResult,
    PrototypeUnavailableError,
    score_current_grid,
)

_TOP_N_PRIORITY = 5
_FRESHNESS_BADGE_COLOR = {
    FRESHNESS_RECENT: "#16a34a",
    FRESHNESS_DELAYED: "#d97706",
    FRESHNESS_HISTORICAL: "#dc2626",
}


@st.cache_data(ttl=300, show_spinner="Calculando ranking de riesgo exploratorio...")
def _cached_score_current_grid() -> GridScoreResult:
    """Cache de 5 min: evita recalcular episodios/DEM en cada rerun de
    Streamlit, sin dejar el ranking desactualizado por horas."""
    return score_current_grid()


def _score_to_color(rank: int, n_cells: int) -> str:
    """Verde (bajo riesgo relativo) -> rojo (alto riesgo relativo), por
    RANK (no por score crudo): con pocos positivos históricos,
    predict_proba devuelve valores muy juntos entre sí — colorear por rank
    da una lectura visual honesta de "orden relativo", que es exactamente
    lo que este prototipo puede afirmar (ver Score relativo de riesgo
    exploratorio, nunca probabilidad calibrada)."""
    fraction = (rank - 1) / max(n_cells - 1, 1)  # 0.0 = rank 1 (peor), 1.0 = rank N (mejor)
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
        "⚠ DATOS HISTÓRICOS\n\n"
        "Última observación meteorológica disponible: "
        f"{result.weather_timestamp.strftime('%d/%m/%Y %H:%M UTC')} "
        f"({result.age_hours:.0f} horas atrás).\n\n"
        "El ranking mostrado corresponde a ese instante histórico y NO "
        "representa el riesgo actual."
    )


def _render_freshness_badge(result: GridScoreResult) -> None:
    color = _FRESHNESS_BADGE_COLOR[result.freshness]
    st.markdown(
        f'<span style="background:{color};color:white;padding:2px 8px;'
        f'border-radius:6px;font-weight:600;font-size:0.75rem;">'
        f"{result.freshness}</span>",
        unsafe_allow_html=True,
    )


def _render_header(result: GridScoreResult) -> None:
    st.markdown("## 🔥 S.A.P.I.")
    st.markdown("**Sistema de Alerta y Priorización de Riesgo de Incendios**")
    badge_col, freshness_col, meta_col = st.columns([1, 1, 3])
    with badge_col:
        st.markdown(
            '<span style="background:#7c3aed;color:white;padding:4px 10px;'
            'border-radius:6px;font-weight:600;font-size:0.85rem;">'
            "PROTOTIPO EXPLORATORIO</span>",
            unsafe_allow_html=True,
        )
    with freshness_col:
        _render_freshness_badge(result)
    with meta_col:
        # Horizonte vs. Ventana evaluada: con datos recientes, "próximas 6
        # horas" es una lectura razonable del horizonte del prototipo. Con
        # datos con retraso/históricos, esa frase implicaría un pronóstico
        # vigente que no existe — se muestra la ventana T -> T+horizon
        # explícita en su lugar, sin ambigüedad sobre "cuándo es ahora".
        if result.freshness == FRESHNESS_RECENT:
            horizonte_txt = f"Horizonte del prototipo: próximas {result.horizon_hours} horas"
        else:
            window_end = result.forecast_time + pd.Timedelta(hours=result.horizon_hours)
            horizonte_txt = f"Ventana evaluada: {result.forecast_time} → {window_end}"
        st.caption(
            f"{horizonte_txt} · "
            f"Forecast time: {result.forecast_time} · "
            f"Estación DMC: {result.station_name} {result.station_id}"
        )


def _inject_metric_contrast_css() -> None:
    """Corrección de contraste (2026-09-07): las 6 tarjetas de meteorología
    se veían apagadas en modo oscuro para una presentación proyectada.
    Refuerza explícitamente título/valor de cada métrica — sin tocar el
    resto del layout ni el tema global."""
    if appearance() == "oscuro":
        label_color, value_color, bg, border = "#d7dce3", "#ffffff", "#2c333d", "#3d4552"
    else:
        label_color, value_color, bg, border = "#33394a", "#0f1115", "#f4f6f8", "#d7dce3"
    st.markdown(
        f"""
        <style>
        div[data-testid="stMetric"] {{
            background: {bg} !important;
            border: 1px solid {border} !important;
            border-radius: 8px;
            padding: 0.6rem 0.8rem;
        }}
        div[data-testid="stMetric"] [data-testid="stMetricLabel"] {{
            color: {label_color} !important;
            font-weight: 600 !important;
            opacity: 1 !important;
        }}
        div[data-testid="stMetric"] [data-testid="stMetricValue"] {{
            color: {value_color} !important;
            font-weight: 700 !important;
            white-space: pre-line !important;
            line-height: 1.25 !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_meteo_cards(result: GridScoreResult) -> None:
    _inject_metric_contrast_css()
    m = result.meteo_actual
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Temperatura regional", f"{m['temperatura']:.1f} °C")
    c2.metric("Humedad relativa", f"{m['humedad_relativa']:.0f} %")
    c3.metric("Viento", f"{m['velocidad_viento_kmh']:.1f} km/h")
    c4.metric("Regla 30-30-30", "ACTIVA" if m["regla_30_30_30"] else "inactiva")
    obs_ts = pd.Timestamp(m["momento_observacion"])
    # Formato compacto (2026-09-08): "2026-09-01 00:00 UTC" (20 caracteres)
    # quedaba truncado en la tarjeta angosta; DD/MM/YYYY + hora en líneas
    # separadas es igual de preciso y cabe sin cortarse. "UTC" se mueve al
    # label (siempre visible completo) en vez de competir por espacio en
    # el valor.
    c5.metric("Hora observación (UTC)", f"{obs_ts.strftime('%d/%m/%Y')}\n{obs_ts.strftime('%H:%M')}")
    c6.metric("Celdas evaluadas", str(len(result.cells)))


def _render_map(result: GridScoreResult) -> None:
    st.markdown("#### Mapa de riesgo relativo — 50 celdas")
    lats = [c.geometry["min_lat"] for c in result.cells] + [c.geometry["max_lat"] for c in result.cells]
    lons = [c.geometry["min_lon"] for c in result.cells] + [c.geometry["max_lon"] for c in result.cells]
    center = [sum(lats) / len(lats), sum(lons) / len(lons)]
    # OpenStreetMap estándar (tile.openstreetmap.org) — el único proveedor
    # que Folium resuelve sin requerir ninguna API key (ver auditoría
    # 2026-09-07: "CartoDB positron" también es gratuito en teoría, pero
    # el watermark "API KEY REQUIRED" visto en la demo no puede arriesgarse
    # de nuevo frente a la comisión; OSM estándar es la opción más segura).
    fmap = folium.Map(location=center, zoom_start=11, tiles="OpenStreetMap")
    n_cells = len(result.cells)
    for c in result.cells:
        g = c.geometry
        # Por display_rank (no por posición): celdas empatadas deben verse
        # con el MISMO color — un degradado por posición insinuaría una
        # diferencia de riesgo que el modelo no está afirmando.
        color = _score_to_color(c.display_rank, n_cells)
        elev_txt = f"{c.elevation:.0f} m" if c.elevation is not None else "sin DEM"
        slope_txt = f"{c.slope:.1f}°" if c.slope is not None else "sin DEM"
        tie_txt = f" (empatada con {c.tie_group_size - 1} celda(s) más)" if c.tie_group_size > 1 else ""
        tooltip = f"<b>{c.cell_id}</b><br>Rank: {c.display_rank}/{n_cells}<br>Score relativo: {c.score:.4f}"
        popup = (
            f"{c.cell_id} — rank {c.display_rank}{tie_txt}<br>"
            f"Score: {c.score:.4f}<br>"
            f"Elevación: {elev_txt}<br>"
            f"Pendiente: {slope_txt}<br>"
            f"Historial FIRMS: {c.historical_count} evento(s)"
        )
        folium.Rectangle(
            bounds=[[g["min_lat"], g["min_lon"]], [g["max_lat"], g["max_lon"]]],
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.65,
            weight=1,
            tooltip=tooltip,
            popup=folium.Popup(popup, max_width=250),
        ).add_to(fmap)
    st_folium(fmap, height=480, use_container_width=True, key="prototype_map")
    _render_map_legend(n_cells)


def _render_map_legend(n_cells: int) -> None:
    """Leyenda del color del mapa (2026-09-08): deliberadamente NO usa
    lenguaje de alerta oficial ("peligro"/"seguro") — el score no está
    calibrado, así que el color codifica únicamente la POSICIÓN relativa
    dentro del ranking exploratorio, nunca un nivel de riesgo absoluto."""
    n_steps = 5
    stops = [1 + round(i * (n_cells - 1) / (n_steps - 1)) for i in range(n_steps)]
    swatches = "".join(
        f'<span style="display:inline-block;width:28px;height:12px;background:{_score_to_color(r, n_cells)};'
        f'margin-right:2px;border-radius:2px;"></span>'
        for r in stops
    )
    st.markdown(
        f"""
        <div style="font-size:0.8rem;margin-top:0.3rem;">
            <b>Mayor score relativo</b> {swatches} <b>Menor score relativo</b>
        </div>
        <div style="font-size:0.72rem;opacity:0.75;margin-top:0.15rem;">
            El color codifica la posición dentro del ranking exploratorio de esta
            corrida, no un nivel de alerta oficial ni una probabilidad calibrada.
        </div>
        """,
        unsafe_allow_html=True,
    )


def _priority_cells(cells: list, min_n: int = _TOP_N_PRIORITY) -> list:
    """Celdas prioritarias honestas ante empates (2026-09-07): recorre en
    orden de score y, al llegar a `min_n`, NO corta un grupo empatado a la
    mitad — incluye el grupo completo. Con datos sin empates se comporta
    exactamente como `cells[:min_n]`."""
    selected: list = []
    seen_display_ranks: set[int] = set()
    for c in cells:
        if len(selected) >= min_n and c.display_rank not in seen_display_ranks:
            break
        selected.append(c)
        seen_display_ranks.add(c.display_rank)
    return selected


def _render_ranking_table(result: GridScoreResult) -> None:
    st.markdown("#### Ranking de riesgo relativo (1 = mayor riesgo exploratorio)")
    priority_ids = {c.cell_id for c in _priority_cells(result.cells)}
    df = pd.DataFrame(
        [
            {
                "Rank": c.display_rank,
                "Celda": c.cell_id,
                "Score": round(c.score, 6),
                "Empate": f"×{c.tie_group_size}" if c.tie_group_size > 1 else "—",
            }
            for c in result.cells
        ]
    )

    def _highlight_top(row: pd.Series) -> list[str]:
        is_priority = row["Celda"] in priority_ids
        return ["background-color: rgba(220, 38, 38, 0.15)"] * len(row) if is_priority else [""] * len(row)

    st.dataframe(df.style.apply(_highlight_top, axis=1), use_container_width=True, hide_index=True, height=420)
    st.caption(
        "El 'Rank' mostrado es honesto ante empates: celdas con score idéntico "
        "comparten el mismo número (el modelo no las distingue) — la columna "
        "'Empate' indica cuántas celdas comparten ese score exacto."
    )


def _render_priority_cells(result: GridScoreResult) -> None:
    top = _priority_cells(result.cells)
    n_extra = len(top) - _TOP_N_PRIORITY
    title = "Celdas prioritarias (exploratorio)"
    if n_extra > 0:
        title += f" — Top {_TOP_N_PRIORITY}, se muestran {len(top)} por empate real de score"
    st.markdown(f"#### {title}")
    st.caption(
        "Apoyo a decisión y priorización exploratoria — NO es una alerta operacional oficial."
    )
    cols = st.columns(len(top))
    for col, c in zip(cols, top):
        with col:
            tie_txt = f" · empate ×{c.tie_group_size}" if c.tie_group_size > 1 else ""
            st.metric(f"#{c.display_rank} · {c.cell_id}", f"{c.score:.4f}")
            elev_txt = f" · Elev: {c.elevation:.0f} m" if c.elevation is not None else ""
            st.caption(f"Historial: {c.historical_count}{elev_txt}{tie_txt}")


def _render_data_status(result: GridScoreResult) -> None:
    with st.expander("Estado de datos y modelo", expanded=False):
        st.markdown(
            f"- **Fuente meteorológica:** DMC {result.station_id} ({result.station_name})\n"
            "- **Fuente de detecciones:** NASA FIRMS\n"
            "- **Topografía:** DEM (Copernicus GLO-30)\n"
            f"- **Dataset:** temporal h={result.horizon_hours}h\n"
            f"- **Modelo:** {result.model_version} — **{result.model_status}**\n"
            f"- **Weather timestamp usado:** {result.weather_timestamp}\n"
            f"- **Antigüedad de la observación:** {result.age_hours:.1f} h — **{result.freshness}**"
        )
        st.caption(
            "El score es un ranking relativo de riesgo exploratorio, NO una "
            "probabilidad calibrada de incendio."
        )


def render_prototype_dashboard() -> None:
    """Punto de entrada de la vista de datos reales. Captura
    `PrototypeUnavailableError` y muestra un mensaje claro — nunca deja
    pasar un stacktrace al usuario."""
    try:
        result = _cached_score_current_grid()
    except PrototypeUnavailableError as exc:
        st.markdown("## 🔥 S.A.P.I. — PROTOTIPO EXPLORATORIO")
        st.error(f"No se pudo generar el ranking: {exc}")
        st.caption(
            "Revisa que existan: el modelo del prototipo "
            "(`python scripts/build_prototype_model.py`), el dataset temporal "
            "(`python scripts/build_temporal_dataset.py`), meteorología DMC "
            "reciente en `data/raw/`, y el histórico FIRMS."
        )
        return

    _render_header(result)
    _render_stale_data_banner(result)
    _render_meteo_cards(result)
    st.markdown("---")
    map_col, rank_col = st.columns([1.3, 1])
    with map_col:
        _render_map(result)
    with rank_col:
        _render_ranking_table(result)
    st.markdown("---")
    _render_priority_cells(result)
    st.markdown("---")
    _render_data_status(result)

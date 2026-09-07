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

from src.inference.prototype_service import GridScoreResult, PrototypeUnavailableError, score_current_grid

_TOP_N_PRIORITY = 5


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


def _render_header(result: GridScoreResult) -> None:
    st.markdown("## 🔥 S.A.P.I.")
    st.markdown("**Sistema de Alerta y Priorización de Riesgo de Incendios**")
    badge_col, meta_col = st.columns([1, 3])
    with badge_col:
        st.markdown(
            '<span style="background:#7c3aed;color:white;padding:4px 10px;'
            'border-radius:6px;font-weight:600;font-size:0.85rem;">'
            "PROTOTIPO EXPLORATORIO</span>",
            unsafe_allow_html=True,
        )
    with meta_col:
        st.caption(
            f"Horizonte: próximas {result.horizon_hours} horas · "
            f"Forecast time: {result.forecast_time} · "
            f"Estación DMC: {result.station_name} {result.station_id}"
        )


def _render_meteo_cards(result: GridScoreResult) -> None:
    m = result.meteo_actual
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Temperatura regional", f"{m['temperatura']:.1f} °C")
    c2.metric("Humedad relativa", f"{m['humedad_relativa']:.0f} %")
    c3.metric("Viento", f"{m['velocidad_viento_kmh']:.1f} km/h")
    c4.metric("Regla 30-30-30", "ACTIVA" if m["regla_30_30_30"] else "inactiva")
    c5.metric("Hora observación", pd.Timestamp(m["momento_observacion"]).strftime("%Y-%m-%d %H:%M UTC"))
    c6.metric("Celdas evaluadas", str(len(result.cells)))


def _render_map(result: GridScoreResult) -> None:
    st.markdown("#### Mapa de riesgo relativo — 50 celdas")
    lats = [c.geometry["min_lat"] for c in result.cells] + [c.geometry["max_lat"] for c in result.cells]
    lons = [c.geometry["min_lon"] for c in result.cells] + [c.geometry["max_lon"] for c in result.cells]
    center = [sum(lats) / len(lats), sum(lons) / len(lons)]
    fmap = folium.Map(location=center, zoom_start=11, tiles="CartoDB positron")
    n_cells = len(result.cells)
    for c in result.cells:
        g = c.geometry
        color = _score_to_color(c.rank, n_cells)
        elev_txt = f"{c.elevation:.0f} m" if c.elevation is not None else "sin DEM"
        slope_txt = f"{c.slope:.1f}°" if c.slope is not None else "sin DEM"
        tooltip = f"<b>{c.cell_id}</b><br>Rank: {c.rank}/{n_cells}<br>Score relativo: {c.score:.4f}"
        popup = (
            f"{c.cell_id} — rank {c.rank}<br>"
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


def _render_ranking_table(result: GridScoreResult) -> None:
    st.markdown("#### Ranking de riesgo relativo (1 = mayor riesgo exploratorio)")
    df = pd.DataFrame(
        [{"Rank": c.rank, "Celda": c.cell_id, "Score": round(c.score, 4)} for c in result.cells]
    )

    def _highlight_top(row: pd.Series) -> list[str]:
        return ["background-color: rgba(220, 38, 38, 0.15)"] * len(row) if row["Rank"] <= _TOP_N_PRIORITY else [""] * len(row)

    st.dataframe(df.style.apply(_highlight_top, axis=1), use_container_width=True, hide_index=True, height=420)


def _render_priority_cells(result: GridScoreResult) -> None:
    st.markdown("#### Celdas prioritarias (exploratorio)")
    st.caption(
        "Apoyo a decisión y priorización exploratoria — NO es una alerta operacional oficial."
    )
    top = result.cells[:_TOP_N_PRIORITY]
    cols = st.columns(len(top))
    for col, c in zip(cols, top):
        with col:
            st.metric(f"#{c.rank} · {c.cell_id}", f"{c.score:.4f}")
            elev_txt = f" · Elev: {c.elevation:.0f} m" if c.elevation is not None else ""
            st.caption(f"Historial: {c.historical_count}{elev_txt}")


def _render_data_status(result: GridScoreResult) -> None:
    with st.expander("Estado de datos y modelo", expanded=False):
        st.markdown(
            f"- **Fuente meteorológica:** DMC {result.station_id} ({result.station_name})\n"
            "- **Fuente de detecciones:** NASA FIRMS\n"
            "- **Topografía:** DEM (Copernicus GLO-30)\n"
            f"- **Dataset:** temporal h={result.horizon_hours}h\n"
            f"- **Modelo:** {result.model_version} — **{result.model_status}**\n"
            f"- **Weather timestamp usado:** {result.weather_timestamp}"
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

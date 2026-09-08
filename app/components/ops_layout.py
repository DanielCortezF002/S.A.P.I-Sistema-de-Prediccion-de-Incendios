"""Layout ops-center (referencia Claude Design) con datos reales del seed/DMC/FIRMS."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping, Optional

import geopandas as gpd
import pandas as pd
import streamlit as st

from app.data.cell_firms import firms_count_for_cell
from app.data.cell_terrain import terrain_for_cell
from app.data.dmc_live import DmcLiveSnapshot, load_rodelillo_snapshot
from app.theme.tokens import RISK_LABEL, risk_palette
from app.utils.cell_zones import comuna_options, zone_for_cell_id, zone_for_comuna, zone_label_for_cell
from app.utils.grid import cell_center, cell_step_meters
from src.config import SAPI_DATA_MODE

_LEGEND_COPY = {
    "bajo": (
        "Bajo",
        "Ninguna o una condición cumplida. Vigilancia normal, sin acción operativa.",
    ),
    "medio": (
        "Medio",
        "Dos condiciones de la regla 30-30-30. Refuerzo preventivo y monitoreo intensificado.",
    ),
    "alto": (
        "Alto",
        "Tres condiciones o probabilidad ≥66 %. Prioridad operativa inmediata.",
    ),
    "sin_dato": (
        "Sin dato",
        "Sin observación disponible para la celda o variable. No se inventa un valor.",
    ),
}


def _diamond_svg(fill: str, size: int = 72) -> str:
    return (
        f'<svg viewBox="0 0 24 24" width="{size}" height="{size}" aria-hidden="true">'
        f'<path fill="{fill}" d="M12 2 L22 12 L12 22 L2 12 Z"/></svg>'
    )


def _circle_svg(fill: str, size: int = 72) -> str:
    return (
        f'<svg viewBox="0 0 24 24" width="{size}" height="{size}" aria-hidden="true">'
        f'<circle fill="{fill}" cx="12" cy="12" r="8"/></svg>'
    )


def _triangle_svg(fill: str, size: int = 72) -> str:
    return (
        f'<svg viewBox="0 0 24 24" width="{size}" height="{size}" aria-hidden="true">'
        f'<path fill="{fill}" d="M12 4 L22 20 H2 Z"/></svg>'
    )


def _level_shape(nivel: str, fill: str, size: int = 72) -> str:
    if nivel == "alto":
        return _triangle_svg(fill, size)
    if nivel == "medio":
        return _diamond_svg(fill, size)
    return _circle_svg(fill, size)


def _rule_hits(row: Mapping[str, Any]) -> tuple[int, list[tuple[str, bool, str]]]:
    t = float(row["temperatura"])
    h = float(row["humedad_relativa"])
    v = float(row["velocidad_viento"])
    checks = [
        ("Temperatura", t > 30, f"{t:.1f} °C · umbral > 30 °C"),
        ("Humedad relativa", h < 30, f"{h:.0f} % · umbral < 30 %"),
        ("Viento", v > 30, f"{v:.1f} km/h · umbral > 30 km/h"),
    ]
    return sum(1 for _, ok, _ in checks if ok), checks


def _trend_html(delta: Optional[float], unit: str) -> str:
    if delta is None:
        return '<span class="sapi-var-trend is-na">sin tendencia</span>'
    arrow = "↑" if delta > 0 else ("↓" if delta < 0 else "→")
    sign = f"{delta:+.1f}"
    return f'<span class="sapi-var-trend">{arrow} {sign} {unit}</span>'


def render_ops_header() -> None:
    """Logo + subtítulo + chips DMC / escenario / fecha."""
    dmc = load_rodelillo_snapshot()
    now = datetime.now().strftime("%d %b %Y · %H:%M").upper()
    dmc_chip = (
        f'<span class="sapi-chip sapi-chip--live">● CLIMA EN VIVO · DMC RODELILLO</span>'
        if dmc.available
        else '<span class="sapi-chip sapi-chip--muted">○ DMC RODELILLO · sin dato en data/raw</span>'
    )
    st.markdown(
        f'<div class="sapi-ops-header">'
        f'<div class="sapi-ops-brand">'
        f'<div class="sapi-ops-mark" aria-hidden="true">S</div>'
        f"<div>"
        f'<div class="sapi-ops-title">S.A.P.I.</div>'
        f'<div class="sapi-ops-sub">Sistema de Alerta y Predicción de Incendios · '
        f"Región de Valparaíso</div>"
        f"</div></div>"
        f'<div class="sapi-ops-chips">'
        f"{dmc_chip}"
        f'<span class="sapi-chip">ESCENARIO: Demo sembrado ({SAPI_DATA_MODE})</span>'
        f'<span class="sapi-chip sapi-chip--time">{now}</span>'
        f"</div></div>",
        unsafe_allow_html=True,
    )


def render_corridor_verified_note() -> None:
    """Nota visual a la derecha del banner protegido (sin alterar su texto)."""
    st.markdown(
        '<div class="sapi-corridor-verified">verificado contra shapefile comunal SUBDERE</div>',
        unsafe_allow_html=True,
    )


def render_mayor_riesgo_block(top: Optional[dict[str, Any]], gdf: gpd.GeoDataFrame) -> None:
    """Bloque dominante: mayor riesgo ahora + desglose 30-30-30."""
    if top is None:
        st.warning("Sin celdas para calcular el mayor riesgo del día.")
        return

    cell_id = str(top["cell_id"])
    row = gdf.loc[gdf["cell_id"] == cell_id]
    if row.empty:
        st.warning(f"La celda {cell_id} no está en el GDF del día.")
        return
    raw = row.iloc[0]
    nivel = str(top["nivel_riesgo"])
    palette = risk_palette(nivel)
    hits, checks = _rule_hits(raw)
    lat, lon = cell_center(int(cell_id.split("-")[1]))
    zona = zone_label_for_cell(cell_id)
    firms_n = firms_count_for_cell(cell_id)
    firms_chip = (
        f'<span class="sapi-mini-chip">{firms_n} detecciones FIRMS 2024-02-03</span>'
        if firms_n is not None and firms_n > 0
        else ""
    )
    shape = _level_shape(nivel, palette.on_solid, 44)

    if hits == 3:
        desc_text = (
            "Las tres condiciones de la regla 30-30-30 se cumplen a la vez. "
            "Ignición probable ante una fuente de calor y propagación rápida por pendiente."
        )
    elif hits == 2:
        desc_text = (
            "Dos condiciones de la regla 30-30-30 activas. "
            "Refuerzo preventivo y monitoreo intensificado en el corredor."
        )
    else:
        desc_text = (
            "Condiciones bajo umbral crítico simultáneo de la regla 30-30-30. "
            "Vigilancia normal sin alerta operativa activa."
        )

    t_val = float(raw["temperatura"])
    h_val = float(raw["humedad_relativa"])
    v_val = float(raw["velocidad_viento"])

    rule_rows_html = (
        f'<div class="sapi-mayor__rule-row {"is-on" if t_val > 30 else "is-off"}">'
        f'<div class="sapi-mayor__rule-check">{"✓" if t_val > 30 else "✗"}</div>'
        f'<div class="sapi-mayor__rule-info">'
        f'<span class="sapi-mayor__rule-name">Temperatura</span>'
        f'<span class="sapi-mayor__rule-thresh">temperatura &gt; 30 °C</span>'
        f'</div>'
        f'<div class="sapi-mayor__rule-val">{t_val:.1f} °C</div>'
        f'</div>'
        f'<div class="sapi-mayor__rule-row {"is-on" if h_val < 30 else "is-off"}">'
        f'<div class="sapi-mayor__rule-check">{"✓" if h_val < 30 else "✗"}</div>'
        f'<div class="sapi-mayor__rule-info">'
        f'<span class="sapi-mayor__rule-name">Humedad relativa</span>'
        f'<span class="sapi-mayor__rule-thresh">humedad relativa &lt; 30 %</span>'
        f'</div>'
        f'<div class="sapi-mayor__rule-val">{h_val:.0f} %</div>'
        f'</div>'
        f'<div class="sapi-mayor__rule-row {"is-on" if v_val > 30 else "is-off"}">'
        f'<div class="sapi-mayor__rule-check">{"✓" if v_val > 30 else "✗"}</div>'
        f'<div class="sapi-mayor__rule-info">'
        f'<span class="sapi-mayor__rule-name">Viento</span>'
        f'<span class="sapi-mayor__rule-thresh">viento &gt; 30 km/h</span>'
        f'</div>'
        f'<div class="sapi-mayor__rule-val">{v_val:.1f} km/h</div>'
        f'</div>'
    )

    st.markdown(
        f'<div class="sapi-mayor" style="--mayor-bg:{palette.surface};--mayor-fg:{palette.on_solid};'
        f'--mayor-stroke:{palette.stroke}">'
        f'<div class="sapi-mayor__left">'
        f'<div class="sapi-mayor__kicker">MAYOR RIESGO AHORA</div>'
        f'<div class="sapi-mayor__level">'
        f'<span class="sapi-mayor__shape">{shape}</span>'
        f'<span class="sapi-mayor__word">{RISK_LABEL.get(nivel, nivel).upper()}</span>'
        f"</div>"
        f'<div class="sapi-mayor__sub">{hits} DE 3 CONDICIONES DE LA REGLA 30-30-30</div>'
        f'<div class="sapi-mayor__id">{zona} · celda {cell_id}</div>'
        f'<div class="sapi-mayor__desc">{desc_text}</div>'
        f'<div class="sapi-mayor__meta">'
        f'<span class="sapi-mini-chip">{lat:.4f} / {lon:.4f}</span>'
        f"{firms_chip}"
        f"</div>"
        f"</div>"
        f'<div class="sapi-mayor__right">'
        f'<div class="sapi-mayor__right-head">'
        f'<span class="sapi-mayor__right-title">REGLA 30-30-30</span>'
        f'<span class="sapi-mayor__right-sub">umbral viento 30 km/h</span>'
        f"</div>"
        f'<div class="sapi-mayor__rule-table">{rule_rows_html}</div>'
        f'<div class="sapi-mayor__rule-footnote">'
        f"La regla se evalúa sobre la lectura horaria de la celda. Las tres condiciones deben cumplirse a la vez para nivel alto."
        f"</div>"
        f"</div></div>",
        unsafe_allow_html=True,
    )


def render_variable_strip(
    focus_row: Optional[Mapping[str, Any]],
    prev_row: Optional[Mapping[str, Any]],
) -> None:
    """Cuatro tarjetas: T, HR, V (celda) + DMC Rodelillo."""
    dmc = load_rodelillo_snapshot()

    def cell_card(sigla: str, name: str, key: str, unit: str, kind: str) -> str:
        if focus_row is None or key not in focus_row:
            return (
                f'<article class="sapi-vcard">'
                f'<div class="sapi-vcard__sig">{sigla}</div>'
                f'<div class="sapi-vcard__name">{name}</div>'
                f'<div class="sapi-vcard__value">—</div>'
                f'<div class="sapi-vcard__unit">{unit}</div>'
                f'<div class="sapi-vcard__meta">'
                f'<span class="sapi-vcard__badge is-na">sin dato</span>'
                f'<span class="sapi-var-trend is-na">sin tendencia</span>'
                f"</div></article>"
            )
        value = float(focus_row[key])
        delta = None
        if prev_row is not None and key in prev_row:
            delta = value - float(prev_row[key])
        if kind == "temperatura":
            badge = ("alto", "Alto") if value > 30 else ("normal", "Normal")
        elif kind == "humedad":
            badge = ("critico", "Crítico") if value < 30 else ("normal", "Normal")
        else:
            badge = ("alto", "Alto") if value > 30 else ("normal", "Normal")
        fmt = f"{value:.1f}" if kind != "humedad" else f"{value:.0f}"
        return (
            f'<article class="sapi-vcard">'
            f'<div class="sapi-vcard__sig">{sigla}</div>'
            f'<div class="sapi-vcard__name">{name}</div>'
            f'<div class="sapi-vcard__value">{fmt}</div>'
            f'<div class="sapi-vcard__unit">{unit}</div>'
            f'<div class="sapi-vcard__meta">'
            f'<span class="sapi-vcard__badge is-{badge[0]}">{badge[1]}</span>'
            f"{_trend_html(delta, unit)}"
            f"</div>"
            f'<div class="sapi-vcard__since">desde celda del día anterior (seed)</div>'
            f"</article>"
        )

    if dmc.available and dmc.temperatura is not None:
        dmc_badge = (
            ("alto", "Alto") if dmc.temperatura > 30 else ("normal", "Normal")
        )
        since = (
            dmc.momento.strftime("%H:%M") if dmc.momento else "—"
        )
        dmc_card = (
            f'<article class="sapi-vcard sapi-vcard--dmc">'
            f'<div class="sapi-vcard__sig">DMC</div>'
            f'<div class="sapi-vcard__name">Rodelillo (vivo)</div>'
            f'<div class="sapi-vcard__value">{dmc.temperatura:.1f}</div>'
            f'<div class="sapi-vcard__unit">°C</div>'
            f'<div class="sapi-vcard__meta">'
            f'<span class="sapi-vcard__badge is-{dmc_badge[0]}">{dmc_badge[1]}</span>'
            f"{_trend_html(dmc.delta_temp, '°C')}"
            f"</div>"
            f'<div class="sapi-vcard__since">desde {since} · HR {dmc.humedad_relativa:.0f}% · '
            f"V {dmc.velocidad_viento_kmh:.1f} km/h</div>"
            f"</article>"
        )
    else:
        dmc_card = (
            f'<article class="sapi-vcard sapi-vcard--dmc">'
            f'<div class="sapi-vcard__sig">DMC</div>'
            f'<div class="sapi-vcard__name">Rodelillo</div>'
            f'<div class="sapi-vcard__value">—</div>'
            f'<div class="sapi-vcard__unit">°C</div>'
            f'<div class="sapi-vcard__meta">'
            f'<span class="sapi-vcard__badge is-na">sin dato</span>'
            f'<span class="sapi-var-trend is-na">sin tendencia</span>'
            f"</div>"
            f'<div class="sapi-vcard__since">sin telemetría en data/raw</div>'
            f"</article>"
        )

    html = (
        '<div class="sapi-vstrip">'
        + cell_card("T", "Temperatura", "temperatura", "°C", "temperatura")
        + cell_card("HR", "Humedad relativa", "humedad_relativa", "%", "humedad")
        + cell_card("V", "Viento", "velocidad_viento", "km/h", "viento")
        + dmc_card
        + "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def render_dmc_live_section(dmc: Optional[DmcLiveSnapshot] = None) -> None:
    """Sección propia de la estación DMC Rodelillo, desplegada directamente.

    Antes lo único "en vivo" era la 4ª tarjeta de variables (temperatura
    nada más) y el chip del header — la humedad, el viento y la dirección de
    Rodelillo no se veían en ningún lado sin ir a inspeccionar el JSON. Esto
    no es un expander que haya que abrir: se muestra siempre, con el detalle
    completo de la última observación.
    """
    dmc = dmc or load_rodelillo_snapshot()
    if not dmc.available:
        st.markdown(
            '<div class="sapi-panel sapi-dmc-panel">'
            '<div class="sapi-panel__head" style="border-color:var(--sapi-border-card)"><div>'
            '<div class="sapi-panel__id">📡 DMC Rodelillo</div>'
            '<div class="sapi-panel__zone">Estación en vivo</div>'
            "</div></div>"
            f'<div class="sapi-panel__block"><p class="sapi-empty">{dmc.detail}</p></div>'
            "</div>",
            unsafe_allow_html=True,
        )
        return
    since = dmc.momento.strftime("%Y-%m-%d %H:%M") if dmc.momento else "—"
    direccion = f"{dmc.direccion_viento_deg:.0f}°" if dmc.direccion_viento_deg is not None else "sin dato"
    fuente = Path(dmc.source_path).name if dmc.source_path else "—"
    st.markdown(
        '<div class="sapi-panel sapi-dmc-panel">'
        '<div class="sapi-panel__head" style="border-color:var(--sapi-border-card)"><div>'
        '<div class="sapi-panel__id">📡 DMC Rodelillo</div>'
        f'<div class="sapi-panel__zone">Estación en vivo · última observación {since}</div>'
        "</div>"
        '<span class="sapi-chip sapi-chip--live">● EN VIVO</span>'
        "</div>"
        '<div class="sapi-panel__block">'
        "<ul class='sapi-kv sapi-kv--row'>"
        f"<li><span>Temperatura</span><strong>{dmc.temperatura:.1f} °C</strong></li>"
        f"<li><span>Humedad relativa</span><strong>{dmc.humedad_relativa:.0f} %</strong></li>"
        f"<li><span>Viento</span><strong>{dmc.velocidad_viento_kmh:.1f} km/h</strong></li>"
        f"<li><span>Dirección</span><strong>{direccion}</strong></li>"
        "</ul>"
        f'<p class="sapi-empty">Fuente: {fuente} · estación 330007</p>'
        "</div></div>",
        unsafe_allow_html=True,
    )


def render_comuna_search(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Buscador de comuna: filtra la grilla a la banda climática de la comuna.

    Restringido a las cuatro comunas con banda verificada por geometría real
    (`app.utils.cell_zones.COMUNA_ZONE`) — no ofrece Valparaíso ni Concón
    porque no hay columna de grilla verificada para ellas, y esta app no
    inventa esa precisión. Devuelve el GDF filtrado (o el original si no hay
    selección) para que mapa, tabla y conteos queden coherentes entre sí.
    """
    opciones = ["Todas las comunas"] + comuna_options()
    elegida = st.selectbox(
        "🔎 Buscar comuna",
        options=opciones,
        key="sapi_comuna_search",
        help="Filtra la grilla a la banda climática de la comuna elegida.",
    )
    if elegida == "Todas las comunas" or gdf.empty:
        return gdf
    zona = zone_for_comuna(elegida)
    filtrado = gdf[gdf["cell_id"].astype(str).map(zone_for_cell_id) == zona]
    st.caption(
        f"Mostrando {len(filtrado)} celda(s) en banda climática de **{elegida}** "
        "(aproximado por banda, no por límite comunal exacto)."
    )
    return filtrado


def render_level_summary_chips(gdf: gpd.GeoDataFrame) -> None:
    """Chips de conteo real por nivel sobre el mapa."""
    if gdf.empty:
        return
    counts = gdf["nivel_riesgo"].astype(str).value_counts().to_dict()
    parts = []
    for nivel in ("bajo", "medio", "alto"):
        n = int(counts.get(nivel, 0))
        palette = risk_palette(nivel)
        parts.append(
            f'<span class="sapi-sum-chip" style="--c:{palette.surface}">'
            f"{RISK_LABEL[nivel]} · {n}</span>"
        )
    st.markdown(
        f'<div class="sapi-sum-row">{"".join(parts)}</div>',
        unsafe_allow_html=True,
    )


def render_ops_detail_panel(
    gdf: gpd.GeoDataFrame,
    selected_id: Optional[str],
    *,
    fecha: date,
    app_build: str,
) -> None:
    """Panel derecho: meteo, regla, DEM, FIRMS, procedencia."""
    if not selected_id:
        st.info("Selecciona una celda en el mapa o en alertas para ver el detalle.")
        return
    match = gdf.loc[gdf["cell_id"] == selected_id]
    if match.empty:
        st.warning("Celda no encontrada en el día consultado.")
        return
    row = match.iloc[0]
    nivel = str(row["nivel_riesgo"])
    palette = risk_palette(nivel)
    zona = zone_label_for_cell(selected_id)
    hits, checks = _rule_hits(row)
    terrain = terrain_for_cell(selected_id)
    firms_n = firms_count_for_cell(selected_id)
    step_km = cell_step_meters()[0] / 1000
    lat, lon = cell_center(int(str(selected_id).split("-")[1]))

    t_val = float(row["temperatura"])
    h_val = float(row["humedad_relativa"])
    v_val = float(row["velocidad_viento"])

    rule_lines = (
        f'<div class="sapi-detail-rule-line {"is-on" if t_val > 30 else "is-off"}">'
        f'<span class="sapi-detail-rule-mark">{"✓" if t_val > 30 else "✗"}</span>'
        f'<span class="sapi-detail-rule-cond">temperatura &gt; 30 °C</span>'
        f'<strong class="sapi-detail-rule-val">{t_val:.1f} °C</strong>'
        f'</div>'
        f'<div class="sapi-detail-rule-line {"is-on" if h_val < 30 else "is-off"}">'
        f'<span class="sapi-detail-rule-mark">{"✓" if h_val < 30 else "✗"}</span>'
        f'<span class="sapi-detail-rule-cond">humedad relativa &lt; 30 %</span>'
        f'<strong class="sapi-detail-rule-val">{h_val:.0f} %</strong>'
        f'</div>'
        f'<div class="sapi-detail-rule-line {"is-on" if v_val > 30 else "is-off"}">'
        f'<span class="sapi-detail-rule-mark">{"✓" if v_val > 30 else "✗"}</span>'
        f'<span class="sapi-detail-rule-cond">viento &gt; 30 km/h</span>'
        f'<strong class="sapi-detail-rule-val">{v_val:.1f} km/h</strong>'
        f'</div>'
    )

    if hits == 3:
        rule_desc = (
            "Las tres condiciones de la regla 30-30-30 se cumplen a la vez. "
            "Ignición probable ante una fuente de calor y propagación rápida por pendiente."
        )
    elif hits == 2:
        rule_desc = (
            "Dos condiciones cumplidas. Vigilancia reforzada y revisión horaria en la celda."
        )
    else:
        rule_desc = (
            "Una o ninguna condición cumplida. Vigilancia normal, sin acción operativa."
        )

    rule_box_html = (
        f'<div class="sapi-rule-score-box">'
        f'<div class="sapi-rule-score-badge">'
        f'<span class="sapi-rule-score-num">{hits}</span>'
        f'<span class="sapi-rule-score-de">de</span>'
        f'<span class="sapi-rule-score-total">3</span>'
        f'</div>'
        f'<div class="sapi-rule-score-desc">{rule_desc}</div>'
        f'</div>'
    )

    if terrain.available:
        topo_html = (
            f"<ul class='sapi-kv'>"
            f"<li><span>Elevación</span><strong>{terrain.elevacion_m:.0f} m</strong></li>"
            f"<li><span>Pendiente</span><strong>{terrain.pendiente_deg:.1f}°</strong></li>"
            f"<li><span>Orientación</span><strong>{terrain.orientacion_deg:.0f}°</strong></li>"
            f"</ul>"
        )
    else:
        topo_html = f'<p class="sapi-empty">{terrain.detail}</p>'

    if firms_n is None:
        firms_html = (
            '<p class="sapi-empty">sin detecciones históricas registradas '
            "(asset FIRMS ausente)</p>"
        )
    elif firms_n == 0:
        firms_html = (
            '<p class="sapi-empty">sin detecciones históricas registradas '
            "en esta celda para 2024-02-03</p>"
        )
    else:
        firms_html = (
            f"<p><strong>{firms_n}</strong> detecciones NASA FIRMS "
            f"(evento 2024-02-03, contención en grilla B).</p>"
        )

    st.markdown(
        f'<div class="sapi-panel">'
        f'<div class="sapi-panel__head" style="border-color:{palette.stroke}">'
        f"<div>"
        f'<div class="sapi-panel__id">{selected_id}</div>'
        f'<div class="sapi-panel__zone">{zona}</div>'
        f'<div class="sapi-panel__coords">{lat:.4f} / {lon:.4f}</div>'
        f"</div>"
        f'<span class="sapi-panel__badge" style="background:{palette.surface};'
        f'color:{palette.on_solid}">{RISK_LABEL.get(nivel, nivel).upper()}</span>'
        f"</div>"
        f'<div class="sapi-panel__block"><div class="sapi-panel__h">VARIABLES METEOROLÓGICAS</div>'
        f"<ul class='sapi-kv'>"
        f"<li><span>Temperatura</span><strong>{t_val:.1f} °C</strong></li>"
        f"<li><span>Humedad relativa</span><strong>{h_val:.0f} %</strong></li>"
        f"<li><span>Viento</span><strong>{v_val:.1f} km/h</strong></li>"
        f"<li><span>Dirección</span><strong>sin dato</strong></li>"
        f"</ul></div>"
        f'<div class="sapi-panel__block"><div class="sapi-panel__h">REGLA 30-30-30</div>'
        f"{rule_lines}{rule_box_html}</div>"
        f'<div class="sapi-panel__block"><div class="sapi-panel__h">'
        f"TOPOGRAFÍA · DEM COPERNICUS 30M</div>{topo_html}</div>"
        f'<div class="sapi-panel__block"><div class="sapi-panel__h">HISTORIAL NASA FIRMS</div>'
        f"{firms_html}</div>"
        f'<div class="sapi-panel__block"><div class="sapi-panel__h">PROCEDENCIA</div>'
        f"<ul class='sapi-kv'>"
        f"<li><span>Origen</span><strong>demo_seed</strong></li>"
        f"<li><span>Última actualización</span><strong>{fecha.isoformat()}</strong></li>"
        f"<li><span>Resolución celda</span><strong>~{step_km:.1f} km · lectura horaria</strong></li>"
        f"<li><span>Centro</span><strong>{lat:.4f}, {lon:.4f}</strong></li>"
        f"</ul></div>"
        f"</div>",
        unsafe_allow_html=True,
    )


def render_four_state_legend() -> None:
    """Leyenda de 4 estados al pie: Bajo, Medio, Alto, Sin dato."""
    items = []
    for key, (label, desc) in _LEGEND_COPY.items():
        if key == "sin_dato":
            fill = "#95a5a6"
            inner = _circle_svg("#ffffff", 14)
        else:
            palette = risk_palette(key)
            fill = palette.surface
            inner = _level_shape(key, palette.on_solid, 14)
        items.append(
            f'<div class="sapi-state-card">'
            f'<div class="sapi-state-card__head">'
            f'<span class="sapi-state-card__mark" style="background:{fill}">{inner}</span>'
            f'<strong class="sapi-state-card__title">{label.upper()}</strong>'
            f"</div>"
            f'<p class="sapi-state-card__desc">{desc}</p>'
            f"</div>"
        )
    st.markdown(
        f'<div class="sapi-four-states">{"".join(items)}</div>',
        unsafe_allow_html=True,
    )


def render_operational_verification_footer() -> None:
    """Notas de auditoría y transparencia técnica (página 2 del diseño)."""
    st.markdown(
        """
        <div class="sapi-audit-box">
            <div class="sapi-audit-col">
                <div class="sapi-audit-title">VERIFICADO CON DATOS REALES</div>
                <p>12.477 detecciones NASA FIRMS (2020-2024) · clima de la estación DMC Rodelillo en vivo · 
                DEM Copernicus 30 m para elevación, pendiente y orientación · 348 detecciones del corredor 2024 
                cruzadas contra límites comunales SUBDERE.</p>
            </div>
            <div class="sapi-audit-col">
                <div class="sapi-audit-title">SIMULADO EN ESTA VISTA</div>
                <p>La grilla muestra un escenario sembrado (demo_seed), no una corrida de inferencia en producción. 
                La regla 30-30-30 opera como proxy de ignición mientras no haya modelo entrenado.</p>
            </div>
            <div class="sapi-audit-col sapi-audit-col--alert">
                <div class="sapi-audit-title">RIESGO ABIERTO · R-ETIQUETA-01</div>
                <p>La regla 30-30-30 casi nunca coincide con incendios confirmados por FIRMS. 
                Sin corrida de modelo real todavía: no se reportan métricas de desempeño.</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def previous_day_row(
    available: list[date],
    selected: date,
    cell_id: Optional[str],
    loader,
) -> Optional[pd.Series]:
    """Fila del mismo cell_id en el día anterior del seed, si existe."""
    if not cell_id or not available:
        return None
    sorted_days = sorted(available)
    if selected not in sorted_days:
        return None
    idx = sorted_days.index(selected)
    if idx == 0:
        return None
    prev = sorted_days[idx - 1]
    gdf = loader(prev)
    match = gdf.loc[gdf["cell_id"] == cell_id]
    if match.empty:
        return None
    return match.iloc[0]

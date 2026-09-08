"""Alertas del día: celdas en riesgo alto del GDF seleccionado."""

from __future__ import annotations

from typing import Optional

import geopandas as gpd
import streamlit as st

from app.components.risk_level import risk_shape_svg
from app.theme.tokens import risk_palette
from app.utils.cell_zones import zone_label_for_cell


def high_risk_rows(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Celdas con nivel_riesgo == alto, ordenadas por probabilidad desc."""
    if gdf is None or gdf.empty:
        return gdf.iloc[0:0] if gdf is not None else gpd.GeoDataFrame()
    alto = gdf.loc[gdf["nivel_riesgo"].astype(str) == "alto"].copy()
    if alto.empty:
        return alto
    return alto.sort_values("probabilidad", ascending=False)


def render_day_alerts(
    gdf: gpd.GeoDataFrame,
    selected_id: Optional[str],
) -> Optional[str]:
    """Lista de alertas del día. Devuelve cell_id si el usuario selecciona una."""
    altos = high_risk_rows(gdf)
    if altos.empty:
        st.caption("Sin celdas en riesgo alto para este día.")
        return None

    st.caption(
        f"{len(altos)} celda(s) en riesgo alto · Probabilidad × 100 (escenario sembrado)"
    )
    chosen: Optional[str] = None
    for _, row in altos.iterrows():
        cell_id = str(row["cell_id"])
        nivel = str(row["nivel_riesgo"])
        palette = risk_palette(nivel)
        score = int(round(float(row["probabilidad"]) * 100))
        zona = zone_label_for_cell(cell_id)
        shape = risk_shape_svg(nivel, fill=palette.on_solid, size=18)
        is_sel = cell_id == selected_id
        st.markdown(
            f'<div class="sapi-alert-row">'
            f'<div class="sapi-risk-chip__mark" style="background:{palette.surface};'
            f'width:32px;height:32px" aria-hidden="true">{shape}</div>'
            f"<div style=\"flex:1\">"
            f"<strong>{cell_id}</strong> · {zona} · {score}%"
            f"</div></div>",
            unsafe_allow_html=True,
        )
        label = "Seleccionada" if is_sel else f"Seleccionar {cell_id}"
        if st.button(
            label,
            key=f"alert_{cell_id}",
            type="primary" if is_sel else "secondary",
            use_container_width=True,
        ):
            chosen = cell_id
    return chosen

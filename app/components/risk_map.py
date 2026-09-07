"""Pestaña del mapa de riesgo."""

from __future__ import annotations

from datetime import date
from typing import Any, Optional, Protocol, Set

import geopandas as gpd

from app.utils.cell_table import cell_id_from_folium_output


class _MapDashboard(Protocol):
    def render_folium_map(
        self,
        fecha: Optional[date] = None,
        gdf: Optional[gpd.GeoDataFrame] = None,
    ) -> Optional[dict]: ...


def render_risk_map(
    dashboard: _MapDashboard,
    selected_date: date,
    gdf: gpd.GeoDataFrame,
    valid_cell_ids: Set[str],
) -> Optional[str]:
    """Renderiza el mapa y devuelve el cell_id clickeado, si hubo uno válido.

    Sin caption propia: `app.py` ya imprime una encima del frame con la
    resolución de celda incluida — dos captions idénticas una debajo de la
    otra era ruido, no refuerzo.
    """
    map_output: Optional[dict[str, Any]] = dashboard.render_folium_map(
        selected_date,
        gdf=gdf,
    )
    return cell_id_from_folium_output(map_output, valid_cell_ids, gdf)

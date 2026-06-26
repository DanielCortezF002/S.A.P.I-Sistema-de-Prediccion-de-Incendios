"""Utilidades de renderizado cartográfico Folium."""

from __future__ import annotations

from typing import Optional

import folium
import geopandas as gpd
from branca.colormap import LinearColormap

from utils.cell_zones import zone_label_for_cell

from utils.risk_colors import RISK_COLORS, map_selection_style

# Radio visual sincronizado con BUFFER_METERS=490 del seed (celdas contiguas ~1 km²)
CELL_RADIUS_METERS = 490


def build_risk_colormap() -> LinearColormap:
    """Construye escala de colores para probabilidad."""
    return LinearColormap(
        colors=["#2ecc71", "#f1c40f", "#e74c3c"],
        vmin=0.0,
        vmax=1.0,
        caption="Probabilidad de ignición",
    )


def _cell_center(geometry) -> tuple[float, float]:
    """Obtiene centro de celda (lat, lon) para marcador circular."""
    if geometry is None or geometry.is_empty:
        return -33.04, -71.45
    if geometry.geom_type == "Point":
        return geometry.y, geometry.x
    centroid = geometry.centroid
    return centroid.y, centroid.x


def render_folium_map(
    gdf: gpd.GeoDataFrame,
    center: Optional[tuple[float, float]] = None,
    zoom: int = 12,
    selected_cell_id: Optional[str] = None,
) -> folium.Map:
    """Renderiza mapa con radios de influencia por celda (~1 km²).

    Args:
        gdf: GeoDataFrame con geometrías y probabilidad.
        center: Centro del mapa (lat, lon).
        zoom: Nivel de zoom inicial.

    Returns:
        Mapa Folium configurado.
    """
    if gdf.empty:
        m = folium.Map(location=(-33.04, -71.45), zoom_start=zoom)
        folium.Marker(
            [-33.04, -71.45],
            popup="Sin datos de riesgo disponibles",
            icon=folium.Icon(color="gray"),
        ).add_to(m)
        return m

    if center is None:
        centers = [_cell_center(g) for g in gdf.geometry]
        avg_lat = sum(c[0] for c in centers) / len(centers)
        avg_lon = sum(c[1] for c in centers) / len(centers)
        center = (avg_lat, avg_lon)

    m = folium.Map(location=center, zoom_start=zoom, tiles="OpenStreetMap")
    colormap = build_risk_colormap()

    for _, row in gdf.iterrows():
        cell_id = str(row.get("cell_id", ""))
        nivel = row.get("nivel_riesgo", "bajo")
        color = RISK_COLORS.get(str(nivel), "#95a5a6")
        prob = float(row.get("probabilidad", 0))
        lat, lon = _cell_center(row.geometry)
        zona = zone_label_for_cell(cell_id)
        is_selected = selected_cell_id is not None and cell_id == selected_cell_id
        sel = map_selection_style(str(nivel), color) if is_selected else None
        popup_html = (
            f"<b>Celda:</b> {cell_id or 'N/A'}<br>"
            f"<b>Zona climática:</b> {zona}<br>"
            f"<b>Probabilidad:</b> {prob:.2%}<br>"
            f"<b>Nivel:</b> {nivel}<br>"
            f"<b>Temperatura:</b> {row.get('temperatura', 'N/A')} °C<br>"
            f"<b>Humedad:</b> {row.get('humedad_relativa', 'N/A')} %<br>"
            f"<b>Viento:</b> {row.get('velocidad_viento', 'N/A')} km/h<br>"
            f"<b>Regla 30-30-30:</b> {'Activa' if row.get('regla_30_30_30') else 'Inactiva'}"
        )
        folium.Circle(
            location=[lat, lon],
            radius=CELL_RADIUS_METERS,
            popup=folium.Popup(popup_html, max_width=320),
            tooltip=cell_id,
            color=sel["stroke"] if sel else color,
            fill=True,
            fill_color=color,
            fill_opacity=sel["fill_opacity"] if sel else 0.45,
            weight=sel["weight"] if sel else 1,
        ).add_to(m)
        folium.CircleMarker(
            location=[lat, lon],
            radius=sel["marker_radius"] if sel else 3,
            color=sel["marker_color"] if sel else "#2c3e50",
            fill=True,
            fill_color=sel["marker_color"] if sel else "#2c3e50",
            fill_opacity=0.95,
            tooltip=cell_id,
            popup=folium.Popup(f"<b>{cell_id}</b>", max_width=120),
        ).add_to(m)

    colormap.add_to(m)
    folium.LayerControl().add_to(m)

    return m

"""Utilidades de renderizado cartográfico Folium."""

from __future__ import annotations

from typing import Optional

import folium
import geopandas as gpd
from branca.colormap import LinearColormap

RISK_COLORS = {
    "bajo": "#2ecc71",
    "medio": "#f1c40f",
    "alto": "#e74c3c",
}


def build_risk_colormap() -> LinearColormap:
    """Construye escala de colores para probabilidad."""
    return LinearColormap(
        colors=["#2ecc71", "#f1c40f", "#e74c3c"],
        vmin=0.0,
        vmax=1.0,
        caption="Probabilidad de ignición",
    )


def render_folium_map(
    gdf: gpd.GeoDataFrame,
    center: Optional[tuple[float, float]] = None,
    zoom: int = 11,
) -> folium.Map:
    """Renderiza mapa coroplético interactivo de riesgo.

    Args:
        gdf: GeoDataFrame con geometrías y probabilidad.
        center: Centro del mapa (lat, lon).
        zoom: Nivel de zoom inicial.

    Returns:
        Mapa Folium configurado.
    """
    if gdf.empty:
        m = folium.Map(location=(-33.05, -71.55), zoom_start=zoom)
        folium.Marker(
            [-33.05, -71.55],
            popup="Sin datos de riesgo disponibles",
            icon=folium.Icon(color="gray"),
        ).add_to(m)
        return m

    simplified = gdf.copy()
    simplified["geometry"] = simplified.geometry.simplify(tolerance=0.001, preserve_topology=True)

    if center is None:
        centroid = simplified.geometry.unary_union.centroid
        center = (centroid.y, centroid.x)

    m = folium.Map(location=center, zoom_start=zoom, tiles="OpenStreetMap")
    colormap = build_risk_colormap()

    for _, row in simplified.iterrows():
        nivel = row.get("nivel_riesgo", "bajo")
        color = RISK_COLORS.get(str(nivel), "#95a5a6")
        prob = float(row.get("probabilidad", 0))
        popup_html = (
            f"<b>Celda:</b> {row.get('cell_id', 'N/A')}<br>"
            f"<b>Probabilidad:</b> {prob:.2%}<br>"
            f"<b>Nivel:</b> {nivel}<br>"
            f"<b>Temperatura:</b> {row.get('temperatura', 'N/A')} °C<br>"
            f"<b>Humedad:</b> {row.get('humedad_relativa', 'N/A')} %<br>"
            f"<b>Viento:</b> {row.get('velocidad_viento', 'N/A')} km/h<br>"
            f"<b>Regla 30-30-30:</b> {'Activa' if row.get('regla_30_30_30') else 'Inactiva'}"
        )
        folium.GeoJson(
            row.geometry.__geo_interface__,
            style_function=lambda x, c=color: {
                "fillColor": c,
                "color": c,
                "weight": 1,
                "fillOpacity": 0.65,
            },
            popup=folium.Popup(popup_html, max_width=300),
        ).add_to(m)

    colormap.add_to(m)
    folium.LayerControl().add_to(m)
    return m

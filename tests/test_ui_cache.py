"""Pruebas de renderizado cartográfico."""

from __future__ import annotations

import geopandas as gpd
from shapely.geometry import box

from app.utils.map_renderer import build_risk_colormap, render_folium_map


def test_build_risk_colormap():
    cmap = build_risk_colormap()
    assert cmap.vmin == 0.0
    assert cmap.vmax == 1.0


def test_render_folium_map_with_data():
    gdf = gpd.GeoDataFrame(
        {
            "cell_id": ["VP-001"],
            "probabilidad": [0.8],
            "nivel_riesgo": ["alto"],
            "temperatura": [34.0],
            "humedad_relativa": [20.0],
            "velocidad_viento": [35.0],
            "regla_30_30_30": [1],
        },
        geometry=[box(-71.58, -33.05, -71.57, -33.04)],
        crs="EPSG:4326",
    )
    m = render_folium_map(gdf)
    assert m is not None


def test_render_folium_map_empty():
    gdf = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    m = render_folium_map(gdf)
    assert m is not None


def test_cell_center_empty_geometry():
    from shapely.geometry import Polygon

    from app.utils.map_renderer import _cell_center

    lat, lon = _cell_center(Polygon())
    assert lat == -33.04
    assert lon == -71.45


def test_cell_center_point():
    from shapely.geometry import Point

    from app.utils.map_renderer import _cell_center

    lat, lon = _cell_center(Point(-71.5, -33.04))
    assert lat == -33.04
    assert lon == -71.5

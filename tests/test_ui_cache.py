"""Pruebas de renderizado cartográfico."""

from __future__ import annotations

import geopandas as gpd
import pandas as pd
from shapely.geometry import box

from app.utils.map_renderer import (
    DETECTION_LAYER_NAME,
    RISK_LAYER_NAME,
    add_detection_layer,
    build_risk_legend_html,
    detection_radius,
    render_folium_map,
    risk_fill_opacity,
    risk_stroke_weight,
)


def _gdf_una_celda(prob: float = 0.8, nivel: str = "alto") -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {
            "cell_id": ["VP-001"],
            "probabilidad": [prob],
            "nivel_riesgo": [nivel],
            "temperatura": [34.0],
            "humedad_relativa": [20.0],
            "velocidad_viento": [35.0],
            "regla_30_30_30": [1],
        },
        geometry=[box(-71.58, -33.05, -71.57, -33.04)],
        crs="EPSG:4326",
    )


def test_risk_fill_opacity_grows_with_probability():
    """Una celda al 10 % y otra al 90 % no pueden pesar visualmente igual.

    El renderizador anterior usaba fill_opacity=0.45 fijo para todas.
    """
    assert risk_fill_opacity(0.9) > risk_fill_opacity(0.5) > risk_fill_opacity(0.1)


def test_risk_fill_opacity_stays_within_visible_range():
    """Ninguna celda queda invisible ni totalmente opaca sobre el basemap."""
    for prob in (-1.0, 0.0, 0.5, 1.0, 2.0):
        assert 0.15 <= risk_fill_opacity(prob) <= 0.75


def test_risk_stroke_weight_grows_with_probability():
    assert risk_stroke_weight(1.0) > risk_stroke_weight(0.0)


def test_detection_radius_grows_with_frp():
    """El tamaño del foco refleja su potencia radiativa."""
    assert detection_radius(300.0, 324.0) > detection_radius(10.0, 324.0)
    assert detection_radius(10.0, 324.0) > detection_radius(0.7, 324.0)


def test_detection_radius_compresses_three_orders_of_magnitude():
    """La escala logarítmica mantiene los focos chicos visibles.

    En escala lineal un foco de 0,7 MW junto a uno de 324 MW sería
    indistinguible de cero.
    """
    chico = detection_radius(0.7, 324.0)
    grande = detection_radius(324.0, 324.0)
    assert chico >= 2.5
    assert grande <= 8.5


def test_detection_radius_handles_degenerate_frp():
    assert detection_radius(0.0, 0.0) == 2.5
    assert detection_radius(5.0, 0.0) == 2.5


def test_build_risk_legend_html_covers_the_three_levels_and_detections():
    from app.theme.tokens import RISK_LEVELS, risk_palette

    html = build_risk_legend_html()
    assert "Alto" in html and "Medio" in html and "Bajo" in html
    for nivel in RISK_LEVELS:
        assert risk_palette(nivel).surface in html, (
            f"La leyenda no muestra el color con el que el mapa pinta el nivel {nivel}"
        )
    assert "FRP" in html


def test_legend_is_a_leaflet_control_not_a_floating_div():
    """La leyenda se ancla al mapa, no a la ventana.

    Con `position: fixed` la leyenda se veía al abrir el HTML del mapa suelto
    pero desaparecía dentro del iframe de st_folium, que es donde vive en la
    app. Un L.control se posiciona contra el contenedor del mapa.
    """
    html = render_folium_map(_gdf_una_celda()).get_root().render()
    assert "L.control({position: 'bottomright'})" in html
    assert "sapi-risk-legend" in html
    assert "position:fixed" not in build_risk_legend_html()


def test_add_detection_layer_skips_when_no_data():
    """Sin el asset de focos el mapa de riesgo sigue funcionando."""
    import folium

    m = folium.Map(location=(-33.07, -71.40))
    assert add_detection_layer(m, pd.DataFrame()) is False


def test_add_detection_layer_reports_success_with_data():
    import folium

    m = folium.Map(location=(-33.07, -71.40))
    focos = pd.DataFrame(
        {"latitude": [-33.05, -33.06], "longitude": [-71.50, -71.40], "frp": [1.2, 300.0]}
    )
    assert add_detection_layer(m, focos) is True


def test_render_folium_map_with_data():
    gdf = _gdf_una_celda()
    m = render_folium_map(gdf)
    assert m is not None
    m_selected = render_folium_map(gdf, selected_cell_id="VP-001")
    assert m_selected is not None


def test_render_folium_map_includes_both_named_layers():
    """Riesgo y focos reales van en capas separadas y apagables.

    Son fechas distintas: el escenario es 2025-02, los focos son 2024-02-03.
    Mezclarlos sin poder separarlos sería engañoso.
    """
    html = render_folium_map(_gdf_una_celda()).get_root().render()
    assert RISK_LAYER_NAME in html
    assert DETECTION_LAYER_NAME in html


def test_render_folium_map_can_omit_detections():
    html = render_folium_map(_gdf_una_celda(), show_detections=False).get_root().render()
    assert DETECTION_LAYER_NAME not in html


def test_render_folium_map_empty():
    gdf = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    m = render_folium_map(gdf)
    assert m is not None


def test_cell_center_empty_geometry():
    """Una geometría vacía cae al centro de la grilla, no a un punto suelto.

    Antes eran coordenadas literales que quedaron fuera de la grilla al
    ensancharse: el mapa sin datos encuadraba otra zona.
    """
    from shapely.geometry import Polygon

    from app.utils.grid import contains
    from app.utils.map_renderer import _cell_center

    lat, lon = _cell_center(Polygon())
    assert contains(lat, lon)


def test_cell_center_point():
    from shapely.geometry import Point

    from app.utils.map_renderer import _cell_center

    lat, lon = _cell_center(Point(-71.5, -33.04))
    assert lat == -33.04
    assert lon == -71.5

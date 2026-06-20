"""Pruebas de la aplicación Streamlit."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import geopandas as gpd
from shapely.geometry import box

from app.app import SapiDashboard


def test_export_report_pdf():
    dashboard = SapiDashboard()
    gdf = gpd.GeoDataFrame(
        {
            "cell_id": ["VP-001", "VP-002"],
            "probabilidad": [0.8, 0.2],
            "nivel_riesgo": ["alto", "bajo"],
        },
        geometry=[box(-71.58, -33.05, -71.57, -33.04), box(-71.57, -33.05, -71.56, -33.04)],
        crs="EPSG:4326",
    )

    with patch.object(dashboard.query, "get_spatial_risk_map", return_value=gdf):
        report = dashboard.export_report_pdf(date.today())

    content = report.decode("utf-8")
    assert "S.A.P.I." in content
    assert "Riesgo alto" in content


@patch("app.app.fetch_spatial_risk_map")
@patch("app.app.st_folium")
@patch("app.app.render_folium_map")
def test_render_folium_map_method(mock_render, mock_st_folium, mock_fetch):
    mock_render.return_value = MagicMock()
    mock_fetch.return_value = gpd.GeoDataFrame(
        {"cell_id": ["VP-001"], "probabilidad": [0.5], "nivel_riesgo": ["medio"]},
        geometry=[box(-71.58, -33.05, -71.57, -33.04)],
        crs="EPSG:4326",
    )
    dashboard = SapiDashboard()
    dashboard.render_folium_map(date.today())

    mock_render.assert_called_once()
    mock_st_folium.assert_called_once()


def test_dashboard_init():
    dashboard = SapiDashboard()
    assert dashboard.query is not None


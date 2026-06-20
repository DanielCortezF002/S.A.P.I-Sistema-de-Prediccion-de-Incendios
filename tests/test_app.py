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
            "regla_30_30_30": [1, 0],
        },
        geometry=[box(-71.58, -33.05, -71.57, -33.04), box(-71.57, -33.05, -71.56, -33.04)],
        crs="EPSG:4326",
    )

    with patch("app.app._cached_date_range", return_value=(date(2025, 2, 9), date(2025, 2, 15))):
        with patch.object(dashboard.query, "get_spatial_risk_map", return_value=gdf):
            report = dashboard.export_report_pdf(date(2025, 2, 15))

    content = report.decode("utf-8")
    assert "S.A.P.I." in content
    assert "Riesgo alto" in content


@patch("app.app._cached_date_range", return_value=(date(2025, 2, 9), date(2025, 2, 15)))
@patch("app.app.st_folium")
@patch("app.app.render_folium_map")
def test_render_folium_map_method(mock_render, mock_st_folium, _mock_range):
    mock_render.return_value = MagicMock()
    gdf = gpd.GeoDataFrame(
        {"cell_id": ["VP-001"], "probabilidad": [0.5], "nivel_riesgo": ["medio"]},
        geometry=[box(-71.58, -33.05, -71.57, -33.04)],
        crs="EPSG:4326",
    )
    dashboard = SapiDashboard()
    with patch.object(dashboard.query, "get_spatial_risk_map", return_value=gdf):
        dashboard.render_folium_map(date(2025, 2, 15))

    mock_render.assert_called_once()
    mock_st_folium.assert_called_once()


def test_dashboard_init():
    dashboard = SapiDashboard()
    assert dashboard.query is not None


@patch("app.app._get_query")
def test_cached_date_range_fallback(mock_get_query: MagicMock) -> None:
    from app.app import DEMO_FALLBACK_END, DEMO_FALLBACK_START, _cached_date_range

    mock_get_query.return_value.get_available_date_range.return_value = (None, None)
    _cached_date_range.clear()
    assert _cached_date_range() == (DEMO_FALLBACK_START, DEMO_FALLBACK_END)


@patch("app.app._get_query")
def test_cached_available_dates_fallback(mock_get_query: MagicMock) -> None:
    from app.app import DEMO_FALLBACK_START, _cached_available_dates

    mock_get_query.return_value.get_available_dates.return_value = []
    _cached_available_dates.clear()
    dates = _cached_available_dates()
    assert len(dates) == 7
    assert dates[0] == DEMO_FALLBACK_START


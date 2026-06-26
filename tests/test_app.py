"""Pruebas de la aplicación Streamlit."""

from __future__ import annotations

from datetime import date, timedelta
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
    assert "Recall XGBoost" in content
    assert "AUC-ROC" in content


def test_export_report_empty():
    dashboard = SapiDashboard()
    empty = gpd.GeoDataFrame(
        columns=["cell_id", "probabilidad", "nivel_riesgo"],
        geometry=[],
        crs="EPSG:4326",
    )
    with patch("app.app._cached_date_range", return_value=(date(2025, 2, 9), date(2025, 2, 15))):
        with patch.object(dashboard.query, "get_spatial_risk_map", return_value=empty):
            report = dashboard.export_report_pdf(date(2025, 2, 9))
    assert b"Celdas analizadas: 0" in report


@patch("app.app._cached_date_range", return_value=(date(2025, 2, 9), date(2025, 2, 15)))
@patch("app.app.st_folium")
@patch("app.app.render_folium_map")
def test_render_folium_map_fetches_gdf_when_missing(mock_render, mock_st_folium, _mock_range):
    mock_render.return_value = MagicMock()
    mock_st_folium.return_value = {}
    gdf = gpd.GeoDataFrame(
        {"cell_id": ["VP-001"], "probabilidad": [0.5], "nivel_riesgo": ["medio"]},
        geometry=[box(-71.58, -33.05, -71.57, -33.04)],
        crs="EPSG:4326",
    )
    dashboard = SapiDashboard()
    with patch.object(dashboard.query, "get_spatial_risk_map", return_value=gdf) as mock_query:
        dashboard.render_folium_map(date(2025, 2, 15))

    mock_query.assert_called_once_with(date(2025, 2, 15))
    mock_render.assert_called_once_with(gdf, selected_cell_id=None)


@patch("app.app._cached_date_range", return_value=(date(2025, 2, 9), date(2025, 2, 15)))
@patch("app.app.st_folium")
@patch("app.app.render_folium_map")
def test_render_folium_map_method(mock_render, mock_st_folium, _mock_range):
    mock_render.return_value = MagicMock()
    mock_st_folium.return_value = {"last_object_clicked_tooltip": "VP-001"}
    gdf = gpd.GeoDataFrame(
        {"cell_id": ["VP-001"], "probabilidad": [0.5], "nivel_riesgo": ["medio"]},
        geometry=[box(-71.58, -33.05, -71.57, -33.04)],
        crs="EPSG:4326",
    )
    dashboard = SapiDashboard()
    output = dashboard.render_folium_map(
        date(2025, 2, 15), gdf=gdf, selected_cell_id="VP-001"
    )

    mock_render.assert_called_once_with(gdf, selected_cell_id="VP-001")
    mock_st_folium.assert_called_once()
    assert output["last_object_clicked_tooltip"] == "VP-001"


def test_dashboard_init():
    dashboard = SapiDashboard()
    assert dashboard.query is not None


def test_is_db_connection_error() -> None:
    assert _is_db_connection_error(Exception("connection refused on localhost:5432"))
    assert _is_db_connection_error(Exception("OperationalError: could not connect"))
    assert not _is_db_connection_error(Exception("column fecha does not exist"))


@patch("app.app.st.markdown")
def test_render_risk_legend(mock_markdown: MagicMock) -> None:
    from app.app import _render_risk_legend

    _render_risk_legend()
    mock_markdown.assert_called_once()


@patch("app.app._cached_ml_metrics", return_value={"xgboost": {"recall": 0.78, "auc_roc": 0.83}, "baseline": {"recall": 0.71}})
@patch("app.app.st.sidebar")
def test_render_sidebar_ml_panel(mock_sidebar: MagicMock, _mock_metrics: MagicMock) -> None:
    from app.app import _render_sidebar_ml_panel

    _render_sidebar_ml_panel()
    mock_sidebar.markdown.assert_called_once()
    assert mock_sidebar.metric.call_count == 3


@patch("app.app.st.sidebar")
def test_pick_demo_date_uses_calendar_when_available(mock_sidebar: MagicMock) -> None:
    from app.app import _pick_demo_date

    available = [date(2025, 2, 9), date(2025, 2, 15)]
    mock_sidebar.select_slider.return_value = date(2025, 2, 9)
    mock_sidebar.date_input.return_value = date(2025, 2, 15)
    assert _pick_demo_date(available, date(2025, 2, 9), date(2025, 2, 15)) == date(2025, 2, 15)


@patch("app.app.st.sidebar")
def test_pick_demo_date_falls_back_to_slider(mock_sidebar: MagicMock) -> None:
    from app.app import _pick_demo_date

    available = [date(2025, 2, 9), date(2025, 2, 15)]
    mock_sidebar.select_slider.return_value = date(2025, 2, 9)
    mock_sidebar.date_input.return_value = date(2025, 2, 10)
    assert _pick_demo_date(available, date(2025, 2, 9), date(2025, 2, 15)) == date(2025, 2, 9)
    mock_sidebar.caption.assert_called_once()


@patch("app.app.resolve_date_range", return_value=(date(2025, 2, 9), date(2025, 2, 15)))
def test_cached_date_range_fallback(_mock_range: MagicMock) -> None:
    from app.app import DEMO_FALLBACK_END, DEMO_FALLBACK_START, _cached_date_range

    _cached_date_range.clear()
    assert _cached_date_range() == (DEMO_FALLBACK_START, DEMO_FALLBACK_END)


@patch("app.app.resolve_available_dates")
def test_cached_available_dates_fallback(mock_resolve: MagicMock) -> None:
    from app.app import DEMO_FALLBACK_START, _cached_available_dates

    mock_resolve.return_value = [DEMO_FALLBACK_START + timedelta(days=i) for i in range(7)]
    _cached_available_dates.clear()
    dates = _cached_available_dates()
    assert len(dates) == 7
    assert dates[0] == DEMO_FALLBACK_START


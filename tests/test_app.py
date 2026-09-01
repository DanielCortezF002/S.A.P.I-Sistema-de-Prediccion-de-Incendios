"""Pruebas de la aplicación Streamlit."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import geopandas as gpd
from shapely.geometry import box

from app.app import SapiDashboard
from app.utils.demo_seed import get_all_demo_dates


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
        report = dashboard.export_report_pdf(date(2025, 2, 15), gdf_precargado=gdf)

    content = report.decode("utf-8")
    assert "S.A.P.I." in content
    assert "Riesgo alto" in content
    assert "Recall XGBoost" in content
    assert "AUC-ROC" in content
    assert "data_source=demo_seed" in content
    assert "SAPI_DATA_MODE=demo_seed" in content


def test_export_report_empty():
    dashboard = SapiDashboard()
    empty = gpd.GeoDataFrame(
        columns=["cell_id", "probabilidad", "nivel_riesgo"],
        geometry=[],
        crs="EPSG:4326",
    )
    with patch("app.app._cached_date_range", return_value=(date(2025, 2, 9), date(2025, 2, 15))):
        report = dashboard.export_report_pdf(date(2025, 2, 9), gdf_precargado=empty)
    assert b"Celdas analizadas: 0" in report
    assert b"data_source=demo_seed" in report


@patch("app.app.st.sidebar")
def test_render_data_mode_badge_demo_seed(mock_sidebar: MagicMock) -> None:
    from app.app import _render_data_mode_badge

    _render_data_mode_badge()
    mock_sidebar.markdown.assert_called_once()
    caption = mock_sidebar.caption.call_args[0][0]
    assert "demo_seed" in caption
    assert "no de inferencia XGBoost" in caption


@patch("app.app.st.info")
def test_render_demo_scope_banner_mentions_vp049(mock_info: MagicMock) -> None:
    from app.app import _render_demo_scope_banner

    _render_demo_scope_banner(date(2025, 2, 9), date(2025, 2, 15))
    mock_info.assert_called_once()
    text = mock_info.call_args[0][0]
    assert "VP-049" in text
    assert "escenario sembrado" in text
    assert "no" in text.lower() and "modelo" in text.lower()


@patch("app.app._cached_date_range", return_value=(date(2025, 2, 9), date(2025, 2, 15)))
@patch("app.app.st_folium")
@patch("app.app._build_folium_map")
@patch("app.app.get_demo_gdf")
def test_render_folium_map_fetches_gdf_when_missing(
    mock_get_demo_gdf, mock_build_map, mock_st_folium, _mock_range
):
    mock_build_map.return_value = MagicMock()
    mock_st_folium.return_value = {}
    gdf = gpd.GeoDataFrame(
        {"cell_id": ["VP-001"], "probabilidad": [0.5], "nivel_riesgo": ["medio"]},
        geometry=[box(-71.58, -33.05, -71.57, -33.04)],
        crs="EPSG:4326",
    )
    mock_get_demo_gdf.return_value = gdf
    dashboard = SapiDashboard()
    dashboard.render_folium_map(date(2025, 2, 15))

    mock_get_demo_gdf.assert_called_once_with(date(2025, 2, 15))
    mock_build_map.assert_called_once_with(date(2025, 2, 15))
    mock_st_folium.assert_called_once()


@patch("app.app._cached_date_range", return_value=(date(2025, 2, 9), date(2025, 2, 15)))
@patch("app.app.st_folium")
@patch("app.app._build_folium_map")
def test_render_folium_map_method(mock_build_map, mock_st_folium, _mock_range):
    mock_build_map.return_value = MagicMock()
    mock_st_folium.return_value = {"last_object_clicked_tooltip": "VP-001"}
    gdf = gpd.GeoDataFrame(
        {"cell_id": ["VP-001"], "probabilidad": [0.5], "nivel_riesgo": ["medio"]},
        geometry=[box(-71.58, -33.05, -71.57, -33.04)],
        crs="EPSG:4326",
    )
    dashboard = SapiDashboard()
    output = dashboard.render_folium_map(date(2025, 2, 15), gdf=gdf)

    mock_build_map.assert_called_once_with(date(2025, 2, 15))
    mock_st_folium.assert_called_once()
    assert output["last_object_clicked_tooltip"] == "VP-001"


def test_dashboard_init():
    dashboard = SapiDashboard()
    assert dashboard.query is not None


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
    mock_sidebar.selectbox.return_value = date(2025, 2, 9)
    mock_sidebar.date_input.return_value = date(2025, 2, 15)
    assert _pick_demo_date(available, date(2025, 2, 9), date(2025, 2, 15)) == date(2025, 2, 15)


@patch("app.app.st.sidebar")
def test_pick_demo_date_falls_back_to_slider(mock_sidebar: MagicMock) -> None:
    from app.app import _pick_demo_date

    available = [date(2025, 2, 9), date(2025, 2, 15)]
    mock_sidebar.selectbox.return_value = date(2025, 2, 9)
    mock_sidebar.date_input.return_value = date(2025, 2, 10)
    assert _pick_demo_date(available, date(2025, 2, 9), date(2025, 2, 15)) == date(2025, 2, 9)
    mock_sidebar.caption.assert_called_once()


def test_cached_date_range_from_demo_seed() -> None:
    from app.app import _cached_date_range

    _cached_date_range.clear()
    min_d, max_d = _cached_date_range()
    demo_dates = get_all_demo_dates()
    assert (min_d, max_d) == (demo_dates[0], demo_dates[-1])


def test_cached_available_dates_from_demo_seed() -> None:
    from app.app import _cached_available_dates

    _cached_available_dates.clear()
    dates = _cached_available_dates()
    assert len(dates) == 7
    assert dates == get_all_demo_dates()

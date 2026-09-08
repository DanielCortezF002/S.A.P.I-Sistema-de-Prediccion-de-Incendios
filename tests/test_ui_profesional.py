"""Contratos de la UI profesional: niveles, alertas, tendencia, ops layout."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import geopandas as gpd
import pandas as pd
from shapely.geometry import box

from app.components.risk_level import risk_shape_svg
from app.components.risk_sparkline import daily_max_probability_series
from app.theme.tokens import RISK_LEVELS


def test_risk_shape_svg_uses_distinct_geometry_per_level():
    svgs = {nivel: risk_shape_svg(nivel) for nivel in RISK_LEVELS}
    assert "circle" in svgs["bajo"]
    assert "rect" in svgs["medio"]
    assert "path" in svgs["alto"]
    assert len(set(svgs.values())) == 3


@patch("app.components.risk_sparkline.get_demo_gdf")
@patch("app.components.risk_sparkline.get_all_demo_dates")
def test_sparkline_series_uses_daily_max(
    mock_dates: MagicMock, mock_gdf: MagicMock
) -> None:
    mock_dates.return_value = [date(2025, 2, 14), date(2025, 2, 15)]
    mock_gdf.side_effect = [
        pd.DataFrame({"probabilidad": [0.4, 0.6]}),
        pd.DataFrame({"probabilidad": [0.5, 0.97]}),
    ]
    series = daily_max_probability_series()
    assert series["2025-02-14"] == 0.6
    assert series["2025-02-15"] == 0.97


@patch("streamlit.markdown")
def test_render_ops_header(mock_md: MagicMock) -> None:
    from app.components.ops_layout import render_ops_header

    render_ops_header()
    mock_md.assert_called_once()
    assert "S.A.P.I" in mock_md.call_args[0][0]


@patch("streamlit.markdown")
def test_render_corridor_verified_note(mock_md: MagicMock) -> None:
    from app.components.ops_layout import render_corridor_verified_note

    render_corridor_verified_note()
    mock_md.assert_called_once()
    assert "SUBDERE" in mock_md.call_args[0][0]


@patch("streamlit.markdown")
def test_render_mayor_riesgo_block(mock_md: MagicMock) -> None:
    from app.components.ops_layout import render_mayor_riesgo_block

    gdf = gpd.GeoDataFrame(
        {
            "cell_id": ["VP-038"],
            "temperatura": [32.5],
            "humedad_relativa": [24.0],
            "velocidad_viento": [34.0],
            "nivel_riesgo": ["alto"],
            "probabilidad": [0.97],
            "regla_30_30_30": [1],
        },
        geometry=[box(-71.5, -33.1, -71.49, -33.09)],
        crs="EPSG:4326",
    )
    top = {
        "cell_id": "VP-038",
        "nivel_riesgo": "alto",
        "probabilidad": 0.97,
    }
    render_mayor_riesgo_block(top, gdf)
    mock_md.assert_called_once()
    html = mock_md.call_args[0][0]
    assert "MAYOR RIESGO AHORA" in html
    assert "VP-038" in html
    assert "ALTO" in html
    assert "32.5 °C" in html


@patch("streamlit.markdown")
def test_render_variable_strip(mock_md: MagicMock) -> None:
    from app.components.ops_layout import render_variable_strip

    row = {
        "temperatura": 32.5,
        "humedad_relativa": 24.0,
        "velocidad_viento": 34.0,
    }
    prev = {
        "temperatura": 30.0,
        "humedad_relativa": 25.0,
        "velocidad_viento": 32.0,
    }
    render_variable_strip(row, prev)
    mock_md.assert_called_once()
    html = mock_md.call_args[0][0]
    assert "32.5" in html
    assert "sapi-vcard" in html


@patch("streamlit.markdown")
def test_render_level_summary_chips(mock_md: MagicMock) -> None:
    from app.components.ops_layout import render_level_summary_chips

    gdf = gpd.GeoDataFrame(
        {
            "cell_id": ["VP-001", "VP-002"],
            "nivel_riesgo": ["alto", "bajo"],
        },
        geometry=[box(-71.5, -33.1, -71.49, -33.09), box(-71.48, -33.1, -71.47, -33.09)],
        crs="EPSG:4326",
    )
    render_level_summary_chips(gdf)
    mock_md.assert_called_once()
    assert "sapi-sum-chip" in mock_md.call_args[0][0]


@patch("streamlit.markdown")
def test_render_ops_detail_panel(mock_md: MagicMock) -> None:
    from app.components.ops_layout import render_ops_detail_panel

    gdf = gpd.GeoDataFrame(
        {
            "cell_id": ["VP-038"],
            "temperatura": [32.5],
            "humedad_relativa": [24.0],
            "velocidad_viento": [34.0],
            "nivel_riesgo": ["alto"],
            "probabilidad": [0.97],
            "regla_30_30_30": [1],
        },
        geometry=[box(-71.5, -33.1, -71.49, -33.09)],
        crs="EPSG:4326",
    )
    render_ops_detail_panel(gdf, "VP-038", fecha=date(2025, 2, 15), app_build="demo-test")
    mock_md.assert_called_once()
    html = mock_md.call_args[0][0]
    assert "VP-038" in html
    assert "VARIABLES METEOROLÓGICAS" in html
    assert "REGLA 30-30-30" in html


@patch("streamlit.markdown")
def test_render_four_state_legend(mock_md: MagicMock) -> None:
    from app.components.ops_layout import render_four_state_legend

    render_four_state_legend()
    mock_md.assert_called_once()
    html = mock_md.call_args[0][0]
    assert "sapi-four-states" in html
    assert "BAJO" in html
    assert "ALTO" in html


@patch("streamlit.markdown")
def test_render_operational_verification_footer(mock_md: MagicMock) -> None:
    from app.components.ops_layout import render_operational_verification_footer

    render_operational_verification_footer()
    mock_md.assert_called_once()
    html = mock_md.call_args[0][0]
    assert "VERIFICADO CON DATOS REALES" in html
    assert "12.477" in html


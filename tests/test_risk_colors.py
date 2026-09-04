"""Pruebas de paleta y estilos de selección por riesgo."""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd

from app.utils.risk_colors import (
    format_cell_summary_html,
    format_top_risk_banner_html,
    inject_table_checkbox_colors,
    map_selection_style,
    risk_color,
    style_display_dataframe,
)


def test_risk_color_by_level():
    assert risk_color("bajo") == "#2ecc71"
    assert risk_color("medio") == "#f1c40f"
    assert risk_color("alto") == "#e74c3c"


def test_risk_color_unknown_level_returns_neutral_gray():
    assert risk_color("desconocido") == "#95a5a6"
    assert risk_color(None) == "#95a5a6"


def test_format_cell_summary_html_contains_color():
    row = pd.Series(
        {
            "cell_id": "VP-038",
            "zona_climatica": "Precordillera (continental)",
            "nivel_riesgo": "alto",
            "probabilidad": 0.97,
        }
    )
    html = format_cell_summary_html(row)
    assert "#e74c3c" in html
    assert "VP-038" in html
    assert "97%" in html


def test_format_top_risk_banner_html_alto_shows_bg_color_and_regla_activa():
    top = {
        "cell_id": "VP-038",
        "zona": "Precordillera",
        "nivel_riesgo": "alto",
        "probabilidad": 0.82,
        "regla_30_30_30": True,
    }
    html = format_top_risk_banner_html(top)
    assert "background:#e74c3c" in html
    assert "VP-038" in html
    assert "82%" in html
    assert "ACTIVA" in html


def test_format_top_risk_banner_html_regla_no_activa():
    top = {
        "cell_id": "VP-021",
        "zona": "Urbano",
        "nivel_riesgo": "medio",
        "probabilidad": 0.54,
        "regla_30_30_30": False,
    }
    html = format_top_risk_banner_html(top)
    assert "background:#f1c40f" in html
    assert "no activa" in html


def test_style_display_dataframe_highlights_selected_row():
    df = pd.DataFrame(
        {
            "cell_id": ["VP-001", "VP-002"],
            "nivel_riesgo": ["bajo", "medio"],
            "probabilidad": [0.2, 0.5],
        }
    )
    styled = style_display_dataframe(df, "VP-002")
    html = styled.to_html()
    assert "rgba(241, 196, 15" in html


def test_style_display_dataframe_no_selection_leaves_rows_unstyled():
    df = pd.DataFrame(
        {
            "cell_id": ["VP-001"],
            "nivel_riesgo": ["bajo"],
            "probabilidad": [0.2],
        }
    )
    styled = style_display_dataframe(df, None)
    html = styled.to_html()
    assert "rgba(46, 204, 113" not in html


def test_style_display_dataframe_unknown_level_falls_back_to_bajo_row_style():
    df = pd.DataFrame(
        {
            "cell_id": ["VP-099"],
            "nivel_riesgo": ["extremo"],
            "probabilidad": [0.99],
        }
    )
    styled = style_display_dataframe(df, "VP-099")
    html = styled.to_html()
    assert "rgba(46, 204, 113" in html


def test_map_selection_style_uses_level_stroke():
    style = map_selection_style("bajo", "#2ecc71")
    assert style["stroke"] == "#1a7a42"
    assert style["weight"] == 5


def test_map_selection_style_unknown_level_uses_base_color():
    style = map_selection_style("desconocido", "#abcdef")
    assert style["stroke"] == "#abcdef"
    assert style["fill_opacity"] == 0.78


@patch("streamlit.components.v1.html")
def test_inject_table_checkbox_colors_emits_risk_colored_script(mock_html) -> None:
    df = pd.DataFrame(
        {
            "cell_id": ["VP-001", "VP-002"],
            "nivel_riesgo": ["alto", "bajo"],
        }
    )
    inject_table_checkbox_colors(df, selected_cell_id="VP-001")

    mock_html.assert_called_once()
    script = mock_html.call_args[0][0]
    assert "#e74c3c" in script
    assert "#2ecc71" in script
    assert "VP-001" in script
    assert mock_html.call_args[1]["height"] == 0

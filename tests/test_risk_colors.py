"""Pruebas de paleta y estilos de selección por riesgo."""

from __future__ import annotations

import pandas as pd

from app.utils.risk_colors import (
    format_cell_summary_html,
    map_selection_style,
    risk_color,
    style_display_dataframe,
)


def test_risk_color_by_level():
    assert risk_color("bajo") == "#2ecc71"
    assert risk_color("medio") == "#f1c40f"
    assert risk_color("alto") == "#e74c3c"


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


def test_map_selection_style_uses_level_stroke():
    style = map_selection_style("bajo", "#2ecc71")
    assert style["stroke"] == "#1a7a42"
    assert style["weight"] == 5

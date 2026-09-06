"""Pruebas de paleta y estilos de selección por riesgo.

Estos tests verifican propiedades, no valores. La versión anterior afirmaba
que el nivel medio era `#f1c40f`, lo que pasaba siempre y no detectó nunca que
ese amarillo daba 1,66:1 sobre blanco y por lo tanto era invisible como
relleno de celda. Un test que afirma «el color del banner se lee sobre su
propio fondo» sí lo habría detectado, y es el que está más abajo.
"""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

from app.theme.contrast import LARGE_TEXT_AA, contrast_ratio, parse_hex
from app.theme.tokens import RISK, RISK_LEVELS, RISK_UNKNOWN, ROW_TINT_ALPHA, risk_palette
from app.utils.risk_colors import (
    format_cell_summary_html,
    format_top_risk_banner_html,
    inject_table_checkbox_colors,
    map_selection_style,
    risk_color,
    style_display_dataframe,
)


def _row_tint(nivel: str) -> str:
    """El fragmento `rgba(...)` que debería pintar la fila de este nivel."""
    red, green, blue = parse_hex(RISK[nivel].surface)
    return f"rgba({red}, {green}, {blue}, {ROW_TINT_ALPHA})"


def test_each_risk_level_gets_a_colour_of_its_own():
    """Tres niveles, tres colores distintos, ninguno igual al neutral."""
    colores = [risk_color(nivel) for nivel in RISK_LEVELS]
    assert len(set(colores)) == len(RISK_LEVELS), (
        f"Dos niveles comparten color y son indistinguibles en el mapa: {colores}"
    )
    assert RISK_UNKNOWN.surface not in colores, (
        "Un nivel válido usa el gris reservado para nivel desconocido"
    )


@pytest.mark.parametrize("entrada", ["desconocido", "extremo", "", None])
def test_unrecognised_level_falls_back_to_the_neutral_grey(entrada):
    """Un nivel que el modelo no produce no debe pintarse como si fuera válido."""
    assert risk_color(entrada) == RISK_UNKNOWN.surface


@pytest.mark.parametrize("nivel", RISK_LEVELS)
def test_cell_summary_is_painted_with_the_colour_of_its_level(nivel):
    row = pd.Series(
        {
            "cell_id": "VP-038",
            "zona_climatica": "Precordillera (continental)",
            "nivel_riesgo": nivel,
            "probabilidad": 0.97,
        }
    )
    html = format_cell_summary_html(row)
    assert risk_palette(nivel).surface in html
    assert "VP-038" in html
    assert "Precordillera (continental)" in html
    assert "97%" in html, "La probabilidad debe mostrarse redondeada a porcentaje entero"


@pytest.mark.parametrize("nivel", RISK_LEVELS)
def test_top_risk_banner_uses_the_level_colour_as_solid_background(nivel):
    html = format_top_risk_banner_html(
        {
            "cell_id": "VP-038",
            "zona": "Precordillera",
            "nivel_riesgo": nivel,
            "probabilidad": 0.82,
            "regla_30_30_30": True,
        }
    )
    assert f"background:{risk_palette(nivel).surface}" in html
    assert "VP-038" in html
    assert "82%" in html
    assert nivel.upper() in html


@pytest.mark.parametrize("nivel", RISK_LEVELS)
def test_top_risk_banner_text_is_legible_over_its_own_background(nivel):
    """El defecto que motivó el rediseño: el color del banner y el de su texto
    se elegían por separado, y para el amarillo no había texto que funcionara.

    El banner se renderiza a 1.05rem en negrita (~16,8 px), que WCAG 2.1
    clasifica como texto grande, así que el umbral aplicable es 3:1.
    """
    palette = risk_palette(nivel)
    ratio = contrast_ratio(palette.on_solid, palette.surface)
    assert ratio >= LARGE_TEXT_AA, (
        f"El texto del banner de riesgo {nivel} da {ratio:.2f}:1 sobre su fondo, "
        f"por debajo del mínimo {LARGE_TEXT_AA}:1 para texto grande"
    )


def test_top_risk_banner_distinguishes_active_from_inactive_rule():
    base = {
        "cell_id": "VP-021",
        "zona": "Urbano",
        "nivel_riesgo": "medio",
        "probabilidad": 0.54,
    }
    activa = format_top_risk_banner_html({**base, "regla_30_30_30": True})
    inactiva = format_top_risk_banner_html({**base, "regla_30_30_30": False})

    assert "ACTIVA" in activa
    assert "no activa" in inactiva
    assert "ACTIVA" not in inactiva


def test_selected_row_is_tinted_with_its_own_level_not_a_generic_highlight():
    df = pd.DataFrame(
        {
            "cell_id": ["VP-001", "VP-002"],
            "nivel_riesgo": ["bajo", "medio"],
            "probabilidad": [0.2, 0.5],
        }
    )
    html = style_display_dataframe(df, "VP-002").to_html()
    assert _row_tint("medio") in html, "La fila seleccionada no lleva el tinte de su nivel"
    assert _row_tint("bajo") not in html, "Se tiñó también una fila no seleccionada"


def test_no_selection_leaves_every_row_unstyled():
    df = pd.DataFrame(
        {"cell_id": ["VP-001"], "nivel_riesgo": ["bajo"], "probabilidad": [0.2]}
    )
    html = style_display_dataframe(df, None).to_html()
    for nivel in RISK_LEVELS:
        assert _row_tint(nivel) not in html


def test_selected_row_of_unknown_level_falls_back_to_bajo_not_to_grey():
    """El resalte solo dice «esta es la fila seleccionada».

    Si cayera al gris neutral se leería como fila deshabilitada, que es
    justo lo contrario de lo que el resalte quiere comunicar.
    """
    df = pd.DataFrame(
        {"cell_id": ["VP-099"], "nivel_riesgo": ["extremo"], "probabilidad": [0.99]}
    )
    html = style_display_dataframe(df, "VP-099").to_html()
    assert _row_tint("bajo") in html
    assert RISK_UNKNOWN.surface not in html


@pytest.mark.parametrize("nivel", RISK_LEVELS)
def test_map_selection_outlines_the_cell_with_a_darker_shade_of_its_level(nivel):
    """El resalte de selección tiene que leerse contra el propio relleno."""
    from app.theme.contrast import relative_luminance

    palette = risk_palette(nivel)
    style = map_selection_style(nivel, palette.surface)

    assert style["stroke"] == palette.stroke
    assert relative_luminance(palette.stroke) < relative_luminance(palette.surface), (
        f"El borde de selección de riesgo {nivel} no es más oscuro que su relleno"
    )
    assert style["weight"] > 1, "El borde de selección debe ser más grueso que el normal"
    assert style["marker_color"] == palette.stroke


def test_map_selection_of_unknown_level_keeps_the_colour_it_was_given():
    style = map_selection_style("desconocido", "#abcdef")
    assert style["stroke"] == "#abcdef"
    assert 0 < style["fill_opacity"] <= 1


@patch("streamlit.components.v1.html")
def test_checkbox_script_carries_one_colour_per_row_in_table_order(mock_html) -> None:
    df = pd.DataFrame(
        {
            "cell_id": ["VP-001", "VP-002", "VP-003"],
            "nivel_riesgo": ["alto", "bajo", "medio"],
        }
    )
    inject_table_checkbox_colors(df, selected_cell_id="VP-001")

    mock_html.assert_called_once()
    script = mock_html.call_args[0][0]

    esperado = [risk_palette(n).surface for n in ["alto", "bajo", "medio"]]
    assert f"const colors = {esperado}".replace("'", '"') in script.replace("'", '"'), (
        "El script debe llevar los colores en el mismo orden que las filas"
    )
    assert '"VP-001"' in script
    assert mock_html.call_args[1]["height"] == 0, (
        "El componente solo inyecta un script: si ocupa alto, empuja el layout"
    )

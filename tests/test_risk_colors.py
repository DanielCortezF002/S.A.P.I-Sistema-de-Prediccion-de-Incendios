"""Pruebas de paleta y estilo de selección en el mapa.

Estos tests verifican propiedades, no valores. La versión anterior afirmaba
que el nivel medio era `#f1c40f`, lo que pasaba siempre y no detectó nunca que
ese amarillo daba 1,66:1 sobre blanco y por lo tanto era invisible como
relleno de celda.

06-09-2026: se eliminaron los tests de `format_cell_summary_html`,
`format_top_risk_banner_html` y `style_display_dataframe` — esas funciones se
quitaron de `app/utils/risk_colors.py` por no tener caller de producción
(`render_ops_detail_panel`/`render_mayor_riesgo_block` las reemplazan). El
contraste de texto sobre fondo sólido que cubrían sigue verificado en
`tests/test_theme.py` sobre `RiskPalette` directamente.
"""

from __future__ import annotations

import pytest

from app.theme.tokens import RISK_LEVELS, RISK_UNKNOWN
from app.utils.risk_colors import map_selection_style, risk_color


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
def test_map_selection_outlines_the_cell_with_a_darker_shade_of_its_level(nivel):
    """El resalte de selección tiene que leerse contra el propio relleno."""
    from app.theme.contrast import relative_luminance
    from app.theme.tokens import risk_palette

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


def test_stylesheet_sets_touch_targets_without_dataframe_checkbox_hack() -> None:
    """Fase 3: selección por tarjetas; el MutationObserver de checkboxes ya no existe."""
    from app.theme.css import build_stylesheet
    from app.theme.tokens import TOUCH_TARGET_PX

    css = build_stylesheet()
    assert f"--sapi-touch-target: {TOUCH_TARGET_PX}px" in css
    assert "min-height: var(--sapi-touch-target)" in css
    assert "MutationObserver" not in css
    assert 'data-testid="stDataFrame"' not in css

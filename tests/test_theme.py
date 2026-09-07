"""Pruebas del sistema de diseño: tokens, contraste y sincronía con Streamlit.

El bloque `[theme]` de `.streamlit/config.toml` no lo lee Python en runtime —
lo consume Streamlit al arrancar — así que nada impedía que se desincronizara
del CSS de la app. Eso ya pasó una vez: el comentario del archivo describía una
dirección de diseño distinta de la que el CSS aplicaba. Acá se ancla.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from app.theme import tokens as t
from app.theme.contrast import (
    GRAPHIC_AA,
    LARGE_TEXT_AA,
    TEXT_AA,
    composite_over,
    contrast_ratio,
    parse_hex,
    relative_luminance,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
BLANCO = "#ffffff"

TODOS_LOS_NIVELES = list(t.RISK.items()) + [("desconocido", t.RISK_UNKNOWN)]

# Déficits de contraste medidos que quedan pendientes de decisión del equipo,
# con su valor actual. Son anteriores a esta fase y no se corrigieron acá
# porque el alcance aprobado fue "solo el ámbar del nivel medio".
#
# Si corregís uno, este test falla: sacá la entrada de este diccionario y el
# umbral general de más abajo pasa a cubrirlo. Es deliberado — así un arreglo
# no queda sin registrar y un déficit no queda sin medir.
DEFICITS_PENDIENTES: dict[str, float] = {
    # El verde y el gris no llegan a 3:1 como relleno. A diferencia del ámbar,
    # que era invisible, estos círculos se perciben por su borde: 5,38:1 y
    # 4,83:1 sobre el mapa base. Corregir el relleno implicaría oscurecer el
    # verde del semáforo, que es lo que el alcance aprobado excluyó.
    "surface:bajo": 2.10,
    "surface:desconocido": 2.56,
}


# ──────────────────────────────────────────────
# El módulo de contraste
# ──────────────────────────────────────────────
def test_contrast_of_black_on_white_is_the_theoretical_maximum():
    assert contrast_ratio("#000000", BLANCO) == pytest.approx(21.0, abs=0.01)


def test_a_colour_has_no_contrast_against_itself():
    assert contrast_ratio("#3b6ea5", "#3b6ea5") == pytest.approx(1.0)


def test_contrast_does_not_depend_on_which_colour_is_the_background():
    assert contrast_ratio("#20242b", "#faf9f6") == pytest.approx(
        contrast_ratio("#faf9f6", "#20242b")
    )


def test_shorthand_and_longhand_hex_parse_to_the_same_colour():
    assert parse_hex("#fff") == parse_hex("#ffffff") == (255, 255, 255)


@pytest.mark.parametrize("invalido", ["", "#12345", "azul", "#gggggg"])
def test_malformed_colours_are_rejected_rather_than_silently_mangled(invalido):
    with pytest.raises(ValueError):
        parse_hex(invalido)


def test_luminance_orders_colours_from_black_to_white():
    assert (
        relative_luminance("#000000")
        < relative_luminance("#808080")
        < relative_luminance("#ffffff")
    )


def test_full_opacity_composite_returns_the_foreground_unchanged():
    assert composite_over("#c8720d", 1.0, BLANCO) == "#c8720d"


def test_zero_opacity_composite_returns_the_background_unchanged():
    assert composite_over("#c8720d", 0.0, BLANCO) == BLANCO


def test_composite_of_a_translucent_tint_lands_between_both_colours():
    """El tinte de la fila resaltada se dibuja con alfa, así que su contraste
    real depende de lo que tenga debajo y no del color nominal."""
    tinte = composite_over("#000000", 0.5, BLANCO)
    assert relative_luminance("#000000") < relative_luminance(tinte)
    assert relative_luminance(tinte) < relative_luminance(BLANCO)


# ──────────────────────────────────────────────
# Sincronía con la configuración de Streamlit
# ──────────────────────────────────────────────
def test_theme_config_matches_tokens():
    """El `[theme]` de Streamlit y los tokens describen la misma paleta."""
    config = tomllib.loads(
        (REPO_ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    )
    theme = config["theme"]

    assert theme["primaryColor"] == t.ACCENT
    assert theme["backgroundColor"] == t.SURFACE_PAGE
    assert theme["secondaryBackgroundColor"] == t.SURFACE_MUTED
    assert theme["textColor"] == t.TEXT_PRIMARY
    assert theme["base"] == "light", (
        "Los umbrales de contraste de los tokens se calculan contra fondos claros"
    )


def test_stylesheet_is_built_from_tokens_and_leaves_no_stray_colour():
    """Ningún color del CSS debe estar escrito a mano en `app/theme/css.py`."""
    import re

    from app.theme.css import build_stylesheet

    for mode, apariencia in t.APPEARANCES.items():
        css = build_stylesheet(mode)
        conocidos = {
            apariencia.surface_page,
            apariencia.surface_muted,
            apariencia.surface_card,
            apariencia.border_card,
            apariencia.border_subtle,
            apariencia.text_primary,
            apariencia.accent,
            t.SURFACE_SIDEBAR,
            t.TEXT_ON_SIDEBAR,
            t.TEXT_ON_SIDEBAR_MUTED,
            t.TEXT_ON_SIDEBAR_LABEL,
            t.RISK_UNKNOWN.surface,
            *(p.surface for p in t.RISK.values()),
            *(p.text for p in t.RISK.values()),
            *(p.stroke for p in t.RISK.values()),
        }
        encontrados = {m.lower() for m in re.findall(r"#[0-9a-fA-F]{6}", css)}
        huerfanos = encontrados - {c.lower() for c in conocidos}
        assert not huerfanos, (
            f"Colores en el CSS ({mode}) que no salen de un token: {huerfanos}"
        )


def test_stylesheet_carries_the_accessible_touch_target():
    from app.theme.css import build_stylesheet

    assert t.TOUCH_TARGET_PX >= 44, "WCAG 2.5.5 pide 44 px de lado mínimo"
    assert f"--sapi-touch-target: {t.TOUCH_TARGET_PX}px" in build_stylesheet()


def test_stylesheet_applies_type_scale_to_headings():
    """La escala tipográfica de tokens alimenta h1–h4 y el cuerpo, no solo :root."""
    from app.theme.css import build_stylesheet

    css = build_stylesheet()
    assert "font-size: var(--sapi-font-display-size)" in css
    assert "font-size: var(--sapi-font-body-size)" in css
    assert f"--sapi-font-display-size: {t.TYPE_SCALE['display'].size_px}px" in css


def test_stylesheet_switches_page_surface_between_light_and_dark():
    from app.theme.css import build_stylesheet

    claro = build_stylesheet(t.APPEARANCE_CLARO)
    oscuro = build_stylesheet(t.APPEARANCE_OSCURO)
    assert t.APPEARANCES[t.APPEARANCE_CLARO].surface_page in claro
    assert t.APPEARANCES[t.APPEARANCE_OSCURO].surface_page in oscuro
    assert t.APPEARANCES[t.APPEARANCE_OSCURO].surface_page not in claro


# ──────────────────────────────────────────────
# Umbrales WCAG de la paleta de riesgo
# ──────────────────────────────────────────────
@pytest.mark.parametrize("nivel,palette", TODOS_LOS_NIVELES)
def test_level_name_is_readable_on_the_page_background(nivel, palette):
    """El rol `text` se usa a tamaño normal, así que le aplica 4,5:1."""
    ratio = contrast_ratio(palette.text, t.SURFACE_PAGE)
    assert ratio >= TEXT_AA, (
        f"El texto del nivel {nivel} da {ratio:.2f}:1 sobre el gris de fondo, "
        f"por debajo de {TEXT_AA}:1"
    )


@pytest.mark.parametrize("nivel,palette", TODOS_LOS_NIVELES)
def test_cell_outline_is_visible_against_the_basemap(nivel, palette):
    """El borde del círculo es lo que delimita el componente: WCAG 1.4.11, 3:1."""
    ratio = contrast_ratio(palette.stroke, BLANCO)
    assert ratio >= GRAPHIC_AA, (
        f"El borde del nivel {nivel} da {ratio:.2f}:1 sobre el mapa base, "
        f"por debajo de {GRAPHIC_AA}:1"
    )


@pytest.mark.parametrize("nivel,palette", TODOS_LOS_NIVELES)
def test_solid_background_admits_legible_text(nivel, palette):
    ratio = contrast_ratio(palette.on_solid, palette.surface)
    assert ratio >= LARGE_TEXT_AA, (
        f"El texto sobre el fondo sólido del nivel {nivel} da {ratio:.2f}:1, "
        f"por debajo de {LARGE_TEXT_AA}:1"
    )


@pytest.mark.parametrize("nivel,palette", TODOS_LOS_NIVELES)
def test_cell_fill_reaches_the_graphic_threshold_or_is_a_recorded_deficit(
    nivel, palette
):
    """El relleno codifica el nivel de riesgo, así que le aplica el 3:1 gráfico.

    El ámbar de riesgo medio se corrigió en esta fase (de 1,66:1 a 3,58:1). El
    verde y el gris siguen por debajo y están registrados como pendientes.
    """
    ratio = contrast_ratio(palette.surface, BLANCO)
    clave = f"surface:{nivel}"

    if clave in DEFICITS_PENDIENTES:
        assert ratio == pytest.approx(DEFICITS_PENDIENTES[clave], abs=0.01), (
            f"El relleno del nivel {nivel} cambió a {ratio:.2f}:1. Si lo corregiste, "
            f"sacá '{clave}' de DEFICITS_PENDIENTES."
        )
        return

    assert ratio >= GRAPHIC_AA, (
        f"El relleno del nivel {nivel} da {ratio:.2f}:1 sobre el mapa base, "
        f"por debajo de {GRAPHIC_AA}:1"
    )


@pytest.mark.parametrize("nivel,palette", TODOS_LOS_NIVELES)
def test_highlighted_row_text_is_readable_or_is_a_recorded_deficit(nivel, palette):
    """La fila resaltada se tiñe con alfa sobre la tabla clara.

    Los cuatro niveles llevaban texto claro sobre ese tinte claro y daban
    entre 1,18:1 y 1,34:1 — texto invisible. El tinte se dibuja al 32%, así
    que hay que medirlo compuesto: el nivel alto tiene relleno oscuro pero
    tinte claro, y por eso `row_text` es un rol distinto de `on_solid`.
    """
    tinte = composite_over(palette.surface, t.ROW_TINT_ALPHA, BLANCO)
    ratio = contrast_ratio(palette.row_text, tinte)
    clave = f"row_text:{nivel}"

    if clave in DEFICITS_PENDIENTES:
        assert ratio == pytest.approx(DEFICITS_PENDIENTES[clave], abs=0.01), (
            f"El texto de la fila de nivel {nivel} cambió a {ratio:.2f}:1. Si lo "
            f"corregiste, sacá '{clave}' de DEFICITS_PENDIENTES."
        )
        return

    assert ratio >= TEXT_AA, (
        f"El texto de la fila resaltada de nivel {nivel} da {ratio:.2f}:1 sobre su "
        f"tinte, por debajo de {TEXT_AA}:1"
    )


def test_the_amber_that_motivated_this_phase_is_gone():
    """Regresión puntual: el amarillo original daba 1,66:1 y era invisible."""
    assert t.RISK["medio"].surface != "#f1c40f"
    assert contrast_ratio(t.RISK["medio"].surface, BLANCO) >= GRAPHIC_AA


# ──────────────────────────────────────────────
# Integridad estructural de los tokens
# ──────────────────────────────────────────────
def test_every_declared_level_has_a_palette_and_a_glyph():
    for nivel in t.RISK_LEVELS:
        assert nivel in t.RISK, f"El nivel {nivel} no tiene paleta"
        assert nivel in t.RISK_GLYPH, f"El nivel {nivel} no tiene glifo"
        assert nivel in t.RISK_SHAPE_PATH, f"El nivel {nivel} no tiene forma SVG"
        assert nivel in t.RISK_DESCRIPTION, f"El nivel {nivel} no tiene descripción"


def test_unknown_level_resolves_to_the_neutral_palette():
    assert t.risk_palette("nivel-que-no-existe") is t.RISK_UNKNOWN
    for nivel in t.RISK_LEVELS:
        assert t.risk_palette(nivel) is not t.RISK_UNKNOWN


def test_type_scale_grows_monotonically_from_micro_to_display():
    orden = ["micro", "small", "body", "h2", "h1", "display"]
    tamanos = [t.TYPE_SCALE[nombre].size_px for nombre in orden]
    assert tamanos == sorted(tamanos), f"La escala tipográfica no es monótona: {tamanos}"


def test_every_type_style_has_line_height_above_its_font_size():
    for nombre, estilo in t.TYPE_SCALE.items():
        assert estilo.line_px > estilo.size_px, (
            f"La interlínea de '{nombre}' no deja aire sobre el tamaño de fuente"
        )

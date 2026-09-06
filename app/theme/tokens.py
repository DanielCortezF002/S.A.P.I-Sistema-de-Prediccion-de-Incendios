"""Fuente única de los tokens de diseño de la capa de presentación.

Antes estos valores vivían repartidos en cuatro lugares sin índice: el bloque
`[theme]` de `.streamlit/config.toml`, las ~130 líneas de CSS de `_inject_css()`
en `app/app.py`, los diccionarios paralelos de `app/utils/risk_colors.py` y el
HTML de la leyenda en `app/utils/map_renderer.py`. Cambiar el rojo de riesgo
alto exigía editar tres archivos y verificar a mano que no quedara ninguno
atrás.

La identidad visual no cambió: el azul institucional da 5,04:1 sobre la crema
y el texto principal 14,79:1, así que pasaban WCAG AA con margen y se movieron
tal cual. El único color que cambió es el del nivel de riesgo medio, y por una
razón medible: `#f1c40f` daba 1,66:1 sobre blanco, por debajo del mínimo de
3:1 para elementos gráficos, de modo que el relleno de una celda de riesgo
medio era indistinguible del mapa base. `tests/test_theme.py` verifica los
umbrales y documenta los dos déficits que quedan pendientes de decisión.
"""

from __future__ import annotations

from typing import NamedTuple

# ──────────────────────────────────────────────
# Superficies y texto
# ──────────────────────────────────────────────
SURFACE_PAGE = "#faf9f6"
SURFACE_MUTED = "#f4f1ea"
SURFACE_CARD = "#ffffff"
BORDER_CARD = "#e3ddd0"
BORDER_SUBTLE = "#d7d2c6"
BORDER_HAIRLINE = "#e6e1d6"

TEXT_PRIMARY = "#20242b"
ACCENT = "#3b6ea5"

# Sidebar: navy institucional. `secondaryBackgroundColor` del theme se deja
# neutro porque Streamlit lo aplica también a widgets fuera del sidebar, así
# que el navy se aplica por CSS acotado a la barra.
SURFACE_SIDEBAR = "#1e3348"
TEXT_ON_SIDEBAR = "#eef2f6"
TEXT_ON_SIDEBAR_MUTED = "#a9b7c6"
TEXT_ON_SIDEBAR_LABEL = "#cbd6e1"
SIDEBAR_RULE = "rgba(255,255,255,0.14)"
SIDEBAR_INPUT_FILL = "rgba(255,255,255,0.07)"
SIDEBAR_INPUT_BORDER = "rgba(255,255,255,0.22)"
SIDEBAR_CODE_FILL = "rgba(255,255,255,0.14)"


# ──────────────────────────────────────────────
# Semáforo de riesgo
# ──────────────────────────────────────────────
class RiskPalette(NamedTuple):
    """Los cuatro roles que cumple el color de un nivel de riesgo.

    Separarlos elimina la clase de bug que tenía el amarillo: un mismo hex
    servía de relleno del mapa, de fondo del banner y de acento de texto, y no
    hay un solo color que funcione bien en los tres. Antes esto se parcheaba
    con `RISK_BANNER_TEXT`, un diccionario aparte que existía solo porque el
    amarillo no admitía texto claro encima.
    """

    surface: str
    """Relleno de la celda en el mapa y fondo sólido del banner de alerta."""

    stroke: str
    """Borde del círculo y resalte de la celda seleccionada."""

    text: str
    """Nombre del nivel o cifra sobre fondo claro. Exige 4,5:1."""

    on_solid: str
    """Texto sobre `surface` cuando se usa de fondo. Exige 3:1 (texto grande)."""

    row_text: str
    """Texto de la fila resaltada de la tabla, sobre `surface` con alfa.

    Es un rol propio y no un alias de `on_solid` porque el tinte de la fila se
    dibuja al 32% sobre una tabla clara: aun el nivel alto, cuyo relleno es
    oscuro y admite texto claro, queda claro después de mezclarse y necesita
    texto oscuro. Los cuatro niveles daban entre 1,18:1 y 1,34:1 con texto
    claro sobre su propio tinte, o sea texto invisible.
    """


RISK: dict[str, RiskPalette] = {
    "bajo": RiskPalette(
        surface="#2ecc71",
        stroke="#1a7a42",
        text="#1a7a42",
        on_solid="#0d3d20",
        row_text="#0d3d20",
    ),
    # Ámbar en lugar del amarillo `#f1c40f` original: 3,58:1 sobre blanco
    # contra 1,66:1. El texto encima pasa a ser oscuro porque un ámbar de
    # luminancia media no admite texto claro con 4,5:1.
    "medio": RiskPalette(
        surface="#c8720d",
        stroke="#8f4f06",
        text="#8f4f06",
        on_solid="#3a2400",
        row_text="#3a2400",
    ),
    "alto": RiskPalette(
        surface="#e74c3c",
        stroke="#a93226",
        text="#a93226",
        on_solid="#fdecea",
        row_text="#5c1610",
    ),
}

RISK_UNKNOWN = RiskPalette(
    surface="#95a5a6",
    stroke="#6b7280",
    text="#4b5563",
    on_solid="#1c1712",
    row_text="#1f2937",
)

RISK_LEVELS: tuple[str, ...] = ("bajo", "medio", "alto")

# Opacidad del tinte de la fila resaltada en la tabla.
ROW_TINT_ALPHA = 0.32

# Glifos del semáforo. Redundan el color con una forma nombrada, que es la
# única distinción que le queda a quien no distingue verde de rojo.
RISK_GLYPH: dict[str, str] = {"bajo": "🟢", "medio": "🟠", "alto": "🔴"}

# Capa de focos reales del mapa. Brasa oscura, deliberadamente fuera del
# semáforo para que una detección satelital no se lea como un nivel calculado.
DETECTION_FILL = "#7b241c"
DETECTION_STROKE = "#ffffff"


# ──────────────────────────────────────────────
# Tipografía
# ──────────────────────────────────────────────
FONT_IMPORT_URL = (
    "https://fonts.googleapis.com/css2?family=Public+Sans:wght@400;500;600;700;800&display=swap"
)
FONT_STACK = (
    "'Public Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
)


class TypeStyle(NamedTuple):
    size_px: int
    line_px: int
    weight: int


TYPE_SCALE: dict[str, TypeStyle] = {
    "display": TypeStyle(28, 34, 700),
    "h1": TypeStyle(22, 28, 700),
    "h2": TypeStyle(18, 24, 700),
    "body": TypeStyle(15, 22, 400),
    "small": TypeStyle(13, 18, 400),
    "micro": TypeStyle(11, 15, 500),
}


# ──────────────────────────────────────────────
# Espaciado, radio y áreas de toque
# ──────────────────────────────────────────────
SPACE_PX: dict[str, int] = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24, "xxl": 32}

RADIUS_PX: dict[str, int] = {"control": 4, "card": 6, "banner": 8}

# Mínimo recomendado por WCAG 2.5.5 para un objetivo táctil.
TOUCH_TARGET_PX = 44

# Ancho por debajo del cual el sidebar no tiene espacio para el calendario
# secundario, que duplica al selector de días.
BREAKPOINT_NARROW_PX = 480


def risk_palette(nivel: str) -> RiskPalette:
    """Paleta del nivel indicado; neutral si el nivel no se reconoce."""
    return RISK.get(str(nivel), RISK_UNKNOWN)

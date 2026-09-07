"""Fuente única de los tokens de diseño de la capa de presentación.

Antes estos valores vivían repartidos en cuatro lugares sin índice: el bloque
`[theme]` de `.streamlit/config.toml`, las ~130 líneas de CSS de `_inject_css()`
en `app/app.py`, los diccionarios paralelos de `app/utils/risk_colors.py` y el
HTML de la leyenda en `app/utils/map_renderer.py`. Cambiar el rojo de riesgo
alto exigía editar tres archivos y verificar a mano que no quedara ninguno
atrás.

El fondo de página admite dos apariencias (`claro` / `oscuro`) elegibles en
runtime. El semáforo de riesgo y el navy del sidebar son compartidos: el mapa
no cambia de semántica al cambiar el fondo.
"""

from __future__ import annotations

from typing import NamedTuple

# ──────────────────────────────────────────────
# Apariencia de página (claro / oscuro)
# ──────────────────────────────────────────────
APPEARANCE_CLARO = "claro"
APPEARANCE_OSCURO = "oscuro"
APPEARANCE_MODES: tuple[str, ...] = (APPEARANCE_CLARO, APPEARANCE_OSCURO)


class Appearance(NamedTuple):
    """Superficies y tipografía de la página (no del semáforo ni del sidebar)."""

    surface_page: str
    surface_muted: str
    surface_card: str
    border_card: str
    border_subtle: str
    border_hairline: str
    text_primary: str
    accent: str


APPEARANCES: dict[str, Appearance] = {
    APPEARANCE_CLARO: Appearance(
        surface_page="#eceeef",
        surface_muted="#e0e3e7",
        surface_card="#ffffff",
        border_card="#c9ced4",
        border_subtle="#c0c5cc",
        border_hairline="#d5d9de",
        text_primary="#20242b",
        accent="#3b6ea5",
    ),
    APPEARANCE_OSCURO: Appearance(
        surface_page="#14171b",
        surface_muted="#1c2128",
        surface_card="#242a32",
        border_card="#3a424d",
        border_subtle="#4a5260",
        border_hairline="#323843",
        text_primary="#e8eaed",
        accent="#6b9fd4",
    ),
}


def appearance_tokens(mode: str) -> Appearance:
    """Paleta de página para el modo indicado; cae a claro si no se reconoce."""
    return APPEARANCES.get(mode, APPEARANCES[APPEARANCE_CLARO])


# Alias del modo claro: lo que lee `.streamlit/config.toml` al arrancar y los
# tests de contraste WCAG del semáforo (calculados sobre fondo claro).
_CLARO = APPEARANCES[APPEARANCE_CLARO]
SURFACE_PAGE = _CLARO.surface_page
SURFACE_MUTED = _CLARO.surface_muted
SURFACE_CARD = _CLARO.surface_card
BORDER_CARD = _CLARO.border_card
BORDER_SUBTLE = _CLARO.border_subtle
BORDER_HAIRLINE = _CLARO.border_hairline
TEXT_PRIMARY = _CLARO.text_primary
ACCENT = _CLARO.accent

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

# Glifos del semáforo (legacy / texto plano). La UI profesional usa formas SVG
# (`RISK_SHAPE_PATH`); estos emojis siguen disponibles para captions y tests.
RISK_GLYPH: dict[str, str] = {"bajo": "🟢", "medio": "🟠", "alto": "🔴"}

# Path SVG (viewBox 0 0 24 24) por nivel: círculo / cuadrado / triángulo.
RISK_SHAPE_PATH: dict[str, str] = {
    "bajo": '<circle cx="12" cy="12" r="8"/>',
    "medio": '<rect x="5" y="5" width="14" height="14" rx="2"/>',
    "alto": '<path d="M12 4 L22 20 H2 Z"/>',
}

# Significado operativo de cada nivel (leyenda, chips).
RISK_DESCRIPTION: dict[str, str] = {
    "bajo": "&lt;33% · vigilancia rutinaria",
    "medio": "33–66% · refuerzo preventivo",
    "alto": "≥66% o regla 30-30-30 · prioridad",
}

RISK_LABEL: dict[str, str] = {
    "bajo": "Bajo",
    "medio": "Medio",
    "alto": "Alto",
}

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

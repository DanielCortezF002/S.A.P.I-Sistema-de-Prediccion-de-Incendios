"""Contraste WCAG 2.1 sobre colores hexadecimales.

Existe para que los umbrales de legibilidad sean una invariante verificada por
la suite y no un criterio de gusto. El defecto que lo motivó: el amarillo
`#f1c40f` del nivel de riesgo medio daba 1,66:1 sobre blanco — por debajo del
mínimo de 3:1 para elementos gráficos — y ningún test lo detectaba porque los
tests afirmaban el valor del color, no su legibilidad.

Umbrales de WCAG 2.1 que se usan acá:

- 4,5:1 — texto normal (criterio 1.4.3, nivel AA).
- 3:1 — texto grande (>=18 px, o >=14 px en negrita) y elementos gráficos o
  bordes de componentes de interfaz (criterios 1.4.3 y 1.4.11).
"""

from __future__ import annotations

TEXT_AA = 4.5
LARGE_TEXT_AA = 3.0
GRAPHIC_AA = 3.0


def _channel_to_linear(value: int) -> float:
    """Linealiza un canal sRGB de 0-255 según WCAG."""
    s = value / 255
    return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4


def parse_hex(color: str) -> tuple[int, int, int]:
    """Convierte `#rrggbb` (o `#rgb`) a una tupla RGB de 0-255."""
    raw = color.strip().lstrip("#")
    if len(raw) == 3:
        raw = "".join(ch * 2 for ch in raw)
    if len(raw) != 6:
        raise ValueError(f"Color hexadecimal inválido: {color!r}")
    return (int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16))


def relative_luminance(color: str) -> float:
    """Luminancia relativa de un color, entre 0 (negro) y 1 (blanco)."""
    red, green, blue = parse_hex(color)
    return (
        0.2126 * _channel_to_linear(red)
        + 0.7152 * _channel_to_linear(green)
        + 0.0722 * _channel_to_linear(blue)
    )


def contrast_ratio(foreground: str, background: str) -> float:
    """Razón de contraste entre dos colores, de 1:1 a 21:1."""
    a = relative_luminance(foreground)
    b = relative_luminance(background)
    lighter, darker = max(a, b), min(a, b)
    return (lighter + 0.05) / (darker + 0.05)


def composite_over(color: str, alpha: float, background: str) -> str:
    """Compone `color` con opacidad `alpha` sobre `background`, opaco.

    Necesario para medir los fondos translúcidos: la fila resaltada de la tabla
    y el relleno de las celdas del mapa se dibujan con alfa, así que su
    contraste real depende de lo que tengan debajo, no del color nominal.
    """
    fr, fg, fb = parse_hex(color)
    br, bg, bb = parse_hex(background)
    mix = (
        round(fr * alpha + br * (1 - alpha)),
        round(fg * alpha + bg * (1 - alpha)),
        round(fb * alpha + bb * (1 - alpha)),
    )
    return "#" + "".join(f"{channel:02x}" for channel in mix)

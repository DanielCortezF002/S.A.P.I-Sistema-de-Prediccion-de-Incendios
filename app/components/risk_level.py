"""Niveles de riesgo: forma SVG (accesibilidad, distinta por nivel)."""

from __future__ import annotations

from typing import Optional

from app.theme.tokens import RISK_SHAPE_PATH, risk_palette


def risk_shape_svg(nivel: str, *, fill: Optional[str] = None, size: int = 24) -> str:
    """SVG estático del nivel (círculo / cuadrado / triángulo)."""
    path = RISK_SHAPE_PATH.get(str(nivel), RISK_SHAPE_PATH["bajo"])
    color = fill or risk_palette(str(nivel)).on_solid
    if path.endswith("/>"):
        path = f'{path[:-2]} fill="{color}"/>'
    return (
        f'<svg viewBox="0 0 24 24" width="{size}" height="{size}" '
        f'aria-hidden="true">{path}</svg>'
    )

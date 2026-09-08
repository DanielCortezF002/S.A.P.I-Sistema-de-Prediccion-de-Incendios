"""Paleta de riesgo compartida entre mapa y componentes de detalle.

Los colores ya no viven acá: se leen de `app.theme.tokens`, que es la fuente
única. Este módulo queda como la capa de presentación de esa paleta para el
mapa — el HTML de ficha/tabla y el estilo de dataframe que vivían acá
(`format_cell_summary_html`, `format_top_risk_banner_html`,
`style_display_dataframe`) se eliminaron 06-09-2026: sin caller de
producción desde que `render_ops_detail_panel`/`render_mayor_riesgo_block`
(`app/components/ops_layout.py`) los reemplazaron.
"""

from __future__ import annotations

from typing import Any

from app.theme.tokens import RISK, risk_palette

# Se mantiene para los consumidores que solo necesitan el color de relleno
# (`app.utils.map_renderer`, `scripts/preview_real_cells_map.py`).
RISK_COLORS: dict[str, str] = {nivel: p.surface for nivel, p in RISK.items()}


def risk_color(nivel: str) -> str:
    """Color de relleno según nivel de riesgo; neutral si no se reconoce."""
    return risk_palette(str(nivel)).surface


def map_selection_style(nivel: str, base_color: str) -> dict[str, Any]:
    """Estilo Folium para círculo seleccionado según nivel."""
    palette = RISK.get(str(nivel))
    stroke = palette.stroke if palette else base_color
    return {
        "stroke": stroke,
        "fill_opacity": 0.78,
        "weight": 5,
        "marker_radius": 5,
        "marker_color": stroke,
    }


__all__ = [
    "RISK_COLORS",
    "map_selection_style",
    "risk_color",
    "risk_palette",
]

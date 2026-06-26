"""Paleta de riesgo compartida entre mapa, tabla y ficha de celda."""

from __future__ import annotations

from typing import Any

import pandas as pd

RISK_COLORS: dict[str, str] = {
    "bajo": "#2ecc71",
    "medio": "#f1c40f",
    "alto": "#e74c3c",
}

# Borde más oscuro del mismo tono para resaltar selección en el mapa
RISK_STROKE: dict[str, str] = {
    "bajo": "#1a7a42",
    "medio": "#b7950b",
    "alto": "#a93226",
}

# Fondo de fila seleccionada en la tabla (mismo tono que el radio)
RISK_ROW_STYLE: dict[str, str] = {
    "bajo": "background-color: rgba(46, 204, 113, 0.32); color: #eafaf1",
    "medio": "background-color: rgba(241, 196, 15, 0.32); color: #fef9e7",
    "alto": "background-color: rgba(231, 76, 60, 0.32); color: #fdedec",
}


def risk_color(nivel: str) -> str:
    """Color principal según nivel de riesgo."""
    return RISK_COLORS.get(str(nivel), "#95a5a6")


def format_cell_summary_html(row: pd.Series) -> str:
    """HTML de la ficha superior con color acorde al nivel de riesgo."""
    nivel = str(row["nivel_riesgo"])
    color = risk_color(nivel)
    prob = float(row["probabilidad"])
    return (
        f'<div style="color:{color}; font-size:1.05rem; font-weight:600; '
        f'margin:0.2rem 0 0.5rem 0; padding:0.4rem 0.65rem; '
        f'border-left:4px solid {color}; background:rgba(0,0,0,0.15); '
        f'border-radius:0 4px 4px 0;">'
        f'{row["cell_id"]} · {row["zona_climatica"]} · {nivel} · {prob:.0%}'
        f"</div>"
    )


def style_display_dataframe(
    display_df: pd.DataFrame,
    selected_cell_id: str | None,
) -> pd.io.formats.style.Styler:
    """Resalta la fila seleccionada con el color de su nivel (no rojo genérico)."""

    def _row_style(row: pd.Series) -> list[str]:
        if selected_cell_id and str(row["cell_id"]) == selected_cell_id:
            nivel = str(row["nivel_riesgo"])
            css = RISK_ROW_STYLE.get(nivel, RISK_ROW_STYLE["bajo"])
            return [css] * len(row)
        return [""] * len(row)

    return display_df.style.apply(_row_style, axis=1)


def map_selection_style(nivel: str, base_color: str) -> dict[str, Any]:
    """Estilo Folium para círculo seleccionado según nivel."""
    stroke = RISK_STROKE.get(str(nivel), base_color)
    return {
        "stroke": stroke,
        "fill_opacity": 0.78,
        "weight": 5,
        "marker_radius": 5,
        "marker_color": stroke,
    }


def inject_table_checkbox_colors(
    display_df: pd.DataFrame,
    selected_cell_id: str | None = None,
) -> None:
    """Pinta el ticket de selección con el color de riesgo de la fila activa."""
    import json

    import streamlit.components.v1 as components

    row_colors = [risk_color(str(nivel)) for nivel in display_df["nivel_riesgo"]]
    cell_ids = [str(cid) for cid in display_df["cell_id"]]
    colors_json = json.dumps(row_colors)
    cells_json = json.dumps(cell_ids)
    selected_json = json.dumps(selected_cell_id or "")
    components.html(
        f"""
        <script>
        (function () {{
            const colors = {colors_json};
            const cellIds = {cells_json};
            const selectedId = {selected_json};
            const doc = window.parent.document;

            function paintCheckboxes() {{
                const grids = doc.querySelectorAll('[data-testid="stDataFrame"] [role="grid"]');
                const grid = grids[grids.length - 1];
                if (!grid) return;

                const rows = grid.querySelectorAll('[role="row"]');
                rows.forEach((row, i) => {{
                    if (i === 0) return;
                    const color = colors[i - 1];
                    const cellId = cellIds[i - 1];
                    if (!color) return;

                    const checked = row.getAttribute("aria-selected") === "true"
                        || row.querySelector('input[type="checkbox"]:checked');
                    const active = checked || (selectedId && cellId === selectedId);
                    if (!active) return;

                    row.querySelectorAll("svg path").forEach((path) => {{
                        path.setAttribute("fill", color);
                        path.setAttribute("stroke", color);
                    }});
                    row.querySelectorAll('input[type="checkbox"]').forEach((input) => {{
                        input.style.accentColor = color;
                    }});
                    row.querySelectorAll('[data-baseweb="checkbox"]').forEach((box) => {{
                        box.style.setProperty("--checkbox-accent", color);
                        box.style.borderColor = color;
                        box.style.backgroundColor = color;
                    }});
                }});
            }}

            paintCheckboxes();
            const frames = doc.querySelectorAll('[data-testid="stDataFrame"]');
            const frame = frames[frames.length - 1];
            if (!frame) return;
            const observer = new MutationObserver(paintCheckboxes);
            observer.observe(frame, {{
                subtree: true,
                attributes: true,
                attributeFilter: ["aria-selected", "class"],
                childList: true,
            }});
        }})();
        </script>
        """,
        height=0,
    )

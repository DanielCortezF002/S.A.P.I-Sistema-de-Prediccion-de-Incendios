"""Tabla de detalle por celda y utilidades de selección."""

from __future__ import annotations

import re
from datetime import date
from typing import Any, Optional

import geopandas as gpd
import pandas as pd
import streamlit as st

from utils.cell_zones import zone_label_for_cell

# Orden para nivel_riesgo en la tabla
_NIVEL_ORDER = {"bajo": 0, "medio": 1, "alto": 2}

DISPLAY_COLUMNS = [
    "#",
    "cell_id",
    "zona",
    "probabilidad",
    "nivel_riesgo",
    "temp (°C)",
    "humedad (%)",
    "viento (km/h)",
    "regla 30-30-30",
]

PANEL_HEIGHT_PX = 520
DEFAULT_MAP_PANEL_PCT = 48
SESSION_CELL_KEY = "selected_cell_id"
SESSION_TABLE_EPOCH_KEY = "_table_epoch"

# Etiquetas cortas para que no se trunquen en la tabla
_ZONA_CORTA = {
    "Costa (marítimo)": "Costa",
    "Urbano (transición)": "Urbano",
    "Precordillera (continental)": "Precordillera",
}


def _fmt_regla(val: Any) -> str:
    """Convierte 0/1 a indicador visual para la regla 30-30-30."""
    try:
        return "🟩 Sí" if int(val) == 1 else "🟥 No"
    except (ValueError, TypeError):
        return str(val)


def build_display_dataframe(gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    """Construye tabla ordenada y formateada para el panel de detalle."""
    df = gdf.drop(columns="geometry", errors="ignore").copy()

    # Zona climática (etiqueta corta)
    df["zona"] = df["cell_id"].map(
        lambda cid: _ZONA_CORTA.get(zone_label_for_cell(cid), zone_label_for_cell(cid))
    )

    # Ordenar: zona_climatica → nivel_riesgo (bajo→medio→alto)
    df["_nivel_ord"] = df["nivel_riesgo"].map(_NIVEL_ORDER).fillna(99)
    df["_zona_ord"] = df["zona"].map({"Costa": 0, "Urbano": 1, "Precordillera": 2}).fillna(9)
    df = (
        df.sort_values(["_zona_ord", "_nivel_ord"])
        .drop(columns=["_nivel_ord", "_zona_ord"])
        .reset_index(drop=True)
    )

    # Número de fila tras ordenar
    df.insert(0, "#", range(1, len(df) + 1))

    # --- Formato de columnas ---
    df["probabilidad"] = df["probabilidad"].apply(
        lambda v: f"{float(v):.0%}" if pd.notna(v) else "-"
    )
    df["temp (°C)"] = df["temperatura"].apply(
        lambda v: f"{float(v):.1f}" if pd.notna(v) else "-"
    )
    df["humedad (%)"] = df["humedad_relativa"].apply(
        lambda v: f"{float(v):.1f}" if pd.notna(v) else "-"
    )
    df["viento (km/h)"] = df["velocidad_viento"].apply(
        lambda v: f"{float(v):.1f}" if pd.notna(v) else "-"
    )
    df["regla 30-30-30"] = df["regla_30_30_30"].apply(_fmt_regla)

    return df[DISPLAY_COLUMNS]


def row_index_for_cell(display_df: pd.DataFrame, cell_id: Optional[str]) -> Optional[int]:
    """Índice de fila (posición en display_df) para una celda."""
    if not cell_id:
        return None
    matches = display_df.index[display_df["cell_id"] == cell_id].tolist()
    return int(matches[0]) if matches else None


def table_widget_key(selected_date: date) -> str:
    """Clave del widget tabla; cambia al seleccionar desde mapa para resetear checkboxes."""
    epoch = int(st.session_state.get(SESSION_TABLE_EPOCH_KEY, 0))
    return f"cell_detail_{selected_date.isoformat()}_{epoch}"


def set_selected_cell(cell_id: Optional[str], source: str) -> None:
    """Actualiza celda activa. Mapa/limpiar reinician el widget de tabla."""
    st.session_state[SESSION_CELL_KEY] = cell_id
    if source in ("map", "clear"):
        st.session_state[SESSION_TABLE_EPOCH_KEY] = (
            int(st.session_state.get(SESSION_TABLE_EPOCH_KEY, 0)) + 1
        )


def cell_id_from_folium_output(
    output: Optional[dict[str, Any]],
    valid_cell_ids: set[str],
    gdf: Optional[gpd.GeoDataFrame] = None,
) -> Optional[str]:
    """Extrae cell_id desde click en mapa (tooltip, popup o coordenadas)."""
    if not output:
        return None

    tooltip = (output.get("last_object_clicked_tooltip") or "").strip()
    if tooltip in valid_cell_ids:
        return tooltip

    popup = output.get("last_object_clicked_popup") or ""
    match = re.search(r"VP-\d{3}", popup)
    if match and match.group(0) in valid_cell_ids:
        return match.group(0)

    clicked = output.get("last_object_clicked")
    if gdf is not None and clicked and "lat" in clicked and "lng" in clicked:
        from utils.map_renderer import _cell_center

        click_lat = float(clicked["lat"])
        click_lon = float(clicked["lng"])
        best_id: Optional[str] = None
        best_dist = float("inf")
        for _, row in gdf.iterrows():
            cell_id = str(row.get("cell_id", ""))
            if cell_id not in valid_cell_ids:
                continue
            lat, lon = _cell_center(row.geometry)
            dist = (lat - click_lat) ** 2 + (lon - click_lon) ** 2
            if dist < best_dist:
                best_dist = dist
                best_id = cell_id
        if best_id is not None and best_dist < 0.0004:
            return best_id

    return None

"""Zona climática por celda VP-XXX (alineado con scripts/generate_seed.py)."""

from __future__ import annotations

ZONE_LABELS = {
    "costa": "Costa (marítimo)",
    "urbano": "Urbano (transición)",
    "precordillera": "Precordillera (continental)",
}


def zone_for_col(col: int) -> str:
    """Clasifica columna oeste→este en costa / urbano / precordillera."""
    if col <= 2:
        return "costa"
    if col <= 6:
        return "urbano"
    return "precordillera"


def zone_for_cell_id(cell_id: str) -> str:
    """Deriva zona desde identificador VP-NNN (grilla 5×10)."""
    num = int(cell_id.split("-")[1])
    col = (num - 1) % 10
    return zone_for_col(col)


def zone_label_for_cell(cell_id: str) -> str:
    """Etiqueta legible de zona climática."""
    return ZONE_LABELS[zone_for_cell_id(cell_id)]

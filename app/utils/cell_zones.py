"""Zona climática por celda VP-XXX, derivada de la columna en la grilla.

Las longitudes de cada banda no se escriben a mano: se calculan desde
`app.utils.grid`. Antes estaban documentadas acá como aproximaciones y
describían una grilla 4,1 veces más ancha que la que el código generaba —
la banda "precordillera" quedaba en realidad a 3 km de la banda "costa".
`tests/test_grid.py` verifica que cada banda caiga sobre la comuna que dice
cubrir.
"""

from __future__ import annotations

from app.utils.grid import BASE_LON, COLS, STEP_LON

ZONE_LABELS = {
    "costa": "Costa (marítimo)",
    "urbano": "Urbano (transición)",
    "precordillera": "Precordillera (continental)",
}

# Última columna de cada banda, oeste→este.
_COSTA_LAST_COL = 1
_URBANO_LAST_COL = 6


def zone_for_col(col: int) -> str:
    """Clasifica columna oeste→este en costa / urbano / precordillera.

    Bandas del corredor Viña del Mar – Quilpué:
      Cols 0-1: litoral de Viña del Mar
      Cols 2-6: interfaz urbano-forestal (Quilpué, Peñablanca)
      Cols 7-9: precordillera y cerros orientales (hacia Limache)

    Las longitudes concretas dependen de la grilla; usar `zone_lon_bounds`.
    """
    if col <= _COSTA_LAST_COL:
        return "costa"
    if col <= _URBANO_LAST_COL:
        return "urbano"
    return "precordillera"


def zone_lon_bounds(zone: str) -> tuple[float, float]:
    """Longitudes (oeste, este) que abarca una banda en la grilla actual."""
    cols = [c for c in range(COLS) if zone_for_col(c) == zone]
    if not cols:
        raise KeyError(f"Zona desconocida: {zone}")
    return (
        round(BASE_LON + min(cols) * STEP_LON, 4),
        round(BASE_LON + max(cols) * STEP_LON, 4),
    )


def zone_for_cell_id(cell_id: str) -> str:
    """Deriva zona desde identificador VP-NNN."""
    num = int(cell_id.split("-")[1])
    col = (num - 1) % COLS
    return zone_for_col(col)


def zone_label_for_cell(cell_id: str) -> str:
    """Etiqueta legible de zona climática."""
    return ZONE_LABELS[zone_for_cell_id(cell_id)]

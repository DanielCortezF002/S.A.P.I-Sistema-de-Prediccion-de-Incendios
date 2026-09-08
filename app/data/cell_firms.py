"""Conteo de focos FIRMS 2024-02-03 por celda de la grilla demo (contención)."""

from __future__ import annotations

from functools import lru_cache

from app.data.firms_detections import load_event_detections
from app.utils.grid import STEP_LAT, STEP_LON, cell_center


def _cell_id_for_point(lat: float, lon: float) -> str | None:
    """Asigna un punto a VP-NNN si cae en la caja de media paso alrededor del centro."""
    from app.utils.grid import CELL_COUNT

    for idx in range(1, CELL_COUNT + 1):
        clat, clon = cell_center(idx)
        if abs(lat - clat) <= STEP_LAT / 2 and abs(lon - clon) <= STEP_LON / 2:
            return f"VP-{idx:03d}"
    return None


@lru_cache(maxsize=1)
def firms_counts_by_cell() -> dict[str, int]:
    """Conteo real de detecciones del evento 2024-02-03 por cell_id."""
    focos = load_event_detections()
    counts: dict[str, int] = {}
    if focos.empty:
        return counts
    for row in focos.itertuples():
        cell = _cell_id_for_point(float(row.latitude), float(row.longitude))
        if cell:
            counts[cell] = counts.get(cell, 0) + 1
    return counts


def firms_count_for_cell(cell_id: str) -> int | None:
    """Conteo para una celda; None si no hay asset de focos cargado."""
    focos = load_event_detections()
    if focos.empty:
        return None
    return firms_counts_by_cell().get(str(cell_id), 0)

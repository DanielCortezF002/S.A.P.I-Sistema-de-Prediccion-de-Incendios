"""Re-export de la geometría de grilla — fuente única en `src/geo/grid.py`.

Este módulo existía como la geometría en sí (ver historial de git para el
docstring original); ahora la geometría vive en `src/geo/grid.py` para que
el pipeline batch (`src/procesamiento/`) y `scripts/generate_seed.py` la
compartan con el dashboard en vez de mantener una copia propia (ver
docstring de `src.geo.grid` para el porqué). Nada que ya importe de acá
necesita cambiar.
"""

from __future__ import annotations

from src.geo.grid import (
    BASE_LAT,
    BASE_LON,
    CELL_COUNT,
    CELL_RADIUS_METERS,
    CLICK_MATCH_TOLERANCE_SQ,
    COLS,
    ROWS,
    STEP_LAT,
    STEP_LON,
    cell_center,
    cell_step_meters,
    contains,
    grid_bounds,
    grid_center,
    grid_extent_km,
)

__all__ = [
    "BASE_LAT",
    "BASE_LON",
    "CELL_COUNT",
    "CELL_RADIUS_METERS",
    "CLICK_MATCH_TOLERANCE_SQ",
    "COLS",
    "ROWS",
    "STEP_LAT",
    "STEP_LON",
    "cell_center",
    "cell_step_meters",
    "contains",
    "grid_bounds",
    "grid_center",
    "grid_extent_km",
]

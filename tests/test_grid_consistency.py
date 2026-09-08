"""Ata la geometría del pipeline batch a la fuente única (`src/geo/grid.py`).

Existían dos grillas con el mismo esquema de IDs (VP-001..050) sobre
coordenadas físicas distintas: `app/utils/grid.py` (dashboard, validada al
74,7 % contra NASA FIRMS) y una copia local en `data_processor.py`,
`spatial_joiner.py` y `generate_seed.py` (~9,3 x 4,5 km dentro de Viña del
Mar). Nada lo detectaba porque cada archivo tenía sus propias constantes.
Estas pruebas fallan si alguna de las tres vuelve a divergir de
`src.geo.grid`.
"""

from __future__ import annotations

import runpy

from src.geo.grid import BASE_LAT, BASE_LON, COLS, ROWS, STEP_LAT, STEP_LON, grid_bounds
from src.procesamiento.data_processor import DataProcessor
from src.procesamiento.spatial_joiner import build_local_grid_gdf


def test_data_processor_grid_matches_canonical_bounds() -> None:
    grid = DataProcessor()._build_grid()
    lon_min, _, lat_min, _ = grid_bounds()

    assert grid["min_lon"].min() == lon_min
    assert grid["min_lat"].min() == lat_min
    assert grid["max_lon"].max() == round(lon_min + (COLS - 1) * STEP_LON + STEP_LON, 5)
    assert len(grid) == COLS * ROWS


def test_spatial_joiner_grid_matches_canonical_bounds() -> None:
    gdf = build_local_grid_gdf()
    lon_min, lon_max, lat_min, lat_max = grid_bounds()
    xmin, ymin, xmax, ymax = gdf.total_bounds

    assert round(xmin, 3) == round(lon_min, 3)
    assert round(ymin, 3) == round(lat_min, 3)
    assert len(gdf) == COLS * ROWS


def test_generate_seed_script_imports_canonical_grid() -> None:
    """`scripts/generate_seed.py` no debe volver a tener constantes propias."""
    module_globals = runpy.run_path("scripts/generate_seed.py", run_name="_test_import")

    assert module_globals["BASE_LON"] == BASE_LON
    assert module_globals["BASE_LAT"] == BASE_LAT
    assert module_globals["COLS"] == COLS
    assert module_globals["ROWS"] == ROWS
    assert module_globals["STEP_LON"] == STEP_LON
    assert module_globals["STEP_LAT"] == STEP_LAT

"""Pruebas de `src.geo.grid.all_cells` / `assign_cell`.

Fuente única de asignación punto→celda: antes de esto, tres scripts
(`build_matriz_features_real_sapi32_preview.py`,
`reverificar_hallazgo_2022_12_11.py`, `spatial_joiner.build_local_grid_gdf`)
reconstruían cada uno su propio bucle de contención estricta.
"""

from __future__ import annotations

from src.geo.grid import COLS, ROWS, all_cells, assign_cell


def test_all_cells_returns_one_entry_per_grid_cell() -> None:
    cells = all_cells()
    assert len(cells) == COLS * ROWS
    assert {c["cell_id"] for c in cells} == {f"VP-{i:03d}" for i in range(1, COLS * ROWS + 1)}


def test_assign_cell_resolves_the_centroid_of_every_cell_to_itself() -> None:
    """`cell_center()` devuelve la esquina SO (queda justo en el borde con la
    celda anterior de la fila), así que acá se usa el centroide real
    (esquina + medio paso) para probar un punto sin ambigüedad de borde."""
    for cell in all_cells():
        centroid_lat = (cell["min_lat"] + cell["max_lat"]) / 2
        centroid_lon = (cell["min_lon"] + cell["max_lon"]) / 2
        assert assign_cell(centroid_lat, centroid_lon) == cell["cell_id"]


def test_assign_cell_returns_none_outside_the_grid() -> None:
    assert assign_cell(0.0, 0.0) is None


def test_all_cells_bounds_are_contiguous_without_gaps_or_overlap_on_the_row() -> None:
    """La celda i y la i+1 de la misma fila deben ser exactamente contiguas."""
    cells = {c["cell_id"]: c for c in all_cells()}
    for row in range(ROWS):
        for col in range(COLS - 1):
            idx = row * COLS + col + 1
            a = cells[f"VP-{idx:03d}"]
            b = cells[f"VP-{idx + 1:03d}"]
            assert a["max_lon"] == b["min_lon"]

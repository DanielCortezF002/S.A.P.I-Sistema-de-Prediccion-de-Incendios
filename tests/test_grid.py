"""Pruebas de la geometría de la grilla de análisis.

Estas pruebas existen por un bug concreto: `demo_seed` generaba 50 celdas
sobre 8,4 x 4,0 km dentro de Viña del Mar mientras el dashboard y el
docstring de `cell_zones` afirmaban cubrir un corredor de 34,5 km hasta
Villa Alemana, con tres zonas climáticas. Nada lo detectaba porque ningún
test ataba la geometría a la realidad, solo a otras constantes.

Se verifican dos propiedades que no se pueden satisfacer por accidente: que
cada banda climática caiga sobre la comuna que dice cubrir, y que la grilla
contenga el incendio real que el proyecto usa como caso de estudio.
"""

from __future__ import annotations

import pytest

from app.data.firms_detections import load_event_detections
from app.utils.cell_zones import COMUNA_ZONE, zone_for_col
from app.utils.grid import (
    BASE_LON,
    CELL_RADIUS_METERS,
    CLICK_MATCH_TOLERANCE_SQ,
    COLS,
    STEP_LAT,
    STEP_LON,
    cell_center,
    cell_step_meters,
    contains,
    grid_bounds,
    grid_center,
)

# Coordenadas de referencia de las localidades que el dashboard nombra. La
# banda esperada de cada una vive en `app.utils.cell_zones.COMUNA_ZONE` —
# fuente única compartida con el buscador de comuna del dashboard, para que
# cambiarla ahí no deje este test verificando una banda distinta sin que
# nadie lo note.
_LOCALIDADES = {
    "Viña del Mar": (-33.0245, -71.5518),
    "Quilpué": (-33.0475, -71.4425),
    "Villa Alemana": (-33.0422, -71.3733),
    "Limache": (-33.0153, -71.2661),
}


def _nearest_col(lon: float) -> int:
    """Columna de la grilla más cercana a una longitud."""
    return min(range(COLS), key=lambda c: abs(BASE_LON + c * STEP_LON - lon))


@pytest.mark.parametrize("localidad", sorted(_LOCALIDADES))
def test_grid_zones_land_on_the_comunas_they_claim(localidad: str) -> None:
    """Cada banda climática cubre la comuna que su etiqueta nombra.

    Con la grilla anterior la banda "precordillera" caía a 3 km de la banda
    "costa", ambas dentro de Viña del Mar: las etiquetas eran decorativas.
    """
    _, lon = _LOCALIDADES[localidad]
    assert zone_for_col(_nearest_col(lon)) == COMUNA_ZONE[localidad]


def test_grid_spans_the_full_corridor() -> None:
    """La grilla abarca de la costa de Viña del Mar hasta la precordillera."""
    lon_min, lon_max, _, _ = grid_bounds()
    costa_lon = _LOCALIDADES["Viña del Mar"][1]
    interior_lon = _LOCALIDADES["Limache"][1]

    assert lon_min <= costa_lon <= lon_max
    assert lon_min <= interior_lon <= lon_max


def test_grid_covers_the_real_2024_fire() -> None:
    """La mayoría de los focos reales del 2024-02-03 caen dentro de la grilla.

    Ata la geometría a un hecho externo, no a otra constante del repo. La
    grilla anterior contenía el 17 % de las detecciones; si alguien la
    vuelve a angostar, este test lo detecta.
    """
    focos = load_event_detections()
    assert not focos.empty, "Falta app/data/incendio_2024-02-03.csv"

    dentro = sum(
        contains(row.latitude, row.longitude) for row in focos.itertuples()
    )
    cobertura = dentro / len(focos)
    assert cobertura >= 0.70, (
        f"La grilla solo contiene {cobertura:.0%} de los {len(focos)} focos reales"
    )


def test_villa_alemana_is_inside_the_grid() -> None:
    """Villa Alemana queda dentro, no fuera del borde oriental.

    El análisis point-in-polygon había concluido que ninguna celda caía en
    Villa Alemana. La causa era que la grilla terminaba ~19 km al oeste, no
    que el incendio no hubiera llegado.
    """
    lat, lon = _LOCALIDADES["Villa Alemana"]
    assert contains(lat, lon)


def test_cell_radius_keeps_cells_contiguous() -> None:
    """El radio de dibujo es media separación: celdas contiguas sin solaparse.

    Era un literal de 490 m calibrado para una grilla de paso 1 km. Al
    ensancharse la grilla quedó dibujando puntos diminutos con huecos de
    kilómetros; ahora se deriva del paso.
    """
    step_x, step_y = cell_step_meters()
    assert CELL_RADIUS_METERS == pytest.approx(min(step_x, step_y) / 2, rel=0.01)


def test_click_tolerance_covers_a_whole_cell() -> None:
    """Un clic en cualquier punto de una celda resuelve a esa celda.

    La tolerancia era un literal de 0.0004 grados². Con el paso nuevo eso
    queda por debajo de media celda y habría rechazado clics válidos.
    """
    esquina_sq = (STEP_LON / 2) ** 2 + (STEP_LAT / 2) ** 2
    assert CLICK_MATCH_TOLERANCE_SQ >= esquina_sq


def test_grid_center_is_inside_the_grid() -> None:
    """El centro por defecto del mapa cae dentro de la grilla."""
    lat, lon = grid_center()
    assert contains(lat, lon)


def test_cell_center_matches_the_grid_walk() -> None:
    """`cell_center` reproduce el recorrido fila/columna del generador."""
    assert cell_center(1) == (pytest.approx(grid_bounds()[2]), pytest.approx(BASE_LON))
    # VP-011 abre la segunda fila: misma columna que VP-001, una fila al norte.
    lat_1, lon_1 = cell_center(1)
    lat_11, lon_11 = cell_center(11)
    assert lon_11 == pytest.approx(lon_1)
    assert lat_11 == pytest.approx(lat_1 + STEP_LAT)

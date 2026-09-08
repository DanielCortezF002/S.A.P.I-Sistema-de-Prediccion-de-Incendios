"""Geometría de la grilla de análisis del corredor Viña del Mar – Quilpué.

Fuente única de la geometría de la grilla para TODO el sistema — dashboard
(`app/utils/grid.py` re-exporta este módulo) y pipeline batch
(`src/procesamiento/data_processor.py`, `src/procesamiento/spatial_joiner.py`,
`scripts/generate_seed.py`). Antes convivían dos grillas con el mismo
esquema de IDs (VP-001..050) sobre coordenadas físicas distintas: una
("Grilla A", la de acá) validada contra NASA FIRMS y usada por el
dashboard/demo; otra ("Grilla B") usada por el pipeline batch, PostGIS y el
DEM, cubriendo solo un sector de 9,3 x 4,5 km dentro de Viña del Mar. Si se
conecta `postgis_inference` sin unificarlas, una celda VP-038 significaría
una ubicación en el mapa y otra en la base de datos.

La extensión tiene 74,7 % de cobertura espacial sobre las 348 detecciones
satelitales reales del incendio del 2024-02-03 en la región (ver
`tests/test_grid.py::test_grid_covers_the_real_2024_fire`) — la grilla
anterior cubría el 17 %. Esto es evidencia de cobertura espacial histórica
sobre un único evento, no una validación de que la geometría, resolución o
cantidad de celdas sea la óptima, ni del desempeño de ningún modelo. Es,
sin embargo, el criterio que decidió cuál de las dos grillas se volvió la
única: un sistema de "alerta temprana" no puede sostenerse sobre un
territorio que ve una fracción minoritaria de los incendios reales que dice
cubrir.
"""

from __future__ import annotations

import math

# ──────────────────────────────────────────────
# Constantes de grilla
# ──────────────────────────────────────────────
# Esquina suroeste y paso. Elegidos para que las 10 columnas recorran el
# corredor completo de oeste a este (costa de Viña del Mar → Quilpué →
# precordillera) y las 5 filas cubran la extensión
# norte-sur del incendio de 2024, que llegó hasta lat -33,15.
BASE_LON = -71.58
BASE_LAT = -33.14
COLS = 10
ROWS = 5
STEP_LON = 0.0411
STEP_LAT = 0.035

CELL_COUNT = COLS * ROWS

# Conversión grados → metros. La latitud es prácticamente constante; la
# longitud se contrae con el coseno de la latitud, que a -33° vale ~0,838.
_M_PER_DEG_LAT = 111_132.0
_M_PER_DEG_LON_AT_EQUATOR = 111_320.0


def _m_per_deg_lon(lat: float) -> float:
    """Metros por grado de longitud a una latitud dada."""
    return _M_PER_DEG_LON_AT_EQUATOR * math.cos(math.radians(lat))


def grid_bounds() -> tuple[float, float, float, float]:
    """Extensión de la grilla como (lon_min, lon_max, lat_min, lat_max)."""
    return (
        BASE_LON,
        BASE_LON + (COLS - 1) * STEP_LON,
        BASE_LAT,
        BASE_LAT + (ROWS - 1) * STEP_LAT,
    )


def grid_center() -> tuple[float, float]:
    """Centro geométrico de la grilla como (lat, lon).

    Es también el centro por defecto del mapa cuando no hay celdas que
    encuadrar, para que un GDF vacío no mande la vista a otra parte.
    """
    lon_min, lon_max, lat_min, lat_max = grid_bounds()
    return (round((lat_min + lat_max) / 2, 5), round((lon_min + lon_max) / 2, 5))


def cell_step_meters() -> tuple[float, float]:
    """Separación entre centros de celdas contiguas, en metros (este-oeste, norte-sur)."""
    center_lat, _ = grid_center()
    return (STEP_LON * _m_per_deg_lon(center_lat), STEP_LAT * _M_PER_DEG_LAT)


def grid_extent_km() -> tuple[float, float]:
    """Extensión total de la grilla en kilómetros (este-oeste, norte-sur)."""
    step_x, step_y = cell_step_meters()
    return ((COLS - 1) * step_x / 1000, (ROWS - 1) * step_y / 1000)


def _cell_radius_meters() -> int:
    """Radio de dibujo que deja las celdas contiguas sin superponerse.

    Media separación en el eje más corto: los círculos se tocan en los
    bordes y dejan hueco solo en las esquinas, que es la convención que ya
    usaba el valor anterior (490 m para una separación de ~1 km).
    """
    step_x, step_y = cell_step_meters()
    return int(min(step_x, step_y) / 2)


def _click_tolerance_sq() -> float:
    """Distancia máxima (en grados²) para asignar un clic del mapa a una celda.

    Media diagonal de una celda: un clic en cualquier punto dentro de la
    celda resuelve a esa celda, y uno claramente fuera de la grilla no
    resuelve a ninguna. `cell_table.cell_id_from_folium_output` compara
    contra distancias al cuadrado, así que se expone ya elevada al cuadrado
    para no hacer una raíz por celda en cada clic.
    """
    return (STEP_LON / 2) ** 2 + (STEP_LAT / 2) ** 2


# Valores derivados. Se calculan una vez al importar: dependen solo de las
# constantes de arriba, así que cambiar la grilla los reajusta solo.
CELL_RADIUS_METERS = _cell_radius_meters()
CLICK_MATCH_TOLERANCE_SQ = _click_tolerance_sq()


def cell_center(index: int) -> tuple[float, float]:
    """Centro (lat, lon) de la celda VP-NNN a partir de su número 1-based."""
    col = (index - 1) % COLS
    row = (index - 1) // COLS
    return (
        round(BASE_LAT + row * STEP_LAT, 5),
        round(BASE_LON + col * STEP_LON, 5),
    )


def contains(lat: float, lon: float) -> bool:
    """Indica si un punto cae dentro de la extensión de la grilla."""
    lon_min, lon_max, lat_min, lat_max = grid_bounds()
    return lon_min <= lon <= lon_max and lat_min <= lat <= lat_max


def all_cells() -> list[dict]:
    """Los 50 polígonos de la grilla (bounding box), como lista de dicts.

    Fuente única de "cell_id -> geometría": antes de esto,
    `scripts/build_matriz_features_real_sapi32_preview.py`,
    `scripts/reverificar_hallazgo_2022_12_11.py` y (con otra grilla)
    `src/procesamiento/spatial_joiner.py::build_local_grid_gdf` reconstruían
    cada uno su propia versión de este bucle. Sin dependencia de pandas a
    propósito — `src/geo` es geometría pura (ver docstring del módulo); el
    caller decide si lo envuelve en un DataFrame.
    """
    cells: list[dict] = []
    idx = 1
    for row in range(ROWS):
        for col in range(COLS):
            min_lon = round(BASE_LON + col * STEP_LON, 5)
            min_lat = round(BASE_LAT + row * STEP_LAT, 5)
            cells.append(
                {
                    "cell_id": f"VP-{idx:03d}",
                    "min_lon": min_lon,
                    "min_lat": min_lat,
                    "max_lon": round(min_lon + STEP_LON, 5),
                    "max_lat": round(min_lat + STEP_LAT, 5),
                }
            )
            idx += 1
    return cells


def assign_cell(lat: float, lon: float) -> str | None:
    """cell_id cuyo polígono contiene (lat, lon), o None si cae fuera.

    Contención estricta (sin aproximación por distancia): el mismo criterio
    que ya usaban por separado los scripts listados en `all_cells()`.
    """
    for cell in all_cells():
        if cell["min_lon"] <= lon <= cell["max_lon"] and cell["min_lat"] <= lat <= cell["max_lat"]:
            return cell["cell_id"]
    return None

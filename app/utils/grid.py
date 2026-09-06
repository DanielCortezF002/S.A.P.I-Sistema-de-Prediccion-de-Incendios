"""Geometría de la grilla de análisis del corredor Viña del Mar – Quilpué.

Fuente única de la geometría de la grilla. Antes las constantes vivían en
`demo_seed.py` y todo lo que se deriva de ellas — el radio de dibujo en
`map_renderer.py`, la tolerancia de clic en `cell_table.py` — estaba escrito
a mano en cada archivo, calibrado para una grilla anterior. Cuando la grilla
cambió, esos literales quedaron desincronizados y nada lo detectó: el
dashboard afirmaba cubrir un corredor de 34,5 km mientras generaba celdas
sobre 8,4 x 4,0 km dentro de Viña del Mar. Acá se derivan de las constantes,
de modo que no puedan volver a divergir.

La extensión está verificada contra NASA FIRMS: el 75 % de las 348
detecciones del incendio del 2024-02-03 en la región cae dentro de esta
grilla. La grilla anterior contenía el 17 %. Ver `tests/test_grid.py`.
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

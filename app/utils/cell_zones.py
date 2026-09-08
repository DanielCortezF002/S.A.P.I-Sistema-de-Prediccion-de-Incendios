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

# Comunas de referencia con evidencia real (coordenada verificada + banda que
# le corresponde). Fuente única para el buscador de comuna y para
# `tests/test_grid.py::test_grid_zones_land_on_the_comunas_they_claim`, que
# antes duplicaba esta misma tabla — un cambio acá bastaba para que el test
# seleccionado quedara verificando otra cosa sin que nadie lo notara.
# Restringida a las comunas atadas a una banda climática verificada por
# geometría real; no incluye Valparaíso ni Concón (nombradas en el banner por
# evidencia FIRMS, pero sin columna de grilla verificada) para no inventar una
# precisión que la grilla no tiene.
COMUNA_ZONE: dict[str, str] = {
    "Viña del Mar": "costa",
    "Quilpué": "urbano",
    "Villa Alemana": "urbano",
    "Limache": "precordillera",
}


def comuna_options() -> list[str]:
    """Comunas buscables, orden alfabético."""
    return sorted(COMUNA_ZONE)


def zone_for_comuna(comuna: str) -> str | None:
    """Banda climática de una comuna buscable; None si no se reconoce."""
    return COMUNA_ZONE.get(comuna)


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

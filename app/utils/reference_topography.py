"""Topografía de referencia por celda para la vista v2 (SAPI-61).

El contrato `GET /api/v1/ranking` no transporta elevación ni pendiente por
celda (`CellRanking` está congelado, freeze_check F4c). Esos dos atributos son
estáticos (DEM Copernicus GLO-30) y su tabla congelada del Hito 1,
`artifacts/hito1/reproducibility/dem/grid_topography.csv`, es exactamente la
que `score_current_grid()` consume en modo reproducibilidad (H8). La vista la
lee solo para presentación, etiquetada como "topografía de referencia", sin
importar `src.inference` ni `src.procesamiento`. Si falta o una celda no tiene
cobertura DEM, el valor es `None` y la UI muestra "N/D" — nunca un 0.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Mapping, Optional

_REPO_ROOT = Path(__file__).resolve().parents[2]
REFERENCE_TOPOGRAPHY_CSV = (
    _REPO_ROOT / "artifacts" / "hito1" / "reproducibility" / "dem" / "grid_topography.csv"
)
REFERENCE_TOPOGRAPHY_LABEL = (
    "Topografía de referencia (DEM Copernicus GLO-30, tabla congelada Hito 1)"
)


@dataclass(frozen=True)
class CellTopography:
    """Elevación (m) y pendiente (°) de referencia; `None` = sin cobertura DEM."""

    cell_id: str
    elevation: Optional[float]
    slope: Optional[float]
    dem_available: bool


def _to_float(raw: Optional[str]) -> Optional[float]:
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    try:
        value = float(text)
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def _to_bool(raw: Optional[str]) -> bool:
    return (raw or "").strip().lower() in {"true", "1", "yes"}


def load_reference_topography(
    path: Path = REFERENCE_TOPOGRAPHY_CSV,
) -> Mapping[str, CellTopography]:
    """Lee la tabla congelada; devuelve `{}` si no existe o no es legible.

    Args:
        path: CSV con columnas `cell_id, elevacion, pendiente, dem_disponible`.

    Returns:
        Mapa `cell_id -> CellTopography`. Nunca lanza por archivo ausente.
    """
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
    except (OSError, UnicodeDecodeError, csv.Error):
        return {}
    table: dict[str, CellTopography] = {}
    for row in rows:
        cell_id = (row.get("cell_id") or "").strip()
        if not cell_id:
            continue
        available = _to_bool(row.get("dem_disponible"))
        elevation = _to_float(row.get("elevacion")) if available else None
        slope = _to_float(row.get("pendiente")) if available else None
        table[cell_id] = CellTopography(
            cell_id=cell_id,
            elevation=elevation,
            slope=slope,
            dem_available=available and elevation is not None and slope is not None,
        )
    return table


@lru_cache(maxsize=1)
def reference_topography() -> Mapping[str, CellTopography]:
    """Tabla cacheada por proceso (es estática)."""
    return load_reference_topography()

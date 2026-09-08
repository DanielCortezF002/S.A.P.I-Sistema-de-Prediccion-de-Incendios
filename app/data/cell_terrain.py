"""Topografía DEM por celda — solo si hay rasters materializados en disco.

No importa src.procesamiento. Si data/processed/dem_terrain está vacío,
devuelve available=False (el UI debe decirlo explícitamente).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEM_DIR = _REPO_ROOT / "data" / "processed" / "dem_terrain"


@dataclass(frozen=True)
class CellTerrain:
    elevacion_m: Optional[float]
    pendiente_deg: Optional[float]
    orientacion_deg: Optional[float]
    available: bool
    detail: str


@lru_cache(maxsize=1)
def dem_assets_present() -> bool:
    """True si hay al menos un GeoTIFF usable en dem_terrain."""
    if not _DEM_DIR.exists():
        return False
    return any(_DEM_DIR.rglob("*.tif")) or any(_DEM_DIR.rglob("*.tiff"))


def terrain_for_cell(cell_id: str) -> CellTerrain:
    """Sin rasters en disco no se inventan cotas: available=False."""
    del cell_id  # la grilla B aún no tiene muestreo precomputado en app/
    if not dem_assets_present():
        return CellTerrain(
            elevacion_m=None,
            pendiente_deg=None,
            orientacion_deg=None,
            available=False,
            detail=(
                "DEM Copernicus 30 m no materializado en "
                "data/processed/dem_terrain (sin GeoTIFF). "
                "El pipeline existe en src/; aquí no se simulan cotas."
            ),
        )
    return CellTerrain(
        elevacion_m=None,
        pendiente_deg=None,
        orientacion_deg=None,
        available=False,
        detail=(
            "Hay rasters DEM, pero aún no hay muestreo zonal precomputado "
            "por celda de la grilla B en la capa app/."
        ),
    )

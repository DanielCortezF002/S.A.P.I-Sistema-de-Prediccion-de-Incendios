"""Pendiente y orientación de ladera a partir del DEM, algoritmo Horn (1981).

El DEM descargado por src.ingesta.dem_ingester llega en WGS84/EPSG:4326
(grados): confirmado ~26×31 m de resolución real por píxel, anisotrópica
porque un arco-segundo de longitud pesa menos que uno de latitud a esta
latitud. Calcular pendiente directo sobre esos píxeles sin reproyectar
mezclaría grados con metros — el resultado sale con valores plausibles pero
incorrectos, sin ningún error visible. Por eso este módulo reproyecta
primero a un CRS métrico (UTM 19S / EPSG:32719, correcto para Chile
central ~71.5°O) y recién ahí aplica Horn con z-factor=1.

Fórmulas Horn y la conversión de aspecto a rumbo de brújula verificadas
2026-09-01 contra la documentación oficial de ESRI/GDAL (misma fórmula que
usa gdaldem internamente), no reconstruidas de memoria:
  dz/dx = ((c + 2f + i) - (a + 2d + g)) / (8 * cellsize_x)
  dz/dy = ((g + 2h + i) - (a + 2b + c)) / (8 * cellsize_y)
  aspect = atan2(dz/dy, -dz/dx); áreas planas (sin gradiente) -> aspect = -1
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import calculate_default_transform, reproject

from src.config import DATA_PROCESSED_DIR

UTM_19S_CRS = "EPSG:32719"
# Rango de resolución esperado tras reproyectar (informativo): COP30 declara
# ~30 m; se tolera 25-35 m para no fallar por variación normal del proceso
# de reproyección/resampleo, pero sí detectar un transform mal calculado.
_EXPECTED_PIXEL_SIZE_M = (25.0, 35.0)


@dataclass(frozen=True)
class TerrainResult:
    """Resumen verificable del procesamiento de un DEM."""

    reprojected_dem_path: Path
    slope_path: Path
    aspect_path: Path
    pixel_size_m: tuple[float, float]
    mean_slope_deg: float
    max_slope_deg: float
    mean_aspect_deg: float


def reproject_dem_to_utm(
    src_path: Path,
    dst_path: Path,
    dst_crs: str = UTM_19S_CRS,
) -> tuple[np.ndarray, rasterio.Affine, dict]:
    """Reproyecta un DEM en CRS geográfico a un CRS métrico (bilinear).

    Bilinear, no nearest-neighbor: la elevación es una variable continua,
    no una capa categórica.
    """

    with rasterio.open(src_path) as src:
        if src.crs is None:
            raise ValueError(f"{src_path} no tiene CRS definido")

        transform, width, height = calculate_default_transform(
            src.crs, dst_crs, src.width, src.height, *src.bounds
        )
        profile = src.profile.copy()
        profile.update(crs=dst_crs, transform=transform, width=width, height=height)

        destination = np.empty((height, width), dtype=profile["dtype"])
        reproject(
            source=rasterio.band(src, 1),
            destination=destination,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=transform,
            dst_crs=dst_crs,
            resampling=Resampling.bilinear,
        )

    dst_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(dst_path, "w", **profile) as dst:
        dst.write(destination, 1)

    return destination, transform, profile


def compute_slope_aspect_horn(
    elevation: np.ndarray,
    pixel_size_x: float,
    pixel_size_y: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Pendiente (grados) y orientación (grados, rumbo de brújula) vía Horn (1981).

    Requiere que `elevation` y los tamaños de píxel estén en la misma unidad
    lineal (metros) — no llamar con un raster todavía en grados.

    Bordes: se replica el valor del borde (equivalente a np.pad mode="edge"),
    mismo comportamiento que el default de GDAL. Áreas sin gradiente
    (superficie perfectamente plana) devuelven aspect = -1, igual que
    ESRI/GDAL, en vez de un rumbo arbitrario de atan2(0, 0).
    """

    if pixel_size_x <= 0 or pixel_size_y <= 0:
        raise ValueError(
            "pixel_size_x/y deben ser positivos y estar en metros "
            "(¿se olvidó reproyectar el raster antes de llamar a esta función?)"
        )

    padded = np.pad(elevation.astype("float64"), pad_width=1, mode="edge")
    a, b, c = padded[:-2, :-2], padded[:-2, 1:-1], padded[:-2, 2:]
    d, f = padded[1:-1, :-2], padded[1:-1, 2:]
    g, h, i = padded[2:, :-2], padded[2:, 1:-1], padded[2:, 2:]

    dz_dx = ((c + 2 * f + i) - (a + 2 * d + g)) / (8 * pixel_size_x)
    dz_dy = ((g + 2 * h + i) - (a + 2 * b + c)) / (8 * pixel_size_y)

    slope_deg = np.degrees(np.arctan(np.sqrt(dz_dx**2 + dz_dy**2)))

    raw_aspect = np.degrees(np.arctan2(dz_dy, -dz_dx))
    aspect_deg = np.where(
        raw_aspect < 0,
        90.0 - raw_aspect,
        np.where(raw_aspect > 90.0, 360.0 - raw_aspect + 90.0, 90.0 - raw_aspect),
    )
    flat = (dz_dx == 0) & (dz_dy == 0)
    aspect_deg = np.where(flat, -1.0, aspect_deg)

    return slope_deg.astype("float32"), aspect_deg.astype("float32")


class DemTerrainProcessor:
    """Orquesta reproyección + Horn, con salida verificable en disco."""

    def __init__(self, out_dir: Path | None = None) -> None:
        self.out_dir = out_dir or DATA_PROCESSED_DIR / "dem_terrain"

    def process(self, dem_path: Path) -> TerrainResult:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        stem = dem_path.stem

        reprojected_path = self.out_dir / f"{stem}_utm19s.tif"
        elevation, transform, profile = reproject_dem_to_utm(dem_path, reprojected_path)

        pixel_size_x, pixel_size_y = transform.a, abs(transform.e)
        if not (
            _EXPECTED_PIXEL_SIZE_M[0] <= pixel_size_x <= _EXPECTED_PIXEL_SIZE_M[1]
            and _EXPECTED_PIXEL_SIZE_M[0] <= pixel_size_y <= _EXPECTED_PIXEL_SIZE_M[1]
        ):
            raise ValueError(
                f"Pixel reproyectado ({pixel_size_x:.1f}, {pixel_size_y:.1f}) m fuera del "
                f"rango esperado {_EXPECTED_PIXEL_SIZE_M} — el transform de reproyección "
                "parece incorrecto, revisar antes de calcular pendiente."
            )

        slope_deg, aspect_deg = compute_slope_aspect_horn(elevation, pixel_size_x, pixel_size_y)

        slope_path = self.out_dir / f"{stem}_slope.tif"
        aspect_path = self.out_dir / f"{stem}_aspect.tif"
        single_band_profile = {**profile, "count": 1, "dtype": "float32"}
        with rasterio.open(slope_path, "w", **single_band_profile) as dst:
            dst.write(slope_deg, 1)
        with rasterio.open(aspect_path, "w", **single_band_profile) as dst:
            dst.write(aspect_deg, 1)

        valid_aspect = aspect_deg[aspect_deg >= 0]
        return TerrainResult(
            reprojected_dem_path=reprojected_path,
            slope_path=slope_path,
            aspect_path=aspect_path,
            pixel_size_m=(pixel_size_x, pixel_size_y),
            mean_slope_deg=float(slope_deg.mean()),
            max_slope_deg=float(slope_deg.max()),
            mean_aspect_deg=float(valid_aspect.mean()) if valid_aspect.size else -1.0,
        )

"""Muestreo zonal de topografía real (DEM/pendiente/orientación) sobre la grilla.

Consume los GeoTIFF ya generados por src.procesamiento.dem_terrain
(reprojectado UTM 19S + pendiente/orientación Horn) — no descarga ni
reproyecta nada acá, solo hace la media zonal por celda de 1 km².

La orientación (aspect) es un ángulo circular (0-360°, brújula): promediar
352° y 8° con una media aritmética simple da 180° (sur), que es exactamente
lo opuesto al valor real (~0°, norte). Por eso usa una media circular
(vía seno/coseno), no `array.mean()`.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.mask import mask
from shapely.geometry import box
from shapely.geometry.base import BaseGeometry

ASPECT_FLAT_SENTINEL = -1.0


def _cell_geometries_in_raster_crs(grid: pd.DataFrame, raster_path: Path) -> list[BaseGeometry]:
    """Reproyecta los polígonos de celda (WGS84) al CRS métrico del raster."""

    cells_wgs84 = gpd.GeoSeries(
        [
            box(row.min_lon, row.min_lat, row.max_lon, row.max_lat)
            for row in grid.itertuples()
        ],
        crs="EPSG:4326",
    )
    with rasterio.open(raster_path) as reference:
        target_crs = reference.crs
    return list(cells_wgs84.to_crs(target_crs).geometry)


def _zonal_mean(raster_path: Path, geometries: list[BaseGeometry]) -> list[float]:
    """Media zonal simple (lineal): válida para elevación y pendiente, no para ángulos."""

    values: list[float] = []
    with rasterio.open(raster_path) as src:
        for geom in geometries:
            try:
                clipped, _ = mask(src, [geom], crop=True, nodata=np.nan, filled=True)
            except ValueError:
                # La celda no se solapa con el raster (fuera de cobertura del DEM).
                values.append(float("nan"))
                continue
            pixels = clipped[0]
            pixels = pixels[~np.isnan(pixels)]
            values.append(float(pixels.mean()) if pixels.size else float("nan"))
    return values


def _zonal_circular_mean_deg(raster_path: Path, geometries: list[BaseGeometry]) -> list[float]:
    """Media zonal circular (grados, brújula) para orientación de ladera.

    Excluye ASPECT_FLAT_SENTINEL (superficies planas, sin dirección de
    descenso) antes de promediar.
    """

    values: list[float] = []
    with rasterio.open(raster_path) as src:
        for geom in geometries:
            try:
                clipped, _ = mask(src, [geom], crop=True, nodata=np.nan, filled=True)
            except ValueError:
                values.append(float("nan"))
                continue
            pixels = clipped[0]
            pixels = pixels[~np.isnan(pixels)]
            pixels = pixels[pixels != ASPECT_FLAT_SENTINEL]
            if pixels.size == 0:
                values.append(float("nan"))
                continue
            radians = np.radians(pixels)
            mean_angle = np.degrees(np.arctan2(np.sin(radians).mean(), np.cos(radians).mean()))
            values.append(float(mean_angle % 360.0))
    return values


def sample_grid_topography(
    grid: pd.DataFrame,
    reprojected_dem_path: Path,
    slope_path: Path,
    aspect_path: Path,
) -> pd.DataFrame:
    """Añade altitud/pendiente/orientación reales a la grilla vía media zonal.

    Args:
        grid: DataFrame con min_lon/min_lat/max_lon/max_lat en EPSG:4326
            (mismo esquema que DataProcessor._build_grid).
        reprojected_dem_path: GeoTIFF de elevación en CRS métrico (salida de
            dem_terrain.reproject_dem_to_utm).
        slope_path: GeoTIFF de pendiente en grados, mismo CRS/grilla.
        aspect_path: GeoTIFF de orientación en grados brújula (-1 = plano),
            mismo CRS/grilla.

    Returns:
        Copia de `grid` con columnas altitud, pendiente, orientacion (float32).
    """

    result = grid.copy()
    geometries = _cell_geometries_in_raster_crs(grid, reprojected_dem_path)

    result["altitud"] = np.array(_zonal_mean(reprojected_dem_path, geometries), dtype="float32")
    result["pendiente"] = np.array(_zonal_mean(slope_path, geometries), dtype="float32")
    result["orientacion"] = np.array(
        _zonal_circular_mean_deg(aspect_path, geometries), dtype="float32"
    )
    return result

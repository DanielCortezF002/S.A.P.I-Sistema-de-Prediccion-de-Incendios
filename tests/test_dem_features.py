"""Pruebas de src.procesamiento.dem_features: media zonal DEM -> grilla."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import rasterio
from rasterio.transform import from_origin

from src.procesamiento.dem_features import ASPECT_FLAT_SENTINEL, sample_grid_topography

# Grilla mínima de 2 celdas, misma forma que DataProcessor._build_grid().
_GRID = pd.DataFrame(
    [
        {"cell_id": "VP-001", "min_lon": -71.535, "min_lat": -33.062, "max_lon": -71.525, "max_lat": -33.053},
        {"cell_id": "VP-002", "min_lon": -71.525, "min_lat": -33.062, "max_lon": -71.515, "max_lat": -33.053},
    ]
)


def _write_utm_geotiff(path: Path, data: np.ndarray, *, origin_x: float, origin_y: float, pixel_size: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    transform = from_origin(origin_x, origin_y, pixel_size, pixel_size)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=data.shape[0],
        width=data.shape[1],
        count=1,
        dtype="float32",
        crs="EPSG:32719",
        transform=transform,
    ) as dataset:
        dataset.write(data.astype("float32"), 1)


@pytest.fixture()
def utm_bbox_for_grid() -> tuple[float, float, float, float]:
    """Bounds UTM 19S que cubren _GRID con margen, para ubicar los rasters de prueba."""

    import pyproj

    transformer = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:32719", always_xy=True)
    min_x, min_y = transformer.transform(_GRID["min_lon"].min() - 0.01, _GRID["min_lat"].min() - 0.01)
    max_x, max_y = transformer.transform(_GRID["max_lon"].max() + 0.01, _GRID["max_lat"].max() + 0.01)
    return min_x, min_y, max_x, max_y


def test_sample_grid_topography_computes_zonal_mean_altitude_and_slope(
    tmp_path: Path, utm_bbox_for_grid: tuple[float, float, float, float]
) -> None:
    min_x, min_y, max_x, max_y = utm_bbox_for_grid
    size = 200
    pixel_size = (max_x - min_x) / size

    # Elevación constante = 300 m en todo el raster -> media zonal debe dar 300.
    elevation = np.full((size, size), 300.0, dtype="float32")
    # Pendiente constante = 12° -> media zonal debe dar 12.
    slope = np.full((size, size), 12.0, dtype="float32")
    # Orientación en columnas alternadas (350°/10°): un split por mitades del
    # raster coincidiría con el propio límite VP-001/VP-002 y cada celda
    # quedaría dominada por un solo valor, no por la mezcla que se quiere
    # probar. Alternar columna a columna garantiza ~50/50 dentro de
    # cualquier celda, sin depender de dónde caiga exactamente su borde.
    col_pattern = np.where(np.arange(size) % 2 == 0, 350.0, 10.0).astype("float32")
    aspect = np.tile(col_pattern, (size, 1))

    dem_path = tmp_path / "dem_utm19s.tif"
    slope_path = tmp_path / "dem_slope.tif"
    aspect_path = tmp_path / "dem_aspect.tif"
    _write_utm_geotiff(dem_path, elevation, origin_x=min_x, origin_y=max_y, pixel_size=pixel_size)
    _write_utm_geotiff(slope_path, slope, origin_x=min_x, origin_y=max_y, pixel_size=pixel_size)
    _write_utm_geotiff(aspect_path, aspect, origin_x=min_x, origin_y=max_y, pixel_size=pixel_size)

    result = sample_grid_topography(_GRID, dem_path, slope_path, aspect_path)

    assert list(result["cell_id"]) == ["VP-001", "VP-002"]
    assert np.allclose(result["altitud"], 300.0, atol=0.5)
    assert np.allclose(result["pendiente"], 12.0, atol=0.5)
    # Mezcla ~50/50 de 350°/10° (valores que están a solo 20° de distancia
    # real, cruzando 0°): la media circular debe quedar cerca de 0°/360°.
    # Una media aritmética ingenua sobre los grados crudos daría ~180°
    # (el extremo opuesto) — si esta aserción pasara con 180°, delataría
    # ese bug.
    circular_dist_to_zero = np.minimum(result["orientacion"], 360.0 - result["orientacion"])
    assert np.all(circular_dist_to_zero < 5.0)


def test_sample_grid_topography_excludes_flat_sentinel_from_aspect_mean(
    tmp_path: Path, utm_bbox_for_grid: tuple[float, float, float, float]
) -> None:
    min_x, min_y, max_x, max_y = utm_bbox_for_grid
    size = 50
    pixel_size = (max_x - min_x) / size

    elevation = np.full((size, size), 100.0, dtype="float32")
    slope = np.full((size, size), 0.0, dtype="float32")
    # 80% del raster es plano (sentinel -1), 20% tiene orientación real = 45°,
    # disperso por módulo en vez de en una esquina fija — así cualquier celda
    # (sin importar dónde caiga su borde exacto) recibe algunos píxeles reales.
    col_pattern = np.where(np.arange(size) % 5 == 0, 45.0, ASPECT_FLAT_SENTINEL).astype("float32")
    aspect = np.tile(col_pattern, (size, 1))

    dem_path = tmp_path / "dem_utm19s.tif"
    slope_path = tmp_path / "dem_slope.tif"
    aspect_path = tmp_path / "dem_aspect.tif"
    _write_utm_geotiff(dem_path, elevation, origin_x=min_x, origin_y=max_y, pixel_size=pixel_size)
    _write_utm_geotiff(slope_path, slope, origin_x=min_x, origin_y=max_y, pixel_size=pixel_size)
    _write_utm_geotiff(aspect_path, aspect, origin_x=min_x, origin_y=max_y, pixel_size=pixel_size)

    result = sample_grid_topography(_GRID, dem_path, slope_path, aspect_path)

    # Si el sentinel -1 se promediara junto con 45°, el resultado sería
    # negativo/absurdo. Debe quedar cerca de 45°, no de un valor mezclado.
    assert np.all(result["orientacion"] >= 0.0)
    assert np.all(np.abs(result["orientacion"] - 45.0) < 90.0)


def test_sample_grid_topography_returns_nan_for_cell_outside_raster_coverage(tmp_path: Path) -> None:
    # Raster chico ubicado lejos de la grilla real -> ninguna celda se solapa.
    dem_path = tmp_path / "dem_utm19s.tif"
    slope_path = tmp_path / "dem_slope.tif"
    aspect_path = tmp_path / "dem_aspect.tif"
    far_away = np.full((10, 10), 500.0, dtype="float32")
    for path, data in [(dem_path, far_away), (slope_path, far_away), (aspect_path, far_away)]:
        _write_utm_geotiff(path, data, origin_x=0.0, origin_y=0.0, pixel_size=1.0)

    result = sample_grid_topography(_GRID, dem_path, slope_path, aspect_path)

    assert result["altitud"].isna().all()

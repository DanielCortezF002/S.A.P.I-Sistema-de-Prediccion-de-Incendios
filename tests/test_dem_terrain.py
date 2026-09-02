"""Pruebas de src.procesamiento.dem_terrain: reproyección + Horn (1981)."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from src.procesamiento.dem_terrain import (
    DemTerrainProcessor,
    UTM_19S_CRS,
    compute_slope_aspect_horn,
    reproject_dem_to_utm,
)


def _write_geotiff(
    path: Path,
    data: np.ndarray,
    *,
    crs: str,
    origin_lon: float,
    origin_lat: float,
    pixel_size: float,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    transform = from_origin(origin_lon, origin_lat, pixel_size, pixel_size)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=data.shape[0],
        width=data.shape[1],
        count=1,
        dtype="float32",
        crs=crs,
        transform=transform,
    ) as dataset:
        dataset.write(data.astype("float32"), 1)


# ---------------------------------------------------------------------------
# compute_slope_aspect_horn: verificación analítica (no solo "corrió sin error")
# ---------------------------------------------------------------------------


def test_horn_matches_analytical_slope_on_flat_plane() -> None:
    """Superficie perfectamente plana: pendiente 0, sin dirección de descenso."""

    elevation = np.full((5, 5), 100.0, dtype="float64")
    slope_deg, aspect_deg = compute_slope_aspect_horn(elevation, pixel_size_x=10.0, pixel_size_y=10.0)

    assert np.allclose(slope_deg, 0.0)
    assert np.all(aspect_deg == -1.0)


def test_horn_matches_analytical_slope_and_aspect_on_east_west_ramp() -> None:
    """Rampa pura este-oeste: pendiente y orientación calculables a mano.

    Elevación sube 1 m cada 10 m hacia el este (columnas crecientes) y no
    varía en la dirección norte-sur. La pendiente real es atan(1/10) por
    trigonometría directa, sin aproximación de Horn de por medio (Horn es
    exacto sobre un plano perfecto). Como la elevación sube hacia el este,
    la ladera "mira" (aspect) hacia el oeste = 270°.
    """

    pixel_size = 10.0
    rise_per_pixel = 1.0
    cols = np.arange(7, dtype="float64")
    elevation = np.tile(cols * rise_per_pixel, (7, 1))

    slope_deg, aspect_deg = compute_slope_aspect_horn(
        elevation, pixel_size_x=pixel_size, pixel_size_y=pixel_size
    )

    expected_slope_deg = math.degrees(math.atan(rise_per_pixel / pixel_size))

    interior_slope = slope_deg[1:-1, 1:-1]
    interior_aspect = aspect_deg[1:-1, 1:-1]
    assert np.allclose(interior_slope, expected_slope_deg, atol=0.01)
    assert np.allclose(interior_aspect, 270.0, atol=0.01)


def test_horn_rejects_non_metric_pixel_size() -> None:
    with pytest.raises(ValueError, match="metros"):
        compute_slope_aspect_horn(np.zeros((3, 3)), pixel_size_x=0.0, pixel_size_y=1.0)


# ---------------------------------------------------------------------------
# reproject_dem_to_utm
# ---------------------------------------------------------------------------


def test_reproject_produces_near_isotropic_metric_pixels(tmp_path: Path) -> None:
    """El DEM real de dem_ingester usa 1 arco-segundo (~30 m). Reproyectado a
    UTM 19S, el pixel debe quedar isotrópico y en ese rango — no ~26x31 m
    anisotrópico como en grados.
    """

    arcsecond = 1 / 3600
    data = np.linspace(0, 200, 10 * 10, dtype="float32").reshape(10, 10)
    src_path = tmp_path / "source_wgs84.tif"
    _write_geotiff(
        src_path, data, crs="EPSG:4326", origin_lon=-71.50, origin_lat=-33.00, pixel_size=arcsecond
    )

    dst_path = tmp_path / "reprojected.tif"
    _, transform, _profile = reproject_dem_to_utm(src_path, dst_path)

    with rasterio.open(dst_path) as written:
        assert written.crs.to_string() == UTM_19S_CRS

    pixel_x, pixel_y = transform.a, abs(transform.e)
    assert 25.0 <= pixel_x <= 35.0
    assert 25.0 <= pixel_y <= 35.0
    assert abs(pixel_x - pixel_y) < 2.0  # isotrópico, a diferencia del original en grados


def test_reproject_rejects_dem_without_crs(tmp_path: Path) -> None:
    src_path = tmp_path / "no_crs.tif"
    with rasterio.open(
        src_path, "w", driver="GTiff", height=3, width=3, count=1, dtype="float32"
    ) as dataset:
        dataset.write(np.zeros((3, 3), dtype="float32"), 1)

    with pytest.raises(ValueError, match="CRS"):
        reproject_dem_to_utm(src_path, tmp_path / "out.tif")


# ---------------------------------------------------------------------------
# DemTerrainProcessor: integración end-to-end
# ---------------------------------------------------------------------------


def test_processor_end_to_end_on_synthetic_hill(tmp_path: Path) -> None:
    arcsecond = 1 / 3600
    size = 20
    # "cerro" sintético: cono con pico al centro, elevación 0-300 m —
    # da pendiente y orientación no triviales, pero acotadas y sanas.
    yy, xx = np.mgrid[0:size, 0:size]
    center = size / 2
    distance = np.sqrt((xx - center) ** 2 + (yy - center) ** 2)
    elevation = (300.0 - distance * 15.0).clip(min=0).astype("float32")

    src_path = tmp_path / "raw" / "dem_test.tif"
    _write_geotiff(
        src_path, elevation, crs="EPSG:4326", origin_lon=-71.50, origin_lat=-33.00, pixel_size=arcsecond
    )

    processor = DemTerrainProcessor(out_dir=tmp_path / "processed")
    result = processor.process(src_path)

    assert result.reprojected_dem_path.exists()
    assert result.slope_path.exists()
    assert result.aspect_path.exists()

    # Sanidad geográfica (paso 3 del diseño): nada de pendientes absurdas,
    # ni un raster "plano" que delataría que no reproyectó de verdad.
    assert 0.0 < result.mean_slope_deg < 50.0
    assert result.max_slope_deg < 89.0
    assert 25.0 <= result.pixel_size_m[0] <= 35.0
    assert 25.0 <= result.pixel_size_m[1] <= 35.0

    with rasterio.open(result.slope_path) as dataset:
        assert dataset.crs.to_string() == UTM_19S_CRS
        assert dataset.count == 1


def test_processor_rejects_bad_reprojection_pixel_size(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Si el transform reproyectado da un pixel fuera de rango, debe fallar
    fuerte en vez de calcular pendiente sobre un raster mal escalado.
    """

    import src.procesamiento.dem_terrain as module

    src_path = tmp_path / "raw.tif"
    _write_geotiff(
        src_path,
        np.zeros((5, 5), dtype="float32"),
        crs="EPSG:4326",
        origin_lon=-71.50,
        origin_lat=-33.00,
        pixel_size=1 / 3600,
    )

    fake_transform = rasterio.Affine(999.0, 0.0, 0.0, 0.0, -999.0, 0.0)

    def _fake_reproject(*args, **kwargs):
        elevation = np.zeros((5, 5), dtype="float32")
        profile = {"crs": UTM_19S_CRS, "count": 1, "dtype": "float32"}
        return elevation, fake_transform, profile

    monkeypatch.setattr(module, "reproject_dem_to_utm", _fake_reproject)

    processor = DemTerrainProcessor(out_dir=tmp_path / "processed")
    with pytest.raises(ValueError, match="fuera del rango esperado"):
        processor.process(src_path)

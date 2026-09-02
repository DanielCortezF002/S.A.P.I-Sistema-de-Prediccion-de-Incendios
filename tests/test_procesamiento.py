"""Pruebas de procesamiento geoespacial."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import from_origin

from src.procesamiento.data_processor import DataProcessor


def test_clean_staging_tables_removes_outliers():
    processor = DataProcessor()
    df = pd.DataFrame({"temperatura": [20.0] * 10 + [500.0]})
    cleaned = processor.clean_staging_tables(df)
    assert cleaned["temperatura"].max() < 100.0


def test_impute_nulls_fills_missing():
    processor = DataProcessor()
    df = pd.DataFrame({"temperatura": [20.0, None, 22.0]})
    result = processor._impute_nulls(df)
    assert result["temperatura"].isna().sum() == 0


def test_validate_completeness():
    processor = DataProcessor()
    df = pd.DataFrame(
        {
            "temperatura": [30.0, 28.0, None],
            "humedad_relativa": [25.0, 40.0, 35.0],
            "velocidad_viento": [32.0, 15.0, 20.0],
            "altitud": [100.0, 200.0, 150.0],
            "pendiente": [10.0, 15.0, 12.0],
        }
    )
    score = processor._validate_completeness(df)
    assert 0.0 < score < 1.0


def test_build_grid_respects_max_cells():
    processor = DataProcessor()
    grid = processor._build_grid()
    assert "cell_id" in grid.columns
    assert len(grid) > 0
    assert len(grid) <= 50


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


def test_add_topography_uses_real_dem_when_processed_files_exist(tmp_path):
    """Si data/processed/dem_terrain/*.tif existe, _add_topography debe usar
    esos valores reales (media zonal) en vez de la aproximación sintética.
    """
    import pyproj

    processed_dir = tmp_path / "processed"
    processor = DataProcessor(raw_dir=tmp_path / "raw", processed_dir=processed_dir)
    grid = processor._build_grid()

    transformer = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:32719", always_xy=True)
    min_x, min_y = transformer.transform(grid["min_lon"].min() - 0.01, grid["min_lat"].min() - 0.01)
    max_x, max_y = transformer.transform(grid["max_lon"].max() + 0.01, grid["max_lat"].max() + 0.01)

    size = 300
    pixel_size = (max_x - min_x) / size
    terrain_dir = processed_dir / "dem_terrain"
    _write_utm_geotiff(
        terrain_dir / "COP30_test_utm19s.tif",
        np.full((size, size), 321.0, dtype="float32"),
        origin_x=min_x, origin_y=max_y, pixel_size=pixel_size,
    )
    _write_utm_geotiff(
        terrain_dir / "COP30_test_slope.tif",
        np.full((size, size), 17.0, dtype="float32"),
        origin_x=min_x, origin_y=max_y, pixel_size=pixel_size,
    )
    _write_utm_geotiff(
        terrain_dir / "COP30_test_aspect.tif",
        np.full((size, size), 200.0, dtype="float32"),
        origin_x=min_x, origin_y=max_y, pixel_size=pixel_size,
    )

    result = processor._add_topography(grid)

    assert np.allclose(result["altitud"], 321.0, atol=1.0)
    assert np.allclose(result["pendiente"], 17.0, atol=1.0)
    assert "orientacion" in result.columns
    assert np.allclose(result["orientacion"], 200.0, atol=1.0)


def test_add_topography_falls_back_to_synthetic_when_no_dem_processed(tmp_path):
    """Sin DEM procesado, debe mantener el comportamiento sintético anterior
    (no romper el pipeline demo/CI que no tiene GeoTIFF disponibles).
    """
    processor = DataProcessor(raw_dir=tmp_path / "raw", processed_dir=tmp_path / "processed")
    grid = processor._build_grid()

    result = processor._add_topography(grid)

    assert "altitud" in result.columns
    assert "pendiente" in result.columns
    assert "orientacion" not in result.columns
    assert result["altitud"].between(50, 800).all()


def test_load_meteo_parses_real_dmc_shape_not_hardcoded_defaults(tmp_path):
    """Regresión: antes, cualquier dmc_meteo_*.json real (dict anidado por
    estación) caía siempre a los defaults hardcodeados (25.0/40.0/15.0) sin
    ningún error, porque _load_meteo asumía top-level {"temperatura": ...}
    plano. Con datos reales de dos lecturas bien distintas, el resultado no
    puede ser ese default constante.
    """
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "dmc_meteo_2024-01-01.json").write_text(
        json.dumps(
            {
                "330007": {
                    "datosEstaciones": {
                        "datos": [
                            {
                                "momento": "2024-01-01 12:00:00",
                                "temperatura": "35.5 °C",
                                "humedadRelativa": "12 %",
                                "fuerzaDelViento": "20.0 kt",
                                "direccionDelViento": "180",
                            }
                        ]
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    processor = DataProcessor(raw_dir=raw_dir, processed_dir=tmp_path / "processed")
    meteo = processor._load_meteo()

    assert not (meteo["temperatura"] == 25.0).all()
    assert abs(meteo["temperatura"].iloc[0] - 35.5) < 0.01
    assert abs(meteo["humedad_relativa"].iloc[0] - 12.0) < 0.01
    assert meteo["velocidad_viento"].iloc[0] > 0  # convertido de nudos a km/h, no el default 15.0


def test_process_all_with_sample_raw(tmp_path):
    raw_dir = tmp_path / "raw"
    processed_dir = tmp_path / "processed"
    raw_dir.mkdir()

    # Forma real de la respuesta DMC (getDatosRecientesEma): dict por código
    # de estación, lecturas anidadas en datosEstaciones.datos[], valores con
    # unidad embebida como string — NO una lista plana de dicts con
    # "temperatura" como float en la raíz (esa forma nunca fue real, ver
    # DataProcessor._load_meteo).
    (raw_dir / "dmc_meteo_2024-01-01.json").write_text(
        json.dumps(
            {
                "330007": {
                    "datosEstaciones": {
                        "datos": [
                            {
                                "momento": "2024-01-01 12:00:00",
                                "temperatura": "30.0 °C",
                                "humedadRelativa": "25 %",
                                "fuerzaDelViento": "17.3 kt",
                                "direccionDelViento": "180",
                            },
                            {
                                "momento": "2024-01-01 13:00:00",
                                "temperatura": "22.0 °C",
                                "humedadRelativa": "60 %",
                                "fuerzaDelViento": "4.3 kt",
                                "direccionDelViento": "270",
                            },
                        ]
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    (raw_dir / "conaf_incendios_2024-01-01.json").write_text(
        json.dumps([{"fecha": "2024-01-01", "latitud": -33.05, "longitud": -71.55}]),
        encoding="utf-8",
    )
    (raw_dir / "nasa_firms_2024-01-01.csv").write_text(
        "latitude,longitude,acq_date\n-33.05,-71.55,2024-01-01",
        encoding="utf-8",
    )

    processor = DataProcessor(raw_dir=raw_dir, processed_dir=processed_dir)

    with __import__("unittest").mock.patch("src.procesamiento.data_processor.get_backend_connection"):
        out = processor.process_all()

    assert out.endswith(".parquet")

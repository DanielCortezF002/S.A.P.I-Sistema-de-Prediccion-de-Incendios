"""Pruebas de procesamiento geoespacial."""

from __future__ import annotations

import json

import pandas as pd

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


def test_process_all_with_sample_raw(tmp_path):
    raw_dir = tmp_path / "raw"
    processed_dir = tmp_path / "processed"
    raw_dir.mkdir()

    (raw_dir / "dmc_meteo_2024-01-01.json").write_text(
        json.dumps(
            [
                {"temperatura": 30, "humedad_relativa": 25, "velocidad_viento": 32},
                {"temperatura": 22, "humedad_relativa": 60, "velocidad_viento": 8},
            ]
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

"""Pruebas de normalización de payloads crudos NASA FIRMS y DMC."""

from __future__ import annotations

import json

import geopandas as gpd
import pandas as pd
import pytest

from src.procesamiento.raw_parser import (
    _clean_float,
    _extract_dmc_records,
    parse_dmc_json,
    parse_nasa_csv,
)


def test_clean_float_handles_dmc_units_and_numeric_inputs():
    assert _clean_float("18.8 °C") == 18.8
    assert _clean_float("72 %") == 72.0
    assert _clean_float(8.5) == 8.5
    assert _clean_float(10) == 10.0
    assert _clean_float(None) is None
    assert _clean_float("") is None
    assert _clean_float({"no": "string"}) is None


def test_extract_dmc_records_returns_empty_on_api_error():
    assert _extract_dmc_records({"error": "Información no disponible"}) == []


def test_extract_dmc_records_fallback_registros_key():
    rows = [{"momento": "2025-02-01 12:00:00", "temperatura": "20.0 °C"}]
    # Si datosEstaciones.datos no es lista, se usa la clave legacy ``registros``.
    payload = {"datosEstaciones": {"datos": "formato-inesperado"}, "registros": rows}
    assert _extract_dmc_records(payload) == rows


def test_parse_dmc_json_merges_available_stations_and_skips_invalid_wrappers(tmp_path):
    path = tmp_path / "dmc_mixed.json"
    path.write_text(
        json.dumps(
            {
                "330004": {"error": "Información no disponible"},
                "330007": {
                    "datosEstaciones": {
                        "datos": [
                            {
                                "momento": "2025-02-10 12:00:00",
                                "temperatura": "22.0 °C",
                                "humedadRelativa": "35 %",
                                "fuerzaDelViento": "10 kt",
                                "direccionDelViento": "180 °",
                            }
                        ]
                    }
                },
                "bad": "not-a-dict",
            }
        ),
        encoding="utf-8",
    )

    df = parse_dmc_json(path)

    assert len(df) == 1
    row = df.iloc[0]
    assert row["codigo_estacion"] == "330007"
    assert row["temperatura"] == 22.0
    assert row["humedad_relativa"] == 35.0
    assert row["velocidad_viento_kmh"] == pytest.approx(18.52)
    assert row["direccion_viento"] == 180.0


def test_parse_dmc_json_registros_fallback_format(tmp_path):
    path = tmp_path / "dmc_registros.json"
    path.write_text(
        json.dumps(
            {
                "330005": {
                    "datosEstaciones": {"datos": "formato-inesperado"},
                    "registros": [
                        {
                            "momento": "2025-02-01 08:15:00",
                            "temperatura": "19.5 °C",
                            "humedadRelativa": "60 %",
                            "fuerzaDelViento": "5 kt",
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    df = parse_dmc_json(path)
    assert len(df) == 1
    assert df.iloc[0]["codigo_estacion"] == "330005"


def test_parse_nasa_csv_empty_returns_empty_geodataframe(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text("latitude,longitude,acq_date,acq_time\n", encoding="utf-8")

    gdf = parse_nasa_csv(path)

    assert isinstance(gdf, gpd.GeoDataFrame)
    assert gdf.empty


def test_parse_nasa_csv_builds_geometry_and_acq_datetime(tmp_path):
    path = tmp_path / "fires.csv"
    path.write_text(
        "latitude,longitude,acq_date,acq_time,bright_ti4\n"
        "-33.06528,-71.55639,2025-02-10,1430,320.5\n"
        "-33.07000,-71.56000,2025-02-10,531,310.0\n",
        encoding="utf-8",
    )

    gdf = parse_nasa_csv(path)

    assert len(gdf) == 2
    assert gdf.crs.to_string() == "EPSG:4326"
    assert gdf.geometry.iloc[0].x == pytest.approx(-71.55639)
    assert gdf.geometry.iloc[0].y == pytest.approx(-33.06528)
    assert pd.notna(gdf["acq_datetime"].iloc[0])
    assert gdf["acq_datetime"].iloc[1].hour == 5
    assert gdf["acq_datetime"].iloc[1].minute == 31

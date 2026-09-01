"""Pruebas sintéticas del join NASA ↔ DMC (SAPI-28)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from src.procesamiento.meteo_fire_joiner import (
    JOIN_STATUS_MATCHED,
    JOIN_STATUS_NO_DMC_COVERAGE,
    JOIN_STATUS_OUT_OF_TOLERANCE,
    discover_dmc_monthly_files,
    ignition_timestamp,
    join_fires_to_meteo,
    stations_with_coverage,
    summarize_join,
)
from src.procesamiento.station_catalog import DmcStation, haversine_km, select_nearest_station


def _dmc_payload(codigo: str, rows: list[dict]) -> dict:
    return {
        codigo: {
            "datosEstaciones": {
                "estacion": {"codigoNacional": codigo},
                "datos": rows,
            }
        }
    }


def _write_dmc_monthly(tmp_path: Path, codigo: str, year: int, month: int, rows: list[dict]) -> Path:
    path = tmp_path / f"dmc_historico_{codigo}_{year}-{month:02d}.json"
    path.write_text(json.dumps(_dmc_payload(codigo, rows)), encoding="utf-8")
    return path


def _fire_row(lat: float, lon: float, acq_date: str, acq_time: int = 1200) -> dict:
    return {"latitude": lat, "longitude": lon, "acq_date": acq_date, "acq_time": acq_time}


@pytest.fixture
def synthetic_catalog() -> dict[str, DmcStation]:
    return {
        "330004": DmcStation("330004", "Quilpué", -33.04722, -71.45861),
        "330005": DmcStation("330005", "Villa Alemana", -33.04583, -71.37139),
        "330007": DmcStation("330007", "Rodelillo", -33.06528, -71.55639),
    }


def test_ignition_timestamp_builds_utc():
    ts = ignition_timestamp("2025-02-15", 1430)
    assert ts == pd.Timestamp("2025-02-15 14:30:00", tz="UTC")


def test_discover_dmc_monthly_files(tmp_path):
    _write_dmc_monthly(tmp_path, "330007", 2025, 2, [])
    _write_dmc_monthly(tmp_path, "330007", 2025, 3, [])
    (tmp_path / "dmc_historico_invalid_name.json").write_text("{}", encoding="utf-8")
    index = discover_dmc_monthly_files(tmp_path)
    assert index[("330007", 2025, 2)].name == "dmc_historico_330007_2025-02.json"
    assert stations_with_coverage(2025, 2, index) == ["330007"]
    assert len(index) == 2


def test_nearest_temporal_match_returns_none_for_empty_meteo() -> None:
    from src.procesamiento.meteo_fire_joiner import _nearest_temporal_match

    row, delta = _nearest_temporal_match(pd.Timestamp("2025-02-15 12:00:00", tz="UTC"), pd.DataFrame())
    assert row is None
    assert delta is None


def test_select_nearest_station_haversine_tiebreak_by_codigo():
    catalog = {
        "330007": DmcStation("330007", "B", -33.0, -71.0),
        "330004": DmcStation("330004", "A", -33.0, -71.0),
    }
    codigo, dist = select_nearest_station(-33.0, -71.0, ["330007", "330004"], catalog)
    assert dist == 0.0
    assert codigo == "330004"


def test_haversine_km_known_distance():
    # ~1° lon at ecuador ≈ 111 km
    dist = haversine_km(0.0, 0.0, 0.0, 1.0)
    assert 110 < dist < 112


def test_join_no_dmc_coverage_before_station_pick(tmp_path, synthetic_catalog):
    """Sin archivo mensual → no_dmc_coverage; no se elige estación."""
    fires = pd.DataFrame([_fire_row(-33.06528, -71.55639, "2025-03-01")])
    result = join_fires_to_meteo(fires, raw_dir=tmp_path, catalog=synthetic_catalog)
    row = result.iloc[0]
    assert row["join_status"] == JOIN_STATUS_NO_DMC_COVERAGE
    assert pd.isna(row["estacion_codigo"]) or row["estacion_codigo"] is None


def test_join_matched_within_tolerance(tmp_path, synthetic_catalog):
    _write_dmc_monthly(
        tmp_path,
        "330007",
        2025,
        2,
        [
            {
                "momento": "2025-02-10 12:00:00",
                "temperatura": "25.0 °C",
                "humedadRelativa": "40 %",
                "fuerzaDelViento": "10 kt",
            }
        ],
    )
    fires = pd.DataFrame([_fire_row(-33.06528, -71.55639, "2025-02-10", 1205)])
    result = join_fires_to_meteo(fires, raw_dir=tmp_path, catalog=synthetic_catalog)
    row = result.iloc[0]
    assert row["join_status"] == JOIN_STATUS_MATCHED
    assert row["estacion_codigo"] == "330007"
    assert row["temperatura"] == 25.0
    assert row["humedad_relativa"] == 40.0
    assert row["delta_minutos"] == pytest.approx(5.0)


def test_join_out_of_tolerance_keeps_row(tmp_path, synthetic_catalog):
    _write_dmc_monthly(
        tmp_path,
        "330007",
        2025,
        2,
        [
            {
                "momento": "2025-02-10 13:00:00",
                "temperatura": "20.0 °C",
                "humedadRelativa": "50 %",
                "fuerzaDelViento": "5 kt",
            }
        ],
    )
    fires = pd.DataFrame([_fire_row(-33.06528, -71.55639, "2025-02-10", 1200)])
    result = join_fires_to_meteo(fires, raw_dir=tmp_path, catalog=synthetic_catalog)
    row = result.iloc[0]
    assert row["join_status"] == JOIN_STATUS_OUT_OF_TOLERANCE
    assert row["estacion_codigo"] == "330007"
    assert row["temperatura"] is None or pd.isna(row["temperatura"])
    assert row["delta_minutos"] == pytest.approx(60.0)


def test_join_picks_nearest_station_with_coverage(tmp_path):
    """Solo estaciones con archivo del mes entran al ranking Haversine."""
    catalog = {
        "330004": DmcStation("330004", "Near", -33.05, -71.50),
        "330007": DmcStation("330007", "Far", -33.10, -71.60),
    }
    _write_dmc_monthly(
        tmp_path,
        "330007",
        2025,
        2,
        [
            {
                "momento": "2025-02-10 12:00:00",
                "temperatura": "22.0 °C",
                "humedadRelativa": "30 %",
                "fuerzaDelViento": "8 kt",
            }
        ],
    )
    # Ignición más cerca de 330004, pero solo 330007 tiene cobertura feb-2025.
    fires = pd.DataFrame([_fire_row(-33.051, -71.505, "2025-02-10", 1200)])
    result = join_fires_to_meteo(fires, raw_dir=tmp_path, catalog=catalog)
    assert result.iloc[0]["estacion_codigo"] == "330007"


def test_join_out_of_tolerance_45min_transmission_gap(tmp_path, synthetic_catalog):
    """Hueco DMC de 45 min: ignición en el medio queda fuera de ±15 min (caso no visto en feb-2025 real)."""
    _write_dmc_monthly(
        tmp_path,
        "330007",
        2025,
        2,
        [
            {
                "momento": "2025-02-10 12:00:00",
                "temperatura": "20.0 °C",
                "humedadRelativa": "50 %",
                "fuerzaDelViento": "5 kt",
            },
            {
                "momento": "2025-02-10 12:45:00",
                "temperatura": "21.0 °C",
                "humedadRelativa": "48 %",
                "fuerzaDelViento": "6 kt",
            },
        ],
    )
    # 12:22 → 22 min al reading anterior y 23 min al siguiente; ambos > 15 min.
    fires = pd.DataFrame([_fire_row(-33.06528, -71.55639, "2025-02-10", 1222)])
    result = join_fires_to_meteo(fires, raw_dir=tmp_path, catalog=synthetic_catalog)
    row = result.iloc[0]
    assert row["join_status"] == JOIN_STATUS_OUT_OF_TOLERANCE
    assert row["estacion_codigo"] == "330007"
    assert row["temperatura"] is None or pd.isna(row["temperatura"])
    assert row["delta_minutos"] == pytest.approx(22.0)


def test_summarize_join_rates():
    result = pd.DataFrame(
        {
            "join_status": [
                JOIN_STATUS_MATCHED,
                JOIN_STATUS_MATCHED,
                JOIN_STATUS_OUT_OF_TOLERANCE,
                JOIN_STATUS_NO_DMC_COVERAGE,
            ]
        }
    )
    summary = summarize_join(result)
    assert summary["total_fires"] == 4
    assert summary["match_rate_overall"] == 0.5
    assert summary["match_rate_where_dmc_available"] == pytest.approx(0.6667, rel=1e-3)

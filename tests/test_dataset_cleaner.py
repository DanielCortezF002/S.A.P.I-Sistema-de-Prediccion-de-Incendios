"""Pruebas de limpieza SAPI-32 sobre dataset ignición ↔ meteo."""

from __future__ import annotations

import pandas as pd
import pytest

from src.procesamiento.dataset_cleaner import (
    clean_fires_meteo_dataset,
    deduplicate_fires,
)
from src.procesamiento.meteo_fire_joiner import (
    JOIN_STATUS_MATCHED,
    JOIN_STATUS_NO_DMC_COVERAGE,
    JOIN_STATUS_OUT_OF_TOLERANCE,
)


def _base_row(**overrides) -> dict:
    row = {
        "latitude": -33.05,
        "longitude": -71.55,
        "acq_date": "2025-02-10",
        "acq_time": 1200,
        "satellite": "N",
        "instrument": "VIIRS",
        "firms_source": "VIIRS_SNPP_SP",
        "join_status": JOIN_STATUS_MATCHED,
        "delta_minutos": 5.0,
        "estacion_codigo": "330007",
        "temperatura": 22.0,
        "humedad_relativa": 40.0,
        "velocidad_viento_kmh": 10.0,
    }
    row.update(overrides)
    return row


def test_deduplicate_keeps_matched_over_out_of_tolerance():
    df = pd.DataFrame(
        [
            _base_row(join_status=JOIN_STATUS_OUT_OF_TOLERANCE, delta_minutos=60.0, temperatura=None),
            _base_row(join_status=JOIN_STATUS_MATCHED, delta_minutos=5.0, temperatura=25.0),
        ]
    )
    deduped, removed = deduplicate_fires(df)
    assert removed == 1
    assert len(deduped) == 1
    assert deduped.iloc[0]["join_status"] == JOIN_STATUS_MATCHED
    assert deduped.iloc[0]["temperatura"] == 25.0


def test_deduplicate_rounds_coordinates_to_five_decimals():
    df = pd.DataFrame(
        [
            _base_row(latitude=-33.050001, longitude=-71.550001),
            _base_row(latitude=-33.050004, longitude=-71.550004, temperatura=30.0),
        ]
    )
    deduped, removed = deduplicate_fires(df)
    assert removed == 1
    assert len(deduped) == 1


def test_clean_preserves_null_meteo_for_non_matched():
    df = pd.DataFrame(
        [
            _base_row(join_status=JOIN_STATUS_MATCHED, temperatura=20.0),
            _base_row(
                join_status=JOIN_STATUS_OUT_OF_TOLERANCE,
                latitude=-33.06,
                acq_time=1300,
                temperatura=None,
                humedad_relativa=None,
                velocidad_viento_kmh=None,
                estacion_codigo="330007",
            ),
            _base_row(
                join_status=JOIN_STATUS_NO_DMC_COVERAGE,
                latitude=-33.07,
                acq_time=1400,
                temperatura=None,
                humedad_relativa=None,
                velocidad_viento_kmh=None,
                estacion_codigo=None,
            ),
        ]
    )
    cleaned, summary = clean_fires_meteo_dataset(df)

    oot = cleaned[cleaned["join_status"] == JOIN_STATUS_OUT_OF_TOLERANCE].iloc[0]
    no_cov = cleaned[cleaned["join_status"] == JOIN_STATUS_NO_DMC_COVERAGE].iloc[0]
    assert pd.isna(oot["temperatura"])
    assert pd.isna(no_cov["temperatura"])
    assert summary["nulls_imputed_matched"] == 0


def test_clean_imputes_and_winsorizes_only_matched():
    # 10 valores normales + 1 outlier extremo en matched
    rows = [
        _base_row(
            latitude=-33.05 + i * 0.01,
            acq_time=1200 + i,
            temperatura=20.0,
            humedad_relativa=50.0,
        )
        for i in range(10)
    ]
    rows.append(
        _base_row(
            latitude=-33.20,
            acq_time=1500,
            temperatura=45.0,
            humedad_relativa=50.0,
        )
    )
    rows.append(
        _base_row(
            latitude=-33.21,
            acq_time=1600,
            join_status=JOIN_STATUS_OUT_OF_TOLERANCE,
            temperatura=None,
            humedad_relativa=None,
            velocidad_viento_kmh=None,
        )
    )
    df = pd.DataFrame(rows)
    cleaned, summary = clean_fires_meteo_dataset(df)

    outlier_row = cleaned[cleaned["temperatura"] == 45.0]
    assert outlier_row.empty
    assert summary["values_winsorized"] >= 1
    assert cleaned.loc[cleaned["join_status"] == JOIN_STATUS_OUT_OF_TOLERANCE, "temperatura"].isna().all()


def test_physical_bounds_clip_temperature_below_minus_10():
    df = pd.DataFrame(
        [
            _base_row(temperatura=-15.0, humedad_relativa=50.0),
            _base_row(latitude=-33.06, acq_time=1300, temperatura=22.0, humedad_relativa=50.0),
        ]
    )
    cleaned, summary = clean_fires_meteo_dataset(df)
    assert summary["physical_clips"] == 1
    clipped = cleaned[cleaned["latitude"] == -33.05].iloc[0]
    assert cleaned["temperatura"].notna().all()
    assert clipped["temperatura"] == pytest.approx(22.0)

"""Pruebas de `src.procesamiento.spatial_joiner.aggregate_dmc_daily`.

Ancla un bug real: agregar temp_max/rh_min/wind_max por separado y evaluar
la regla 30-30-30 sobre el agregado puede mezclar lecturas de horas
distintas como si fueran una sola observación. Así resultó ser un artefacto
el hallazgo "VP-025/2022-12-11" (ver docs/matriz-riesgo.md,
`scripts/reverificar_hallazgo_2022_12_11.py`) — corregido acá el 06-09-2026.
"""

from __future__ import annotations

import pandas as pd

from src.procesamiento.spatial_joiner import aggregate_dmc_daily


def test_regla_activa_when_one_reading_meets_all_three_conditions() -> None:
    df = pd.DataFrame(
        {
            "temperatura": [32.0],
            "humedad_relativa": [24.0],
            "velocidad_viento_kmh": [34.0],
        }
    )
    assert aggregate_dmc_daily(df)["regla_30_30_30"] == 1


def test_regla_inactive_when_extremes_come_from_different_readings() -> None:
    """El caso VP-025: temperatura alta a una hora, viento alto a otra — nunca juntos."""
    df = pd.DataFrame(
        {
            "temperatura": [32.0, 20.0],
            "humedad_relativa": [24.0, 50.0],
            "velocidad_viento_kmh": [10.0, 34.0],
        }
    )
    result = aggregate_dmc_daily(df)
    # Los agregados por separado sí cruzan los tres umbrales...
    assert result["temp_max_daily"] == 32.0
    assert result["rh_min_daily"] == 24.0
    assert result["wind_speed_max"] == 34.0
    # ...pero ninguna lectura real cumplió las tres condiciones a la vez.
    assert result["regla_30_30_30"] == 0


def test_regla_inactive_when_no_reading_meets_any_threshold() -> None:
    df = pd.DataFrame(
        {
            "temperatura": [20.0, 22.0],
            "humedad_relativa": [60.0, 55.0],
            "velocidad_viento_kmh": [10.0, 12.0],
        }
    )
    assert aggregate_dmc_daily(df)["regla_30_30_30"] == 0


def test_empty_dataframe_returns_null_metrics_and_inactive_rule() -> None:
    result = aggregate_dmc_daily(pd.DataFrame(columns=["temperatura", "humedad_relativa", "velocidad_viento_kmh"]))
    assert result == {
        "temp_max_daily": None,
        "rh_min_daily": None,
        "wind_speed_max": None,
        "regla_30_30_30": 0,
    }

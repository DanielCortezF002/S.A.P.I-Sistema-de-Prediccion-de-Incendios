"""Pruebas de `src.procesamiento.regional_meteo`.

Incluye el fixture de "no futuro" pedido explícitamente en la auditoría: T =
12:00, lecturas a las 11:00 (pasado, válida), 12:00 (presente, válida) y
13:00 (futuro, jamás debe entrar a una feature predictiva).
"""

from __future__ import annotations

from datetime import timedelta

import pandas as pd
import pytest

from src.procesamiento.regional_meteo import meteo_before, nearest_meteo_around


def _series(rows: list[tuple[str, float, float, float]]) -> pd.DataFrame:
    """rows: [(momento_iso, temp, hr, viento), ...]"""
    return pd.DataFrame(
        [
            {
                "station_id": "330007",
                "momento": pd.Timestamp(momento, tz="UTC"),
                "temperatura": temp,
                "humedad_relativa": hr,
                "velocidad_viento_kmh": viento,
            }
            for momento, temp, hr, viento in rows
        ]
    )


T = pd.Timestamp("2026-01-01 12:00:00", tz="UTC")

_FIXTURE = _series(
    [
        ("2026-01-01 11:00:00", 20.0, 50.0, 10.0),  # pasado — debe poder entrar
        ("2026-01-01 12:00:00", 25.0, 40.0, 15.0),  # presente — puede entrar
        ("2026-01-01 13:00:00", 35.0, 20.0, 40.0),  # futuro — JAMÁS debe entrar a una feature
    ]
)


def test_meteo_before_at_t_never_returns_the_future_reading() -> None:
    """Sección 16 del pedido: T=12:00, la lectura de las 13:00 jamás debe
    poder alimentar una feature calculada en T."""
    match = meteo_before(_FIXTURE, T, max_lookback=timedelta(0), min_lookback=timedelta(0))
    assert match is not None
    assert match.momento <= T
    assert match.temperatura != 35.0  # el valor de la lectura futura


def test_meteo_before_never_returns_a_reading_after_t_even_far_in_the_past() -> None:
    """Con min_lookback grande (ej. un lag de 24h) tampoco puede colarse la
    lectura futura, aunque esté "cerca" en índice de fila."""
    match = meteo_before(_FIXTURE, T, max_lookback=timedelta(hours=24), min_lookback=timedelta(hours=24))
    # No hay ninguna lectura 24h antes de T en este fixture (todas están
    # dentro de la misma hora) -> debe devolver None, nunca inventar ni
    # usar la lectura de las 13:00 por estar "más cerca" en la tabla.
    assert match is None


def test_nearest_meteo_around_can_return_the_future_reading_by_design() -> None:
    """`nearest_meteo_around` es el modo EXPLICATIVO — sí puede mirar hacia
    adelante dentro de la tolerancia. Esto es intencional (ver docstring),
    y por eso nunca debe usarse para features predictivas."""
    match = nearest_meteo_around(_FIXTURE, T, tolerance=timedelta(minutes=90))
    assert match is not None
    assert match.momento == T  # la más cercana es la exactamente simultánea


def test_meteo_before_returns_none_without_silently_falling_back() -> None:
    empty = _series([])
    assert meteo_before(empty, T, max_lookback=timedelta(hours=1), min_lookback=timedelta(0)) is None


def test_meteo_before_respects_tolerance_and_does_not_reach_further_back() -> None:
    """Una lectura fuera de tolerancia no debe usarse aunque sea la única disponible."""
    lonely = _series([("2026-01-01 06:00:00", 18.0, 60.0, 5.0)])  # 6h antes de T
    match = meteo_before(lonely, T, max_lookback=timedelta(hours=1), min_lookback=timedelta(0), tolerance=timedelta(minutes=30))
    assert match is None


def test_regla_30_30_30_uses_the_same_observation() -> None:
    match = meteo_before(_FIXTURE, T, max_lookback=timedelta(0), min_lookback=timedelta(0))
    assert match is not None
    assert match.regla_30_30_30 == 0  # T=25.0/40.0/15.0 no cumple ninguna variante de la regla


def test_regla_30_30_30_active_when_the_same_reading_meets_all_three() -> None:
    hot = _series([("2026-01-01 12:00:00", 32.0, 24.0, 34.0)])
    match = meteo_before(hot, T, max_lookback=timedelta(0), min_lookback=timedelta(0))
    assert match is not None
    assert match.regla_30_30_30 == 1

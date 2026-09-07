"""Pruebas de `app.components.risk_sparkline` (Tendencia del riesgo)."""

from __future__ import annotations

from app.components.risk_sparkline import daily_max_probability_series
from app.utils.demo_seed import get_all_demo_dates


def test_series_has_one_point_per_seed_day() -> None:
    dates = get_all_demo_dates()
    series = daily_max_probability_series(dates)
    assert len(series) == len(dates) == 7


def test_series_indexed_by_iso_date_strings() -> None:
    dates = get_all_demo_dates()
    series = daily_max_probability_series(dates)
    assert list(series.index) == [d.isoformat() for d in dates]


def test_peak_day_has_the_highest_probability() -> None:
    """El día pico del seed (2025-02-15, VP-038/VP-049 con regla activa) es el máximo."""
    dates = get_all_demo_dates()
    series = daily_max_probability_series(dates)
    assert series.idxmax() == "2025-02-15"
    assert series.max() == 0.97


def test_series_is_monotonic_or_flat_before_the_peak() -> None:
    """El seed sube progresivamente hacia el día crítico, sin caídas bruscas."""
    dates = get_all_demo_dates()
    series = daily_max_probability_series(dates)
    values = series.tolist()
    assert values == sorted(values)

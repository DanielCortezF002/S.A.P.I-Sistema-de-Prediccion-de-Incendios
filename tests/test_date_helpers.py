"""Pruebas de helpers de fechas demo."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

from app.utils.date_helpers import demo_date_window, resolve_available_dates, resolve_date_range


def test_demo_date_window_seven_days() -> None:
    start = date(2025, 2, 9)
    end = date(2025, 2, 15)
    dates = demo_date_window(start, end)
    assert len(dates) == 7
    assert dates[0] == start
    assert dates[-1] == end


def test_resolve_date_range_from_query() -> None:
    query = MagicMock()
    query.get_available_date_range.return_value = (date(2025, 2, 9), date(2025, 2, 15))
    min_d, max_d = resolve_date_range(query, date(2025, 1, 1), date(2025, 1, 7))
    assert min_d == date(2025, 2, 9)
    assert max_d == date(2025, 2, 15)


def test_resolve_date_range_fallback() -> None:
    query = MagicMock()
    query.get_available_date_range.return_value = (None, None)
    min_d, max_d = resolve_date_range(query, date(2025, 2, 9), date(2025, 2, 15))
    assert min_d == date(2025, 2, 9)
    assert max_d == date(2025, 2, 15)


def test_resolve_available_dates_from_query() -> None:
    query = MagicMock()
    query.get_available_dates.return_value = [date(2025, 2, 9), date(2025, 2, 15)]
    dates = resolve_available_dates(query, date(2025, 1, 1), date(2025, 1, 7))
    assert dates == [date(2025, 2, 9), date(2025, 2, 15)]


def test_resolve_available_dates_fallback() -> None:
    query = MagicMock()
    query.get_available_dates.return_value = []
    dates = resolve_available_dates(query, date(2025, 2, 9), date(2025, 2, 15))
    assert len(dates) == 7

"""Pruebas de helpers de fechas demo."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

from app.utils.date_helpers import demo_date_window, resolve_available_dates, resolve_date_range


def test_demo_date_window_seven_days() -> None:
    start = date(2025, 2, 9)
    end = date(2026, 6, 24)
    dates = demo_date_window(start, end)
    assert len(dates) == 8
    assert dates[0] == start
    assert dates[-1] == end


def test_resolve_date_range_from_query() -> None:
    query = MagicMock()
    query.get_available_date_range.return_value = (date(2025, 2, 9), date(2026, 6, 24))
    min_d, max_d = resolve_date_range(query, date(2025, 1, 1), date(2025, 1, 7))
    assert min_d == date(2025, 2, 9)
    assert max_d == date(2026, 6, 24)


def test_resolve_date_range_fallback_without_methods() -> None:
    query = object()
    min_d, max_d = resolve_date_range(query, date(2025, 2, 9), date(2026, 6, 24))
    assert min_d == date(2025, 2, 9)
    assert max_d == date(2026, 6, 24)


def test_resolve_date_range_module_fallback() -> None:
    query = MagicMock(spec=[])
    with patch("app.utils.date_helpers._module_fetch_date_range") as mock_mod:
        mock_mod.return_value = (date(2025, 2, 9), date(2025, 2, 14))
        min_d, max_d = resolve_date_range(query, date(2025, 2, 9), date(2026, 6, 24))
    assert min_d == date(2025, 2, 9)
    assert max_d == date(2025, 2, 14)


def test_resolve_available_dates_from_query() -> None:
    query = MagicMock()
    query.get_available_dates.return_value = [date(2025, 2, 9), date(2026, 6, 24)]
    dates = resolve_available_dates(query, date(2025, 1, 1), date(2025, 1, 7))
    assert dates == [date(2025, 2, 9), date(2026, 6, 24)]


def test_resolve_available_dates_fallback_without_methods() -> None:
    query = object()
    dates = resolve_available_dates(query, date(2025, 2, 9), date(2026, 6, 24))
    assert len(dates) == 8


def test_call_date_range_fn_handles_exception() -> None:
    from app.utils.date_helpers import _call_date_range_fn

    def _boom() -> tuple[None, None]:
        raise RuntimeError("db")

    assert _call_date_range_fn(_boom) is None


def test_call_date_range_fn_none_values() -> None:
    from app.utils.date_helpers import _call_date_range_fn

    assert _call_date_range_fn(lambda: (None, None)) is None

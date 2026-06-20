"""Resolución de fechas demo — sin imports nombrados frágiles."""

from __future__ import annotations

import importlib
from datetime import date, timedelta
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from src.query.prediction_query import PredictionQuery


def demo_date_window(start: date, end: date) -> list[date]:
    """Genera lista de fechas consecutivas inclusive."""
    days = (end - start).days
    return [start + timedelta(days=i) for i in range(days + 1)]


def resolve_date_range(
    query: PredictionQuery,
    fallback_start: date,
    fallback_end: date,
) -> tuple[date, date]:
    """Obtiene rango min/max desde PostGIS con degradación a ventana demo."""
    min_d: Optional[date]
    max_d: Optional[date]

    try:
        mod = importlib.import_module("src.query.prediction_query")
        fn = getattr(mod, "fetch_available_date_range", None)
        if callable(fn):
            min_d, max_d = fn()
            if min_d is not None and max_d is not None:
                return min_d, max_d
    except Exception:
        pass

    if hasattr(query, "get_available_date_range"):
        min_d, max_d = query.get_available_date_range()
        if min_d is not None and max_d is not None:
            return min_d, max_d

    return fallback_start, fallback_end


def resolve_available_dates(
    query: PredictionQuery,
    fallback_start: date,
    fallback_end: date,
) -> list[date]:
    """Lista fechas con datos; fallback a ventana demo de 7 días."""
    try:
        mod = importlib.import_module("src.query.prediction_query")
        fn = getattr(mod, "fetch_available_dates", None)
        if callable(fn):
            dates = fn()
            if dates:
                return dates
    except Exception:
        pass

    if hasattr(query, "get_available_dates"):
        dates = query.get_available_dates()
        if dates:
            return dates

    return demo_date_window(fallback_start, fallback_end)

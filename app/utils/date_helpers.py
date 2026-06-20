"""Resolución de fechas demo con degradación segura (compatible Cloud)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Callable, Optional


def demo_date_window(start: date, end: date) -> list[date]:
    """Genera lista de fechas consecutivas inclusive."""
    days = (end - start).days
    return [start + timedelta(days=i) for i in range(days + 1)]


def _call_date_range_fn(fn: Callable[[], tuple[Optional[date], Optional[date]]]) -> Optional[tuple[date, date]]:
    """Ejecuta un resolver de rango; retorna None si falla o no hay datos."""
    try:
        min_d, max_d = fn()
        if min_d is not None and max_d is not None:
            return min_d, max_d
    except Exception:
        return None
    return None


def _module_fetch_date_range() -> tuple[Optional[date], Optional[date]]:
    from src.query.prediction_query import fetch_available_date_range

    return fetch_available_date_range()


def _module_fetch_dates() -> list[date]:
    from src.query.prediction_query import fetch_available_dates

    return fetch_available_dates()


def resolve_date_range(
    query: Any,
    fallback_start: date,
    fallback_end: date,
) -> tuple[date, date]:
    """Obtiene rango min/max desde PostGIS con degradación a ventana demo."""
    resolvers: list[Callable[[], tuple[Optional[date], Optional[date]]]] = []

    instance_fn = getattr(query, "get_available_date_range", None)
    if callable(instance_fn):
        resolvers.append(instance_fn)

    try:
        from src.query import prediction_query as pq

        mod_fn = getattr(pq, "fetch_available_date_range", None)
        if callable(mod_fn):
            resolvers.append(mod_fn)
    except Exception:
        pass

    resolvers.append(_module_fetch_date_range)

    for fn in resolvers:
        result = _call_date_range_fn(fn)
        if result is not None:
            return result

    return fallback_start, fallback_end


def resolve_available_dates(
    query: Any,
    fallback_start: date,
    fallback_end: date,
) -> list[date]:
    """Lista fechas con datos; fallback a ventana demo."""
    resolvers: list[Callable[[], list[date]]] = []

    instance_fn = getattr(query, "get_available_dates", None)
    if callable(instance_fn):
        resolvers.append(instance_fn)

    try:
        from src.query import prediction_query as pq

        mod_fn = getattr(pq, "fetch_available_dates", None)
        if callable(mod_fn):
            resolvers.append(mod_fn)
    except Exception:
        pass

    resolvers.append(_module_fetch_dates)

    for fn in resolvers:
        try:
            dates = fn()
            if dates:
                return dates
        except Exception:
            continue

    return demo_date_window(fallback_start, fallback_end)

"""Resolución de fechas demo vía PredictionQuery (sin imports dinámicos a src)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional, Protocol


class _DateQuery(Protocol):
    """Contrato mínimo para consultar fechas disponibles."""

    def get_available_date_range(self) -> tuple[Optional[date], Optional[date]]: ...

    def get_available_dates(self) -> list[date]: ...


def demo_date_window(start: date, end: date) -> list[date]:
    """Genera lista de fechas consecutivas inclusive."""
    days = (end - start).days
    return [start + timedelta(days=i) for i in range(days + 1)]


def resolve_date_range(
    query: _DateQuery,
    fallback_start: date,
    fallback_end: date,
) -> tuple[date, date]:
    """Obtiene rango min/max desde PostGIS con degradación a ventana demo."""
    min_d, max_d = query.get_available_date_range()
    if min_d is not None and max_d is not None:
        return min_d, max_d
    return fallback_start, fallback_end


def resolve_available_dates(
    query: _DateQuery,
    fallback_start: date,
    fallback_end: date,
) -> list[date]:
    """Lista fechas con datos; fallback a ventana demo."""
    dates = query.get_available_dates()
    if dates:
        return dates
    return demo_date_window(fallback_start, fallback_end)

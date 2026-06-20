"""Consulta espacial de riesgo — delegada a PredictionQuery (serving layer)."""

from __future__ import annotations

from src.query.prediction_query import (
    QUERY_ENGINE_VERSION,
    fetch_available_date_range,
    fetch_available_dates,
    fetch_spatial_risk_map,
)

__all__ = [
    "QUERY_ENGINE_VERSION",
    "fetch_available_date_range",
    "fetch_available_dates",
    "fetch_spatial_risk_map",
]

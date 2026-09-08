"""Pruebas de `app.components.day_alerts` (Top zonas prioritarias)."""

from __future__ import annotations

import geopandas as gpd
from shapely.geometry import box

from app.components.day_alerts import high_risk_rows


def _gdf(rows: list[dict]) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        rows,
        geometry=[box(0, 0, 1, 1) for _ in rows],
        crs="EPSG:4326",
    )


def test_high_risk_rows_filters_to_alto_only() -> None:
    gdf = _gdf(
        [
            {"cell_id": "VP-001", "nivel_riesgo": "bajo", "probabilidad": 0.1},
            {"cell_id": "VP-002", "nivel_riesgo": "alto", "probabilidad": 0.7},
            {"cell_id": "VP-003", "nivel_riesgo": "medio", "probabilidad": 0.5},
        ]
    )
    altos = high_risk_rows(gdf)
    assert list(altos["cell_id"]) == ["VP-002"]


def test_high_risk_rows_sorts_by_probability_descending() -> None:
    gdf = _gdf(
        [
            {"cell_id": "VP-001", "nivel_riesgo": "alto", "probabilidad": 0.7},
            {"cell_id": "VP-002", "nivel_riesgo": "alto", "probabilidad": 0.95},
            {"cell_id": "VP-003", "nivel_riesgo": "alto", "probabilidad": 0.8},
        ]
    )
    altos = high_risk_rows(gdf)
    assert list(altos["cell_id"]) == ["VP-002", "VP-003", "VP-001"]


def test_high_risk_rows_empty_gdf_returns_empty() -> None:
    gdf = _gdf([])
    assert high_risk_rows(gdf).empty


def test_high_risk_rows_no_high_risk_cells_returns_empty() -> None:
    gdf = _gdf(
        [
            {"cell_id": "VP-001", "nivel_riesgo": "bajo", "probabilidad": 0.1},
            {"cell_id": "VP-002", "nivel_riesgo": "medio", "probabilidad": 0.5},
        ]
    )
    assert high_risk_rows(gdf).empty


def test_high_risk_rows_handles_none() -> None:
    assert high_risk_rows(None).empty

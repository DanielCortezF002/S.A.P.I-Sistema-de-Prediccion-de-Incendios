"""Resultado de scoring SINTÉTICO para pruebas y readiness del Output Plane.

SYNTHETIC: hashes inventados ("1"*64, …), no son archivos ni datos reales. Sirve
para ejercitar bridge → contrato canónico → Control Center → alerta → n8n → artefacto
sin tocar almacenes operacionales. Nunca se usa en la vía operacional.
"""

from __future__ import annotations

import dataclasses
from datetime import date

import pandas as pd

from src.geo.grid import all_cells
from src.inference.prototype_service import (
    FIRMS_STATUS_CURRENT,
    CellScore,
    GridScoreResult,
)
from src.inference.scoring_inputs import _canonical_sha


def synthetic_cells(scores: list[float]) -> list[CellScore]:
    grid = all_cells()
    return [
        CellScore(
            cell_id=grid[i]["cell_id"],
            score=score,
            rank=i + 1,
            display_rank=1 + sum(s > score for s in scores),
            tie_group_size=scores.count(score),
            geometry={
                k: grid[i][k] for k in ("min_lon", "min_lat", "max_lon", "max_lat")
            },
            elevation=None,
            slope=8.1,
            historical_count=0,
        )
        for i, score in enumerate(scores)
    ]


def synthetic_manifest() -> dict:
    """Forma de ScoringInputs.manifest() con hashes sintéticos (no son archivos reales)."""
    return {
        "reproducibility_mode": False,
        "forecast_time": "2026-09-24T12:00:00+00:00",
        "weather_timestamp": "2026-09-24T12:00:00+00:00",
        "model": {
            "role": "model",
            "origin": "pinned",
            "name": "prototype_model_d.pkl",
            "sha256": "1" * 64,
            "size": 1024,
            "model_version": "prototype_model_d_v1",
        },
        "firms": {
            "role": "firms",
            "origin": "current",
            "name": "firms.csv",
            "sha256": "2" * 64,
            "size": 2048,
            "coverage_start": "2024-01-01",
            "coverage_end": "2026-09-23",
            "lag_days": 1,
            "status": FIRMS_STATUS_CURRENT,
            "pointer_version": "v7",
        },
        "dmc": {
            "files": [
                {
                    "role": "dmc",
                    "origin": "versioned",
                    "name": "2026-09.json",
                    "sha256": "3" * 64,
                    "size": 512,
                }
            ],
            "manifest_sha256": "4" * 64,
            "coverage_start": "2026-08-01T00:00:00+00:00",
            "coverage_end": "2026-09-24T12:00:00+00:00",
            "pointer_version": "v3",
        },
        "topography": {"origin": "baseline", "sha256": "5" * 64},
    }


def synthetic_result(**changes) -> GridScoreResult:
    scores = [0.4, 0.4] + [round(0.3 - 0.005 * i, 4) for i in range(48)]
    manifest = changes.pop("manifest", synthetic_manifest())
    result = GridScoreResult(
        forecast_time=pd.Timestamp("2026-09-24T12:00:00Z"),
        horizon_hours=6,
        station_id="330007",
        station_name="Rodelillo",
        weather_timestamp=pd.Timestamp("2026-09-24T12:00:00Z"),
        age_hours=1.0,
        freshness="DATOS RECIENTES",
        model_version="prototype_model_d_v1",
        model_status="PROTOTYPE / EXPLORATORY",
        meteo_actual={
            "temperatura": 31.0,
            "humedad_relativa": 28.0,
            "velocidad_viento_kmh": 32.0,
            "regla_30_30_30": True,
            "momento_observacion": pd.Timestamp("2026-09-24T12:00:00Z"),
        },
        cells=synthetic_cells(scores),
        firms_origin="current",
        firms_coverage_end=date(2026, 9, 23),
        firms_lag_days=1,
        firms_status=FIRMS_STATUS_CURRENT,
        inputs_fingerprint=_canonical_sha(manifest),
        scoring_inputs=manifest,
    )
    return dataclasses.replace(result, **changes)

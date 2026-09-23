"""Puente HTTP de desarrollo local para que n8n consulte Model D.

NO es el servicio FastAPI de la arquitectura objetivo (ver
docs/architecture-stack-freeze-sprint2.md, ADR-002): ese vive detrás de
Spring Boot y persiste en PostgreSQL/PostGIS. Este módulo es un atajo de
desarrollo local/universitario -- expone `score_current_grid()` (el mismo
pipeline temporal + Modelo D que ya usa el dashboard Streamlit vía
`app/components/prototype_view.py`) por HTTP para que n8n pueda leerlo sin
acceso a Docker ni comandos arbitrarios. No persiste nada, no reentrena
nada, no toca PostgreSQL/PostGIS.

Nunca importa el pipeline legacy (el optimizador XGBoost legacy, el
orquestador diario legacy, matriz_features, xgboost_optimized.pkl) --
solo `src.inference.prototype_service`, exactamente igual que la vista
Streamlit del prototipo.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from src.inference.prototype_service import (
    MODEL_PATH,
    GridScoreResult,
    PrototypeUnavailableError,
    score_current_grid,
)

logger = logging.getLogger("sapi.n8n_bridge")

METADATA_PATH = MODEL_PATH.with_name("prototype_model_d_metadata.json")

# Fallas de los insumos de datos que `score_current_grid()` deja pasar sin
# envolver en `PrototypeUnavailableError`: un JSON DMC truncado/corrupto
# (`json.load` en `parse_dmc_json`), un archivo FIRMS/DMC que desaparece
# entre el `exists()`/`glob()` y su lectura, o un CSV FIRMS vacío o
# malformado. Son indisponibilidad de datos (503), no un bug. Se listan
# por tipo exacto -- nunca `ValueError`/`OSError` genéricos -- para que un
# error de programación siga saliendo como 500 con traza en el log.
DATA_INPUT_ERRORS = (
    json.JSONDecodeError,
    FileNotFoundError,
    pd.errors.EmptyDataError,
    pd.errors.ParserError,
)

_FALLBACK_DISCLAIMER = (
    "PROTOTIPO EXPLORATORIO. El score es un ranking relativo de riesgo, "
    "NO una probabilidad calibrada de incendio. No usar para decisiones "
    "operacionales."
)

app = FastAPI(
    title="S.A.P.I. n8n-bridge",
    description=(
        "Puente HTTP local de desarrollo para que n8n consulte el ranking "
        "de Modelo D. No es el servicio FastAPI de la arquitectura "
        "objetivo (ver ADR-002)."
    ),
    version="0.1.0",
)


def _read_metadata_json() -> Optional[dict]:
    """Lee `prototype_model_d_metadata.json` sin deserializar el pickle
    del modelo (evita el costo de joblib.load solo para leer el aviso
    científico y la versión)."""
    try:
        return json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _serialize_cell(cell) -> dict:
    return {
        "cell_id": cell.cell_id,
        "score": cell.score,
        "rank": cell.rank,
        "display_rank": cell.display_rank,
        "tie_group_size": cell.tie_group_size,
        "geometry": cell.geometry,
        "elevation": cell.elevation,
        "slope": cell.slope,
        "historical_count": cell.historical_count,
    }


def _serialize_grid_result(result: GridScoreResult, disclaimer: str) -> dict:
    meteo_actual = dict(result.meteo_actual)
    meteo_actual["momento_observacion"] = meteo_actual[
        "momento_observacion"
    ].isoformat()
    return {
        "status": "ok",
        "model_version": result.model_version,
        "model_status": result.model_status,
        "disclaimer": disclaimer,
        "forecast_time": result.forecast_time.isoformat(),
        "horizon_hours": result.horizon_hours,
        "station_id": result.station_id,
        "station_name": result.station_name,
        "weather_timestamp": result.weather_timestamp.isoformat(),
        "age_hours": result.age_hours,
        "freshness": result.freshness,
        "meteo_actual": meteo_actual,
        "cells": [_serialize_cell(c) for c in result.cells],
    }


@app.get("/health")
def health() -> dict:
    """Chequeo barato: solo existencia de archivos + lectura de JSON.
    Nunca ejecuta `score_current_grid()` -- seguro de consultar seguido."""
    model_exists = MODEL_PATH.exists()
    metadata = _read_metadata_json() if model_exists else None
    status = "ok" if (model_exists and metadata is not None) else "degraded"
    return {
        "status": status,
        "model_path_exists": model_exists,
        "model_version": (metadata or {}).get("model_version"),
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/score")
def get_score() -> JSONResponse:
    """Endpoint fijo, sin parámetros: siempre puntúa la grilla actual con
    `score_current_grid()` (última lectura meteorológica real, nunca una
    fecha futura inventada). Cualquier query param enviado por error es
    ignorado por FastAPI -- este endpoint nunca interpreta comandos."""
    try:
        result = score_current_grid()
    except PrototypeUnavailableError as exc:
        logger.warning("Model D scoring unavailable: %s", exc)
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "error_type": "prototype_unavailable",
                "message": str(exc),
            },
        )
    except DATA_INPUT_ERRORS as exc:
        logger.warning("Model D scoring input data unavailable", exc_info=True)
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "error_type": "data_unavailable",
                "message": (
                    f"Insumo de datos no disponible o ilegible ({type(exc).__name__}). "
                    "Revisar logs del servicio n8n-bridge."
                ),
            },
        )
    except Exception:  # noqa: BLE001 -- nunca exponer detalles internos a n8n
        logger.exception("Unexpected error while scoring Model D")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error_type": "internal_error",
                "message": (
                    "Error interno al generar el ranking. "
                    "Revisar logs del servicio n8n-bridge."
                ),
            },
        )

    metadata = _read_metadata_json()
    disclaimer = (metadata or {}).get("aviso", _FALLBACK_DISCLAIMER)
    return JSONResponse(
        status_code=200, content=_serialize_grid_result(result, disclaimer)
    )

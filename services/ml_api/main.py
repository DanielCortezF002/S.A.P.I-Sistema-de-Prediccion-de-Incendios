"""Servicio ML de S.A.P.I. v2 (SAPI-55): expone el Modelo D por HTTP.

Implementa el contrato congelado `contracts/openapi/ml-service.v0.yaml`
(ADR-002). Su único cliente es el backend Spring Boot: no es una API pública.

- `GET /health`: 200 si el modelo y su metadata se pueden leer; 503 si no.
  Nunca ejecuta inferencia.
- `POST /predict`: puntúa las 50 celdas con `score_current_grid()`. La única
  entrada es un `forecast_time` opcional; las features se resuelven aquí, desde
  los stores versionados FIRMS/DMC, nunca desde el cliente.

El score es un ranking relativo entre las 50 celdas de una misma evaluación,
no una probabilidad calibrada de incendio (`scientific_model_validation=false`).
Este servicio no persiste nada y no modifica el puente n8n (`tools/n8n_bridge`),
del que solo importa el validador de resultados.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Annotated, Literal, Optional

import pandas as pd
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from src.inference.prototype_service import (
    MODEL_PATH,
    PrototypeUnavailableError,
    score_current_grid,
)
from tools.n8n_bridge.contract import InvalidScoreResultError, validate_grid_result

logger = logging.getLogger("sapi.ml_api")

METADATA_PATH = MODEL_PATH.with_name("prototype_model_d_metadata.json")
SCHEMA_VERSION = "sapi-ranking-v0"

# Contenido corrupto de un insumo que sí se pudo leer (mismos tipos que el
# puente n8n): indisponibilidad de datos, no un bug. Tipos exactos, nunca
# `ValueError`/`OSError` genéricos.
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

# Mensajes genéricos: el contrato prohíbe exponer rutas o detalles internos.
MESSAGES = {
    "invalid_request": (
        "La petición no cumple el contrato: solo se admite forecast_time, "
        "como fecha-hora ISO 8601 con zona horaria."
    ),
    "prototype_unavailable": (
        "No se puede puntuar con los insumos disponibles para el forecast_time " "solicitado."
    ),
    "data_unavailable": "Insumo de datos no disponible o ilegible.",
    "internal_error": "Error interno al generar el ranking.",
}


class PredictRequest(BaseModel):
    """Única entrada admitida; sin features ni otros campos."""

    model_config = ConfigDict(extra="forbid")

    forecast_time: Optional[AwareDatetime] = None

    @field_validator("forecast_time", mode="before")
    @classmethod
    def _iso_string_only(cls, value):
        if value is not None and not isinstance(value, str):
            raise ValueError("forecast_time debe ser un string ISO 8601")
        return value


class CellRanking(BaseModel):
    cell_id: Annotated[str, Field(pattern=r"^VP-\d{3}$")]
    score: Annotated[float, Field(ge=0, le=1)]
    rank: Annotated[int, Field(ge=1, le=50)]
    display_rank: Annotated[int, Field(ge=1, le=50)]
    tie_group_size: Annotated[int, Field(ge=1, le=50)]


class RankingResult(BaseModel):
    schema_version: Literal["sapi-ranking-v0"]
    model_version: Annotated[str, Field(min_length=1)]
    forecast_time: AwareDatetime
    inputs_fingerprint: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    score_semantics: Literal["relative_rank"]
    scientific_model_validation: Literal[False]
    horizon_hours: Optional[Annotated[int, Field(ge=1)]] = None
    disclaimer: Optional[str] = None
    # Metadata opcional de la evaluación (sapi-ranking-v0). Ausente en
    # respuestas anteriores; si está, sale del GridScoreResult ya calculado.
    # No incluye model_status, meteo_actual ni historical_count.
    weather_timestamp: Optional[AwareDatetime] = None
    age_hours: Optional[Annotated[float, Field(ge=0)]] = None
    freshness: Optional[
        Literal[
            "DATOS RECIENTES",
            "DATOS CON RETRASO",
            "DATOS HISTÓRICOS / DESACTUALIZADOS",
        ]
    ] = None
    station_id: Optional[Annotated[str, Field(min_length=1)]] = None
    station_name: Optional[Annotated[str, Field(min_length=1)]] = None
    firms_origin: Optional[Literal["baseline", "current", "reproducibility"]] = None
    firms_coverage_end: Optional[date] = None
    firms_lag_days: Optional[Annotated[int, Field(ge=0)]] = None
    firms_status: Optional[Literal["FIRMS AL DÍA", "FIRMS DESACTUALIZADO"]] = None
    cells: Annotated[list[CellRanking], Field(min_length=50, max_length=50)]


class MlHealth(BaseModel):
    status: Literal["ok", "degraded"]
    model_version: Optional[str]


class ErrorBody(BaseModel):
    status: Literal["error"]
    error_type: str
    message: str


app = FastAPI(
    title="S.A.P.I. ML Service (Modelo D)",
    description=(
        "Servicio ML interno de S.A.P.I. v2. Implementa "
        "contracts/openapi/ml-service.v0.yaml. El score es un ranking "
        "relativo, no una probabilidad calibrada."
    ),
    version="0.1.0",
)


def _error(status_code: int, error_type: str) -> JSONResponse:
    body = ErrorBody(status="error", error_type=error_type, message=MESSAGES[error_type])
    return JSONResponse(status_code=status_code, content=body.model_dump())


@app.exception_handler(RequestValidationError)
async def _invalid_request(_request: Request, exc: RequestValidationError):
    # El 422 por defecto de FastAPI es {"detail": [...]}: no cumple el contrato.
    logger.info("Invalid /predict request: %s", exc.errors())
    return _error(422, "invalid_request")


def _read_metadata() -> Optional[dict]:
    """Lee la metadata JSON sin deserializar el pickle del modelo."""
    try:
        return json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


@app.get(
    "/health",
    response_model=MlHealth,
    responses={503: {"model": MlHealth, "description": "Modelo no disponible."}},
)
def health():
    metadata = _read_metadata() if MODEL_PATH.exists() else None
    model_version = (metadata or {}).get("model_version")
    if isinstance(model_version, str) and model_version:
        return MlHealth(status="ok", model_version=model_version)
    body = MlHealth(status="degraded", model_version=None)
    return JSONResponse(status_code=503, content=body.model_dump())


def _aware(value) -> datetime:
    """Datetime con zona, truncado a microsegundos (RFC 3339, ≤ 9 decimales)."""
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        raise ValueError("timestamp sin zona horaria")
    return ts.to_pydatetime()


def _coverage_end(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, pd.Timestamp):
        return value.date()
    if isinstance(value, date):
        return value
    raise ValueError("firms_coverage_end no es una fecha")


def _ranking(result, disclaimer: str) -> RankingResult:
    # age_hours y freshness ya vienen de la evaluación (captured_at −
    # weather_timestamp). Este servicio no los recalcula.
    return RankingResult(
        schema_version=SCHEMA_VERSION,
        model_version=result.model_version,
        forecast_time=_aware(result.forecast_time),
        inputs_fingerprint=result.inputs_fingerprint,
        score_semantics="relative_rank",
        scientific_model_validation=False,
        horizon_hours=result.horizon_hours,
        disclaimer=disclaimer,
        weather_timestamp=_aware(result.weather_timestamp),
        age_hours=float(result.age_hours),
        freshness=result.freshness,
        station_id=result.station_id,
        station_name=result.station_name,
        firms_origin=result.firms_origin,
        firms_coverage_end=_coverage_end(result.firms_coverage_end),
        firms_lag_days=int(result.firms_lag_days),
        firms_status=result.firms_status,
        cells=[
            CellRanking(
                cell_id=c.cell_id,
                score=c.score,
                rank=c.rank,
                display_rank=c.display_rank,
                tie_group_size=c.tie_group_size,
            )
            for c in result.cells
        ],
    )


@app.post(
    "/predict",
    response_model=RankingResult,
    responses={
        422: {"model": ErrorBody, "description": "La petición no cumple el contrato."},
        500: {"model": ErrorBody, "description": "Error interno."},
        503: {"model": ErrorBody, "description": "No se puede puntuar."},
    },
)
def predict(body: Optional[PredictRequest] = None):
    forecast_time = None
    if body is not None and body.forecast_time is not None:
        try:
            # UTC antes de puntuar: el mismo instante con distinto offset da el
            # mismo fingerprint y el mismo desfase FIRMS.
            forecast_time = pd.Timestamp(body.forecast_time).tz_convert("UTC")
        except (ValueError, OverflowError):
            # Fuera del rango que soporta pandas (p. ej. año 0001 o 9999).
            return _error(422, "invalid_request")

    try:
        result = score_current_grid(forecast_time=forecast_time)
    except PrototypeUnavailableError as exc:
        logger.warning("Model D scoring unavailable: %s", exc)
        return _error(503, "prototype_unavailable")
    except DATA_INPUT_ERRORS:
        logger.warning("Model D scoring input data unavailable", exc_info=True)
        return _error(503, "data_unavailable")
    except Exception:  # noqa: BLE001 -- nunca exponer detalles internos
        logger.exception("Unexpected error while scoring Model D")
        return _error(500, "internal_error")

    # Nunca un 200 con un resultado incompleto o inconsistente.
    try:
        validate_grid_result(result)
        metadata = _read_metadata()
        disclaimer = (metadata or {}).get("aviso", _FALLBACK_DISCLAIMER)
        payload = _ranking(result, disclaimer)
    except InvalidScoreResultError as exc:
        logger.error("Model D result violates the ranking contract: %s", exc)
        return _error(500, "internal_error")
    except Exception:  # noqa: BLE001 -- serialización fallida: mismo cierre
        logger.exception("Unexpected error while serializing Model D result")
        return _error(500, "internal_error")
    return JSONResponse(status_code=200, content=payload.model_dump(mode="json"))

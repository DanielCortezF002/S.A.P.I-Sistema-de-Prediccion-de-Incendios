"""Cliente HTTP y view-model del ranking servido por el backend Spring Boot.

SAPI-61 (arquitectura v2): la vista PROTOTIPO del dashboard ya no ejecuta el
Modelo D en proceso. Consume `GET {SAPI_BACKEND_BASE_URL}/api/v1/ranking`
(`contracts/openapi/backend.v0.yaml`, cuyo cuerpo es el `RankingResult` de
`ml-service.v0.yaml`) y lo convierte en un `RankingView` inmutable.

Principios:
- Fail-closed: una respuesta que no cumple el contrato se rechaza completa.
  Nunca se reordena, recalcula ni rellena nada.
- Tolerante a cambios aditivos: los campos desconocidos se ignoran y los
  campos opcionales previstos para la extensión aditiva (frescura, estación,
  meteorología usada, procedencia FIRMS) se leen solo si llegan. Si no llegan
  quedan en `None`, que la vista muestra como "no informado por el backend";
  jamás se derivan localmente.
- Errores tipados con mensaje genérico para el usuario (RN-09): sin host,
  ruta, credenciales ni stack trace.

Este módulo no importa nada de `src.inference`: la geometría se toma de la
fuente estática `src/geo/grid.py` solo para validar el conjunto de celdas.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Mapping, Optional

import requests

from src.config import get_backend_base_url, get_backend_timeouts
from src.geo.grid import all_cells

RANKING_PATH = "/api/v1/ranking"
SCHEMA_VERSION = "sapi-ranking-v0"
SCORE_SEMANTICS = "relative_rank"
EXPECTED_CELL_COUNT = 50
EXPECTED_CELL_IDS: frozenset[str] = frozenset(c["cell_id"] for c in all_cells())
MAX_BODY_BYTES = 2 * 1024 * 1024

_CELL_ID_RE = re.compile(r"^VP-\d{3}$")
_FINGERPRINT_RE = re.compile(r"^[0-9a-f]{64}$")
_CELL_REQUIRED = ("cell_id", "score", "rank", "display_rank", "tie_group_size")
_TOP_REQUIRED = (
    "schema_version",
    "model_version",
    "forecast_time",
    "inputs_fingerprint",
    "score_semantics",
    "scientific_model_validation",
    "cells",
)

# Campos opcionales top-level previstos para la extensión aditiva (Etapa B).
ADDITIVE_FIELDS = (
    "weather_timestamp",
    "age_hours",
    "freshness",
    "station_id",
    "station_name",
    "model_status",
    "meteo_actual",
    "firms_origin",
    "firms_coverage_end",
    "firms_lag_days",
    "firms_status",
)
FRESHNESS_FIELDS = ("weather_timestamp", "age_hours", "freshness")
STATION_FIELDS = ("station_id", "station_name")

ERROR_KIND_CONNECTION = "connection"
ERROR_KIND_TIMEOUT = "timeout"
ERROR_KIND_HTTP_BACKEND = "http_backend"
ERROR_KIND_INVALID_JSON = "invalid_json"
ERROR_KIND_INVALID_RANKING = "invalid_ranking"

_HTTP_USER_MESSAGES = {
    422: "El backend rechazó la petición de ranking (HTTP 422).",
    500: "El backend reportó un error interno al generar el ranking (HTTP 500).",
    502: "El backend recibió una respuesta inválida del servicio ML (HTTP 502).",
    503: "El servicio de ranking no está disponible en este momento (HTTP 503).",
    504: "El servicio ML no respondió a tiempo al backend (HTTP 504).",
}
_USER_MESSAGES = {
    ERROR_KIND_CONNECTION: (
        "No se pudo conectar con el backend de ranking. "
        "Verifica que el servicio esté en ejecución."
    ),
    ERROR_KIND_TIMEOUT: "El backend de ranking no respondió dentro del tiempo límite.",
    ERROR_KIND_INVALID_JSON: "El backend devolvió una respuesta vacía o no legible.",
    ERROR_KIND_INVALID_RANKING: (
        "El backend devolvió un ranking que no cumple el contrato; "
        "no se muestra para no presentar datos inválidos."
    ),
}
_MAX_REMOTE_MESSAGE_CHARS = 200


class BackendError(Exception):
    """Fallo controlado al obtener el ranking del backend.

    Attributes:
        kind: Categoría (`connection`, `timeout`, `http_backend`,
            `invalid_json`, `invalid_ranking`).
        user_message: Texto genérico apto para la UI (sin detalles internos).
        http_status: Código HTTP cuando `kind == http_backend`.
        error_type: `error_type` del cuerpo `Error` del contrato, si llegó.
        backend_message: `message` del cuerpo `Error`, saneado y acotado.
        detail: Motivo técnico para logs/tests; nunca se muestra al usuario.
    """

    def __init__(
        self,
        kind: str,
        *,
        detail: str = "",
        http_status: Optional[int] = None,
        error_type: Optional[str] = None,
        backend_message: Optional[str] = None,
    ) -> None:
        self.kind = kind
        self.http_status = http_status
        self.error_type = error_type
        self.backend_message = backend_message
        self.detail = detail
        if kind == ERROR_KIND_HTTP_BACKEND:
            self.user_message = _HTTP_USER_MESSAGES.get(
                http_status or 0,
                f"El backend respondió con un error HTTP ({http_status}).",
            )
        else:
            self.user_message = _USER_MESSAGES[kind]
        super().__init__(self.user_message)


@dataclass(frozen=True)
class RankingCell:
    """Una celda tal como la emitió el backend. Sin campos derivados."""

    cell_id: str
    score: float
    rank: int
    display_rank: int
    tie_group_size: int


@dataclass(frozen=True)
class MeteoSnapshot:
    """Meteorología regional usada por la corrida (solo si el backend la envía)."""

    temperatura: float
    humedad_relativa: float
    velocidad_viento_kmh: float
    regla_30_30_30: bool


@dataclass(frozen=True)
class RankingView:
    """View-model inmutable del `RankingResult` validado.

    Los campos a partir de `weather_timestamp` son la extensión aditiva
    opcional: `None` significa "el backend no lo informó", nunca un valor
    por defecto.
    """

    schema_version: str
    model_version: str
    forecast_time: datetime
    inputs_fingerprint: str
    score_semantics: str
    scientific_model_validation: bool
    horizon_hours: Optional[int]
    disclaimer: Optional[str]
    cells: tuple[RankingCell, ...]
    fetched_at: datetime
    weather_timestamp: Optional[datetime] = None
    age_hours: Optional[float] = None
    freshness: Optional[str] = None
    station_id: Optional[str] = None
    station_name: Optional[str] = None
    model_status: Optional[str] = None
    meteo_actual: Optional[MeteoSnapshot] = None
    firms_origin: Optional[str] = None
    firms_coverage_end: Optional[date] = None
    firms_lag_days: Optional[int] = None
    firms_status: Optional[str] = None

    @property
    def window_end(self) -> Optional[datetime]:
        """Fin de la ventana (T + horizon_hours) o None si el horizonte no llegó."""
        if self.horizon_hours is None:
            return None
        return datetime.fromtimestamp(
            self.forecast_time.timestamp() + self.horizon_hours * 3600, tz=timezone.utc
        )

    @property
    def missing_additive_fields(self) -> tuple[str, ...]:
        """Campos aditivos que el backend no informó (orden del contrato objetivo)."""
        return tuple(name for name in ADDITIVE_FIELDS if getattr(self, name) is None)

    @property
    def freshness_available(self) -> bool:
        """True solo si llegaron los tres campos de frescura."""
        return all(getattr(self, name) is not None for name in FRESHNESS_FIELDS)

    @property
    def station_available(self) -> bool:
        return all(getattr(self, name) is not None for name in STATION_FIELDS)

    @property
    def firms_provenance_available(self) -> bool:
        return any(
            getattr(self, name) is not None
            for name in ("firms_origin", "firms_coverage_end", "firms_lag_days", "firms_status")
        )


def _invalid(reason: str) -> BackendError:
    return BackendError(ERROR_KIND_INVALID_RANKING, detail=reason)


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _parse_datetime(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise _invalid(f"{field} debe ser string ISO 8601")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise _invalid(f"{field} no es ISO 8601: {value!r}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise _invalid(f"{field} sin zona horaria: {value!r}")
    return parsed.astimezone(timezone.utc)


def _parse_date(value: Any, field: str) -> date:
    if not isinstance(value, str) or not value:
        raise _invalid(f"{field} debe ser string ISO 8601 (fecha)")
    try:
        return date.fromisoformat(value)
    except ValueError:
        pass
    try:
        return _parse_datetime(value, field).date()
    except BackendError as exc:
        raise _invalid(f"{field} no es una fecha ISO 8601: {value!r}") from exc


def _parse_optional_str(payload: Mapping[str, Any], field: str) -> Optional[str]:
    value = payload.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        raise _invalid(f"{field} debe ser string")
    return value


def _parse_optional_number(payload: Mapping[str, Any], field: str) -> Optional[float]:
    value = payload.get(field)
    if value is None:
        return None
    if not _is_number(value) or not math.isfinite(float(value)) or float(value) < 0:
        raise _invalid(f"{field} debe ser un número finito ≥ 0")
    return float(value)


def _parse_optional_int(payload: Mapping[str, Any], field: str, minimum: int) -> Optional[int]:
    value = payload.get(field)
    if value is None:
        return None
    if not _is_int(value) or value < minimum:
        raise _invalid(f"{field} debe ser entero ≥ {minimum}")
    return value


def _parse_meteo(payload: Mapping[str, Any]) -> Optional[MeteoSnapshot]:
    raw = payload.get("meteo_actual")
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise _invalid("meteo_actual debe ser un objeto")
    values: dict[str, float] = {}
    for key in ("temperatura", "humedad_relativa", "velocidad_viento_kmh"):
        value = raw.get(key)
        if not _is_number(value) or not math.isfinite(float(value)):
            raise _invalid(f"meteo_actual.{key} debe ser un número finito")
        values[key] = float(value)
    regla = raw.get("regla_30_30_30")
    if not isinstance(regla, bool):
        raise _invalid("meteo_actual.regla_30_30_30 debe ser booleano")
    return MeteoSnapshot(regla_30_30_30=regla, **values)


def _parse_cells(raw_cells: Any) -> tuple[RankingCell, ...]:
    if not isinstance(raw_cells, list):
        raise _invalid("cells debe ser una lista")
    if len(raw_cells) != EXPECTED_CELL_COUNT:
        raise _invalid(f"cells debe tener {EXPECTED_CELL_COUNT} celdas, llegaron {len(raw_cells)}")

    cells: list[RankingCell] = []
    seen: set[str] = set()
    previous_score: Optional[float] = None
    for index, raw in enumerate(raw_cells):
        if not isinstance(raw, Mapping):
            raise _invalid(f"cells[{index}] no es un objeto")
        missing = [k for k in _CELL_REQUIRED if k not in raw]
        if missing:
            raise _invalid(f"cells[{index}] sin campos requeridos: {missing}")
        cell_id = raw["cell_id"]
        if not isinstance(cell_id, str) or not _CELL_ID_RE.match(cell_id):
            raise _invalid(f"cells[{index}].cell_id inválido: {cell_id!r}")
        if cell_id not in EXPECTED_CELL_IDS:
            raise _invalid(f"cells[{index}].cell_id fuera de la grilla: {cell_id}")
        if cell_id in seen:
            raise _invalid(f"cell_id duplicado: {cell_id}")
        seen.add(cell_id)

        score = raw["score"]
        if not _is_number(score) or not math.isfinite(float(score)):
            raise _invalid(f"{cell_id}.score no es un número finito")
        score = float(score)
        if not 0.0 <= score <= 1.0:
            raise _invalid(f"{cell_id}.score fuera de [0, 1]: {score}")
        if previous_score is not None and score > previous_score:
            raise _invalid(f"{cell_id}.score crece respecto del rank anterior")
        previous_score = score

        rank = raw["rank"]
        if not _is_int(rank) or rank != index + 1:
            raise _invalid(f"{cell_id}.rank debe ser {index + 1}, llegó {rank!r}")
        display_rank = raw["display_rank"]
        if not _is_int(display_rank) or not 1 <= display_rank <= EXPECTED_CELL_COUNT:
            raise _invalid(f"{cell_id}.display_rank inválido: {display_rank!r}")
        tie_group_size = raw["tie_group_size"]
        if not _is_int(tie_group_size) or not 1 <= tie_group_size <= EXPECTED_CELL_COUNT:
            raise _invalid(f"{cell_id}.tie_group_size inválido: {tie_group_size!r}")
        cells.append(
            RankingCell(
                cell_id=cell_id,
                score=score,
                rank=rank,
                display_rank=display_rank,
                tie_group_size=tie_group_size,
            )
        )

    if seen != EXPECTED_CELL_IDS:
        raise _invalid("el conjunto de cell_id no es exactamente VP-001..VP-050")

    # Coherencia de empates (se verifica, no se recalcula ni se corrige):
    # display_rank = rank de la primera celda con ese score (método min) y
    # tie_group_size = número de celdas con exactamente ese score.
    first_rank_by_score: dict[float, int] = {}
    count_by_score: dict[float, int] = {}
    for cell in cells:
        first_rank_by_score.setdefault(cell.score, cell.rank)
        count_by_score[cell.score] = count_by_score.get(cell.score, 0) + 1
    for cell in cells:
        if cell.display_rank != first_rank_by_score[cell.score]:
            raise _invalid(
                f"{cell.cell_id}.display_rank={cell.display_rank} no coincide con el "
                f"método min ({first_rank_by_score[cell.score]})"
            )
        if cell.tie_group_size != count_by_score[cell.score]:
            raise _invalid(
                f"{cell.cell_id}.tie_group_size={cell.tie_group_size} no coincide con "
                f"las {count_by_score[cell.score]} celdas de ese score"
            )
    return tuple(cells)


def parse_ranking(payload: Any, fetched_at: Optional[datetime] = None) -> RankingView:
    """Valida un `RankingResult` (dict ya decodificado) y construye el view-model.

    Args:
        payload: Cuerpo JSON decodificado de `GET /api/v1/ranking`.
        fetched_at: Instante UTC en que se recibió; por defecto ahora.

    Returns:
        `RankingView` con las celdas en el orden exacto del backend.

    Raises:
        BackendError: `kind == invalid_ranking` si cualquier invariante del
            contrato falla. No se devuelve nunca un resultado parcial.
    """
    if not isinstance(payload, Mapping):
        raise _invalid("el cuerpo no es un objeto JSON")
    missing = [k for k in _TOP_REQUIRED if k not in payload]
    if missing:
        raise _invalid(f"faltan campos requeridos: {missing}")
    if payload["schema_version"] != SCHEMA_VERSION:
        raise _invalid(f"schema_version inesperado: {payload['schema_version']!r}")
    model_version = payload["model_version"]
    if not isinstance(model_version, str) or not model_version.strip():
        raise _invalid("model_version vacío")
    fingerprint = payload["inputs_fingerprint"]
    if not isinstance(fingerprint, str) or not _FINGERPRINT_RE.match(fingerprint):
        raise _invalid("inputs_fingerprint no es un sha256 hex")
    if payload["score_semantics"] != SCORE_SEMANTICS:
        raise _invalid(f"score_semantics inesperado: {payload['score_semantics']!r}")
    if payload["scientific_model_validation"] is not False:
        raise _invalid("scientific_model_validation debe ser false")

    horizon = payload.get("horizon_hours")
    if horizon is not None and (not _is_int(horizon) or horizon < 1):
        raise _invalid(f"horizon_hours inválido: {horizon!r}")
    disclaimer = _parse_optional_str(payload, "disclaimer")

    weather_ts_raw = payload.get("weather_timestamp")
    weather_timestamp = (
        _parse_datetime(weather_ts_raw, "weather_timestamp") if weather_ts_raw is not None else None
    )
    coverage_raw = payload.get("firms_coverage_end")
    firms_coverage_end = (
        _parse_date(coverage_raw, "firms_coverage_end") if coverage_raw is not None else None
    )

    return RankingView(
        schema_version=SCHEMA_VERSION,
        model_version=model_version,
        forecast_time=_parse_datetime(payload["forecast_time"], "forecast_time"),
        inputs_fingerprint=fingerprint,
        score_semantics=SCORE_SEMANTICS,
        scientific_model_validation=False,
        horizon_hours=horizon,
        disclaimer=disclaimer,
        cells=_parse_cells(payload["cells"]),
        fetched_at=fetched_at or datetime.now(timezone.utc),
        weather_timestamp=weather_timestamp,
        age_hours=_parse_optional_number(payload, "age_hours"),
        freshness=_parse_optional_str(payload, "freshness"),
        station_id=_parse_optional_str(payload, "station_id"),
        station_name=_parse_optional_str(payload, "station_name"),
        model_status=_parse_optional_str(payload, "model_status"),
        meteo_actual=_parse_meteo(payload),
        firms_origin=_parse_optional_str(payload, "firms_origin"),
        firms_coverage_end=firms_coverage_end,
        firms_lag_days=_parse_optional_int(payload, "firms_lag_days", minimum=0),
        firms_status=_parse_optional_str(payload, "firms_status"),
    )


def _sanitize_remote_text(value: Any) -> Optional[str]:
    """Texto remoto para mostrar: solo str, sin controles, acotado."""
    if not isinstance(value, str):
        return None
    cleaned = "".join(ch for ch in value if ch.isprintable()).strip()
    if not cleaned:
        return None
    return cleaned[:_MAX_REMOTE_MESSAGE_CHARS]


def _error_from_response(response: requests.Response) -> BackendError:
    error_type: Optional[str] = None
    message: Optional[str] = None
    try:
        body = response.json()
    except ValueError:
        body = None
    if isinstance(body, Mapping):
        error_type = _sanitize_remote_text(body.get("error_type"))
        message = _sanitize_remote_text(body.get("message"))
    return BackendError(
        ERROR_KIND_HTTP_BACKEND,
        detail=f"HTTP {response.status_code} error_type={error_type}",
        http_status=int(response.status_code),
        error_type=error_type,
        backend_message=message,
    )


class BackendRankingClient:
    """Cliente mínimo de `GET /api/v1/ranking` del backend Spring Boot.

    Args:
        base_url: URL base del backend (sin ruta), p. ej. `http://localhost:8080`.
        connect_timeout: Segundos para establecer la conexión.
        read_timeout: Segundos de espera de la respuesta (el backend espera al ML).
        session: `requests.Session` inyectable (tests, pooling). Se crea una
            por cliente si no se entrega.
    """

    def __init__(
        self,
        base_url: str,
        *,
        connect_timeout: float = 3.0,
        read_timeout: float = 90.0,
        session: Optional[requests.Session] = None,
    ) -> None:
        if not isinstance(base_url, str) or not base_url.strip():
            raise ValueError("base_url vacío")
        self.base_url = base_url.strip().rstrip("/")
        self.connect_timeout = float(connect_timeout)
        self.read_timeout = float(read_timeout)
        self._session = session or requests.Session()

    @classmethod
    def from_env(cls, session: Optional[requests.Session] = None) -> "BackendRankingClient":
        """Cliente con `SAPI_BACKEND_BASE_URL` y timeouts leídos del entorno."""
        connect_timeout, read_timeout = get_backend_timeouts()
        return cls(
            get_backend_base_url(),
            connect_timeout=connect_timeout,
            read_timeout=read_timeout,
            session=session,
        )

    @property
    def ranking_url(self) -> str:
        return f"{self.base_url}{RANKING_PATH}"

    @property
    def timeout(self) -> tuple[float, float]:
        return (self.connect_timeout, self.read_timeout)

    def fetch_ranking(self, forecast_time: Optional[str] = None) -> RankingView:
        """Obtiene y valida el ranking.

        Args:
            forecast_time: ISO 8601 con zona horaria; se envía tal cual como
                query `forecast_time`. Sin él, el backend usa el último bucket real.

        Returns:
            `RankingView` validado.

        Raises:
            BackendError: Para cualquier fallo de red, HTTP o de contrato.
        """
        params = {"forecast_time": forecast_time} if forecast_time else None
        try:
            response = self._session.get(
                self.ranking_url,
                params=params,
                headers={"Accept": "application/json"},
                timeout=self.timeout,
            )
        except requests.exceptions.Timeout as exc:
            raise BackendError(ERROR_KIND_TIMEOUT, detail=type(exc).__name__) from exc
        except requests.exceptions.RequestException as exc:
            raise BackendError(ERROR_KIND_CONNECTION, detail=type(exc).__name__) from exc

        fetched_at = datetime.now(timezone.utc)
        if response.status_code != 200:
            raise _error_from_response(response)
        content = response.content or b""
        if not content.strip():
            raise BackendError(ERROR_KIND_INVALID_JSON, detail="cuerpo vacío")
        if len(content) > MAX_BODY_BYTES:
            raise _invalid(f"cuerpo mayor a {MAX_BODY_BYTES} bytes")
        try:
            payload = response.json()
        except ValueError as exc:
            raise BackendError(ERROR_KIND_INVALID_JSON, detail="JSON inválido") from exc
        return parse_ranking(payload, fetched_at=fetched_at)

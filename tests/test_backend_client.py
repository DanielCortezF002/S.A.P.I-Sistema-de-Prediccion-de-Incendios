"""SAPI-61 — UNIT: `app.utils.backend_client` (CA2, CA3-ranking/empates, CA4).

Cubre el parse fail-closed del `RankingResult` v0, la tolerancia a campos
aditivos, y el cliente HTTP con una `requests.Session` falsa (sin red). El
stub HTTP real vive en `tests/test_sapi61_http_stub.py`.
"""

from __future__ import annotations

import copy
import json
import math
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pytest
import requests

from app.utils.backend_client import (
    ADDITIVE_FIELDS,
    BODY_CHUNK_BYTES,
    ERROR_KIND_CONNECTION,
    ERROR_KIND_HTTP_BACKEND,
    ERROR_KIND_INVALID_JSON,
    ERROR_KIND_INVALID_RANKING,
    ERROR_KIND_TIMEOUT,
    EXPECTED_CELL_IDS,
    KNOWN_ERROR_TYPES,
    MAX_BODY_BYTES,
    RANKING_PATH,
    BackendError,
    BackendRankingClient,
    MeteoSnapshot,
    RankingView,
    parse_ranking,
)
from src.geo.grid import all_cells

REPO_ROOT = Path(__file__).resolve().parents[1]
# Corrida real reproducible del servicio ML (misma fixture que usa Spring en
# sus tests): 3 scores únicos, empates de 7, 41 y 2 celdas.
REAL_FIXTURE = (
    REPO_ROOT / "services/backend/src/test/resources/ml/predict-reproducible-2026-09-01.json"
)

EXTENDED_FIELDS: dict[str, Any] = {
    "weather_timestamp": "2026-08-31T23:45:00Z",
    "age_hours": 156.9,
    "freshness": "DATOS HISTÓRICOS / DESACTUALIZADOS",
    "station_id": "330007",
    "station_name": "Rodelillo",
    "model_status": "PROTOTYPE / EXPLORATORY",
    "meteo_actual": {
        "temperatura": 18.8,
        "humedad_relativa": 72.0,
        "velocidad_viento_kmh": 15.7,
        "regla_30_30_30": False,
    },
    "firms_origin": "current",
    "firms_coverage_end": "2026-08-30",
    "firms_lag_days": 2,
    "firms_status": "FIRMS AL DÍA",
}


def real_payload() -> dict:
    return json.loads(REAL_FIXTURE.read_text(encoding="utf-8"))


def synthetic_payload(scores: list[float] | None = None) -> dict:
    """Payload v0 válido construido desde la grilla; sin empates por defecto."""
    ids = [c["cell_id"] for c in all_cells()]
    if scores is None:
        scores = [round(1.0 - i * 0.01, 6) for i in range(50)]
    assert len(scores) == 50
    first_rank: dict[float, int] = {}
    counts: dict[float, int] = {}
    for i, s in enumerate(scores):
        first_rank.setdefault(s, i + 1)
        counts[s] = counts.get(s, 0) + 1
    cells = [
        {
            "cell_id": ids[i],
            "score": s,
            "rank": i + 1,
            "display_rank": first_rank[s],
            "tie_group_size": counts[s],
        }
        for i, s in enumerate(scores)
    ]
    return {
        "schema_version": "sapi-ranking-v0",
        "model_version": "prototype_model_d_v1",
        "forecast_time": "2026-10-01T18:00:00-03:00",
        "inputs_fingerprint": "a" * 64,
        "score_semantics": "relative_rank",
        "scientific_model_validation": False,
        "horizon_hours": 6,
        "disclaimer": "Ranking relativo exploratorio.",
        "cells": cells,
    }


def _expect_invalid(payload: Any, fragment: str = "") -> BackendError:
    with pytest.raises(BackendError) as info:
        parse_ranking(payload)
    assert info.value.kind == ERROR_KIND_INVALID_RANKING
    if fragment:
        assert fragment in info.value.detail
    return info.value


# ── parse: payload válido ─────────────────────────────────────────────────────


def test_real_v0_fixture_parses_with_exact_preservation() -> None:
    payload = real_payload()
    view = parse_ranking(payload)
    assert isinstance(view, RankingView)
    assert len(view.cells) == 50
    for raw, cell in zip(payload["cells"], view.cells):
        assert cell.cell_id == raw["cell_id"]
        assert cell.score == raw["score"]
        assert cell.rank == raw["rank"]
        assert cell.display_rank == raw["display_rank"]
        assert cell.tie_group_size == raw["tie_group_size"]
    assert view.model_version == "prototype_model_d_v1"
    assert view.inputs_fingerprint == payload["inputs_fingerprint"]
    assert view.forecast_time == datetime(2026, 9, 1, tzinfo=timezone.utc)
    assert view.horizon_hours == 6
    assert view.window_end == datetime(2026, 9, 1, 6, tzinfo=timezone.utc)
    assert view.score_semantics == "relative_rank"
    assert view.scientific_model_validation is False
    assert view.disclaimer == payload["disclaimer"]


def test_real_ties_are_preserved_not_recomputed() -> None:
    view = parse_ranking(real_payload())
    top = [c for c in view.cells if c.display_rank == 1]
    assert len(top) == 7 and {c.tie_group_size for c in top} == {7}
    middle = [c for c in view.cells if c.display_rank == 8]
    assert len(middle) == 41 and {c.tie_group_size for c in middle} == {41}
    last = [c for c in view.cells if c.display_rank == 49]
    assert [c.cell_id for c in last] == ["VP-028", "VP-038"]
    assert {c.tie_group_size for c in last} == {2}
    assert [c.rank for c in view.cells] == list(range(1, 51))


def test_order_is_the_backend_order_even_with_ties() -> None:
    payload = real_payload()
    ids_in = [c["cell_id"] for c in payload["cells"]]
    assert ids_in != sorted(ids_in), "la fixture real no viene ordenada por id"
    assert [c.cell_id for c in parse_ranking(payload).cells] == ids_in


def test_v0_without_additive_metadata_leaves_all_optional_fields_none() -> None:
    view = parse_ranking(real_payload())
    assert view.missing_additive_fields == ADDITIVE_FIELDS
    assert view.freshness_available is False
    assert view.station_available is False
    assert view.firms_provenance_available is False
    assert view.meteo_actual is None
    assert view.freshness is None and view.age_hours is None and view.weather_timestamp is None


def test_forecast_time_with_offset_is_normalised_to_utc() -> None:
    view = parse_ranking(synthetic_payload())
    assert view.forecast_time == datetime(2026, 10, 1, 21, tzinfo=timezone.utc)
    assert view.forecast_time.tzinfo is not None


def test_optional_horizon_and_disclaimer_may_be_absent() -> None:
    payload = synthetic_payload()
    del payload["horizon_hours"]
    del payload["disclaimer"]
    view = parse_ranking(payload)
    assert view.horizon_hours is None and view.window_end is None
    assert view.disclaimer is None


def test_fetched_at_is_recorded() -> None:
    stamp = datetime(2026, 10, 10, 12, tzinfo=timezone.utc)
    assert parse_ranking(synthetic_payload(), fetched_at=stamp).fetched_at == stamp
    assert parse_ranking(synthetic_payload()).fetched_at.tzinfo is not None


# ── parse: tolerancia aditiva ────────────────────────────────────────────────


def test_unknown_additive_fields_are_ignored_top_level_and_per_cell() -> None:
    payload = synthetic_payload()
    payload["campo_nuevo"] = {"anidado": [1, 2, 3]}
    payload["cells"][0]["otro_campo"] = "x"
    view = parse_ranking(payload)
    assert view.cells[0].cell_id == payload["cells"][0]["cell_id"]
    assert not hasattr(view, "campo_nuevo")


def test_extended_metadata_is_read_verbatim() -> None:
    payload = {**synthetic_payload(), **copy.deepcopy(EXTENDED_FIELDS)}
    view = parse_ranking(payload)
    assert view.weather_timestamp == datetime(2026, 8, 31, 23, 45, tzinfo=timezone.utc)
    assert view.age_hours == 156.9
    assert view.freshness == "DATOS HISTÓRICOS / DESACTUALIZADOS"
    assert view.station_id == "330007" and view.station_name == "Rodelillo"
    assert view.model_status == "PROTOTYPE / EXPLORATORY"
    assert view.meteo_actual == MeteoSnapshot(18.8, 72.0, 15.7, False)
    assert view.firms_origin == "current"
    assert view.firms_coverage_end == date(2026, 8, 30)
    assert view.firms_lag_days == 2
    assert view.firms_status == "FIRMS AL DÍA"
    assert view.missing_additive_fields == ()
    assert view.freshness_available and view.station_available
    assert view.firms_provenance_available


def test_partial_extension_does_not_claim_freshness() -> None:
    payload = synthetic_payload()
    payload["freshness"] = "DATOS RECIENTES"  # sin age_hours ni weather_timestamp
    view = parse_ranking(payload)
    assert view.freshness == "DATOS RECIENTES"
    assert view.freshness_available is False


def test_explicit_null_additive_fields_are_treated_as_absent() -> None:
    payload = synthetic_payload()
    payload.update({name: None for name in ADDITIVE_FIELDS})
    view = parse_ranking(payload)
    assert view.missing_additive_fields == ADDITIVE_FIELDS


@pytest.mark.parametrize(
    "field, value",
    [
        ("weather_timestamp", "2026-08-31 23:45"),
        ("weather_timestamp", "2026-08-31T23:45:00"),
        ("age_hours", "156"),
        ("age_hours", -1),
        ("age_hours", float("nan")),
        ("freshness", 3),
        ("station_id", 330007),
        ("model_status", ["x"]),
        ("meteo_actual", "18.8"),
        ("meteo_actual", {"temperatura": 18.8}),
        ("meteo_actual", {**EXTENDED_FIELDS["meteo_actual"], "regla_30_30_30": "si"}),
        ("firms_coverage_end", "ayer"),
        ("firms_lag_days", 1.5),
        ("firms_lag_days", -1),
        ("firms_lag_days", True),
    ],
)
def test_known_additive_field_with_wrong_type_fails_closed(field: str, value: Any) -> None:
    payload = synthetic_payload()
    payload[field] = value
    _expect_invalid(payload, field.split(".")[0])


def test_firms_coverage_end_accepts_datetime_string() -> None:
    payload = synthetic_payload()
    payload["firms_coverage_end"] = "2026-08-30T12:00:00Z"
    assert parse_ranking(payload).firms_coverage_end == date(2026, 8, 30)


# ── parse: rechazos top-level ────────────────────────────────────────────────


@pytest.mark.parametrize("payload", [None, [], "texto", 42, [synthetic_payload()]])
def test_non_object_payload_is_rejected(payload: Any) -> None:
    _expect_invalid(payload, "objeto JSON")


@pytest.mark.parametrize(
    "field",
    [
        "schema_version",
        "model_version",
        "forecast_time",
        "inputs_fingerprint",
        "score_semantics",
        "scientific_model_validation",
        "cells",
    ],
)
def test_missing_required_field_is_rejected(field: str) -> None:
    payload = synthetic_payload()
    del payload[field]
    _expect_invalid(payload, "requeridos")


def test_wrong_schema_version_is_rejected() -> None:
    payload = synthetic_payload()
    payload["schema_version"] = "sapi-ranking-v1"
    _expect_invalid(payload, "schema_version")


@pytest.mark.parametrize("value", ["probability", "", None, 1])
def test_score_semantics_must_be_relative_rank(value: Any) -> None:
    payload = synthetic_payload()
    payload["score_semantics"] = value
    _expect_invalid(payload, "score_semantics")


@pytest.mark.parametrize("value", [True, "false", 0, None])
def test_scientific_model_validation_must_be_false(value: Any) -> None:
    payload = synthetic_payload()
    payload["scientific_model_validation"] = value
    _expect_invalid(payload, "scientific_model_validation")


@pytest.mark.parametrize("value", ["", "   ", None, 7])
def test_empty_model_version_is_rejected(value: Any) -> None:
    payload = synthetic_payload()
    payload["model_version"] = value
    _expect_invalid(payload, "model_version")


@pytest.mark.parametrize("value", ["abc", "A" * 64, "0" * 63, None])
def test_bad_fingerprint_is_rejected(value: Any) -> None:
    payload = synthetic_payload()
    payload["inputs_fingerprint"] = value
    _expect_invalid(payload, "inputs_fingerprint")


@pytest.mark.parametrize("value", ["2026-10-01T18:00:00", "ayer", "", None, 1700000000])
def test_forecast_time_must_be_aware_iso8601(value: Any) -> None:
    payload = synthetic_payload()
    payload["forecast_time"] = value
    _expect_invalid(payload, "forecast_time")


@pytest.mark.parametrize("value", [0, -6, 6.0, "6", True])
def test_bad_horizon_is_rejected(value: Any) -> None:
    payload = synthetic_payload()
    payload["horizon_hours"] = value
    _expect_invalid(payload, "horizon_hours")


# ── parse: rechazos por celda ────────────────────────────────────────────────


def test_49_cells_rejected() -> None:
    payload = synthetic_payload()
    payload["cells"].pop()
    _expect_invalid(payload, "50 celdas")


def test_51_cells_rejected() -> None:
    payload = synthetic_payload()
    payload["cells"].append(dict(payload["cells"][-1]))
    _expect_invalid(payload, "50 celdas")


def test_duplicate_cell_id_rejected() -> None:
    payload = synthetic_payload()
    payload["cells"][1]["cell_id"] = payload["cells"][0]["cell_id"]
    _expect_invalid(payload, "duplicado")


def test_cell_outside_grid_rejected() -> None:
    payload = synthetic_payload()
    payload["cells"][0]["cell_id"] = "VP-051"
    _expect_invalid(payload, "fuera de la grilla")
    payload["cells"][0]["cell_id"] = "vp-001"
    _expect_invalid(payload, "cell_id inválido")


def test_cells_must_be_a_list_of_objects() -> None:
    payload = synthetic_payload()
    payload["cells"] = {"a": 1}
    _expect_invalid(payload, "lista")
    payload = synthetic_payload()
    payload["cells"][3] = "VP-004"
    _expect_invalid(payload, "no es un objeto")


def test_missing_cell_field_rejected() -> None:
    payload = synthetic_payload()
    del payload["cells"][5]["tie_group_size"]
    _expect_invalid(payload, "sin campos requeridos")


@pytest.mark.parametrize("bad_rank", [0, 3, 51, "2", 2.0, True])
def test_bad_rank_rejected(bad_rank: Any) -> None:
    payload = synthetic_payload()
    payload["cells"][1]["rank"] = bad_rank
    _expect_invalid(payload, "rank")


@pytest.mark.parametrize("score", [1.0001, -0.1, 2, "0.5", None, float("nan"), float("inf")])
def test_score_out_of_range_or_not_numeric_rejected(score: Any) -> None:
    payload = synthetic_payload()
    payload["cells"][0]["score"] = score
    _expect_invalid(payload, "score")


def test_increasing_score_rejected() -> None:
    payload = synthetic_payload()
    payload["cells"][10]["score"] = payload["cells"][9]["score"] + 0.001
    _expect_invalid(payload, "crece")


def test_inconsistent_display_rank_rejected() -> None:
    payload = synthetic_payload()
    payload["cells"][4]["display_rank"] = 4
    _expect_invalid(payload, "display_rank")


def test_inconsistent_tie_group_size_rejected() -> None:
    payload = real_payload()
    payload["cells"][0]["tie_group_size"] = 6
    _expect_invalid(payload, "tie_group_size")


def test_display_rank_min_method_is_verified_on_real_ties() -> None:
    payload = real_payload()
    payload["cells"][1]["display_rank"] = 2  # debería ser 1 (empate de 7)
    _expect_invalid(payload, "método min")


@pytest.mark.parametrize("field", ["display_rank", "tie_group_size"])
@pytest.mark.parametrize("value", [0, 51, "1", 1.0, False])
def test_display_rank_and_tie_group_size_bounds(field: str, value: Any) -> None:
    payload = synthetic_payload()
    payload["cells"][0][field] = value
    _expect_invalid(payload, field)


def test_cell_set_must_cover_the_whole_grid() -> None:
    assert len(EXPECTED_CELL_IDS) == 50
    assert EXPECTED_CELL_IDS == {c["cell_id"] for c in all_cells()}


# ── window_end (Astra MINOR 1) ───────────────────────────────────────────────


def test_window_end_normal_six_hours() -> None:
    view = parse_ranking(synthetic_payload())  # forecast 2026-10-01T18:00-03:00, h=6
    assert view.window_end == datetime(2026, 10, 2, 3, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    "horizon",
    [
        10**18,  # timedelta no construible (OverflowError en días)
        10**8,  # construible, pero T+h cae fuera del rango de datetime (año > 9999)
        70_000_000,  # ~7 990 años: justo por encima del máximo representable
    ],
)
def test_window_end_out_of_range_is_none_not_a_crash(horizon: int) -> None:
    payload = synthetic_payload()
    payload["horizon_hours"] = horizon
    view = parse_ranking(payload)
    assert view.horizon_hours == horizon  # no se recorta ni se corrige
    assert view.window_end is None


def test_window_end_largest_representable_is_still_computed() -> None:
    payload = synthetic_payload()
    payload["horizon_hours"] = 69_000_000  # ≈ año 9897: representable
    assert parse_ranking(payload).window_end is not None


# ── timeouts finitos (Astra MINOR 2) ─────────────────────────────────────────


@pytest.mark.parametrize(
    "raw",
    ["nan", "inf", "+inf", "-inf", "Infinity", "0", "0.0", "-3", "-0.5", "rápido", "", "  "],
)
def test_env_float_rejects_non_finite_zero_negative_and_text(
    monkeypatch: pytest.MonkeyPatch, raw: str
) -> None:
    monkeypatch.setenv("SAPI_BACKEND_CONNECT_TIMEOUT", raw)
    monkeypatch.setenv("SAPI_BACKEND_READ_TIMEOUT", raw)
    assert BackendRankingClient.from_env().timeout == (3.0, 90.0)
    for value in BackendRankingClient.from_env().timeout:
        assert math.isfinite(value) and value > 0


@pytest.mark.parametrize(
    "raw, expected", [("0.5", 0.5), ("7", 7.0), (" 12.25 ", 12.25), ("1e2", 100.0)]
)
def test_env_float_accepts_finite_positive(
    monkeypatch: pytest.MonkeyPatch, raw: str, expected: float
) -> None:
    monkeypatch.setenv("SAPI_BACKEND_CONNECT_TIMEOUT", raw)
    monkeypatch.setenv("SAPI_BACKEND_READ_TIMEOUT", raw)
    assert BackendRankingClient.from_env().timeout == (expected, expected)


# ── cliente HTTP con sesión falsa ────────────────────────────────────────────


class _FakeResponse:
    """Respuesta en streaming. `.content` y `.json()` están prohibidos: si el
    cliente los toca, materializaría el cuerpo completo (Astra MAJOR 1)."""

    def __init__(
        self,
        status: int,
        body: bytes | str = b"",
        *,
        content_length: int | None | str = "auto",
        chunk_size: int | None = None,
        fail_after: int | None = None,
        fail_with: BaseException | None = None,
    ) -> None:
        self.status_code = status
        self._body = body.encode("utf-8") if isinstance(body, str) else body
        self.headers: dict[str, str] = {}
        if content_length == "auto":
            self.headers["Content-Length"] = str(len(self._body))
        elif content_length is not None:
            self.headers["Content-Length"] = str(content_length)
        self._chunk_size = chunk_size
        self._fail_after = fail_after
        self._fail_with = fail_with or requests.exceptions.ChunkedEncodingError("cut")
        self.closed = 0
        self.bytes_served = 0
        self.chunks_requested: list[int] = []

    @property
    def content(self) -> bytes:
        raise AssertionError("el cliente no debe materializar response.content")

    def json(self) -> Any:
        raise AssertionError("el cliente no debe usar response.json()")

    def iter_content(self, chunk_size: int = 1) -> Any:
        self.chunks_requested.append(chunk_size)
        size = self._chunk_size or chunk_size
        offset = 0
        while offset < len(self._body):
            if self._fail_after is not None and offset >= self._fail_after:
                raise self._fail_with
            chunk = self._body[offset : offset + size]
            offset += len(chunk)
            self.bytes_served += len(chunk)
            yield chunk

    def close(self) -> None:
        self.closed += 1


class _FakeSession:
    def __init__(self, response: Any = None, raise_exc: BaseException | None = None) -> None:
        self.response = response
        self.raise_exc = raise_exc
        self.calls: list[dict] = []

    def get(self, url: str, **kwargs: Any) -> Any:
        self.calls.append({"url": url, **kwargs})
        if self.raise_exc is not None:
            raise self.raise_exc
        return self.response


def _client(session: _FakeSession, base: str = "http://backend.test:8080/") -> BackendRankingClient:
    return BackendRankingClient(base, connect_timeout=1.5, read_timeout=2.5, session=session)


def _fetch_error(response: _FakeResponse) -> BackendError:
    with pytest.raises(BackendError) as info:
        _client(_FakeSession(response)).fetch_ranking()
    assert response.closed == 1, "response.close() debe ocurrir exactamente una vez"
    return info.value


def test_fetch_ranking_hits_the_contract_path_with_accept_timeout_and_stream() -> None:
    response = _FakeResponse(200, json.dumps(synthetic_payload()))
    session = _FakeSession(response)
    view = _client(session).fetch_ranking()
    assert len(view.cells) == 50
    call = session.calls[0]
    assert call["url"] == "http://backend.test:8080/api/v1/ranking"
    assert call["headers"]["Accept"] == "application/json"
    assert call["timeout"] == (1.5, 2.5)
    assert call["params"] is None
    assert call["stream"] is True
    assert response.closed == 1
    assert response.chunks_requested == [BODY_CHUNK_BYTES]


def test_fetch_ranking_forwards_forecast_time_as_query() -> None:
    session = _FakeSession(_FakeResponse(200, json.dumps(synthetic_payload())))
    _client(session).fetch_ranking(forecast_time="2026-10-01T18:00:00-03:00")
    assert session.calls[0]["params"] == {"forecast_time": "2026-10-01T18:00:00-03:00"}


def test_client_never_touches_content_or_json_on_success_or_error() -> None:
    # Las propiedades falsas lanzan AssertionError: si el cliente las usara,
    # el AssertionError saldría por fuera de BackendError y rompería el test.
    ok = _FakeResponse(200, json.dumps(synthetic_payload()), content_length=None)
    assert len(_client(_FakeSession(ok)).fetch_ranking().cells) == 50
    err = _FakeResponse(503, json.dumps(error_body("upstream_unavailable")), content_length=None)
    assert _fetch_error(err).error_type == "upstream_unavailable"


def test_base_url_is_configurable_by_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SAPI_BACKEND_BASE_URL", "http://backend:9090/")
    monkeypatch.setenv("SAPI_BACKEND_CONNECT_TIMEOUT", "0.5")
    monkeypatch.setenv("SAPI_BACKEND_READ_TIMEOUT", "7")
    client = BackendRankingClient.from_env()
    assert client.ranking_url == "http://backend:9090" + RANKING_PATH
    assert client.timeout == (0.5, 7.0)


def test_default_base_url_is_localhost_8080(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SAPI_BACKEND_BASE_URL", raising=False)
    monkeypatch.delenv("SAPI_BACKEND_CONNECT_TIMEOUT", raising=False)
    monkeypatch.delenv("SAPI_BACKEND_READ_TIMEOUT", raising=False)
    import src.config as config

    monkeypatch.setattr(config, "SAPI_BACKEND_BASE_URL", config.SAPI_BACKEND_BASE_URL_DEFAULT)
    client = BackendRankingClient.from_env()
    assert client.ranking_url == "http://localhost:8080/api/v1/ranking"
    assert client.timeout == (3.0, 90.0)


def test_empty_base_url_is_rejected() -> None:
    with pytest.raises(ValueError):
        BackendRankingClient("   ")


@pytest.mark.parametrize(
    "exc, kind",
    [
        (requests.exceptions.ConnectTimeout("t"), ERROR_KIND_TIMEOUT),
        (requests.exceptions.ReadTimeout("t"), ERROR_KIND_TIMEOUT),
        (requests.exceptions.ConnectionError("refused"), ERROR_KIND_CONNECTION),
        (requests.exceptions.InvalidURL("bad"), ERROR_KIND_CONNECTION),
        (requests.exceptions.ChunkedEncodingError("cut"), ERROR_KIND_CONNECTION),
    ],
)
def test_network_errors_map_to_typed_backend_errors(exc: BaseException, kind: str) -> None:
    with pytest.raises(BackendError) as info:
        _client(_FakeSession(raise_exc=exc)).fetch_ranking()
    assert info.value.kind == kind
    assert info.value.http_status is None


# ── límite de cuerpo en streaming (Astra MAJOR 1) ────────────────────────────


def _oversized_json(extra: int = 1) -> bytes:
    """JSON sintácticamente válido de MAX_BODY_BYTES + extra bytes."""
    return b"{" + b" " * (MAX_BODY_BYTES + extra - 2) + b"}"


def _exact_limit_json() -> bytes:
    body = b"{" + b" " * (MAX_BODY_BYTES - 2) + b"}"
    assert len(body) == MAX_BODY_BYTES
    return body


def test_200_oversized_with_content_length_fails_before_reading() -> None:
    response = _FakeResponse(200, _oversized_json())  # Content-Length real
    err = _fetch_error(response)
    assert err.kind == ERROR_KIND_INVALID_RANKING
    assert response.bytes_served == 0, "con Content-Length > límite no se lee nada"


def test_200_oversized_without_content_length_is_cut_during_streaming() -> None:
    response = _FakeResponse(200, _oversized_json(512 * 1024), content_length=None)
    err = _fetch_error(response)
    assert err.kind == ERROR_KIND_INVALID_RANKING
    # Se leyó como mucho el límite más el chunk que lo cruzó; nunca el cuerpo entero.
    assert MAX_BODY_BYTES < response.bytes_served <= MAX_BODY_BYTES + BODY_CHUNK_BYTES
    assert response.bytes_served < len(_oversized_json(512 * 1024))


def test_503_oversized_without_content_length_is_still_controlled() -> None:
    response = _FakeResponse(503, b"x" * (MAX_BODY_BYTES + 4096), content_length=None)
    err = _fetch_error(response)
    assert err.kind == ERROR_KIND_HTTP_BACKEND
    assert err.http_status == 503
    assert err.error_type is None
    assert response.bytes_served <= MAX_BODY_BYTES + BODY_CHUNK_BYTES


def test_503_oversized_with_content_length_fails_early() -> None:
    response = _FakeResponse(500, b"x" * (MAX_BODY_BYTES + 1))
    err = _fetch_error(response)
    assert err.kind == ERROR_KIND_HTTP_BACKEND and err.http_status == 500
    assert response.bytes_served == 0


def test_stream_crossing_limit_mid_iteration_stops_immediately() -> None:
    # Content-Length miente (pequeño); el flujo real cruza el límite en un chunk.
    body = _oversized_json(10 * BODY_CHUNK_BYTES)
    response = _FakeResponse(200, body, content_length=10, chunk_size=BODY_CHUNK_BYTES)
    err = _fetch_error(response)
    assert err.kind == ERROR_KIND_INVALID_RANKING
    served_chunks = response.bytes_served // BODY_CHUNK_BYTES
    assert served_chunks == MAX_BODY_BYTES // BODY_CHUNK_BYTES + 1


def test_exact_limit_is_accepted_as_body_and_fails_only_on_contract() -> None:
    response = _FakeResponse(200, _exact_limit_json(), content_length=None)
    err = _fetch_error(response)
    # Pasó el límite de tamaño: se parseó el JSON ({} sin campos) y falló el contrato.
    assert err.kind == ERROR_KIND_INVALID_RANKING
    assert "requeridos" in err.detail
    assert response.bytes_served == MAX_BODY_BYTES


def test_exact_limit_with_declared_length_is_accepted() -> None:
    response = _FakeResponse(200, _exact_limit_json())
    err = _fetch_error(response)
    assert "requeridos" in err.detail and response.bytes_served == MAX_BODY_BYTES


def test_limit_plus_one_is_rejected_for_size_without_and_with_declared_length() -> None:
    no_cl = _FakeResponse(200, _oversized_json(1), content_length=None)
    assert "mayor a" in _fetch_error(no_cl).detail
    with_cl = _FakeResponse(200, _oversized_json(1))
    assert "supera" in _fetch_error(with_cl).detail


@pytest.mark.parametrize(
    "exc, kind",
    [
        (requests.exceptions.ChunkedEncodingError("cut"), ERROR_KIND_CONNECTION),
        (requests.exceptions.ConnectionError("reset"), ERROR_KIND_CONNECTION),
        (requests.exceptions.ReadTimeout("slow"), ERROR_KIND_TIMEOUT),
        (requests.exceptions.ContentDecodingError("gzip"), ERROR_KIND_CONNECTION),
    ],
)
def test_failure_mid_stream_closes_response_and_is_controlled(
    exc: BaseException, kind: str
) -> None:
    response = _FakeResponse(
        200,
        json.dumps(synthetic_payload()),
        content_length=None,
        chunk_size=1024,
        fail_after=4096,
        fail_with=exc,
    )
    err = _fetch_error(response)
    assert err.kind == kind
    assert err.http_status is None


def test_failure_mid_stream_on_error_status_keeps_http_classification() -> None:
    response = _FakeResponse(
        503,
        json.dumps(error_body("upstream_unavailable")),
        content_length=None,
        chunk_size=8,
        fail_after=8,
    )
    err = _fetch_error(response)
    assert err.kind == ERROR_KIND_HTTP_BACKEND and err.http_status == 503
    assert err.error_type is None


def test_bogus_content_length_header_does_not_bypass_the_limit() -> None:
    for bogus in ("abc", "-5", ""):
        response = _FakeResponse(200, _oversized_json(4096), content_length=bogus)
        assert _fetch_error(response).kind == ERROR_KIND_INVALID_RANKING
        assert response.bytes_served <= MAX_BODY_BYTES + BODY_CHUNK_BYTES


def test_response_is_closed_on_success_and_on_every_error_path() -> None:
    paths = [
        _FakeResponse(200, json.dumps(synthetic_payload())),
        _FakeResponse(200, b""),
        _FakeResponse(200, b"{not json"),
        _FakeResponse(200, b"[1, 2]"),
        _FakeResponse(200, _oversized_json()),
        _FakeResponse(503, json.dumps(error_body("upstream_unavailable"))),
        _FakeResponse(418, b"<html>"),
    ]
    for response in paths:
        try:
            _client(_FakeSession(response)).fetch_ranking()
        except BackendError:
            pass
        assert response.closed == 1, f"close() faltó para status {response.status_code}"


# ── errores HTTP y frontera de presentación (Astra MAJOR 2) ──────────────────

MALICIOUS_MESSAGES = [
    r"C:\Users\private\secret",
    "/home/internal/service/key",
    "http://internal-backend:8080/private",
    "postgresql://user:password@db/internal",
    "`**markdown**`",
    "<script>alert('x')</script><img src=x onerror=alert(1)>",
    "línea 1\nlínea 2\r\n\x1b[31mrojo\x00",
    'Traceback (most recent call last):\n  File "/srv/app.py", line 1',
]


def error_body(error_type: str, message: str = "mensaje remoto") -> dict:
    return {"status": "error", "error_type": error_type, "message": message}


@pytest.mark.parametrize(
    "status, error_type",
    [
        (422, "invalid_request"),
        (500, "internal_error"),
        (502, "upstream_invalid_response"),
        (503, "upstream_unavailable"),
        (503, "prototype_unavailable"),
        (503, "data_unavailable"),
        (504, "upstream_timeout"),
    ],
)
def test_http_errors_expose_status_and_contract_error_type_only(
    status: int, error_type: str
) -> None:
    err = _fetch_error(_FakeResponse(status, json.dumps(error_body(error_type))))
    assert err.kind == ERROR_KIND_HTTP_BACKEND
    assert err.http_status == status
    assert err.error_type == error_type
    assert str(status) in err.user_message
    assert not hasattr(err, "backend_message")


def test_known_error_types_match_the_contract_enum() -> None:
    assert KNOWN_ERROR_TYPES == {
        "invalid_request",
        "internal_error",
        "upstream_invalid_response",
        "upstream_unavailable",
        "prototype_unavailable",
        "data_unavailable",
        "upstream_timeout",
    }


@pytest.mark.parametrize("bad_type", MALICIOUS_MESSAGES + ["tipo_503", "", 42, None, ["x"]])
def test_unknown_error_type_is_dropped(bad_type: Any) -> None:
    err = _fetch_error(_FakeResponse(503, json.dumps(error_body(bad_type))))
    assert err.error_type is None
    assert (
        BackendError(ERROR_KIND_HTTP_BACKEND, http_status=503, error_type=bad_type).error_type
        is None
    )


@pytest.mark.parametrize("message", MALICIOUS_MESSAGES)
def test_remote_message_never_persists_in_the_error_object(message: str) -> None:
    err = _fetch_error(_FakeResponse(503, json.dumps(error_body("upstream_unavailable", message))))
    assert not hasattr(err, "backend_message")
    surface = " ".join(
        [err.user_message, str(err), repr(err), err.detail] + [str(v) for v in vars(err).values()]
    )
    for fragment in (
        "secret",
        "internal",
        "password",
        "**markdown**",
        "<script",
        "Traceback",
        "\n",
        "\x1b",
        "\x00",
        "C:\\",
    ):
        assert fragment not in surface, f"{fragment!r} se filtró en {surface!r}"


def test_http_error_without_json_body_still_typed() -> None:
    err = _fetch_error(_FakeResponse(503, "<html>gateway</html>"))
    assert err.kind == ERROR_KIND_HTTP_BACKEND
    assert err.http_status == 503
    assert err.error_type is None


def test_http_error_with_non_object_json_body() -> None:
    err = _fetch_error(_FakeResponse(503, '["upstream_unavailable"]'))
    assert err.error_type is None


def test_unknown_http_status_has_generic_message() -> None:
    err = _fetch_error(_FakeResponse(418, "{}"))
    assert err.http_status == 418
    assert "418" in err.user_message


@pytest.mark.parametrize("body", [b"", b"   \n"])
def test_empty_body_is_invalid_json(body: bytes) -> None:
    assert _fetch_error(_FakeResponse(200, body)).kind == ERROR_KIND_INVALID_JSON


@pytest.mark.parametrize("body", [b"{not json", b"\xff\xfe\x00", b"nulo"])
def test_invalid_json_body(body: bytes) -> None:
    assert _fetch_error(_FakeResponse(200, body)).kind == ERROR_KIND_INVALID_JSON


def test_200_with_invalid_ranking_fails_closed() -> None:
    payload = synthetic_payload()
    payload["cells"].pop()
    assert _fetch_error(_FakeResponse(200, json.dumps(payload))).kind == ERROR_KIND_INVALID_RANKING


def test_200_with_json_array_fails_closed() -> None:
    assert _fetch_error(_FakeResponse(200, "[1, 2]")).kind == ERROR_KIND_INVALID_RANKING


def test_user_messages_never_leak_host_path_or_stack() -> None:
    session = _FakeSession(raise_exc=requests.exceptions.ConnectionError("http://secreto:8080/x"))
    with pytest.raises(BackendError) as info:
        _client(session, base="http://secreto:8080").fetch_ranking()
    for text in (info.value.user_message, str(info.value), info.value.detail):
        assert "secreto" not in text
        assert "8080" not in text
        assert RANKING_PATH not in text
        assert "Traceback" not in text and "requests." not in text


def test_every_error_kind_has_a_user_message() -> None:
    for kind in (
        ERROR_KIND_CONNECTION,
        ERROR_KIND_TIMEOUT,
        ERROR_KIND_INVALID_JSON,
        ERROR_KIND_INVALID_RANKING,
    ):
        assert BackendError(kind).user_message
    assert BackendError(ERROR_KIND_HTTP_BACKEND, http_status=503).user_message

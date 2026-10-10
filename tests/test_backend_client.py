"""SAPI-61 — UNIT: `app.utils.backend_client` (CA2, CA3-ranking/empates, CA4).

Cubre el parse fail-closed del `RankingResult` v0, la tolerancia a campos
aditivos, y el cliente HTTP con una `requests.Session` falsa (sin red). El
stub HTTP real vive en `tests/test_sapi61_http_stub.py`.
"""

from __future__ import annotations

import copy
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pytest
import requests

from app.utils.backend_client import (
    ADDITIVE_FIELDS,
    ERROR_KIND_CONNECTION,
    ERROR_KIND_HTTP_BACKEND,
    ERROR_KIND_INVALID_JSON,
    ERROR_KIND_INVALID_RANKING,
    ERROR_KIND_TIMEOUT,
    EXPECTED_CELL_IDS,
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


# ── cliente HTTP con sesión falsa ────────────────────────────────────────────


class _FakeResponse:
    def __init__(self, status: int, body: bytes | str = b"", json_error: bool = False) -> None:
        self.status_code = status
        self.content = body.encode("utf-8") if isinstance(body, str) else body
        self._json_error = json_error

    def json(self) -> Any:
        if self._json_error:
            raise ValueError("no json")
        return json.loads(self.content.decode("utf-8"))


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


def test_fetch_ranking_hits_the_contract_path_with_accept_and_timeout() -> None:
    session = _FakeSession(_FakeResponse(200, json.dumps(synthetic_payload())))
    view = _client(session).fetch_ranking()
    assert len(view.cells) == 50
    call = session.calls[0]
    assert call["url"] == "http://backend.test:8080/api/v1/ranking"
    assert call["headers"]["Accept"] == "application/json"
    assert call["timeout"] == (1.5, 2.5)
    assert call["params"] is None


def test_fetch_ranking_forwards_forecast_time_as_query() -> None:
    session = _FakeSession(_FakeResponse(200, json.dumps(synthetic_payload())))
    _client(session).fetch_ranking(forecast_time="2026-10-01T18:00:00-03:00")
    assert session.calls[0]["params"] == {"forecast_time": "2026-10-01T18:00:00-03:00"}


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


def test_invalid_timeout_env_falls_back_to_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SAPI_BACKEND_CONNECT_TIMEOUT", "rápido")
    monkeypatch.setenv("SAPI_BACKEND_READ_TIMEOUT", "-3")
    assert BackendRankingClient.from_env().timeout == (3.0, 90.0)


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


@pytest.mark.parametrize("status", [422, 500, 502, 503, 504])
def test_http_errors_expose_status_error_type_and_sanitised_message(status: int) -> None:
    body = {
        "status": "error",
        "error_type": f"tipo_{status}",
        "message": "Mensaje\x00 \x1bdel backend",
    }
    with pytest.raises(BackendError) as info:
        _client(_FakeSession(_FakeResponse(status, json.dumps(body)))).fetch_ranking()
    err = info.value
    assert err.kind == ERROR_KIND_HTTP_BACKEND
    assert err.http_status == status
    assert err.error_type == f"tipo_{status}"
    assert err.backend_message == "Mensaje del backend"
    assert f"HTTP {status}" in err.user_message or f"({status})" in err.user_message


def test_http_error_without_json_body_still_typed() -> None:
    with pytest.raises(BackendError) as info:
        _client(
            _FakeSession(_FakeResponse(503, "<html>gateway</html>", json_error=True))
        ).fetch_ranking()
    assert info.value.kind == ERROR_KIND_HTTP_BACKEND
    assert info.value.http_status == 503
    assert info.value.error_type is None and info.value.backend_message is None


def test_unknown_http_status_has_generic_message() -> None:
    with pytest.raises(BackendError) as info:
        _client(_FakeSession(_FakeResponse(418, "{}"))).fetch_ranking()
    assert info.value.http_status == 418
    assert "418" in info.value.user_message


def test_remote_message_is_truncated() -> None:
    body = {"status": "error", "error_type": "x", "message": "m" * 1000}
    with pytest.raises(BackendError) as info:
        _client(_FakeSession(_FakeResponse(500, json.dumps(body)))).fetch_ranking()
    assert len(info.value.backend_message) == 200


@pytest.mark.parametrize("body", [b"", b"   \n"])
def test_empty_body_is_invalid_json(body: bytes) -> None:
    with pytest.raises(BackendError) as info:
        _client(_FakeSession(_FakeResponse(200, body))).fetch_ranking()
    assert info.value.kind == ERROR_KIND_INVALID_JSON


def test_invalid_json_body() -> None:
    with pytest.raises(BackendError) as info:
        _client(_FakeSession(_FakeResponse(200, "{not json", json_error=True))).fetch_ranking()
    assert info.value.kind == ERROR_KIND_INVALID_JSON


def test_200_with_invalid_ranking_fails_closed() -> None:
    payload = synthetic_payload()
    payload["cells"].pop()
    with pytest.raises(BackendError) as info:
        _client(_FakeSession(_FakeResponse(200, json.dumps(payload)))).fetch_ranking()
    assert info.value.kind == ERROR_KIND_INVALID_RANKING


def test_200_with_json_array_fails_closed() -> None:
    with pytest.raises(BackendError) as info:
        _client(_FakeSession(_FakeResponse(200, "[1, 2]"))).fetch_ranking()
    assert info.value.kind == ERROR_KIND_INVALID_RANKING


def test_oversized_body_is_rejected() -> None:
    big = b"{" + b" " * MAX_BODY_BYTES + b"}"
    with pytest.raises(BackendError) as info:
        _client(_FakeSession(_FakeResponse(200, big))).fetch_ranking()
    assert info.value.kind == ERROR_KIND_INVALID_RANKING


def test_user_messages_never_leak_host_path_or_stack() -> None:
    session = _FakeSession(raise_exc=requests.exceptions.ConnectionError("http://secreto:8080/x"))
    with pytest.raises(BackendError) as info:
        _client(session, base="http://secreto:8080").fetch_ranking()
    for text in (info.value.user_message, str(info.value)):
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

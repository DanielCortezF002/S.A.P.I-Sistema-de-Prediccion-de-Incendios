"""BRIDGE-01: contrato de salida de `/score` (tools/n8n_bridge/contract.py).

Un resultado de scoring incompleto o inconsistente nunca sale como 200:
el puente responde 500 `internal_error` (fallo interno), distinto del 503
de insumos no disponibles. Todos los tests mockean `score_current_grid`.
"""

from __future__ import annotations

import dataclasses
from datetime import date, datetime

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import tools.n8n_bridge.app as bridge_app
from src.inference.prototype_service import (
    FIRMS_STATUS_STALE,
    PrototypeUnavailableError,
)
from test_n8n_bridge import _fixture_result
from tools.n8n_bridge.contract import InvalidScoreResultError, validate_grid_result

client = TestClient(bridge_app.app)


def _score(monkeypatch, result):
    monkeypatch.setattr(bridge_app, "score_current_grid", lambda: result)
    monkeypatch.setattr(bridge_app, "_read_metadata_json", lambda: None)
    return client.get("/score")


def _assert_fail_closed(resp):
    assert resp.status_code == 500
    body = resp.json()
    assert body == {
        "status": "error",
        "error_type": "internal_error",
        "message": body["message"],
    }
    assert "cells" not in body and "score" not in body


def _with_cells(result, cells):
    return dataclasses.replace(result, cells=cells)


def _set_cell(result, index, **changes):
    cells = list(result.cells)
    cells[index] = dataclasses.replace(cells[index], **changes)
    return _with_cells(result, cells)


# --- VALID -------------------------------------------------------------------


def test_valid_01_fifty_valid_cells_accepted(monkeypatch):
    resp = _score(monkeypatch, _fixture_result())
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert len(body["cells"]) == 50
    assert sorted(c["rank"] for c in body["cells"]) == list(range(1, 51))


def test_valid_all_tied_scores_accepted(monkeypatch):
    """Empates reales del modelo son válidos: rank único, display_rank 1
    compartido por las 50 celdas."""
    resp = _score(monkeypatch, _fixture_result([0.07] * 50))
    assert resp.status_code == 200
    assert {c["display_rank"] for c in resp.json()["cells"]} == {1}


@pytest.mark.parametrize("origin", ["baseline", "reproducibility"])
def test_valid_other_firms_origins_accepted(monkeypatch, origin):
    result = dataclasses.replace(_fixture_result(), firms_origin=origin)
    assert _score(monkeypatch, result).status_code == 200


def test_valid_stale_firms_is_scored_not_rejected(monkeypatch):
    """Lag 4..7 es FIRMS DESACTUALIZADO: la implementación sí puntúa (con
    aviso); retenerlo es política de n8n, no del contrato del puente."""
    result = dataclasses.replace(
        _fixture_result(),
        firms_coverage_end=date(2026, 9, 15),
        firms_lag_days=5,
        firms_status=FIRMS_STATUS_STALE,
    )
    assert _score(monkeypatch, result).status_code == 200


def test_valid_optional_cell_fields_may_be_null(monkeypatch):
    result = _set_cell(_fixture_result(), 3, elevation=None, slope=None)
    assert _score(monkeypatch, result).status_code == 200


# --- INVALID -----------------------------------------------------------------


def test_invalid_01_forty_nine_cells(monkeypatch):
    result = _fixture_result()
    _assert_fail_closed(_score(monkeypatch, _with_cells(result, result.cells[:49])))


def test_invalid_02_fifty_one_cells(monkeypatch):
    result = _fixture_result()
    extra = dataclasses.replace(result.cells[-1], cell_id="VP-051", rank=51)
    _assert_fail_closed(
        _score(monkeypatch, _with_cells(result, result.cells + [extra]))
    )


def test_invalid_03_duplicate_cell_id(monkeypatch):
    _assert_fail_closed(
        _score(monkeypatch, _set_cell(_fixture_result(), 1, cell_id="VP-001"))
    )


def test_invalid_03b_cell_id_outside_grid(monkeypatch):
    _assert_fail_closed(
        _score(monkeypatch, _set_cell(_fixture_result(), 1, cell_id="C01"))
    )


def test_invalid_04_duplicate_rank(monkeypatch):
    _assert_fail_closed(_score(monkeypatch, _set_cell(_fixture_result(), 2, rank=2)))


def test_invalid_05_rank_gap(monkeypatch):
    _assert_fail_closed(_score(monkeypatch, _set_cell(_fixture_result(), 49, rank=51)))


def test_invalid_06_no_rank_1(monkeypatch):
    result = _fixture_result()
    cells = [dataclasses.replace(c, rank=c.rank + 1) for c in result.cells]
    _assert_fail_closed(_score(monkeypatch, _with_cells(result, cells)))


def test_invalid_07_multiple_rank_1(monkeypatch):
    _assert_fail_closed(_score(monkeypatch, _set_cell(_fixture_result(), 49, rank=1)))


def test_invalid_08_nan_score(monkeypatch):
    _assert_fail_closed(
        _score(monkeypatch, _set_cell(_fixture_result(), 10, score=float("nan")))
    )


@pytest.mark.parametrize("value", [float("inf"), float("-inf")], ids=["inf", "-inf"])
def test_invalid_09_infinite_score(monkeypatch, value):
    _assert_fail_closed(_score(monkeypatch, _set_cell(_fixture_result(), 10, score=value)))


@pytest.mark.parametrize(
    "field,value",
    [("score", None), ("rank", None), ("cell_id", None), ("cell_id", ""),
     ("score", "0.3"), ("rank", 1.0), ("rank", True), ("score", 1.5)],
)
def test_invalid_cell_field_types(monkeypatch, field, value):
    _assert_fail_closed(_score(monkeypatch, _set_cell(_fixture_result(), 5, **{field: value})))


@pytest.mark.parametrize(
    "field",
    ["model_version", "model_status", "station_id", "forecast_time",
     "weather_timestamp", "horizon_hours", "age_hours", "freshness",
     "meteo_actual", "firms_origin", "firms_coverage_end", "firms_lag_days",
     "firms_status", "inputs_fingerprint"],
)
def test_invalid_10_missing_required_metadata(monkeypatch, field):
    result = dataclasses.replace(_fixture_result(), **{field: None})
    _assert_fail_closed(_score(monkeypatch, result))


@pytest.mark.parametrize(
    "fingerprint",
    ["", "a" * 63, "a" * 65, "A" * 64, "g" * 64, " " + "a" * 63, 123],
    ids=["empty", "short", "long", "uppercase", "non_hex", "whitespace", "not_str"],
)
def test_invalid_11_malformed_inputs_fingerprint(monkeypatch, fingerprint):
    result = dataclasses.replace(_fixture_result(), inputs_fingerprint=fingerprint)
    _assert_fail_closed(_score(monkeypatch, result))


@pytest.mark.parametrize(
    "changes",
    [
        {"firms_origin": "live"},
        {"firms_status": "CURRENT"},
        {"firms_status": FIRMS_STATUS_STALE},  # lag 1 exige FIRMS AL DÍA
        {"firms_lag_days": 2},  # no coincide con fecha(T) - coverage_end
        {"firms_lag_days": 1.0},
        {"firms_lag_days": "1"},
        {"firms_coverage_end": "2026-09-19"},
        {"firms_coverage_end": datetime(2026, 9, 19)},
        {"firms_coverage_end": date(2026, 9, 1), "firms_lag_days": 19},  # > máx
    ],
    ids=["origin", "status_unknown", "status_vs_lag", "lag_mismatch", "lag_float",
         "lag_str", "coverage_str", "coverage_datetime", "lag_over_max"],
)
def test_invalid_12_invalid_firms_metadata(monkeypatch, changes):
    result = dataclasses.replace(_fixture_result(), **changes)
    _assert_fail_closed(_score(monkeypatch, result))


@pytest.mark.parametrize(
    "mutate",
    [
        lambda r: _with_cells(r, []),
        lambda r: _with_cells(r, None),
        lambda r: _with_cells(r, list(reversed(r.cells))[:1] + r.cells[1:]),
        lambda r: _set_cell(r, 0, score=0.0),  # rank 1 con score menor que rank 2
        lambda r: _set_cell(r, 7, display_rank=1),
        lambda r: _set_cell(r, 7, tie_group_size=3),
        lambda r: dataclasses.replace(r, meteo_actual={"temperatura": 20.0}),
        lambda r: dataclasses.replace(
            r, meteo_actual={**r.meteo_actual, "regla_30_30_30": None}
        ),
        lambda r: dataclasses.replace(
            r, forecast_time=pd.Timestamp("2026-09-20T12:00:00")  # sin zona
        ),
        lambda r: dataclasses.replace(r, forecast_time=pd.NaT),
        lambda r: dataclasses.replace(r, age_hours=float("nan")),
        lambda r: dataclasses.replace(r, freshness="OK"),
        lambda r: dataclasses.replace(r, horizon_hours=0),
        lambda r: dataclasses.replace(r, model_version="   "),
    ],
    ids=["no_cells", "cells_none", "cells_mixed", "rank_vs_score_order",
         "display_rank", "tie_group_size", "meteo_incomplete", "meteo_rule_null",
         "naive_forecast_time", "nat_forecast_time", "age_nan", "freshness",
         "horizon_zero", "blank_model_version"],
)
def test_invalid_13_structurally_valid_but_semantically_incomplete(monkeypatch, mutate):
    """GridScoreResult bien tipado como dataclass, pero con contenido que
    no puede describir un ranking operacional."""
    _assert_fail_closed(_score(monkeypatch, mutate(_fixture_result())))


def test_invalid_result_object_missing(monkeypatch):
    _assert_fail_closed(_score(monkeypatch, None))


def test_invalid_result_never_degrades_to_low_risk_payload(monkeypatch):
    """Prohibido: resultado inválido -> celdas vacías / score 0 / 200."""
    result = _with_cells(_fixture_result(), [])
    resp = _score(monkeypatch, result)
    assert resp.status_code != 200
    assert resp.json().get("status") != "ok"


def test_invalid_result_details_only_in_log(monkeypatch, caplog):
    result = _set_cell(_fixture_result(), 10, score=float("nan"))
    with caplog.at_level("ERROR", logger="sapi.n8n_bridge"):
        resp = _score(monkeypatch, result)
    assert "cells[10].score" in caplog.text
    assert "cells[10]" not in resp.text


def test_serialization_failure_also_fails_closed(monkeypatch):
    def boom(result, disclaimer):
        raise TypeError("detalle interno")

    monkeypatch.setattr(bridge_app, "_serialize_grid_result", boom)
    resp = _score(monkeypatch, _fixture_result())
    _assert_fail_closed(resp)
    assert "detalle interno" not in resp.text


def test_invalid_14_upstream_503_behavior_preserved(monkeypatch):
    """Indisponibilidad de insumos sigue siendo 503 -- nunca se confunde
    con el 500 de un resultado interno inválido."""

    def _raise():
        raise PrototypeUnavailableError("FIRMS supera el desfase máximo.")

    monkeypatch.setattr(bridge_app, "score_current_grid", _raise)
    resp = client.get("/score")
    assert resp.status_code == 503
    assert resp.json()["error_type"] == "prototype_unavailable"


def test_validator_raises_with_all_violations():
    result = dataclasses.replace(
        _fixture_result(), inputs_fingerprint=None, firms_origin=None
    )
    with pytest.raises(InvalidScoreResultError) as info:
        validate_grid_result(result)
    assert len(info.value.violations) == 2


def test_validator_accepts_valid_result():
    validate_grid_result(_fixture_result())

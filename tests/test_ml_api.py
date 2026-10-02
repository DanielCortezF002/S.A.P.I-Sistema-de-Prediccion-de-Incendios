"""Tests del servicio ML de S.A.P.I. v2 (SAPI-55, services/ml_api/main.py).

Contrato: contracts/openapi/ml-service.v0.yaml (v0 congelado). Los tests con
el Modelo D real usan `SAPI_REPRODUCIBILITY_MODE=1`: modelo y snapshots del
Hito 1 versionados en git, sin red ni datos locales. El resto mockea
`score_current_grid` para cubrir cada salida de error del contrato.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import services.ml_api.main as ml_api
from src.inference.prototype_service import PrototypeUnavailableError
from src.output.synthetic import synthetic_result

MODEL_D_FINGERPRINT = "33c2eacc49bd0cc130928b5bd182ec523e63614f0e3dd97a129a8d4657f231ff"
CELL_IDS = [f"VP-{i:03d}" for i in range(1, 51)]
RANKING_KEYS = {
    "schema_version",
    "model_version",
    "forecast_time",
    "inputs_fingerprint",
    "score_semantics",
    "scientific_model_validation",
    "horizon_hours",
    "disclaimer",
    "cells",
}
CELL_KEYS = {"cell_id", "score", "rank", "display_rank", "tie_group_size"}
ERROR_KEYS = {"status", "error_type", "message"}

client = TestClient(ml_api.app)


def _ranking_fingerprint(cells: list[dict]) -> str:
    lines = "\n".join(f"{c['cell_id']},{c['score']!r},{c['rank']}" for c in cells)
    return hashlib.sha256(lines.encode()).hexdigest()


def _assert_error(response, status_code: int, error_type: str) -> None:
    assert response.status_code == status_code
    body = response.json()
    assert set(body) == ERROR_KEYS
    assert body["status"] == "error"
    assert body["error_type"] == error_type
    # Mensajes genéricos: sin rutas ni pistas internas.
    assert "data/" not in body["message"] and "\\" not in body["message"]


@pytest.fixture
def reproducible(monkeypatch):
    monkeypatch.setenv("SAPI_REPRODUCIBILITY_MODE", "1")


# --- Modelo D real (modo reproducible) ----------------------------------------


def test_predict_real_model_matches_contract_and_fingerprint(reproducible):
    response = client.post("/predict", json={})
    assert response.status_code == 200
    body = response.json()
    assert set(body) == RANKING_KEYS
    assert body["schema_version"] == "sapi-ranking-v0"
    assert body["model_version"] == "prototype_model_d_v1"
    assert body["score_semantics"] == "relative_rank"
    assert body["scientific_model_validation"] is False
    assert body["horizon_hours"] == 6
    assert pd.Timestamp(body["forecast_time"]) == pd.Timestamp("2026-09-01T00:00Z")
    assert len(body["inputs_fingerprint"]) == 64

    cells = body["cells"]
    assert len(cells) == 50
    assert all(set(c) == CELL_KEYS for c in cells)
    assert sorted(c["cell_id"] for c in cells) == CELL_IDS
    assert [c["rank"] for c in cells] == list(range(1, 51))
    assert cells[0]["cell_id"] == "VP-001"
    assert round(cells[0]["score"], 12) == 0.131293368748
    # Mismo ranking que vigila la sentinela RC-SCI-RANKING de la Release Gate.
    assert _ranking_fingerprint(cells) == MODEL_D_FINGERPRINT


def test_predict_preserves_real_ties(reproducible):
    cells = client.post("/predict", json={}).json()["cells"]
    scores = [c["score"] for c in cells]
    for c in cells:
        assert c["display_rank"] == 1 + sum(s > c["score"] for s in scores)
        assert c["tie_group_size"] == scores.count(c["score"])
    assert sorted({c["tie_group_size"] for c in cells}) == [2, 7, 41]


def test_predict_without_body_uses_latest_real_bucket(reproducible):
    with_body = client.post("/predict", json={}).json()
    without_body = client.post("/predict").json()
    assert without_body["inputs_fingerprint"] == with_body["inputs_fingerprint"]


def test_predict_normalizes_forecast_time_to_utc(reproducible):
    utc = client.post("/predict", json={"forecast_time": "2026-09-01T00:00:00Z"})
    chile = client.post("/predict", json={"forecast_time": "2026-08-31T21:00:00-03:00"})
    assert utc.status_code == chile.status_code == 200
    assert utc.json()["inputs_fingerprint"] == chile.json()["inputs_fingerprint"]
    assert pd.Timestamp(chile.json()["forecast_time"]) == pd.Timestamp(
        "2026-09-01T00:00Z"
    )


def test_predict_future_forecast_time_is_503(reproducible):
    response = client.post("/predict", json={"forecast_time": "2026-09-02T00:00:00Z"})
    _assert_error(response, 503, "prototype_unavailable")


@pytest.mark.parametrize("year", ["0001", "9999"])
def test_predict_extreme_years_never_500(reproducible, year):
    response = client.post(
        "/predict", json={"forecast_time": f"{year}-01-01T00:00:00Z"}
    )
    assert response.status_code in (422, 503)
    assert response.json()["status"] == "error"


# --- Validación del request (422 con el schema Error) ---------------------------


@pytest.mark.parametrize(
    "body",
    [
        {"features": [1, 2, 3]},
        {"forecast_time": "2026-09-01T00:00:00Z", "cell_id": "VP-001"},
        {"forecast_time": "2026-09-01T00:00:00"},
        {"forecast_time": "2026-09-01"},
        {"forecast_time": 1756684800},
        {"forecast_time": "no-es-una-fecha"},
        [1, 2],
    ],
)
def test_predict_rejects_invalid_requests_with_contract_error(body):
    _assert_error(client.post("/predict", json=body), 422, "invalid_request")


# --- Errores de scoring (mock) ---------------------------------------------------


def test_prototype_unavailable_is_503(monkeypatch):
    def _raise(**_kwargs):
        raise PrototypeUnavailableError("detalle interno con data/raw/x.json")

    monkeypatch.setattr(ml_api, "score_current_grid", _raise)
    _assert_error(client.post("/predict", json={}), 503, "prototype_unavailable")


def test_corrupt_input_is_503_data_unavailable(monkeypatch):
    def _raise(**_kwargs):
        raise json.JSONDecodeError("bad", "doc", 0)

    monkeypatch.setattr(ml_api, "score_current_grid", _raise)
    _assert_error(client.post("/predict", json={}), 503, "data_unavailable")


def test_unexpected_exception_is_500(monkeypatch):
    def _raise(**_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(ml_api, "score_current_grid", _raise)
    _assert_error(client.post("/predict", json={}), 500, "internal_error")


def test_result_violating_contract_is_500_never_200(monkeypatch):
    broken = synthetic_result()
    broken = dataclasses.replace(broken, cells=broken.cells[:49])
    monkeypatch.setattr(ml_api, "score_current_grid", lambda **_kwargs: broken)
    _assert_error(client.post("/predict", json={}), 500, "internal_error")


def test_valid_synthetic_result_is_serialized_per_contract(monkeypatch):
    monkeypatch.setattr(
        ml_api, "score_current_grid", lambda **_kwargs: synthetic_result()
    )
    body = client.post("/predict", json={}).json()
    assert set(body) == RANKING_KEYS
    assert [c["display_rank"] for c in body["cells"][:3]] == [1, 1, 3]
    assert [c["tie_group_size"] for c in body["cells"][:2]] == [2, 2]


# --- Health --------------------------------------------------------------------------


def test_health_ok_reads_metadata_without_scoring(monkeypatch):
    def _must_not_score(**_kwargs):
        raise AssertionError("/health no debe ejecutar inferencia")

    monkeypatch.setattr(ml_api, "score_current_grid", _must_not_score)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "model_version": "prototype_model_d_v1"}


def test_health_degraded_is_503(monkeypatch, tmp_path):
    monkeypatch.setattr(ml_api, "METADATA_PATH", tmp_path / "missing.json")
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "model_version": None}


# --- OpenAPI generado vs contrato ------------------------------------------------------


def test_generated_openapi_declares_contract_operations_and_codes():
    spec = ml_api.app.openapi()
    assert set(spec["paths"]) == {"/health", "/predict"}
    assert set(spec["paths"]["/health"]["get"]["responses"]) >= {"200", "503"}
    assert set(spec["paths"]["/predict"]["post"]["responses"]) >= {
        "200",
        "422",
        "500",
        "503",
    }
    schemas = spec["components"]["schemas"]
    assert set(schemas["RankingResult"]["required"]) == RANKING_KEYS - {
        "horizon_hours",
        "disclaimer",
    }
    assert set(schemas["CellRanking"]["required"]) == CELL_KEYS


def test_no_field_is_named_as_a_probability():
    schemas = ml_api.app.openapi()["components"]["schemas"]
    fields = {f for s in schemas.values() for f in s.get("properties", {})}
    assert not [f for f in fields if "probab" in f.lower()]

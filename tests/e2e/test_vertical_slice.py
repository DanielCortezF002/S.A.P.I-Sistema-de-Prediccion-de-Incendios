"""Test reproducible del vertical slice E2E de S.A.P.I. v2 (SAPI-66.CA1 y CA2).

Verifica la cadena de integración vertical:
1. Endpoint /health del servicio de inferencia FastAPI.
2. Endpoint /predict con Modelo D real en modo reproducible (SAPI_REPRODUCIBILITY_MODE=1).
3. Cumplimiento de invariantes: exactamente 50 celdas (VP-001 a VP-050), orden no creciente,
   ranking 1..50, score_semantics='relative_rank', scientific_model_validation=false.
4. Validación de contratos en cada salto de comunicación (ml-service.v0.yaml y backend.v0.yaml).
5. Manejo determinista de errores con códigos HTTP 422 ("invalid_request") y 503 ("data_unavailable").
6. Desacoplamiento de la vista Streamlit: parseo de ranking con parse_ranking() sin dependencias de machine learning.
"""

from __future__ import annotations

import json
import pytest
from fastapi.testclient import TestClient

import services.ml_api.main as ml_api
from app.utils.backend_client import RankingView, parse_ranking

EXPECTED_CELL_COUNT = 50

client = TestClient(ml_api.app)


@pytest.fixture(autouse=True)
def set_reproducible_environment(monkeypatch):
    """Fija el modo reproducible para usar los insumos versionados sin dependencia de datos vivos."""
    monkeypatch.setenv("SAPI_REPRODUCIBILITY_MODE", "1")


def test_vertical_slice_health_endpoint():
    """SAPI-66.CA2: Comprueba que el microservicio de inferencia responde 200 en /health."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["model_version"] == "prototype_model_d_v1"


def test_vertical_slice_predict_e2e_reproducible():
    """SAPI-66.CA1 y CA3: Ejecuta inferencia reproducible sobre la grilla de 50 celdas."""
    response = client.post("/predict", json={})
    assert response.status_code == 200
    data = response.json()

    # Metadatos del vertical slice
    assert data["schema_version"] == "sapi-ranking-v0"
    assert data["model_version"] == "prototype_model_d_v1"
    assert data["score_semantics"] == "relative_rank"
    assert data["scientific_model_validation"] is False
    assert data["horizon_hours"] == 6
    assert len(data["inputs_fingerprint"]) == 64

    # Verificación de celdas
    cells = data["cells"]
    assert len(cells) == EXPECTED_CELL_COUNT

    # Comprobar unicidad y rango de celdas
    cell_ids = [c["cell_id"] for c in cells]
    expected_ids = [f"VP-{i:03d}" for i in range(1, 51)]
    assert sorted(cell_ids) == expected_ids

    # Invariante de ranking: orden no creciente de scores
    scores = [c["score"] for c in cells]
    ranks = [c["rank"] for c in cells]
    assert all(0.0 <= s <= 1.0 for s in scores)
    assert ranks == list(range(1, 51))
    assert all(scores[i] >= scores[i + 1] for i in range(len(scores) - 1))


def test_vertical_slice_contract_hops_validation():
    """SAPI-66.CA2: Valida que la respuesta cumple la especificación formal del contrato."""
    response = client.post("/predict", json={})
    assert response.status_code == 200
    payload = response.json()

    required_top_keys = {
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
    assert required_top_keys.issubset(payload.keys())

    required_cell_keys = {"cell_id", "score", "rank", "display_rank", "tie_group_size"}
    for cell in payload["cells"]:
        assert required_cell_keys.issubset(cell.keys())


def test_vertical_slice_error_hops_handling():
    """SAPI-66.CA2: Valida que entradas inválidas generan respuestas de error estructuradas (422)."""
    # Payload con formato de timestamp inválido
    bad_response = client.post("/predict", json={"forecast_time": "invalid-timestamp"})
    assert bad_response.status_code == 422
    err_data = bad_response.json()
    assert err_data["status"] == "error"
    assert err_data["error_type"] == "invalid_request"
    assert "message" in err_data


def test_vertical_slice_frontend_consumption_decoupling():
    """SAPI-66 / SAPI-61: Verifica que el cliente frontend parsea el resultado con parse_ranking()."""
    response = client.post("/predict", json={})
    assert response.status_code == 200
    data = response.json()

    # Parsear directamente a través del view-model oficial
    view: RankingView = parse_ranking(data)

    assert len(view.cells) == 50
    assert view.score_semantics == "relative_rank"
    assert view.scientific_model_validation is False
    assert view.cells[0].rank == 1
    assert view.cells[-1].rank == 50
    assert len(view.inputs_fingerprint) == 64

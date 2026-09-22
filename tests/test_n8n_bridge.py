"""Tests del puente HTTP n8n-bridge (tools/n8n_bridge/app.py).

Todos los tests mockean `score_current_grid` / lectura de metadata --
ninguno requiere el modelo real ni datos reales en disco (igual que el
resto de la suite trata los casos que sí necesitan datos reales como
categoria aparte, con marca explicita).
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

import tools.n8n_bridge.app as bridge_app
from src.inference.prototype_service import CellScore, GridScoreResult, PrototypeUnavailableError
from src.procesamiento.pipeline_validators import FORBIDDEN_LEGACY_REFERENCES, validate_pipeline_isolation

client = TestClient(bridge_app.app)


def _fixture_result() -> GridScoreResult:
    cell = CellScore(
        cell_id="C01",
        score=0.42,
        rank=1,
        display_rank=1,
        tie_group_size=1,
        geometry={"min_lon": -71.6, "min_lat": -33.1, "max_lon": -71.5, "max_lat": -33.0},
        elevation=512.3,
        slope=8.1,
        historical_count=3,
    )
    return GridScoreResult(
        forecast_time=pd.Timestamp("2026-09-20T12:00:00Z"),
        horizon_hours=6,
        station_id="330007",
        station_name="Rodelillo",
        weather_timestamp=pd.Timestamp("2026-09-20T06:00:00Z"),
        age_hours=6.3,
        freshness="DATOS RECIENTES",
        model_version="prototype_model_d_v1",
        model_status="PROTOTYPE / EXPLORATORY",
        meteo_actual={
            "temperatura": 21.4,
            "humedad_relativa": 35.0,
            "velocidad_viento_kmh": 12.1,
            "regla_30_30_30": False,
            "momento_observacion": pd.Timestamp("2026-09-20T06:00:00Z"),
        },
        cells=[cell],
    )


def test_health_ok_when_model_and_metadata_present(monkeypatch, tmp_path):
    model_path = tmp_path / "prototype_model_d.pkl"
    model_path.write_bytes(b"fake")
    metadata_path = tmp_path / "prototype_model_d_metadata.json"
    metadata_path.write_text(json.dumps({"model_version": "prototype_model_d_v1"}), encoding="utf-8")
    monkeypatch.setattr(bridge_app, "MODEL_PATH", model_path)
    monkeypatch.setattr(bridge_app, "METADATA_PATH", metadata_path)

    resp = client.get("/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["model_path_exists"] is True
    assert body["model_version"] == "prototype_model_d_v1"


def test_health_degraded_when_model_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(bridge_app, "MODEL_PATH", tmp_path / "missing.pkl")
    monkeypatch.setattr(bridge_app, "METADATA_PATH", tmp_path / "missing.json")

    resp = client.get("/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["model_path_exists"] is False
    assert body["model_version"] is None


def test_health_degraded_when_metadata_corrupt(monkeypatch, tmp_path):
    model_path = tmp_path / "prototype_model_d.pkl"
    model_path.write_bytes(b"fake")
    metadata_path = tmp_path / "prototype_model_d_metadata.json"
    metadata_path.write_text("{ esto no es json valido", encoding="utf-8")
    monkeypatch.setattr(bridge_app, "MODEL_PATH", model_path)
    monkeypatch.setattr(bridge_app, "METADATA_PATH", metadata_path)

    resp = client.get("/health")

    assert resp.status_code == 200
    assert resp.json()["status"] == "degraded"


def test_score_200_shape_and_disclaimer(monkeypatch):
    monkeypatch.setattr(bridge_app, "score_current_grid", lambda: _fixture_result())
    monkeypatch.setattr(bridge_app, "_read_metadata_json", lambda: {"aviso": "AVISO DE PRUEBA"})

    resp = client.get("/score")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["model_version"] == "prototype_model_d_v1"
    assert body["model_status"] == "PROTOTYPE / EXPLORATORY"
    assert body["disclaimer"] == "AVISO DE PRUEBA"
    assert body["forecast_time"] == "2026-09-20T12:00:00+00:00"
    assert body["weather_timestamp"] == "2026-09-20T06:00:00+00:00"
    assert body["freshness"] == "DATOS RECIENTES"
    assert body["meteo_actual"]["momento_observacion"] == "2026-09-20T06:00:00+00:00"
    assert body["cells"] == [
        {
            "cell_id": "C01",
            "score": 0.42,
            "rank": 1,
            "display_rank": 1,
            "tie_group_size": 1,
            "geometry": {"min_lon": -71.6, "min_lat": -33.1, "max_lon": -71.5, "max_lat": -33.0},
            "elevation": 512.3,
            "slope": 8.1,
            "historical_count": 3,
        }
    ]


def test_score_disclaimer_falls_back_when_metadata_unreadable(monkeypatch):
    monkeypatch.setattr(bridge_app, "score_current_grid", lambda: _fixture_result())
    monkeypatch.setattr(bridge_app, "_read_metadata_json", lambda: None)

    resp = client.get("/score")

    assert resp.status_code == 200
    assert resp.json()["disclaimer"] == bridge_app._FALLBACK_DISCLAIMER


def test_score_503_on_prototype_unavailable(monkeypatch):
    def _raise():
        raise PrototypeUnavailableError(
            "No existe el modelo del prototipo en models/prototype_model_d.pkl."
        )

    monkeypatch.setattr(bridge_app, "score_current_grid", _raise)

    resp = client.get("/score")

    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "error"
    assert body["error_type"] == "prototype_unavailable"
    assert "prototype_model_d.pkl" in body["message"]


def test_score_500_hides_internal_details(monkeypatch):
    def _raise():
        raise ValueError("boom - detalle interno que no debe fugarse")

    monkeypatch.setattr(bridge_app, "score_current_grid", _raise)

    resp = client.get("/score")

    assert resp.status_code == 500
    body = resp.json()
    assert body["status"] == "error"
    assert body["error_type"] == "internal_error"
    assert "boom" not in body["message"]


def test_score_ignores_unexpected_query_params(monkeypatch):
    monkeypatch.setattr(bridge_app, "score_current_grid", lambda: _fixture_result())
    monkeypatch.setattr(bridge_app, "_read_metadata_json", lambda: {"aviso": "AVISO"})

    resp = client.get(
        "/score",
        params={"forecast_time": "2099-01-01T00:00:00Z", "cmd": "rm -rf /"},
    )

    assert resp.status_code == 200  # parametros libres se ignoran, nunca se interpretan


def test_bridge_module_does_not_import_legacy_pipeline():
    """Reusa el mismo mecanismo que ya protege a `prototype_service.py`
    (ver tests/test_prototype_service.py::test_no_legacy_imports_in_
    prototype_modules) en vez de una lista de tokens ad-hoc -- una lista
    propia corre el riesgo de marcar como "legacy" nombres que el propio
    docstring de este módulo menciona en prosa (p. ej. "matriz_features")
    al explicar qué NO usa, que es exactamente lo que pasó al escribir
    este test por primera vez."""
    result = validate_pipeline_isolation(
        [Path(bridge_app.__file__)], forbidden=FORBIDDEN_LEGACY_REFERENCES
    )
    assert result.status == "PASS", result.detail

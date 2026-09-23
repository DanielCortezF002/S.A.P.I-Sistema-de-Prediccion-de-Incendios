"""Tests del puente HTTP n8n-bridge (tools/n8n_bridge/app.py).

Todos los tests mockean `score_current_grid` / lectura de metadata --
ninguno requiere el modelo real ni datos reales en disco (igual que el
resto de la suite trata los casos que sí necesitan datos reales como
categoria aparte, con marca explicita).
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import src.inference.prototype_service as prototype_service
import tools.n8n_bridge.app as bridge_app
from src.inference.prototype_service import CellScore, GridScoreResult, PrototypeUnavailableError
from src.procesamiento.pipeline_validators import FORBIDDEN_LEGACY_REFERENCES, validate_pipeline_isolation
from test_docker_build_hygiene import _service_block

REPO_ROOT = Path(__file__).resolve().parent.parent
BRIDGE_PORT = "8600"

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


@pytest.mark.parametrize(
    "exc",
    [
        json.JSONDecodeError("Expecting value", "{ truncado", 2),
        FileNotFoundError(2, "No such file or directory", "/app/data/raw/dmc_meteo_x.json"),
        FileNotFoundError(2, "No such file or directory", "/app/data/processed/nasa_firms.csv"),
        pd.errors.EmptyDataError("No columns to parse from file"),
        pd.errors.ParserError("Error tokenizing data"),
    ],
    ids=["dmc_json_decode", "dmc_missing", "firms_missing", "firms_empty", "firms_malformed"],
)
def test_score_503_on_data_input_errors(monkeypatch, exc):
    def _raise():
        raise exc

    monkeypatch.setattr(bridge_app, "score_current_grid", _raise)

    resp = client.get("/score")

    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "error"
    assert body["error_type"] == "data_unavailable"
    assert type(exc).__name__ in body["message"]
    assert "/app/data" not in body["message"]  # rutas internas solo al log


def test_score_503_on_real_corrupt_dmc_json(monkeypatch, tmp_path):
    """Sin mockear el parser: un JSON DMC truncado llega como
    JSONDecodeError desde `parse_dmc_json` real (no lo envuelve en
    DmcFormatError) y el puente lo responde como 503, no 500."""
    (tmp_path / "dmc_meteo_2026-09-20.json").write_text('{"330007": {"datos"', encoding="utf-8")
    monkeypatch.setenv("SAPI_REPRODUCIBILITY_MODE", "1")
    monkeypatch.setattr(prototype_service, "REPRODUCIBILITY_DMC_DIR", tmp_path)
    monkeypatch.setattr(
        prototype_service,
        "_load_model",
        lambda: (object(), {"feature_columns": [], "horizon_hours": 6}),
    )

    resp = client.get("/score")

    assert resp.status_code == 503
    assert resp.json()["error_type"] == "data_unavailable"
    assert "JSONDecodeError" in resp.json()["message"]


@pytest.mark.parametrize(
    "exc",
    [
        ValueError("boom - detalle interno que no debe fugarse"),
        KeyError("boom"),
        TypeError("boom"),
        PermissionError(13, "boom"),
    ],
    ids=["value_error", "key_error", "type_error", "permission_error"],
)
def test_score_500_hides_internal_details(monkeypatch, exc):
    """Un error de programación no se disfraza de indisponibilidad de
    datos: sigue siendo 500 (con traza en el log), sin detalles en la
    respuesta."""

    def _raise():
        raise exc

    monkeypatch.setattr(bridge_app, "score_current_grid", _raise)

    resp = client.get("/score")

    assert resp.status_code == 500
    body = resp.json()
    assert body["status"] == "error"
    assert body["error_type"] == "internal_error"
    assert "boom" not in body["message"]


def test_score_passes_model_d_ranking_through_unchanged(monkeypatch):
    """El puente no reordena, redondea ni recalcula: devuelve el orden y
    los scores exactos de `score_current_grid()` (Model D / ranking)."""
    base = _fixture_result()
    scores = [0.13129336874795144, 0.12, 0.12, 0.05]
    cells = [
        dataclasses.replace(base.cells[0], cell_id=f"VP-00{i}", score=s, rank=i, display_rank=i)
        for i, s in enumerate(scores, start=1)
    ]
    result = dataclasses.replace(base, cells=cells)
    monkeypatch.setattr(bridge_app, "score_current_grid", lambda: result)
    monkeypatch.setattr(bridge_app, "_read_metadata_json", lambda: None)

    body = client.get("/score").json()

    assert [(c["cell_id"], c["score"], c["rank"]) for c in body["cells"]] == [
        (c.cell_id, c.score, c.rank) for c in cells
    ]


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


# --- Seguridad Docker/Compose del puente (SAPI-71) ---------------------------
# Estáticos: leen docker-compose.yml y Dockerfile.n8n-bridge tal como están
# versionados. La verificación empírica (imagen sin secretos, montajes no
# escribibles, bind real) se hace construyendo y levantando el servicio.


def _bridge_block() -> list[str]:
    block = _service_block((REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8"), "n8n-bridge")
    assert block, "servicio n8n-bridge no encontrado en docker-compose.yml"
    return block


def _list_entries(block: list[str], key: str) -> list[str]:
    """Entradas `- ...` bajo `key:` dentro del bloque del servicio."""
    entries, inside = [], False
    for line in block:
        stripped = line.strip()
        if stripped == f"{key}:":
            inside = True
            continue
        if inside:
            if stripped.startswith("- "):
                entries.append(stripped[2:].strip().strip('"'))
            elif stripped and not stripped.startswith("#"):
                break
    return entries


def _bridge_config_lines() -> list[str]:
    """Líneas efectivas (sin comentarios) del servicio y su Dockerfile."""
    dockerfile = (REPO_ROOT / "Dockerfile.n8n-bridge").read_text(encoding="utf-8").splitlines()
    return [
        line.split("#", 1)[0]
        for line in _bridge_block() + dockerfile
        if line.split("#", 1)[0].strip()
    ]


def test_bridge_does_not_receive_env_file():
    assert not any(line.strip().startswith("env_file") for line in _bridge_config_lines())


def test_bridge_mounts_only_data_and_models_read_only():
    assert _list_entries(_bridge_block(), "volumes") == [
        "./data:/app/data:ro",
        "./models:/app/models:ro",
    ]


def test_bridge_published_only_on_loopback_8600():
    assert _list_entries(_bridge_block(), "ports") == [f"127.0.0.1:{BRIDGE_PORT}:{BRIDGE_PORT}"]


def test_bridge_uvicorn_listens_on_published_container_port():
    dockerfile = (REPO_ROOT / "Dockerfile.n8n-bridge").read_text(encoding="utf-8")
    assert f"EXPOSE {BRIDGE_PORT}" in dockerfile
    assert f'"--port", "{BRIDGE_PORT}"' in dockerfile


@pytest.mark.parametrize("forbidden", ["docker.sock", "DOCKER_HOST"])
def test_bridge_has_no_docker_control(forbidden):
    assert not any(forbidden in line for line in _bridge_config_lines())


def test_bridge_dockerfile_never_copies_env_explicitly():
    """El único `COPY . .` queda filtrado por .dockerignore (SAPI-70,
    ver tests/test_docker_build_hygiene.py); ningún COPY nombra .env."""
    copies = [line for line in _bridge_config_lines() if line.strip().upper().startswith("COPY")]
    assert copies == ["COPY requirements.txt requirements-dev.txt ./", "COPY . ."]

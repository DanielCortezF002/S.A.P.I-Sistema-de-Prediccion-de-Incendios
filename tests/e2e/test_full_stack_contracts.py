"""CA2: conformidad de contratos por servicio sobre el stack real.

Este modulo NO simula respuestas: llama por HTTP real a FastAPI (``ml-api``) y a
Spring Boot (``backend``) y valida cada cuerpo contra los contratos congelados de
``contracts/openapi/``.

Cobertura honesta (ver ``coverage`` en el JSON emitido):

- Response 200 de FastAPI contra ``ml-service.v0.yaml#RankingResult``.
- Response 422 de FastAPI contra ``ml-service.v0.yaml#Error``.
- Response 200 y 422 del backend contra ``backend.v0.yaml`` (que referencia el
  mismo ``RankingResult``/``Error``).
- Health de ambos servicios contra sus esquemas.

Lo que **no** se observa: el cuerpo exacto que Spring Boot envia a FastAPI ni el
que Streamlit envia al backend. Sin un proxy/tap esos saltos no se pueden
capturar, por lo que la validacion "por salto" se clasifica PARCIAL.

Se omite por defecto:

    $env:SAPI_E2E_FULL_STACK = "1"
    python -m pytest tests/e2e/test_full_stack_contracts.py -v --no-cov
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
import requests
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
ML_URL = os.getenv("SAPI_E2E_ML_URL", "http://127.0.0.1:58000").rstrip("/")
BACKEND_URL = os.getenv("SAPI_E2E_BACKEND_URL", "http://127.0.0.1:58080").rstrip("/")
FORECAST_TIME = os.getenv("SAPI_E2E_FORECAST_TIME", "2026-09-01T00:00:00Z")
EXPECTED_CELL_COUNT = 50
ARTIFACT_DIR = Path(
    os.getenv(
        "SAPI_E2E_CONTRACT_ARTIFACT_DIR",
        str(REPO_ROOT / "artifacts" / "oc-e2e-20261024" / "e2e"),
    )
)


def _git(*args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(REPO_ROOT), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    return completed.stdout.strip() if completed.returncode == 0 else ""


def _provenance() -> dict[str, Any]:
    status = _git("status", "--porcelain")
    return {
        "harness_path": "tests/e2e/test_full_stack_contracts.py",
        "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "harness_git_blob": _git(
            "hash-object", "tests/e2e/test_full_stack_contracts.py"
        ),
        "repo_head_at_capture": _git("rev-parse", "HEAD"),
        "repo_head_subject": _git("log", "-1", "--format=%s"),
        "app_trees": {
            "services": _git("rev-parse", "HEAD:services"),
            "app": _git("rev-parse", "HEAD:app"),
            "contracts": _git("rev-parse", "HEAD:contracts"),
        },
        "worktree_dirty_count": len(status.splitlines()) if status else 0,
    }


def _enabled() -> bool:
    return os.getenv("SAPI_E2E_FULL_STACK", "").strip() == "1"


pytestmark = pytest.mark.skipif(
    not _enabled(),
    reason=(
        "Contratos E2E deshabilitados: requieren stack Compose levantado. "
        "Definir SAPI_E2E_FULL_STACK=1."
    ),
)


def _contracts() -> tuple[dict[str, Any], dict[str, Any]]:
    ml = yaml.safe_load(
        (REPO_ROOT / "contracts" / "openapi" / "ml-service.v0.yaml").read_text(
            encoding="utf-8"
        )
    )
    backend = yaml.safe_load(
        (REPO_ROOT / "contracts" / "openapi" / "backend.v0.yaml").read_text(
            encoding="utf-8"
        )
    )
    return ml, backend


def _validate(
    instance: Any, schema: dict[str, Any], components: dict[str, Any]
) -> None:
    jsonschema = pytest.importorskip("jsonschema")
    combined = dict(schema)
    combined.setdefault("components", components)
    jsonschema.validate(instance=instance, schema=combined)


def _emit(results: dict[str, Any]) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "run_label": "R2-evidence-remediation",
        "ml_url": ML_URL,
        "backend_url": BACKEND_URL,
        "forecast_time": FORECAST_TIME,
        "results": results,
        "provenance": _provenance(),
        "coverage": {
            "ml_response_200_schema": "verificado (llamada directa real)",
            "ml_response_422_schema": "verificado (llamada directa real)",
            "backend_response_200_schema": "verificado (llamada directa real)",
            "backend_response_422_schema": "verificado (llamada directa real)",
            "ml_health_schema": "verificado",
            "backend_health_schema": "verificado",
            "backend_to_ml_wire_request": "no observado (sin proxy/tap)",
            "streamlit_to_backend_wire_request": "no observado (sin proxy/tap)",
            "per_hop_contract_validation": "PARCIAL",
        },
    }
    (ARTIFACT_DIR / "contracts-r2.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def test_full_stack_contracts_by_service() -> None:
    ml_contract, backend_contract = _contracts()
    ml_components = ml_contract["components"]
    ml_schemas = ml_components["schemas"]
    results: dict[str, Any] = {}

    # ---- FastAPI: health ----
    response = requests.get(f"{ML_URL}/health", timeout=30)
    assert response.status_code == 200, response.text
    health = response.json()
    _validate(health, ml_schemas["MlHealth"], ml_components)
    results["ml_health"] = {"status": response.status_code, "body": health}

    # ---- FastAPI: /predict valido ----
    response = requests.post(
        f"{ML_URL}/predict", json={"forecast_time": FORECAST_TIME}, timeout=120
    )
    assert response.status_code == 200, response.text
    ranking = response.json()
    _validate(ranking, ml_schemas["RankingResult"], ml_components)
    assert ranking["score_semantics"] == "relative_rank"
    assert ranking["scientific_model_validation"] is False
    assert ranking["model_version"] == "prototype_model_d_v1"
    assert len(ranking["cells"]) == EXPECTED_CELL_COUNT
    results["ml_predict_200"] = {
        "status": response.status_code,
        "cells": len(ranking["cells"]),
        "schema_version": ranking["schema_version"],
        "inputs_fingerprint": ranking["inputs_fingerprint"],
    }

    # ---- FastAPI: /predict invalido (campo no admitido) ----
    response = requests.post(
        f"{ML_URL}/predict",
        json={"forecast_time": FORECAST_TIME, "features": [1, 2, 3]},
        timeout=30,
    )
    assert response.status_code == 422, response.text
    error = response.json()
    _validate(error, ml_schemas["Error"], ml_components)
    assert error["status"] == "error"
    assert error["error_type"] == "invalid_request"
    results["ml_predict_422"] = {"status": response.status_code, "body": error}

    # ---- Spring Boot: health ----
    response = requests.get(f"{BACKEND_URL}/health", timeout=30)
    assert response.status_code == 200, response.text
    backend_health = response.json()
    _validate(
        backend_health,
        backend_contract["components"]["schemas"]["BackendHealth"],
        backend_contract["components"],
    )
    results["backend_health"] = {
        "status": response.status_code,
        "body": backend_health,
    }

    # ---- Spring Boot: ranking valido ----
    response = requests.get(f"{BACKEND_URL}/api/v1/ranking", timeout=120)
    assert response.status_code == 200, response.text
    backend_ranking = response.json()
    _validate(backend_ranking, ml_schemas["RankingResult"], ml_components)
    assert len(backend_ranking["cells"]) == EXPECTED_CELL_COUNT
    results["backend_ranking_200"] = {
        "status": response.status_code,
        "cells": len(backend_ranking["cells"]),
        "inputs_fingerprint": backend_ranking["inputs_fingerprint"],
    }

    # ---- Spring Boot: forecast_time invalido ----
    response = requests.get(
        f"{BACKEND_URL}/api/v1/ranking",
        params={"forecast_time": "not-a-date"},
        timeout=30,
    )
    assert response.status_code == 422, response.text
    backend_error = response.json()
    _validate(backend_error, ml_schemas["Error"], ml_components)
    assert backend_error["status"] == "error"
    assert backend_error["error_type"] == "invalid_request"
    results["backend_ranking_422"] = {
        "status": response.status_code,
        "body": backend_error,
    }

    # La misma evaluacion debe devolver el mismo fingerprint en ambos saltos.
    assert (
        backend_ranking["inputs_fingerprint"] == ranking["inputs_fingerprint"]
    ), "FastAPI y backend devolvieron fingerprints distintos para la misma T"

    _emit(results)

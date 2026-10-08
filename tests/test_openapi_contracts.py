"""Tests de los contratos OpenAPI v0 congelados (SAPI-56, Quality Gate W0.8).

Validan `contracts/openapi/*.v0.yaml` como documentos OpenAPI 3.0.3 y los
comparan con lo que el servicio ML realmente expone, para que una deriva entre
el YAML, FastAPI y (luego) Spring Boot falle en pytest antes de evolucionar el
contrato a v0.2.

La comparación con el spec generado por FastAPI es normalizada, no literal:
FastAPI emite OpenAPI 3.1 (`anyOf` con `null`, `const`) y el YAML es 3.0.3
(`nullable`, `enum`). Se comparan rutas, métodos, códigos de respuesta,
nombres de propiedades, campos requeridos y valores permitidos.

Criterios cubiertos: SAPI-56.CA1-CA4, SAPI-55.CA2. Reglas: RN-01, RN-02,
RN-03, RN-08.
"""

from __future__ import annotations

import copy
import re
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from openapi_schema_validator import OAS30Validator
from openapi_spec_validator import validate as validate_spec
from openapi_spec_validator.validation.exceptions import OpenAPIValidationError

import services.ml_api.main as ml_api

CONTRACTS = Path(__file__).resolve().parent.parent / "contracts" / "openapi"
ML_SPEC_PATH = CONTRACTS / "ml-service.v0.yaml"
BACKEND_SPEC_PATH = CONTRACTS / "backend.v0.yaml"
CELL_IDS = [f"VP-{i:03d}" for i in range(1, 51)]

# Nombre del schema en el YAML -> nombre en el spec generado por FastAPI.
GENERATED_SCHEMA_NAMES = {
    "PredictRequest": "PredictRequest",
    "RankingResult": "RankingResult",
    "CellRanking": "CellRanking",
    "MlHealth": "MlHealth",
    "Error": "ErrorBody",
}

client = TestClient(ml_api.app)


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def ml_spec() -> dict:
    return _load(ML_SPEC_PATH)


@pytest.fixture(scope="module")
def backend_spec() -> dict:
    return _load(BACKEND_SPEC_PATH)


@pytest.fixture
def reproducible(monkeypatch):
    monkeypatch.setenv("SAPI_REPRODUCIBILITY_MODE", "1")


def _inline_refs(node, spec: dict):
    """Resuelve los `$ref` internos (`#/components/...`) de un schema."""
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/"):
            target = spec
            for part in ref[2:].split("/"):
                target = target[part]
            return _inline_refs(copy.deepcopy(target), spec)
        return {key: _inline_refs(value, spec) for key, value in node.items()}
    if isinstance(node, list):
        return [_inline_refs(item, spec) for item in node]
    return node


def _validator(spec: dict, schema_name: str) -> OAS30Validator:
    schema = _inline_refs(spec["components"]["schemas"][schema_name], spec)
    return OAS30Validator(schema)


def _allowed_values(prop: dict):
    """Valores permitidos de una propiedad, en OpenAPI 3.0 o 3.1."""
    if "enum" in prop:
        return sorted(prop["enum"], key=repr)
    if "const" in prop:
        return [prop["const"]]
    for option in prop.get("anyOf", []):
        values = _allowed_values(option)
        if values is not None:
            return values
    return None


def _schema_shape(schema: dict) -> dict:
    properties = schema.get("properties", {})
    return {
        "properties": sorted(properties),
        "required": sorted(schema.get("required", [])),
        "allowed": {
            name: _allowed_values(prop)
            for name, prop in properties.items()
            if _allowed_values(prop) is not None
        },
    }


def _contract_drift(frozen: dict, generated: dict) -> list[str]:
    drift = []
    for path, operations in frozen["paths"].items():
        generated_ops = generated["paths"].get(path)
        if generated_ops is None:
            drift.append(f"ruta ausente: {path}")
            continue
        for method, operation in operations.items():
            if method not in generated_ops:
                drift.append(f"método ausente: {method.upper()} {path}")
                continue
            missing = set(operation["responses"]) - set(
                generated_ops[method]["responses"]
            )
            if missing:
                drift.append(
                    f"códigos ausentes en {method.upper()} {path}: {sorted(missing)}"
                )
    for frozen_name, generated_name in GENERATED_SCHEMA_NAMES.items():
        expected = _schema_shape(frozen["components"]["schemas"][frozen_name])
        actual = _schema_shape(generated["components"]["schemas"][generated_name])
        for key in ("properties", "required"):
            if expected[key] != actual[key]:
                drift.append(
                    f"{frozen_name}.{key}: YAML={expected[key]} FastAPI={actual[key]}"
                )
        for name, values in expected["allowed"].items():
            implemented = actual["allowed"].get(name)
            if implemented != values:
                drift.append(
                    f"{frozen_name}.{name} valores: YAML={values} FastAPI={implemented}"
                )
    return drift


def _property_names(node) -> set[str]:
    names = set()
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "properties" and isinstance(value, dict):
                names.update(value)
            names |= _property_names(value)
    elif isinstance(node, list):
        for item in node:
            names |= _property_names(item)
    return names


def _documented_error_types(ml_spec: dict) -> set[str]:
    description = ml_spec["components"]["schemas"]["Error"]["properties"]["error_type"][
        "description"
    ]
    return set(re.findall(r"`([a-z_]+)` \(\d{3}", description))


def _example_error_types(node) -> set[str]:
    found = set()
    if isinstance(node, dict):
        if node.get("status") == "error" and isinstance(node.get("error_type"), str):
            found.add(node["error_type"])
        for value in node.values():
            found |= _example_error_types(value)
    elif isinstance(node, list):
        for item in node:
            found |= _example_error_types(item)
    return found


# --- Validez de los documentos ------------------------------------------------


@pytest.mark.parametrize(
    "path", [ML_SPEC_PATH, BACKEND_SPEC_PATH], ids=lambda p: p.name
)
def test_contracts_are_valid_openapi_303(path):
    """SAPI-56.CA1, SAPI-56.CA5: cada contrato es OpenAPI 3.0.3 válido."""
    spec = _load(path)
    assert spec["openapi"] == "3.0.3"
    validate_spec(spec, base_uri=path.as_uri())


def test_backend_cross_file_refs_resolve(ml_spec, backend_spec):
    """SAPI-56.CA2: el backend reutiliza los schemas del servicio ML."""
    refs = re.findall(
        r"'?\./ml-service\.v0\.yaml#/([^'\s]+)", BACKEND_SPEC_PATH.read_text()
    )
    assert refs, "backend.v0.yaml debería referenciar ml-service.v0.yaml"
    for ref in refs:
        target = ml_spec
        for part in ref.split("/"):
            assert part in target, f"$ref sin destino: {ref}"
            target = target[part]
    assert backend_spec["paths"]["/api/v1/ranking"]["get"]["responses"].keys() >= {
        "200",
        "422",
        "500",
        "502",
        "503",
        "504",
    }


def test_spec_validator_rejects_a_broken_contract(tmp_path):
    """Control negativo: el validador detecta un contrato roto."""
    broken = _load(ML_SPEC_PATH)
    del broken["paths"]["/predict"]["post"]["responses"]
    path = tmp_path / "ml-service.broken.yaml"
    path.write_text(yaml.safe_dump(broken), encoding="utf-8")
    with pytest.raises(OpenAPIValidationError):
        validate_spec(_load(path), base_uri=path.as_uri())


# --- Reglas de negocio expresadas en el contrato -------------------------------


def test_synthetic_example_satisfies_ranking_rules(ml_spec):
    """SAPI-56.CA2, RN-02, RN-03: el ejemplo del contrato cumple sus invariantes."""
    example = ml_spec["components"]["examples"]["RankingResultSynthetic"]["value"]
    _validator(ml_spec, "RankingResult").validate(example)
    cells = example["cells"]
    assert [c["cell_id"] for c in sorted(cells, key=lambda c: c["cell_id"])] == CELL_IDS
    assert [c["rank"] for c in cells] == list(range(1, 51))
    scores = [c["score"] for c in cells]
    assert scores == sorted(scores, reverse=True)
    for c in cells:
        assert c["display_rank"] == 1 + sum(s > c["score"] for s in scores)
        assert c["tie_group_size"] == scores.count(c["score"])


def test_no_contract_property_is_named_as_a_probability(ml_spec, backend_spec):
    """SAPI-56.CA4, RN-01: ningún campo del contrato se llama probabilidad."""
    names = _property_names(ml_spec) | _property_names(backend_spec)
    assert not [n for n in names if "probab" in n.lower()]


def test_ranking_semantics_are_pinned_in_the_contract(ml_spec):
    """RN-01: el contrato fija score relativo y ausencia de validación científica."""
    props = ml_spec["components"]["schemas"]["RankingResult"]["properties"]
    assert props["score_semantics"]["enum"] == ["relative_rank"]
    assert props["scientific_model_validation"]["enum"] == [False]
    assert (
        ml_spec["components"]["schemas"]["PredictRequest"]["additionalProperties"]
        is False
    )


def test_example_error_types_are_documented(ml_spec, backend_spec):
    """SAPI-56.CA3: todo error_type usado en ejemplos o por el servicio está documentado."""
    documented = _documented_error_types(ml_spec)
    assert {"invalid_request", "prototype_unavailable", "internal_error"} <= documented
    used = _example_error_types(ml_spec) | _example_error_types(backend_spec)
    assert used <= documented, used - documented
    assert set(ml_api.MESSAGES) <= documented


# --- Implementación frente al contrato ------------------------------------------


def test_fastapi_spec_matches_frozen_contract(ml_spec):
    """SAPI-55.CA2: rutas, códigos, campos y valores coinciden con el YAML."""
    assert _contract_drift(ml_spec, ml_api.app.openapi()) == []


def test_drift_detector_catches_a_removed_required_field(ml_spec):
    """Control negativo: quitar un campo requerido se reporta como deriva."""
    generated = copy.deepcopy(ml_api.app.openapi())
    generated["components"]["schemas"]["RankingResult"]["required"].remove(
        "inputs_fingerprint"
    )
    assert any(
        "RankingResult.required" in d for d in _contract_drift(ml_spec, generated)
    )


def test_real_model_response_validates_against_contract(ml_spec, reproducible):
    """SAPI-55.CA2, SAPI-56.CA2: una respuesta real del Modelo D cumple RankingResult."""
    response = client.post("/predict", json={})
    assert response.status_code == 200
    _validator(ml_spec, "RankingResult").validate(response.json())


@pytest.mark.parametrize(
    "body,status",
    [({"features": [1, 2, 3]}, 422), ({"forecast_time": "2026-09-02T00:00:00Z"}, 503)],
    ids=["campo-no-admitido", "forecast-futuro"],
)
def test_real_error_responses_validate_against_contract(
    ml_spec, reproducible, body, status
):
    """SAPI-56.CA3, RN-05, RN-08: los errores reales cumplen el schema Error."""
    response = client.post("/predict", json=body)
    assert response.status_code == status
    _validator(ml_spec, "Error").validate(response.json())

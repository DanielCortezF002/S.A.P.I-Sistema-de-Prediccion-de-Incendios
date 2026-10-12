"""Complementary component/AppTest checks retained from Antigravity.

Requires explicit SAPI66_RUN_COMPONENT_TESTS=1 and an existing test stack.
These checks are NOT final browser E2E acceptance; run scripts/e2e_slice.py
for the isolated real-browser, full-response timing and exact HTTP/SQL proof.
"""

from __future__ import annotations

from unittest.mock import patch
import copy
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import jsonschema
import pytest
import yaml

# Retained component/AppTest coverage from Antigravity, not browser E2E proof.
# External stack tests must never run accidentally in the offline unit suite.
pytestmark = pytest.mark.skipif(
    os.environ.get("SAPI66_RUN_COMPONENT_TESTS") != "1",
    reason="Explicit existing test-stack opt-in; final E2E is scripts/e2e_slice.py",
)


@pytest.fixture(autouse=True)
def restore_environment():
    with patch.dict(os.environ):
        yield


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CONTRACTS_DIR = REPO_ROOT / "contracts" / "openapi"
ML_CONTRACT_PATH = CONTRACTS_DIR / "ml-service.v0.yaml"
BACKEND_CONTRACT_PATH = CONTRACTS_DIR / "backend.v0.yaml"
LATEST_RANKING_SQL = REPO_ROOT / "db" / "queries" / "latest_ranking.sql"
APP_PATH = REPO_ROOT / "app" / "app.py"

BACKEND_BASE_URL = os.environ.get("SAPI_BACKEND_BASE_URL", "http://127.0.0.1:18080")
ML_BASE_URL = os.environ.get("SAPI_ML_BASE_URL", "http://127.0.0.1:18000")
WEB_BASE_URL = os.environ.get("SAPI_WEB_BASE_URL", "http://127.0.0.1:18501")
COMPOSE_PROJECT = os.environ.get("SAPI_COMPOSE_PROJECT", "sapi66-e2e")
DB_SERVICE = os.environ.get("SAPI_DB_SERVICE", "db-v2")
DB_USER = os.environ.get("SAPI_DB_USER", "sapi")
DB_NAME = os.environ.get("SAPI_DB_NAME", "sapi_v2")

EXPECTED_CELL_COUNT = 50
EXPECTED_MODEL_VERSION = "prototype_model_d_v1"
EXPECTED_FINGERPRINT = (
    "09482d6b3a8b4ab210c32cdddaec352c8eca8be25bbf76592799c1702096c5a3"
)


# --- Helper functions: Schema Resolution & HTTP -------------------------------


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _inline_schema_refs(node: Any, root: dict) -> Any:
    """Resuelve referencias internas ($ref: '#/components/...') en esquemas."""
    if isinstance(node, dict):
        if "$ref" in node:
            ref = node["$ref"]
            if ref.startswith("#/"):
                target = root
                for part in ref[2:].split("/"):
                    target = target[part]
                return _inline_schema_refs(copy.deepcopy(target), root)
        return {k: _inline_schema_refs(v, root) for k, v in node.items()}
    if isinstance(node, list):
        return [_inline_schema_refs(x, root) for x in node]
    return node


def _http_request(
    method: str,
    url: str,
    *,
    body: dict | None = None,
    timeout: float = 30.0,
) -> tuple[int, dict[str, str], bytes, float]:
    """Realiza una petición HTTP y mide el tiempo exacto en segundos."""
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    started = time.monotonic()
    try:
        with opener.open(req, timeout=timeout) as resp:
            payload = resp.read()
            elapsed = time.monotonic() - started
            return resp.status, dict(resp.headers), payload, elapsed
    except urllib.error.HTTPError as err:
        payload = err.read()
        elapsed = time.monotonic() - started
        return err.code, dict(err.headers), payload, elapsed
    except Exception as exc:
        elapsed = time.monotonic() - started
        raise RuntimeError(f"Error HTTP hacia {url}: {exc}") from exc


def _exec_docker_psql(sql: str) -> str:
    """Ejecuta una consulta SQL dentro del contenedor db-v2."""
    cmd = [
        "docker",
        "compose",
        "--project-name",
        COMPOSE_PROJECT,
        "exec",
        "-T",
        DB_SERVICE,
        "psql",
        "-U",
        DB_USER,
        "-d",
        DB_NAME,
        "-At",
        "-F",
        "|",
    ]
    res = subprocess.run(
        cmd,
        input=sql,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=REPO_ROOT,
        timeout=30,
    )
    if res.returncode != 0:
        raise RuntimeError(f"psql fallo ({res.returncode}): {res.stderr}")
    return res.stdout.strip()


# --- Test Cases ---------------------------------------------------------------


@pytest.mark.e2e
def test_sapi66_ca1_full_vertical_slice_chain() -> None:
    """SAPI-66.CA1: Vertical slice completo Streamlit -> Spring Boot -> FastAPI -> PostGIS.

    Verifica que:
    1. Spring Boot responde 200 en GET /api/v1/ranking.
    2. Devuelve 50 celdas con scores relativos estrictamente no crecientes.
    3. Trae la identidad fija esperada: modelo, fingerprint, score_semantics.
    4. AppTest de Streamlit renderiza la respuesta real del backend sin errores.
    5. web-v2 publica HTTP 200 en su puerto expuesto.
    """
    # 1. Spring Boot GET /api/v1/ranking
    status, _, body_bytes, elapsed = _http_request(
        "GET", f"{BACKEND_BASE_URL}/api/v1/ranking"
    )
    assert status == 200, f"Expected 200 from backend ranking, got {status}"
    ranking = json.loads(body_bytes.decode("utf-8"))

    # Invariantes de ranking
    assert ranking["model_version"] == EXPECTED_MODEL_VERSION
    assert ranking["inputs_fingerprint"] == EXPECTED_FINGERPRINT
    assert ranking["score_semantics"] == "relative_rank"
    assert ranking["scientific_model_validation"] is False
    assert len(ranking["cells"]) == EXPECTED_CELL_COUNT

    cells = ranking["cells"]
    assert cells[0]["cell_id"] == "VP-001"
    assert [c["rank"] for c in cells] == list(range(1, EXPECTED_CELL_COUNT + 1))

    scores = [c["score"] for c in cells]
    assert all(a >= b for a, b in zip(scores, scores[1:])), "Scores must be descending"

    # 2. Streamlit UI (AppTest) consumiendo el backend real
    os.environ["SAPI_BACKEND_BASE_URL"] = BACKEND_BASE_URL
    os.environ["SAPI_BACKEND_CONNECT_TIMEOUT"] = "3"
    os.environ["SAPI_BACKEND_READ_TIMEOUT"] = "15"
    os.environ.pop("SAPI_UI_LEGACY_MODES", None)

    from streamlit.testing.v1 import AppTest
    from app.components.ranking_backend_view import refresh_ranking_cache

    refresh_ranking_cache()
    at = AppTest.from_file(str(APP_PATH), default_timeout=60)
    at.run()

    assert not at.exception, f"Streamlit lanzo excepcion: {at.exception}"
    assert not at.error, f"Streamlit mostro errores en UI: {[e.value for e in at.error]}"

    # Elementos renderizados en UI
    markdown_text = " ".join(m.value for m in at.markdown)
    assert "PROTOTIPO EXPLORATORIO" in markdown_text
    assert "BACKEND REST" in markdown_text
    assert "7 celdas empatadas" in markdown_text or "7 celdas" in markdown_text
    assert EXPECTED_FINGERPRINT in markdown_text

    cell_selectboxes = [s for s in at.selectbox if s.label == "Celda"]
    assert len(cell_selectboxes) == 1
    assert len(cell_selectboxes[0].options) == EXPECTED_CELL_COUNT
    assert cell_selectboxes[0].options[0] == "VP-001"

    # 3. web-v2 contenedor HTTP
    web_status, _, web_body, _ = _http_request("GET", f"{WEB_BASE_URL}/")
    assert web_status == 200
    assert b"Streamlit" in web_body or b"streamlit" in web_body


@pytest.mark.e2e
def test_sapi66_ca2_contract_validation_and_error_paths() -> None:
    """SAPI-66.CA2: Errores y contratos OpenAPI verificados en cada salto.

    Verifica:
    1. Contrato OpenAPI Spring Boot: respuesta 200 cumple el esquema RankingResult.
    2. Contrato OpenAPI FastAPI: respuesta 200 de POST /predict cumple RankingResult.
    3. Error en Spring Boot: forecast_time invalido genera HTTP 422 con ErrorBody.
    4. Error en FastAPI: body con campos extra genera HTTP 422 con ErrorBody.
    5. Manejo de error en UI: backend caido muestra st.error visible sin fallback legacy.
    """
    ml_spec = _load_yaml(ML_CONTRACT_PATH)
    ranking_schema = _inline_schema_refs(
        ml_spec["components"]["schemas"]["RankingResult"], ml_spec
    )
    error_schema = _inline_schema_refs(
        ml_spec["components"]["schemas"]["Error"], ml_spec
    )

    # 1. Validacion de contrato Spring Boot GET /api/v1/ranking
    status, _, body_bytes, _ = _http_request(
        "GET", f"{BACKEND_BASE_URL}/api/v1/ranking"
    )
    assert status == 200
    spring_payload = json.loads(body_bytes.decode("utf-8"))
    jsonschema.validate(instance=spring_payload, schema=ranking_schema)

    # 2. Validacion de contrato FastAPI POST /predict
    status_ml, _, ml_bytes, _ = _http_request(
        "POST", f"{ML_BASE_URL}/predict", body={}
    )
    assert status_ml == 200
    ml_payload = json.loads(ml_bytes.decode("utf-8"))
    jsonschema.validate(instance=ml_payload, schema=ranking_schema)

    # 3. Error path Spring Boot: forecast_time invalido -> 422
    err_status, _, err_bytes, _ = _http_request(
        "GET", f"{BACKEND_BASE_URL}/api/v1/ranking?forecast_time=not-a-timestamp"
    )
    assert err_status == 422
    err_payload = json.loads(err_bytes.decode("utf-8"))
    jsonschema.validate(instance=err_payload, schema=error_schema)
    assert err_payload["status"] == "error"
    assert err_payload["error_type"] == "invalid_request"

    # 4. Error path FastAPI: payload desconocido -> 422
    err_ml_status, _, err_ml_bytes, _ = _http_request(
        "POST", f"{ML_BASE_URL}/predict", body={"unexpected_field": 123}
    )
    assert err_ml_status == 422
    err_ml_payload = json.loads(err_ml_bytes.decode("utf-8"))
    jsonschema.validate(instance=err_ml_payload, schema=error_schema)
    assert err_ml_payload["status"] == "error"
    assert err_ml_payload["error_type"] == "invalid_request"

    # 5. Manejo de error en UI con backend inalcanzable
    from streamlit.testing.v1 import AppTest
    from app.components.ranking_backend_view import refresh_ranking_cache

    os.environ["SAPI_BACKEND_BASE_URL"] = "http://127.0.0.1:19999"  # Puerto muerto
    os.environ["SAPI_BACKEND_CONNECT_TIMEOUT"] = "1"
    os.environ["SAPI_BACKEND_READ_TIMEOUT"] = "1"
    refresh_ranking_cache()

    at_err = AppTest.from_file(str(APP_PATH), default_timeout=10)
    at_err.run()

    assert at_err.error, "La UI debe renderizar st.error ante backend inalcanzable"
    err_msg = at_err.error[0].value
    assert "No se pudo obtener el ranking del backend" in err_msg
    ui_text = " ".join(m.value for m in at_err.markdown)
    assert "MODO HISTÓRICO" not in ui_text
    assert "Modo sintético" not in ui_text


@pytest.mark.e2e
def test_sapi66_ca3_postgis_persistence_and_spatial_integrity() -> None:
    """SAPI-66.CA3: Persistencia en PostgreSQL/PostGIS, latest_ranking.sql e integridad espacial.

    Verifica:
    1. latest_ranking.sql devuelve exactamente 50 filas ordenadas por rank 1..50.
    2. Las filas pertenecen a la ejecucion auditada y coinciden con la respuesta REST.
    3. Idempotencia: una llamada repetida no duplica ejecuciones ni predicciones.
    4. Integridad PostGIS: todas las celdas en celdas_geom tienen ST_IsValid=TRUE y SRID=4326.
    """
    # Ejecutar latest_ranking.sql en db-v2
    sql_content = LATEST_RANKING_SQL.read_text(encoding="utf-8")
    raw_output = _exec_docker_psql(sql_content)
    rows = [line.split("|") for line in raw_output.splitlines() if line.strip()]

    assert len(rows) == EXPECTED_CELL_COUNT, (
        f"Se esperaban {EXPECTED_CELL_COUNT} filas en latest_ranking.sql, se obtuvieron {len(rows)}"
    )

    # Columnas esperadas de latest_ranking.sql:
    # 0 ejecucion_id, 1 forecast_time, 2 model_version, 3 inputs_fingerprint,
    # 4 schema_version, 5 score_semantics, 6 scientific_model_validation,
    # 7 horizon_hours, 8 created_at, 9 cell_id, 10 score, 11 rank, 12 tie_group, 13 tie_count
    for i, row in enumerate(rows, start=1):
        assert len(row) == 14, f"Fila {i} no tiene 14 columnas: {row}"
        assert row[2] == EXPECTED_MODEL_VERSION
        assert row[3] == EXPECTED_FINGERPRINT
        assert row[5] == "relative_rank"
        assert row[6] == "f"
        assert int(row[11]) == i, f"Rank esperado {i}, obtenido {row[11]}"

    # Verificar coincidencia de cell_id con respuesta de Spring Boot
    _, _, body_bytes, _ = _http_request("GET", f"{BACKEND_BASE_URL}/api/v1/ranking")
    ranking = json.loads(body_bytes.decode("utf-8"))
    expected_cell_order = [c["cell_id"] for c in ranking["cells"]]
    actual_cell_order = [row[9] for row in rows]
    assert actual_cell_order == expected_cell_order

    # Idempotencia: conteo de ejecuciones y predicciones
    exec_count_before = int(
        _exec_docker_psql("SELECT count(*) FROM ejecuciones;").strip()
    )
    pred_count_before = int(
        _exec_docker_psql("SELECT count(*) FROM predicciones_celda;").strip()
    )

    # Nueva llamada a ranking (mismos insumos)
    _http_request("GET", f"{BACKEND_BASE_URL}/api/v1/ranking")

    exec_count_after = int(
        _exec_docker_psql("SELECT count(*) FROM ejecuciones;").strip()
    )
    pred_count_after = int(
        _exec_docker_psql("SELECT count(*) FROM predicciones_celda;").strip()
    )

    assert exec_count_after == exec_count_before, "No debe duplicar ejecuciones"
    assert pred_count_after == pred_count_before, "No debe duplicar predicciones"

    # Integridad espacial PostGIS: celdas_geom unidas con predicciones_celda
    geom_check_sql = """
    SELECT
        count(*) AS total,
        count(*) FILTER (WHERE ST_IsValid(geom)) AS valids,
        count(*) FILTER (WHERE ST_SRID(geom) = 4326) AS srid4326,
        count(*) FILTER (WHERE ST_GeometryType(geom) = 'ST_Polygon') AS polygons
    FROM celdas_geom cg
    JOIN predicciones_celda pc ON cg.cell_id = pc.cell_id
    WHERE pc.ejecucion_id = (SELECT id FROM ejecuciones ORDER BY created_at DESC, id DESC LIMIT 1);
    """
    geom_res = _exec_docker_psql(geom_check_sql)
    total, valids, srid4326, polygons = [
        int(x) for x in geom_res.strip().split("|")
    ]
    assert total == EXPECTED_CELL_COUNT
    assert valids == EXPECTED_CELL_COUNT, "Todas las geometrias deben ser validas"
    assert srid4326 == EXPECTED_CELL_COUNT, "SRID debe ser 4326 (WGS 84)"
    assert polygons == EXPECTED_CELL_COUNT, (
        "El tipo de geometria debe ser ST_Polygon"
    )


@pytest.mark.e2e
def test_sapi66_ca4_response_timings_recorded() -> None:
    """SAPI-66.CA4: Tiempo total de respuesta documentado (frío y caliente).

    Registra los tiempos por salto:
    - FastAPI POST /predict
    - Spring Boot GET /api/v1/ranking (con persistencia JDBC)
    - Streamlit UI renderizado (AppTest)
    - web-v2 HTTP GET /
    """
    timings: list[dict[str, Any]] = []

    # 1. FastAPI (frío y caliente)
    _, _, _, ml_t1 = _http_request("POST", f"{ML_BASE_URL}/predict", body={})
    _, _, _, ml_t2 = _http_request("POST", f"{ML_BASE_URL}/predict", body={})
    timings.append({"hop": "ml-api", "phase": "sample_1", "seconds": round(ml_t1, 4)})
    timings.append({"hop": "ml-api", "phase": "sample_2", "seconds": round(ml_t2, 4)})

    # 2. Spring Boot (frío y caliente)
    _, _, _, sb_t1 = _http_request("GET", f"{BACKEND_BASE_URL}/api/v1/ranking")
    _, _, _, sb_t2 = _http_request("GET", f"{BACKEND_BASE_URL}/api/v1/ranking")
    timings.append({"hop": "backend", "phase": "sample_1", "seconds": round(sb_t1, 4)})
    timings.append({"hop": "backend", "phase": "sample_2", "seconds": round(sb_t2, 4)})

    # 3. web-v2 HTTP
    _, _, _, web_t1 = _http_request("GET", f"{WEB_BASE_URL}/")
    _, _, _, web_t2 = _http_request("GET", f"{WEB_BASE_URL}/")
    timings.append({"hop": "web-v2-http", "phase": "sample_1", "seconds": round(web_t1, 4)})
    timings.append({"hop": "web-v2-http", "phase": "sample_2", "seconds": round(web_t2, 4)})

    # Verificacion basica de validez de tiempos (positivos y razonables)
    for entry in timings:
        assert entry["seconds"] > 0, f"Tiempo no positivo: {entry}"

    # Exportar datos temporales para scripts/e2e_slice.py si se requiere
    test_sapi66_ca4_response_timings_recorded.last_timings = timings  # type: ignore[attr-defined]


@pytest.mark.e2e
def test_sapi66_ca5_compose_services_health_and_ports() -> None:
    """SAPI-66.CA5: Verificacion de servicios Docker Compose y puertos aislados."""
    cmd = [
        "docker",
        "compose",
        "--project-name",
        COMPOSE_PROJECT,
        "ps",
        "--format",
        "json",
    ]
    res = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=REPO_ROOT,
        timeout=15,
    )
    assert res.returncode == 0
    raw = res.stdout.strip()
    if raw.startswith("["):
        rows = json.loads(raw)
    else:
        rows = [json.loads(line) for line in raw.splitlines() if line.strip()]

    by_service = {r["Service"]: r for r in rows}
    assert "backend" in by_service
    assert "ml-api" in by_service
    assert "db-v2" in by_service
    assert "web-v2" in by_service

    for s in ("backend", "ml-api", "db-v2"):
        health = by_service[s].get("Health", "")
        state = by_service[s].get("State", "")
        assert (
            health == "healthy" and state == "running"
        ), f"Servicio {s} no esta saludable: {by_service[s]}"

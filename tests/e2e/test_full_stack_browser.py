"""E2E fisico del stack completo S.A.P.I. v2 (OCC-OC-A2, 2026-10-24).

Diferencia deliberada con ``tests/e2e/test_vertical_slice.py``: ese modulo usa
``FastAPI TestClient`` en proceso y no demuestra el stack desplegado. Este
modulo exige un stack Compose ya levantado y recorre el camino real:

    navegador (Edge) -> Streamlit -> Spring Boot -> FastAPI/Modelo D
                     -> PostgreSQL/PostGIS -> ranking -> interfaz de 50 celdas

Se omite por defecto. Para ejecutarlo:

    $env:SAPI_E2E_FULL_STACK = "1"
    python -m pytest tests/e2e/test_full_stack_browser.py -v --no-cov

Variables (todas opcionales salvo la primera):

- ``SAPI_E2E_FULL_STACK=1``        habilita el modulo.
- ``SAPI_E2E_WEB_URL``             default ``http://127.0.0.1:58501``.
- ``SAPI_E2E_BACKEND_URL``         default ``http://127.0.0.1:58080``.
- ``SAPI_E2E_ML_URL``              default ``http://127.0.0.1:58000``.
- ``SAPI_E2E_DB_CONTAINER``        default ``sapi-oc-e2e-20261024-db-v2-1``.
- ``SAPI_E2E_DB_NAME``/``USER``    default ``sapi_v2`` / ``sapi``.
- ``SAPI_E2E_BROWSER_CHANNEL``     default ``msedge`` (navegador real instalado).
- ``SAPI_E2E_ARTIFACT_DIR``        default ``artifacts/oc-e2e-20261024/e2e``.

No inventa valores: si un salto no responde, el test falla con el codigo y el
cuerpo observados. No modifica el ranking ni la base.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_CELL_COUNT = 50
EXPECTED_CELL_IDS = [f"VP-{i:03d}" for i in range(1, 51)]


def _enabled() -> bool:
    return os.getenv("SAPI_E2E_FULL_STACK", "").strip() == "1"


pytestmark = pytest.mark.skipif(
    not _enabled(),
    reason=(
        "E2E fisico deshabilitado: requiere stack Compose levantado. "
        "Definir SAPI_E2E_FULL_STACK=1."
    ),
)

WEB_URL = os.getenv("SAPI_E2E_WEB_URL", "http://127.0.0.1:58501").rstrip("/")
BACKEND_URL = os.getenv("SAPI_E2E_BACKEND_URL", "http://127.0.0.1:58080").rstrip("/")
ML_URL = os.getenv("SAPI_E2E_ML_URL", "http://127.0.0.1:58000").rstrip("/")
DB_CONTAINER = os.getenv("SAPI_E2E_DB_CONTAINER", "sapi-oc-e2e-20261024-db-v2-1")
DB_NAME = os.getenv("SAPI_E2E_DB_NAME", "sapi_v2")
DB_USER = os.getenv("SAPI_E2E_DB_USER", "sapi")
BROWSER_CHANNEL = os.getenv("SAPI_E2E_BROWSER_CHANNEL", "msedge")
ARTIFACT_DIR = Path(
    os.getenv("SAPI_E2E_ARTIFACT_DIR", str(REPO_ROOT / "artifacts" / "oc-e2e-20261024" / "e2e"))
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _artifact_dir() -> Path:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    return ARTIFACT_DIR


def _write_evidence(name: str, payload: Any) -> Path:
    path = _artifact_dir() / name
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    return path


def _http_json(path_or_url: str, *, timeout: float = 120.0) -> dict[str, Any]:
    """Peticion GET real; devuelve status, latencia, cabeceras y JSON/bytes."""
    url = path_or_url if path_or_url.startswith("http") else f"{BACKEND_URL}{path_or_url}"
    started = time.perf_counter()
    response = requests.get(url, timeout=timeout, headers={"Accept": "application/json"})
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    body = response.content
    try:
        decoded: Any = json.loads(body.decode("utf-8")) if body else None
    except (UnicodeDecodeError, ValueError):
        decoded = None
    return {
        "url": url,
        "status": response.status_code,
        "elapsed_ms": elapsed_ms,
        "headers": {k: v for k, v in response.headers.items()},
        "body_sha256": _sha256_bytes(body),
        "body_bytes": len(body),
        "json": decoded,
        "at": _utc_now(),
    }


def _psql(sql: str) -> list[list[str]]:
    """Ejecuta SQL en el contenedor de base aislado, via socket local trust.

    No usa credenciales en la linea de comandos ni imprime el secreto: el
    acceso es el socket Unix interno del contenedor de prueba.
    """
    completed = subprocess.run(
        [
            "docker",
            "exec",
            DB_CONTAINER,
            "psql",
            "-U",
            DB_USER,
            "-d",
            DB_NAME,
            "-tA",
            "-F",
            "\t",
            "-c",
            sql,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    if completed.returncode != 0:
        pytest.fail(f"psql fallo ({completed.returncode}): {completed.stderr.strip()}")
    return [line.split("\t") for line in completed.stdout.splitlines() if line.strip()]


@pytest.fixture(scope="module")
def ranking() -> dict[str, Any]:
    """Ranking real del backend, capturado una vez y persistido como evidencia."""
    result = _http_json("/api/v1/ranking")
    _write_evidence(
        "ranking-http.json",
        {
            "captured_at": result["at"],
            "url": result["url"],
            "status": result["status"],
            "elapsed_ms": result["elapsed_ms"],
            "request_id": result["headers"].get("X-Request-Id"),
            "body_sha256": result["body_sha256"],
            "body_bytes": result["body_bytes"],
            "payload": result["json"],
        },
    )
    assert result["status"] == 200, f"ranking HTTP {result['status']}: {result['json']!r}"
    assert isinstance(result["json"], dict), "el ranking no es un objeto JSON"
    return result["json"]


def test_full_stack_services_healthy() -> None:
    """Los cuatro servicios del stack aislado responden por HTTP real."""
    ml = _http_json(f"{ML_URL}/health", timeout=15)
    backend = _http_json(f"{BACKEND_URL}/health", timeout=15)
    web = _http_json(f"{WEB_URL}/_stcore/health", timeout=30)
    evidence = {
        "captured_at": _utc_now(),
        "ml": {k: ml[k] for k in ("url", "status", "elapsed_ms", "json")},
        "backend": {k: backend[k] for k in ("url", "status", "elapsed_ms", "json")},
        "web": {k: web[k] for k in ("url", "status", "elapsed_ms")},
    }
    _write_evidence("health-hops.json", evidence)

    assert ml["status"] == 200, ml
    assert ml["json"] == {"status": "ok", "model_version": "prototype_model_d_v1"}
    assert backend["status"] == 200, backend
    assert backend["json"] == {"status": "UP"}
    assert web["status"] == 200, web


def test_full_stack_ranking_contract(ranking: dict[str, Any]) -> None:
    """El backend reexpone el contrato sapi-ranking-v0 sin alterar el ranking."""
    assert ranking["schema_version"] == "sapi-ranking-v0"
    assert ranking["model_version"] == "prototype_model_d_v1"
    assert ranking["score_semantics"] == "relative_rank"
    assert ranking["scientific_model_validation"] is False
    assert ranking["horizon_hours"] == 6
    assert len(ranking["inputs_fingerprint"]) == 64
    assert ranking["disclaimer"]

    cells = ranking["cells"]
    assert len(cells) == EXPECTED_CELL_COUNT
    assert sorted(c["cell_id"] for c in cells) == EXPECTED_CELL_IDS
    assert [c["rank"] for c in cells] == list(range(1, EXPECTED_CELL_COUNT + 1))
    scores = [c["score"] for c in cells]
    assert all(0.0 <= s <= 1.0 for s in scores)
    assert all(scores[i] >= scores[i + 1] for i in range(len(scores) - 1))

    # Coherencia de empates del contrato (se verifica, no se recalcula).
    first_rank: dict[float, int] = {}
    count: dict[float, int] = {}
    for cell in cells:
        first_rank.setdefault(cell["score"], cell["rank"])
        count[cell["score"]] = count.get(cell["score"], 0) + 1
    for cell in cells:
        assert cell["display_rank"] == first_rank[cell["score"]]
        assert cell["tie_group_size"] == count[cell["score"]]


def test_full_stack_postgis_persistence_matches_response(ranking: dict[str, Any]) -> None:
    """V001-V004 aplicadas y 50 filas persistidas identicas a la respuesta HTTP."""
    flyway = _psql(
        "SELECT version || '|' || description || '|' || CASE WHEN success THEN 'success' "
        "ELSE 'FAIL' END FROM flyway_schema_history ORDER BY installed_rank"
    )
    versions = [row[0].split("|")[0] for row in flyway]
    assert versions == ["001", "002", "003", "004"], flyway
    assert all(row[0].endswith("|success") for row in flyway), flyway

    geom = _psql(
        "SELECT count(*), count(*) FILTER (WHERE ST_SRID(geom) = 4326 AND ST_IsValid(geom)), "
        "string_agg(DISTINCT GeometryType(geom), ',') FROM celdas_geom"
    )
    assert geom == [["50", "50", "POLYGON"]], geom

    execution = _psql(
        "SELECT id, to_char(forecast_time AT TIME ZONE 'UTC', 'YYYY-MM-DD\"T\"HH24:MI:SS\"Z\"'), "
        "model_version, inputs_fingerprint, score_semantics, "
        "CASE WHEN scientific_model_validation THEN 'true' ELSE 'false' END, firms_origin "
        "FROM ejecuciones ORDER BY created_at DESC, id DESC LIMIT 1"
    )
    assert len(execution) == 1, execution
    exec_id, forecast_time, model_version, fingerprint, semantics, sci, origin = execution[0]
    assert model_version == ranking["model_version"]
    assert fingerprint == ranking["inputs_fingerprint"]
    assert semantics == ranking["score_semantics"]
    assert sci == "false"
    assert origin == ranking["firms_origin"]
    assert forecast_time == ranking["forecast_time"]

    rows = _psql(
        f"SELECT cell_id, score, rank, display_rank, tie_group_size "
        f"FROM predicciones_celda WHERE ejecucion_id = {int(exec_id)} ORDER BY rank"
    )
    assert len(rows) == EXPECTED_CELL_COUNT, len(rows)
    for row, cell in zip(rows, ranking["cells"]):
        cell_id, score, rank, display_rank, tie_group_size = row
        assert cell_id == cell["cell_id"]
        assert float(score) == cell["score"]
        assert int(rank) == cell["rank"]
        assert int(display_rank) == cell["display_rank"]
        assert int(tie_group_size) == cell["tie_group_size"]

    # Una sola ejecucion para la clave natural (T, modelo, fingerprint).
    natural_key = _psql(
        f"SELECT count(*) FROM ejecuciones WHERE forecast_time = '{forecast_time}' "
        f"AND model_version = '{model_version}' AND inputs_fingerprint = '{fingerprint}'"
    )
    assert natural_key == [["1"]], natural_key

    _write_evidence(
        "postgis-verification.json",
        {
            "captured_at": _utc_now(),
            "container": DB_CONTAINER,
            "flyway": flyway,
            "celdas_geom": geom,
            "ejecucion": {
                "id": exec_id,
                "forecast_time": forecast_time,
                "model_version": model_version,
                "inputs_fingerprint": fingerprint,
                "score_semantics": semantics,
                "scientific_model_validation": sci,
                "firms_origin": origin,
            },
            "predicciones": len(rows),
            "comparison": "1:1 exacta (cell_id, score, rank, display_rank, tie_group_size)",
        },
    )


def test_full_stack_repeat_is_idempotent(ranking: dict[str, Any]) -> None:
    """Repetir la solicitud no duplica ejecuciones ni cambia las celdas."""
    before = _psql("SELECT count(*) FROM ejecuciones")[0][0]
    second = _http_json("/api/v1/ranking")
    assert second["status"] == 200, second["json"]
    after = _psql("SELECT count(*) FROM ejecuciones")[0][0]

    assert second["json"]["cells"] == ranking["cells"]
    assert second["json"]["inputs_fingerprint"] == ranking["inputs_fingerprint"]
    assert before == after, f"ejecuciones {before} -> {after}"

    _write_evidence(
        "idempotency.json",
        {
            "captured_at": _utc_now(),
            "first_body_sha256": _sha256_bytes(
                json.dumps(ranking, sort_keys=True, ensure_ascii=False).encode("utf-8")
            ),
            "second_body_sha256": _sha256_bytes(
                json.dumps(second["json"], sort_keys=True, ensure_ascii=False).encode("utf-8")
            ),
            "cells_equal": second["json"]["cells"] == ranking["cells"],
            "ejecuciones_before": before,
            "ejecuciones_after": after,
            "age_hours_first": ranking.get("age_hours"),
            "age_hours_second": second["json"].get("age_hours"),
            "note": (
                "age_hours se calcula contra el reloj de evaluacion; puede variar "
                "entre repeticiones aunque la clave natural persistida sea la misma."
            ),
        },
    )


def test_full_stack_payload_matches_frozen_openapi_schema(ranking: dict[str, Any]) -> None:
    """El payload real valida contra ``contracts/openapi/ml-service.v0.yaml``."""
    yaml = pytest.importorskip("yaml")
    jsonschema = pytest.importorskip("jsonschema")

    ml_contract = yaml.safe_load(
        (REPO_ROOT / "contracts" / "openapi" / "ml-service.v0.yaml").read_text(
            encoding="utf-8"
        )
    )
    backend_contract = yaml.safe_load(
        (REPO_ROOT / "contracts" / "openapi" / "backend.v0.yaml").read_text(
            encoding="utf-8"
        )
    )
    schemas = ml_contract["components"]["schemas"]
    ranking_schema = schemas["RankingResult"]

    # Invariantes congelados del contrato, no del test.
    assert ranking_schema["properties"]["score_semantics"]["enum"] == ["relative_rank"]
    assert ranking_schema["properties"]["scientific_model_validation"]["enum"] == [False]
    assert ranking_schema["properties"]["cells"]["minItems"] == EXPECTED_CELL_COUNT
    assert ranking_schema["properties"]["cells"]["maxItems"] == EXPECTED_CELL_COUNT

    # El backend reexpone el mismo RankingResult del servicio ML.
    backend_200 = backend_contract["paths"]["/api/v1/ranking"]["get"]["responses"]["200"]
    backend_ref = json.dumps(backend_200)
    assert "ml-service.v0.yaml#/components/schemas/RankingResult" in backend_ref

    # Validacion formal: los $ref relativos al documento se resuelven incluyendo
    # el arbol components en la raiz del schema.
    combined = dict(ranking_schema)
    combined["components"] = ml_contract["components"]
    jsonschema.validate(instance=ranking, schema=combined)

    _write_evidence(
        "openapi-conformance.json",
        {
            "captured_at": _utc_now(),
            "contracts": [
                "contracts/openapi/ml-service.v0.yaml#/components/schemas/RankingResult",
                "contracts/openapi/backend.v0.yaml#/paths/~1api~1v1~1ranking/get/responses/200",
            ],
            "result": "valid",
            "cells": len(ranking["cells"]),
        },
    )


def test_full_stack_browser_consumes_backend(ranking: dict[str, Any]) -> None:
    """Un navegador real ve en Streamlit el ranking del backend y 50 celdas."""
    pytest.importorskip("playwright.sync_api", reason="playwright no instalado")
    from playwright.sync_api import sync_playwright

    screenshot = _artifact_dir() / "streamlit-ranking.png"

    with sync_playwright() as p:
        browser = p.chromium.launch(channel=BROWSER_CHANNEL, headless=True)
        page = browser.new_page(viewport={"width": 1600, "height": 1000})
        console_errors: list[str] = []
        page.on(
            "console",
            lambda msg: console_errors.append(msg.text) if msg.type == "error" else None,
        )
        started = time.perf_counter()
        page.goto(WEB_URL, wait_until="domcontentloaded", timeout=90_000)
        page.get_by_text("PROTOTIPO EXPLORATORIO").first.wait_for(timeout=90_000)
        page.wait_for_timeout(5_000)  # mapa Leaflet + tabla
        load_ms = round((time.perf_counter() - started) * 1000, 2)

        body = page.locator("body").inner_text()
        assert "S.A.P.I." in body
        assert "BACKEND REST" in body
        assert "50" in body and "CELDAS EVALUADAS" in body
        assert "GRUPO PRIORITARIO" in body
        assert "#1" in body
        assert "Probabilidad" not in body  # nunca se presenta como probabilidad
        assert "ranking relativo" in body.lower()

        # La huella mostrada en la UI debe ser la misma que emitio el backend.
        page.get_by_text("Información técnica y fuentes").click()
        page.wait_for_timeout(1_500)
        body_tech = page.locator("body").inner_text()
        assert ranking["inputs_fingerprint"] in body_tech
        assert "relative_rank" in body_tech
        assert "scientific_model_validation" in body_tech.lower() or "validación científica" in body_tech.lower()

        # Expander del ranking completo: el filtro declara las 50 celdas al abrirse.
        page.get_by_text("Ver ranking completo").click()
        page.wait_for_timeout(1_500)
        assert page.get_by_text("Criterio de ordenación").is_visible()
        selectboxes = page.locator('[data-testid="stSelectbox"]')
        assert selectboxes.count() >= 2  # Celda + filtro por grupo
        group_filter = selectboxes.nth(1)
        group_filter.scroll_into_view_if_needed()
        group_filter.wait_for(state="visible", timeout=10_000)
        group_filter.click()
        # El desplegable puede tardar en montarse tras un arranque en frio.
        page.get_by_text("Todos los grupos (50 celdas)").wait_for(
            state="visible", timeout=10_000
        )
        assert page.get_by_text("Todos los grupos (50 celdas)").is_visible()
        page.keyboard.press("Escape")

        # Representacion territorial: exactamente 50 rectangulos Leaflet.
        leaflet_counts = {
            frame.url: frame.locator(".leaflet-interactive").count()
            for frame in page.frames
            if "streamlit_folium" in frame.url
        }
        assert leaflet_counts, "no se encontro el iframe de Folium"
        assert list(leaflet_counts.values()) == [EXPECTED_CELL_COUNT], leaflet_counts

        page.screenshot(path=str(screenshot), full_page=True)
        screenshot_sha = _sha256_bytes(screenshot.read_bytes())
        browser.close()

    _write_evidence(
        "browser-verification.json",
        {
            "captured_at": _utc_now(),
            "browser": f"chromium channel={BROWSER_CHANNEL} headless",
            "viewport": "1600x1000",
            "url": WEB_URL,
            "load_ms": load_ms,
            "screenshot": str(screenshot.relative_to(REPO_ROOT)),
            "screenshot_sha256": screenshot_sha,
            "leaflet_rectangles": leaflet_counts,
            "fingerprint_seen_in_ui": ranking["inputs_fingerprint"],
            "console_errors": console_errors,
        },
    )


def test_full_stack_ml_logs_received_request() -> None:
    """El servicio FastAPI registro la peticion que origino el backend.

    Evidencia de que el salto Spring -> FastAPI ocurrio de verdad y no fue un
    cache del navegador ni un dato embebido en Streamlit.
    """
    completed = subprocess.run(
        [
            "docker",
            "logs",
            "--since",
            "30m",
            "sapi-oc-e2e-20261024-ml-api-1",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    assert completed.returncode == 0, completed.stderr
    combined = (completed.stdout or "") + (completed.stderr or "")
    assert "/predict" in combined or "predict" in combined.lower(), combined[-2000:]

    path = _artifact_dir() / "ml-service-log-tail.txt"
    path.write_text(
        f"captured_at={_utc_now()}\ncontainer=sapi-oc-e2e-20261024-ml-api-1\n"
        + "\n".join(combined.splitlines()[-40:])
        + "\n",
        encoding="utf-8",
    )
    _write_evidence(
        "ml-service-log.json",
        {
            "captured_at": _utc_now(),
            "container": "sapi-oc-e2e-20261024-ml-api-1",
            "tail_file": str(path.relative_to(REPO_ROOT)),
            "tail_sha256": _sha256_bytes(path.read_bytes()),
        },
    )

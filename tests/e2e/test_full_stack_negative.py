"""Matriz negativa E2E del stack completo (OCC-OC-A2, 2026-10-24).

Opt-in: modifica el estado de los contenedores del proyecto aislado
(``docker stop`` / ``docker start``), por lo que exige ``SAPI_E2E_FAULT_INJECTION=1``.
Cada prueba restaura el servicio en ``finally`` y verifica recuperacion.

No toca volumenes, no borra datos y no modifica el proyecto original: solo
detiene y arranca contenedores del proyecto Compose de prueba.

    $env:SAPI_E2E_FULL_STACK = "1"
    $env:SAPI_E2E_FAULT_INJECTION = "1"
    python -m pytest tests/e2e/test_full_stack_negative.py -v --no-cov
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
BACKEND_URL = os.getenv("SAPI_E2E_BACKEND_URL", "http://127.0.0.1:58080").rstrip("/")
ML_URL = os.getenv("SAPI_E2E_ML_URL", "http://127.0.0.1:58000").rstrip("/")
WEB_URL = os.getenv("SAPI_E2E_WEB_URL", "http://127.0.0.1:58501").rstrip("/")
DB_CONTAINER = os.getenv("SAPI_E2E_DB_CONTAINER", "sapi-oc-e2e-20261024-db-v2-1")
ML_CONTAINER = os.getenv("SAPI_E2E_ML_CONTAINER", "sapi-oc-e2e-20261024-ml-api-1")
BACKEND_CONTAINER = os.getenv("SAPI_E2E_BACKEND_CONTAINER", "sapi-oc-e2e-20261024-backend-1")
WEB_CONTAINER = os.getenv("SAPI_E2E_WEB_CONTAINER", "sapi-oc-e2e-20261024-web-v2-1")
DB_NAME = os.getenv("SAPI_E2E_DB_NAME", "sapi_v2")
DB_USER = os.getenv("SAPI_E2E_DB_USER", "sapi")
BROWSER_CHANNEL = os.getenv("SAPI_E2E_BROWSER_CHANNEL", "msedge")
ARTIFACT_DIR = Path(
    os.getenv("SAPI_E2E_ARTIFACT_DIR", str(REPO_ROOT / "artifacts" / "oc-e2e-20261024" / "negative"))
)


def _enabled() -> bool:
    return (
        os.getenv("SAPI_E2E_FULL_STACK", "").strip() == "1"
        and os.getenv("SAPI_E2E_FAULT_INJECTION", "").strip() == "1"
    )


pytestmark = pytest.mark.skipif(
    not _enabled(),
    reason=(
        "Matriz negativa deshabilitada: detiene contenedores. "
        "Definir SAPI_E2E_FULL_STACK=1 y SAPI_E2E_FAULT_INJECTION=1."
    ),
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _docker(*args: str, timeout: int = 180) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def _psql(sql: str) -> list[list[str]]:
    completed = subprocess.run(
        [
            "docker", "exec", DB_CONTAINER, "psql",
            "-U", DB_USER, "-d", DB_NAME, "-tA", "-F", "\t", "-c", sql,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    if completed.returncode != 0:
        pytest.fail(f"psql fallo: {completed.stderr.strip()}")
    return [line.split("\t") for line in completed.stdout.splitlines() if line.strip()]


def _counts() -> str:
    return _psql("SELECT count(*)||'/'||(SELECT count(*) FROM predicciones_celda) FROM ejecuciones")[0][0]


def _wait_http(url: str, timeout_s: int = 180) -> int | None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                return response.status_code
        except requests.RequestException:
            pass
        time.sleep(2)
    return None


def _call_backend(timeout: float = 120.0) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        response = requests.get(f"{BACKEND_URL}/api/v1/ranking", timeout=timeout)
        elapsed = round((time.perf_counter() - started) * 1000, 2)
        return {
            "status": response.status_code,
            "elapsed_ms": elapsed,
            "json": response.json() if response.content else None,
        }
    except requests.RequestException as exc:
        return {
            "status": None,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
            "error": type(exc).__name__,
        }


def _write(name: str, payload: Any) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    (ARTIFACT_DIR / name).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )


def test_invalid_forecast_time_is_rejected_without_writes() -> None:
    before = _counts()
    response = requests.get(
        f"{BACKEND_URL}/api/v1/ranking",
        params={"forecast_time": "not-a-date"},
        timeout=60,
    )
    assert response.status_code == 422
    assert response.json()["error_type"] == "invalid_request"
    assert _counts() == before
    _write(
        "invalid-forecast-time.json",
        {"captured_at": _now(), "http": response.status_code, "body": response.json(),
         "counts_before": before, "counts_after": _counts()},
    )


def test_invalid_payload_is_rejected_by_ml_service() -> None:
    cases = [
        {"forecast_time": "invalid-timestamp"},
        {"features": [1, 2, 3]},
        {"forecast_time": 123},
    ]
    results = []
    for payload in cases:
        response = requests.post(f"{ML_URL}/predict", json=payload, timeout=60)
        assert response.status_code == 422, (payload, response.text)
        assert response.json()["error_type"] == "invalid_request"
        results.append({"payload": payload, "http": response.status_code,
                        "body": response.json()})
    _write("invalid-payload-ml.json", {"captured_at": _now(), "cases": results})


def test_ml_unavailable_returns_controlled_503_and_writes_nothing() -> None:
    before = _counts()
    try:
        assert _docker("stop", ML_CONTAINER).returncode == 0
        time.sleep(2)
        down = _call_backend()
        assert down["status"] == 503, down
        assert down["json"]["error_type"] == "upstream_unavailable", down
        assert _counts() == before
    finally:
        assert _docker("start", ML_CONTAINER).returncode == 0
        assert _wait_http(f"{ML_URL}/health") == 200

    recovered = None
    deadline = time.time() + 120
    while time.time() < deadline:
        recovered = _call_backend()
        if recovered["status"] == 200:
            break
        time.sleep(3)
    assert recovered and recovered["status"] == 200, recovered

    _write(
        "ml-unavailable.json",
        {
            "captured_at": _now(),
            "down": down,
            "counts_before": before,
            "counts_after": _counts(),
            "recovered_status": recovered["status"],
            "recovered_ms": recovered["elapsed_ms"],
            "note": (
                "Tras reiniciar ml-api el backend puede devolver 503 durante unos "
                "segundos (conexion/DNS en cache); se reintenta hasta 120 s."
            ),
        },
    )


def test_database_unavailable_fails_closed_and_writes_nothing() -> None:
    before = _counts()
    try:
        assert _docker("stop", DB_CONTAINER).returncode == 0
        time.sleep(2)
        down = _call_backend(timeout=120)
        assert down["status"] == 500, down
        assert down["json"]["error_type"] == "internal_error", down
    finally:
        assert _docker("start", DB_CONTAINER).returncode == 0
        deadline = time.time() + 180
        health = None
        while time.time() < deadline:
            health = _docker("inspect", "--format", "{{.State.Health.Status}}", DB_CONTAINER)
            if health.stdout.strip() == "healthy":
                break
            time.sleep(2)
        assert health and health.stdout.strip() == "healthy"

    assert _counts() == before, "la caida de la base no debe dejar escrituras parciales"
    recovered = None
    deadline = time.time() + 120
    while time.time() < deadline:
        recovered = _call_backend()
        if recovered["status"] == 200:
            break
        time.sleep(3)
    assert recovered and recovered["status"] == 200, recovered

    _write(
        "database-unavailable.json",
        {
            "captured_at": _now(),
            "down": down,
            "counts_before": before,
            "counts_after": _counts(),
            "recovered_status": recovered["status"],
            "recovered_ms": recovered["elapsed_ms"],
        },
    )


def test_backend_unavailable_ui_shows_controlled_error_and_recovers() -> None:
    pytest.importorskip("playwright.sync_api", reason="playwright no instalado")
    from playwright.sync_api import sync_playwright

    screenshot_down = ARTIFACT_DIR / "ui-backend-down.png"
    screenshot_up = ARTIFACT_DIR / "ui-backend-up.png"
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    try:
        assert _docker("stop", BACKEND_CONTAINER).returncode == 0
        assert _docker("restart", WEB_CONTAINER).returncode == 0
        assert _wait_http(f"{WEB_URL}/_stcore/health", 180) == 200

        with sync_playwright() as p:
            browser = p.chromium.launch(channel=BROWSER_CHANNEL, headless=True)
            page = browser.new_page(viewport={"width": 1600, "height": 1000})
            page.goto(WEB_URL, wait_until="domcontentloaded", timeout=90_000)
            page.get_by_text("No se pudo obtener el ranking del backend").first.wait_for(
                timeout=90_000
            )
            page.wait_for_timeout(2_000)
            body_down = page.locator("body").inner_text()
            assert "No se pudo conectar con el backend" in body_down
            assert "Traceback" not in body_down
            assert "backend:8080" not in body_down
            page.screenshot(path=str(screenshot_down), full_page=True)
            browser.close()
    finally:
        assert _docker("start", BACKEND_CONTAINER).returncode == 0
        assert _wait_http(f"{BACKEND_URL}/health") == 200

    with sync_playwright() as p:
        browser = p.chromium.launch(channel=BROWSER_CHANNEL, headless=True)
        page = browser.new_page(viewport={"width": 1600, "height": 1000})
        page.goto(WEB_URL, wait_until="domcontentloaded", timeout=90_000)
        page.get_by_text("PROTOTIPO EXPLORATORIO").first.wait_for(timeout=90_000)
        page.wait_for_timeout(3_000)
        body_up = page.locator("body").inner_text()
        assert "50" in body_up and "CELDAS EVALUADAS" in body_up
        page.screenshot(path=str(screenshot_up), full_page=True)
        browser.close()

    _write(
        "backend-unavailable-ui.json",
        {
            "captured_at": _now(),
            "down": {
                "screenshot": str(screenshot_down.relative_to(REPO_ROOT)),
                "screenshot_sha256": hashlib.sha256(screenshot_down.read_bytes()).hexdigest(),
                "controlled_error_seen": True,
                "traceback_present": False,
                "host_leaked": False,
            },
            "up": {
                "screenshot": str(screenshot_up.relative_to(REPO_ROOT)),
                "screenshot_sha256": hashlib.sha256(screenshot_up.read_bytes()).hexdigest(),
                "ranking_visible": True,
            },
        },
    )

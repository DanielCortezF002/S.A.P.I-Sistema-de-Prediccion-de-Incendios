"""CA4: tiempos reales de UI fria, actualizacion y rerun cacheado.

Este modulo complementa ``test_full_stack_browser.py`` sin modificarlo. Mide
tres acciones distintas sobre el stack Compose ya levantado:

1. ``cold_ui``: navegador nuevo, primera carga hasta cabecera y mapa Leaflet.
2. ``update``: clic en "Actualizar ranking", que invalida ``st.cache_data`` y
   obliga a Streamlit -> Spring Boot -> FastAPI -> PostGIS.
3. ``cached``: cambio de orden en la tabla, que provoca un rerun de Streamlit
   pero NO vuelve a consultar al backend (cache de 5 min).

El discriminador no es el PNG (la cabecera solo muestra HH:MM): es el conteo
de lineas ``ml_predict request_id=`` en el log del backend y el delta de
predicciones antes/despues de cada accion. Los screenshots y sus SHA-256 se
guardan igual para auditoria visual.

Se omite por defecto. Para ejecutarlo:

    $env:SAPI_E2E_FULL_STACK = "1"
    python -m pytest tests/e2e/test_full_stack_timings.py -v --no-cov

No inventa valores: si una accion no produce el efecto esperado, el test falla
con los conteos y tiempos observados. No modifica el ranking ni la base.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_CELL_COUNT = 50

WEB_URL = os.getenv("SAPI_E2E_WEB_URL", "http://127.0.0.1:58501").rstrip("/")
BACKEND_URL = os.getenv("SAPI_E2E_BACKEND_URL", "http://127.0.0.1:58080").rstrip("/")
ML_URL = os.getenv("SAPI_E2E_ML_URL", "http://127.0.0.1:58000").rstrip("/")
BACKEND_CONTAINER = os.getenv(
    "SAPI_E2E_BACKEND_CONTAINER", "sapi-oc-e2e-20261024-backend-1"
)
BROWSER_CHANNEL = os.getenv("SAPI_E2E_BROWSER_CHANNEL", "msedge")
ARTIFACT_DIR = Path(
    os.getenv(
        "SAPI_E2E_TIMINGS_ARTIFACT_DIR",
        str(REPO_ROOT / "artifacts" / "oc-e2e-20261024" / "timings"),
    )
)


def _enabled() -> bool:
    return os.getenv("SAPI_E2E_FULL_STACK", "").strip() == "1"


pytestmark = pytest.mark.skipif(
    not _enabled(),
    reason=(
        "CA4 deshabilitado: requiere stack Compose levantado. "
        "Definir SAPI_E2E_FULL_STACK=1."
    ),
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _artifact_dir() -> Path:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    return ARTIFACT_DIR


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _backend_log() -> str:
    completed = subprocess.run(
        ["docker", "logs", "--timestamps", BACKEND_CONTAINER],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    assert completed.returncode == 0, completed.stderr
    return (completed.stdout or "") + (completed.stderr or "")


def _predict_lines() -> list[str]:
    return [
        line
        for line in _backend_log().splitlines()
        if "ml_predict request_id=" in line
    ]


def _last_ml_latency_ms() -> int | None:
    lines = _predict_lines()
    if not lines:
        return None
    match = re.search(r"ml_latency_ms=(\d+)", lines[-1])
    return int(match.group(1)) if match else None


def _health() -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, url in (
        ("ml", f"{ML_URL}/health"),
        ("backend", f"{BACKEND_URL}/health"),
        ("web", f"{WEB_URL}/_stcore/health"),
    ):
        started = time.perf_counter()
        response = requests.get(url, timeout=30)
        result[name] = {
            "url": url,
            "status": response.status_code,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
        }
        assert response.status_code == 200, result[name]
    return result


def _fetched_at_text(page: Any) -> str:
    body = page.locator("body").inner_text()
    match = re.search(r"Obtenido del backend:\s*(\d{2}:\d{2} UTC)", body)
    return match.group(1) if match else ""


def _wait_for_leaflet(page: Any, timeout_s: float = 60.0) -> int:
    deadline = time.time() + timeout_s
    rectangles = 0
    while time.time() < deadline:
        for frame in page.frames:
            if "streamlit_folium" in frame.url:
                rectangles = frame.locator(".leaflet-interactive").count()
                if rectangles == EXPECTED_CELL_COUNT:
                    return rectangles
        page.wait_for_timeout(250)
    return rectangles


def _wait_until(predicate: Any, timeout_s: float, page: Any) -> float:
    started = time.perf_counter()
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if predicate():
            return round((time.perf_counter() - started) * 1000, 2)
        page.wait_for_timeout(250)
    return round((time.perf_counter() - started) * 1000, 2)


def _screenshot(page: Any, name: str) -> tuple[str, str]:
    path = _artifact_dir() / name
    page.screenshot(path=str(path), full_page=True)
    return str(path.relative_to(REPO_ROOT)), _sha256_bytes(path.read_bytes())


def test_full_stack_ca4_timings_cold_update_cached() -> None:
    pytest.importorskip("playwright.sync_api", reason="playwright no instalado")
    from playwright.sync_api import sync_playwright

    health = _health()
    actions: list[dict[str, Any]] = []
    console_errors: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(channel=BROWSER_CHANNEL, headless=True)
        page = browser.new_page(viewport={"width": 1600, "height": 1000})
        page.on(
            "console",
            lambda msg: console_errors.append(msg.text) if msg.type == "error" else None,
        )

        # ---- 1. UI fria: navegador nuevo, sin cache del navegador ----
        predict_before = len(_predict_lines())
        started_iso = _utc_now()
        started = time.perf_counter()
        page.goto(WEB_URL, wait_until="domcontentloaded", timeout=90_000)
        page.get_by_text("PROTOTIPO EXPLORATORIO").first.wait_for(timeout=90_000)
        header_ms = round((time.perf_counter() - started) * 1000, 2)
        rectangles = _wait_for_leaflet(page)
        map_ms = round((time.perf_counter() - started) * 1000, 2)
        # Estabilizar CSS/fuentes antes de la captura; no altera la medicion.
        page.wait_for_timeout(5_000)
        screenshot, screenshot_sha = _screenshot(page, "ca4-cold-ui.png")
        predict_after = len(_predict_lines())
        cold_delta = predict_after - predict_before
        navigation_type = page.evaluate(
            "() => performance.getEntriesByType('navigation')[0]?.type || 'unknown'"
        )
        actions.append(
            {
                "action": "cold_ui",
                "started_at_utc": started_iso,
                "elapsed_ms": map_ms,
                "elapsed_to_header_ms": header_ms,
                "elapsed_to_backend_ms": None,
                "navigation_type": navigation_type,
                "ml_predict_delta": cold_delta,
                "ml_latency_ms": _last_ml_latency_ms(),
                "fetched_at_text": _fetched_at_text(page),
                "screenshot": screenshot,
                "screenshot_sha256": screenshot_sha,
                "notes": (
                    f"Navegador nuevo; ml_predict_delta={cold_delta} "
                    f"(cache {'fria' if cold_delta else 'tibia'})."
                ),
            }
        )
        assert rectangles == EXPECTED_CELL_COUNT, (
            f"Leaflet mostro {rectangles} rectangulos, se esperaban "
            f"{EXPECTED_CELL_COUNT}"
        )

        # El sidebar arranca colapsado en este viewport; abrirlo para el boton.
        sidebar_toggle = page.get_by_role(
            "button", name="keyboard_double_arrow_right"
        )
        if sidebar_toggle.count():
            sidebar_toggle.click()
            page.wait_for_timeout(500)

        # ---- 2. Actualizacion: invalida cache y recorre todo el backend ----
        predict_before = len(_predict_lines())
        started_iso = _utc_now()
        started = time.perf_counter()
        page.get_by_role("button", name="Actualizar ranking").click()
        backend_ms = _wait_until(
            lambda: len(_predict_lines()) > predict_before, 90.0, page
        )
        page.locator('[data-testid="stStatusWidget"]').wait_for(
            state="hidden", timeout=30_000
        )
        page.get_by_text("CELDAS EVALUADAS").first.wait_for(timeout=30_000)
        update_ms = round((time.perf_counter() - started) * 1000, 2)
        # Estabilizar CSS/fuentes antes de la captura; ya no altera la medicion.
        page.wait_for_timeout(5_000)
        screenshot, screenshot_sha = _screenshot(page, "ca4-update.png")
        predict_after = len(_predict_lines())
        actions.append(
            {
                "action": "update",
                "started_at_utc": started_iso,
                "elapsed_ms": update_ms,
                "elapsed_to_header_ms": None,
                "elapsed_to_backend_ms": backend_ms,
                "navigation_type": "streamlit-rerun-cache-clear",
                "ml_predict_delta": predict_after - predict_before,
                "ml_latency_ms": _last_ml_latency_ms(),
                "fetched_at_text": _fetched_at_text(page),
                "screenshot": screenshot,
                "screenshot_sha256": screenshot_sha,
                "notes": "Boton Actualizar ranking: st.cache_data.clear() + backend.",
            }
        )
        assert predict_after > predict_before, (
            "Actualizar ranking no produjo ninguna prediccion ML: "
            f"{predict_before} -> {predict_after}"
        )

        # Abrir el ranking completo para poder provocar un rerun cacheado.
        page.get_by_text("Ver ranking completo").click()
        page.wait_for_timeout(1_500)
        page.locator('[data-testid="stDataFrame"]').first.wait_for(
            state="visible", timeout=30_000
        )

        # ---- 3. Rerun cacheado: cambia orden, no consulta al backend ----
        predict_before = len(_predict_lines())
        started_iso = _utc_now()
        started = time.perf_counter()
        page.get_by_text("Identificador de celda", exact=False).first.click()
        page.get_by_text(
            "ascendente por identificador de celda", exact=False
        ).first.wait_for(timeout=30_000)
        page.locator('[data-testid="stStatusWidget"]').wait_for(
            state="hidden", timeout=30_000
        )
        cached_ms = round((time.perf_counter() - started) * 1000, 2)
        # Estabilizar CSS/fuentes antes de la captura; ya no altera la medicion.
        page.wait_for_timeout(5_000)
        screenshot, screenshot_sha = _screenshot(page, "ca4-cached.png")
        predict_after = len(_predict_lines())
        actions.append(
            {
                "action": "cached",
                "started_at_utc": started_iso,
                "elapsed_ms": cached_ms,
                "elapsed_to_header_ms": None,
                "elapsed_to_backend_ms": None,
                "navigation_type": "streamlit-rerun-cache-hit",
                "ml_predict_delta": predict_after - predict_before,
                "ml_latency_ms": None,
                "fetched_at_text": _fetched_at_text(page),
                "screenshot": screenshot,
                "screenshot_sha256": screenshot_sha,
                "notes": "Cambio de orden: rerun de Streamlit con cache vigente.",
            }
        )
        assert predict_after == predict_before, (
            "El rerun cacheado volvio a llamar al backend: "
            f"{predict_before} -> {predict_after}"
        )

        browser.close()

    cold = actions[0]
    update = actions[1]
    cached = actions[2]
    assert cold["elapsed_to_header_ms"] > 0
    assert cold["elapsed_ms"] >= cold["elapsed_to_header_ms"]
    assert update["elapsed_to_backend_ms"] is not None
    assert cached["ml_predict_delta"] == 0

    csv_path = _artifact_dir() / "ca4-timings.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "action",
                "started_at_utc",
                "elapsed_ms",
                "elapsed_to_header_ms",
                "elapsed_to_backend_ms",
                "navigation_type",
                "ml_predict_delta",
                "ml_latency_ms",
                "fetched_at_text",
                "screenshot",
                "screenshot_sha256",
                "notes",
            ],
        )
        writer.writeheader()
        writer.writerows(actions)

    evidence = {
        "captured_at": _utc_now(),
        "url": WEB_URL,
        "browser": f"chromium channel={BROWSER_CHANNEL} headless",
        "viewport": "1600x1000",
        "health": health,
        "actions": actions,
        "console_errors": console_errors,
        "notes": [
            "elapsed_ms de cold_ui incluye cabecera y mapa Leaflet con 50 celdas.",
            "update invalida st.cache_data y debe producir >=1 ml_predict.",
            "cached es un rerun de Streamlit y debe producir 0 ml_predict.",
            "La cabecera solo muestra HH:MM; el discriminador real es ml_predict_delta.",
        ],
    }
    (_artifact_dir() / "ca4-timings.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )

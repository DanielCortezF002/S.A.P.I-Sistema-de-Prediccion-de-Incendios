"""CA4: tiempos reales de UI fria, actualizacion y rerun cacheado.

Este modulo mide tres acciones distintas sobre el stack Compose ya levantado y,
a diferencia de la version R1, **no acepta** un escenario tibio: impone y
verifica las condiciones por si mismo.

1. ``cold_ui``: reinicia solo ``web-v2`` para vaciar ``st.cache_data``, espera
   salud, abre un navegador nuevo y exige >=1 ``ml_predict`` real y >=1
   ``POST /predict 200`` en el servicio ML durante la medicion.
2. ``update``: clic en "Actualizar ranking" (``st.cache_data.clear()``), exige
   una peticion nueva identificada por ``request_id``, con ``ml_responded=true``,
   ``ml_http_status=200`` y el mismo ``inputs_fingerprint``.
3. ``cached``: cambio de orden en la tabla, exige **cero** ``ml_predict`` y
   **cero** ``POST /predict`` nuevos, y confirma que el rerun ocurrio.

Si cualquiera de esas condiciones no se cumple, el test falla. Ademas archiva
los logs crudos con timestamps y un JSON de correlacion por accion.

Se omite por defecto. Para ejecutarlo:

    $env:SAPI_E2E_FULL_STACK = "1"
    python -m pytest tests/e2e/test_full_stack_timings.py -v --no-cov

No inventa valores ni reutiliza mediciones previas: cada corrida reinicia
``web-v2`` y escribe sus propios artefactos. No modifica el ranking ni la base.
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
WEB_CONTAINER = os.getenv("SAPI_E2E_WEB_CONTAINER", "sapi-oc-e2e-20261024-web-v2-1")
BACKEND_CONTAINER = os.getenv(
    "SAPI_E2E_BACKEND_CONTAINER", "sapi-oc-e2e-20261024-backend-1"
)
ML_CONTAINER = os.getenv("SAPI_E2E_ML_CONTAINER", "sapi-oc-e2e-20261024-ml-api-1")
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


def _docker(*args: str, timeout: int = 120) -> str:
    completed = subprocess.run(
        ["docker", *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    assert completed.returncode == 0, (
        f"docker {' '.join(args)} fallo con {completed.returncode}: "
        f"{(completed.stdout or '').strip()}"
    )
    return completed.stdout or ""


def _log_lines(container: str) -> list[str]:
    return [
        line
        for line in _docker("logs", "--timestamps", container).splitlines()
        if line.strip()
    ]


def _predict_lines(lines: list[str]) -> list[str]:
    return [line for line in lines if "ml_predict request_id=" in line]


def _ml_predict_200_lines(lines: list[str]) -> list[str]:
    return [line for line in lines if 'POST /predict HTTP/1.1" 200' in line]


def _parse_predict(line: str) -> dict[str, Any]:
    def group(pattern: str) -> str | None:
        match = re.search(pattern, line)
        return match.group(1) if match else None

    return {
        "timestamp": line.split(" ", 1)[0],
        "request_id": group(r"request_id=([0-9a-fA-F-]+)"),
        "ml_responded": group(r"ml_responded=(\w+)"),
        "ml_http_status": group(r"ml_http_status=(\d+)"),
        "ml_latency_ms": group(r"ml_latency_ms=(\d+)"),
        "outcome": group(r"outcome=(\w+)"),
        "backend_http_status": group(r"backend_http_status=(\d+)"),
        "model_version": group(r"model_version=(\S+)"),
        "forecast_time": group(r"forecast_time=(\S+)"),
        "inputs_fingerprint": group(r"inputs_fingerprint=(\w+)"),
        "ejecucion_id": group(r"ejecucion_id=(\d+)"),
        "raw": line,
    }


def _snapshot() -> dict[str, Any]:
    backend = _log_lines(BACKEND_CONTAINER)
    ml = _log_lines(ML_CONTAINER)
    return {
        "backend": backend,
        "ml": ml,
        "predicts": _predict_lines(backend),
        "ml_200": _ml_predict_200_lines(ml),
    }


def _window(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    new_predicts = after["predicts"][len(before["predicts"]) :]
    new_ml = after["ml_200"][len(before["ml_200"]) :]
    return {
        "new_predicts": [_parse_predict(line) for line in new_predicts],
        "new_ml_200": new_ml,
        "predict_delta": len(new_predicts),
        "ml_predict_delta": len(new_ml),
    }


def _restart_web() -> dict[str, Any]:
    """Reinicia solo web-v2 para garantizar cache de Streamlit vacia."""
    container_id = _docker("inspect", "-f", "{{.Id}}", WEB_CONTAINER).strip()
    started_iso = _utc_now()
    started = time.perf_counter()
    _docker("restart", WEB_CONTAINER, timeout=180)
    deadline = time.time() + 180
    status: int | None = None
    while time.time() < deadline:
        try:
            response = requests.get(f"{WEB_URL}/_stcore/health", timeout=5)
            status = response.status_code
            if status == 200:
                break
        except requests.RequestException:
            status = None
        time.sleep(1.0)
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    assert (
        status == 200
    ), f"{WEB_CONTAINER} no respondio /_stcore/health tras el reinicio: {status}"
    return {
        "method": "docker restart de web-v2 (solo este contenedor)",
        "container": WEB_CONTAINER,
        "container_id": container_id,
        "restarted_at_utc": started_iso,
        "ready_ms": elapsed_ms,
        "health_status": status,
        "assertion": "cache de Streamlit vacia por reinicio del proceso",
    }


def _last_ml_latency_ms(lines: list[str]) -> int | None:
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


def _write_raw_logs(backend: list[str], ml: list[str]) -> tuple[str, str]:
    directory = _artifact_dir()
    backend_path = directory / "ca4-raw-backend.log"
    ml_path = directory / "ca4-raw-ml.log"
    header = f"# captured_at={_utc_now()}"
    backend_path.write_text("\n".join([header, *backend]) + "\n", encoding="utf-8")
    ml_path.write_text("\n".join([header, *ml]) + "\n", encoding="utf-8")
    return (
        str(backend_path.relative_to(REPO_ROOT)),
        str(ml_path.relative_to(REPO_ROOT)),
    )


def test_full_stack_ca4_timings_cold_update_cached() -> None:
    pytest.importorskip("playwright.sync_api", reason="playwright no instalado")
    from playwright.sync_api import sync_playwright

    health_before = _health()
    cache_establishment = _restart_web()
    health_after = _health()

    actions: list[dict[str, Any]] = []
    windows: dict[str, Any] = {}
    console_errors: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(channel=BROWSER_CHANNEL, headless=True)
        page = browser.new_page(viewport={"width": 1600, "height": 1000})
        page.on(
            "console",
            lambda msg: (
                console_errors.append(msg.text) if msg.type == "error" else None
            ),
        )

        # ---- 1. UI fria: web-v2 reiniciado, navegador nuevo ----
        cold_before = _snapshot()
        started_iso = _utc_now()
        started = time.perf_counter()
        page.goto(WEB_URL, wait_until="domcontentloaded", timeout=90_000)
        page.get_by_text("PROTOTIPO EXPLORATORIO").first.wait_for(timeout=90_000)
        header_ms = round((time.perf_counter() - started) * 1000, 2)
        rectangles = _wait_for_leaflet(page)
        map_ms = round((time.perf_counter() - started) * 1000, 2)
        page.wait_for_timeout(5_000)  # estabilizar CSS; posterior a la medicion
        screenshot, screenshot_sha = _screenshot(page, "ca4-cold-ui.png")
        cold_after = _snapshot()
        cold_window = _window(cold_before, cold_after)
        windows["cold_ui"] = {
            "window_started_at_utc": started_iso,
            "window_ended_at_utc": _utc_now(),
            **cold_window,
        }
        cold_ids = [item["request_id"] for item in cold_window["new_predicts"]]
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
                "backend_predict_delta": cold_window["predict_delta"],
                "ml_predict_delta": cold_window["ml_predict_delta"],
                "new_request_ids": cold_ids,
                "ml_latency_ms": (
                    int(cold_window["new_predicts"][-1]["ml_latency_ms"])
                    if cold_window["new_predicts"]
                    and cold_window["new_predicts"][-1]["ml_latency_ms"]
                    else None
                ),
                "fetched_at_text": _fetched_at_text(page),
                "screenshot": screenshot,
                "screenshot_sha256": screenshot_sha,
                "notes": (
                    "web-v2 reiniciado antes de medir; se exige llamada real "
                    "al backend y a FastAPI."
                ),
            }
        )
        assert rectangles == EXPECTED_CELL_COUNT, (
            f"Leaflet mostro {rectangles} rectangulos, se esperaban "
            f"{EXPECTED_CELL_COUNT}"
        )
        assert cold_window["predict_delta"] >= 1, (
            "CA4 cold_ui no produjo ninguna llamada real al backend "
            f"(ml_predict delta={cold_window['predict_delta']}). "
            "La cache de Streamlit no estaba fria pese al reinicio de web-v2."
        )
        assert cold_window["ml_predict_delta"] >= 1, (
            "CA4 cold_ui no produjo ningun POST /predict 200 en el servicio ML "
            f"(delta={cold_window['ml_predict_delta']})."
        )

        # El sidebar arranca colapsado en este viewport; abrirlo para el boton.
        sidebar_toggle = page.get_by_role("button", name="keyboard_double_arrow_right")
        if sidebar_toggle.count():
            sidebar_toggle.click()
            page.wait_for_timeout(500)

        # ---- 2. Actualizacion: invalida cache y recorre todo el backend ----
        update_before = _snapshot()
        started_iso = _utc_now()
        started = time.perf_counter()
        page.get_by_role("button", name="Actualizar ranking").click()
        backend_ms = _wait_until(
            lambda: len(_predict_lines(_log_lines(BACKEND_CONTAINER)))
            > len(update_before["predicts"]),
            120.0,
            page,
        )
        page.locator('[data-testid="stStatusWidget"]').wait_for(
            state="hidden", timeout=30_000
        )
        page.get_by_text("CELDAS EVALUADAS").first.wait_for(timeout=30_000)
        update_ms = round((time.perf_counter() - started) * 1000, 2)
        page.wait_for_timeout(5_000)  # estabilizar CSS; posterior a la medicion
        screenshot, screenshot_sha = _screenshot(page, "ca4-update.png")
        update_after = _snapshot()
        update_window = _window(update_before, update_after)
        windows["update"] = {
            "window_started_at_utc": started_iso,
            "window_ended_at_utc": _utc_now(),
            **update_window,
        }
        update_ids = [item["request_id"] for item in update_window["new_predicts"]]
        actions.append(
            {
                "action": "update",
                "started_at_utc": started_iso,
                "elapsed_ms": update_ms,
                "elapsed_to_header_ms": None,
                "elapsed_to_backend_ms": backend_ms,
                "navigation_type": "streamlit-rerun-cache-clear",
                "backend_predict_delta": update_window["predict_delta"],
                "ml_predict_delta": update_window["ml_predict_delta"],
                "new_request_ids": update_ids,
                "ml_latency_ms": (
                    int(update_window["new_predicts"][-1]["ml_latency_ms"])
                    if update_window["new_predicts"]
                    and update_window["new_predicts"][-1]["ml_latency_ms"]
                    else None
                ),
                "fetched_at_text": _fetched_at_text(page),
                "screenshot": screenshot,
                "screenshot_sha256": screenshot_sha,
                "notes": (
                    "Boton Actualizar ranking: st.cache_data.clear() + backend; "
                    "se exige request_id nuevo y respuesta ML 200."
                ),
            }
        )
        assert update_window["predict_delta"] >= 1, (
            "Actualizar ranking no produjo ninguna prediccion ML: "
            f"delta={update_window['predict_delta']}"
        )
        assert update_window["ml_predict_delta"] >= 1, (
            "Actualizar ranking no produjo ningun POST /predict 200: "
            f"delta={update_window['ml_predict_delta']}"
        )
        for item in update_window["new_predicts"]:
            assert item["ml_responded"] == "true", item
            assert item["ml_http_status"] == "200", item
            assert item["outcome"] == "ok", item
            assert item["request_id"], item
            assert item["request_id"] not in cold_ids, (
                "El request_id de update se repite respecto de cold_ui: "
                f"{item['request_id']}"
            )
        fingerprints = {
            item["inputs_fingerprint"]
            for item in cold_window["new_predicts"] + update_window["new_predicts"]
            if item["inputs_fingerprint"]
        }
        assert (
            len(fingerprints) == 1
        ), f"El fingerprint cambio entre cold y update: {fingerprints}"

        # Abrir el ranking completo para poder provocar un rerun cacheado.
        page.get_by_text("Ver ranking completo").click()
        page.wait_for_timeout(1_500)
        page.locator('[data-testid="stDataFrame"]').first.wait_for(
            state="visible", timeout=30_000
        )

        # ---- 3. Rerun cacheado: cambia orden, no consulta al backend ----
        cached_before = _snapshot()
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
        page.wait_for_timeout(5_000)  # estabilizar CSS; posterior a la medicion
        screenshot, screenshot_sha = _screenshot(page, "ca4-cached.png")
        cached_after = _snapshot()
        cached_window = _window(cached_before, cached_after)
        windows["cached"] = {
            "window_started_at_utc": started_iso,
            "window_ended_at_utc": _utc_now(),
            **cached_window,
        }
        actions.append(
            {
                "action": "cached",
                "started_at_utc": started_iso,
                "elapsed_ms": cached_ms,
                "elapsed_to_header_ms": None,
                "elapsed_to_backend_ms": None,
                "navigation_type": "streamlit-rerun-cache-hit",
                "backend_predict_delta": cached_window["predict_delta"],
                "ml_predict_delta": cached_window["ml_predict_delta"],
                "new_request_ids": [
                    item["request_id"] for item in cached_window["new_predicts"]
                ],
                "ml_latency_ms": None,
                "fetched_at_text": _fetched_at_text(page),
                "screenshot": screenshot,
                "screenshot_sha256": screenshot_sha,
                "notes": (
                    "Cambio de orden: rerun de Streamlit con cache vigente; "
                    "se exige cero inferencia nueva."
                ),
            }
        )
        assert cached_window["predict_delta"] == 0, (
            "El rerun cacheado volvio a llamar al backend: "
            f"delta={cached_window['predict_delta']} "
            f"ids={[i['request_id'] for i in cached_window['new_predicts']]}"
        )
        assert cached_window["ml_predict_delta"] == 0, (
            "El rerun cacheado volvio a llamar a FastAPI: "
            f"delta={cached_window['ml_predict_delta']}"
        )

        final_snapshot = _snapshot()
        browser.close()

    raw_backend, raw_ml = _write_raw_logs(
        final_snapshot["backend"], final_snapshot["ml"]
    )

    cold = actions[0]
    update = actions[1]
    cached = actions[2]
    assert cold["elapsed_to_header_ms"] > 0
    assert cold["elapsed_ms"] >= cold["elapsed_to_header_ms"]
    assert update["elapsed_to_backend_ms"] is not None
    assert cached["backend_predict_delta"] == 0

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
                "backend_predict_delta",
                "ml_predict_delta",
                "new_request_ids",
                "ml_latency_ms",
                "fetched_at_text",
                "screenshot",
                "screenshot_sha256",
                "notes",
            ],
        )
        writer.writeheader()
        writer.writerows(
            {
                **action,
                "new_request_ids": ";".join(action["new_request_ids"]),
            }
            for action in actions
        )

    status = _git("status", "--porcelain")
    provenance = {
        "harness_path": "tests/e2e/test_full_stack_timings.py",
        "harness_sha256": _sha256_bytes(Path(__file__).read_bytes()),
        "harness_git_blob": _git("hash-object", "tests/e2e/test_full_stack_timings.py"),
        "repo_head_at_capture": _git("rev-parse", "HEAD"),
        "repo_head_subject": _git("log", "-1", "--format=%s"),
        "app_code_commit": _git(
            "log", "-1", "--format=%H", "--", "services", "app", "contracts"
        ),
        "app_code_commit_subject": _git(
            "log", "-1", "--format=%s", "--", "services", "app", "contracts"
        ),
        "app_trees": {
            "services": _git("rev-parse", "HEAD:services"),
            "app": _git("rev-parse", "HEAD:app"),
            "contracts": _git("rev-parse", "HEAD:contracts"),
        },
        "worktree_dirty_count": len(status.splitlines()) if status else 0,
        "worktree_dirty_sample": status.splitlines()[:10] if status else [],
    }

    evidence = {
        "captured_at": _utc_now(),
        "run_label": "R2-evidence-remediation",
        "url": WEB_URL,
        "browser": f"chromium channel={BROWSER_CHANNEL} headless",
        "viewport": "1600x1000",
        "health_before": health_before,
        "cache_establishment": cache_establishment,
        "health_after_restart": health_after,
        "actions": actions,
        "console_errors": console_errors,
        "provenance": provenance,
        "raw_logs": {"backend": raw_backend, "ml": raw_ml},
        "gates": {
            "cold_requires_backend_call": True,
            "cold_backend_predicts": cold["backend_predict_delta"],
            "cold_ml_predicts_200": cold["ml_predict_delta"],
            "update_requires_new_request_id": True,
            "update_backend_predicts": update["backend_predict_delta"],
            "update_ml_predicts_200": update["ml_predict_delta"],
            "update_fingerprint_unchanged": True,
            "cached_requires_zero_inference": True,
            "cached_backend_predicts": cached["backend_predict_delta"],
            "cached_ml_predicts_200": cached["ml_predict_delta"],
        },
        "notes": [
            "cold_ui se mide despues de reiniciar solo web-v2; si no hay "
            "llamada real al backend el test falla.",
            "update exige request_id nuevo con ml_responded=true y "
            "ml_http_status=200.",
            "cached exige cero ml_predict y cero POST /predict nuevos.",
            "La cabecera solo muestra HH:MM; el discriminador real es la "
            "correlacion de request_id y los deltas de logs.",
        ],
    }
    (_artifact_dir() / "ca4-timings.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    (_artifact_dir() / "ca4-request-correlation.json").write_text(
        json.dumps(
            {
                "captured_at": evidence["captured_at"],
                "backend_container": BACKEND_CONTAINER,
                "ml_container": ML_CONTAINER,
                "web_container": WEB_CONTAINER,
                "cache_establishment": cache_establishment,
                "actions": windows,
                "raw_logs": evidence["raw_logs"],
                "provenance": provenance,
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )

"""Aceptación headless del Control Center: DEMO, EN VIVO sintético y REPLAY.

Un solo servidor servido por el lanzador (página en la raíz) + un stub del bridge en
127.0.0.1 con la salida real del serializador para un resultado SINTÉTICO. Se salta
si Playwright/Chromium no están disponibles.
"""

from __future__ import annotations

import http.server
import json
import os
import socket
import subprocess
import threading
import time
from pathlib import Path

import pytest
import requests

from app import control_center as launcher
from src.output import accepted_run as ar

REPO = Path(__file__).resolve().parents[1]
WIDTHS = {"desktop": 1440, "laptop": 1366, "tablet": 820}
MODES = {"DEMO": "/?demo=1", "EN VIVO": "/", "REPLAY": "/?replay=1"}


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def app_server(tmp_path_factory):
    sync_api = pytest.importorskip("playwright.sync_api")
    from fastapi.testclient import TestClient

    import tools.n8n_bridge.app as bridge_app
    from src.output.synthetic import synthetic_result

    mp = pytest.MonkeyPatch()
    mp.setattr(bridge_app, "score_current_grid", synthetic_result)
    mp.setattr(bridge_app, "_read_metadata_json", lambda: None)
    body = TestClient(bridge_app.app).get("/score").json()
    mp.undo()
    raw = json.dumps(body).encode()

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, *args):
            pass

    bridge = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=bridge.serve_forever, daemon=True).start()
    bridge_url = f"http://127.0.0.1:{bridge.server_address[1]}/score"

    doc = ar.build_artifact(
        body,
        data_origin=ar.DATA_SYNTHETIC,
        captured_at="2026-09-24T13:05:00+00:00",
        source_url=bridge_url,
    )
    artifact, _ = ar.write_artifact(doc, tmp_path_factory.mktemp("runs"))

    port = _free_port()
    env = {
        **os.environ,
        "SAPI_SCORE_URL": bridge_url,
        launcher.REPLAY_ENV: str(artifact),
    }
    proc = subprocess.Popen(
        launcher.build_command(port),
        cwd=REPO,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            try:
                if requests.get(base + "/_stcore/health", timeout=1).status_code == 200:
                    break
            except requests.RequestException:
                time.sleep(0.5)
        else:
            pytest.skip("el servidor local no arrancó")
        with sync_api.sync_playwright() as p:
            try:
                browser = p.chromium.launch()
            except Exception as exc:  # noqa: BLE001
                pytest.skip(f"Chromium no disponible: {exc}")
            yield base, browser, doc
            browser.close()
    finally:
        proc.terminate()
        proc.wait(timeout=30)
        bridge.shutdown()


@pytest.mark.parametrize("width", sorted(WIDTHS))
@pytest.mark.parametrize("mode", sorted(MODES))
def test_mode_renders_complete_product(app_server, mode, width):
    base, browser, doc = app_server
    page = browser.new_page(viewport={"width": WIDTHS[width], "height": 1000})
    failed, console = [], []
    page.on(
        "response",
        lambda r: failed.append((r.status, r.url)) if r.status >= 400 else None,
    )
    page.on("console", lambda m: console.append(m.text) if m.type == "error" else None)
    page.goto(base + MODES[mode])
    page.wait_for_selector(".ops-top li", timeout=60000)
    page.wait_for_timeout(1000)
    info = page.evaluate(
        """() => ({
        chips: [...document.querySelectorAll('.ops-modeline .ops-chip')].map(e => e.innerText),
        map: document.querySelectorAll('.ops-map rect').length,
        rows: document.querySelectorAll('.ops-table tbody tr').length,
        top: [...document.querySelectorAll('.ops-top li')].map(li => li.dataset.rank),
        text: document.body.innerText,
        overflow: document.documentElement.scrollWidth > window.innerWidth,
        artifact: document.querySelector('[data-artifact]')?.dataset.artifact || null})"""
    )
    page.close()
    assert f"MODO: {mode}" in info["chips"]
    assert not any(
        c.startswith("MODO:") and c != f"MODO: {mode}" for c in info["chips"]
    )
    assert info["map"] == 50 and info["rows"] == 50
    assert info["top"] == ["1", "2", "3", "4", "5"]
    assert "No corresponde a una probabilidad calibrada" in info["text"]
    assert not info["overflow"]
    assert failed == [] and console == []
    if mode == "REPLAY":
        assert (
            info["artifact"] == doc["artifact_fingerprint"]
            and "SYNTHETIC" in info["text"]
        )
    if mode == "DEMO":
        assert "DATOS DEMOSTRATIVOS" in info["text"]
    if mode == "EN VIVO":
        assert "DATOS DEMOSTRATIVOS" not in info["text"] and "CONECTADO" in info["text"]

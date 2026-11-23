"""Arnés de capturas HU-86.T3 / HU-80.T1 (Playwright, 1366×768).

Levanta un backend HTTP mínimo (stub) que sirve un `RankingResult` fijo y un
Streamlit real de `app/app.py` contra él, abre el panel en Chromium a
1366×768 y guarda:

- una captura de la primera pantalla (sin scroll) por escenario;
- un `manifest.json` con fecha UTC, SHA del commit, SHA-256 de cada PNG y las
  mediciones que sustentan los criterios (mapa sobre el pliegue, número de
  advertencias visibles, subtítulo, texto prohibido) con su veredicto.

Criterios evaluados por escenario (`checks` en el manifiesto; el proceso sale
con código 1 si alguno falla):

- HU-80 CA3: exactamente una advertencia (`stAlert`) en la primera pantalla y
  un expander de detalle plegado.
- HU-80 CA4: el iframe del mapa termina dentro del viewport 1366×768.
- HU-80 CA1: la cabecera no menciona un sprint.
- HU-86: el texto vacío legado no aparece.

La revisión se registra antes de escribir ningún archivo y solo cuenta los
cambios en archivos versionados: una captura tomada con cambios sin confirmar
queda marcada `+dirty` y no sirve como evidencia de CA.

No usa Docker ni el backend Spring real: el payload es la fixture reproducible
del servicio ML (`predict-reproducible-2026-09-01.json`) o esa misma fixture
con los campos aditivos de prueba (`EXTENDED_FIELDS`). Las capturas se
rotulan con el escenario; ninguna se presenta como salida del backend real.

Uso (desde la raíz del repo):

    python tests/e2e/hu86_capture_panel.py --out tests/e2e/evidence/hu86 \
        [--repo-root RUTA] [--label after] [--port 18631]

`--repo-root` permite capturar otra revisión exportada (p. ej. la línea base
«antes») con este mismo arnés.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

FORBIDDEN_TEXT = "no informado por el backend"
VIEWPORT = {"width": 1366, "height": 768}
FIXTURE_REL = (
    "services/backend/src/test/resources/ml/predict-reproducible-2026-09-01.json"
)

# Copia de tests/test_backend_client.py::EXTENDED_FIELDS (payload de prueba).
EXTENDED_FIELDS: dict[str, Any] = {
    "weather_timestamp": "2026-08-31T23:45:00Z",
    "age_hours": 156.9,
    "freshness": "DATOS HISTÓRICOS / DESACTUALIZADOS",
    "station_id": "330007",
    "station_name": "Rodelillo",
    "model_status": "PROTOTYPE / EXPLORATORY",
    "meteo_actual": {
        "temperatura": 18.8,
        "humedad_relativa": 72.0,
        "velocidad_viento_kmh": 15.7,
        "regla_30_30_30": False,
    },
    "firms_origin": "current",
    "firms_coverage_end": "2026-08-30",
    "firms_lag_days": 2,
    "firms_status": "FIRMS AL DÍA",
}

# Medición en el navegador. Devuelve solo datos observables del DOM.
_MEASURE_JS = r"""
(forbidden) => {
  const vh = window.innerHeight, vw = window.innerWidth;
  const inView = (r) => r.bottom > 0 && r.top < vh && r.width > 0 && r.height > 0;
  const maps = [...document.querySelectorAll('iframe')]
    .map(f => f.getBoundingClientRect())
    .filter(r => r.height > 200)
    .sort((a, b) => a.top - b.top);
  const m = maps[0] || null;
  const map = m ? {
    top: Math.round(m.top), bottom: Math.round(m.bottom), height: Math.round(m.height),
    visible_px: Math.max(0, Math.round(Math.min(m.bottom, vh) - Math.max(m.top, 0))),
  } : null;
  const alerts = [...document.querySelectorAll('[data-testid="stAlert"]')]
    .filter(a => inView(a.getBoundingClientRect()))
    .map(a => a.innerText.trim().slice(0, 160));
  const disclaimers = [...document.querySelectorAll('.sapi-v2-disclaimer')]
    .filter(a => inView(a.getBoundingClientRect()))
    .map(a => a.innerText.trim().slice(0, 160));
  const sub = document.querySelector('.sapi-header-left');
  const header = document.querySelector('.sapi-v2-header');
  const dmc = document.querySelector('.sapi-dmc-top-bar');
  const detail = [...document.querySelectorAll('[data-testid="stExpander"] summary')]
    .filter(s => s.innerText.includes('Detalle del aviso'))
    .map(s => ({top: Math.round(s.getBoundingClientRect().top),
                open: s.closest('details') ? s.closest('details').open : null}));
  const body = document.body.innerText;
  const main = document.querySelector('[data-testid="stMain"], section.main') || document.body;
  return {
    viewport: {width: vw, height: vh},
    scroll_height: main.scrollHeight,
    map, alerts_in_view: alerts, disclaimers_in_view: disclaimers,
    subtitle: sub ? sub.innerText.trim() : null,
    header_mentions_sprint: header ? /sprint/i.test(header.innerText) : null,
    scope_detail_expanders: detail,
    dmc_strip_top: dmc ? Math.round(dmc.getBoundingClientRect().top) : null,
    forbidden_text_present: body.includes(forbidden),
  };
}
"""


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def git_sha(repo_root: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
        sha = out.stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        ).stdout.strip()
        return f"{sha}{'+dirty' if dirty else ''}"
    except (OSError, subprocess.CalledProcessError):
        marker = repo_root / "REVISION.txt"
        return (
            marker.read_text(encoding="utf-8").strip()
            if marker.exists()
            else "desconocido"
        )


class _Stub:
    def __init__(self, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_: Any) -> None:
                return

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server.server_port}"

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()


def _wait_port(port: int, timeout: float = 60.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.3)
    raise TimeoutError(f"Streamlit no abrió el puerto {port}")


def capture_scenario(
    repo_root: Path,
    out_dir: Path,
    name: str,
    payload: dict,
    port: int,
    label: str,
    theme: str = "dark",
) -> dict:
    from playwright.sync_api import sync_playwright

    stub = _Stub(payload)
    env = dict(os.environ)
    env.update(
        {
            "SAPI_BACKEND_BASE_URL": stub.url,
            "SAPI_UI_LEGACY_MODES": "0",
            "PYTHONPATH": str(repo_root),
            "STREAMLIT_BROWSER_GATHER_USAGE_STATS": "false",
        }
    )
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(repo_root / "app" / "app.py"),
            "--server.headless",
            "true",
            "--server.port",
            str(port),
            "--server.address",
            "127.0.0.1",
        ],
        cwd=repo_root,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_port(port)
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(viewport=VIEWPORT, color_scheme=theme)
            page.goto(f"http://127.0.0.1:{port}/", wait_until="networkidle")
            page.wait_for_selector(".sapi-v2-header", timeout=60000)
            # El mapa Folium vive en un iframe; se espera a que tenga altura.
            page.wait_for_function(
                "() => [...document.querySelectorAll('iframe')]"
                ".some(f => f.getBoundingClientRect().height > 200)",
                timeout=60000,
            )
            page.wait_for_timeout(2500)
            metrics = page.evaluate(_MEASURE_JS, FORBIDDEN_TEXT)
            shot = out_dir / f"{label}_{name}_1366x768.png"
            page.screenshot(path=str(shot), full_page=False)
            browser.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
        stub.stop()
    return {
        "scenario": name,
        "checks": evaluate(metrics),
        "screenshot": shot.name,
        "screenshot_sha256": sha256_file(shot),
        "metrics": metrics,
    }


def evaluate(metrics: dict) -> dict[str, bool]:
    """Veredicto por criterio a partir de las mediciones del DOM."""
    vh = metrics["viewport"]["height"]
    m = metrics.get("map")
    detail = metrics.get("scope_detail_expanders") or []
    return {
        "HU-80_CA3_una_advertencia": len(metrics.get("alerts_in_view", [])) == 1,
        "HU-80_CA3_detalle_en_expander_plegado": len(detail) == 1
        and detail[0]["open"] is False,
        "HU-80_CA4_mapa_sobre_el_pliegue": bool(m)
        and m["top"] >= 0
        and m["bottom"] <= vh,
        "HU-80_CA1_sin_sprint": metrics.get("header_mentions_sprint") is False,
        "HU-86_sin_texto_legado": metrics.get("forbidden_text_present") is False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default="tests/e2e/evidence/hu86")
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[2]))
    parser.add_argument("--label", default="after")
    parser.add_argument("--port", type=int, default=18631)
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    revision = git_sha(repo_root)  # antes de escribir capturas o manifiestos
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    fixture = json.loads((repo_root / FIXTURE_REL).read_text(encoding="utf-8"))
    extended = copy.deepcopy(fixture)
    extended.update(EXTENDED_FIELDS)

    scenarios = [
        ("contrato_v0_fixture_real", fixture),
        ("payload_extendido_prueba", extended),
    ]
    results = [
        capture_scenario(repo_root, out_dir, name, payload, args.port + i, args.label)
        for i, (name, payload) in enumerate(scenarios)
    ]
    manifest = {
        "harness": "tests/e2e/hu86_capture_panel.py",
        "captured_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "label": args.label,
        "revision": revision,
        "viewport": VIEWPORT,
        "backend": "stub HTTP local (no Spring real)",
        "results": results,
    }
    manifest_path = out_dir / f"{args.label}_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    failed = [
        f"{r['scenario']}:{k}"
        for r in results
        for k, ok in r["checks"].items()
        if not ok
    ]
    if failed:
        print("FALLAN: " + ", ".join(failed), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

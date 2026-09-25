"""Lanzador único del Centro de Control de SAPI (solo presentación, solo lectura).

    python -m app.control_center --demo                 # sin bridge, n8n ni internet
    python -m app.control_center --demo --presentation  # modo presentación
    python -m app.control_center --live                 # lee SAPI_SCORE_URL (GET /score)
    python -m app.control_center --live --score-url http://127.0.0.1:8600/score

Sirve `app/pages/dashboard.py` como script principal, en la raíz del servidor
(`http://localhost:<puerto>/`). Así el frontend de Streamlit no sondea
`/<página>/_stcore/*`, que es lo que devuelve 404 al abrir una página por subruta.

NO inicia ni detiene nada más: ni el bridge, ni n8n, ni refresh FIRMS/DMC, ni
Docker, ni el operador. En modo en vivo, si el bridge no está corriendo, el
panel muestra SERVICIO NO DISPONIBLE (nunca datos de demo).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

PAGE = Path(__file__).resolve().parent / "pages" / "dashboard.py"
REPO_ROOT = PAGE.parents[2]
DEFAULT_PORT = 8501


def page_query(demo: bool, presentation: bool) -> str:
    params = (["demo=1"] if demo else []) + (["presentation=1"] if presentation else [])
    return "?" + "&".join(params) if params else ""


def build_command(port: int) -> list[str]:
    return [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(PAGE),
        "--server.port",
        str(port),
        "--server.address",
        "127.0.0.1",
        "--server.headless",
        "true",
        "--browser.gatherUsageStats",
        "false",
    ]


def _open_when_ready(url: str, health: str, timeout_s: float = 60.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(health, timeout=2) as r:  # GET local de salud
                if r.status == 200:
                    webbrowser.open(url)
                    return
        except OSError:
            time.sleep(0.5)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m app.control_center",
        description="Centro de Control SAPI (solo lectura). No inicia otros servicios.",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--demo", action="store_true", help="fixture sintética local")
    mode.add_argument("--live", action="store_true", help="lee GET /score del bridge")
    parser.add_argument("--presentation", action="store_true", help="modo presentación")
    parser.add_argument(
        "--score-url",
        help="endpoint /score (por defecto SAPI_SCORE_URL de src/config.py)",
    )
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--no-browser", action="store_true", help="no abrir el navegador"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    env = dict(os.environ)
    if args.score_url:
        env["SAPI_SCORE_URL"] = args.score_url
    base = f"http://127.0.0.1:{args.port}"
    url = base + "/" + page_query(args.demo, args.presentation)
    print(f"Centro de Control SAPI: {url}")
    if args.live:
        print(
            "Modo en vivo: requiere el bridge ya en ejecucion; este comando no lo inicia."
        )
    if not args.no_browser:
        threading.Thread(
            target=_open_when_ready, args=(url, base + "/_stcore/health"), daemon=True
        ).start()
    try:
        return subprocess.call(build_command(args.port), cwd=REPO_ROOT, env=env)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

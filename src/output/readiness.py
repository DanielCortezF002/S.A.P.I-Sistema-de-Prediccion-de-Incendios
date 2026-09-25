"""¿Está el Output Plane listo para RC1? Un comando, sin servicios reales.

    python -m src.output.readiness [--out OUTPUT_PLANE_MANIFEST.json]

Ejecuta, con un resultado SINTÉTICO (src/output/synthetic.py) y solo en proceso o
loopback (127.0.0.1), los chequeos de la cadena de salida y emite un
OUTPUT_PLANE_MANIFEST determinista y versionado. Estados:

    READY       todos los chequeos pasaron
    NOT_READY   al menos un chequeo falló
    INCOMPLETE  ninguno falló pero alguno no pudo ejecutarse (p. ej. sin `node`)

El manifest es EVIDENCIA, no autorización: no habilita envíos ni despliegues.
Exit: 0 READY · 1 NOT_READY · 2 INCOMPLETE.
"""

from __future__ import annotations

import argparse
import copy
import dataclasses
import hashlib
import http.server
import json
import shutil
import socket
import subprocess
import sys
import threading
from pathlib import Path
from typing import Callable, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_SCHEMA_VERSION = "sapi-output-plane-manifest-v1"
READY, NOT_READY, INCOMPLETE = "READY", "NOT_READY", "INCOMPLETE"
PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"

# Código que compone el Output Plane (identidad de contenido, independiente de git).
OUTPUT_SOURCES = (
    "app/components/ops_dashboard.py",
    "app/control_center.py",
    "app/data/demo_score_synthetic.json",
    "app/pages/dashboard.py",
    "app/utils/score_contract.py",
    "ops/n8n/build_workflow.py",
    "ops/n8n/controlled-preview.json",
    "ops/n8n/policy.js",
    "src/notifications/alert_payload.py",
    "src/output/__init__.py",
    "src/output/accepted_run.py",
    "src/output/contract.py",
    "src/output/readiness.py",
    "src/output/synthetic.py",
    "tools/n8n_bridge/app.py",
    "tools/n8n_bridge/contract.py",
    "tools/n8n_bridge/output_contract.py",
)
CONTROL_CENTER_SOURCES = OUTPUT_SOURCES[:5]
_WRITE_TOKENS = (
    ".post(",
    ".put(",
    ".patch(",
    ".delete(",
    "api.telegram",
    "sendmessage",
    "smtplib",
    "webhook",
)


class CheckFailed(AssertionError):
    pass


def _require(condition: bool, detail: str) -> None:
    if not condition:
        raise CheckFailed(detail)


def _normalized(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n")  # autocrlf no cambia la identidad


def sources_sha256(paths=OUTPUT_SOURCES) -> str:
    digest = hashlib.sha256()
    for rel in sorted(paths):
        digest.update(
            rel.encode() + b"\0" + hashlib.sha256(_normalized(REPO_ROOT / rel)).digest()
        )
    return digest.hexdigest()


def _git(*args: str) -> Optional[str]:
    try:
        out = subprocess.run(
            ["git", *args],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=20,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip()


# --- Contexto sintético compartido -----------------------------------------------------


class _Context:
    def __init__(self):
        self._body: Optional[dict] = None

    def bridge_response(self, result):
        from fastapi.testclient import TestClient

        import tools.n8n_bridge.app as bridge_app

        saved = bridge_app.score_current_grid, bridge_app._read_metadata_json
        bridge_app.score_current_grid = lambda: result
        bridge_app._read_metadata_json = lambda: None
        try:
            return TestClient(bridge_app.app).get("/score")
        finally:
            bridge_app.score_current_grid, bridge_app._read_metadata_json = saved

    @property
    def body(self) -> dict:
        if self._body is None:
            from src.output.synthetic import synthetic_result

            resp = self.bridge_response(synthetic_result())
            _require(resp.status_code == 200, f"bridge devolvió {resp.status_code}")
            self._body = resp.json()
        return copy.deepcopy(self._body)


def _serve_once(body: bytes) -> tuple[str, Callable[[], None]]:
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    def stop():
        server.shutdown()
        server.server_close()

    return f"http://127.0.0.1:{server.server_address[1]}/score", stop


def _node_policy(body: dict) -> Optional[dict]:
    node = shutil.which("node")
    if node is None:
        return None
    runner = (
        "const {evaluate}=require(process.argv[1]);let r='';process.stdin.on('data',d=>r+=d)"
        ".on('end',()=>{const b=JSON.parse(r);process.stdout.write(JSON.stringify("
        "evaluate({statusCode:200,data:JSON.stringify(b)},'2026-09-24T13:00:00Z','readiness')"
        "))});"
    )
    proc = subprocess.run(
        [node, "-e", runner, str(REPO_ROOT / "ops/n8n/policy.js")],
        input=json.dumps(body),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=True,
    )
    return json.loads(proc.stdout)


# --- Chequeos ------------------------------------------------------------------------------


def check_bridge_serializer(ctx: _Context) -> str:
    from src.output.contract import OUTPUT_SCHEMA_VERSION

    body = ctx.body
    _require(
        body.get("output_schema_version") == OUTPUT_SCHEMA_VERSION,
        "sin contrato canónico",
    )
    _require(len(body["cells"]) == 50 and "alert_identity" in body, "salida incompleta")
    return f"GET /score → 200 {OUTPUT_SCHEMA_VERSION}, 50 celdas, alert_identity"


def check_bridge_fail_closed(ctx: _Context) -> str:
    from src.output.synthetic import synthetic_result

    result = synthetic_result()
    bad = dataclasses.replace(result, cells=result.cells[:49])
    resp = ctx.bridge_response(bad)
    body = resp.json()
    _require(
        resp.status_code == 500
        and body.get("error_type") == "internal_error"
        and "cells" not in body,
        "un resultado inválido no cerró con 500",
    )
    return "49 celdas → 500 internal_error, sin celdas"


def check_control_center_adapter(ctx: _Context) -> str:
    from app.utils import score_contract as sc

    view = sc.from_payload(ctx.body)
    _require(
        view.state == sc.LIVE_READY and len(view.cells) == 50, f"estado {view.state}"
    )
    _require([c.rank for c in view.top] == [1, 2, 3, 4, 5], "Top 5 fuera de orden")
    return "salida canónica → LIVE_READY, 50 celdas, Top 5 = ranks 1..5"


def check_demo_mode(ctx: _Context) -> str:
    from app.utils import score_contract as sc

    view = sc.load_demo()
    _require(view.state == sc.DEMO and len(view.cells) == 50, f"estado {view.state}")
    marked = sc.from_payload(json.loads(sc.DEMO_FIXTURE.read_text(encoding="utf-8")))
    _require(
        marked.state == sc.INVALID_RESULT, "la fixture demo pasaría por la vía en vivo"
    )
    return "fixture local → DEMO; la misma fixture por la vía en vivo se rechaza"


def check_live_mode(ctx: _Context) -> str:
    from app.utils import score_contract as sc

    url, stop = _serve_once(json.dumps(ctx.body).encode())
    try:
        view = sc.fetch_live(url)
    finally:
        stop()
    _require(view.state == sc.LIVE_READY, f"estado {view.state}")
    dead = sc.fetch_live(url)  # servidor ya detenido
    _require(
        dead.state == sc.NETWORK_ERROR and not dead.cells,
        "sin servicio no dio NETWORK_ERROR",
    )
    return "GET loopback → LIVE_READY; sin servicio → NETWORK_ERROR sin demo"


def check_replay_mode(ctx: _Context) -> str:
    from app.utils import score_contract as sc
    from src.output import accepted_run as ar

    body = ctx.body
    doc = ar.build_artifact(
        body,
        data_origin=ar.DATA_SYNTHETIC,
        captured_at="2026-09-24T13:05:00+00:00",
        source_url="http://127.0.0.1:8600/score",
    )
    reasons, replay = ar.verify_artifact(doc)
    _require(not reasons and replay is not None, f"artefacto rechazado: {reasons}")
    live = sc.from_payload(body)
    same = [(c.rank, c.cell_id, c.score) for c in live.cells] == [
        (c.rank, c.cell_id, c.score) for c in replay.cells
    ]
    _require(
        same and replay.alert.fingerprint == live.alert.fingerprint, "replay ≠ en vivo"
    )
    tampered = copy.deepcopy(doc)
    tampered["stable"]["output"]["cells"][0]["score"] = 0.99
    _require(ar.verify_artifact(tampered)[0], "artefacto alterado aceptado")
    return (
        f"{ar.ARTIFACT_SCHEMA_VERSION} → REPLAY_READY ≡ en vivo; alterado → rechazado"
    )


def check_alert_renderer(ctx: _Context) -> str:
    from src.notifications.alert_payload import (
        assert_claim_safe,
        build_alert,
        render_text,
    )

    alert = build_alert(ctx.body)
    _require(alert["status"] == "READY", "alerta no READY")
    assert_claim_safe(render_text(alert))
    return f"{alert['schema_version']} READY, texto sin afirmaciones prohibidas"


def check_identity_python_js(ctx: _Context) -> str:
    body = ctx.body
    result = _node_policy(body)
    if result is None:
        raise _Skip("node no disponible")
    _require(
        result.get("alert_identity_verified") is True, "n8n no verificó la identidad"
    )
    _require(
        result["notification_identity"] == body["alert_identity"]["alert_fingerprint"],
        "identidad Python ≠ JavaScript",
    )
    return "ops/n8n/policy.js recalcula la misma alert_fingerprint que Python"


def check_n8n_policy_verify(ctx: _Context) -> str:
    body = ctx.body
    body["alert_identity"]["alert_fingerprint"] = "0" * 64
    result = _node_policy(body)
    if result is None:
        raise _Skip("node no disponible")
    _require(
        result["category"] == "blocked"
        and result["reason"] == "alert_identity_mismatch",
        "identidad alterada no bloqueada",
    )
    return "identidad alterada → blocked (nunca notificable), delivery NOT_SENT"


def check_application_resources(ctx: _Context) -> str:
    from app import control_center as launcher

    missing = [rel for rel in CONTROL_CENTER_SOURCES if not (REPO_ROOT / rel).is_file()]
    _require(not missing, f"faltan: {missing}")
    for rel in ("app/pages/dashboard.py", "app/control_center.py"):
        compile((REPO_ROOT / rel).read_text(encoding="utf-8"), rel, "exec")
    cmd = launcher.build_command(8501)
    _require(
        Path(cmd[4]) == REPO_ROOT / "app/pages/dashboard.py",
        "el lanzador no sirve la página en la raíz (404 de _stcore)",
    )
    return "página, lanzador, tema y fixture presentes; página servida en la raíz"


def check_no_write_routes(ctx: _Context) -> str:
    import tools.n8n_bridge.app as bridge_app

    methods = {
        m for r in bridge_app.app.routes for m in getattr(r, "methods", set()) or set()
    }
    _require(methods <= {"GET", "HEAD"}, f"el bridge expone {sorted(methods)}")
    offenders = [
        rel
        for rel in OUTPUT_SOURCES
        if rel.endswith((".py", ".js"))
        and rel != "src/output/readiness.py"
        and any(
            tok in (REPO_ROOT / rel).read_text(encoding="utf-8").lower()
            for tok in _WRITE_TOKENS
        )
    ]
    _require(not offenders, f"posibles escrituras/envíos en {offenders}")
    workflow = json.loads(
        (REPO_ROOT / "ops/n8n/controlled-preview.json").read_text("utf-8")
    )
    _require(workflow.get("active") is False, "el workflow n8n está activo")
    return "bridge solo GET/HEAD; sin POST/PUT/DELETE/envíos; workflow n8n inactivo"


class _Skip(Exception):
    pass


CHECKS: tuple[tuple[str, Callable[[_Context], str]], ...] = (
    ("bridge_canonical_serializer", check_bridge_serializer),
    ("bridge_invalid_fail_closed", check_bridge_fail_closed),
    ("control_center_adapter", check_control_center_adapter),
    ("demo_mode", check_demo_mode),
    ("live_mode", check_live_mode),
    ("replay_mode", check_replay_mode),
    ("alert_renderer", check_alert_renderer),
    ("notification_identity_python_js", check_identity_python_js),
    ("n8n_policy_verification", check_n8n_policy_verify),
    ("application_resources", check_application_resources),
    ("no_write_routes", check_no_write_routes),
)


def run_checks() -> list[dict]:
    ctx, results = _Context(), []
    for name, fn in CHECKS:
        try:
            results.append({"name": name, "status": PASS, "detail": fn(ctx)})
        except _Skip as exc:
            results.append({"name": name, "status": SKIP, "detail": str(exc)})
        except (
            Exception
        ) as exc:  # noqa: BLE001 -- cualquier fallo es NOT_READY, con motivo
            detail = str(exc) if isinstance(exc, CheckFailed) else type(exc).__name__
            results.append({"name": name, "status": FAIL, "detail": detail})
    return results


def overall(results: list[dict]) -> str:
    statuses = {r["status"] for r in results}
    if FAIL in statuses:
        return NOT_READY
    return INCOMPLETE if SKIP in statuses else READY


def build_manifest(results: list[dict]) -> dict:
    from src.notifications.alert_payload import SCHEMA_VERSION as ALERT_SCHEMA
    from src.output.accepted_run import ARTIFACT_SCHEMA_VERSION
    from src.output.contract import OUTPUT_SCHEMA_VERSION

    policy = (REPO_ROOT / "ops/n8n/policy.js").read_text(encoding="utf-8")
    suppression = "sapi-suppression-v1" if "'sapi-suppression-v1'" in policy else None
    dirty = _git("status", "--porcelain", "--", *OUTPUT_SOURCES)
    manifest = {
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "output_code": {
            "git_head": _git("rev-parse", "HEAD"),
            "output_sources_clean": None if dirty is None else dirty == "",
            "sources_sha256": sources_sha256(),
            "sources": list(OUTPUT_SOURCES),
        },
        "bridge_contract_version": OUTPUT_SCHEMA_VERSION,
        "control_center": {
            "identity_sha256": sources_sha256(CONTROL_CENTER_SOURCES),
            "launch": "python -m app.control_center --demo|--live|--replay",
        },
        "alert_schema_version": ALERT_SCHEMA,
        "notification_identity_recipe": f"{ALERT_SCHEMA}/alert_fingerprint",
        "suppression_policy_version": suppression,
        "replay_artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "readiness": {"status": overall(results), "checks": results},
        "authorization": "NONE: este manifest es evidencia, no autoriza envíos ni despliegues",
    }
    canonical = json.dumps(
        manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    manifest["manifest_fingerprint"] = hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()
    return manifest


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m src.output.readiness",
        description="Readiness del Output Plane para RC1.",
    )
    parser.add_argument(
        "--out", type=Path, help="escribe el OUTPUT_PLANE_MANIFEST en esta ruta"
    )
    args = parser.parse_args(argv)
    socket.setdefaulttimeout(30)
    manifest = build_manifest(run_checks())
    text = json.dumps(manifest, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text, end="")
    return {READY: 0, NOT_READY: 1, INCOMPLETE: 2}[manifest["readiness"]["status"]]


if __name__ == "__main__":
    sys.exit(main())

"""Integración del lado de salida (sapi-output-v1), sin datos reales ni envío.

GridScoreResult sintético → bridge GET /score → contrato canónico
  ├─ Control Center (app/utils/score_contract.py)
  ├─ payload de alerta (src/notifications/alert_payload.py)
  └─ política n8n (ops/n8n/policy.js, ejecutada con Node sin workflow)

Los cuatro deben coincidir en celdas, rank, inputs_fingerprint e identidad de
alerta. Las partes en JavaScript se saltan si no hay `node` en el PATH.
"""

from __future__ import annotations

import copy
import dataclasses
import http.server
import json
import math
import shutil
import subprocess
import threading
from datetime import date
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import tools.n8n_bridge.app as bridge_app
from app.utils import score_contract as sc
from src.inference.prototype_service import (
    FIRMS_STATUS_CURRENT,
    CellScore,
    GridScoreResult,
)
from src.inference.scoring_inputs import _canonical_sha
from src.geo.grid import all_cells
from src.notifications.alert_payload import build_alert
from tools.n8n_bridge.output_contract import OUTPUT_SCHEMA_VERSION

REPO = Path(__file__).resolve().parents[1]
POLICY = REPO / "ops" / "n8n" / "policy.js"
FIXTURES = REPO / "ops" / "n8n" / "fixtures"
NOW = "2026-09-24T13:00:00Z"  # dentro de la ventana de 6 h de la evaluación sintética
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="node no disponible")
client = TestClient(bridge_app.app)
SECRET = "SYNTH-SECRET-output-NOT-REAL"


# --- Resultado sintético -------------------------------------------------------------


def _cells(scores: list[float]) -> list[CellScore]:
    grid = all_cells()
    return [
        CellScore(
            cell_id=grid[i]["cell_id"],
            score=score,
            rank=i + 1,
            display_rank=1 + sum(s > score for s in scores),
            tie_group_size=scores.count(score),
            geometry={
                k: grid[i][k] for k in ("min_lon", "min_lat", "max_lon", "max_lat")
            },
            elevation=None,
            slope=8.1,
            historical_count=0,
        )
        for i, score in enumerate(scores)
    ]


def _manifest() -> dict:
    """Forma de ScoringInputs.manifest() con hashes sintéticos (no son archivos reales)."""
    return {
        "reproducibility_mode": False,
        "forecast_time": "2026-09-24T12:00:00+00:00",
        "weather_timestamp": "2026-09-24T12:00:00+00:00",
        "model": {
            "role": "model",
            "origin": "pinned",
            "name": "prototype_model_d.pkl",
            "sha256": "1" * 64,
            "size": 1024,
            "model_version": "prototype_model_d_v1",
        },
        "firms": {
            "role": "firms",
            "origin": "current",
            "name": "firms.csv",
            "sha256": "2" * 64,
            "size": 2048,
            "coverage_start": "2024-01-01",
            "coverage_end": "2026-09-23",
            "lag_days": 1,
            "status": FIRMS_STATUS_CURRENT,
            "pointer_version": "v7",
        },
        "dmc": {
            "files": [
                {
                    "role": "dmc",
                    "origin": "versioned",
                    "name": "2026-09.json",
                    "sha256": "3" * 64,
                    "size": 512,
                }
            ],
            "manifest_sha256": "4" * 64,
            "coverage_start": "2026-08-01T00:00:00+00:00",
            "coverage_end": "2026-09-24T12:00:00+00:00",
            "pointer_version": "v3",
        },
        "topography": {"origin": "baseline", "sha256": "5" * 64},
    }


def synthetic_result(**changes) -> GridScoreResult:
    scores = [0.4, 0.4] + [round(0.3 - 0.005 * i, 4) for i in range(48)]
    manifest = changes.pop("manifest", _manifest())
    result = GridScoreResult(
        forecast_time=pd.Timestamp("2026-09-24T12:00:00Z"),
        horizon_hours=6,
        station_id="330007",
        station_name="Rodelillo",
        weather_timestamp=pd.Timestamp("2026-09-24T12:00:00Z"),
        age_hours=1.0,
        freshness="DATOS RECIENTES",
        model_version="prototype_model_d_v1",
        model_status="PROTOTYPE / EXPLORATORY",
        meteo_actual={
            "temperatura": 31.0,
            "humedad_relativa": 28.0,
            "velocidad_viento_kmh": 32.0,
            "regla_30_30_30": True,
            "momento_observacion": pd.Timestamp("2026-09-24T12:00:00Z"),
        },
        cells=_cells(scores),
        firms_origin="current",
        firms_coverage_end=date(2026, 9, 23),
        firms_lag_days=1,
        firms_status=FIRMS_STATUS_CURRENT,
        inputs_fingerprint=_canonical_sha(manifest),
        scoring_inputs=manifest,
    )
    return dataclasses.replace(result, **changes)


def bridge_get(monkeypatch, result):
    monkeypatch.setattr(bridge_app, "score_current_grid", lambda: result)
    monkeypatch.setattr(bridge_app, "_read_metadata_json", lambda: None)
    return client.get("/score")


def bridge_body(monkeypatch, result=None) -> dict:
    resp = bridge_get(monkeypatch, result or synthetic_result())
    assert resp.status_code == 200, resp.text
    return resp.json()


# --- Política n8n ejecutada con Node (sin workflow, sin red) -----------------------------

_RUNNER = """
const { evaluate, deduplicate } = require(process.argv[1]);
let raw = ''; process.stdin.on('data', d => raw += d).on('end', () => {
  const job = JSON.parse(raw);
  const results = job.envelopes.map((e, i) => evaluate(e, job.now, 'pytest-' + i));
  const dedup = results.map((r, i) => deduplicate(r, i ? results[i - 1] : null));
  process.stdout.write(JSON.stringify({ results, dedup }));
});
"""


def run_policy(*bodies, now: str = NOW, raw: bool = False) -> dict:
    envelopes = [
        (
            b
            if raw
            else {
                "statusCode": 200,
                "statusMessage": "OK",
                "headers": {},
                "data": json.dumps(b, ensure_ascii=False),
            }
        )
        for b in bodies
    ]
    proc = subprocess.run(
        [NODE, "-e", _RUNNER, str(POLICY)],
        input=json.dumps({"envelopes": envelopes, "now": now}),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=True,
    )
    return json.loads(proc.stdout)


# --- 17. Integración de extremo a extremo ----------------------------------------------------


@needs_node
def test_end_to_end_same_result_across_all_components(monkeypatch):
    result = synthetic_result()
    body = bridge_body(monkeypatch, result)

    # contrato canónico
    assert body["output_schema_version"] == OUTPUT_SCHEMA_VERSION
    fp = body["alert_identity"]["alert_fingerprint"]
    assert body["alert_identity"] == {
        "schema_version": "sapi-alert-v1",
        "alert_fingerprint": fp,
        "top_n": 5,
    }

    # Control Center (vía en vivo, sin transformar el JSON)
    view = sc.from_payload(body)
    assert view.state == sc.LIVE_READY
    assert [(c.rank, c.cell_id, c.score) for c in view.cells] == [
        (c.rank, c.cell_id, c.score) for c in result.cells
    ]
    assert view.inputs_fingerprint == result.inputs_fingerprint
    assert view.alert.fingerprint == fp

    # payload de alerta
    alert = build_alert(body)
    assert alert["alert_fingerprint"] == fp
    assert [(c["rank"], c["cell_id"], c["score"]) for c in alert["top_cells"]] == [
        (c.rank, c.cell_id, c.score) for c in result.cells[:5]
    ]

    # política n8n
    policy = run_policy(body)["results"][0]
    assert policy["alert_identity_verified"] is True
    assert policy["notification_identity"] == fp
    assert policy["inputs_fingerprint"] == result.inputs_fingerprint
    assert policy["category"] == "candidate" and policy["delivery"] == "NOT_SENT"
    assert policy["top_group"] == [
        "VP-001",
        "VP-002",
    ]  # empate en rank 1-2, sin re-rankear


def test_input_identity_is_passed_through_and_whitelisted(monkeypatch):
    body = bridge_body(monkeypatch)
    ident = body["input_identity"]
    assert ident["model"] == {
        "sha256": "1" * 64,
        "name": "prototype_model_d.pkl",
        "version": "prototype_model_d_v1",
    }
    assert (
        ident["firms"]["sha256"] == "2" * 64
        and ident["firms"]["pointer_version"] == "v7"
    )
    assert ident["dmc"]["manifest_sha256"] == "4" * 64
    assert ident["topography"] == {"sha256": "5" * 64, "origin": "baseline"}
    assert ident["code"] is None  # no existe upstream: no se inventa
    assert "files" not in json.dumps(ident) and "size" not in ident["model"]

    view = sc.from_payload(body)
    assert view.identity["model_sha256"] == "1" * 64
    assert view.identity["dmc_manifest_sha256"] == "4" * 64
    assert view.identity["topography_sha256"] == "5" * 64


def test_technical_details_show_every_identity(monkeypatch):
    from app.components import ops_dashboard as ui

    body = bridge_body(monkeypatch)
    view = sc.from_payload(body)
    tech = ui.technical_details(view)
    for value in (
        body["inputs_fingerprint"],
        "1" * 64,
        "2" * 64,
        "4" * 64,
        "5" * 64,
        body["alert_identity"]["alert_fingerprint"],
    ):
        assert f"{value[:12]}…" in tech  # truncado en pantalla
        assert value in [v for _, v in ui.full_hashes(view)]  # completo y copiable


def test_missing_scoring_inputs_marks_identities_unavailable(monkeypatch):
    manifest = None
    result = dataclasses.replace(synthetic_result(), scoring_inputs=manifest)
    body = bridge_body(monkeypatch, result)
    assert {
        k: body["input_identity"][k] for k in ("model", "firms", "dmc", "topography")
    } == {"model": None, "firms": None, "dmc": None, "topography": None}
    assert sc.from_payload(body).identity == {}


def test_fingerprint_must_match_scoring_inputs(monkeypatch):
    result = dataclasses.replace(synthetic_result(), inputs_fingerprint="f" * 64)
    resp = bridge_get(monkeypatch, result)
    assert resp.status_code == 500 and resp.json()["error_type"] == "internal_error"


def test_secrets_in_manifest_or_result_never_leave_the_bridge(monkeypatch):
    manifest = _manifest()
    manifest["dmc"]["token"] = SECRET
    manifest["dmc"]["pointer_version"] = f"Authorization: Bearer {SECRET}"
    manifest["env"] = {"NASA_FIRMS_API_KEY": SECRET, "DMC_USUARIO": SECRET}
    body = bridge_body(monkeypatch, synthetic_result(manifest=manifest))
    text = json.dumps(body)
    for leak in (
        SECRET,
        "NASA_FIRMS_API_KEY",
        "DMC_USUARIO",
        "DMC_TOKEN",
        "Authorization",
        "Cookie",
    ):
        assert leak not in text
    assert (
        body["input_identity"]["dmc"]["pointer_version"] is None
    )  # etiqueta no segura


# --- 18. Reintentos / deduplicación ---------------------------------------------------------


def _fp(body) -> str:
    return body["alert_identity"]["alert_fingerprint"]


def test_retry_identity_is_stable_and_bound_to_content(monkeypatch):
    first = bridge_body(monkeypatch)
    again = bridge_body(monkeypatch)
    assert _fp(first) == _fp(again)  # mismo resultado procesado dos veces
    a = build_alert(first, generated_at="2026-09-24T12:01:00+00:00")
    b = build_alert(first, generated_at="2026-09-24T12:59:00+00:00")
    assert a["alert_fingerprint"] == b["alert_fingerprint"] == _fp(first)

    other_inputs = _manifest()
    other_inputs["model"]["sha256"] = "9" * 64
    assert _fp(
        bridge_body(monkeypatch, synthetic_result(manifest=other_inputs))
    ) != _fp(first)

    cells = list(synthetic_result().cells)
    cells[4] = dataclasses.replace(
        cells[4], score=0.2851
    )  # 5.ª celda, sin alterar el orden
    assert _fp(bridge_body(monkeypatch, synthetic_result(cells=cells))) != _fp(first)

    later = synthetic_result(
        forecast_time=pd.Timestamp("2026-09-24T13:00:00Z"),
        weather_timestamp=pd.Timestamp("2026-09-24T13:00:00Z"),
        meteo_actual={
            **synthetic_result().meteo_actual,
            "momento_observacion": pd.Timestamp("2026-09-24T13:00:00Z"),
        },
    )
    assert _fp(bridge_body(monkeypatch, later)) != _fp(first)


@needs_node
def test_n8n_dedupe_retry_suppressed_new_evaluation_notifies(monkeypatch):
    body = bridge_body(monkeypatch)
    other = _manifest()
    other["firms"]["sha256"] = "8" * 64
    new_eval = bridge_body(monkeypatch, synthetic_result(manifest=other))
    out = run_policy(body, body, new_eval)
    first, retry, fresh = out["dedup"]
    assert first["would_notify"] is True
    assert retry["would_notify"] is False and retry["notification_identity"] == _fp(
        body
    )
    assert fresh["would_notify"] is True and fresh["notification_identity"] == _fp(
        new_eval
    )
    assert {r["delivery"] for r in out["dedup"]} == {"NOT_SENT"}


# --- 19/20. Fallos: el bridge rechaza; n8n no deja enviable nada sin identidad ----------------


@pytest.mark.parametrize(
    "mutate",
    [
        lambda r: dataclasses.replace(r, cells=r.cells[:49]),
        lambda r: dataclasses.replace(
            r, cells=[r.cells[0], dataclasses.replace(r.cells[1], rank=1), *r.cells[2:]]
        ),
        lambda r: dataclasses.replace(
            r,
            cells=[
                r.cells[0],
                dataclasses.replace(r.cells[1], cell_id="VP-001"),
                *r.cells[2:],
            ],
        ),
        lambda r: dataclasses.replace(
            r,
            cells=[
                *r.cells[:3],
                dataclasses.replace(r.cells[3], score=math.nan),
                *r.cells[4:],
            ],
        ),
        lambda r: dataclasses.replace(r, inputs_fingerprint=None),
    ],
    ids=["49_cells", "duplicate_rank", "duplicate_cell", "nan", "missing_fingerprint"],
)
def test_bridge_rejects_invalid_results(monkeypatch, mutate):
    resp = bridge_get(monkeypatch, mutate(synthetic_result()))
    assert resp.status_code == 500
    body = resp.json()
    assert body["error_type"] == "internal_error" and "cells" not in body
    assert "alert_identity" not in body


@needs_node
@pytest.mark.parametrize(
    "mutate,reason",
    [
        (lambda b: b.pop("alert_identity"), "missing_alert_identity"),
        (lambda b: b.pop("output_schema_version"), "missing_alert_identity"),
        (
            lambda b: b["alert_identity"].update(alert_fingerprint="0" * 64),
            "alert_identity_mismatch",
        ),
        (
            lambda b: [b["cells"][i].update(score=0.39) for i in (0, 1)],
            "alert_identity_mismatch",
        ),
        (lambda b: b.update(inputs_fingerprint="e" * 64), "alert_identity_mismatch"),
        (
            lambda b: b.update(forecast_time="2026-09-24T12:30:00+00:00"),
            "alert_identity_mismatch",
        ),
    ],
    ids=[
        "no_identity",
        "no_schema",
        "tampered_fp",
        "tampered_score",
        "tampered_inputs",
        "tampered_time",
    ],
)
def test_n8n_blocks_missing_or_tampered_identity(monkeypatch, mutate, reason):
    body = copy.deepcopy(bridge_body(monkeypatch))
    mutate(body)
    out = run_policy(body)
    result, dedup = out["results"][0], out["dedup"][0]
    assert result["category"] == "blocked" and result["reason"] == reason
    assert result["alert_identity_verified"] is False
    assert dedup["would_notify"] is False and dedup["delivery"] == "NOT_SENT"
    assert result["notification_identity"] != _fp(bridge_body(monkeypatch))


@needs_node
@pytest.mark.parametrize("error_type", ["data_unavailable", "prototype_unavailable"])
def test_unavailable_never_becomes_ranking_notification(monkeypatch, error_type):
    envelope = {
        "statusCode": 503,
        "data": json.dumps({"status": "error", "error_type": error_type}),
    }
    policy = run_policy(envelope, raw=True)["results"][0]
    assert policy["category"] == "error" and policy["top_group"] == []
    assert "No implica riesgo bajo ni ausencia de incendios" in policy["message"]
    # misma identidad no-lista que alert_payload (receta única)
    python = build_alert({"status": "error", "error_type": error_type})
    assert policy["notification_identity"] == python["alert_fingerprint"]
    view = sc.from_payload({"status": "error", "error_type": error_type})
    assert (
        view.state in (sc.DATA_UNAVAILABLE, sc.PROTOTYPE_UNAVAILABLE) and not view.cells
    )


@needs_node
def test_internal_error_identity_matches_alert_payload():
    envelope = {
        "statusCode": 500,
        "data": '{"status":"error","error_type":"internal_error"}',
    }
    policy = run_policy(envelope, raw=True)["results"][0]
    python = build_alert({"status": "error", "error_type": "internal_error"})
    assert policy["notification_identity"] == python["alert_fingerprint"]


def test_control_center_rejects_tampered_or_missing_identity(monkeypatch):
    body = bridge_body(monkeypatch)
    tampered = copy.deepcopy(body)
    tampered["alert_identity"]["alert_fingerprint"] = "0" * 64
    missing = copy.deepcopy(body)
    missing.pop("alert_identity")
    for payload, reason in (
        (tampered, "alert_identity_mismatch"),
        (missing, "missing_alert_identity"),
    ):
        view = sc.from_payload(payload)
        assert (
            view.state == sc.INVALID_RESULT
            and not view.cells
            and reason in view.reasons
        )


# --- Identidad canónica en Python y JavaScript: mismos bytes --------------------------------


@needs_node
@pytest.mark.parametrize(
    "scores",
    [
        [1.0] * 50,
        [0.0] * 50,
        [3.2e-05, 1e-05] + [1e-07] * 48,
        [0.30000000000000004, 0.1583, 0.1] + [0.05] * 47,
    ],
    ids=["all_one", "all_zero", "tiny_exponents", "long_repr"],
)
def test_python_and_js_identity_agree_on_float_edge_cases(monkeypatch, scores):
    result = dataclasses.replace(synthetic_result(), cells=_cells(scores))
    body = bridge_body(monkeypatch, result)
    policy = run_policy(body)["results"][0]
    assert policy["alert_identity_verified"] is True
    assert policy["notification_identity"] == _fp(body)


# --- 25. Control Center contra un bridge HTTP local ----------------------------------------


def test_control_center_live_contract_over_http(monkeypatch):
    payload = json.dumps(bridge_body(monkeypatch)).encode("utf-8")

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        view = sc.fetch_live(f"http://127.0.0.1:{server.server_address[1]}/score")
    finally:
        server.shutdown()
    assert view.state == sc.LIVE_READY and len(view.cells) == 50
    assert [c.rank for c in view.top] == [1, 2, 3, 4, 5]
    assert (
        view.alert.fingerprint
        == json.loads(payload)["alert_identity"]["alert_fingerprint"]
    )


# --- 26. Fixtures de contrato para n8n (generados desde la salida real del bridge) ----------


def canonical_fixture(monkeypatch) -> dict:
    return bridge_body(monkeypatch)


def tampered_fixture(monkeypatch) -> dict:
    body = copy.deepcopy(canonical_fixture(monkeypatch))
    # rejilla todavía consistente (empate intacto), pero la identidad declarada ya
    # no corresponde al contenido
    body["cells"][0]["score"] = body["cells"][1]["score"] = 0.39
    return body


def test_n8n_fixtures_are_current_bridge_output(monkeypatch):
    expected = {
        "canonical-notification.json": canonical_fixture(monkeypatch),
        "tampered-identity.json": tampered_fixture(monkeypatch),
    }
    for name, body in expected.items():
        stored = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
        assert (
            stored == body
        ), f"{name} desactualizado: regenerar con tests/test_output_pipeline.py"


@needs_node
def test_n8n_fixtures_accepted_and_rejected():
    canonical = json.loads(
        (FIXTURES / "canonical-notification.json").read_text("utf-8")
    )
    tampered = json.loads((FIXTURES / "tampered-identity.json").read_text("utf-8"))
    ok, bad = run_policy(canonical, tampered)["results"]
    assert ok["category"] == "candidate" and ok["alert_identity_verified"] is True
    assert bad["category"] == "blocked" and bad["reason"] == "alert_identity_mismatch"


def write_fixtures() -> None:  # pragma: no cover - utilidad manual
    """python -c "import tests.test_output_pipeline as t; t.write_fixtures()"."""
    mp = pytest.MonkeyPatch()
    try:
        FIXTURES.mkdir(exist_ok=True)
        for name, body in (
            ("canonical-notification.json", canonical_fixture(mp)),
            ("tampered-identity.json", tampered_fixture(mp)),
        ):
            (FIXTURES / name).write_text(
                json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
    finally:
        mp.undo()


# --- Workflow n8n: sigue inactivo y embebe esta misma política -----------------------------


def test_workflow_embeds_current_policy_and_stays_inactive():
    import sys

    sys.path.insert(0, str(REPO / "ops" / "n8n"))
    try:
        import build_workflow
    finally:
        sys.path.pop(0)
    stored = json.loads(
        (REPO / "ops" / "n8n" / "controlled-preview.json").read_text("utf-8")
    )
    assert stored == build_workflow.build()
    assert stored["active"] is False
    text = json.dumps(stored).lower()
    assert "telegram" not in text and "scheduletrigger" not in text


# --- 21/22. Lenguaje científico y sin umbrales nuevos, en todas las salidas ----------------


def _all_output_texts(monkeypatch) -> list[str]:
    from app.components import ops_dashboard as ui
    from src.notifications.alert_payload import render_text

    body = bridge_body(monkeypatch)
    view = sc.from_payload(body)
    texts = [
        json.dumps(body, ensure_ascii=False),
        ui.render(view),
        render_text(build_alert(body)),
    ]
    if NODE:
        texts += [r["message"] for r in run_policy(body)["results"]]
    return texts


def test_output_language_is_relative_prioritization(monkeypatch):
    import re

    for text in _all_output_texts(monkeypatch):
        low = re.sub(r"<[^>]+>", " ", text).lower()
        for match in re.finditer(r"probabilidad calibrada", low):
            window = low[max(0, match.start() - 40) : match.start()]
            assert re.search(r"\bno\b|\bni\b|no es una|no corresponde", window), window
        for claim in (
            "incendio confirmado",
            "incendio detectado",
            "incendios detectados",
        ):
            assert claim not in low
        for tier in ("low", "medium", "high", "critical", "riesgo bajo", "riesgo alto"):
            assert not re.search(rf"\b{tier}\b", low), tier


def test_schema_versions_agree_between_bridge_and_control_center():
    from src.notifications.alert_payload import SCHEMA_VERSION

    assert sc.OUTPUT_SCHEMA_VERSION == OUTPUT_SCHEMA_VERSION
    assert sc.ALERT_SCHEMA_VERSION == SCHEMA_VERSION
    policy = POLICY.read_text(encoding="utf-8")
    assert f"'{OUTPUT_SCHEMA_VERSION}'" in policy and f"'{SCHEMA_VERSION}'" in policy

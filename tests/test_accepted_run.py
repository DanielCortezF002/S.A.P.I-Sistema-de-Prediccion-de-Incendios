"""Artefacto de corrida aceptada: captura segura, replay, equivalencia y matriz de fallos.

Todo es local: un stub HTTP en 127.0.0.1 hace de bridge con la salida REAL del
serializador del bridge para un GridScoreResult sintético. Sin datos reales,
sin servicios, sin envío.
"""

from __future__ import annotations

import copy
import dataclasses
import http.server
import json
import math
import socket
import threading
from pathlib import Path

import pytest
import requests

from app.components import ops_dashboard as ui
from app.utils import score_contract as sc
from src.output import accepted_run as ar
from test_output_pipeline import NODE, bridge_body, run_policy, synthetic_result

CAPTURED_AT = "2026-09-24T13:05:00+00:00"


def artifact(monkeypatch, body=None, **kwargs) -> dict:
    body = body or bridge_body(monkeypatch)
    opts = dict(
        data_origin=ar.DATA_SYNTHETIC,
        captured_at=CAPTURED_AT,
        source_url="http://127.0.0.1:8600/score",
        content_type="application/json",
    )
    opts.update(kwargs)
    return ar.build_artifact(body, **opts)


def refingerprint(doc: dict) -> dict:
    """Simula un atacante que recalcula el fingerprint tras alterar el contenido."""
    doc["artifact_fingerprint"] = ar.fingerprint(doc["stable"])
    doc["identities"]["artifact_fingerprint"] = doc["artifact_fingerprint"]
    return doc


# --- Stub HTTP local (solo GET) -----------------------------------------------------------


class _Stub:
    def __init__(self, status: int, body: bytes):
        calls: list = []
        self.calls = calls

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                calls.append(("GET", self.path, self.headers.get("Authorization")))
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/score"

    def stop(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def stub():
    started = []

    def start(status: int, payload) -> _Stub:
        raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        s = _Stub(status, raw)
        started.append(s)
        return s

    yield start
    for s in started:
        try:
            s.stop()
        except Exception:  # noqa: BLE001 -- ya detenido por el test
            pass


def capture_cli(url: str, out: Path, *extra: str, capsys=None) -> tuple[int, dict]:
    code = ar.main(["capture", "--url", url, "--out", str(out), *extra])
    printed = json.loads(capsys.readouterr().out) if capsys else {}
    return code, printed


# --- A. Artefacto e identidades -----------------------------------------------------------


def test_artifact_has_whitelisted_content_and_three_distinct_identities(monkeypatch):
    body = bridge_body(monkeypatch)
    body.update(
        NASA_FIRMS_API_KEY="SYNTH-SECRET",
        Authorization="Bearer SYNTH-SECRET",
        env={"DMC_TOKEN": "SYNTH-SECRET"},
        traceback="Traceback SYNTH-SECRET",
    )
    doc = artifact(monkeypatch, body)
    stable = doc["stable"]
    assert (
        doc["artifact_schema_version"]
        == stable["artifact_schema_version"]
        == ar.ARTIFACT_SCHEMA_VERSION
    )
    assert stable["canonical_output_schema_version"] == "sapi-output-v1"
    out = stable["output"]
    assert len(out["cells"]) == 50 and [c["rank"] for c in out["cells"]] == list(
        range(1, 51)
    )
    assert set(out["cells"][0]) == {
        "cell_id",
        "score",
        "rank",
        "display_rank",
        "tie_group_size",
        "geometry",
    }
    assert out["input_identity"]["dmc"]["manifest_sha256"] == "4" * 64
    text = json.dumps(doc)
    for leak in (
        "SYNTH-SECRET",
        "NASA_FIRMS_API_KEY",
        "Authorization",
        "DMC_TOKEN",
        "Traceback",
        "disclaimer",
        "historical_count",
    ):
        assert leak not in text, leak
    ids = doc["identities"]
    assert ids == {
        "inputs_fingerprint": body["inputs_fingerprint"],
        "notification_identity": body["alert_identity"]["alert_fingerprint"],
        "artifact_fingerprint": doc["artifact_fingerprint"],
    }
    assert len(set(ids.values())) == 3  # tres identidades con propósitos distintos


def test_same_result_captured_twice_has_same_stable_identity(monkeypatch):
    a = artifact(monkeypatch, captured_at="2026-09-24T13:05:00+00:00")
    b = artifact(
        monkeypatch,
        captured_at="2026-09-24T13:59:59+00:00",
        source_url="http://user:pw@127.0.0.1:8600/score?token=x",
    )
    assert a["artifact_fingerprint"] == b["artifact_fingerprint"]
    assert a["stable"] == b["stable"] and a["capture"] != b["capture"]
    assert (
        b["capture"]["source_url"] == "http://127.0.0.1:8600/score"
    )  # sin credenciales


def test_artifact_identity_changes_with_content_and_origin(monkeypatch):
    base = artifact(monkeypatch)["artifact_fingerprint"]
    cells = list(synthetic_result().cells)
    cells[40] = dataclasses.replace(
        cells[40], score=cells[40].score - 0.0001
    )  # fuera del Top 5
    other = artifact(
        monkeypatch, bridge_body(monkeypatch, synthetic_result(cells=cells))
    )
    assert other["artifact_fingerprint"] != base
    assert (
        other["identities"]["notification_identity"]
        == artifact(monkeypatch)["identities"]["notification_identity"]
    )  # la alerta no cambia
    operational = artifact(monkeypatch, data_origin=ar.DATA_OPERATIONAL)
    assert (
        operational["artifact_fingerprint"] != base
    )  # el origen está en el contenido estable


# --- B. Captura segura (solo GET) ------------------------------------------------------------


def test_capture_is_get_only_validated_and_idempotent(
    monkeypatch, stub, tmp_path, capsys
):
    body = bridge_body(monkeypatch)
    s = stub(200, body)
    code, printed = capture_cli(
        s.url, tmp_path / "evidence", "--synthetic", capsys=capsys
    )
    assert code == ar.EXIT_OK and printed["result"] == "CAPTURED"
    assert printed["write"] == "written" and printed["data_origin"] == "SYNTHETIC"
    assert s.calls == [("GET", "/score", None)]
    path = Path(printed["path"])
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert ar.verify_artifact(doc)[0] == []
    assert doc["capture"]["http_status"] == 200
    assert doc["capture"]["content_type"] == "application/json"
    first = path.read_bytes()
    code, again = capture_cli(
        s.url, tmp_path / "evidence", "--synthetic", capsys=capsys
    )
    assert code == ar.EXIT_OK and again["write"] == "already_captured"
    assert path.read_bytes() == first  # la primera captura se conserva intacta


@pytest.mark.parametrize(
    "target", ["data/raw/x", "data/processed", "models", "versions", "with_current"]
)
def test_capture_refuses_operational_directories_before_any_request(
    monkeypatch, stub, tmp_path, capsys, target
):
    s = stub(200, bridge_body(monkeypatch))
    if target == "versions":
        out = tmp_path / "firms" / "versions"
    elif target == "with_current":
        (tmp_path / "store").mkdir()
        (tmp_path / "store" / "CURRENT.json").write_text("{}")
        out = tmp_path / "store" / "evidence"
    else:
        out = ar.REPO_ROOT / target
    code, printed = capture_cli(s.url, out, capsys=capsys)
    assert code == ar.EXIT_USAGE and printed["result"] == "REFUSED"
    assert s.calls == []  # ni siquiera se consultó el servicio


@pytest.mark.parametrize(
    "error_type", ["data_unavailable", "prototype_unavailable", "internal_error"]
)
def test_unavailable_results_produce_no_artifact(stub, tmp_path, capsys, error_type):
    s = stub(
        503 if error_type != "internal_error" else 500,
        {"status": "error", "error_type": error_type, "message": "SYNTH-SECRET"},
    )
    code, printed = capture_cli(s.url, tmp_path, capsys=capsys)
    assert code == ar.EXIT_NOT_ACCEPTED and printed["reasons"] == [error_type]
    assert not list(tmp_path.iterdir()) and "SYNTH-SECRET" not in json.dumps(printed)


def test_network_failure_produces_no_artifact_and_live_never_falls_back(
    tmp_path, capsys
):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        dead = f"http://127.0.0.1:{sock.getsockname()[1]}/score"
    code, printed = capture_cli(dead, tmp_path, capsys=capsys)
    assert code == ar.EXIT_NETWORK and printed["result"] == "NOT_CAPTURED"
    assert not list(tmp_path.iterdir())
    view = sc.fetch_live(dead)
    assert (
        view.state == sc.NETWORK_ERROR and not view.cells and view.mode == sc.MODE_LIVE
    )
    assert "DATOS DEMOSTRATIVOS" not in ui.render(view)


# --- C/D. Replay y equivalencia con en vivo ------------------------------------------------


def _presentation(view: sc.DashboardView) -> dict:
    return {
        "cells": [
            (c.rank, c.display_rank, c.tie_group_size, c.cell_id, c.score)
            for c in view.cells
        ],
        "top": [(c.rank, c.cell_id, c.score) for c in view.top],
        "firms": dict(view.firms),
        "scoring_time": view.scoring_time,
        "inputs_fingerprint": view.inputs_fingerprint,
        "notification_identity": view.alert.fingerprint,
        "alert_text": view.alert.text,
        "alert_top": view.alert.top,
        "model": (view.model_version, view.model_status),
        "identity": dict(view.identity),
    }


def test_replay_matches_live_presentation_offline(monkeypatch, tmp_path):
    body = bridge_body(monkeypatch)
    live = sc.from_payload(body)
    doc = artifact(monkeypatch, body)
    path, _ = ar.write_artifact(doc, tmp_path)

    def no_network(*a, **k):
        raise AssertionError("el replay intentó usar la red")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    replay = ar.load_replay(path)
    assert replay.state == sc.REPLAY_READY and replay.mode == sc.MODE_REPLAY
    assert _presentation(replay) == _presentation(live)
    assert replay.artifact_fingerprint == doc["artifact_fingerprint"]
    assert replay.captured_at == CAPTURED_AT and replay.connection is None

    html = ui.render(replay)
    assert "MODO: REPLAY" in html and "REPLAY · CORRIDA ACEPTADA" in html
    assert "MODO: EN VIVO" not in html and "MODO: DEMO" not in html
    assert "SYNTHETIC" in html  # artefacto de datos sintéticos, siempre rotulado
    assert 'data-time="captured"' in html and 'data-time="scoring"' in html
    assert f'data-artifact="{doc["artifact_fingerprint"]}"' in html
    assert html.count("<title>Celda VP-") == 50 and html.count('<td class="num">') == 50
    assert "no corresponde a una probabilidad calibrada" in html.lower()
    tech = ui.technical_details(replay)
    assert f'{doc["artifact_fingerprint"][:12]}…' in tech
    assert ("Artifact fingerprint", doc["artifact_fingerprint"]) in ui.full_hashes(
        replay
    )


def test_operational_replay_has_no_synthetic_banner(monkeypatch, tmp_path):
    doc = artifact(monkeypatch, data_origin=ar.DATA_OPERATIONAL)
    path, _ = ar.write_artifact(doc, tmp_path)
    html = ui.render(ar.load_replay(path))
    assert "MODO: REPLAY" in html and ">SYNTHETIC<" not in html


# --- F. Integración sintética completa ------------------------------------------------------


def test_full_synthetic_output_e2e(monkeypatch, stub, tmp_path, capsys):
    body = bridge_body(
        monkeypatch
    )  # GridScoreResult sintético → serializador del bridge
    s = stub(200, body)

    live = sc.fetch_live(s.url)  # Control Center EN VIVO contra el stub local
    assert live.state == sc.LIVE_READY
    fp = body["alert_identity"]["alert_fingerprint"]
    assert live.alert.fingerprint == fp
    if NODE:  # política n8n: verifica la misma identidad (sin workflow, sin envío)
        policy = run_policy(body)["results"][0]
        assert (
            policy["alert_identity_verified"] and policy["notification_identity"] == fp
        )
        assert policy["delivery"] == "NOT_SENT"

    code, printed = capture_cli(s.url, tmp_path / "ev", "--synthetic", capsys=capsys)
    assert code == ar.EXIT_OK
    s.stop()  # sin servicio: el replay no lo necesita
    with pytest.raises(requests.RequestException):
        requests.get(s.url, timeout=1)

    replay = ar.load_replay(printed["path"])
    assert replay.state == sc.REPLAY_READY
    assert _presentation(replay) == _presentation(live)
    assert printed["notification_identity"] == fp
    assert printed["inputs_fingerprint"] == body["inputs_fingerprint"]

    # la misma corrida capturada de nuevo (servicio levantado otra vez) → misma identidad
    s2 = stub(200, body)
    code, again = capture_cli(s2.url, tmp_path / "ev2", "--synthetic", capsys=capsys)
    assert again["artifact_fingerprint"] == printed["artifact_fingerprint"]


# --- G. Matriz de manipulación y fallos -------------------------------------------------------


def _mutate_output(mutation):
    def apply(doc):
        mutation(doc["stable"]["output"])
        return doc

    return apply


def _cells(fn):
    return _mutate_output(lambda o: fn(o["cells"]))


TAMPER = {
    "49_cells": _cells(lambda c: c.pop()),
    "duplicate_cell": _cells(
        lambda c: c[1].update(cell_id=c[0]["cell_id"], geometry=c[0]["geometry"])
    ),
    "duplicate_rank": _cells(lambda c: c[1].update(rank=1)),
    "rank_gap": _cells(lambda c: c[4].update(rank=51)),
    "missing_fingerprint": _mutate_output(lambda o: o.pop("inputs_fingerprint")),
    "wrong_notification_identity": _mutate_output(
        lambda o: o["alert_identity"].update(alert_fingerprint="0" * 64)
    ),
    "geometry_mismatch": _cells(lambda c: c[0]["geometry"].update(min_lon=-70.0)),
    "secret_identity_metadata": _mutate_output(
        lambda o: o["input_identity"]["dmc"].update(
            pointer_version="Authorization: Bearer x"
        )
    ),
    "demo_marker": _mutate_output(lambda o: o.update(_synthetic="DEMO")),
    "unknown_output_field": _mutate_output(lambda o: o.update(cookies="session=x")),
    "bad_origin": lambda d: d["stable"].update(data_origin="LIVE"),
}


@pytest.mark.parametrize("name", sorted(TAMPER))
@pytest.mark.parametrize("attacker_refingerprints", [False, True])
def test_tampered_artifact_is_rejected(monkeypatch, name, attacker_refingerprints):
    doc = copy.deepcopy(artifact(monkeypatch))
    TAMPER[name](doc)
    if attacker_refingerprints:
        refingerprint(doc)
    reasons, view = ar.verify_artifact(doc)
    assert reasons and view is None
    if not attacker_refingerprints:
        assert "artifact_fingerprint_mismatch" in reasons


def test_consistent_edit_with_recomputed_fingerprint_needs_the_capture_anchor(
    monkeypatch, tmp_path, capsys
):
    """Límite honesto: un fingerprint auto-referente no prueba autenticidad. Editar un
    score fuera del Top 5 y recalcular el fingerprint da OTRO artefacto válido en sí
    mismo; el ancla es el fingerprint registrado en la captura."""
    original = artifact(monkeypatch)
    edited = copy.deepcopy(original)
    cell = edited["stable"]["output"]["cells"][20]
    cell["score"] = cell["score"] - 0.0001  # orden y empates siguen consistentes
    refingerprint(edited)
    assert ar.verify_artifact(edited)[0] == []  # íntegro en sí mismo…
    assert (
        edited["artifact_fingerprint"] != original["artifact_fingerprint"]
    )  # …pero otro
    reasons, view = ar.verify_artifact(
        edited, expected_fingerprint=original["artifact_fingerprint"]
    )
    assert "artifact_fingerprint_not_expected" in reasons and view is None

    path = tmp_path / "edited.json"
    path.write_text(json.dumps(edited), encoding="utf-8")
    anchor = ["--expect-fingerprint", original["artifact_fingerprint"]]
    assert ar.main(["verify", str(path), *anchor]) == ar.EXIT_NOT_ACCEPTED
    assert ar.main(["verify", str(path)]) == ar.EXIT_OK
    capsys.readouterr()

    from app import control_center as launcher

    code = launcher.main(["--replay", str(path), *anchor, "--no-browser"])
    assert code == 3  # el lanzador no inicia un replay que no calza con el ancla


@pytest.mark.parametrize(
    "tamper,reason",
    [
        (
            lambda d: d.update(artifact_fingerprint="f" * 64),
            "artifact_fingerprint_mismatch",
        ),
        (
            lambda d: d.update(artifact_fingerprint="xyz"),
            "artifact_fingerprint_missing",
        ),
        (
            lambda d: d["identities"].update(notification_identity="0" * 64),
            "identities_mismatch",
        ),
        (
            lambda d: d["capture"].update(source_url="http://u:p@host/score?k=v"),
            "capture_url_unsafe",
        ),
        (
            lambda d: d["capture"].update(env={"DMC_TOKEN": "x"}),
            "capture_metadata_invalid",
        ),
        (
            lambda d: d.update(artifact_schema_version="sapi-accepted-run-v0"),
            "artifact_schema_version_mismatch",
        ),
        (lambda d: d.update(headers={"Authorization": "x"}), "artifact_unknown_field"),
    ],
    ids=[
        "fingerprint_changed",
        "fingerprint_malformed",
        "identities_changed",
        "url_secret",
        "capture_extra",
        "schema",
        "extra_top_level",
    ],
)
def test_artifact_envelope_tampering_is_rejected(monkeypatch, tamper, reason):
    doc = copy.deepcopy(artifact(monkeypatch))
    tamper(doc)
    reasons, view = ar.verify_artifact(doc)
    assert reason in reasons and view is None


@pytest.mark.parametrize(
    "mutate",
    [
        lambda b: b["cells"].pop(),
        lambda b: b["cells"][1].update(
            cell_id=b["cells"][0]["cell_id"], geometry=b["cells"][0]["geometry"]
        ),
        lambda b: b["cells"][1].update(rank=1),
        lambda b: b["cells"][4].update(rank=51),
        lambda b: b["cells"][3].update(score=math.nan),
        lambda b: b["cells"][3].update(score=math.inf),
        lambda b: b.pop("inputs_fingerprint"),
        lambda b: b["alert_identity"].update(alert_fingerprint="0" * 64),
        lambda b: b.update(_synthetic="DEMO"),
        lambda b: b["cells"][0]["geometry"].update(min_lon=-70.0),
        lambda b: b["input_identity"]["model"].update(name="Bearer SYNTH-SECRET"),
    ],
    ids=[
        "49_cells",
        "duplicate_cell",
        "duplicate_rank",
        "rank_gap",
        "nan",
        "infinity",
        "missing_fingerprint",
        "wrong_notification_identity",
        "demo_marker",
        "geometry_mismatch",
        "secret_identity_metadata",
    ],
)
def test_live_capture_rejects_invalid_responses(
    monkeypatch, stub, tmp_path, capsys, mutate
):
    body = copy.deepcopy(bridge_body(monkeypatch))
    mutate(body)
    s = stub(200, json.dumps(body).encode())  # NaN/Infinity viajan como tokens JSON
    code, printed = capture_cli(s.url, tmp_path, capsys=capsys)
    assert code == ar.EXIT_NOT_ACCEPTED and printed["result"] == "NOT_ACCEPTED"
    assert not list(tmp_path.iterdir())  # ningún artefacto aceptado
    assert "SYNTH-SECRET" not in json.dumps(printed)


def test_unreadable_or_missing_artifact_is_invalid_replay(tmp_path):
    bad = tmp_path / "broken.json"
    bad.write_text("{not json")
    for path in (bad, tmp_path / "missing.json"):
        view = ar.load_replay(path)
        assert view.state == sc.INVALID_RESULT and view.mode == sc.MODE_REPLAY
        assert not view.cells and "RESULTADO INVÁLIDO" in ui.render(view)


# --- I. Paquete de evidencia -------------------------------------------------------------------


def test_evidence_pack_is_compact_deterministic_and_labeled(
    monkeypatch, tmp_path, capsys
):
    doc = artifact(monkeypatch)
    path, _ = ar.write_artifact(doc, tmp_path / "runs")
    for out in ("a", "b"):
        assert (
            ar.main(["evidence", str(path), "--out", str(tmp_path / out)]) == ar.EXIT_OK
        )
    capsys.readouterr()
    folder_a = tmp_path / "a" / f"evidence_{doc['artifact_fingerprint'][:12]}"
    folder_b = tmp_path / "b" / folder_a.name
    names = sorted(p.name for p in folder_a.iterdir())
    assert names == ["artifact_fingerprint.txt", "summary.json", "summary.md"]
    for name in names:
        assert (folder_a / name).read_bytes() == (folder_b / name).read_bytes()
    summary = json.loads((folder_a / "summary.json").read_text(encoding="utf-8"))
    assert summary["evidence_kind"] == "ACCEPTED RUN (LIVE CAPTURE)"
    assert summary["data_origin"] == "SYNTHETIC" and summary["synthetic_banner"]
    assert [c["rank"] for c in summary["top5"]] == [1, 2, 3, 4, 5]
    md = (folder_a / "summary.md").read_text(encoding="utf-8")
    assert md.startswith("> **SYNTHETIC") and "probabilidad calibrada" in md
    assert sum(p.stat().st_size for p in folder_a.iterdir()) < 20_000  # compacto


def test_evidence_refuses_tampered_artifact(monkeypatch, tmp_path, capsys):
    doc = copy.deepcopy(artifact(monkeypatch))
    doc["stable"]["output"]["cells"][0]["score"] = 0.99
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(doc))
    assert (
        ar.main(["evidence", str(path), "--out", str(tmp_path / "e")])
        == ar.EXIT_NOT_ACCEPTED
    )
    assert not (tmp_path / "e").exists()

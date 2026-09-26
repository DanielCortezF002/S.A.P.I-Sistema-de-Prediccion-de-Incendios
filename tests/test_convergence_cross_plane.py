"""RC1 convergence: cross-plane contract, determinism, Attempt2 state machine, failure matrix.

SYNTHETIC only: temp stores (tests/test_scoring_inputs.env), real Model D, no network,
no real workspace/CURRENT/writers. The Data manifest step uses the Operations consumer's
existing synthetic flat contract because the reserved Data->Operations adapter has not
landed; the real Data manifest handshake is test_convergence_data_adapter_contract.py.
"""

from __future__ import annotations

import copy
import dataclasses
import json
import math
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import tools.n8n_bridge.app as bridge_app
from app.utils import score_contract as sc
from src.convergence import output_acceptance as oa
from src.geo.grid import all_cells
from src.inference import prototype_service as svc
from src.ops.attempt2_operator.output_plane_manifest import (
    compute_output_manifest_fingerprint,
)
from src.ops.attempt2_operator.data_plane_manifest import (
    compute_data_manifest_fingerprint,
)
from src.ops.attempt2_operator.operator import Attempt2Operator
from src.ops.attempt2_operator.states import Attempt2State
from src.output import accepted_run as ar
from src.output import readiness as rd
from test_convergence_output_acceptance import REAL_OUTPUT_FP, REAL_OUTPUT_MANIFEST
from test_scoring_inputs import env, publish_firms  # noqa: F401 (fixture reuse)

REPO = Path(__file__).resolve().parents[1]
MODEL_SHA = "ac017bef1f42a30ac74ba3e3787368c4418798b2d562adcfba01c923cff2173f"
EXPECTED_IDS = {c["cell_id"] for c in all_cells()}
RUN_ID = "SAPI-ATTEMPT2-CONVERGENCE-SYNTHETIC"


@pytest.fixture
def scored(env, monkeypatch):  # noqa: F811
    """Real Model D over a synthetic FIRMS publication → canonical bridge body."""
    pointer = publish_firms(env, detections=3)
    inputs = svc.capture_scoring_inputs()
    result = svc.score_current_grid(inputs=inputs)
    monkeypatch.setattr(bridge_app, "score_current_grid", lambda: result)
    monkeypatch.setattr(bridge_app, "_read_metadata_json", lambda: None)
    resp = TestClient(bridge_app.app).get("/score")
    assert resp.status_code == 200, resp.text
    return result, inputs, pointer, resp.json()


def _artifact(body: dict) -> dict:
    return ar.build_artifact(
        body,
        data_origin=ar.DATA_SYNTHETIC,
        captured_at="2026-09-25T12:00:00+00:00",
        source_url="http://127.0.0.1:8600/score",
    )


def _plane(tmp_path: Path) -> tuple[Path, str]:
    if REAL_OUTPUT_MANIFEST.is_file():
        return REAL_OUTPUT_MANIFEST, REAL_OUTPUT_FP
    manifest = rd.build_manifest(rd.run_checks())
    if manifest["readiness"]["status"] != rd.READY:
        pytest.skip("no real Output manifest and generated plane is not READY")
    path = tmp_path / "OUTPUT_PLANE_MANIFEST.json"
    path.write_text(json.dumps(manifest, ensure_ascii=True), encoding="utf-8")
    return path, manifest["manifest_fingerprint"]


# --- Phase 11: 50-cell contract end to end ------------------------------------------------------


def test_fifty_cell_contract_through_integrated_candidate(scored):
    result, inputs, pointer, body = scored
    cells = body["cells"]
    assert len(cells) == 50 and {c["cell_id"] for c in cells} == EXPECTED_IDS
    ranks = [c["rank"] for c in cells]
    assert sorted(ranks) == list(range(1, 51))
    assert all(
        isinstance(c["score"], float) and math.isfinite(c["score"]) for c in cells
    )
    by_rank = sorted(cells, key=lambda c: c["rank"])
    assert all(a["score"] >= b["score"] for a, b in zip(by_rank, by_rank[1:]))
    scores = [c["score"] for c in cells]
    assert all(
        c["display_rank"] == 1 + sum(s > c["score"] for s in scores) for c in cells
    )
    assert body["inputs_fingerprint"] == inputs.fingerprint == result.inputs_fingerprint
    for key in ("firms_origin", "firms_coverage_end", "firms_lag_days", "firms_status"):
        assert body[key] is not None
    identity = body["input_identity"]
    assert identity["firms"]["sha256"] == pointer["sha256"]
    assert (
        identity["dmc"]["manifest_sha256"] and identity["model"]["sha256"] == MODEL_SHA
    )
    first, second = _artifact(body), _artifact(copy.deepcopy(body))
    assert first == second  # deterministic, including notification identity


# --- Phase 12: replay determinism stress --------------------------------------------------------

_PROBE = r"""
import json, random, sys
from pathlib import Path
from src.output import accepted_run as ar
from src.output import readiness as rd
body = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
rng = random.Random(int(sys.argv[2]))
def shuffle(o):
    if isinstance(o, dict):
        items = list(o.items()); rng.shuffle(items)
        return {k: shuffle(v) for k, v in items}
    return [shuffle(v) for v in o] if isinstance(o, list) else o
body = shuffle(body)
rng.shuffle(body["cells"])  # enumeration order must not matter
doc = ar.build_artifact(body, data_origin="SYNTHETIC", captured_at=sys.argv[3],
                        source_url="http://127.0.0.1:8600/score")
out = Path(sys.argv[4]); out.mkdir(parents=True, exist_ok=True)
path, _ = ar.write_artifact(doc, out)
view = ar.load_replay(path, doc["artifact_fingerprint"])
print(json.dumps({"artifact": doc["artifact_fingerprint"],
                  "notification": view.alert.fingerprint,
                  "ranking": [(c.rank, c.cell_id, c.score) for c in view.cells],
                  "state": view.state, "sources": rd.sources_sha256()}))
"""


def test_replay_determinism_across_processes_paths_seeds_and_ordering(scored, tmp_path):
    body = scored[3]
    src = tmp_path / "body.json"
    src.write_text(json.dumps(body), encoding="utf-8")
    outputs = []
    for seed, folder, captured in (
        ("0", "a", "2026-09-25T12:00:00+00:00"),
        ("1", "dir with spaces/b", "2026-09-25T18:30:00+00:00"),
        ("4242", "c/deeper path/c", "2026-09-26T01:02:03+00:00"),
    ):
        env_vars = {**os.environ, "PYTHONHASHSEED": seed, "PYTHONIOENCODING": "utf-8"}
        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                _PROBE,
                str(src),
                seed,
                captured,
                str(tmp_path / folder),
            ],
            cwd=REPO,
            env=env_vars,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
            timeout=300,
        )
        outputs.append(json.loads(proc.stdout))
    assert all(o["state"] == "REPLAY_READY" for o in outputs)
    for key in ("artifact", "notification", "ranking", "sources"):
        assert len({json.dumps(o[key]) for o in outputs}) == 1, key
    assert outputs[0]["artifact"] == _artifact(body)["artifact_fingerprint"]


# --- Phase 17: Attempt2 synthetic state machine with real cross-plane content -----------------


def _flat_synthetic_data_manifest(tmp_path: Path) -> Path:
    """The Operations consumer's EXISTING synthetic contract (pre-adapter; not the real one)."""
    data = {
        "schema_version": 1,
        "readiness_status": "READY",
        "firms_component_sha": "a" * 40,
        "dmc_component_sha": "b" * 40,
        "model_sha": MODEL_SHA,
        "topography_identity": "synthetic-topography",
        "baseline_identity": "synthetic-baseline",
        "expected_current_state": {"firms": "ABSENT", "dmc": "ABSENT"},
    }
    data["manifest_fingerprint"] = compute_data_manifest_fingerprint(data)
    path = tmp_path / "DATA-PLANE-MANIFEST.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_attempt2_state_machine_reaches_accepted_with_real_output_acceptance(
    scored, tmp_path
):
    result, inputs, pointer, body = scored
    code_sha, tree_sha = "c" * 40, "d" * 40
    plane_path, plane_fp = _plane(tmp_path)
    run_path, _ = ar.write_artifact(_artifact(body), tmp_path / "runs")
    record = oa.build_acceptance_record(
        plane_path, run_path, expected_output_fingerprint=plane_fp, run_id=RUN_ID
    )
    record_path, _ = oa.write_record(record, tmp_path / "acceptance")

    run_id = RUN_ID
    op = Attempt2Operator.init_run(
        evidence_root=tmp_path / "evidence",
        dry_run=True,
        run_id=run_id,
        synthetic_identity={"code_sha": code_sha, "tree_sha": tree_sha},
        expected_code_sha=code_sha,
        data_plane_manifest=_flat_synthetic_data_manifest(tmp_path),
    )
    states = [op.run.current_state()]

    def step(fn, *a, **k):
        out = fn(*a, **k)
        states.append(op.run.current_state())
        return out

    snapshot = {
        "schema_version": 2,
        "run_id": run_id,
        "expected_code_sha": code_sha,
        "observed_code_sha": code_sha,
        "tree_sha": tree_sha,
        "dirty": False,
        "code": {
            "head_sha": code_sha,
            "tree_sha": tree_sha,
            "worktree_clean": True,
            "observed_at": "2026-09-25T15:00:00Z",
        },
        "firms": {"current": {"state": "ABSENT", "known": True, "present": False}},
        "dmc": {"current": {"state": "ABSENT", "known": True, "present": False}},
        "firms_current_state": "ABSENT",
        "dmc_current_state": "ABSENT",
        "artifacts": {"overall_status": "PASS"},
        "credentials": {"credentials": []},
        "workspace_safety": {"status": "PASS", "overall_status": "PASS"},
        "workspace_manifest": {"status": "PASS", "fingerprint": "w" * 64},
        "data_plane": {"status": "PASS", "ready": True},
        "quiescence": {
            "status": "QUIESCENT",
            "n8n": {"status": "STOPPED"},
            "writers": {"active_writers": []},
            "locks": {"active_locks": []},
            "telegram": {"armed": False},
        },
        "runtime": {"docker": {"status": "AVAILABLE"}},
        "warnings": [],
        "failures": [],
        "overall_status": "PASS",
        "attempt1": {"preserve": True},
        "policy": {"human_authorization": False},
    }
    assert step(op.preflight, snapshot=snapshot)["ready_for_authorization"] is True
    step(op.advance)
    assert op.next_action()["gate"] == "ATTEMPT2_AUTHORIZATION"
    step(op.authorize, "ATTEMPT2_AUTHORIZATION", actor="convergence-synthetic")
    step(op.advance)
    step(op.authorize, "FIRMS_WRITER_AUTHORIZATION", actor="convergence-synthetic")
    common = {
        "run_id": run_id,
        "code_sha": code_sha,
        "exit_code": 0,
        "stderr": "",
        "started_at": "2026-09-25T15:10:00Z",
        "finished_at": "2026-09-25T15:11:00Z",
        "sanitization_status": "PASS",
    }
    assert (
        step(
            op.import_result,
            "firms",
            {
                **common,
                "step": "firms",
                "stdout": "synthetic FIRMS publication",
                "operation_success": True,
                "firms_current_after": {"present": True, "state": "PRESENT"},
                "files_added": [pointer["relative_path"]],
            },
        )["result"]
        == "PASS"
    )
    step(op.advance)
    step(op.authorize, "DMC_WRITER_AUTHORIZATION", actor="convergence-synthetic")
    assert (
        step(
            op.import_result,
            "dmc",
            {
                **common,
                "step": "dmc",
                "quality_ok": True,
                "pointer_ok": True,
                "dmc_current_after": {"present": True},
                "attempt1_modified": False,
                "stdout": "synthetic DMC",
                "files_added": [],
            },
        )["result"]
        == "PASS"
    )
    step(op.advance)
    assert (
        step(
            op.import_result,
            "scoring",
            {
                **common,
                "step": "scoring",
                "cells": body["cells"],
                "inputs_fingerprint": inputs.fingerprint,
                "model_sha": body["input_identity"]["model"]["sha256"],
                "stdout": "real Model D over synthetic stores",
            },
        )["result"]
        == "PASS"
    )
    step(op.advance)
    assert (
        step(
            op.import_result,
            "bridge",
            {
                **common,
                "step": "bridge",
                "http_status": 200,
                "body": body,
                "stdout": "GET /score 200",
            },
        )["result"]
        == "PASS"
    )
    assert oa.verify_run_binding(record_path, op.run.root) == []
    assert op.accept_output_manifest(record_path)["status"] == "PASS"
    assert oa.verify_run_binding(record_path, op.run.root) == []
    states.append(op.run.current_state())
    step(op.advance)
    assert (
        step(
            op.import_result,
            "n8n",
            {
                **common,
                "step": "n8n",
                "schedule_enabled": False,
                "telegram_sent": False,
                "score_path_ok": True,
                "fail_closed_cases": {
                    "prototype_unavailable": True,
                    "data_unavailable": True,
                    "internal_error": True,
                },
            },
        )["result"]
        == "PASS"
    )
    step(op.advance)
    step(op.advance)
    names = [s.value if hasattr(s, "value") else str(s) for s in states]
    assert (
        names[0] == Attempt2State.NEW.value
        and names[-1] == Attempt2State.ACCEPTED.value
    )
    final = op.status()
    assert final["acceptance"]["software_operational"] is True
    assert final["acceptance"]["scientific_model_validation"] is False
    ctx = json.loads(
        (op.run.root / "identity" / "rc1_execution_context.json").read_text("utf-8")
    )
    assert ctx["output_plane_manifest_fingerprint"] == record["manifest_fingerprint"]
    (tmp_path / "transitions.json").write_text(json.dumps(names), encoding="utf-8")
    print("TRANSITIONS", json.dumps(names))


# --- Phase 18: convergence failure matrix --------------------------------------------------------


# The real Data manifest handshake lives in test_convergence_data_adapter_contract.py.


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("run_id", "OTHER-RUN", "wrong_run"),
        ("step", "dmc", "wrong_step"),
        ("code_sha", "e" * 40, "stale_or_wrong_sha"),
    ],
)
def test_cross_plane_run_binding_mismatch_rejected(tmp_path, field, value, reason):
    op = Attempt2Operator.init_run(
        evidence_root=tmp_path / "ev",
        dry_run=True,
        run_id="R1",
        synthetic_identity={"code_sha": "c" * 40, "tree_sha": "d" * 40},
        expected_code_sha="c" * 40,
    )
    payload = {"run_id": "R1", "step": "bridge", "code_sha": "c" * 40, field: value}
    with pytest.raises(RuntimeError, match=reason):
        op._enforce_import_binding("bridge", payload)


def test_bridge_output_disagreement_rejected(scored, tmp_path):
    body = scored[3]
    plane_path, plane_fp = _plane(tmp_path)
    run_path, _ = ar.write_artifact(_artifact(body), tmp_path / "runs")
    record = oa.build_acceptance_record(
        plane_path, run_path, expected_output_fingerprint=plane_fp, run_id=RUN_ID
    )
    bad = dict(
        record, notification_identity="f" * 64
    )  # identity of another bridge result
    bad["manifest_fingerprint"] = compute_output_manifest_fingerprint(
        bad
    )  # attacker re-signs
    path, _ = oa.write_record(bad, tmp_path / "bad")
    assert oa.verify_acceptance_record(
        path, output_manifest_path=plane_path, expected_output_fingerprint=plane_fp
    )


def test_model_identity_and_scoring_inputs_mismatch_rejected(scored, monkeypatch):
    result = scored[0]
    manifest = copy.deepcopy(result.scoring_inputs)
    manifest["model"]["sha256"] = (
        "0" * 64
    )  # model identity no longer matches the fingerprint
    tampered = dataclasses.replace(result, scoring_inputs=manifest)
    monkeypatch.setattr(bridge_app, "score_current_grid", lambda: tampered)
    resp = TestClient(bridge_app.app).get("/score")
    assert resp.status_code == 500 and "cells" not in resp.json()


def test_fifty_cell_violation_never_becomes_an_accepted_run(scored, monkeypatch):
    result = scored[0]
    short = dataclasses.replace(result, cells=result.cells[:49])
    monkeypatch.setattr(bridge_app, "score_current_grid", lambda: short)
    resp = TestClient(bridge_app.app).get("/score")
    assert resp.status_code == 500
    with pytest.raises(ar.ArtifactError):
        ar.build_artifact(
            resp.json(),
            data_origin=ar.DATA_SYNTHETIC,
            captured_at="2026-09-25T12:00:00+00:00",
            source_url="http://127.0.0.1:8600/score",
        )


def test_unknown_current_never_becomes_pass(tmp_path):
    op = Attempt2Operator.init_run(
        evidence_root=tmp_path / "ev",
        dry_run=True,
        run_id="R2",
        synthetic_identity={"code_sha": "c" * 40, "tree_sha": "d" * 40},
        expected_code_sha="c" * 40,
    )
    snapshot = {
        "schema_version": 2,
        "run_id": "R2",
        "expected_code_sha": "c" * 40,
        "firms": {"current": {"state": "UNKNOWN"}},
        "dmc": {"current": {"state": "ABSENT"}},
        "overall_status": "PASS",
    }
    assert op.preflight(snapshot=snapshot)["ready_for_authorization"] is False
    assert op.run.current_state() != Attempt2State.PREFLIGHT_READY


def test_live_replay_view_mismatch_rejected(scored, tmp_path):
    body = scored[3]
    doc = _artifact(body)
    edited = copy.deepcopy(doc)
    edited["stable"]["output"]["cells"][40]["score"] -= 0.0001
    edited["artifact_fingerprint"] = ar.fingerprint(edited["stable"])
    edited["identities"]["artifact_fingerprint"] = edited["artifact_fingerprint"]
    reasons, view = ar.verify_artifact(
        edited, expected_fingerprint=doc["artifact_fingerprint"]
    )
    assert "artifact_fingerprint_not_expected" in reasons and view is None
    live = sc.from_payload(body)
    assert live.state == sc.LIVE_READY

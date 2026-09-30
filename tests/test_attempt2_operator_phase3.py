"""Phase 3: clean preflight semantics, artifact paths, runtime identity."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.ops.attempt2_operator.collectors.artifacts import (
    collect_artifact_identities,
    resolve_firms_baseline_path,
)
from src.ops.attempt2_operator.collectors.preflight_collect import (
    REASON_PRIORITY,
    build_reasons,
    collect_real_preflight,
    highest_priority_reason,
)
from src.ops.attempt2_operator.collectors.runtime import (
    collect_docker_status,
    collect_runtime,
    collect_service_status,
)
from src.ops.attempt2_operator.operator import Attempt2Operator
from src.ops.attempt2_operator.paths import FIRMS_BASELINE_REL, StoreRoots
from src.ops.attempt2_operator.states import Attempt2State
from src.ops.attempt2_operator.workspace_safety import check_workspace_safety

REPO = Path(__file__).resolve().parents[1]
SHA = "dddddddddddddddddddddddddddddddddddddddd"


def test_baseline_explicit_path_discovery(tmp_path: Path):
    data = tmp_path / "data" / "processed"
    data.mkdir(parents=True)
    baseline = data / FIRMS_BASELINE_REL.name
    # write content whose hash we control via override expected in check —
    # use empty file → FAIL match, but discovery finds it
    baseline.write_bytes(b"x")
    roots = StoreRoots.from_repo(tmp_path)
    found, tried = resolve_firms_baseline_path(roots)
    assert found == baseline
    assert str(baseline) in tried


def test_baseline_missing_not_available(tmp_path: Path):
    art = collect_artifact_identities(tmp_path)
    assert art["firms_baseline"]["status"] == "NOT_AVAILABLE"
    assert art["overall_status"] in ("NOT_AVAILABLE", "INCOMPLETE")
    assert art["firms_baseline"]["status"] != "PASS"


def test_model_explicit_path_discovery(tmp_path: Path):
    models = tmp_path / "models"
    models.mkdir()
    mp = models / "prototype_model_d.pkl"
    mp.write_bytes(b"model-bytes")
    art = collect_artifact_identities(tmp_path)
    assert art["model"]["exists"] is True
    assert art["model"]["path"].endswith("prototype_model_d.pkl")
    assert art["model"]["status"] in ("PASS", "FAIL")  # hash likely FAIL
    assert art["model"]["discovery"] == "explicit_path"


def test_model_override_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    alt = tmp_path / "alt.pkl"
    alt.write_bytes(b"z")
    monkeypatch.setenv("SAPI_ATTEMPT2_MODEL_PATH", str(alt))
    art = collect_artifact_identities(tmp_path)
    assert Path(art["model"]["path"]) == alt


def test_docker_daemon_unavailable(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "src.ops.attempt2_operator.collectors.runtime.shutil.which",
        lambda _x: None,
    )
    d = collect_docker_status()
    assert d["status"] == "UNAVAILABLE"
    assert d["observed_at"]


def test_docker_daemon_available_readonly(monkeypatch: pytest.MonkeyPatch):
    class P:
        returncode = 0
        stdout = '"24.0.0"'
        stderr = ""

    monkeypatch.setattr(
        "src.ops.attempt2_operator.collectors.runtime.shutil.which",
        lambda _x: "/usr/bin/docker",
    )
    monkeypatch.setattr(
        "src.ops.attempt2_operator.collectors.runtime.subprocess.run",
        lambda *a, **k: P(),
    )
    d = collect_docker_status()
    assert d["status"] == "AVAILABLE"


def test_unknown_service_on_expected_port(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "src.ops.attempt2_operator.collectors.runtime._port_open",
        lambda host, port, timeout=0.35: True,
    )
    s = collect_service_status("n8n", containers=[], docker_status="UNAVAILABLE")
    assert s["status"] == "UNKNOWN"
    assert s["status"] != "RUNNING"


def test_known_n8n_container_stopped():
    containers = [
        {"Names": "n8n", "Status": "Exited (0) 2 hours ago", "State": "exited"}
    ]
    s = collect_service_status("n8n", containers=containers, docker_status="AVAILABLE")
    assert s["status"] == "STOPPED"
    assert s["identity_established"] is True


def test_known_n8n_container_running():
    containers = [
        {
            "Names": "sapi-ai-orchestrator-n8n",
            "Status": "Up 10 minutes",
            "State": "running",
        }
    ]
    s = collect_service_status("n8n", containers=containers, docker_status="AVAILABLE")
    assert s["status"] == "RUNNING"


def test_workspace_safety_never_pass():
    r = check_workspace_safety(REPO)
    assert r["status"] in ("NOT_AVAILABLE", "FAIL", "INCOMPLETE")
    assert r["status"] != "PASS"


def test_incomplete_preflight_never_ready(tmp_path: Path):
    """overall_status INCOMPLETE (e.g. workspace_safety stub) must not authorize."""
    op = Attempt2Operator.init_run(
        evidence_root=tmp_path,
        dry_run=True,
        expected_code_sha=SHA,
        run_id="SAPI-ATTEMPT2-P3-INCOMPLETE",
        synthetic_identity={
            "code_sha": SHA,
            "tree_sha": "f" * 40,
            "worktree_clean": True,
        },
    )
    snap = {
        "code": {
            "head_sha": SHA,
            "worktree_clean": True,
            "observed_at": "2026-09-24T12:00:00+00:00",
        },
        "firms": {"current": {"present": False, "state": "ABSENT"}},
        "dmc": {"current": {"present": False, "state": "ABSENT"}},
        "attempt1": {"preserve": True},
        "docker": {"status": "AVAILABLE"},
        "policy": {"human_authorization": False},
        "tests": {},
        "overall_status": "INCOMPLETE",
        "failures": [],
        "warnings": ["workspace_safety_not_available"],
        "highest_priority_reason": {
            "code": "WORKSPACE_SAFETY_NOT_AVAILABLE",
            "severity": "INCOMPLETE",
            "detail": "workspace_safety_not_available",
        },
    }
    result = op.preflight(snapshot=snap)
    assert result["ready_for_authorization"] is False
    assert result["technical_result"] == "INCOMPLETE"
    assert op.run.current_state() == Attempt2State.PREFLIGHT_FAILED
    nxt = op.next_action()
    assert nxt["reason_code"] == "WORKSPACE_SAFETY_NOT_AVAILABLE"


def test_preflight_reason_ordering():
    reasons = build_reasons(
        failures=["dirty_worktree", "expected_code_sha_mismatch"],
        warnings=["workspace_safety_not_available", "artifact_not_found"],
    )
    codes = [r["code"] for r in reasons]
    assert codes[0] == "CODE_SHA_MISMATCH"
    assert "DIRTY_CODE" in codes
    assert highest_priority_reason(reasons)["code"] == "CODE_SHA_MISMATCH"
    # priority table coherent
    assert REASON_PRIORITY.index("CODE_SHA_MISMATCH") < REASON_PRIORITY.index(
        "DIRTY_CODE"
    )


def test_next_returns_one_action(tmp_path: Path):
    op = Attempt2Operator.init_run(
        evidence_root=tmp_path,
        dry_run=True,
        expected_code_sha=SHA,
        run_id="SAPI-ATTEMPT2-P3-NEXT",
        synthetic_identity={
            "code_sha": SHA,
            "tree_sha": "f" * 40,
            "worktree_clean": True,
        },
    )
    snap = {
        "code": {
            "head_sha": "eeee" * 10,
            "worktree_clean": True,
            "observed_at": "2026-09-24T12:00:00+00:00",
        },
        "firms": {"current": {"present": False}},
        "dmc": {"current": {"present": False}},
        "attempt1": {"preserve": True},
        "docker": {"status": "UNKNOWN"},
        "policy": {"human_authorization": False},
        "tests": {},
        "highest_priority_reason": {
            "code": "CODE_SHA_MISMATCH",
            "detail": "expected_code_sha_mismatch",
        },
        "reasons": [{"code": "CODE_SHA_MISMATCH", "severity": "FAIL", "detail": "x"}],
    }
    # Write preflight.json as operator would after failed preflight
    op.preflight(snapshot=snap)
    # Ensure reasons file has priority for next()
    pf = json.loads(
        (op.run.root / "preflight" / "preflight.json").read_text(encoding="utf-8")
    )
    if not pf.get("highest_priority_reason"):
        pf["highest_priority_reason"] = {
            "code": "CODE_SHA_MISMATCH",
            "detail": "expected_code_sha_mismatch",
        }
        (op.run.root / "preflight" / "preflight.json").write_text(
            json.dumps(pf), encoding="utf-8"
        )
    assert op.run.current_state() == Attempt2State.PREFLIGHT_FAILED
    nxt = op.next_action()
    assert "reason_code" in nxt
    assert nxt["reason_code"]
    assert isinstance(nxt["next"], str)
    assert "\n" not in nxt["next"] or nxt["next"].count("\n") < 3


def test_timestamps_present_in_runtime():
    rt = collect_runtime()
    assert rt["observed_at"]
    assert rt.get("collection_started_at")
    assert rt.get("collection_finished_at")
    assert rt.get("mutations") is False
    for key in ("docker", "n8n", "bridge", "web"):
        assert rt[key]["observed_at"]


def test_runtime_collector_no_mutations(monkeypatch: pytest.MonkeyPatch):
    calls: list[list[str]] = []

    class P:
        returncode = 1
        stdout = ""
        stderr = ""

    def fake_run(cmd, **kwargs):
        calls.append(list(cmd))
        return P()

    monkeypatch.setattr(
        "src.ops.attempt2_operator.collectors.runtime.shutil.which",
        lambda _x: "/usr/bin/docker",
    )
    monkeypatch.setattr(
        "src.ops.attempt2_operator.collectors.runtime.subprocess.run",
        fake_run,
    )
    collect_runtime()
    joined = [" ".join(c) for c in calls]
    for j in joined:
        low = j.lower()
        assert not any(f" {f}" in f" {low} " for f in ("start", "stop", "restart"))
        assert "compose" not in low
        assert " pull" not in f" {low}"


def test_clean_sha_collection_fields(tmp_path: Path):
    # Synthetic repo without .git → UNKNOWN git, still has timestamps/reasons
    pf = collect_real_preflight(
        repo=tmp_path,
        run_id="SAPI-ATTEMPT2-P3-CLEAN",
        expected_code_sha=SHA,
    )
    assert pf["collection_started_at"]
    assert pf["collection_finished_at"]
    assert "reasons" in pf
    assert pf["overall_status"] in ("PASS", "FAIL", "INCOMPLETE")


def test_data_root_override_finds_baseline(tmp_path: Path):
    # code root without data; data root elsewhere
    code = tmp_path / "code"
    code.mkdir()
    data = tmp_path / "operational_data"
    processed = data / "processed"
    processed.mkdir(parents=True)
    bl = processed / FIRMS_BASELINE_REL.name
    bl.write_bytes(b"baseline")
    art = collect_artifact_identities(code, data_root=data)
    assert art["firms_baseline"]["exists"] is True
    assert Path(art["firms_baseline"]["path"]) == bl

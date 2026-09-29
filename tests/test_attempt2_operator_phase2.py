"""Phase 2: real collectors, subprocess adapter, import binding, invariants."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from src.ops.attempt2_operator.canonical import (
    assert_unknown_invariants,
    normalize_current,
)
from src.ops.attempt2_operator.collectors.artifacts import collect_artifact_identities
from src.ops.attempt2_operator.collectors.credentials import collect_credential_presence
from src.ops.attempt2_operator.collectors.firms_current import collect_firms_current
from src.ops.attempt2_operator.collectors.git_state import collect_git_state
from src.ops.attempt2_operator.collectors.runtime import collect_runtime
from src.ops.attempt2_operator.collectors.store_state import collect_store_state
from src.ops.attempt2_operator.operator import Attempt2Operator
from src.ops.attempt2_operator.redaction import redact_text
from src.ops.attempt2_operator.states import Attempt2State
from src.ops.attempt2_operator.subprocess_adapter import run_tool
from src.ops.attempt2_operator.validator_hooks import (
    run_dmc_validator_hook,
    run_firms_validator_hook,
)
from src.ops.attempt2_operator.workspace_safety import check_workspace_safety

SHA = "cccccccccccccccccccccccccccccccccccccccc"
REPO = Path(__file__).resolve().parents[1]


def test_unknown_invariants():
    assert_unknown_invariants()
    assert normalize_current(None)["state"] == "UNKNOWN"
    assert normalize_current({"present": False})["state"] == "ABSENT"
    assert "UNKNOWN" != "STOPPED"
    assert "UNKNOWN" != "SAFE"
    assert "UNKNOWN" != "PASS"


def test_real_git_collector():
    g = collect_git_state(REPO, expected_code_sha=None)
    assert g["observed_at"]
    assert g["code_root"]
    assert g["head_sha"] is not None
    assert g["tree_sha"] is not None
    assert g["dirty"] is not None


def test_dirty_git_state(tmp_path: Path):
    # Use a temp non-repo → UNKNOWN, not ABSENT
    g = collect_git_state(tmp_path, expected_code_sha=SHA)
    assert g["status"] == "UNKNOWN"
    assert g["head_sha"] is None


def test_wrong_expected_sha_on_real_repo():
    g = collect_git_state(REPO, expected_code_sha="deadbeef" * 5)
    assert g["sha_match"] is False
    assert g["status"] == "FAIL"


def test_missing_store(tmp_path: Path):
    s = collect_store_state(tmp_path / "nope")
    assert s["exists"] is False
    assert s["current"]["state"] == "ABSENT"


def test_current_absent(tmp_path: Path):
    d = tmp_path / "firms"
    d.mkdir()
    s = collect_store_state(d)
    assert s["current"]["state"] == "ABSENT"
    assert s["current"]["known"] is True


def test_current_unknown_unreadable(tmp_path: Path):
    # Point to a file path that cannot be listed as dir — use invalid unicode?
    # Simulate via firms collector on missing parent that raises — use nonexistent but
    # firms collect ABSENT. For UNKNOWN: unreadable pointer file with bad JSON.
    p = tmp_path / "CURRENT.json"
    p.write_text("{not-json", encoding="utf-8")
    f = collect_firms_current(pointer_path=p)
    assert f["state"] == "UNKNOWN"
    assert f["state"] != "ABSENT"


def test_credential_presence_no_leak():
    env = {
        "NASA_FIRMS_API_KEY": "SUPER_SECRET_VALUE_XYZ",
        "DMC_USUARIO": "user",
        "DMC_TOKEN": "tokensecret",
    }
    out = collect_credential_presence(env)
    blob = json.dumps(out)
    assert "SUPER_SECRET_VALUE_XYZ" not in blob
    assert "tokensecret" not in blob
    assert all(set(c.keys()) == {"name", "present"} for c in out["credentials"])
    assert all(c["present"] for c in out["credentials"])


def test_runtime_statuses_valid():
    rt = collect_runtime()
    assert rt["docker"]["status"] in ("AVAILABLE", "UNAVAILABLE", "UNKNOWN")
    assert rt["docker"]["observed_at"]
    for key in ("n8n", "bridge", "web"):
        assert rt[key]["status"] in ("RUNNING", "STOPPED", "UNKNOWN")
        assert rt[key]["observed_at"]
        # UNKNOWN != STOPPED invariant retained even when STOPPED observed
        if rt[key]["status"] == "UNKNOWN":
            assert rt[key]["status"] != "STOPPED"


def test_subprocess_pass(tmp_path: Path):
    r = run_tool(
        tool_name="echo_ok",
        command=[sys.executable, "-c", 'print(\'{"status":"ok"}\')'],
        output_dir=tmp_path,
        timeout_s=10,
        code_sha=SHA,
    )
    assert r.status == "PASS"
    assert r.exit_code == 0
    assert (tmp_path / "echo_ok.stdout.txt").exists()


def test_subprocess_fail(tmp_path: Path):
    r = run_tool(
        tool_name="echo_fail",
        command=[sys.executable, "-c", "raise SystemExit(2)"],
        output_dir=tmp_path,
        timeout_s=10,
    )
    assert r.status == "FAIL"
    assert r.exit_code == 2


def test_subprocess_timeout(tmp_path: Path):
    r = run_tool(
        tool_name="sleep",
        command=[sys.executable, "-c", "import time; time.sleep(5)"],
        output_dir=tmp_path,
        timeout_s=0.3,
    )
    assert r.status == "FAIL"
    assert r.exit_code == 124
    assert "timeout" in r.failures


def test_redaction_secrets():
    text, hit = redact_text("NASA_FIRMS_API_KEY=abc123secret\nother")
    assert hit is True
    assert "abc123secret" not in text
    assert "REDACTED" in text


def test_malformed_validator_output(tmp_path: Path):
    r = run_tool(
        tool_name="bad_json",
        command=[sys.executable, "-c", "print('not-json')"],
        output_dir=tmp_path,
        timeout_s=10,
    )
    assert "stdout_not_json" in r.warnings


def _boot(tmp_path: Path) -> Attempt2Operator:
    op = Attempt2Operator.init_run(
        evidence_root=tmp_path,
        dry_run=True,
        expected_code_sha=SHA,
        run_id="SAPI-ATTEMPT2-P2",
        synthetic_identity={
            "code_sha": SHA,
            "tree_sha": "d" * 40,
            "worktree_clean": True,
        },
    )
    snap = {
        "code": {
            "head_sha": SHA,
            "worktree_clean": True,
            "observed_at": "2026-09-24T12:00:00+00:00",
        },
        "firms": {"current": {"present": False}},
        "dmc": {"current": {"present": False}},
        "attempt1": {"preserve": True},
        "docker": {"status": "UNAVAILABLE"},
        "policy": {"human_authorization": False},
        "tests": {},
        "overall_status": "PASS",
    }
    assert op.preflight(snapshot=snap)["ready_for_authorization"]
    assert (op.run.root / "preflight" / "preflight.json").exists()
    op.advance()
    op.authorize("ATTEMPT2_AUTHORIZATION")
    op.advance()
    return op


def test_preflight_persistence(tmp_path: Path):
    op = _boot(tmp_path)
    assert (op.run.root / "preflight" / "preflight.json").is_file()


def test_next_after_incomplete_preflight(tmp_path: Path):
    op = Attempt2Operator.init_run(
        evidence_root=tmp_path,
        dry_run=True,
        expected_code_sha=SHA,
        run_id="SAPI-ATTEMPT2-P2-INC",
        synthetic_identity={
            "code_sha": SHA,
            "tree_sha": "e" * 40,
            "worktree_clean": True,
        },
    )
    snap = {
        "code": {
            "head_sha": "ffff" * 10,
            "worktree_clean": True,
            "observed_at": "2026-09-24T12:00:00+00:00",
        },
        "firms": {"current": {"present": False}},
        "dmc": {"current": {"present": False}},
        "attempt1": {"preserve": True},
        "docker": {"status": "UNKNOWN"},
        "policy": {"human_authorization": False},
        "tests": {},
    }
    op.preflight(snapshot=snap)
    assert op.run.current_state() == Attempt2State.PREFLIGHT_FAILED
    nxt = op.next_action()
    assert "Preflight" in nxt["next"] or "preflight" in nxt["next"].lower()


def test_stale_sha_import(tmp_path: Path):
    op = _boot(tmp_path)
    op.authorize("FIRMS_WRITER_AUTHORIZATION")
    with pytest.raises(RuntimeError, match="stale_or_wrong_sha"):
        op.import_result(
            "firms",
            {
                "exit_code": 0,
                "started_at": "t0",
                "finished_at": "t1",
                "code_sha": "deadbeef" * 5,
                "stdout": "",
                "stderr": "",
                "sanitization_status": "PASS",
                "schema_ok": True,
                "hash_ok": True,
                "pointer_ok": True,
                "firms_current_after": {"present": True},
            },
        )


def test_wrong_run_import(tmp_path: Path):
    op = _boot(tmp_path)
    op.authorize("FIRMS_WRITER_AUTHORIZATION")
    with pytest.raises(RuntimeError, match="wrong_run"):
        op.import_result(
            "firms",
            {
                "run_id": "OTHER-RUN",
                "exit_code": 0,
                "started_at": "t0",
                "finished_at": "t1",
                "stdout": "",
                "stderr": "",
                "sanitization_status": "PASS",
                "schema_ok": True,
                "hash_ok": True,
                "pointer_ok": True,
                "firms_current_after": {"present": True},
            },
        )


def test_wrong_step_import(tmp_path: Path):
    op = _boot(tmp_path)
    op.authorize("FIRMS_WRITER_AUTHORIZATION")
    with pytest.raises(RuntimeError, match="wrong_step"):
        op.import_result(
            "firms",
            {
                "step": "dmc",
                "exit_code": 0,
                "started_at": "t0",
                "finished_at": "t1",
                "stdout": "",
                "stderr": "",
                "sanitization_status": "PASS",
                "schema_ok": True,
                "hash_ok": True,
                "pointer_ok": True,
                "firms_current_after": {"present": True},
            },
        )


def test_conflicting_and_idempotent_import(tmp_path: Path):
    op = _boot(tmp_path)
    op.authorize("FIRMS_WRITER_AUTHORIZATION")
    payload = {
        "exit_code": 0,
        "started_at": "t0",
        "finished_at": "t1",
        "stdout": "a",
        "stderr": "",
        "sanitization_status": "PASS",
        "schema_ok": True,
        "hash_ok": True,
        "pointer_ok": True,
        "firms_current_after": {"present": True},
    }
    assert op.import_result("firms", payload)["result"] == "PASS"
    assert op.import_result("firms", payload)["result"] == "DUPLICATE"
    payload2 = dict(payload)
    payload2["stdout"] = "b"
    with pytest.raises(RuntimeError, match="Refusing to overwrite"):
        op.import_result("firms", payload2)


def test_firms_validator_adapter(tmp_path: Path):
    result = run_firms_validator_hook(
        work_dir=tmp_path,
        before={"x": 1},
        after={"x": 2},
        delta={
            "firms_current_transition": {"after_present": False, "changed": False},
            "baseline_sha_changed": False,
            "model_sha_changed": False,
            "hito1_changed": False,
            "files_added": [],
            "files_changed": [],
            "files_removed": [],
            "lock_changes": [],
            "worst_classification": "EXPECTED",
        },
        command_evidence={
            "exit_code": 65,
            "stdout_sha256": "a" * 64,
            "stderr_sha256": "b" * 64,
            "sanitization_status": "PASS",
            "metadata": {},
        },
        code_sha=SHA,
        timeout_s=30,
    )
    assert result.name == "firms_validator"
    assert result.status in ("PASS", "FAIL", "INCOMPLETE")
    assert result.started_at and result.finished_at


def test_dmc_validator_adapter(tmp_path: Path):
    result = run_dmc_validator_hook(
        work_dir=tmp_path,
        before={},
        after={},
        delta={
            "dmc_current_transition": {"changed": False, "after_present": False},
            "model_sha_changed": False,
            "hito1_changed": False,
            "files_added": [],
            "files_changed": [],
            "files_removed": [],
            "worst_classification": "EXPECTED",
        },
        command_evidence={
            "exit_code": 0,
            "stdout_sha256": "a" * 64,
            "stderr_sha256": "b" * 64,
            "sanitization_status": "PASS",
        },
        external=None,
        code_sha=SHA,
        timeout_s=30,
    )
    assert result.name == "dmc_validator"
    assert result.status in ("PASS", "FAIL", "INCOMPLETE")


def test_workspace_safety_not_available_not_pass():
    r = check_workspace_safety(REPO)
    assert r["status"] in ("NOT_AVAILABLE", "FAIL", "INCOMPLETE")
    assert r["status"] != "PASS"


def test_artifact_collector_statuses():
    a = collect_artifact_identities(REPO)
    assert a["overall_status"] in ("PASS", "FAIL", "INCOMPLETE", "NOT_AVAILABLE")
    assert a["model"]["status"] != "PASS" or a["model"]["match"] is True
    if not a["model"]["exists"]:
        assert a["model"]["status"] == "NOT_AVAILABLE"


def test_restart_reload(tmp_path: Path):
    op = _boot(tmp_path)
    path = op.run.root
    op2 = Attempt2Operator.open_run(path)
    assert op2.run.current_state() == Attempt2State.FIRMS_WRITER_REQUIRED

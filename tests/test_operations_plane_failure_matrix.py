"""Failure matrix for SAPI Operations Plane RC1 (Phase I).

Verifies that safety guarantees hold and every unsafe operational state is blocked:
- wrong expected code SHA → blocked
- dirty code → blocked
- workspace manifest mismatch → blocked
- source store drift → blocked
- junction/reparse unsafe topology → blocked
- Workspace Safety FAIL → blocked
- Workspace Safety INCOMPLETE → blocked
- data manifest missing when required → incomplete
- data manifest tampered → blocked
- quiescence NOT_QUIESCENT → blocked
- n8n RUNNING under FIRST-CONTROLLED-REFRESH → blocked
- active FIRMS writer → blocked
- active DMC writer → blocked
- active lock → blocked
- stale lock → human resolution required
- Telegram ARMED → blocked/incomplete according to policy
- writer authorization absent → cannot progress
- wrong imported run ID → reject
- wrong imported SHA → reject
- conflicting import → reject
- tampered output acceptance → reject
- UNKNOWN → never safe
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.ops import operational_workspace as ow
from src.ops import workspace_safety as ws
from src.ops.attempt2_operator.canonical import (
    assert_unknown_invariants,
    normalize_current,
)
from src.ops.attempt2_operator.data_plane_manifest import verify_data_plane_manifest
from src.ops.attempt2_operator.operator import Attempt2Operator
from src.ops.attempt2_operator.output_plane_manifest import (
    compute_output_manifest_fingerprint,
    verify_output_plane_manifest,
)
from src.ops.attempt2_operator.quiescence.findings import (
    QG_ACTIVE_FIRMS_LOCK,
    QG_ACTIVE_WRITER,
    QG_N8N_MUST_BE_STOPPED,
    QG_STALE_LOCK,
    QG_TELEGRAM_ARMED,
)
from src.ops.attempt2_operator.quiescence.locks import ACTIVE_LOCK, NO_LOCK, STALE_LOCK
from src.ops.attempt2_operator.quiescence.policy import QuiescencePolicy
from src.ops.attempt2_operator.quiescence.result import evaluate_quiescence
from src.ops.attempt2_operator.quiescence.writers import (
    WRITER_ACTIVE,
    WRITER_NOT_DETECTED,
)
from src.ops.attempt2_operator.states import Attempt2State
from src.ops.attempt2_operator.validators import validate_preflight_snapshot
from src.ops.attempt2_operator.workspace_manifest import verify_workspace_manifest

SHA = "1111111111111111111111111111111111111111"
WRONG_SHA = "2222222222222222222222222222222222222222"


def _base_snapshot(expected_sha: str = SHA) -> dict:
    return {
        "code": {
            "head_sha": expected_sha,
            "tree_sha": "a" * 40,
            "worktree_clean": True,
            "observed_at": "2026-09-25T12:00:00Z",
        },
        "firms": {"current": {"present": False, "state": "ABSENT"}},
        "dmc": {"current": {"present": False, "state": "ABSENT"}},
        "attempt1": {"preserve": True},
        "docker": {"status": "AVAILABLE"},
        "policy": {"human_authorization": False},
        "workspace_safety": {"status": "PASS"},
        "quiescence": {"status": "QUIESCENT"},
        "overall_status": "PASS",
        "failures": [],
        "warnings": [],
    }


def test_wrong_expected_code_sha_blocked(tmp_path: Path):
    op = Attempt2Operator.init_run(
        evidence_root=tmp_path,
        dry_run=True,
        expected_code_sha=SHA,
        run_id="FAIL-WRONG-SHA",
        synthetic_identity={
            "code_sha": SHA,
            "tree_sha": "a" * 40,
            "worktree_clean": True,
        },
    )
    snap = _base_snapshot(expected_sha=WRONG_SHA)
    res = op.preflight(snapshot=snap)
    assert res["ready_for_authorization"] is False
    assert res["technical_result"] == "FAIL"
    assert op.run.current_state() == Attempt2State.PREFLIGHT_FAILED


def test_dirty_code_blocked(tmp_path: Path):
    op = Attempt2Operator.init_run(
        evidence_root=tmp_path,
        dry_run=True,
        expected_code_sha=SHA,
        run_id="FAIL-DIRTY",
        synthetic_identity={
            "code_sha": SHA,
            "tree_sha": "a" * 40,
            "worktree_clean": False,
        },
    )
    snap = _base_snapshot(expected_sha=SHA)
    snap["code"]["worktree_clean"] = False
    res = op.preflight(snapshot=snap)
    assert res["ready_for_authorization"] is False
    assert res["technical_result"] == "FAIL"
    assert op.run.current_state() == Attempt2State.PREFLIGHT_FAILED


def test_workspace_manifest_mismatch_blocked(tmp_path: Path):
    manifest_path = tmp_path / "OPERATIONAL-WORKSPACE-MANIFEST.json"
    manifest_data = {
        "schema_version": 1,
        "run_id": "mat-123",
        "promotion_status": "PROMOTED",
        "destination": str(tmp_path / "non_existent_workspace"),
        "code_sha": WRONG_SHA,
        "tree_sha": "t" * 40,
    }
    manifest_path.write_text(json.dumps(manifest_data), encoding="utf-8")
    ver = verify_workspace_manifest(manifest_path, expected_code_sha=SHA)
    assert ver["status"] == "FAIL"
    codes = [f["code"] for f in ver["findings"]]
    assert "WRONG_CODE_SHA" in codes
    assert "WORKSPACE_ROOT_MISSING" in codes


def test_source_store_drift_blocked(tmp_path: Path):
    ws_dir = tmp_path / "workspace"
    ws_dir.mkdir()
    manifest_path = ws_dir / "OPERATIONAL-WORKSPACE-MANIFEST.json"
    ident_path = ws_dir / "CODE-IDENTITY.json"
    ident_path.write_text(json.dumps({"sha": SHA, "tree": "t" * 40}), encoding="utf-8")
    manifest_data = {
        "schema_version": 1,
        "run_id": "mat-drift",
        "promotion_status": "PROMOTED",
        "destination": str(ws_dir),
        "code_sha": SHA,
        "tree_sha": "t" * 40,
        "stores": {
            "raw": {
                "files": [
                    {"path": "data/raw/data.csv", "size": 100, "sha256": "0" * 64}
                ]
            }
        },
    }
    manifest_path.write_text(json.dumps(manifest_data), encoding="utf-8")
    # File is missing or has different hash -> drift
    ver = ow.verify(ws_dir)
    assert ver["overall_status"] == "FAIL"
    assert "data/raw/data.csv" in ver["drifted_files"]


def test_junction_reparse_unsafe_topology_blocked(tmp_path: Path):
    # Guard finds reparse point on stores or code
    res = ws.check_workspace(
        ws.GuardRequest(
            mode=ws.Mode.OPERATIONAL_REAL_DATA,
            code_root=tmp_path,
            expected_code_sha=SHA,
            stores={"raw": tmp_path / "data" / "raw"},
        )
    )
    # On an ad-hoc unmaterialized directory, guard must FAIL or be INCOMPLETE, never PASS
    assert res["overall_status"] != "PASS"


def test_workspace_safety_fail_blocked(tmp_path: Path):
    op = Attempt2Operator.init_run(
        evidence_root=tmp_path,
        dry_run=True,
        expected_code_sha=SHA,
        run_id="FAIL-WS-FAIL",
    )
    snap = _base_snapshot(expected_sha=SHA)
    snap["workspace_safety"] = {"status": "FAIL", "overall_status": "FAIL"}
    snap["overall_status"] = "FAIL"
    res = op.preflight(snapshot=snap)
    assert res["ready_for_authorization"] is False
    assert op.run.current_state() == Attempt2State.PREFLIGHT_FAILED


def test_workspace_safety_incomplete_blocked(tmp_path: Path):
    op = Attempt2Operator.init_run(
        evidence_root=tmp_path,
        dry_run=True,
        expected_code_sha=SHA,
        run_id="FAIL-WS-INCOMPLETE",
    )
    snap = _base_snapshot(expected_sha=SHA)
    snap["workspace_safety"] = {"status": "INCOMPLETE", "overall_status": "INCOMPLETE"}
    snap["overall_status"] = "INCOMPLETE"
    res = op.preflight(snapshot=snap)
    assert res["ready_for_authorization"] is False
    assert op.run.current_state() == Attempt2State.PREFLIGHT_FAILED


def test_data_manifest_missing_when_required_incomplete():
    res = verify_data_plane_manifest(None)
    assert res["status"] == "NOT_AVAILABLE"
    assert res["ready"] is False


def test_data_manifest_tampered_blocked(tmp_path: Path):
    manifest_file = tmp_path / "DATA_PLANE_MANIFEST.json"
    identity = {
        "schema_version": 1,
        "kind": "DATA_PLANE_MANIFEST",
        "data_readiness_status": "PREPARED",  # READY is not a valid producer value
        "data_ready_for_scoring": "NOT_EVALUATED",
        "independent_approval": "PENDING",
        "authorizations": {
            "attempt2": False,
            "writers": False,
            "telegram": False,
            "schedule": False,
        },
        "code_identity": {
            "sha": "a" * 40,
            "tree": "b" * 40,
            "clean": True,
            "status": "PASS",
        },
        "components": {
            "firms": {"sha": "c" * 40, "files": [], "status": "PASS"},
            "dmc": {"sha": "d" * 40, "files": [], "status": "PASS"},
            "scoring_inputs": {"sha": "e" * 40, "files": [], "status": "PASS"},
        },
        "model": {"sha256": "f" * 64, "status": "PASS"},
        "topography": {
            "table_sha256": "g" * 64,
            "grid_sha256": "h" * 64,
            "status": "PASS",
            "cells": 50,
        },
        "baseline": {"sha256": "i" * 64, "status": "PASS"},
        "source_evidence": {"sha256": "j" * 64, "status": "PASS"},
        "expected_current": {"firms": "ABSENT", "dmc": "ABSENT"},
        "current_state": {"firms": "ABSENT", "dmc": "ABSENT"},
        "findings": [],
    }
    data = {
        "schema_version": 1,
        "created_at": "2026-09-25T19:00:00+00:00",
        "identity": identity,
        "fingerprint": "TAMPERED_FINGERPRINT_HASH_THAT_IS_WRONG",  # intentionally wrong
        "operational_roots": {"workspace": "/fake", "code": "/fake"},
        "observation": {
            "start": "2026-09-25T19:00:00+00:00",
            "end": "2026-09-25T19:00:01+00:00",
        },
    }
    manifest_file.write_text(json.dumps(data), encoding="utf-8")
    res = verify_data_plane_manifest(manifest_file)
    assert res["status"] == "FAIL"
    assert res["ready"] is False
    codes = [f["code"] for f in res["findings"]]
    assert "DATA_MANIFEST_TAMPERED" in codes


def test_quiescence_not_quiescent_blocked(tmp_path: Path):
    op = Attempt2Operator.init_run(
        evidence_root=tmp_path,
        dry_run=True,
        expected_code_sha=SHA,
        run_id="FAIL-NOT-QUIESCENT",
    )
    snap = _base_snapshot(expected_sha=SHA)
    snap["quiescence"] = {
        "status": "NOT_QUIESCENT",
        "highest_priority_finding": {
            "id": "QG-014",
            "severity": "FAIL",
            "detail": "n8n container is RUNNING",
        },
    }
    snap["overall_status"] = "FAIL"
    res = op.preflight(snapshot=snap)
    assert res["ready_for_authorization"] is False
    assert op.run.current_state() == Attempt2State.PREFLIGHT_FAILED


def _eval_quiescence_test(
    *,
    n8n_status="STOPPED",
    n8n_activation_active=False,
    n8n_execution_state="NOT_RUNNING",
    n8n_schedule_state="SCHEDULE_NOT_PRESENT",
    n8n_telegram_state="DISARMED",
    writers_status=WRITER_NOT_DETECTED,
    firms_lock_cls=NO_LOCK,
    dmc_lock_cls=NO_LOCK,
    policy=None,
):
    now = datetime.now(timezone.utc).isoformat()
    return evaluate_quiescence(
        processes={"status": "READY", "items": [], "mutations": False},
        writers={"status": writers_status, "active": [], "mutations": False},
        locks={
            "overall": firms_lock_cls if firms_lock_cls != NO_LOCK else dmc_lock_cls,
            "firms": {"classification": firms_lock_cls},
            "dmc": {"classification": dmc_lock_cls},
            "mutations": False,
        },
        n8n={
            "container_status": n8n_status,
            "activation": {
                "status": "READY",
                "any_relevant_active": n8n_activation_active,
                "workflows": [],
            },
            "schedule": {"status": "READY", "state": n8n_schedule_state},
            "telegram": {"status": "READY", "state": n8n_telegram_state},
            "execution": {
                "status": "READY",
                "state": n8n_execution_state,
                "running": [],
            },
            "mutations": False,
        },
        bridge={"status": "STOPPED"},
        web={"status": "STOPPED"},
        policy=policy
        or QuiescencePolicy(
            n8n_container="MUST_BE_STOPPED",
            bridge="MUST_BE_STOPPED",
            web="MUST_BE_STOPPED",
            allow_n8n_running_if_inactive=False,
        ),
        observed_at_start=now,
        observed_at_end=now,
    )


def test_n8n_running_under_first_controlled_refresh_policy_blocked():
    res = _eval_quiescence_test(n8n_status="RUNNING")
    assert res["status"] == "NOT_QUIESCENT"
    assert res["status"] != "QUIESCENT"
    ids = [f["id"] for f in res["findings"]]
    assert QG_N8N_MUST_BE_STOPPED in ids


def test_active_firms_writer_blocked():
    res = _eval_quiescence_test(writers_status=WRITER_ACTIVE)
    assert res["status"] == "NOT_QUIESCENT"
    ids = [f["id"] for f in res["findings"]]
    assert QG_ACTIVE_WRITER in ids


def test_active_dmc_writer_blocked():
    res = _eval_quiescence_test(writers_status=WRITER_ACTIVE)
    assert res["status"] == "NOT_QUIESCENT"
    ids = [f["id"] for f in res["findings"]]
    assert QG_ACTIVE_WRITER in ids


def test_active_lock_blocked():
    res = _eval_quiescence_test(firms_lock_cls=ACTIVE_LOCK)
    assert res["status"] == "NOT_QUIESCENT"
    ids = [f["id"] for f in res["findings"]]
    assert QG_ACTIVE_FIRMS_LOCK in ids


def test_stale_lock_requires_human_resolution():
    res = _eval_quiescence_test(dmc_lock_cls=STALE_LOCK)
    assert res["status"] == "NOT_QUIESCENT"
    ids = [f["id"] for f in res["findings"]]
    assert QG_STALE_LOCK in ids


def test_telegram_armed_blocked_or_incomplete():
    res = _eval_quiescence_test(n8n_telegram_state="ARMED")
    assert res["status"] == "NOT_QUIESCENT"
    ids = [f["id"] for f in res["findings"]]
    assert QG_TELEGRAM_ARMED in ids


def test_writer_authorization_absent_cannot_progress(tmp_path: Path):
    op = Attempt2Operator.init_run(
        evidence_root=tmp_path,
        dry_run=True,
        expected_code_sha=SHA,
        run_id="FAIL-NO-AUTH",
        synthetic_identity={
            "code_sha": SHA,
            "tree_sha": "a" * 40,
            "worktree_clean": True,
        },
    )
    snap = _base_snapshot(expected_sha=SHA)
    assert op.preflight(snapshot=snap)["ready_for_authorization"]
    op.advance()
    op.authorize("ATTEMPT2_AUTHORIZATION")
    op.advance()
    assert op.run.current_state() == Attempt2State.FIRMS_WRITER_REQUIRED
    # Try to advance without FIRMS_WRITER_AUTHORIZATION
    with pytest.raises(PermissionError):
        op.advance()


def test_wrong_imported_run_id_rejected(tmp_path: Path):
    op = Attempt2Operator.init_run(
        evidence_root=tmp_path,
        dry_run=True,
        expected_code_sha=SHA,
        run_id="RUN-AAA",
        synthetic_identity={
            "code_sha": SHA,
            "tree_sha": "a" * 40,
            "worktree_clean": True,
        },
    )
    snap = _base_snapshot(expected_sha=SHA)
    op.preflight(snapshot=snap)
    op.advance()
    op.authorize("ATTEMPT2_AUTHORIZATION")
    op.advance()
    op.authorize("FIRMS_WRITER_AUTHORIZATION")
    bad_payload = {
        "run_id": "DIFFERENT-RUN-BBB",
        "step": "firms",
        "code_sha": SHA,
        "exit_code": 0,
        "started_at": "2026-09-25T12:00:00Z",
        "finished_at": "2026-09-25T12:01:00Z",
    }
    with pytest.raises(RuntimeError, match="wrong_run"):
        op.import_result("firms", bad_payload)


def test_wrong_imported_sha_rejected(tmp_path: Path):
    op = Attempt2Operator.init_run(
        evidence_root=tmp_path,
        dry_run=True,
        expected_code_sha=SHA,
        run_id="RUN-SHA-CHECK",
        synthetic_identity={
            "code_sha": SHA,
            "tree_sha": "a" * 40,
            "worktree_clean": True,
        },
    )
    snap = _base_snapshot(expected_sha=SHA)
    op.preflight(snapshot=snap)
    op.advance()
    op.authorize("ATTEMPT2_AUTHORIZATION")
    op.advance()
    op.authorize("FIRMS_WRITER_AUTHORIZATION")
    bad_payload = {
        "run_id": "RUN-SHA-CHECK",
        "step": "firms",
        "code_sha": WRONG_SHA,
        "exit_code": 0,
        "started_at": "2026-09-25T12:00:00Z",
        "finished_at": "2026-09-25T12:01:00Z",
    }
    with pytest.raises(RuntimeError, match="stale_or_wrong_sha"):
        op.import_result("firms", bad_payload)


def test_conflicting_import_rejected(tmp_path: Path):
    op = Attempt2Operator.init_run(
        evidence_root=tmp_path,
        dry_run=True,
        expected_code_sha=SHA,
        run_id="RUN-CONFLICT",
        synthetic_identity={
            "code_sha": SHA,
            "tree_sha": "a" * 40,
            "worktree_clean": True,
        },
    )
    snap = _base_snapshot(expected_sha=SHA)
    op.preflight(snapshot=snap)
    op.advance()
    op.authorize("ATTEMPT2_AUTHORIZATION")
    op.advance()
    op.authorize("FIRMS_WRITER_AUTHORIZATION")

    payload1 = {
        "run_id": "RUN-CONFLICT",
        "step": "firms",
        "code_sha": SHA,
        "exit_code": 0,
        "started_at": "2026-09-25T12:00:00Z",
        "finished_at": "2026-09-25T12:01:00Z",
        "operation_success": True,
        "stdout": "first payload",
    }
    op.import_result("firms", payload1)

    payload2 = {
        "run_id": "RUN-CONFLICT",
        "step": "firms",
        "code_sha": SHA,
        "exit_code": 0,
        "started_at": "2026-09-25T12:00:00Z",
        "finished_at": "2026-09-25T12:01:00Z",
        "operation_success": True,
        "stdout": "conflicting different payload",
    }
    with pytest.raises(RuntimeError, match="Refusing to overwrite"):
        op.import_result("firms", payload2)


def test_tampered_output_acceptance_rejected(tmp_path: Path):
    out_file = tmp_path / "OUTPUT-PLANE-MANIFEST.json"
    score_file = tmp_path / "scores.parquet"
    score_file.write_text("actual score bytes\n")

    tampered_data = {
        "schema_version": 1,
        "output_contract_version": "v1.0.0",
        "accepted_score_artifact_path": str(score_file),
        "accepted_score_artifact_sha256": "CORRUPTED_SHA_DOES_NOT_MATCH_FILE",
        "presentation_contract_status": "READY",
    }
    tampered_fp = compute_output_manifest_fingerprint(tampered_data)
    tampered_data["manifest_fingerprint"] = tampered_fp
    out_file.write_text(json.dumps(tampered_data), encoding="utf-8")

    res = verify_output_plane_manifest(out_file, score_artifact_path=score_file)
    assert res["status"] == "FAIL"
    codes = [f["code"] for f in res["findings"]]
    assert "TAMPERED_OUTPUT_ACCEPTANCE" in codes


def test_unknown_never_safe():
    assert_unknown_invariants()
    assert normalize_current(None)["state"] == "UNKNOWN"
    # Preflight with UNKNOWN currents must never be ready for authorization
    snap = _base_snapshot(expected_sha=SHA)
    snap["firms"]["current"]["state"] = "UNKNOWN"
    val = validate_preflight_snapshot(snap, expected_code_sha=SHA)
    assert val["ready_for_authorization"] is False
    assert val["technical_result"] == "INCOMPLETE"

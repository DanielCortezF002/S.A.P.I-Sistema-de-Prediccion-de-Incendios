"""Full synthetic end-to-end test for Operations Plane RC1 (Phase H).

Executes the complete 21-step operational lifecycle:
1. create synthetic Git/code source
2. create synthetic raw/processed/model stores
3. materializer plan
4. synthetic test authorization
5. physical temp workspace materialization
6. verify manifest
7. Workspace Safety Guard PASS
8. create synthetic DATA_PLANE_MANIFEST PASS
9. Attempt2 Operator init
10. preflight PASS
11. synthetic quiescence QUIESCENT
12. reach ATTEMPT2_AUTHORIZATION_REQUIRED
13. explicit synthetic authorization
14. synthetic FIRMS writer-result import
15. FIRMS validation PASS
16. synthetic DMC writer-result import
17. DMC validation PASS
18. synthetic ScoringInputs/scoring result
19. synthetic bridge acceptance
20. synthetic OUTPUT manifest/artifact acceptance
21. final Attempt2 state: ACCEPTED

Uses temporary directories only. No real stores, no network, no operational containers.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


from src.ops import operational_workspace as ow
from src.ops import workspace_safety as ws
from src.ops.attempt2_operator.data_plane_manifest import (
    compute_data_manifest_fingerprint,
    verify_data_plane_manifest,
)
from src.ops.attempt2_operator.events import sha256_file
from src.ops.attempt2_operator.operator import Attempt2Operator
from src.ops.attempt2_operator.output_plane_manifest import (
    compute_output_manifest_fingerprint,
)
from src.ops.attempt2_operator.states import Attempt2State
from src.ops.attempt2_operator.workspace_manifest import verify_workspace_manifest


def _run_git(cwd: Path, *args: str) -> str:
    env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0"}
    res = subprocess.run(
        ["git", "--no-optional-locks", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=True,
        env=env,
    )
    return res.stdout.strip()


def test_full_synthetic_operations_e2e(tmp_path: Path):
    # -------------------------------------------------------------------------
    # Step 1: Create synthetic Git/code source repository
    # -------------------------------------------------------------------------
    repo_dir = tmp_path / "synthetic_repo"
    repo_dir.mkdir(parents=True)
    _run_git(repo_dir, "init", "-q")
    _run_git(repo_dir, "config", "core.autocrlf", "false")
    _run_git(repo_dir, "config", "core.symlinks", "false")
    _run_git(repo_dir, "config", "user.email", "operator@example.com")
    _run_git(repo_dir, "config", "user.name", "Synthetic Operator")

    # Create tracked files mirroring repo structure
    (repo_dir / "src").mkdir(parents=True)
    (repo_dir / "src" / "__init__.py").write_text(
        '"""Synthetic SAPI package."""\n', encoding="utf-8"
    )
    (repo_dir / "src" / "config.py").write_text('"""Config."""\n', encoding="utf-8")
    (repo_dir / "models").mkdir(parents=True)
    (repo_dir / "models" / ".gitkeep").write_text("", encoding="utf-8")
    (repo_dir / "data" / "raw").mkdir(parents=True)
    (repo_dir / "data" / "raw" / ".gitkeep").write_text("", encoding="utf-8")
    (repo_dir / "data" / "processed").mkdir(parents=True)
    (repo_dir / "data" / "processed" / ".gitkeep").write_text("", encoding="utf-8")
    (repo_dir / "data" / "predictions").mkdir(parents=True)
    (repo_dir / "data" / "predictions" / ".gitkeep").write_text("", encoding="utf-8")

    _run_git(repo_dir, "add", "-A")
    _run_git(repo_dir, "commit", "-q", "-m", "chore: synthetic baseline code")
    code_sha = _run_git(repo_dir, "rev-parse", "HEAD")
    tree_sha = _run_git(repo_dir, "rev-parse", "HEAD^{tree}")
    assert len(code_sha) == 40
    assert len(tree_sha) == 40

    # -------------------------------------------------------------------------
    # Step 2: Create synthetic raw/processed/model stores
    # -------------------------------------------------------------------------
    stores_root = tmp_path / "source_stores"
    raw_src = stores_root / "raw"
    processed_src = stores_root / "processed"
    models_src = stores_root / "models"

    raw_src.mkdir(parents=True)
    (raw_src / "CURRENT.json").write_text(
        '{"state": "ABSENT", "synthetic": true}\n', encoding="utf-8"
    )
    (raw_src / "firms_data.csv").write_text(
        "latitude,longitude,frp\n-33.4,-70.6,12.5\n", encoding="utf-8"
    )

    processed_src.mkdir(parents=True)
    (processed_src / "CURRENT.json").write_text(
        '{"state": "ABSENT", "synthetic": true}\n', encoding="utf-8"
    )
    (processed_src / "meteo.csv").write_text(
        "temp,rh,wind\n28.5,35.0,15.2\n", encoding="utf-8"
    )

    models_src.mkdir(parents=True)
    (models_src / "model.txt").write_text(
        "SYNTHETIC_MODEL_WEIGHTS_V1\n", encoding="utf-8"
    )

    # -------------------------------------------------------------------------
    # Step 3: Materializer plan
    # -------------------------------------------------------------------------
    dest_workspace = tmp_path / "canonical_operational_workspace"
    req = ow.WorkspaceRequest(
        repo_root=repo_dir,
        code_sha=code_sha,
        source_stores={
            "raw": raw_src,
            "processed": processed_src,
            "models": models_src,
        },
        destination=dest_workspace,
        margin_bytes=1024 * 1024,
    )
    plan_result = ow.plan(req)
    assert (
        plan_result["overall_status"] == "PASS"
    ), f"Plan failed: {plan_result.get('findings')}"
    plan_id = plan_result["plan_id"]
    assert plan_id is not None

    # -------------------------------------------------------------------------
    # Step 4: Synthetic test authorization
    # -------------------------------------------------------------------------
    confirm_plan_id = plan_id

    # -------------------------------------------------------------------------
    # Step 5: Physical temp workspace materialization
    # -------------------------------------------------------------------------
    mat_result = ow.materialize(req, confirm_plan_id=confirm_plan_id)
    assert (
        mat_result["overall_status"] == "PASS"
    ), f"Materialize failed: {mat_result.get('findings')}"
    assert mat_result["promotion_status"] == "PROMOTED"
    assert dest_workspace.is_dir()
    manifest_file = dest_workspace / ow.MANIFEST_NAME
    assert manifest_file.is_file()

    # -------------------------------------------------------------------------
    # Step 6: Verify manifest
    # -------------------------------------------------------------------------
    ws_ver = verify_workspace_manifest(
        manifest_file,
        expected_code_sha=code_sha,
        expected_workspace_root=dest_workspace,
    )
    assert ws_ver["status"] == "PASS"
    assert ws_ver["verification_state"] == "VERIFIED"
    assert ws_ver["code_sha"] == code_sha
    assert ws_ver["manifest_fingerprint"] is not None

    # -------------------------------------------------------------------------
    # Step 7: Workspace Safety Guard PASS
    # -------------------------------------------------------------------------
    guard_res = ws.check_workspace(
        ws.GuardRequest(
            mode=ws.Mode.OPERATIONAL_REAL_DATA,
            code_root=dest_workspace,
            expected_code_sha=code_sha,
            expected_tree_sha=tree_sha,
            stores={
                "raw": dest_workspace / "data" / "raw",
                "processed": dest_workspace / "data" / "processed",
                "models": dest_workspace / "models",
            },
        )
    )
    assert (
        guard_res["overall_status"] == "PASS"
    ), f"Guard failed: {guard_res.get('failures')}"

    # -------------------------------------------------------------------------
    # Step 8: Create synthetic DATA_PLANE_MANIFEST (authoritative nested schema v1)
    # Readiness: PREPARED (the highest valid producer state — READY is not valid per
    # producer contract at cd9c01408059961fb30e4b6321429a018e4a0df5).
    # OLD ASSUMPTION CORRECTED: READY->PASS was incorrect; PREPARED->PREPARED is right.
    # -------------------------------------------------------------------------
    data_manifest_file = tmp_path / "DATA_PLANE_MANIFEST.json"
    _firms_sha = "a" * 40
    _dmc_sha = "b" * 40
    _model_sha = "c" * 40
    dm_identity = {
        "schema_version": 1,
        "kind": "DATA_PLANE_MANIFEST",
        "data_readiness_status": "PREPARED",  # highest valid producer state
        "data_ready_for_scoring": "NOT_EVALUATED",
        "independent_approval": "PENDING",
        "authorizations": {
            "attempt2": False,
            "writers": False,
            "telegram": False,
            "schedule": False,
        },
        "code_identity": {
            "sha": code_sha,
            "tree": tree_sha,
            "clean": True,
            "status": "PASS",
        },
        "components": {
            "firms": {"sha": _firms_sha, "files": [], "status": "PASS"},
            "dmc": {"sha": _dmc_sha, "files": [], "status": "PASS"},
            "scoring_inputs": {"sha": "d" * 40, "files": [], "status": "PASS"},
        },
        "model": {"sha256": _model_sha, "status": "PASS"},
        "topography": {
            "table_sha256": "e" * 64,
            "grid_sha256": "f" * 64,
            "status": "PASS",
            "cells": 50,
        },
        "baseline": {"sha256": "g" * 64, "status": "PASS"},
        "source_evidence": {
            "sha256": "h" * 64,
            "status": "PASS",
        },  # required for PREPARED
        "expected_current": {"firms": "ABSENT", "dmc": "ABSENT"},
        "current_state": {
            "firms": "ABSENT",
            "dmc": "ABSENT",
        },  # must match expected_current
        "findings": [],  # must be empty for PREPARED
    }
    dm_fp = compute_data_manifest_fingerprint(dm_identity)
    dm_data = {
        "schema_version": 1,
        "created_at": "2026-09-25T19:00:00+00:00",
        "identity": dm_identity,
        "fingerprint": dm_fp,
        "operational_roots": {
            "workspace": str(dest_workspace),
            "code": str(dest_workspace),
        },
        "observation": {
            "start": "2026-09-25T19:00:00+00:00",
            "end": "2026-09-25T19:00:01+00:00",
        },
    }
    data_manifest_file.write_text(json.dumps(dm_data, indent=2), encoding="utf-8")

    dm_ver = verify_data_plane_manifest(data_manifest_file, expected_code_sha=code_sha)
    assert (
        dm_ver["status"] == "PREPARED"
    ), f"Data manifest verification failed: {dm_ver['findings']}"
    assert dm_ver["prepared"] is True  # PREPARED = producer-valid, data staged
    assert dm_ver["ready"] is False  # ready is always False — no producer READY state

    # -------------------------------------------------------------------------
    # Step 9: Attempt2 Operator init
    # -------------------------------------------------------------------------
    evidence_root = tmp_path / "evidence"
    run_id = "SAPI-ATTEMPT2-RC1-SYNTHETIC"
    op = Attempt2Operator.init_run(
        evidence_root=evidence_root,
        repo=dest_workspace,
        expected_code_sha=code_sha,
        run_id=run_id,
        workspace_manifest=manifest_file,
        data_plane_manifest=data_manifest_file,
    )
    assert op.run.current_state() == Attempt2State.NEW
    status = op.status()
    assert status["run_id"] == run_id
    assert status["workspace_manifest_fingerprint"] == ws_ver["manifest_fingerprint"]
    assert status["data_plane_manifest_fingerprint"] == dm_fp

    # RC1 Execution Context check
    rc_ctx = status.get("rc_execution_context")
    assert rc_ctx is not None
    assert rc_ctx["expected_code_sha"] == code_sha
    assert rc_ctx["workspace_manifest_fingerprint"] == ws_ver["manifest_fingerprint"]
    assert rc_ctx["data_plane_manifest_fingerprint"] == dm_fp

    # -------------------------------------------------------------------------
    # Step 10 & 11: Preflight PASS and synthetic quiescence QUIESCENT
    # -------------------------------------------------------------------------
    synthetic_preflight_snapshot = {
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
        "workspace_manifest": {
            "status": "PASS",
            "fingerprint": ws_ver["manifest_fingerprint"],
        },
        "data_plane": {
            "status": "PREPARED",
            "ready": False,  # always False — no producer READY state
            "prepared": True,
            "manifest_fingerprint": dm_fp,
        },
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

    pf_result = op.preflight(snapshot=synthetic_preflight_snapshot)
    assert pf_result["ready_for_authorization"] is True
    assert op.run.current_state() == Attempt2State.PREFLIGHT_READY

    # -------------------------------------------------------------------------
    # Step 12: Reach ATTEMPT2_AUTHORIZATION_REQUIRED
    # -------------------------------------------------------------------------
    op.advance()
    assert op.run.current_state() == Attempt2State.ATTEMPT2_AUTHORIZATION_REQUIRED
    nxt = op.next_action()
    assert nxt["gate"] == "ATTEMPT2_AUTHORIZATION"

    # -------------------------------------------------------------------------
    # Step 13: Explicit synthetic authorization
    # -------------------------------------------------------------------------
    auth_res = op.authorize("ATTEMPT2_AUTHORIZATION", actor="dan-synthetic-test")
    assert auth_res["authorized"] is True
    assert op.run.current_state() == Attempt2State.ATTEMPT2_AUTHORIZED

    op.advance()
    assert op.run.current_state() == Attempt2State.FIRMS_WRITER_REQUIRED
    op.authorize("FIRMS_WRITER_AUTHORIZATION", actor="dan-synthetic-test")
    assert op.run.current_state() == Attempt2State.FIRMS_RESULT_PENDING

    # -------------------------------------------------------------------------
    # Step 14 & 15: Synthetic FIRMS writer-result import & validation PASS
    # -------------------------------------------------------------------------
    firms_payload = {
        "run_id": run_id,
        "step": "firms",
        "code_sha": code_sha,
        "exit_code": 0,
        "started_at": "2026-09-25T15:10:00Z",
        "finished_at": "2026-09-25T15:11:00Z",
        "operation_success": True,
        "stdout": "FIRMS synthetic refresh completed successfully",
        "stderr": "",
        "sanitization_status": "PASS",
        "firms_current_after": {"present": True, "state": "PRESENT"},
        "files_added": ["data/raw/firms_sample.parquet"],
    }
    firms_imp = op.import_result("firms", firms_payload)
    assert firms_imp["result"] == "PASS"
    assert op.run.current_state() == Attempt2State.FIRMS_VALIDATED

    # -------------------------------------------------------------------------
    # Step 16 & 17: Synthetic DMC writer-result import & validation PASS
    # -------------------------------------------------------------------------
    op.advance()
    assert op.run.current_state() == Attempt2State.DMC_WRITER_REQUIRED
    op.authorize("DMC_WRITER_AUTHORIZATION", actor="dan-synthetic-test")
    assert op.run.current_state() == Attempt2State.DMC_RESULT_PENDING

    dmc_payload = {
        "run_id": run_id,
        "step": "dmc",
        "code_sha": code_sha,
        "exit_code": 0,
        "started_at": "2026-09-25T15:12:00Z",
        "finished_at": "2026-09-25T15:13:00Z",
        "quality_ok": True,
        "pointer_ok": True,
        "sanitization_status": "PASS",
        "dmc_current_after": {"present": True},
        "attempt1_modified": False,
        "stdout": "DMC synthetic refresh completed successfully",
        "stderr": "",
        "files_added": ["data/processed/dmc_sample.parquet"],
    }
    dmc_imp = op.import_result("dmc", dmc_payload)
    assert dmc_imp["result"] == "PASS"
    assert op.run.current_state() == Attempt2State.DMC_VALIDATED

    # -------------------------------------------------------------------------
    # Step 18: Synthetic ScoringInputs / scoring result
    # -------------------------------------------------------------------------
    op.advance()
    assert op.run.current_state() == Attempt2State.SCORING_READY

    scoring_payload = {
        "run_id": run_id,
        "step": "scoring",
        "code_sha": code_sha,
        "exit_code": 0,
        "started_at": "2026-09-25T15:14:00Z",
        "finished_at": "2026-09-25T15:15:00Z",
        "cells": [
            {"cell_id": f"VP-{i:03d}", "score": 1.0 - i * 0.01, "rank": i}
            for i in range(1, 51)
        ],
        "inputs_fingerprint": "c" * 64,
        "frozen_fingerprint": "33c2eacc49bd0cc130928b5bd182ec523e63614f0e3dd97a129a8d4657f231ff",
        "model_sha": "ac017bef1f42a30ac74ba3e3787368c4418798b2d562adcfba01c923cff2173f",
        "confuse_fingerprints": False,
        "stdout": "Scoring inference engine completed successfully",
        "stderr": "",
    }
    scoring_imp = op.import_result("scoring", scoring_payload)
    assert scoring_imp["result"] == "PASS"
    assert op.run.current_state() == Attempt2State.SCORING_VALIDATED

    # -------------------------------------------------------------------------
    # Step 19: Synthetic bridge acceptance
    # -------------------------------------------------------------------------
    op.advance()
    assert op.run.current_state() == Attempt2State.BRIDGE_READY

    bridge_payload = {
        "run_id": run_id,
        "step": "bridge",
        "code_sha": code_sha,
        "exit_code": 0,
        "started_at": "2026-09-25T15:16:00Z",
        "finished_at": "2026-09-25T15:16:30Z",
        "http_status": 200,
        "body": {
            "status": "ok",
            "cells": [
                {"cell_id": f"VP-{i:03d}", "score": 1.0 - i * 0.01, "rank": i}
                for i in range(1, 51)
            ],
            "inputs_fingerprint": "c" * 64,
        },
        "stdout": "Bridge POST 200 OK",
        "stderr": "",
    }
    bridge_imp = op.import_result("bridge", bridge_payload)
    assert bridge_imp["result"] == "PASS"
    assert op.run.current_state() == Attempt2State.BRIDGE_VALIDATED

    # -------------------------------------------------------------------------
    # Step 20: Synthetic OUTPUT manifest/artifact acceptance
    # -------------------------------------------------------------------------
    pred_dir = dest_workspace / "data" / "predictions"
    pred_dir.mkdir(parents=True, exist_ok=True)
    score_file = pred_dir / "synthetic_scores.parquet"
    score_file.write_text("synthetic prediction score bytes\n", encoding="utf-8")
    score_sha = sha256_file(score_file)

    output_manifest_file = tmp_path / "OUTPUT-PLANE-MANIFEST.json"
    op_data = {
        "schema_version": 1,
        "output_contract_version": "v1.0.0",
        "accepted_score_artifact_path": str(score_file),
        "accepted_score_artifact_sha256": score_sha,
        "presentation_contract_status": "READY",
    }
    op_fp = compute_output_manifest_fingerprint(op_data)
    op_data["manifest_fingerprint"] = op_fp
    output_manifest_file.write_text(json.dumps(op_data, indent=2), encoding="utf-8")

    out_ver = op.accept_output_manifest(
        output_manifest_file, score_artifact_path=score_file
    )
    assert out_ver["status"] == "PASS"
    assert out_ver["manifest_fingerprint"] == op_fp

    # Step through n8n manual review
    op.advance()
    assert op.run.current_state() == Attempt2State.N8N_MANUAL_READY
    n8n_payload = {
        "run_id": run_id,
        "step": "n8n",
        "code_sha": code_sha,
        "exit_code": 0,
        "started_at": "2026-09-25T15:17:00Z",
        "finished_at": "2026-09-25T15:17:30Z",
        "schedule_enabled": False,
        "telegram_sent": False,
        "score_path_ok": True,
        "fail_closed_cases": {
            "prototype_unavailable": True,
            "data_unavailable": True,
            "internal_error": True,
        },
    }
    n8n_imp = op.import_result("n8n", n8n_payload)
    assert n8n_imp["result"] == "PASS"
    assert op.run.current_state() == Attempt2State.N8N_VALIDATED

    op.advance()
    assert op.run.current_state() == Attempt2State.ACCEPTANCE_READY

    # -------------------------------------------------------------------------
    # Step 21: Final Attempt2 state: ACCEPTED
    # -------------------------------------------------------------------------
    op.advance()
    assert op.run.current_state() == Attempt2State.ACCEPTED
    status_final = op.status()
    assert status_final["state"] == "ACCEPTED"
    assert status_final["acceptance"]["software_operational"] is True
    assert status_final["acceptance"]["scientific_model_validation"] is False

    rep = op.report()
    assert rep["report"]["state"] == "ACCEPTED"
    assert (evidence_root / run_id / "reports" / "ATTEMPT2-REPORT.md").is_file()

    # Final verification of RC1 Execution Context
    rc1_file = evidence_root / run_id / "identity" / "rc1_execution_context.json"
    assert rc1_file.is_file()
    rc1_data = json.loads(rc1_file.read_text(encoding="utf-8"))
    assert rc1_data["expected_code_sha"] == code_sha
    assert rc1_data["workspace_manifest_fingerprint"] == ws_ver["manifest_fingerprint"]
    assert rc1_data["data_plane_manifest_fingerprint"] == dm_fp
    assert rc1_data["output_plane_manifest_fingerprint"] == op_fp
    assert rc1_data["run_id"] == run_id

"""Release Candidate preparation status check (Phase L & L1).

Summarizes whether we are ready to BEGIN real RC1 preparation.
Answers:
- CODE IDENTITY READY?
- WORKSPACE READY?
- DATA MANIFEST READY?
- QUIESCENCE READY?
- OUTPUT CONTRACT KNOWN?
- HUMAN ACTION REQUIRED? (ONE highest-priority action)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.ops.attempt2_operator.collectors.git_state import collect_git_state
from src.ops.attempt2_operator.collectors.runtime import collect_runtime
from src.ops.attempt2_operator.data_plane_manifest import verify_data_plane_manifest
from src.ops.attempt2_operator.output_plane_manifest import verify_output_plane_manifest
from src.ops.attempt2_operator.quiescence.collect import collect_quiescence
from src.ops.attempt2_operator.workspace_manifest import verify_workspace_manifest
from src.ops.attempt2_operator.workspace_safety import check_workspace_safety


def collect_rc_status(
    *,
    repo: Path,
    expected_code_sha: str | None = None,
    workspace_manifest_path: Path | str | None = None,
    data_plane_manifest_path: Path | str | None = None,
    output_manifest_path: Path | str | None = None,
) -> dict[str, Any]:
    observed_at = datetime.now(timezone.utc).isoformat()
    repo_path = Path(repo).resolve()

    # 1. Code Identity
    git = collect_git_state(repo_path, expected_code_sha=expected_code_sha)
    code_ready = (
        git.get("dirty") is False
        and git.get("status") not in ("UNKNOWN", "ERROR")
        and (git.get("sha_match") is True if expected_code_sha else bool(git.get("head_sha")))
    )

    # 2. Workspace Readiness
    if workspace_manifest_path:
        ws_ver = verify_workspace_manifest(
            workspace_manifest_path,
            expected_code_sha=expected_code_sha,
        )
        ws_status = ws_ver.get("status", "FAIL")
        ws_ready = ws_status == "PASS"
        ws_evidence = ws_ver
    else:
        # Fall back to checking repo directly under OPERATIONAL_REAL_DATA
        ws_res = check_workspace_safety(
            repo_path,
            expected_code_sha=expected_code_sha,
        )
        ws_status = ws_res.get("status", "FAIL")
        ws_ready = ws_status == "PASS"
        ws_evidence = ws_res

    # 3. Data Manifest Readiness
    dm_res = verify_data_plane_manifest(
        data_plane_manifest_path,
        expected_code_sha=expected_code_sha,
    )
    dm_status = dm_res.get("status", "NOT_AVAILABLE")
    dm_ready = dm_status == "PASS"
    # PREPARED = valid schema, data staged, not yet READY for scoring.
    # Accepted for informational purposes; does not satisfy all_prerequisites_ready.
    dm_accepted = dm_status in ("PASS", "PREPARED")

    # 4. Quiescence
    runtime = collect_runtime()
    quiescence = collect_quiescence(
        repo=repo_path,
        data_root=repo_path / "data",
        runtime=runtime,
    )
    q_status = quiescence.get("status", "INCOMPLETE")
    q_ready = q_status == "QUIESCENT"

    # 5. Output Contract Known
    op_res = verify_output_plane_manifest(output_manifest_path)
    op_status = op_res.get("status", "NOT_AVAILABLE")
    op_known = op_status == "PASS"

    # 6. Human Action Required (ONE highest-priority action)
    if not code_ready:
        if git.get("dirty"):
            one_action = {
                "priority": 1,
                "code": "DIRTY_WORKTREE",
                "next": "Commit or stash working tree changes to achieve clean code state.",
            }
        elif git.get("sha_match") is False:
            one_action = {
                "priority": 1,
                "code": "CODE_SHA_MISMATCH",
                "next": f"Checkout expected code SHA ({expected_code_sha}); currently at {git.get('head_sha')}.",
            }
        else:
            one_action = {
                "priority": 1,
                "code": "CHECK_GIT_IDENTITY",
                "next": "Ensure valid clean Git checkout with known commit SHA.",
            }
    elif not ws_ready:
        if workspace_manifest_path:
            one_action = {
                "priority": 2,
                "code": "WORKSPACE_MANIFEST_INVALID",
                "next": f"Workspace manifest verification failed: {ws_evidence.get('findings', [{}])[0].get('message', 'Check workspace safety.')}",
            }
        else:
            one_action = {
                "priority": 2,
                "code": "MATERIALIZE_WORKSPACE",
                "next": "Materialize canonical operational workspace via: python -m src.ops.operational_workspace plan ...",
            }
    elif not q_ready:
        top_finding = quiescence.get("highest_priority_finding") or {}
        remediation = top_finding.get("remediation")
        finding_id = top_finding.get("id", "OPERATIONAL_NOT_QUIESCENT")
        if remediation:
            one_action = {
                "priority": 3,
                "code": finding_id,
                "next": remediation,
            }
        else:
            one_action = {
                "priority": 3,
                "code": finding_id,
                "next": "Achieve quiescence: ensure n8n container is STOPPED, no active refresh writers, no stale locks.",
            }
    elif not dm_ready and not dm_accepted:
        one_action = {
            "priority": 4,
            "code": "AWAIT_DATA_PLANE_MANIFEST",
            "next": "Provide verified DATA_PLANE_MANIFEST from Astra: --data-readiness-manifest <path>.",
        }
    elif not dm_ready and dm_accepted:
        one_action = {
            "priority": 4,
            "code": "AWAIT_DATA_PLANE_READY",
            "next": f"Data plane manifest accepted (status={dm_status}). Await data_readiness_status=READY before initializing Attempt 2.",
        }
    else:
        one_action = {
            "priority": 5,
            "code": "READY_TO_INITIALIZE_ATTEMPT2",
            "next": f"Prerequisites ready. Initialize Attempt 2: python -m src.ops.attempt2_operator init --expected-code-sha {expected_code_sha or git.get('head_sha')}",
        }

    all_ready = code_ready and ws_ready and q_ready and dm_ready

    result = {
        "schema_version": 1,
        "observed_at": observed_at,
        "repo": str(repo_path),
        "expected_code_sha": expected_code_sha,
        "all_prerequisites_ready": all_ready,
        "questions": {
            "code_identity_ready": code_ready,
            "workspace_ready": ws_ready,
            "data_manifest_ready": dm_ready,
            "quiescence_ready": q_ready,
            "output_contract_known": op_known,
        },
        "details": {
            "code": {
                "ready": code_ready,
                "head_sha": git.get("head_sha"),
                "dirty": git.get("dirty"),
                "expected_code_sha": expected_code_sha,
                "sha_match": git.get("sha_match"),
            },
            "workspace": {
                "ready": ws_ready,
                "status": ws_status,
                "manifest_path": str(workspace_manifest_path) if workspace_manifest_path else None,
            },
            "data_manifest": {
                "ready": dm_ready,
                "accepted": dm_accepted,
                "status": dm_status,
                "manifest_path": str(data_plane_manifest_path) if data_plane_manifest_path else None,
                "data_readiness_status": dm_res.get("data_readiness_status"),
                "writers_authorized": dm_res.get("writers_authorized", False),
                "attempt2_authorized": dm_res.get("attempt2_authorized", False),
                "fingerprint_match": dm_res.get("fingerprint_match", False),
            },
            "quiescence": {
                "ready": q_ready,
                "status": q_status,
                "highest_priority_finding": quiescence.get("highest_priority_finding"),
                "n8n": quiescence.get("n8n"),
                "writers": quiescence.get("writers"),
                "locks": quiescence.get("locks"),
                "telegram": quiescence.get("telegram"),
            },
            "output_contract": {
                "known": op_known,
                "status": op_status,
                "manifest_path": str(output_manifest_path) if output_manifest_path else None,
            },
        },
        "human_action_required": one_action,
    }
    return result


def format_rc_status_human(status: dict[str, Any]) -> str:
    q = status["questions"]
    det = status["details"]
    act = status["human_action_required"]

    lines = [
        "============================================================",
        "SAPI RELEASE CANDIDATE 1 — OPERATIONS PLANE STATUS",
        "============================================================",
        f"Observed at:        {status['observed_at']}",
        f"Repository:         {status['repo']}",
        f"Expected Code SHA:  {status.get('expected_code_sha') or 'Not specified'}",
        "------------------------------------------------------------",
        f"1. CODE IDENTITY READY?    {'[PASS]' if q['code_identity_ready'] else '[BLOCKED]'} (HEAD: {det['code']['head_sha']}, dirty: {det['code']['dirty']})",
        f"2. WORKSPACE READY?        {'[PASS]' if q['workspace_ready'] else '[BLOCKED]'} (status: {det['workspace']['status']})",
        f"3. DATA MANIFEST READY?    {'[PASS]' if q['data_manifest_ready'] else '[BLOCKED]'} (status: {det['data_manifest']['status']})",
        f"4. QUIESCENCE READY?       {'[PASS]' if q['quiescence_ready'] else '[BLOCKED]'} (status: {det['quiescence']['status']})",
        f"5. OUTPUT CONTRACT KNOWN?  {'[YES]' if q['output_contract_known'] else '[NOT_AVAILABLE]'} (status: {det['output_contract']['status']})",
        "------------------------------------------------------------",
        "HUMAN ACTION REQUIRED (HIGHEST PRIORITY):",
        f"[{act['code']}] {act['next']}",
        "============================================================",
    ]
    return "\n".join(lines)

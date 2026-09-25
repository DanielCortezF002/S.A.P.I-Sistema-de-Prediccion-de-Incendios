"""Assemble canonical real read-only preflight object."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.ops.attempt2_operator.collectors.artifacts import collect_artifact_identities
from src.ops.attempt2_operator.collectors.credentials import collect_credential_presence
from src.ops.attempt2_operator.collectors.dmc_current import collect_dmc_current
from src.ops.attempt2_operator.collectors.firms_current import collect_firms_current
from src.ops.attempt2_operator.collectors.git_state import collect_git_state
from src.ops.attempt2_operator.collectors.runtime import collect_runtime
from src.ops.attempt2_operator.collectors.store_state import collect_store_state
from src.ops.attempt2_operator.workspace_safety import check_workspace_safety


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def collect_real_preflight(
    *,
    repo: Path,
    run_id: str,
    expected_code_sha: str | None,
    tool_results: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    observed_at = _utc_now()
    git = collect_git_state(repo, expected_code_sha=expected_code_sha)
    firms_store = collect_store_state(repo / "data" / "processed" / "firms")
    dmc_store = collect_store_state(repo / "data" / "processed" / "dmc" / "330007")
    firms = collect_firms_current(repo)
    dmc = collect_dmc_current(repo)
    artifacts = collect_artifact_identities(repo)
    credentials = collect_credential_presence()
    runtime = collect_runtime()
    workspace = check_workspace_safety(repo)

    warnings: list[str] = []
    failures: list[str] = []

    if git.get("sha_match") is False:
        failures.append("expected_code_sha_mismatch")
    if git.get("dirty") is True:
        failures.append("dirty_worktree")
    if git.get("status") == "UNKNOWN":
        warnings.append("git_state_unknown")
    if firms.get("state") == "UNKNOWN":
        warnings.append("firms_current_unknown")
    if dmc.get("state") == "UNKNOWN":
        warnings.append("dmc_current_unknown")
    if artifacts.get("overall_status") == "FAIL":
        failures.append("artifact_identity_fail")
    elif artifacts.get("overall_status") in ("NOT_AVAILABLE", "INCOMPLETE"):
        warnings.append("artifact_identity_incomplete")
    if workspace.get("status") == "NOT_AVAILABLE":
        warnings.append("workspace_safety_not_available")
    elif workspace.get("status") == "FAIL":
        failures.append("workspace_safety_fail")

    if failures:
        overall = "FAIL"
    elif warnings or git.get("status") == "INCOMPLETE":
        overall = "INCOMPLETE"
    elif git.get("sha_match") is True and git.get("dirty") is False:
        overall = "PASS"
    else:
        overall = "INCOMPLETE"

    return {
        "schema_version": 1,
        "run_id": run_id,
        "expected_code_sha": expected_code_sha,
        "observed_code_sha": git.get("head_sha"),
        "tree_sha": git.get("tree_sha"),
        "dirty": git.get("dirty"),
        "git": git,
        "stores": {
            "firms": firms_store,
            "dmc": dmc_store,
        },
        "firms": {"current": firms, **{k: v for k, v in firms.items() if k != "state"}},
        "dmc": {"current": dmc, **{k: v for k, v in dmc.items() if k != "state"}},
        # Phase-2 flat convenience mirrors
        "firms_current_state": firms.get("state"),
        "dmc_current_state": dmc.get("state"),
        "artifacts": artifacts,
        "credentials": credentials,
        "runtime": runtime,
        "workspace_safety": workspace,
        "tool_results": tool_results or [],
        "warnings": warnings,
        "failures": failures,
        "overall_status": overall,
        "observed_at": observed_at,
        # Compatibility fields for Phase-1 validator snapshot shape
        "code": {
            "head_sha": git.get("head_sha"),
            "tree_sha": git.get("tree_sha"),
            "worktree_clean": git.get("worktree_clean"),
            "status_entries": git.get("status_entries") or [],
            "expected_main_sha": expected_code_sha,
            "observed_at": git.get("observed_at"),
            "path": git.get("code_root"),
        },
        "attempt1": {"preserve": True},
        "docker": runtime.get("docker") or {"status": "UNKNOWN"},
        "n8n": runtime.get("n8n") or {"status": "UNKNOWN"},
        "bridge": runtime.get("bridge") or {"status": "UNKNOWN"},
        "policy": {"human_authorization": False},
        "tests": {},
    }

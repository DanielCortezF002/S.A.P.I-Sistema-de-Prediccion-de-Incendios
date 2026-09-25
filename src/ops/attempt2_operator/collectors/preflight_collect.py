"""Assemble canonical real read-only preflight object with structured reasons."""

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
from src.ops.attempt2_operator.paths import StoreRoots
from src.ops.attempt2_operator.workspace_safety import check_workspace_safety

# Highest-priority first for `next` UX
REASON_PRIORITY = (
    "CODE_SHA_MISMATCH",
    "DIRTY_CODE",
    "WORKSPACE_SAFETY_FAIL",
    "ARTIFACT_IDENTITY_FAIL",
    "ARTIFACT_NOT_FOUND",
    "FIRMS_CURRENT_UNKNOWN",
    "DMC_CURRENT_UNKNOWN",
    "WORKSPACE_SAFETY_NOT_AVAILABLE",
    "ARTIFACT_INCOMPLETE",
    "GIT_STATE_UNKNOWN",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_reasons(
    *,
    failures: list[str],
    warnings: list[str],
) -> list[dict[str, str]]:
    """Structured reasons with codes for UX."""
    mapping = {
        "expected_code_sha_mismatch": ("CODE_SHA_MISMATCH", "FAIL"),
        "dirty_worktree": ("DIRTY_CODE", "FAIL"),
        "workspace_safety_fail": ("WORKSPACE_SAFETY_FAIL", "FAIL"),
        "artifact_identity_fail": ("ARTIFACT_IDENTITY_FAIL", "FAIL"),
        "artifact_not_found": ("ARTIFACT_NOT_FOUND", "INCOMPLETE"),
        "artifact_identity_incomplete": ("ARTIFACT_INCOMPLETE", "INCOMPLETE"),
        "firms_current_unknown": ("FIRMS_CURRENT_UNKNOWN", "INCOMPLETE"),
        "dmc_current_unknown": ("DMC_CURRENT_UNKNOWN", "INCOMPLETE"),
        "workspace_safety_not_available": ("WORKSPACE_SAFETY_NOT_AVAILABLE", "INCOMPLETE"),
        "git_state_unknown": ("GIT_STATE_UNKNOWN", "INCOMPLETE"),
    }
    reasons: list[dict[str, str]] = []
    for key in failures + warnings:
        code, severity = mapping.get(key, (key.upper(), "INCOMPLETE"))
        reasons.append({"code": code, "severity": severity, "detail": key})
    # sort by REASON_PRIORITY
    order = {c: i for i, c in enumerate(REASON_PRIORITY)}
    reasons.sort(key=lambda r: order.get(r["code"], 999))
    return reasons


def highest_priority_reason(reasons: list[dict[str, str]]) -> dict[str, str] | None:
    return reasons[0] if reasons else None


def collect_real_preflight(
    *,
    repo: Path,
    run_id: str,
    expected_code_sha: str | None,
    tool_results: list[dict[str, Any]] | None = None,
    data_root: Path | None = None,
    models_root: Path | None = None,
    firms_baseline_path: Path | None = None,
    model_path: Path | None = None,
) -> dict[str, Any]:
    collection_started_at = _utc_now()
    roots = StoreRoots.from_repo(repo, data_root=data_root, models_root=models_root)
    git = collect_git_state(repo, expected_code_sha=expected_code_sha)
    firms_store = collect_store_state(roots.firms_store())
    dmc_store = collect_store_state(roots.dmc_store())
    firms = collect_firms_current(repo, pointer_path=roots.firms_store() / "CURRENT.json")
    dmc = collect_dmc_current(repo, pointer_path=roots.dmc_store() / "CURRENT.json")
    artifacts = collect_artifact_identities(
        repo,
        data_root=roots.data_root,
        models_root=roots.models_root,
        firms_baseline_path=firms_baseline_path,
        model_path=model_path,
    )
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
    elif artifacts.get("overall_status") == "NOT_AVAILABLE":
        warnings.append("artifact_not_found")
    elif artifacts.get("overall_status") == "INCOMPLETE":
        warnings.append("artifact_identity_incomplete")
    if workspace.get("status") == "NOT_AVAILABLE":
        warnings.append("workspace_safety_not_available")
    elif workspace.get("status") == "FAIL":
        failures.append("workspace_safety_fail")
    elif workspace.get("status") == "INCOMPLETE":
        warnings.append("workspace_safety_not_available")

    reasons = build_reasons(failures=failures, warnings=warnings)
    if failures:
        overall = "FAIL"
    elif warnings or git.get("status") == "INCOMPLETE":
        overall = "INCOMPLETE"
    elif expected_code_sha and git.get("sha_match") is True and git.get("dirty") is False:
        overall = "PASS"
    elif expected_code_sha is None and git.get("dirty") is False and git.get("head_sha"):
        overall = "INCOMPLETE"  # no expected SHA → incomplete by policy
        reasons.append(
            {
                "code": "EXPECTED_SHA_NOT_PROVIDED",
                "severity": "INCOMPLETE",
                "detail": "expected_code_sha_missing",
            }
        )
    else:
        overall = "INCOMPLETE"

    collection_finished_at = _utc_now()
    return {
        "schema_version": 2,
        "run_id": run_id,
        "expected_code_sha": expected_code_sha,
        "observed_code_sha": git.get("head_sha"),
        "tree_sha": git.get("tree_sha"),
        "dirty": git.get("dirty"),
        "git": git,
        "roots": {
            "code_root": str(roots.code_root),
            "data_root": str(roots.data_root),
            "models_root": str(roots.models_root),
        },
        "stores": {
            "firms": firms_store,
            "dmc": dmc_store,
        },
        "firms": {"current": firms, **{k: v for k, v in firms.items() if k != "state"}},
        "dmc": {"current": dmc, **{k: v for k, v in dmc.items() if k != "state"}},
        "firms_current_state": firms.get("state"),
        "dmc_current_state": dmc.get("state"),
        "artifacts": artifacts,
        "credentials": credentials,
        "runtime": runtime,
        "workspace_safety": workspace,
        "tool_results": tool_results or [],
        "warnings": warnings,
        "failures": failures,
        "reasons": reasons,
        "highest_priority_reason": highest_priority_reason(reasons),
        "overall_status": overall,
        "observed_at": collection_finished_at,
        "collection_started_at": collection_started_at,
        "collection_finished_at": collection_finished_at,
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

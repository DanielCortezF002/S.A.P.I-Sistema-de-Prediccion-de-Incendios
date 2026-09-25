"""Workspace manifest verifier for Attempt 2 handoff (CRR-OPS-02).

Validates canonical operational workspace manifests produced by
src.ops.operational_workspace, ensuring stale workspace rejection:
- code SHA changed / mismatch with expected code SHA
- tree changed unexpectedly
- store snapshot identity changed unexpectedly / store file drift
- manifest fingerprint mismatch / tampering
- workspace safety no longer PASS
- workspace path no longer matches manifest
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from src.ops import operational_workspace as ow
from src.ops import workspace_safety as ws

SCHEMA_VERSION = 1
WORKSPACE_MANIFEST_NAME = ow.MANIFEST_NAME


def compute_manifest_fingerprint(manifest_path_or_dict: Path | str | dict[str, Any]) -> str:
    """Deterministic SHA-256 fingerprint of the operational workspace manifest."""
    if isinstance(manifest_path_or_dict, (str, Path)):
        p = Path(manifest_path_or_dict)
        if p.is_dir():
            p = p / WORKSPACE_MANIFEST_NAME
        h = hashlib.sha256()
        with open(p, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    return hashlib.sha256(
        json.dumps(manifest_path_or_dict, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def verify_workspace_manifest(
    manifest_path: Path | str,
    *,
    expected_code_sha: str | None = None,
    expected_workspace_root: Path | str | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Strictly verify a materialized workspace against its manifest.

    Never silently passes on missing, invalid, drifting, or unsafe workspaces.
    """
    path = Path(manifest_path)
    if path.is_dir():
        path = path / WORKSPACE_MANIFEST_NAME

    observed_at = datetime.now(timezone.utc).isoformat()
    if not path.is_file():
        return {
            "status": "FAIL",
            "overall_status": "FAIL",
            "code": "WORKSPACE_MANIFEST_MISSING",
            "message": f"Workspace manifest file not found: {path}",
            "observed_at": observed_at,
            "manifest_path": str(path),
            "findings": [{"id": "WM-001", "code": "WORKSPACE_MANIFEST_MISSING", "severity": "FAIL", "message": f"Manifest not found: {path}"}],
        }

    try:
        manifest_bytes = path.read_bytes()
        manifest = json.loads(manifest_bytes.decode("utf-8"))
        fingerprint = hashlib.sha256(manifest_bytes).hexdigest()
    except Exception as exc:
        return {
            "status": "FAIL",
            "overall_status": "FAIL",
            "code": "WORKSPACE_MANIFEST_CORRUPT",
            "message": f"Failed to parse workspace manifest JSON: {exc}",
            "observed_at": observed_at,
            "manifest_path": str(path),
            "findings": [{"id": "WM-002", "code": "WORKSPACE_MANIFEST_CORRUPT", "severity": "FAIL", "message": str(exc)}],
        }

    findings: list[dict[str, Any]] = []

    # 1. Manifest structure and promotion state
    if manifest.get("schema_version") != ow.SCHEMA_VERSION:
        findings.append({
            "id": "WM-003",
            "code": "UNSUPPORTED_SCHEMA_VERSION",
            "severity": "FAIL",
            "message": f"Unsupported schema version: {manifest.get('schema_version')}",
        })

    promotion_status = manifest.get("promotion_status")
    if promotion_status != "PROMOTED":
        findings.append({
            "id": "WM-004",
            "code": "WORKSPACE_NOT_PROMOTED",
            "severity": "FAIL",
            "message": f"Workspace promotion_status is '{promotion_status}', expected 'PROMOTED'",
        })

    dest_declared = manifest.get("destination")
    if not dest_declared:
        findings.append({
            "id": "WM-005",
            "code": "WORKSPACE_DESTINATION_MISSING",
            "severity": "FAIL",
            "message": "Manifest does not declare destination workspace path",
        })
        dest_path = path.parent
    else:
        dest_path = Path(dest_declared)

    # 2. Workspace root existence and path matching
    if not dest_path.is_dir():
        findings.append({
            "id": "WM-006",
            "code": "WORKSPACE_ROOT_MISSING",
            "severity": "FAIL",
            "message": f"Declared workspace destination directory does not exist: {dest_path}",
        })

    if expected_workspace_root is not None:
        try:
            exp_norm = ws._norm(os.path.realpath(str(expected_workspace_root)))
            dest_norm = ws._norm(os.path.realpath(str(dest_path)))
            if exp_norm != dest_norm:
                findings.append({
                    "id": "WM-007",
                    "code": "WORKSPACE_PATH_MISMATCH",
                    "severity": "FAIL",
                    "message": f"Workspace path {dest_norm} != expected {exp_norm}",
                })
        except Exception as exc:
            findings.append({
                "id": "WM-007",
                "code": "WORKSPACE_PATH_MISMATCH",
                "severity": "FAIL",
                "message": f"Failed comparing workspace paths: {exc}",
            })

    # 3. Expected code SHA validation
    code_sha = (manifest.get("code_sha") or "").strip().lower()
    tree_sha = (manifest.get("tree_sha") or "").strip().lower()
    if expected_code_sha:
        exp_sha = expected_code_sha.strip().lower()
        if code_sha != exp_sha:
            findings.append({
                "id": "WM-008",
                "code": "WRONG_CODE_SHA",
                "severity": "FAIL",
                "message": f"Workspace code SHA {code_sha} != expected {exp_sha}",
            })

    # 4. Git code check at workspace root (if dir exists)
    if dest_path.is_dir():
        git_env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0"}
        try:
            head = subprocess.check_output(
                ["git", "--no-optional-locks", "-C", str(dest_path), "rev-parse", "HEAD"],
                text=True,
                env=git_env,
                stderr=subprocess.PIPE,
            ).strip().lower()
            got_tree = subprocess.check_output(
                ["git", "--no-optional-locks", "-C", str(dest_path), "rev-parse", "HEAD^{tree}"],
                text=True,
                env=git_env,
                stderr=subprocess.PIPE,
            ).strip().lower()
            status_out = subprocess.check_output(
                ["git", "--no-optional-locks", "-C", str(dest_path), "status", "--porcelain"],
                text=True,
                env=git_env,
                stderr=subprocess.PIPE,
            ).strip()

            if head != code_sha:
                findings.append({
                    "id": "WM-009",
                    "code": "WORKSPACE_GIT_HEAD_MISMATCH",
                    "severity": "FAIL",
                    "message": f"Destination Git HEAD {head} != manifest code_sha {code_sha}",
                })
            if got_tree != tree_sha:
                findings.append({
                    "id": "WM-010",
                    "code": "WORKSPACE_GIT_TREE_MISMATCH",
                    "severity": "FAIL",
                    "message": f"Destination Git tree {got_tree} != manifest tree_sha {tree_sha}",
                })
            # Check dirty entries (ignoring excluded store paths and manifest)
            if status_out:
                dirty_lines = [
                    line for line in status_out.splitlines()
                    if not any(ex.strip("/") in line for ex in ow.METADATA_EXCLUDES)
                ]
                if dirty_lines:
                    findings.append({
                        "id": "WM-011",
                        "code": "DIRTY_CODE",
                        "severity": "FAIL",
                        "message": f"Destination workspace has {len(dirty_lines)} uncommitted changes: {dirty_lines[:3]}",
                    })
        except (subprocess.CalledProcessError, OSError) as exc:
            findings.append({
                "id": "WM-012",
                "code": "WORKSPACE_GIT_ERROR",
                "severity": "FAIL",
                "message": f"Failed checking Git repository in destination workspace: {exc}",
            })

        # 5. Full operational workspace verification (store file rehash + workspace safety guard)
        op_ver = ow.verify(dest_path, environ=environ)
        if op_ver.get("drifted_files"):
            findings.append({
                "id": "WM-013",
                "code": "SOURCE_STORE_DRIFT",
                "severity": "FAIL",
                "message": f"Store drift detected in workspace: {op_ver['drifted_files'][:5]}",
                "drifted_files": op_ver["drifted_files"],
            })
        if op_ver.get("overall_status") != "PASS":
            for f in op_ver.get("findings", []):
                findings.append({
                    "id": f.get("id", "WM-014"),
                    "code": f.get("code", "WORKSPACE_SAFETY_FAIL"),
                    "severity": f.get("severity", "FAIL"),
                    "message": f.get("message", "Workspace safety check failed"),
                })

    status = "FAIL" if any(f.get("severity") == "FAIL" for f in findings) else "PASS"
    return {
        "status": status,
        "overall_status": status,
        "materialization_id": manifest.get("run_id"),
        "plan_id": manifest.get("plan_id"),
        "manifest_fingerprint": fingerprint,
        "workspace_root": str(dest_path),
        "code_sha": code_sha,
        "tree_sha": tree_sha,
        "stores": manifest.get("stores", {}),
        "source_store_paths": manifest.get("source_store_paths", {}),
        "verification_state": "VERIFIED" if status == "PASS" else "FAILED",
        "observed_at": observed_at,
        "findings": findings,
    }

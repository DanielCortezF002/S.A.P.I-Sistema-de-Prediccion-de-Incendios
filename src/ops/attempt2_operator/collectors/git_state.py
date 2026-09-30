"""Read-only git identity collector — no fetch/checkout/reset/stash."""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _git(repo: Path, args: list[str]) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        return proc.returncode, (proc.stdout or "").strip(), (proc.stderr or "").strip()
    except FileNotFoundError:
        return 127, "", "git_not_found"
    except subprocess.TimeoutExpired:
        return 124, "", "git_timeout"


def collect_git_state(
    repo: Path,
    *,
    expected_code_sha: str | None = None,
) -> dict[str, Any]:
    """Collect HEAD/tree/branch/dirty/origin/main (locally known only)."""
    observed_at = _utc_now()
    repo = Path(repo)
    if not (repo / ".git").exists() and not (repo / ".git").is_file():
        # worktree .git may be a file
        if not any((repo / p).exists() for p in (".git",)):
            return {
                "code_root": str(repo),
                "head_sha": None,
                "tree_sha": None,
                "branch": None,
                "dirty": None,
                "origin_main_sha": None,
                "expected_code_sha": expected_code_sha,
                "sha_match": None,
                "status": "UNKNOWN",
                "observed_at": observed_at,
                "detail": "not_a_git_repo",
            }

    rc_h, head, _ = _git(repo, ["rev-parse", "HEAD"])
    rc_t, tree, _ = _git(repo, ["rev-parse", "HEAD^{tree}"])
    rc_b, branch, _ = _git(repo, ["branch", "--show-current"])
    rc_s, status, _ = _git(repo, ["status", "--porcelain"])
    # locally-known origin/main — no fetch
    rc_o, origin_main, _ = _git(repo, ["rev-parse", "origin/main"])

    head_sha = head if rc_h == 0 and head else None
    tree_sha = tree if rc_t == 0 and tree else None
    dirty: bool | None
    if rc_s != 0:
        dirty = None
    else:
        dirty = bool(status.strip())

    sha_match: bool | None = None
    if expected_code_sha and head_sha:
        sha_match = head_sha.lower() == expected_code_sha.lower()
    elif expected_code_sha and not head_sha:
        sha_match = False

    status_label = "PASS"
    if head_sha is None:
        status_label = "UNKNOWN"
    elif expected_code_sha and sha_match is False:
        status_label = "FAIL"
    elif dirty is True:
        status_label = "FAIL"
    elif dirty is None:
        status_label = "INCOMPLETE"

    return {
        "code_root": str(repo.resolve()),
        "head_sha": head_sha,
        "tree_sha": tree_sha,
        "branch": branch if rc_b == 0 else None,
        "dirty": dirty,
        "status_entries": status.splitlines() if rc_s == 0 and status else [],
        "origin_main_sha": origin_main if rc_o == 0 else None,
        "expected_code_sha": expected_code_sha,
        "sha_match": sha_match,
        "worktree_clean": (not dirty) if dirty is not None else None,
        "status": status_label,
        "observed_at": observed_at,
    }

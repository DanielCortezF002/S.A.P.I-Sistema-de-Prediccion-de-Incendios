"""Read-only store path inspection — no writes, no whole-store hashing."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def collect_store_state(
    requested_path: str | Path,
    *,
    current_name: str = "CURRENT.json",
    lock_globs: tuple[str, ...] = ("*.lock", ".lock", "LOCK"),
) -> dict[str, Any]:
    """Inspect a store directory read-only."""
    observed_at = _utc_now()
    requested = Path(requested_path)
    try:
        resolved = requested.resolve()
    except OSError:
        return {
            "requested_path": str(requested),
            "resolved_path": None,
            "exists": False,
            "file_count": None,
            "current": {"state": "UNKNOWN", "known": False, "present": None},
            "lock": {"state": "UNKNOWN", "paths": []},
            "observed_at": observed_at,
            "status": "UNKNOWN",
        }

    exists = resolved.exists()
    if not exists:
        return {
            "requested_path": str(requested),
            "resolved_path": str(resolved),
            "exists": False,
            "file_count": 0,
            "current": {
                "state": "ABSENT",
                "known": True,
                "present": False,
                "path": None,
            },
            "lock": {"state": "ABSENT", "paths": []},
            "observed_at": observed_at,
            "status": "ABSENT",
        }

    file_count = 0
    try:
        for p in resolved.rglob("*"):
            if p.is_file():
                file_count += 1
                if file_count > 100_000:
                    break
    except OSError:
        return {
            "requested_path": str(requested),
            "resolved_path": str(resolved),
            "exists": True,
            "file_count": None,
            "current": {"state": "UNKNOWN", "known": False, "present": None},
            "lock": {"state": "UNKNOWN", "paths": []},
            "observed_at": observed_at,
            "status": "UNKNOWN",
            "detail": "unreadable",
        }

    current_path = resolved / current_name
    if current_path.is_file():
        current = {
            "state": "PRESENT",
            "known": True,
            "present": True,
            "path": str(current_path),
        }
    else:
        # directory exists but no CURRENT → known ABSENT pointer
        current = {
            "state": "ABSENT",
            "known": True,
            "present": False,
            "path": str(current_path),
        }

    lock_paths: list[str] = []
    try:
        for pattern in lock_globs:
            lock_paths.extend(str(p) for p in resolved.glob(pattern) if p.is_file())
            lock_paths.extend(str(p) for p in resolved.rglob(pattern) if p.is_file())
    except OSError:
        lock = {"state": "UNKNOWN", "paths": []}
    else:
        # de-dupe
        lock_paths = sorted(set(lock_paths))
        lock = {
            "state": "PRESENT" if lock_paths else "ABSENT",
            "paths": lock_paths[:20],
        }

    return {
        "requested_path": str(requested),
        "resolved_path": str(resolved),
        "exists": True,
        "file_count": file_count,
        "current": current,
        "lock": lock,
        "observed_at": observed_at,
        "status": "PASS",
    }

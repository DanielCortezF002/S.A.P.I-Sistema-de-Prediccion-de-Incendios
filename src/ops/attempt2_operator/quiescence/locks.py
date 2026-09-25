"""Read-only FIRMS/DMC refresh lock inspection — never delete locks."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from src.refresh.lock import STALE_AFTER

ACTIVE_LOCK = "ACTIVE_LOCK"
STALE_LOCK = "STALE_LOCK"
NO_LOCK = "NO_LOCK"
UNKNOWN = "UNKNOWN"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _pid_alive(pid: int | None) -> bool | None:
    if pid is None:
        return None
    try:
        pid_i = int(pid)
    except (TypeError, ValueError):
        return None
    if pid_i <= 0:
        return False
    if sys.platform.startswith("win"):
        try:
            import ctypes

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(  # type: ignore[attr-defined]
                PROCESS_QUERY_LIMITED_INFORMATION, False, pid_i
            )
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)  # type: ignore[attr-defined]
                return True
            # ERROR_ACCESS_DENIED (5) often means process exists
            err = ctypes.windll.kernel32.GetLastError()  # type: ignore[attr-defined]
            if err == 5:
                return True
            return False
        except Exception:  # noqa: BLE001
            return None
    try:
        os.kill(pid_i, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return None


def inspect_lock_file(path: Path, *, now: datetime | None = None) -> dict[str, Any]:
    """Classify a single `.refresh.lock` file."""
    now = now or _utc_now()
    observed_at = now.isoformat()
    result: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "observed_at": observed_at,
        "mutations": False,
    }
    if not path.exists():
        result["classification"] = NO_LOCK
        return result
    try:
        raw = path.read_text(encoding="utf-8")
        meta = json.loads(raw) if raw.strip() else {}
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        result["classification"] = UNKNOWN
        result["detail"] = type(exc).__name__
        return result

    if not isinstance(meta, dict):
        result["classification"] = UNKNOWN
        result["detail"] = "lock_metadata_not_object"
        return result

    result["metadata"] = {
        "pid": meta.get("pid"),
        "host": meta.get("host"),
        "started_at": meta.get("started_at"),
        "command": meta.get("command"),
    }
    pid = meta.get("pid")
    alive = _pid_alive(pid if isinstance(pid, int) else None)
    result["pid_alive"] = alive

    age: timedelta | None = None
    try:
        age = now - datetime.fromisoformat(str(meta["started_at"]))
        result["age_seconds"] = age.total_seconds()
    except (KeyError, TypeError, ValueError):
        result["age_seconds"] = None

    stale_by_age = age is None or age > STALE_AFTER
    if alive is True and not stale_by_age:
        result["classification"] = ACTIVE_LOCK
    elif alive is False or stale_by_age:
        result["classification"] = STALE_LOCK
        result["stale_reason"] = (
            "pid_dead" if alive is False else "age_exceeded_or_unknown_started_at"
        )
    else:
        # pid liveness unknown
        if stale_by_age:
            result["classification"] = STALE_LOCK
            result["stale_reason"] = "age_exceeded_pid_unknown"
        else:
            result["classification"] = UNKNOWN
            result["detail"] = "pid_liveness_unknown"
    return result


def inspect_refresh_locks(
    *,
    firms_lock: Path,
    dmc_lock: Path,
    now: datetime | None = None,
) -> dict[str, Any]:
    firms = inspect_lock_file(firms_lock, now=now)
    dmc = inspect_lock_file(dmc_lock, now=now)
    classes = {firms["classification"], dmc["classification"]}
    if ACTIVE_LOCK in classes:
        overall = ACTIVE_LOCK
    elif UNKNOWN in classes:
        overall = UNKNOWN
    elif STALE_LOCK in classes:
        overall = STALE_LOCK
    else:
        overall = NO_LOCK
    return {
        "overall": overall,
        "firms": firms,
        "dmc": dmc,
        "observed_at": (now or _utc_now()).isoformat(),
        "mutations": False,
        "note": "Operator never deletes locks.",
    }

"""Read-only FIRMS CURRENT collector — never refresh/publish."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def collect_firms_current(
    repo: Path | None = None,
    *,
    pointer_path: Path | None = None,
) -> dict[str, Any]:
    """Return PRESENT / ABSENT / UNKNOWN for FIRMS CURRENT pointer."""
    observed_at = _utc_now()
    try:
        from src.procesamiento.firms_source import (
            FIRMS_CURRENT_POINTER,
            POINTER_SCHEMA_VERSION,
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "state": "UNKNOWN",
            "known": False,
            "present": None,
            "observed_at": observed_at,
            "detail": f"import_error:{type(exc).__name__}",
        }

    path = pointer_path or FIRMS_CURRENT_POINTER
    if repo is not None and pointer_path is None:
        path = Path(repo) / "data" / "processed" / "firms" / "CURRENT.json"

    try:
        if not path.exists():
            return {
                "state": "ABSENT",
                "known": True,
                "present": False,
                "path": str(path),
                "observed_at": observed_at,
            }
    except OSError as exc:
        return {
            "state": "UNKNOWN",
            "known": False,
            "present": None,
            "path": str(path),
            "observed_at": observed_at,
            "detail": f"stat_error:{type(exc).__name__}",
        }

    try:
        raw = path.read_text(encoding="utf-8")
        pointer = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "state": "UNKNOWN",
            "known": False,
            "present": None,
            "path": str(path),
            "observed_at": observed_at,
            "detail": f"unreadable:{type(exc).__name__}",
        }

    if not isinstance(pointer, dict):
        return {
            "state": "UNKNOWN",
            "known": False,
            "present": None,
            "path": str(path),
            "observed_at": observed_at,
            "detail": "pointer_not_object",
        }

    schema = pointer.get("schema_version")
    return {
        "state": "PRESENT",
        "known": True,
        "present": True,
        "path": str(path),
        "pointer_schema": schema,
        "pointer_schema_expected": POINTER_SCHEMA_VERSION,
        "schema_ok": schema == POINTER_SCHEMA_VERSION,
        "selected_version": pointer.get("relative_path"),
        "manifest_identity": pointer.get("sha256"),
        "coverage_start": pointer.get("coverage_start"),
        "coverage_end": pointer.get("coverage_end"),
        "created_at": pointer.get("created_at"),
        "observed_at": observed_at,
    }

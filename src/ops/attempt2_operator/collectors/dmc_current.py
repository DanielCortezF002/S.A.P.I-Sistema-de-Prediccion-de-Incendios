"""Read-only DMC CURRENT collector — never refresh/publish."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_STATION = "330007"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def collect_dmc_current(
    repo: Path | None = None,
    *,
    station_id: str = DEFAULT_STATION,
    pointer_path: Path | None = None,
) -> dict[str, Any]:
    """Return PRESENT / ABSENT / UNKNOWN for DMC CURRENT pointer."""
    observed_at = _utc_now()
    if pointer_path is not None:
        path = Path(pointer_path)
    elif repo is not None:
        path = (
            Path(repo)
            / "data"
            / "processed"
            / "dmc"
            / station_id
            / "CURRENT.json"
        )
    else:
        path = (
            Path("data")
            / "processed"
            / "dmc"
            / station_id
            / "CURRENT.json"
        )

    try:
        if not path.exists():
            return {
                "state": "ABSENT",
                "known": True,
                "present": False,
                "path": str(path),
                "station_id": station_id,
                "observed_at": observed_at,
            }
    except OSError as exc:
        return {
            "state": "UNKNOWN",
            "known": False,
            "present": None,
            "path": str(path),
            "station_id": station_id,
            "observed_at": observed_at,
            "detail": f"stat_error:{type(exc).__name__}",
        }

    try:
        pointer = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "state": "UNKNOWN",
            "known": False,
            "present": None,
            "path": str(path),
            "station_id": station_id,
            "observed_at": observed_at,
            "detail": f"unreadable:{type(exc).__name__}",
        }

    if not isinstance(pointer, dict):
        return {
            "state": "UNKNOWN",
            "known": False,
            "present": None,
            "path": str(path),
            "station_id": station_id,
            "observed_at": observed_at,
            "detail": "pointer_not_object",
        }

    return {
        "state": "PRESENT",
        "known": True,
        "present": True,
        "path": str(path),
        "station_id": station_id,
        "pointer_schema": pointer.get("schema_version"),
        "manifest_identity": pointer.get("manifest_sha256"),
        "month_count": len(pointer.get("months") or {}),
        "observed_at": observed_at,
    }

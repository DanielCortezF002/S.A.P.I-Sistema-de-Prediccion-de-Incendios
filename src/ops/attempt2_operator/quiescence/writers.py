"""Detect known protected writers — observe only; never kill."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

WRITER_ACTIVE = "WRITER_ACTIVE"
WRITER_NOT_DETECTED = "WRITER_NOT_DETECTED"
WRITER_UNKNOWN = "WRITER_UNKNOWN"

# Must look like an actual refresh/write invocation, not status/rollback alone.
_WRITER_CMDS = (
    re.compile(r"(?i)src\.refresh\.firms_refresh(?:\s+|.*\s)refresh\b"),
    re.compile(r"(?i)firms_refresh(?:\s+|.*\s)refresh\b"),
    re.compile(r"(?i)src\.refresh\.dmc_refresh(?:\s+|.*\s)refresh\b"),
    re.compile(r"(?i)dmc_refresh(?:\s+|.*\s)refresh\b"),
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_writer_command(command: str | None) -> bool:
    if not command:
        return False
    # Exclude explicit non-write subcommands when alone
    low = command.lower()
    if re.search(r"\b(status|rollback|cleanup)\b", low) and not re.search(
        r"\brefresh\b", low
    ):
        return False
    return any(p.search(command) for p in _WRITER_CMDS)


def detect_writers(
    processes: dict[str, Any] | None,
    *,
    process_scan_ok: bool = True,
) -> dict[str, Any]:
    """Classify writer presence from process inventory."""
    observed_at = _utc_now()
    if processes is None or processes.get("status") == "UNKNOWN":
        return {
            "status": WRITER_UNKNOWN,
            "active": [],
            "observed_at": observed_at,
            "detail": "process_inventory_unavailable",
            "mutations": False,
        }
    if not process_scan_ok and not processes.get("items"):
        return {
            "status": WRITER_UNKNOWN,
            "active": [],
            "observed_at": observed_at,
            "detail": "process_scan_failed",
            "mutations": False,
        }

    active: list[dict[str, Any]] = []
    for item in processes.get("items") or []:
        if item.get("state") != "RUNNING":
            continue
        cmd = item.get("command_identity") or ""
        labels = item.get("labels") or [item.get("name")]
        if _is_writer_command(cmd) or (
            any(l in ("firms_refresh", "dmc_refresh", "attempt2_writer") for l in labels)
            and "refresh" in cmd.lower()
            and "status" not in cmd.lower()
        ):
            kind = "firms" if "firms" in cmd.lower() or "firms" in str(labels) else (
                "dmc" if "dmc" in cmd.lower() or "dmc" in str(labels) else "unknown"
            )
            active.append(
                {
                    "kind": kind,
                    "pid": item.get("pid"),
                    "container_id": item.get("container_id"),
                    "command_identity": cmd,
                    "confidence": item.get("confidence"),
                }
            )

    if active:
        return {
            "status": WRITER_ACTIVE,
            "active": active,
            "observed_at": observed_at,
            "mutations": False,
        }
    return {
        "status": WRITER_NOT_DETECTED,
        "active": [],
        "observed_at": observed_at,
        "mutations": False,
    }

"""Read-only process / container inventory for quiescence."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any, Callable

from src.ops.attempt2_operator.collectors.runtime import list_containers_readonly
from src.ops.attempt2_operator.redaction import redact_text

ProcessLister = Callable[[], list[dict[str, Any]]]

# Patterns for known operational processes (cmdline substring, case-insensitive)
PROCESS_PATTERNS: dict[str, tuple[str, ...]] = {
    "n8n": ("n8n",),
    "bridge": ("n8n_bridge", "n8n-bridge", "tools.n8n_bridge"),
    "web": ("streamlit", "web-presentation"),
    "firms_refresh": ("src.refresh.firms_refresh", "firms_refresh"),
    "dmc_refresh": ("src.refresh.dmc_refresh", "dmc_refresh"),
    "scoring": ("tools.ops.capture_score", "capture_score", "score_current_grid"),
    "attempt2_writer": ("attempt2_operator", "firms_refresh refresh", "dmc_refresh refresh"),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _redact_cmd(cmd: str | None) -> str:
    text, _ = redact_text(cmd or "")
    # Also scrub common env-style secrets in argv blobs
    text = re.sub(r"(?i)(MAP_KEY|API_KEY|TOKEN|PASSWORD)=(\S+)", r"\1=REDACTED", text)
    return text


def list_host_processes_windows() -> list[dict[str, Any]]:
    """Read-only CIM process listing (Windows)."""
    ps = (
        "Get-CimInstance Win32_Process | "
        "Select-Object ProcessId,Name,CommandLine | "
        "ConvertTo-Json -Compress"
    )
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True,
            text=True,
            timeout=25,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if proc.returncode != 0 or not (proc.stdout or "").strip():
        return []
    import json

    try:
        raw = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return []
    if isinstance(raw, dict):
        raw = [raw]
    out: list[dict[str, Any]] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        out.append(
            {
                "pid": row.get("ProcessId"),
                "name": row.get("Name"),
                "command": _redact_cmd(row.get("CommandLine")),
                "source": "win32_process",
            }
        )
    return out


def list_host_processes_posix() -> list[dict[str, Any]]:
    """Read /proc cmdline entries (Linux/macOS-ish)."""
    out: list[dict[str, Any]] = []
    proc_root = "/proc"
    if not os.path.isdir(proc_root):
        return out
    for entry in os.listdir(proc_root):
        if not entry.isdigit():
            continue
        cmd_path = os.path.join(proc_root, entry, "cmdline")
        try:
            raw = open(cmd_path, "rb").read()  # noqa: PTH123
        except OSError:
            continue
        cmd = raw.replace(b"\x00", b" ").decode("utf-8", errors="replace").strip()
        if not cmd:
            continue
        out.append(
            {
                "pid": int(entry),
                "name": cmd.split()[0] if cmd else None,
                "command": _redact_cmd(cmd),
                "source": "procfs",
            }
        )
    return out


def default_host_process_lister() -> list[dict[str, Any]]:
    if sys.platform.startswith("win"):
        return list_host_processes_windows()
    return list_host_processes_posix()


def classify_process(command: str | None, name: str | None = None) -> list[str]:
    blob = f"{name or ''} {command or ''}".lower()
    hits: list[str] = []
    for label, patterns in PROCESS_PATTERNS.items():
        if any(p.lower() in blob for p in patterns):
            hits.append(label)
    return hits


def inventory_processes(
    *,
    host_lister: ProcessLister | None = None,
    containers: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return process inventory with redacted command_identity."""
    observed_at = _utc_now()
    host_lister = host_lister or default_host_process_lister
    try:
        host_procs = host_lister()
        host_status = "READY"
    except Exception as exc:  # noqa: BLE001
        host_procs = []
        host_status = "UNKNOWN"
        host_error = type(exc).__name__
    else:
        host_error = None

    if containers is None:
        containers = list_containers_readonly()

    items: list[dict[str, Any]] = []
    for hp in host_procs:
        labels = classify_process(hp.get("command"), hp.get("name"))
        if not labels:
            continue
        items.append(
            {
                "name": labels[0],
                "labels": labels,
                "pid": hp.get("pid"),
                "container_id": None,
                "state": "RUNNING",
                "command_identity": hp.get("command"),
                "observed_at": observed_at,
                "confidence": "HIGH" if hp.get("command") else "MEDIUM",
                "source": hp.get("source"),
            }
        )

    for c in containers:
        names = str(c.get("Names") or c.get("names") or "")
        state = str(c.get("State") or c.get("state") or "").lower()
        status = str(c.get("Status") or c.get("status") or "")
        cid = c.get("ID") or c.get("Id") or c.get("id")
        labels = classify_process(names)
        # Map container hints
        low = names.lower()
        if "n8n" in low and "bridge" not in low:
            labels = list(dict.fromkeys(["n8n", *labels]))
        if "bridge" in low:
            labels = list(dict.fromkeys(["bridge", *labels]))
        if "sapi-web" in low or "web-presentation" in low:
            labels = list(dict.fromkeys(["web", *labels]))
        if not labels:
            continue
        running = state == "running" or status.lower().startswith("up")
        items.append(
            {
                "name": labels[0],
                "labels": labels,
                "pid": None,
                "container_id": cid,
                "state": "RUNNING" if running else "STOPPED",
                "command_identity": _redact_cmd(names),
                "observed_at": observed_at,
                "confidence": "HIGH",
                "source": "docker_ps_readonly",
                "container_status": status,
            }
        )

    return {
        "status": host_status if host_status != "UNKNOWN" else "PARTIAL",
        "items": items,
        "host_process_count_scanned": len(host_procs),
        "containers_scanned": len(containers),
        "observed_at": observed_at,
        "host_error": host_error,
        "mutations": False,
    }

"""Read-only n8n activation / execution / schedule / Telegram inspection.

Uses `n8n list:workflow` when the container is running, and a temporary
read-only sqlite copy for executions + node-type scans. Never mutates n8n_data.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from src.ops.attempt2_operator.redaction import redact_text

DockerExec = Callable[..., subprocess.CompletedProcess[str]]

RELEVANT_NAME_HINTS = (
    "sapi",
    "controlled",
    "preview",
    "orchestrat",
    "firms",
    "dmc",
    "refresh",
    "score",
    "telegram",
)

TELEGRAM_NODE = "n8n-nodes-base.telegram"
SCHEDULE_NODE = "n8n-nodes-base.scheduleTrigger"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _docker_exec(
    container: str, args: list[str], *, timeout: float = 60
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "exec", container, *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def find_n8n_container(containers: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Prefer running n8n (not bridge); else any n8n-named container."""
    candidates: list[dict[str, Any]] = []
    for c in containers:
        names = str(c.get("Names") or "")
        low = names.lower()
        if "n8n" not in low:
            continue
        if "bridge" in low:
            continue
        candidates.append(c)
    running = [
        c
        for c in candidates
        if str(c.get("State") or "").lower() == "running"
        or str(c.get("Status") or "").lower().startswith("up")
    ]
    return (running or candidates or [None])[0]


def _parse_workflow_list(stdout: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in (stdout or "").splitlines():
        line = line.strip()
        if not line or line.startswith("USAGE") or "|" not in line:
            # n8n format: id|name
            if "|" in line:
                pass
            else:
                continue
        parts = line.split("|", 1)
        if len(parts) != 2:
            continue
        wid, name = parts[0].strip(), parts[1].strip()
        if wid.lower() in ("id", "flags"):
            continue
        rows.append({"id": wid, "name": name})
    return rows


def _is_relevant_workflow(name: str) -> bool:
    low = name.lower()
    return any(h in low for h in RELEVANT_NAME_HINTS)


def list_workflows_via_cli(
    container: str,
    *,
    docker_exec: DockerExec | None = None,
) -> dict[str, Any]:
    """Read-only `n8n list:workflow` — never update/publish."""
    exe = docker_exec or _docker_exec
    observed_at = _utc_now()
    try:
        all_p = exe(container, ["n8n", "list:workflow"], timeout=90)
        active_p = exe(
            container, ["n8n", "list:workflow", "--active=true"], timeout=90
        )
        inactive_p = exe(
            container, ["n8n", "list:workflow", "--active=false"], timeout=90
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "status": "UNKNOWN",
            "detail": type(exc).__name__,
            "observed_at": observed_at,
            "workflows": [],
            "mutations": False,
        }
    if all_p.returncode != 0:
        return {
            "status": "UNKNOWN",
            "detail": f"list_workflow_exit_{all_p.returncode}",
            "stderr": (all_p.stderr or "")[:200],
            "observed_at": observed_at,
            "workflows": [],
            "mutations": False,
        }
    all_w = _parse_workflow_list(all_p.stdout or "")
    active_ids = {w["id"] for w in _parse_workflow_list(active_p.stdout or "")}
    inactive_ids = {w["id"] for w in _parse_workflow_list(inactive_p.stdout or "")}
    workflows = []
    for w in all_w:
        if w["id"] in active_ids:
            active: bool | None = True
        elif w["id"] in inactive_ids:
            active = False
        else:
            active = None
        workflows.append(
            {
                "id": w["id"],
                "name": w["name"],
                "active": active,
                "relevant": _is_relevant_workflow(w["name"]),
            }
        )
    return {
        "status": "READY",
        "workflows": workflows,
        "observed_at": observed_at,
        "mutations": False,
        "method": "n8n_list_workflow",
    }


def _copy_n8n_db(container: str, dest_dir: Path) -> Path | None:
    """docker cp database into dest_dir (read copy; does not modify volume)."""
    if shutil.which("docker") is None:
        return None
    dest = dest_dir / "database.sqlite"
    try:
        for name in ("database.sqlite", "database.sqlite-wal", "database.sqlite-shm"):
            subprocess.run(
                ["docker", "cp", f"{container}:/home/node/.n8n/{name}", str(dest_dir / name)],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
        if not dest.is_file():
            return None
        return dest
    except (OSError, subprocess.TimeoutExpired):
        return None


def _open_ro_sqlite(path: Path) -> sqlite3.Connection:
    uri = f"file:{path.as_posix()}?mode=ro"
    return sqlite3.connect(uri, uri=True)


def inspect_db_nodes_and_executions(
    db_path: Path,
) -> dict[str, Any]:
    """Parse workflow nodes + running executions from a RO sqlite copy."""
    observed_at = _utc_now()
    try:
        con = _open_ro_sqlite(db_path)
    except sqlite3.Error as exc:
        return {
            "status": "UNKNOWN",
            "detail": type(exc).__name__,
            "observed_at": observed_at,
            "mutations": False,
        }
    try:
        cur = con.cursor()
        workflows = []
        for row in cur.execute(
            "SELECT id, name, active, nodes FROM workflow_entity"
        ):
            wid, name, active, nodes_raw = row
            nodes = []
            try:
                nodes = json.loads(nodes_raw) if nodes_raw else []
            except (TypeError, json.JSONDecodeError):
                nodes = []
            types = [str(n.get("type") or "") for n in nodes if isinstance(n, dict)]
            has_telegram = any(TELEGRAM_NODE in t for t in types)
            has_schedule = any(SCHEDULE_NODE in t for t in types)
            # Redact node parameters — keep types only
            workflows.append(
                {
                    "id": wid,
                    "name": name,
                    "active": bool(active),
                    "relevant": _is_relevant_workflow(str(name or "")),
                    "has_telegram_node": has_telegram,
                    "has_schedule_node": has_schedule,
                    "node_types": sorted(set(types)),
                }
            )

        running = []
        for row in cur.execute(
            "SELECT id, workflowId, status, finished, startedAt FROM execution_entity "
            "WHERE status IN ('running','waiting','new') "
            "OR (finished = 0 AND status NOT IN ('success','error','crashed','canceled','cancelled'))"
        ):
            running.append(
                {
                    "id": row[0],
                    "workflow_id": row[1],
                    "status": row[2],
                    "finished": bool(row[3]),
                    "started_at": row[4],
                }
            )
        return {
            "status": "READY",
            "workflows": workflows,
            "running_executions": running,
            "observed_at": observed_at,
            "mutations": False,
            "method": "sqlite_readonly_copy",
        }
    except sqlite3.Error as exc:
        return {
            "status": "UNKNOWN",
            "detail": type(exc).__name__,
            "observed_at": observed_at,
            "mutations": False,
        }
    finally:
        con.close()


def collect_n8n_quiescence_signals(
    *,
    n8n_runtime: dict[str, Any],
    containers: list[dict[str, Any]],
    docker_exec: DockerExec | None = None,
    db_inspector: Callable[[Path], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Assemble n8n / schedule / telegram / execution signals."""
    observed_at = _utc_now()
    container_status = n8n_runtime.get("status")  # RUNNING/STOPPED/UNKNOWN
    matched = n8n_runtime.get("matched_container")
    cinfo = find_n8n_container(containers)
    container_name = matched or (
        str(cinfo.get("Names") or "").split(",")[0] if cinfo else None
    )

    activation: dict[str, Any] = {
        "status": "UNKNOWN",
        "workflows": [],
        "any_relevant_active": None,
    }
    schedule: dict[str, Any] = {
        "status": "UNKNOWN",
        "state": "UNKNOWN",
    }
    telegram: dict[str, Any] = {
        "status": "UNKNOWN",
        "state": "UNKNOWN",
    }
    execution: dict[str, Any] = {
        "status": "UNKNOWN",
        "state": "UNKNOWN",
        "running": [],
    }

    if container_status == "STOPPED":
        # Container stopped ⇒ no live executions; activation still unknown without DB.
        execution = {
            "status": "READY",
            "state": "NOT_RUNNING",
            "running": [],
            "detail": "container_stopped",
            "observed_at": observed_at,
        }
        # Try sqlite via docker cp even when stopped (volume still exists)
        if container_name and cinfo is not None:
            db_info = _inspect_via_copy(container_name, db_inspector)
            activation, schedule, telegram, execution = _merge_db(
                db_info, activation, schedule, telegram, execution
            )
        else:
            activation = {
                "status": "UNKNOWN",
                "detail": "n8n_stopped_no_container_for_db",
                "workflows": [],
                "any_relevant_active": None,
                "observed_at": observed_at,
            }
            schedule["detail"] = "n8n_stopped_db_unavailable"
            telegram["detail"] = "n8n_stopped_db_unavailable"

    elif container_status == "RUNNING" and container_name:
        cli = list_workflows_via_cli(container_name, docker_exec=docker_exec)
        if cli.get("status") == "READY":
            wfs = cli.get("workflows") or []
            relevant = [w for w in wfs if w.get("relevant")]
            any_active = any(w.get("active") is True for w in (relevant or wfs))
            any_unknown = any(w.get("active") is None for w in (relevant or wfs))
            activation = {
                "status": "UNKNOWN" if any_unknown and not relevant else "READY",
                "workflows": wfs,
                "any_relevant_active": any_active if relevant else any_active,
                "observed_at": cli.get("observed_at"),
                "method": cli.get("method"),
                "mutations": False,
            }
            if any_unknown and relevant:
                activation["status"] = "UNKNOWN"
        else:
            activation = {
                "status": "UNKNOWN",
                "detail": cli.get("detail"),
                "workflows": [],
                "any_relevant_active": None,
                "observed_at": observed_at,
            }

        db_info = _inspect_via_copy(container_name, db_inspector)
        activation, schedule, telegram, execution = _merge_db(
            db_info, activation, schedule, telegram, execution
        )
    else:
        activation["detail"] = "n8n_container_state_unknown"
        schedule["detail"] = "n8n_container_state_unknown"
        telegram["detail"] = "n8n_container_state_unknown"
        execution["detail"] = "n8n_container_state_unknown"

    return {
        "container_status": container_status,
        "container_name": container_name,
        "activation": activation,
        "schedule": schedule,
        "telegram": telegram,
        "execution": execution,
        "observed_at": observed_at,
        "mutations": False,
    }


def _inspect_via_copy(
    container_name: str,
    db_inspector: Callable[[Path], dict[str, Any]] | None,
) -> dict[str, Any]:
    inspector = db_inspector or inspect_db_nodes_and_executions
    tmp = tempfile.mkdtemp(prefix="sapi-n8n-ro-")
    try:
        db = _copy_n8n_db(container_name, Path(tmp))
        if db is None:
            return {"status": "UNKNOWN", "detail": "db_copy_failed", "mutations": False}
        return inspector(db)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _merge_db(
    db_info: dict[str, Any],
    activation: dict[str, Any],
    schedule: dict[str, Any],
    telegram: dict[str, Any],
    execution: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    if db_info.get("status") != "READY":
        if schedule.get("state") == "UNKNOWN":
            schedule = {
                **schedule,
                "status": "UNKNOWN",
                "state": "UNKNOWN",
                "detail": db_info.get("detail", "db_unavailable"),
            }
        if telegram.get("state") == "UNKNOWN":
            telegram = {
                **telegram,
                "status": "UNKNOWN",
                "state": "UNKNOWN",
                "detail": db_info.get("detail", "db_unavailable"),
            }
        if execution.get("state") == "UNKNOWN":
            execution = {
                **execution,
                "status": "UNKNOWN",
                "state": "UNKNOWN",
                "detail": db_info.get("detail", "db_unavailable"),
            }
        return activation, schedule, telegram, execution

    wfs = db_info.get("workflows") or []
    relevant = [w for w in wfs if w.get("relevant")] or wfs

    # Enrich activation from DB if CLI incomplete
    if activation.get("status") != "READY" or activation.get("any_relevant_active") is None:
        any_active = any(w.get("active") for w in relevant)
        activation = {
            "status": "READY",
            "workflows": wfs,
            "any_relevant_active": any_active,
            "observed_at": db_info.get("observed_at"),
            "method": db_info.get("method"),
            "mutations": False,
        }

    # Schedule
    sched_present = any(w.get("has_schedule_node") for w in relevant)
    sched_enabled = any(
        w.get("has_schedule_node") and w.get("active") for w in relevant
    )
    if not sched_present:
        schedule = {
            "status": "READY",
            "state": "SCHEDULE_NOT_PRESENT",
            "observed_at": db_info.get("observed_at"),
        }
    elif sched_enabled:
        schedule = {
            "status": "READY",
            "state": "SCHEDULE_ENABLED",
            "observed_at": db_info.get("observed_at"),
        }
    else:
        schedule = {
            "status": "READY",
            "state": "SCHEDULE_DISABLED",
            "observed_at": db_info.get("observed_at"),
        }

    # Telegram: ARMED if telegram node exists on an active relevant workflow
    has_tg = any(w.get("has_telegram_node") for w in relevant)
    armed = any(w.get("has_telegram_node") and w.get("active") for w in relevant)
    # Also ARMED if telegram node exists and workflow has schedule enabled
    # (autonomous path) — already covered by active+telegram
    if not has_tg:
        telegram = {
            "status": "READY",
            "state": "DISARMED",
            "detail": "no_telegram_nodes",
            "observed_at": db_info.get("observed_at"),
        }
    elif armed:
        telegram = {
            "status": "READY",
            "state": "ARMED",
            "detail": "telegram_on_active_workflow",
            "observed_at": db_info.get("observed_at"),
        }
    else:
        # Node present but workflow inactive → DISARMED for Attempt 2 quiescence
        telegram = {
            "status": "READY",
            "state": "DISARMED",
            "detail": "telegram_nodes_on_inactive_workflow",
            "observed_at": db_info.get("observed_at"),
        }

    running = db_info.get("running_executions") or []
    if running:
        execution = {
            "status": "READY",
            "state": "RUNNING",
            "running": running,
            "observed_at": db_info.get("observed_at"),
        }
    else:
        execution = {
            "status": "READY",
            "state": "NOT_RUNNING",
            "running": [],
            "observed_at": db_info.get("observed_at"),
        }

    # Never persist raw node params / credentials
    for w in activation.get("workflows") or []:
        if isinstance(w, dict) and "nodes" in w:
            w.pop("nodes", None)
    return activation, schedule, telegram, execution


def redact_process_command(command: str | None) -> str:
    text, _ = redact_text(command or "")
    return re.sub(r"(?i)(MAP_KEY|API_KEY|TOKEN|PASSWORD)=(\S+)", r"\1=REDACTED", text)

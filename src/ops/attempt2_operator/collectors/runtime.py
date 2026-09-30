"""Read-only runtime detection — never start/stop services.

Rules:
- open port alone ≠ RUNNING (identity required)
- Docker inspect is read-only (no start/stop/pull/compose)
- UNKNOWN ≠ STOPPED ≠ AVAILABLE
"""

from __future__ import annotations

import json
import shutil
import socket
import subprocess
from datetime import datetime, timezone
from typing import Any

# Known container name substrings → logical service
SERVICE_CONTAINER_HINTS: dict[str, tuple[str, ...]] = {
    "n8n": ("n8n",),
    "n8n-bridge": ("n8n-bridge", "sapi-n8n-bridge"),
    "web-presentation": ("sapi-web", "web-presentation"),
}

# Names that must never identify a service even if they contain its hint:
# "sapi-n8n-bridge" contains "n8n" but is the bridge (same rule as find_n8n_container).
SERVICE_CONTAINER_EXCLUDES: dict[str, tuple[str, ...]] = {
    "n8n": ("bridge",),
}

SERVICE_PORTS: dict[str, tuple[int, ...]] = {
    "n8n": (5678, 5680),
    "n8n-bridge": (8600,),
    "web-presentation": (8501,),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _port_open(host: str, port: int, timeout: float = 0.35) -> bool | None:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False
    except Exception:  # noqa: BLE001
        return None


def collect_docker_status() -> dict[str, Any]:
    observed_at = _utc_now()
    if shutil.which("docker") is None:
        return {
            "status": "UNAVAILABLE",
            "observed_at": observed_at,
            "detail": "docker_not_on_path",
            "method": "which",
        }
    try:
        proc = subprocess.run(
            ["docker", "info", "--format", "{{json .ServerVersion}}"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        if proc.returncode == 0:
            return {
                "status": "AVAILABLE",
                "observed_at": observed_at,
                "method": "docker_info",
                "server_version": (proc.stdout or "").strip().strip('"'),
            }
        return {
            "status": "UNAVAILABLE",
            "observed_at": observed_at,
            "detail": f"docker_info_exit_{proc.returncode}",
            "method": "docker_info",
        }
    except subprocess.TimeoutExpired:
        return {
            "status": "UNKNOWN",
            "observed_at": observed_at,
            "detail": "docker_info_timeout",
            "method": "docker_info",
        }
    except OSError as exc:
        return {
            "status": "UNKNOWN",
            "observed_at": observed_at,
            "detail": type(exc).__name__,
            "method": "docker_info",
        }


def list_containers_readonly() -> list[dict[str, Any]]:
    """Read-only `docker ps -a` JSON. Empty list if unavailable."""
    if shutil.which("docker") is None:
        return []
    try:
        proc = subprocess.run(
            [
                "docker",
                "ps",
                "-a",
                "--format",
                "{{json .}}",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if proc.returncode != 0:
        return []
    out: list[dict[str, Any]] = []
    for line in (proc.stdout or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _match_container(
    containers: list[dict[str, Any]],
    hints: tuple[str, ...],
    excludes: tuple[str, ...] = (),
) -> dict[str, Any] | None:
    """Prefer a running match, else the first match; never an excluded name."""
    candidates = []
    for c in containers:
        # docker ps --format json may use Names like "sapi-n8n-bridge"
        lname = str(c.get("Names") or c.get("names") or "").lower()
        if any(x.lower() in lname for x in excludes):
            continue
        if any(h.lower() in lname for h in hints):
            candidates.append(c)
    running = [c for c in candidates if _container_running(c) is True]
    return (running or candidates or [None])[0]


def _container_running(c: dict[str, Any]) -> bool | None:
    status = str(c.get("Status") or c.get("State") or "").lower()
    if status.startswith("up") or status == "running":
        return True
    if any(status.startswith(p) for p in ("exited", "created", "dead", "paused")):
        return False
    state = str(c.get("State") or "").lower()
    if state == "running":
        return True
    if state in ("exited", "created", "dead", "paused"):
        return False
    return None


def collect_service_status(
    service: str,
    *,
    containers: list[dict[str, Any]] | None = None,
    docker_status: str | None = None,
) -> dict[str, Any]:
    observed_at = _utc_now()
    ports = SERVICE_PORTS.get(service, ())
    hints = SERVICE_CONTAINER_HINTS.get(service, ())
    port_hits = {p: _port_open("127.0.0.1", p) for p in ports}
    any_open = any(v is True for v in port_hits.values())
    any_unknown_port = any(v is None for v in port_hits.values())

    matched = None
    if containers is not None:
        matched = _match_container(
            containers, hints, SERVICE_CONTAINER_EXCLUDES.get(service, ())
        )

    identity: dict[str, Any] = {
        "matched_container": None,
        "port_hits": port_hits,
        "identity_established": False,
    }

    if matched is not None:
        running = _container_running(matched)
        identity["matched_container"] = matched.get("Names") or matched.get("names")
        identity["container_status"] = matched.get("Status") or matched.get("State")
        identity["identity_established"] = True
        if running is True:
            status = "RUNNING"
        elif running is False:
            status = "STOPPED"
        else:
            status = "UNKNOWN"
        return {
            "name": service,
            "status": status,
            "observed_at": observed_at,
            "method": "docker_ps_readonly",
            **identity,
        }

    # No container identity
    if docker_status == "AVAILABLE":
        # Daemon up, no matching container → treat as STOPPED (not present)
        # unless a port is open without identity → UNKNOWN
        if any_open:
            status = "UNKNOWN"
            identity["detail"] = "port_open_without_container_identity"
        else:
            status = "STOPPED"
            identity["detail"] = "no_matching_container"
        return {
            "name": service,
            "status": status,
            "observed_at": observed_at,
            "method": "docker_ps_readonly",
            **identity,
        }

    # Docker unavailable: port alone cannot establish identity
    if any_open:
        status = "UNKNOWN"
        identity["detail"] = "port_open_without_verified_identity"
    elif any_unknown_port:
        status = "UNKNOWN"
        identity["detail"] = "port_probe_inconclusive"
    else:
        # Ports closed and no docker identity → UNKNOWN (not STOPPED)
        # Spec: open port alone ≠ RUNNING; closed port alone ≠ definitive STOPPED
        # without process/container confirmation
        status = "UNKNOWN"
        identity["detail"] = "no_identity_signal"
    return {
        "name": service,
        "status": status,
        "observed_at": observed_at,
        "method": "port_probe_unverified",
        **identity,
        "note": "Port state alone never yields RUNNING",
    }


def collect_runtime() -> dict[str, Any]:
    started = _utc_now()
    docker = collect_docker_status()
    containers: list[dict[str, Any]] = []
    if docker.get("status") == "AVAILABLE":
        containers = list_containers_readonly()
    n8n = collect_service_status(
        "n8n", containers=containers, docker_status=docker.get("status")
    )
    bridge = collect_service_status(
        "n8n-bridge", containers=containers, docker_status=docker.get("status")
    )
    web = collect_service_status(
        "web-presentation", containers=containers, docker_status=docker.get("status")
    )
    finished = _utc_now()
    return {
        "docker": docker,
        "n8n": n8n,
        "bridge": bridge,
        "web": web,
        "observed_at": finished,
        "collection_started_at": started,
        "collection_finished_at": finished,
        "containers_inspected": len(containers),
        "note": (
            "UNKNOWN!=STOPPED. Port-open alone never RUNNING. "
            "Docker inspect is read-only (no start/stop/pull/compose)."
        ),
        "mutations": False,
    }

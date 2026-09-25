"""Read-only runtime detection — never start/stop services."""

from __future__ import annotations

import shutil
import socket
import subprocess
from datetime import datetime, timezone
from typing import Any


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
        return {"status": "UNAVAILABLE", "observed_at": observed_at, "detail": "docker_not_on_path"}
    try:
        proc = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        if proc.returncode == 0:
            return {"status": "AVAILABLE", "observed_at": observed_at}
        return {
            "status": "UNAVAILABLE",
            "observed_at": observed_at,
            "detail": f"docker_info_exit_{proc.returncode}",
        }
    except subprocess.TimeoutExpired:
        return {"status": "UNKNOWN", "observed_at": observed_at, "detail": "docker_info_timeout"}
    except OSError as exc:
        return {
            "status": "UNKNOWN",
            "observed_at": observed_at,
            "detail": type(exc).__name__,
        }


def _service_status(port: int, name: str) -> dict[str, Any]:
    observed_at = _utc_now()
    open_ = _port_open("127.0.0.1", port)
    if open_ is True:
        status = "RUNNING"
    elif open_ is False:
        status = "STOPPED"
    else:
        status = "UNKNOWN"
    return {"name": name, "port": port, "status": status, "observed_at": observed_at}


def collect_runtime() -> dict[str, Any]:
    docker = collect_docker_status()
    n8n = _service_status(5678, "n8n")
    bridge = _service_status(8600, "n8n-bridge")
    web = _service_status(8501, "web-presentation")
    return {
        "docker": docker,
        "n8n": n8n,
        "bridge": bridge,
        "web": web,
        "observed_at": _utc_now(),
        "note": "UNKNOWN is not STOPPED; detection is best-effort localhost ports only",
    }

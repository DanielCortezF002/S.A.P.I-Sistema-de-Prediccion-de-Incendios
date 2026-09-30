"""Attempt 2 readiness fixes: DMC writer lock seen by quiescence (R2) and the
bridge never taken for the n8n container (R3). Read-only fakes, no Docker."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.ops.attempt2_operator.collectors.runtime import collect_service_status
from src.ops.attempt2_operator.paths import StoreRoots
from src.ops.attempt2_operator.quiescence import collect as qcollect
from src.ops.attempt2_operator.quiescence.findings import QG_ACTIVE_DMC_LOCK
from src.ops.attempt2_operator.quiescence.locks import ACTIVE_LOCK, NO_LOCK, STALE_LOCK
from src.ops.attempt2_operator.quiescence.policy import QuiescencePolicy
from src.ops.attempt2_operator.quiescence.result import NOT_QUIESCENT
from src.refresh.dmc_refresh import DmcPaths
from src.refresh.lock import STALE_AFTER

# --- R2: DMC lock ---------------------------------------------------------------------


def test_dmc_lock_is_the_writer_lock(tmp_path: Path):
    roots = StoreRoots.from_repo(tmp_path)
    assert (
        roots.dmc_lock() == DmcPaths(root=tmp_path / "data" / "processed" / "dmc").lock
    )


def _quiescence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    monkeypatch.setattr(qcollect, "list_containers_readonly", lambda: [])
    monkeypatch.setattr(
        qcollect,
        "collect_n8n_quiescence_signals",
        lambda **kw: {
            "container_status": "STOPPED",
            "activation": {
                "status": "READY",
                "any_relevant_active": False,
                "workflows": [],
            },
            "schedule": {"status": "READY", "state": "SCHEDULE_NOT_PRESENT"},
            "telegram": {"status": "READY", "state": "DISARMED"},
            "execution": {"status": "READY", "state": "NOT_RUNNING", "running": []},
            "mutations": False,
        },
    )
    stopped = {"status": "STOPPED"}
    return qcollect.collect_quiescence(
        repo=tmp_path,
        runtime={"n8n": stopped, "bridge": stopped, "web": stopped},
        policy=QuiescencePolicy(),
        skip_host_processes=True,
    )


def _write_lock(path: Path, started: datetime) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "pid": 4242,
                "host": "t",
                "started_at": started.isoformat(),
                "command": "dmc_refresh refresh",
            }
        ),
        encoding="utf-8",
    )


def test_active_dmc_writer_lock_blocks(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "src.ops.attempt2_operator.quiescence.locks._pid_alive", lambda _p: True
    )
    _write_lock(
        DmcPaths(root=tmp_path / "data" / "processed" / "dmc").lock,
        datetime.now(timezone.utc),
    )
    r = _quiescence(tmp_path, monkeypatch)
    assert r["locks"]["dmc"]["classification"] == ACTIVE_LOCK
    assert r["status"] == NOT_QUIESCENT
    assert any(f["id"] == QG_ACTIVE_DMC_LOCK for f in r["findings"])


def test_stale_dmc_writer_lock(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "src.ops.attempt2_operator.quiescence.locks._pid_alive", lambda _p: False
    )
    _write_lock(
        DmcPaths(root=tmp_path / "data" / "processed" / "dmc").lock,
        datetime.now(timezone.utc) - STALE_AFTER - timedelta(minutes=5),
    )
    r = _quiescence(tmp_path, monkeypatch)
    assert r["locks"]["dmc"]["classification"] == STALE_LOCK
    assert r["status"] == NOT_QUIESCENT


def test_no_dmc_lock(tmp_path, monkeypatch):
    (tmp_path / "data" / "processed" / "dmc" / "330007").mkdir(parents=True)
    r = _quiescence(tmp_path, monkeypatch)
    assert r["locks"]["dmc"]["classification"] == NO_LOCK


# --- R3: n8n vs bridge ----------------------------------------------------------------

ORCH_UP = {
    "Names": "sapi-ai-orchestrator-n8n",
    "Status": "Up 2 hours",
    "State": "running",
}
ORCH_DOWN = {
    "Names": "sapi-ai-orchestrator-n8n",
    "Status": "Exited (0) 1 hour ago",
    "State": "exited",
}
BRIDGE_UP = {"Names": "sapi-n8n-bridge", "Status": "Up 5 minutes", "State": "running"}


@pytest.fixture(autouse=True)
def _ports_closed(monkeypatch):
    # A real n8n may listen on 5680 on the host; identity must come from containers.
    monkeypatch.setattr(
        "src.ops.attempt2_operator.collectors.runtime._port_open",
        lambda host, port, timeout=0.35: False,
    )


def test_orchestrator_only():
    s = collect_service_status("n8n", containers=[ORCH_UP], docker_status="AVAILABLE")
    assert (s["status"], s["matched_container"]) == ("RUNNING", ORCH_UP["Names"])


def test_bridge_only_is_never_n8n():
    n8n = collect_service_status(
        "n8n", containers=[BRIDGE_UP], docker_status="AVAILABLE"
    )
    bridge = collect_service_status(
        "n8n-bridge", containers=[BRIDGE_UP], docker_status="AVAILABLE"
    )
    assert n8n["status"] == "STOPPED" and n8n["matched_container"] is None
    assert bridge["status"] == "RUNNING"


@pytest.mark.parametrize("order", [[BRIDGE_UP, ORCH_UP], [ORCH_UP, BRIDGE_UP]])
def test_both_present_selects_orchestrator(order):
    s = collect_service_status("n8n", containers=order, docker_status="AVAILABLE")
    assert (s["status"], s["matched_container"]) == ("RUNNING", ORCH_UP["Names"])


def test_running_bridge_does_not_mask_stopped_orchestrator():
    s = collect_service_status(
        "n8n", containers=[BRIDGE_UP, ORCH_DOWN], docker_status="AVAILABLE"
    )
    assert (s["status"], s["matched_container"]) == ("STOPPED", ORCH_DOWN["Names"])


def test_none_present():
    assert (
        collect_service_status("n8n", containers=[], docker_status="AVAILABLE")[
            "status"
        ]
        == "STOPPED"
    )
    assert (
        collect_service_status("n8n", containers=[], docker_status="UNAVAILABLE")[
            "status"
        ]
        == "UNKNOWN"
    )

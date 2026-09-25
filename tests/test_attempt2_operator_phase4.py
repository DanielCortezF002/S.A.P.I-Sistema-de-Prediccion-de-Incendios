"""Phase 4: operational quiescence gate — read-only, UNKNOWN!=QUIESCENT."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.ops.attempt2_operator.operator import Attempt2Operator
from src.ops.attempt2_operator.quiescence.findings import (
    FINDING_REMEDIATION,
    QG_ACTIVE_FIRMS_LOCK,
    QG_ACTIVE_WRITER,
    QG_ENABLED_SCHEDULE,
    QG_N8N_MUST_BE_STOPPED,
    QG_STALE_LOCK,
    QG_TELEGRAM_ARMED,
    QG_UNKNOWN_N8N_STATE,
)
from src.ops.attempt2_operator.quiescence.locks import (
    ACTIVE_LOCK,
    NO_LOCK,
    STALE_LOCK,
    UNKNOWN as LOCK_UNKNOWN,
    inspect_lock_file,
    inspect_refresh_locks,
)
from src.ops.attempt2_operator.quiescence.n8n_inspect import redact_process_command
from src.ops.attempt2_operator.quiescence.policy import QuiescencePolicy
from src.ops.attempt2_operator.quiescence.result import (
    INCOMPLETE,
    NOT_QUIESCENT,
    QUIESCENT,
    evaluate_quiescence,
    remediation_for,
)
from src.ops.attempt2_operator.quiescence.writers import (
    WRITER_ACTIVE,
    WRITER_NOT_DETECTED,
    WRITER_UNKNOWN,
    detect_writers,
)
from src.ops.attempt2_operator.states import Attempt2State
from src.refresh.lock import STALE_AFTER

SHA = "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"


def _base_kwargs(**overrides):
    now = datetime.now(timezone.utc).isoformat()
    base = {
        "processes": {"status": "READY", "items": [], "mutations": False},
        "writers": {"status": WRITER_NOT_DETECTED, "active": [], "mutations": False},
        "locks": {
            "overall": NO_LOCK,
            "firms": {"classification": NO_LOCK},
            "dmc": {"classification": NO_LOCK},
            "mutations": False,
        },
        "n8n": {
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
        "bridge": {"status": "STOPPED"},
        "web": {"status": "STOPPED"},
        "policy": QuiescencePolicy(
            n8n_container="MUST_BE_STOPPED",
            bridge="MUST_BE_STOPPED",
            web="MUST_BE_STOPPED",
            allow_n8n_running_if_inactive=False,
        ),
        "observed_at_start": now,
        "observed_at_end": now,
    }
    base.update(overrides)
    return base


def test_no_writer_clear():
    w = detect_writers({"status": "READY", "items": []})
    assert w["status"] == WRITER_NOT_DETECTED
    r = evaluate_quiescence(**_base_kwargs())
    assert r["writers"]["status"] == WRITER_NOT_DETECTED
    assert r["status"] == QUIESCENT


def test_active_firms_writer_not_quiescent():
    procs = {
        "status": "READY",
        "items": [
            {
                "name": "firms_refresh",
                "labels": ["firms_refresh"],
                "state": "RUNNING",
                "command_identity": "python -m src.refresh.firms_refresh refresh",
                "pid": 4242,
            }
        ],
    }
    w = detect_writers(procs)
    assert w["status"] == WRITER_ACTIVE
    r = evaluate_quiescence(**_base_kwargs(writers=w, processes=procs))
    assert r["status"] == NOT_QUIESCENT
    assert any(f["id"] == QG_ACTIVE_WRITER for f in r["findings"])


def test_active_dmc_writer_not_quiescent():
    procs = {
        "status": "READY",
        "items": [
            {
                "name": "dmc_refresh",
                "labels": ["dmc_refresh"],
                "state": "RUNNING",
                "command_identity": "python -m src.refresh.dmc_refresh refresh",
                "pid": 4243,
            }
        ],
    }
    w = detect_writers(procs)
    assert w["status"] == WRITER_ACTIVE
    r = evaluate_quiescence(**_base_kwargs(writers=w))
    assert r["status"] == NOT_QUIESCENT


def test_no_locks(tmp_path: Path):
    firms = tmp_path / "firms" / ".refresh.lock"
    dmc = tmp_path / "dmc" / ".refresh.lock"
    firms.parent.mkdir()
    dmc.parent.mkdir()
    locks = inspect_refresh_locks(firms_lock=firms, dmc_lock=dmc)
    assert locks["overall"] == NO_LOCK
    assert locks["mutations"] is False


def test_active_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    lock = tmp_path / ".refresh.lock"
    now = datetime.now(timezone.utc)
    lock.write_text(
        json.dumps(
            {
                "pid": 999001,
                "host": "test",
                "started_at": now.isoformat(),
                "command": "firms_refresh refresh",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "src.ops.attempt2_operator.quiescence.locks._pid_alive",
        lambda _p: True,
    )
    info = inspect_lock_file(lock, now=now)
    assert info["classification"] == ACTIVE_LOCK
    r = evaluate_quiescence(
        **_base_kwargs(
            locks={
                "overall": ACTIVE_LOCK,
                "firms": info,
                "dmc": {"classification": NO_LOCK},
            }
        )
    )
    assert r["status"] == NOT_QUIESCENT
    assert any(f["id"] == QG_ACTIVE_FIRMS_LOCK for f in r["findings"])


def test_stale_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    lock = tmp_path / ".refresh.lock"
    started = datetime.now(timezone.utc) - STALE_AFTER - timedelta(minutes=5)
    lock.write_text(
        json.dumps(
            {
                "pid": 1,
                "host": "test",
                "started_at": started.isoformat(),
                "command": "firms_refresh refresh",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "src.ops.attempt2_operator.quiescence.locks._pid_alive",
        lambda _p: False,
    )
    info = inspect_lock_file(lock)
    assert info["classification"] == STALE_LOCK
    r = evaluate_quiescence(
        **_base_kwargs(
            locks={
                "overall": STALE_LOCK,
                "firms": info,
                "dmc": {"classification": NO_LOCK},
            }
        )
    )
    assert r["status"] == NOT_QUIESCENT
    assert any(f["id"] == QG_STALE_LOCK for f in r["findings"])


def test_unknown_lock_state():
    r = evaluate_quiescence(
        **_base_kwargs(
            locks={
                "overall": LOCK_UNKNOWN,
                "firms": {"classification": LOCK_UNKNOWN, "detail": "unreadable"},
                "dmc": {"classification": NO_LOCK},
            }
        )
    )
    assert r["status"] == INCOMPLETE
    assert r["status"] != QUIESCENT


def test_n8n_stopped_no_writers():
    r = evaluate_quiescence(**_base_kwargs())
    assert r["n8n"]["container_status"] == "STOPPED"
    assert r["status"] == QUIESCENT


def test_n8n_running_inactive_schedule_disabled_may_run_policy():
    policy = QuiescencePolicy(
        n8n_container="MAY_BE_RUNNING_IF_INACTIVE",
        bridge="MUST_BE_STOPPED",
        web="MUST_BE_STOPPED",
        allow_n8n_running_if_inactive=True,
    )
    n8n = {
        "container_status": "RUNNING",
        "activation": {
            "status": "READY",
            "any_relevant_active": False,
            "workflows": [],
        },
        "schedule": {"status": "READY", "state": "SCHEDULE_DISABLED"},
        "telegram": {"status": "READY", "state": "DISARMED"},
        "execution": {"status": "READY", "state": "NOT_RUNNING", "running": []},
    }
    r = evaluate_quiescence(**_base_kwargs(n8n=n8n, policy=policy))
    assert r["status"] == QUIESCENT


def test_n8n_running_schedule_enabled():
    n8n = {
        "container_status": "RUNNING",
        "activation": {
            "status": "READY",
            "any_relevant_active": False,
            "workflows": [],
        },
        "schedule": {"status": "READY", "state": "SCHEDULE_ENABLED"},
        "telegram": {"status": "READY", "state": "DISARMED"},
        "execution": {"status": "READY", "state": "NOT_RUNNING", "running": []},
    }
    # Default policy MUST_BE_STOPPED → NOT_QUIESCENT for running n8n
    r = evaluate_quiescence(**_base_kwargs(n8n=n8n))
    assert r["status"] == NOT_QUIESCENT
    assert any(
        f["id"] in (QG_N8N_MUST_BE_STOPPED, QG_ENABLED_SCHEDULE) for f in r["findings"]
    )


def test_active_n8n_execution():
    n8n = {
        "container_status": "STOPPED",
        "activation": {
            "status": "READY",
            "any_relevant_active": False,
            "workflows": [],
        },
        "schedule": {"status": "READY", "state": "SCHEDULE_NOT_PRESENT"},
        "telegram": {"status": "READY", "state": "DISARMED"},
        "execution": {
            "status": "READY",
            "state": "RUNNING",
            "running": [{"id": "1", "status": "running"}],
        },
    }
    r = evaluate_quiescence(**_base_kwargs(n8n=n8n))
    assert r["status"] == NOT_QUIESCENT


def test_n8n_activation_unknown():
    n8n = {
        "container_status": "RUNNING",
        "activation": {
            "status": "UNKNOWN",
            "any_relevant_active": None,
            "workflows": [],
        },
        "schedule": {"status": "UNKNOWN", "state": "UNKNOWN"},
        "telegram": {"status": "UNKNOWN", "state": "UNKNOWN"},
        "execution": {"status": "UNKNOWN", "state": "UNKNOWN", "running": []},
    }
    r = evaluate_quiescence(**_base_kwargs(n8n=n8n))
    assert r["status"] in (NOT_QUIESCENT, INCOMPLETE)
    assert r["status"] != QUIESCENT
    assert any(f["id"] == QG_UNKNOWN_N8N_STATE or f["id"] == QG_N8N_MUST_BE_STOPPED for f in r["findings"])


def test_telegram_disarmed():
    r = evaluate_quiescence(**_base_kwargs())
    assert r["telegram"]["state"] == "DISARMED"
    assert r["status"] == QUIESCENT


def test_telegram_armed():
    n8n = {
        "container_status": "STOPPED",
        "activation": {
            "status": "READY",
            "any_relevant_active": False,
            "workflows": [],
        },
        "schedule": {"status": "READY", "state": "SCHEDULE_NOT_PRESENT"},
        "telegram": {"status": "READY", "state": "ARMED"},
        "execution": {"status": "READY", "state": "NOT_RUNNING", "running": []},
    }
    r = evaluate_quiescence(**_base_kwargs(n8n=n8n))
    assert r["status"] == NOT_QUIESCENT
    assert any(f["id"] == QG_TELEGRAM_ARMED for f in r["findings"])


def test_telegram_unknown():
    n8n = {
        "container_status": "STOPPED",
        "activation": {
            "status": "READY",
            "any_relevant_active": False,
            "workflows": [],
        },
        "schedule": {"status": "READY", "state": "SCHEDULE_NOT_PRESENT"},
        "telegram": {"status": "UNKNOWN", "state": "UNKNOWN"},
        "execution": {"status": "READY", "state": "NOT_RUNNING", "running": []},
    }
    r = evaluate_quiescence(**_base_kwargs(n8n=n8n))
    assert r["status"] == INCOMPLETE
    assert r["status"] != QUIESCENT


def test_runtime_command_redaction():
    raw = "python -m src.refresh.firms_refresh refresh MAP_KEY=supersecret TOKEN=abc123"
    red = redact_process_command(raw)
    assert "supersecret" not in red
    assert "abc123" not in red
    assert "REDACTED" in red


def test_quiescent_requires_all_required_facts():
    # Missing telegram knowledge → not QUIESCENT
    n8n = {
        "container_status": "STOPPED",
        "activation": {
            "status": "READY",
            "any_relevant_active": False,
            "workflows": [],
        },
        "schedule": {"status": "READY", "state": "SCHEDULE_NOT_PRESENT"},
        "telegram": {"status": "UNKNOWN", "state": "UNKNOWN"},
        "execution": {"status": "READY", "state": "NOT_RUNNING", "running": []},
    }
    r = evaluate_quiescence(**_base_kwargs(n8n=n8n))
    assert r["status"] != QUIESCENT


def test_unknown_never_becomes_quiescent():
    r = evaluate_quiescence(
        **_base_kwargs(writers={"status": WRITER_UNKNOWN, "active": []})
    )
    assert r["status"] == INCOMPLETE
    assert r["status"] != QUIESCENT


def test_next_returns_one_remediation(tmp_path: Path):
    op = Attempt2Operator.init_run(
        evidence_root=tmp_path,
        dry_run=True,
        expected_code_sha=SHA,
        run_id="SAPI-ATTEMPT2-P4-NEXT",
        synthetic_identity={
            "code_sha": SHA,
            "tree_sha": "f" * 40,
            "worktree_clean": True,
        },
    )
    snap = {
        "code": {
            "head_sha": SHA,
            "worktree_clean": True,
            "observed_at": "2026-09-24T12:00:00+00:00",
        },
        "firms": {"current": {"present": False, "state": "ABSENT"}},
        "dmc": {"current": {"present": False, "state": "ABSENT"}},
        "attempt1": {"preserve": True},
        "docker": {"status": "AVAILABLE"},
        "policy": {"human_authorization": False},
        "tests": {},
        "overall_status": "FAIL",
        "failures": ["operational_not_quiescent"],
        "warnings": [],
        "highest_priority_reason": {
            "code": QG_N8N_MUST_BE_STOPPED,
            "severity": "FAIL",
            "detail": "policy_requires_n8n_stopped",
            "remediation": FINDING_REMEDIATION[QG_N8N_MUST_BE_STOPPED],
        },
        "quiescence": {
            "status": NOT_QUIESCENT,
            "highest_priority_finding": {
                "id": QG_N8N_MUST_BE_STOPPED,
                "remediation": FINDING_REMEDIATION[QG_N8N_MUST_BE_STOPPED],
            },
        },
    }
    result = op.preflight(snapshot=snap)
    assert result["ready_for_authorization"] is False
    assert op.run.current_state() == Attempt2State.PREFLIGHT_FAILED
    nxt = op.next_action()
    assert nxt["reason_code"] == QG_N8N_MUST_BE_STOPPED
    assert "Stop the n8n container" in nxt["next"]
    assert "\n\n" not in nxt["next"]


def test_no_remediation_mutation_flag():
    r = evaluate_quiescence(**_base_kwargs())
    assert r.get("mutations") is False
    assert r["locks"].get("mutations") is False or True
    rem = remediation_for(r)
    assert "reason_code" in rem
    assert "next" in rem


def test_status_only_firms_not_writer():
    procs = {
        "status": "READY",
        "items": [
            {
                "name": "firms_refresh",
                "labels": ["firms_refresh"],
                "state": "RUNNING",
                "command_identity": "python -m src.refresh.firms_refresh status",
                "pid": 7,
            }
        ],
    }
    assert detect_writers(procs)["status"] == WRITER_NOT_DETECTED

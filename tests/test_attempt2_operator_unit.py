"""Unit tests for Attempt 2 operator primitives."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.ops.attempt2_operator.canonical import normalize_current
from src.ops.attempt2_operator.operator import Attempt2Operator
from src.ops.attempt2_operator.run_store import InvalidTransitionError
from src.ops.attempt2_operator.states import Attempt2State, HUMAN_GATES
from src.ops.attempt2_operator.validators import validate_preflight_snapshot

SHA = "7ef8d3c9f7ecb4758718255b8e48d6468f8613ea"


def _op(tmp_path: Path, expected: str = SHA) -> Attempt2Operator:
    return Attempt2Operator.init_run(
        evidence_root=tmp_path,
        dry_run=True,
        expected_code_sha=expected,
        run_id="SAPI-ATTEMPT2-TEST-UNIT",
        synthetic_identity={
            "code_sha": expected,
            "tree_sha": "t" * 40,
            "worktree_clean": True,
        },
    )


def test_unknown_not_absent():
    u = normalize_current(None)
    a = normalize_current({"present": False})
    assert u["state"] == "UNKNOWN"
    assert a["state"] == "ABSENT"
    assert u["state"] != a["state"]


def test_human_gates_defined():
    assert "ATTEMPT2_AUTHORIZATION" in HUMAN_GATES
    assert "TELEGRAM_AUTHORIZATION" in HUMAN_GATES
    assert "SCHEDULE_AUTHORIZATION" in HUMAN_GATES


def test_wrong_sha_blocks_preflight(tmp_path: Path):
    op = _op(tmp_path, expected=SHA)
    snap = {
        "code": {
            "head_sha": "deadbeef" * 5,
            "worktree_clean": True,
            "observed_at": "2026-09-24T00:00:00+00:00",
        },
        "firms": {"current": {"present": False}},
        "dmc": {"current": {"present": False}},
        "attempt1": {"preserve": True},
        "docker": {"status": "UNKNOWN"},
        "policy": {"human_authorization": False},
        "tests": {},
    }
    result = op.preflight(snapshot=snap)
    assert result["ready_for_authorization"] is False
    assert op.run.current_state() == Attempt2State.PREFLIGHT_FAILED


def test_dirty_tree_blocks(tmp_path: Path):
    op = _op(tmp_path)
    snap = {
        "code": {
            "head_sha": SHA,
            "worktree_clean": False,
            "status_entries": [" M src/x.py"],
            "observed_at": "2026-09-24T00:00:00+00:00",
        },
        "firms": {"current": {"present": False}},
        "dmc": {"current": {"present": False}},
        "attempt1": {"preserve": True},
        "docker": {"status": "UNAVAILABLE"},
        "policy": {"human_authorization": False},
        "tests": {},
    }
    result = op.preflight(snapshot=snap)
    assert result["ready_for_authorization"] is False


def test_unknown_current_blocks(tmp_path: Path):
    op = _op(tmp_path)
    snap = {
        "code": {
            "head_sha": SHA,
            "worktree_clean": True,
            "observed_at": "2026-09-24T00:00:00+00:00",
        },
        "firms": {"current": {}},  # UNKNOWN
        "dmc": {"current": {"present": False}},
        "attempt1": {"preserve": True},
        "docker": {"status": "AVAILABLE"},
        "policy": {"human_authorization": False},
        "tests": {},
    }
    result = op.preflight(snapshot=snap)
    assert result["firms_current"]["state"] == "UNKNOWN"
    assert result["ready_for_authorization"] is False


def test_stale_test_sha(tmp_path: Path):
    op = _op(tmp_path)
    snap = {
        "code": {
            "head_sha": SHA,
            "worktree_clean": True,
            "observed_at": "2026-09-24T00:00:00+00:00",
        },
        "firms": {"current": {"present": False}},
        "dmc": {"current": {"present": False}},
        "attempt1": {"preserve": True},
        "docker": {"status": "UNKNOWN"},
        "policy": {"human_authorization": False},
        "tests": {"code_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},
    }
    result = op.preflight(snapshot=snap)
    assert any(
        c["rule"] == "PF-TEST-SHA" and c["status"] == "FAIL" for c in result["checks"]
    )
    assert result["ready_for_authorization"] is False


def test_skip_state_rejected(tmp_path: Path):
    op = _op(tmp_path)
    with pytest.raises(InvalidTransitionError):
        op.run.set_state(
            Attempt2State.FIRMS_VALIDATED,
            event_type="SKIP",
            result="BAD",
        )


def test_status_idempotent(tmp_path: Path):
    op = _op(tmp_path)
    a = op.status()
    b = op.status()
    assert a == b
    assert op.run.events.count() == 1  # only init


def test_auth_not_inferred(tmp_path: Path):
    op = _op(tmp_path)
    auth = op.run.read_authorizations()
    assert auth["gates"]["ATTEMPT2_AUTHORIZATION"] is False
    # preflight snapshot claiming true must fail
    v = validate_preflight_snapshot(
        {
            "code": {"head_sha": SHA, "worktree_clean": True, "observed_at": "t"},
            "firms": {"current": {"present": False}},
            "dmc": {"current": {"present": False}},
            "attempt1": {"preserve": True},
            "docker": {"status": "UNKNOWN"},
            "policy": {"human_authorization": True},
            "tests": {},
        },
        expected_code_sha=SHA,
    )
    assert any(
        c["rule"] == "PF-AUTH-INFER" and c["status"] == "FAIL" for c in v["checks"]
    )


def test_crash_recovery(tmp_path: Path):
    op = _op(tmp_path)
    path = op.run.root
    op2 = Attempt2Operator.open_run(path)
    assert op2.status()["run_id"] == "SAPI-ATTEMPT2-TEST-UNIT"
    assert op2.run.current_state() == Attempt2State.NEW

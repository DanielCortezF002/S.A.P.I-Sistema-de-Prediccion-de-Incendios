"""Failure matrix for Attempt 2 operator."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.ops.attempt2_operator.operator import Attempt2Operator
from src.ops.attempt2_operator.states import Attempt2State

SHA = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"


def _ts() -> dict:
    return {
        "started_at": "2026-09-24T12:01:00+00:00",
        "finished_at": "2026-09-24T12:02:00+00:00",
    }


def _boot(tmp_path: Path) -> Attempt2Operator:
    op = Attempt2Operator.init_run(
        evidence_root=tmp_path,
        dry_run=True,
        expected_code_sha=SHA,
        run_id="SAPI-ATTEMPT2-FAIL",
        synthetic_identity={
            "code_sha": SHA,
            "tree_sha": "c" * 40,
            "worktree_clean": True,
        },
    )
    snap = {
        "code": {
            "head_sha": SHA,
            "worktree_clean": True,
            "observed_at": "2026-09-24T12:00:00+00:00",
        },
        "firms": {"current": {"present": False}},
        "dmc": {"current": {"present": False}},
        "attempt1": {"preserve": True},
        "docker": {"status": "UNKNOWN"},
        "policy": {"human_authorization": False},
        "tests": {},
    }
    assert op.preflight(snapshot=snap)["ready_for_authorization"]
    op.advance()
    op.authorize("ATTEMPT2_AUTHORIZATION")
    op.advance()
    return op


def test_unauthorized_firms_writer(tmp_path: Path):
    op = _boot(tmp_path)
    assert op.run.current_state() == Attempt2State.FIRMS_WRITER_REQUIRED
    # force pending without auth
    op.run.write_text("commands/firms.txt", "x")
    # manually illegal: try import without auth by hacking state
    op.run.set_state(
        Attempt2State.FIRMS_RESULT_PENDING,
        event_type="TEST_FORCE",
        result="TEST",
    )
    with pytest.raises(PermissionError):
        op.import_result(
            "firms",
            {
                "exit_code": 0,
                "started_at": "2026-09-24T12:01:00+00:00",
                "finished_at": "2026-09-24T12:02:00+00:00",
                "stdout": "",
                "stderr": "",
                "sanitization_status": "PASS",
                "schema_ok": True,
                "hash_ok": True,
                "pointer_ok": True,
                "firms_current_after": {"present": True},
            },
        )


def test_firms_exit65(tmp_path: Path):
    op = _boot(tmp_path)
    op.authorize("FIRMS_WRITER_AUTHORIZATION")
    out = op.import_result(
        "firms",
        {
            "exit_code": 65,
            "started_at": "2026-09-24T12:01:00+00:00",
            "finished_at": "2026-09-24T12:02:00+00:00",
            "stdout": "",
            "stderr": "schema mismatch",
            "sanitization_status": "PASS",
            "schema_ok": True,
            "hash_ok": True,
            "pointer_ok": True,
            "firms_current_after": {"present": False},
            "attempt1_modified": False,
        },
    )
    assert out["result"] == "FAIL"
    assert op.run.current_state() == Attempt2State.FIRMS_VALIDATION_FAILED


def test_firms_schema_mismatch(tmp_path: Path):
    op = _boot(tmp_path)
    op.authorize("FIRMS_WRITER_AUTHORIZATION")
    out = op.import_result(
        "firms",
        {
            "exit_code": 0,
            "started_at": "2026-09-24T12:01:00+00:00",
            "finished_at": "2026-09-24T12:02:00+00:00",
            "stdout": "",
            "stderr": "",
            "sanitization_status": "PASS",
            "schema_ok": False,
            "hash_ok": True,
            "pointer_ok": True,
            "firms_current_after": {"present": True},
        },
    )
    assert out["result"] == "FAIL"


def test_hash_mismatch(tmp_path: Path):
    op = _boot(tmp_path)
    op.authorize("FIRMS_WRITER_AUTHORIZATION")
    out = op.import_result(
        "firms",
        {
            "exit_code": 0,
            "started_at": "2026-09-24T12:01:00+00:00",
            "finished_at": "2026-09-24T12:02:00+00:00",
            "stdout": "",
            "stderr": "",
            "sanitization_status": "PASS",
            "schema_ok": True,
            "hash_ok": False,
            "pointer_ok": True,
            "firms_current_after": {"present": True},
        },
    )
    assert out["result"] == "FAIL"


def test_dmc_validation_failure(tmp_path: Path):
    op = _boot(tmp_path)
    op.authorize("FIRMS_WRITER_AUTHORIZATION")
    op.import_result(
        "firms",
        {
            "exit_code": 0,
            "started_at": "2026-09-24T12:01:00+00:00",
            "finished_at": "2026-09-24T12:02:00+00:00",
            "stdout": "",
            "stderr": "",
            "sanitization_status": "PASS",
            "schema_ok": True,
            "hash_ok": True,
            "pointer_ok": True,
            "firms_current_after": {"present": True},
        },
    )
    op.advance()
    op.authorize("DMC_WRITER_AUTHORIZATION")
    out = op.import_result(
        "dmc",
        {
            "exit_code": 65,
            "started_at": "2026-09-24T12:01:00+00:00",
            "finished_at": "2026-09-24T12:02:00+00:00",
            "quality_ok": False,
            "pointer_ok": False,
            "sanitization_status": "PASS",
            "dmc_current_after": {"present": False},
        },
    )
    assert out["result"] == "FAIL"
    assert op.run.current_state() == Attempt2State.DMC_VALIDATION_FAILED


def test_invalid_scoring_contract(tmp_path: Path):
    op = _boot(tmp_path)
    # fast-forward via successive success imports
    op.authorize("FIRMS_WRITER_AUTHORIZATION")
    op.import_result(
        "firms",
        {
            "exit_code": 0,
            "started_at": "2026-09-24T12:01:00+00:00",
            "finished_at": "2026-09-24T12:02:00+00:00",
            "stdout": "",
            "stderr": "",
            "sanitization_status": "PASS",
            "schema_ok": True,
            "hash_ok": True,
            "pointer_ok": True,
            "firms_current_after": {"present": True},
        },
    )
    op.advance()
    op.authorize("DMC_WRITER_AUTHORIZATION")
    op.import_result(
        "dmc",
        {
            "exit_code": 0,
            "started_at": "2026-09-24T12:01:00+00:00",
            "finished_at": "2026-09-24T12:02:00+00:00",
            "quality_ok": True,
            "pointer_ok": True,
            "sanitization_status": "PASS",
            "dmc_current_after": {"present": True},
        },
    )
    op.advance()
    out = op.import_result(
        "scoring",
        {
            "cells": [{"cell_id": "VP-001", "score": 0.1, "rank": 1}],
            "inputs_fingerprint": "x",
        },
    )
    assert out["result"] == "FAIL"
    assert op.run.current_state() == Attempt2State.SCORING_FAILED


def test_bridge_500(tmp_path: Path):
    op = _boot(tmp_path)
    op.authorize("FIRMS_WRITER_AUTHORIZATION")
    op.import_result(
        "firms",
        {
            "exit_code": 0,
            "started_at": "2026-09-24T12:01:00+00:00",
            "finished_at": "2026-09-24T12:02:00+00:00",
            "stdout": "",
            "stderr": "",
            "sanitization_status": "PASS",
            "schema_ok": True,
            "hash_ok": True,
            "pointer_ok": True,
            "firms_current_after": {"present": True},
        },
    )
    op.advance()
    op.authorize("DMC_WRITER_AUTHORIZATION")
    op.import_result(
        "dmc",
        {
            "exit_code": 0,
            "started_at": "2026-09-24T12:01:00+00:00",
            "finished_at": "2026-09-24T12:02:00+00:00",
            "quality_ok": True,
            "pointer_ok": True,
            "sanitization_status": "PASS",
            "dmc_current_after": {"present": True},
        },
    )
    op.advance()
    cells = [{"cell_id": f"VP-{i:03d}", "score": 0.5, "rank": i} for i in range(1, 51)]
    op.import_result(
        "scoring",
        {
            "cells": cells,
            "inputs_fingerprint": "d" * 64,
            "model_sha": "m" * 64,
        },
    )
    op.advance()
    out = op.import_result(
        "bridge",
        {
            "http_status": 500,
            "body": {"status": "error", "error_type": "internal_error"},
        },
    )
    assert out["result"] == "FAIL"
    assert op.run.current_state() == Attempt2State.BRIDGE_FAILED


def test_n8n_fail_closed_incomplete(tmp_path: Path):
    op = _boot(tmp_path)
    # reach n8n
    op.authorize("FIRMS_WRITER_AUTHORIZATION")
    op.import_result(
        "firms",
        {
            "exit_code": 0,
            "started_at": "2026-09-24T12:01:00+00:00",
            "finished_at": "2026-09-24T12:02:00+00:00",
            "stdout": "",
            "stderr": "",
            "sanitization_status": "PASS",
            "schema_ok": True,
            "hash_ok": True,
            "pointer_ok": True,
            "firms_current_after": {"present": True},
        },
    )
    op.advance()
    op.authorize("DMC_WRITER_AUTHORIZATION")
    op.import_result(
        "dmc",
        {
            "exit_code": 0,
            "started_at": "2026-09-24T12:01:00+00:00",
            "finished_at": "2026-09-24T12:02:00+00:00",
            "quality_ok": True,
            "pointer_ok": True,
            "sanitization_status": "PASS",
            "dmc_current_after": {"present": True},
        },
    )
    op.advance()
    cells = [{"cell_id": f"VP-{i:03d}", "score": 0.5, "rank": i} for i in range(1, 51)]
    op.import_result(
        "scoring",
        {"cells": cells, "inputs_fingerprint": "e" * 64, "model_sha": "m" * 64},
    )
    op.advance()
    op.import_result(
        "bridge",
        {
            "http_status": 200,
            "body": {"status": "ok", "cells": cells, "inputs_fingerprint": "e" * 64},
        },
    )
    op.advance()
    out = op.import_result(
        "n8n",
        {
            "schedule_enabled": False,
            "telegram_sent": False,
            "score_path_ok": True,
            "fail_closed_cases": {"prototype_unavailable": False},  # incomplete
        },
    )
    assert out["result"] == "FAIL"


def test_telegram_without_authorization(tmp_path: Path):
    op = _boot(tmp_path)
    op.authorize("FIRMS_WRITER_AUTHORIZATION")
    op.import_result(
        "firms",
        {
            "exit_code": 0,
            "started_at": "2026-09-24T12:01:00+00:00",
            "finished_at": "2026-09-24T12:02:00+00:00",
            "stdout": "",
            "stderr": "",
            "sanitization_status": "PASS",
            "schema_ok": True,
            "hash_ok": True,
            "pointer_ok": True,
            "firms_current_after": {"present": True},
        },
    )
    op.advance()
    op.authorize("DMC_WRITER_AUTHORIZATION")
    op.import_result(
        "dmc",
        {
            "exit_code": 0,
            "started_at": "2026-09-24T12:01:00+00:00",
            "finished_at": "2026-09-24T12:02:00+00:00",
            "quality_ok": True,
            "pointer_ok": True,
            "sanitization_status": "PASS",
            "dmc_current_after": {"present": True},
        },
    )
    op.advance()
    cells = [{"cell_id": f"VP-{i:03d}", "score": 0.5, "rank": i} for i in range(1, 51)]
    op.import_result(
        "scoring",
        {"cells": cells, "inputs_fingerprint": "f" * 64, "model_sha": "m" * 64},
    )
    op.advance()
    op.import_result(
        "bridge",
        {
            "http_status": 200,
            "body": {"status": "ok", "cells": cells, "inputs_fingerprint": "f" * 64},
        },
    )
    op.advance()
    with pytest.raises(PermissionError):
        op.import_result(
            "n8n",
            {
                "schedule_enabled": False,
                "telegram_sent": True,
                "score_path_ok": True,
                "fail_closed_cases": {
                    "prototype_unavailable": True,
                    "data_unavailable": True,
                    "internal_error": True,
                },
            },
        )


def test_schedule_without_authorization(tmp_path: Path):
    op = _boot(tmp_path)
    op.authorize("FIRMS_WRITER_AUTHORIZATION")
    op.import_result(
        "firms",
        {
            "exit_code": 0,
            "started_at": "2026-09-24T12:01:00+00:00",
            "finished_at": "2026-09-24T12:02:00+00:00",
            "stdout": "",
            "stderr": "",
            "sanitization_status": "PASS",
            "schema_ok": True,
            "hash_ok": True,
            "pointer_ok": True,
            "firms_current_after": {"present": True},
        },
    )
    op.advance()
    op.authorize("DMC_WRITER_AUTHORIZATION")
    op.import_result(
        "dmc",
        {
            "exit_code": 0,
            "started_at": "2026-09-24T12:01:00+00:00",
            "finished_at": "2026-09-24T12:02:00+00:00",
            "quality_ok": True,
            "pointer_ok": True,
            "sanitization_status": "PASS",
            "dmc_current_after": {"present": True},
        },
    )
    op.advance()
    cells = [{"cell_id": f"VP-{i:03d}", "score": 0.5, "rank": i} for i in range(1, 51)]
    op.import_result(
        "scoring",
        {"cells": cells, "inputs_fingerprint": "g" * 64, "model_sha": "m" * 64},
    )
    op.advance()
    op.import_result(
        "bridge",
        {
            "http_status": 200,
            "body": {"status": "ok", "cells": cells, "inputs_fingerprint": "g" * 64},
        },
    )
    op.advance()
    with pytest.raises(PermissionError):
        op.import_result(
            "n8n",
            {
                "schedule_enabled": True,
                "telegram_sent": False,
                "score_path_ok": True,
                "fail_closed_cases": {
                    "prototype_unavailable": True,
                    "data_unavailable": True,
                    "internal_error": True,
                },
            },
        )


def test_different_evidence_no_overwrite(tmp_path: Path):
    op = _boot(tmp_path)
    op.authorize("FIRMS_WRITER_AUTHORIZATION")
    payload = {
        "exit_code": 0,
        "started_at": "2026-09-24T12:01:00+00:00",
        "finished_at": "2026-09-24T12:02:00+00:00",
        "stdout": "a",
        "stderr": "",
        "sanitization_status": "PASS",
        "schema_ok": True,
        "hash_ok": True,
        "pointer_ok": True,
        "firms_current_after": {"present": True},
    }
    op.import_result("firms", payload)
    payload2 = dict(payload)
    payload2["stdout"] = "b"
    with pytest.raises(RuntimeError, match="Refusing to overwrite"):
        op.import_result("firms", payload2)


def test_tampered_evidence_detected(tmp_path: Path):
    op = _boot(tmp_path)
    op.authorize("FIRMS_WRITER_AUTHORIZATION")
    op.import_result(
        "firms",
        {
            "exit_code": 0,
            "started_at": "2026-09-24T12:01:00+00:00",
            "finished_at": "2026-09-24T12:02:00+00:00",
            "stdout": "",
            "stderr": "",
            "sanitization_status": "PASS",
            "schema_ok": True,
            "hash_ok": True,
            "pointer_ok": True,
            "firms_current_after": {"present": True},
        },
    )
    target = op.run.root / "imports" / "firms.json"
    target.write_text(target.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    assert op.verify_manifest_integrity() is False

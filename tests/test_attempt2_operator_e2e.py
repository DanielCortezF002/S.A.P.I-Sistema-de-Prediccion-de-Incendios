"""Synthetic end-to-end Attempt 2 (no network, no stores)."""

from __future__ import annotations

from pathlib import Path

from src.ops.attempt2_operator.operator import Attempt2Operator
from src.ops.attempt2_operator.states import Attempt2State

SHA = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"


def _good_preflight(sha: str = SHA) -> dict:
    return {
        "code": {
            "head_sha": sha,
            "worktree_clean": True,
            "observed_at": "2026-09-24T12:00:00+00:00",
        },
        "firms": {"current": {"present": False}},
        "dmc": {"current": {"present": False}},
        "attempt1": {"preserve": True},
        "docker": {"status": "UNAVAILABLE"},
        "policy": {"human_authorization": False},
        "tests": {"code_sha": sha},
    }


def _cells() -> list[dict]:
    return [
        {"cell_id": f"VP-{i:03d}", "score": 1.0 - i * 0.01, "rank": i}
        for i in range(1, 51)
    ]


def test_synthetic_e2e_accepted(tmp_path: Path):
    op = Attempt2Operator.init_run(
        evidence_root=tmp_path,
        dry_run=True,
        expected_code_sha=SHA,
        run_id="SAPI-ATTEMPT2-SYNTH-E2E",
        synthetic_identity={
            "code_sha": SHA,
            "tree_sha": "b" * 40,
            "worktree_clean": True,
        },
    )
    assert op.preflight(snapshot=_good_preflight())["ready_for_authorization"]
    assert op.run.current_state() == Attempt2State.PREFLIGHT_READY

    op.advance()
    assert op.run.current_state() == Attempt2State.ATTEMPT2_AUTHORIZATION_REQUIRED
    op.authorize("ATTEMPT2_AUTHORIZATION")
    assert op.run.current_state() == Attempt2State.ATTEMPT2_AUTHORIZED
    op.advance()
    assert op.run.current_state() == Attempt2State.FIRMS_WRITER_REQUIRED

    op.authorize("FIRMS_WRITER_AUTHORIZATION")
    assert op.run.current_state() == Attempt2State.FIRMS_RESULT_PENDING
    assert (op.run.root / "commands" / "firms.txt").exists()

    firms = {
        "exit_code": 0,
        "started_at": "2026-09-24T12:01:00+00:00",
        "finished_at": "2026-09-24T12:02:00+00:00",
        "stdout": "ok",
        "stderr": "",
        "stdout_sha256": None,
        "stderr_sha256": None,
        "sanitization_status": "PASS",
        "schema_ok": True,
        "hash_ok": True,
        "pointer_ok": True,
        "firms_current_after": {
            "present": True,
            "path": "processed/firms/CURRENT.json",
        },
        "attempt1_modified": False,
        "started_at": "2026-09-24T12:01:00+00:00",
        "finished_at": "2026-09-24T12:02:00+00:00",
        "metadata": {"http_status": 200, "content_type": "text/csv"},
    }
    assert op.import_result("firms", firms)["result"] == "PASS"
    assert op.run.current_state() == Attempt2State.FIRMS_VALIDATED

    # idempotent duplicate
    assert op.import_result("firms", firms)["result"] == "DUPLICATE"

    op.advance()
    op.authorize("DMC_WRITER_AUTHORIZATION")
    dmc = {
        "exit_code": 0,
        "started_at": "2026-09-24T12:01:00+00:00",
        "finished_at": "2026-09-24T12:02:00+00:00",
        "quality_ok": True,
        "pointer_ok": True,
        "sanitization_status": "PASS",
        "dmc_current_after": {"present": True},
        "attempt1_modified": False,
        "stdout": "",
        "stderr": "",
    }
    assert op.import_result("dmc", dmc)["result"] == "PASS"
    op.advance()

    scoring = {
        "cells": _cells(),
        "inputs_fingerprint": "c" * 64,
        "frozen_fingerprint": "33c2eacc49bd0cc130928b5bd182ec523e63614f0e3dd97a129a8d4657f231ff",
        "model_sha": "ac017bef1f42a30ac74ba3e3787368c4418798b2d562adcfba01c923cff2173f",
        "confuse_fingerprints": False,
    }
    assert op.import_result("scoring", scoring)["result"] == "PASS"
    op.advance()

    bridge = {
        "http_status": 200,
        "body": {
            "status": "ok",
            "cells": _cells(),
            "inputs_fingerprint": "c" * 64,
        },
    }
    assert op.import_result("bridge", bridge)["result"] == "PASS"
    op.advance()

    n8n = {
        "schedule_enabled": False,
        "telegram_sent": False,
        "score_path_ok": True,
        "fail_closed_cases": {
            "prototype_unavailable": True,
            "data_unavailable": True,
            "internal_error": True,
        },
    }
    assert op.import_result("n8n", n8n)["result"] == "PASS"
    op.advance()
    assert op.run.current_state() == Attempt2State.ACCEPTANCE_READY
    op.advance()
    assert op.run.current_state() == Attempt2State.ACCEPTED

    report = op.report()
    assert report["report"]["distinction"]["scientific_model_validation"] is False
    assert report["report"]["distinction"]["software_operational_acceptance"] is True

    # crash reopen
    op2 = Attempt2Operator.open_run(op.run.root)
    assert op2.run.current_state() == Attempt2State.ACCEPTED
    assert op2.verify_manifest_integrity() is True

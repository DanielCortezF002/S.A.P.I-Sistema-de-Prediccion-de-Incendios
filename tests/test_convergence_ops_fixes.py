"""Regression tests for the Operations fixes NEW-1 (init fail-open) and SEM-4 (FIRMS v3 pointer)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.ops.attempt2_operator.collectors.firms_current import collect_firms_current
from src.ops.attempt2_operator.operator import Attempt2Operator
from src.ops.attempt2_operator.output_plane_manifest import (
    compute_output_manifest_fingerprint,
)


def _record(tmp_path: Path, *, valid: bool) -> Path:
    artifact = tmp_path / "artifact.json"
    artifact.write_text("{}", encoding="utf-8")
    import hashlib

    rec = {
        "schema_version": 1,
        "output_contract_version": "sapi-output-v1",
        "accepted_score_artifact_path": str(artifact),
        "accepted_score_artifact_sha256": hashlib.sha256(
            artifact.read_bytes()
        ).hexdigest(),
    }
    rec["manifest_fingerprint"] = (
        compute_output_manifest_fingerprint(rec) if valid else "0" * 64
    )
    path = tmp_path / ("ok.json" if valid else "bad.json")
    path.write_text(json.dumps(rec), encoding="utf-8")
    return path


def test_new1_init_run_rejects_unverified_output_manifest(tmp_path):
    with pytest.raises(ValueError, match="Output plane manifest verification failed"):
        Attempt2Operator.init_run(
            evidence_root=tmp_path / "ev",
            expected_code_sha="c" * 40,
            output_manifest=_record(tmp_path, valid=False),
        )


def test_new1_init_run_binds_only_verified_fingerprint(tmp_path):
    good = _record(tmp_path, valid=True)
    op = Attempt2Operator.init_run(
        evidence_root=tmp_path / "ev1", expected_code_sha="c" * 40, output_manifest=good
    )
    assert (
        op.run.read_state()["output_manifest_fingerprint"]
        == json.loads(good.read_text("utf-8"))["manifest_fingerprint"]
    )
    dry = Attempt2Operator.init_run(
        evidence_root=tmp_path / "ev2",
        dry_run=True,
        synthetic_identity={"code_sha": "c" * 40, "tree_sha": "d" * 40},
        expected_code_sha="c" * 40,
        output_manifest=_record(tmp_path, valid=False),
    )
    assert (
        dry.run.read_state()["output_manifest_fingerprint"] is None
    )  # never a tampered fp


@pytest.mark.parametrize("schema,ok", [(2, True), (3, True), (9, False)])
def test_sem4_firms_collector_accepts_v2_and_v3_pointers(tmp_path, schema, ok):
    pointer = tmp_path / "CURRENT.json"
    pointer.write_text(
        json.dumps({"schema_version": schema, "relative_path": "v.csv"}), "utf-8"
    )
    result = collect_firms_current(pointer_path=pointer)
    assert result["state"] == "PRESENT" and result["schema_ok"] is ok

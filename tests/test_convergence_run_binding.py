"""RC1 convergence: a per-run Output acceptance record binds to exactly one Attempt2 run.

SYNTHETIC only (dry-run operator, synthetic bridge body, temp dirs). No notifications.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import tools.n8n_bridge.app as bridge_app
from src.convergence import output_acceptance as oa
from src.ops.attempt2_operator.operator import Attempt2Operator
from src.ops.attempt2_operator.output_plane_manifest import (
    compute_output_manifest_fingerprint,
)
from src.output import accepted_run as ar
from src.output.synthetic import synthetic_result
from test_convergence_output_acceptance import (  # noqa: F401 (fixture reuse)
    RUN_ID,
    plane,
    real_hash_before,
)


def _body(**changes) -> dict:
    mp = pytest.MonkeyPatch()
    mp.setattr(bridge_app, "score_current_grid", lambda: synthetic_result(**changes))
    mp.setattr(bridge_app, "_read_metadata_json", lambda: None)
    try:
        return TestClient(bridge_app.app).get("/score").json()
    finally:
        mp.undo()


def _artifact(body: dict, folder: Path) -> Path:
    doc = ar.build_artifact(
        body,
        data_origin=ar.DATA_SYNTHETIC,
        captured_at="2026-09-25T12:00:00+00:00",
        source_url="http://127.0.0.1:8600/score",
    )
    return ar.write_artifact(doc, folder)[0]


def _record(pl, artifact: Path, folder: Path, run_id: str = RUN_ID) -> Path:
    rec = oa.build_acceptance_record(
        pl[0], artifact, expected_output_fingerprint=pl[1], run_id=run_id
    )
    return oa.write_record(rec, folder)[0]


def _run(tmp_path: Path, run_id: str = RUN_ID) -> Attempt2Operator:
    return Attempt2Operator.init_run(
        evidence_root=tmp_path / f"ev-{run_id}",
        dry_run=True,
        run_id=run_id,
        synthetic_identity={"code_sha": "c" * 40, "tree_sha": "d" * 40},
        expected_code_sha="c" * 40,
    )


def _import(op: Attempt2Operator, name: str, payload: dict) -> None:
    op.run.write_json(f"imports/{name}.json", payload)  # synthetic imported evidence


@pytest.fixture
def bound(plane, tmp_path):  # noqa: F811
    body = _body()
    op = _run(tmp_path)
    _import(op, "scoring", {"inputs_fingerprint": body["inputs_fingerprint"]})
    _import(op, "bridge", {"http_status": 200, "body": body})
    record = _record(plane, _artifact(body, tmp_path / "runs"), tmp_path / "acc")
    return op, body, record


def test_matching_record_binds_before_and_after_acceptance(plane, bound):  # noqa: F811
    op, body, record = bound
    assert (
        oa.verify_acceptance_record(
            record, output_manifest_path=plane[0], expected_output_fingerprint=plane[1]
        )
        == []
    )
    assert oa.verify_run_binding(record, op.run.root) == []
    assert oa.verify_run_binding(record, op.run.root, bridge_body=body) == []
    assert op.accept_output_manifest(record)["status"] == "PASS"
    assert oa.verify_run_binding(record, op.run.root) == []


def test_wrong_run_id_rejected_even_when_resigned(plane, bound):  # noqa: F811
    op, _, record = bound
    rec = json.loads(record.read_text("utf-8"))
    rec["run_id"] = "SAPI-ATTEMPT2-OTHER"
    rec["manifest_fingerprint"] = compute_output_manifest_fingerprint(rec)
    record.write_text(json.dumps(rec), "utf-8")
    assert "run_id_mismatch" in oa.verify_run_binding(record, op.run.root)


def test_cross_run_reuse_rejected(plane, bound, tmp_path):  # noqa: F811
    _, body, record = bound
    other = _run(tmp_path, "SAPI-ATTEMPT2-SECOND")
    _import(other, "bridge", {"http_status": 200, "body": body})  # even the same score
    assert "run_id_mismatch" in oa.verify_run_binding(record, other.run.root)


def test_wrong_score_artifact_rejected(plane, bound, tmp_path):  # noqa: F811
    op, _, _ = bound
    other_body = _body(age_hours=2.0)
    foreign = _record(plane, _artifact(other_body, tmp_path / "o"), tmp_path / "oacc")
    assert (
        oa.verify_acceptance_record(
            foreign, output_manifest_path=plane[0], expected_output_fingerprint=plane[1]
        )
        == []
    )  # a valid record ...
    assert "score_artifact_not_this_bridge_result" in oa.verify_run_binding(
        foreign, op.run.root
    )  # ... of another score


def test_stale_record_of_an_earlier_score_rejected(plane, tmp_path):  # noqa: F811
    op = _run(tmp_path)
    earlier = _body(age_hours=3.0)
    stale = _record(plane, _artifact(earlier, tmp_path / "r0"), tmp_path / "a0")
    latest = _body()
    _import(op, "scoring", {"inputs_fingerprint": "0" * 64})  # run re-scored since
    _import(op, "bridge", {"http_status": 200, "body": latest})
    reasons = oa.verify_run_binding(stale, op.run.root)
    assert {"score_artifact_not_this_bridge_result", "stale_vs_run_scoring"} <= set(
        reasons
    )


def test_wrong_output_fingerprint_rejected(plane, bound, tmp_path):  # noqa: F811
    op, body, record = bound
    assert oa.verify_acceptance_record(
        record, output_manifest_path=plane[0], expected_output_fingerprint="0" * 64
    )
    state = op.run.read_state()
    state["output_manifest_fingerprint"] = "e" * 64  # run already bound elsewhere
    op.run.write_state(state)
    assert "run_bound_to_another_record" in oa.verify_run_binding(record, op.run.root)


def test_wrong_notification_identity_rejected_even_when_resigned(
    plane, bound  # noqa: F811
):
    op, _, record = bound
    rec = json.loads(record.read_text("utf-8"))
    rec["notification_identity"] = "f" * 64
    rec["manifest_fingerprint"] = compute_output_manifest_fingerprint(rec)
    record.write_text(json.dumps(rec), "utf-8")
    assert "notification_identity_mismatch" in oa.verify_run_binding(
        record, op.run.root
    )
    assert oa.verify_acceptance_record(
        record, output_manifest_path=plane[0], expected_output_fingerprint=plane[1]
    )


def test_missing_or_invalid_bridge_result_rejected(
    plane, bound, tmp_path  # noqa: F811
):
    _, body, record = bound
    fresh = _run(tmp_path / "fresh")  # same run_id, no bridge import yet
    (fresh.run.root / "imports" / "bridge.json").unlink(missing_ok=True)
    assert "bridge_result_missing" in oa.verify_run_binding(record, fresh.run.root)
    broken = dict(body, cells=body["cells"][:49])
    assert "bridge_result_invalid" in oa.verify_run_binding(
        record, fresh.run.root, bridge_body=broken
    )


@pytest.mark.parametrize("run_id", ["", "../x", "a b", "x" * 200, None])
def test_invalid_run_id_refused_at_build(plane, tmp_path, run_id):  # noqa: F811
    artifact = _artifact(_body(), tmp_path / "runs")
    with pytest.raises(ar.ArtifactError):
        oa.build_acceptance_record(
            plane[0], artifact, expected_output_fingerprint=plane[1], run_id=run_id
        )


def test_cli_verify_with_run(plane, bound, tmp_path, capsys):  # noqa: F811
    op, body, record = bound
    common = [
        "--output-manifest",
        str(plane[0]),
        "--expect-output-fingerprint",
        plane[1],
    ]
    assert oa.main(["verify", str(record), *common, "--run", str(op.run.root)]) == 0
    capsys.readouterr()
    other = _run(tmp_path, "SAPI-ATTEMPT2-THIRD")
    bridge = tmp_path / "bridge.json"
    bridge.write_text(json.dumps({"http_status": 200, "body": body}), "utf-8")
    code = oa.main(
        [
            "verify",
            str(record),
            *common,
            "--run",
            str(other.run.root),
            "--bridge",
            str(bridge),
        ]
    )
    assert code == oa.EXIT_REJECTED
    assert "run_id_mismatch" in json.loads(capsys.readouterr().out)["reasons"]

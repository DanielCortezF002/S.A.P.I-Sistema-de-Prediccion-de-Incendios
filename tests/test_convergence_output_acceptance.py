"""RC1 BLOCKER 2: Output → Operations acceptance (src/convergence/output_acceptance.py).

The real persistent Output plane manifest is used read-only when present (sibling
SAPI-71-evidence directory); otherwise a manifest is generated in-process by the
Output readiness producer. Accepted runs are SYNTHETIC. Only temp copies are mutated.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import tools.n8n_bridge.app as bridge_app
from src.convergence import output_acceptance as oa
from src.ops.attempt2_operator.operator import Attempt2Operator
from src.ops.attempt2_operator.output_plane_manifest import (
    compute_output_manifest_fingerprint,
    verify_output_plane_manifest,
)
from src.output import accepted_run as ar
from src.output import readiness as rd
from src.output.synthetic import synthetic_result

REPO = Path(__file__).resolve().parents[1]
REAL_OUTPUT_MANIFEST = (
    REPO.parent
    / "SAPI-71-evidence"
    / "output-plane-rc1-2026-09-25"
    / "OUTPUT_PLANE_MANIFEST.json"
)
REAL_OUTPUT_FP = "9441f7178805f48ab6d7f563b8bd5c70e555ba621bfb6779ba2360cec61b01a3"
RUN_ID = "SAPI-ATTEMPT2-CONVERGENCE-TEST"
needs_real = pytest.mark.skipif(
    not REAL_OUTPUT_MANIFEST.is_file(), reason="real Output manifest absent"
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def real_hash_before():
    return _sha(REAL_OUTPUT_MANIFEST) if REAL_OUTPUT_MANIFEST.is_file() else None


@pytest.fixture(scope="module")
def plane(tmp_path_factory, real_hash_before):
    """(path, fingerprint) of an Output plane manifest: the real one, else generated."""
    if REAL_OUTPUT_MANIFEST.is_file():
        return REAL_OUTPUT_MANIFEST, REAL_OUTPUT_FP
    manifest = rd.build_manifest(rd.run_checks())
    if manifest["readiness"]["status"] != rd.READY:  # e.g. no `node`: never fake READY
        pytest.skip(
            f"generated Output plane manifest is {manifest['readiness']['status']}"
        )
    path = tmp_path_factory.mktemp("plane") / "OUTPUT_PLANE_MANIFEST.json"
    path.write_text(
        json.dumps(manifest, ensure_ascii=True, indent=2, sort_keys=True), "utf-8"
    )
    return path, manifest["manifest_fingerprint"]


def _synthetic_accepted_run(folder: Path, **result_changes) -> tuple[Path, dict]:
    mp = pytest.MonkeyPatch()
    mp.setattr(
        bridge_app, "score_current_grid", lambda: synthetic_result(**result_changes)
    )
    mp.setattr(bridge_app, "_read_metadata_json", lambda: None)
    try:
        body = TestClient(bridge_app.app).get("/score").json()
    finally:
        mp.undo()
    doc = ar.build_artifact(
        body,
        data_origin=ar.DATA_SYNTHETIC,
        captured_at="2026-09-24T13:05:00+00:00",
        source_url="http://127.0.0.1:8600/score",
    )
    path, _ = ar.write_artifact(doc, folder)
    return path, doc


@pytest.fixture
def accepted(tmp_path):
    return _synthetic_accepted_run(tmp_path / "runs")


@pytest.fixture
def record(plane, accepted, tmp_path):
    plane_path, plane_fp = plane
    run_path, doc = accepted
    rec = oa.build_acceptance_record(
        plane_path,
        run_path,
        expected_output_fingerprint=plane_fp,
        run_id=RUN_ID,
        expected_artifact_fingerprint=doc["artifact_fingerprint"],
    )
    path, _ = oa.write_record(rec, tmp_path / "acceptance")
    return path, rec


# --- before-state and producer parity ---------------------------------------------------------


@needs_real
def test_control_real_plane_manifest_is_not_an_operations_acceptance_record():
    verdict = verify_output_plane_manifest(REAL_OUTPUT_MANIFEST)
    codes = {f["code"] for f in verdict["findings"]}
    assert verdict["status"] == "FAIL" and not verdict["ready"]
    assert {
        "UNSUPPORTED_OUTPUT_MANIFEST_SCHEMA",
        "MISSING_REQUIRED_FIELD",
        "TAMPERED_OUTPUT_ACCEPTANCE",
    } <= codes  # the false TAMPERED is a recipe mismatch


@needs_real
def test_real_plane_manifest_verifies_with_producer_recipe_and_anchor():
    reasons, manifest = oa.verify_output_plane(
        REAL_OUTPUT_MANIFEST, expected_fingerprint=REAL_OUTPUT_FP
    )
    assert reasons == [] and manifest["output_code"]["git_head"] == (
        "dd96a39372146cbbec2f621773582a06de815a07"
    )
    wrong = oa.verify_output_plane(REAL_OUTPUT_MANIFEST, expected_fingerprint="0" * 64)[
        0
    ]
    assert wrong == ["output_manifest_fingerprint_not_expected"]
    assert (
        "output_manifest_anchor_missing"
        in oa.verify_output_plane(REAL_OUTPUT_MANIFEST, expected_fingerprint=None)[0]
    )


def test_producer_recipe_parity():
    results = [{"name": "x", "status": rd.PASS, "detail": "Ñ → ≡ non-ascii"}]
    manifest = rd.build_manifest(results)
    assert oa.output_plane_fingerprint(manifest) == manifest["manifest_fingerprint"]


# --- the resolution: record accepted by the unchanged Operations consumer and operator ---------


def test_record_is_accepted_by_operations_consumer_and_operator(
    plane, accepted, record, tmp_path
):
    plane_path, plane_fp = plane
    run_path, doc = accepted
    rec_path, rec = record
    verdict = verify_output_plane_manifest(rec_path)
    assert verdict["status"] == "PASS" and verdict["ready"] is True
    assert verdict["manifest_fingerprint"] == rec["manifest_fingerprint"]
    assert verdict["output_contract_version"] == "sapi-output-v1"
    assert rec["output_plane_manifest_fingerprint"] == plane_fp
    assert rec["accepted_run_artifact_fingerprint"] == doc["artifact_fingerprint"]
    assert rec["notification_identity"] == doc["identities"]["notification_identity"]
    assert rec["authorization"].startswith("NONE")
    assert (
        oa.verify_acceptance_record(
            rec_path,
            output_manifest_path=plane_path,
            expected_output_fingerprint=plane_fp,
            expected_artifact_fingerprint=doc["artifact_fingerprint"],
        )
        == []
    )

    op = Attempt2Operator.init_run(
        evidence_root=tmp_path / "attempt2",
        dry_run=True,
        synthetic_identity={"code_sha": "c" * 40, "tree_sha": "t" * 40},
        expected_code_sha="c" * 40,
        output_manifest=rec_path,
    )
    state = op.run.read_state()
    assert state["output_manifest_fingerprint"] == rec["manifest_fingerprint"]
    accepted_ver = op.accept_output_manifest(rec_path)
    assert accepted_ver["status"] == "PASS"
    ctx = json.loads(
        (op.run.root / "identity" / "rc1_execution_context.json").read_text("utf-8")
    )
    assert ctx["output_plane_manifest_fingerprint"] == rec["manifest_fingerprint"]


def test_cli_build_and_verify(plane, accepted, tmp_path, capsys):
    plane_path, plane_fp = plane
    run_path, doc = accepted
    out = tmp_path / "cli"
    common = [
        "--output-manifest",
        str(plane_path),
        "--expect-output-fingerprint",
        plane_fp,
    ]
    assert (
        oa.main(
            [
                "build",
                *common,
                "--run-id",
                RUN_ID,
                "--accepted-run",
                str(run_path),
                "--out",
                str(out),
            ]
        )
        == 0
    )
    built = json.loads(capsys.readouterr().out)
    assert oa.main(["verify", built["path"], *common]) == 0
    assert (
        oa.main(
            [
                "build",
                *common,
                "--run-id",
                RUN_ID,
                "--accepted-run",
                str(run_path),
                "--out",
                str(ar.REPO_ROOT / "models"),
            ]
        )
        == oa.EXIT_USAGE
    )  # unsafe destination


# --- Phase 6: Output plane manifest tamper matrix (temp copies only) ---------------------------


def _mutated_plane(plane, tmp_path, mutate, refingerprint):
    manifest = json.loads(Path(plane[0]).read_text(encoding="utf-8"))
    mutate(manifest)
    if refingerprint:
        manifest["manifest_fingerprint"] = oa.output_plane_fingerprint(manifest)
    path = tmp_path / "tampered_plane.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    return path


PLANE_TAMPER = {
    "fingerprint_mutation": (lambda m: m.update(manifest_fingerprint="1" * 64), False),
    "malformed_fingerprint": (lambda m: m.update(manifest_fingerprint="xyz"), False),
    "output_sha_mutation": (lambda m: m["output_code"].update(git_head="e" * 40), True),
    "sources_hash_mutation": (
        lambda m: m["output_code"].update(sources_sha256="0" * 64),
        True,
    ),
    "unknown_schema": (
        lambda m: m.update(manifest_schema_version="sapi-output-plane-manifest-v0"),
        True,
    ),
    "missing_field": (lambda m: m.pop("bridge_contract_version"), True),
    "unknown_field": (lambda m: m.update(cookies="x"), True),
    "not_ready": (lambda m: m["readiness"].update(status="NOT_READY"), True),
    "authorization_claim": (lambda m: m.update(authorization="AUTHORIZED"), True),
    "alert_recipe_changed": (
        lambda m: m.update(notification_identity_recipe="x/y"),
        True,
    ),
}


@pytest.mark.parametrize("name", sorted(PLANE_TAMPER))
def test_plane_manifest_tampering_rejected(plane, accepted, tmp_path, name):
    mutate, refp = PLANE_TAMPER[name]
    path = _mutated_plane(plane, tmp_path, mutate, refp)
    with pytest.raises(ar.ArtifactError):
        oa.build_acceptance_record(
            path, accepted[0], expected_output_fingerprint=plane[1], run_id=RUN_ID
        )


# --- Phase 6: acceptance record tamper matrix ---------------------------------------------------


def _rewrite(path: Path, record: dict, keep_fingerprint: bool) -> None:
    if not keep_fingerprint:
        record["manifest_fingerprint"] = compute_output_manifest_fingerprint(record)
    path.write_text(json.dumps(record), encoding="utf-8")


RECORD_TAMPER = {
    "artifact_sha_mutation": lambda r: r.update(
        accepted_score_artifact_sha256="0" * 64
    ),
    "accepted_result_fingerprint": lambda r: r.update(
        accepted_run_artifact_fingerprint="0" * 64
    ),
    "notification_identity_mismatch": lambda r: r.update(
        notification_identity="0" * 64
    ),
    "inputs_fingerprint_mismatch": lambda r: r.update(inputs_fingerprint="0" * 64),
    "plane_fingerprint_mismatch": lambda r: r.update(
        output_plane_manifest_fingerprint="0" * 64
    ),
    "output_sha_mismatch": lambda r: r.update(output_code_git_head="e" * 40),
    "schema_version": lambda r: r.update(schema_version=2),
    "record_version": lambda r: r.update(acceptance_record_version="v0"),
    "data_origin_relabel": lambda r: r.update(data_origin="OPERATIONAL"),
    "authorization_claim": lambda r: r.update(authorization="AUTHORIZED"),
}


@pytest.mark.parametrize("attacker_refingerprints", [False, True])
@pytest.mark.parametrize("name", sorted(RECORD_TAMPER))
def test_record_tampering_rejected(plane, record, name, attacker_refingerprints):
    path, rec = record
    tampered = copy.deepcopy(rec)
    RECORD_TAMPER[name](tampered)
    _rewrite(path, tampered, keep_fingerprint=not attacker_refingerprints)
    assert oa.verify_acceptance_record(
        path, output_manifest_path=plane[0], expected_output_fingerprint=plane[1]
    )


def test_path_substitution_to_another_artifact_rejected(plane, record, tmp_path):
    path, rec = record
    other, _ = _synthetic_accepted_run(
        tmp_path / "other", horizon_hours=6, age_hours=2.0
    )  # different accepted run
    tampered = dict(rec, accepted_score_artifact_path=str(other))
    _rewrite(path, tampered, keep_fingerprint=False)
    assert verify_output_plane_manifest(path)["status"] == "FAIL"  # artifact SHA bound
    assert oa.verify_acceptance_record(
        path, output_manifest_path=plane[0], expected_output_fingerprint=plane[1]
    )


def test_artifact_modified_after_record_rejected(plane, accepted, record):
    run_path, _ = accepted
    doc = json.loads(run_path.read_text(encoding="utf-8"))
    doc["capture"]["captured_at"] = "2000-01-01T00:00:00+00:00"
    run_path.write_text(json.dumps(doc), encoding="utf-8")
    assert verify_output_plane_manifest(record[0])["status"] == "FAIL"


def test_replay_live_mismatch_rejected_with_anchor(plane, accepted, record, tmp_path):
    """A consistently edited, re-fingerprinted artifact is another run: the anchor rejects it."""
    run_path, doc = accepted
    edited = copy.deepcopy(doc)
    cell = edited["stable"]["output"]["cells"][30]
    cell["score"] = cell["score"] - 0.0001
    edited["artifact_fingerprint"] = ar.fingerprint(edited["stable"])
    edited["identities"]["artifact_fingerprint"] = edited["artifact_fingerprint"]
    alt = tmp_path / "edited.json"
    alt.write_text(json.dumps(edited), encoding="utf-8")
    with pytest.raises(ar.ArtifactError):
        oa.build_acceptance_record(
            plane[0],
            alt,
            expected_output_fingerprint=plane[1],
            run_id=RUN_ID,
            expected_artifact_fingerprint=doc["artifact_fingerprint"],
        )


# --- the persistent real manifest is never mutated --------------------------------------------


@needs_real
def test_persistent_output_manifest_byte_identical(real_hash_before):
    assert _sha(REAL_OUTPUT_MANIFEST) == real_hash_before

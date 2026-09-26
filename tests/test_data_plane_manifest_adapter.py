"""Focused tests for the Data Plane Manifest verifier — authoritative nested schema v1.

Covers:
- Fingerprint recipe (producer contract: SHA-256 of identity block)
- Real manifest acceptance (D:\\portafolio y seminario\\SAPI-71-evidence\\...)
- PREPARED semantics (not PASS, not FAIL, not writer-authorized)
- Authorization semantics (fail-closed)
- Tamper matrix (10 mutation categories must all FAIL)
- Schema version gate
- Single shared parser path (all consumers use verify_data_plane_manifest)
- NOT_AVAILABLE and missing-identity guard

NO network, NO real data modification, NO n8n interaction.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from src.ops.attempt2_operator.data_plane_manifest import (
    DataPlaneManifestView,
    compute_data_manifest_fingerprint,
    verify_data_plane_manifest,
)

# ---------------------------------------------------------------------------
# Canonical fixture builder (authoritative nested schema v1)
# ---------------------------------------------------------------------------

REAL_MANIFEST_PATH = Path(
    r"D:\portafolio y seminario\SAPI-71-evidence"
    r"\data-plane-rc1-2026-09-25\DATA_PLANE_MANIFEST.json"
)
REAL_FINGERPRINT = "5a6484fc4b047751fa6cec8e29a377c0ed96a19e1873ec25539745bca32a1ae0"
REAL_CODE_SHA = "cd9c01408059961fb30e4b6321429a018e4a0df5"


def _make_identity(
    *,
    readiness: str = "READY",
    firms_sha: str = "a" * 40,
    dmc_sha: str = "b" * 40,
    model_sha: str = "c" * 64,
    topo_sha: str = "d" * 64,
    baseline_sha: str = "e" * 64,
    code_sha: str = "f" * 40,
    authorizations: dict | None = None,
    kind: str = "DATA_PLANE_MANIFEST",
    schema_version: int = 1,
) -> dict:
    if authorizations is None:
        authorizations = {"attempt2": False, "writers": False, "telegram": False, "schedule": False}
    return {
        "schema_version": schema_version,
        "kind": kind,
        "data_readiness_status": readiness,
        "data_ready_for_scoring": "NOT_EVALUATED",
        "independent_approval": "PENDING",
        "authorizations": authorizations,
        "code_identity": {"sha": code_sha, "tree": "0" * 40, "clean": True, "status": "PASS"},
        "components": {
            "firms": {"sha": firms_sha, "files": [], "status": "PASS"},
            "dmc": {"sha": dmc_sha, "files": [], "status": "PASS"},
            "scoring_inputs": {"sha": "9" * 40, "files": [], "status": "PASS"},
        },
        "model": {"sha256": model_sha, "status": "PASS"},
        "topography": {
            "table_sha256": topo_sha,
            "grid_sha256": "f" * 64,
            "status": "PASS",
            "cells": 50,
        },
        "baseline": {"sha256": baseline_sha, "status": "PASS"},
        "expected_current": {"firms": "ABSENT", "dmc": "ABSENT"},
        "current_state": {"firms": "ABSENT", "dmc": "ABSENT"},
    }


def _make_manifest(identity: dict, fingerprint: str | None = None) -> dict:
    fp = fingerprint if fingerprint is not None else compute_data_manifest_fingerprint(identity)
    return {
        "schema_version": 1,
        "created_at": "2026-09-25T19:00:00+00:00",
        "identity": identity,
        "fingerprint": fp,
        "operational_roots": {"workspace": "/fake", "code": "/fake"},
        "observation": {"start": "2026-09-25T19:00:00+00:00", "end": "2026-09-25T19:00:01+00:00"},
    }


def _write(tmp_path: Path, manifest: dict) -> Path:
    p = tmp_path / "DATA_PLANE_MANIFEST.json"
    p.write_text(json.dumps(manifest), encoding="utf-8")
    return p


# ===========================================================================
# 1. FINGERPRINT RECIPE
# ===========================================================================

class TestFingerprintRecipe:
    """Fingerprint = SHA-256(canonical_json(identity_block)).

    Must match the Astra producer contract exactly.
    """

    def test_fingerprint_matches_producer_recipe(self):
        """compute_data_manifest_fingerprint(identity) == SHA-256(sorted compact JSON of identity)."""
        identity = _make_identity()
        expected = hashlib.sha256(
            json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        assert compute_data_manifest_fingerprint(identity) == expected

    def test_fingerprint_is_deterministic(self):
        identity = _make_identity()
        fp1 = compute_data_manifest_fingerprint(identity)
        fp2 = compute_data_manifest_fingerprint(identity)
        assert fp1 == fp2

    def test_fingerprint_changes_on_identity_mutation(self):
        identity = _make_identity()
        fp_before = compute_data_manifest_fingerprint(identity)
        identity["components"]["firms"]["sha"] = "z" * 40
        fp_after = compute_data_manifest_fingerprint(identity)
        assert fp_before != fp_after

    def test_fingerprint_does_not_cover_envelope(self):
        """Envelope fields (fingerprint, created_at, etc.) are NOT part of the hash input."""
        identity = _make_identity()
        fp = compute_data_manifest_fingerprint(identity)
        # The fingerprint field itself is in the envelope, not the identity block
        manifest = _make_manifest(identity, fingerprint=fp)
        # Changing envelope fields (other than identity) should not affect the fingerprint
        manifest["created_at"] = "2099-01-01T00:00:00+00:00"
        # Recomputing from the same identity block gives the same result
        assert compute_data_manifest_fingerprint(manifest["identity"]) == fp


# ===========================================================================
# 2. REAL MANIFEST ACCEPTANCE
# ===========================================================================

class TestRealManifestAcceptance:
    """The authoritative RC1 Data Plane artifact must be accepted."""

    @pytest.mark.skipif(
        not REAL_MANIFEST_PATH.is_file(),
        reason="Real manifest not available in this environment",
    )
    def test_real_manifest_accepted(self):
        result = verify_data_plane_manifest(REAL_MANIFEST_PATH, expected_code_sha=REAL_CODE_SHA)
        assert result["status"] == "PREPARED", (
            f"Expected PREPARED, got {result['status']}. Findings: {result['findings']}"
        )
        assert result["ready"] is False  # PREPARED != READY (correct)
        assert result["prepared"] is True  # But schema is accepted

    @pytest.mark.skipif(
        not REAL_MANIFEST_PATH.is_file(),
        reason="Real manifest not available in this environment",
    )
    def test_real_manifest_fingerprint_matches(self):
        result = verify_data_plane_manifest(REAL_MANIFEST_PATH)
        assert result["fingerprint_match"] is True
        assert result["manifest_fingerprint"] == REAL_FINGERPRINT

    @pytest.mark.skipif(
        not REAL_MANIFEST_PATH.is_file(),
        reason="Real manifest not available in this environment",
    )
    def test_real_manifest_code_sha_matches(self):
        result = verify_data_plane_manifest(REAL_MANIFEST_PATH)
        assert result["code_sha"] == REAL_CODE_SHA

    @pytest.mark.skipif(
        not REAL_MANIFEST_PATH.is_file(),
        reason="Real manifest not available in this environment",
    )
    def test_real_manifest_no_writer_authorization(self):
        result = verify_data_plane_manifest(REAL_MANIFEST_PATH)
        assert result["writers_authorized"] is False
        assert result["attempt2_authorized"] is False
        assert result["telegram_authorized"] is False
        assert result["schedule_authorized"] is False

    @pytest.mark.skipif(
        not REAL_MANIFEST_PATH.is_file(),
        reason="Real manifest not available in this environment",
    )
    def test_real_manifest_not_modified(self):
        """Verify we haven't accidentally mutated the real artifact."""
        raw = REAL_MANIFEST_PATH.read_bytes()
        actual_fp = hashlib.sha256(
            json.dumps(
                json.loads(raw.decode("utf-8"))["identity"],
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        assert actual_fp == REAL_FINGERPRINT


# ===========================================================================
# 3. PREPARED SEMANTICS
# ===========================================================================

class TestPreparedSemantics:
    """PREPARED = valid schema, data staged. NOT a writer authorization.

    PREPARED must NOT:
    - map to overall status PASS
    - imply writers_authorized=True
    - imply attempt2_authorized=True

    PREPARED MUST:
    - produce overall status == "PREPARED"
    - set ready=False
    - set prepared=True
    - be distinguishable from INCOMPLETE and FAIL
    """

    def test_prepared_status_is_prepared(self, tmp_path: Path):
        identity = _make_identity(readiness="PREPARED")
        path = _write(tmp_path, _make_manifest(identity))
        result = verify_data_plane_manifest(path)
        assert result["status"] == "PREPARED"

    def test_prepared_is_not_pass(self, tmp_path: Path):
        identity = _make_identity(readiness="PREPARED")
        path = _write(tmp_path, _make_manifest(identity))
        result = verify_data_plane_manifest(path)
        assert result["status"] != "PASS"
        assert result["ready"] is False

    def test_prepared_sets_prepared_flag(self, tmp_path: Path):
        identity = _make_identity(readiness="PREPARED")
        path = _write(tmp_path, _make_manifest(identity))
        result = verify_data_plane_manifest(path)
        assert result["prepared"] is True

    def test_prepared_is_not_fail(self, tmp_path: Path):
        identity = _make_identity(readiness="PREPARED")
        path = _write(tmp_path, _make_manifest(identity))
        result = verify_data_plane_manifest(path)
        assert result["status"] != "FAIL"

    def test_prepared_no_writer_authorization(self, tmp_path: Path):
        identity = _make_identity(readiness="PREPARED")
        path = _write(tmp_path, _make_manifest(identity))
        result = verify_data_plane_manifest(path)
        assert result["writers_authorized"] is False
        assert result["attempt2_authorized"] is False

    def test_ready_produces_pass(self, tmp_path: Path):
        identity = _make_identity(readiness="READY")
        path = _write(tmp_path, _make_manifest(identity))
        result = verify_data_plane_manifest(path)
        assert result["status"] == "PASS"
        assert result["ready"] is True
        assert result["prepared"] is True


# ===========================================================================
# 4. AUTHORIZATION SEMANTICS
# ===========================================================================

class TestAuthorizationSemantics:
    """Authorization flags must be explicitly present and explicitly false.

    Missing flag → FAIL (fail-closed).
    True flag → field is readable but does NOT mean operator may proceed.
    """

    def test_all_false_accepted(self, tmp_path: Path):
        identity = _make_identity()
        path = _write(tmp_path, _make_manifest(identity))
        result = verify_data_plane_manifest(path)
        assert result["writers_authorized"] is False
        assert result["attempt2_authorized"] is False
        assert result["telegram_authorized"] is False
        assert result["schedule_authorized"] is False

    def test_missing_auth_flag_fails(self, tmp_path: Path):
        identity = _make_identity(authorizations={"attempt2": False, "writers": False})
        # Missing "telegram" and "schedule"
        path = _write(tmp_path, _make_manifest(identity))
        result = verify_data_plane_manifest(path)
        assert result["status"] == "FAIL"
        codes = [f["code"] for f in result["findings"]]
        assert "MISSING_AUTH_FLAG" in codes

    def test_missing_authorizations_block_fails(self, tmp_path: Path):
        identity = _make_identity()
        identity.pop("authorizations")
        path = _write(tmp_path, _make_manifest(identity))
        result = verify_data_plane_manifest(path)
        # authorizations field is missing → should FAIL (missing required field)
        assert result["status"] == "FAIL"

    def test_none_authorization_fails(self, tmp_path: Path):
        identity = _make_identity()
        identity["authorizations"] = None
        path = _write(tmp_path, _make_manifest(identity))
        result = verify_data_plane_manifest(path)
        assert result["status"] == "FAIL"


# ===========================================================================
# 5. TAMPER MATRIX
# ===========================================================================

class TestTamperMatrix:
    """Every mutation of a fingerprinted field must produce FAIL with DATA_MANIFEST_TAMPERED.

    Tests that each individually mutated component produces tamper rejection.
    """

    def _tamper_test(self, tmp_path: Path, mutated_identity: dict) -> None:
        """Write manifest with correct fingerprint for original, then mutate identity."""
        original_identity = _make_identity()
        fp = compute_data_manifest_fingerprint(original_identity)
        manifest = _make_manifest(mutated_identity, fingerprint=fp)  # fp is for original, not mutated
        path = _write(tmp_path, manifest)
        result = verify_data_plane_manifest(path)
        assert result["status"] == "FAIL", (
            f"Expected FAIL for tampered manifest, got {result['status']}. Findings: {result['findings']}"
        )
        codes = [f["code"] for f in result["findings"]]
        assert "DATA_MANIFEST_TAMPERED" in codes, (
            f"Expected DATA_MANIFEST_TAMPERED in findings. Got: {codes}"
        )

    def test_tamper_firms_sha(self, tmp_path: Path):
        identity = _make_identity()
        identity["components"]["firms"]["sha"] = "z" * 40
        self._tamper_test(tmp_path, identity)

    def test_tamper_dmc_sha(self, tmp_path: Path):
        identity = _make_identity()
        identity["components"]["dmc"]["sha"] = "z" * 40
        self._tamper_test(tmp_path, identity)

    def test_tamper_model_sha(self, tmp_path: Path):
        identity = _make_identity()
        identity["model"]["sha256"] = "z" * 64
        self._tamper_test(tmp_path, identity)

    def test_tamper_topography_identity(self, tmp_path: Path):
        identity = _make_identity()
        identity["topography"]["table_sha256"] = "z" * 64
        self._tamper_test(tmp_path, identity)

    def test_tamper_baseline_identity(self, tmp_path: Path):
        identity = _make_identity()
        identity["baseline"]["sha256"] = "z" * 64
        self._tamper_test(tmp_path, identity)

    def test_tamper_readiness_status(self, tmp_path: Path):
        identity = _make_identity(readiness="READY")
        fp = compute_data_manifest_fingerprint(identity)
        identity["data_readiness_status"] = "PREPARED"  # mutate after fingerprinting
        manifest = _make_manifest(identity, fingerprint=fp)
        path = _write(tmp_path, manifest)
        result = verify_data_plane_manifest(path)
        assert result["status"] == "FAIL"
        codes = [f["code"] for f in result["findings"]]
        assert "DATA_MANIFEST_TAMPERED" in codes

    def test_tamper_authorization_flag(self, tmp_path: Path):
        identity = _make_identity()
        fp = compute_data_manifest_fingerprint(identity)
        identity["authorizations"]["attempt2"] = True  # mutate after fingerprinting
        manifest = _make_manifest(identity, fingerprint=fp)
        path = _write(tmp_path, manifest)
        result = verify_data_plane_manifest(path)
        assert result["status"] == "FAIL"
        codes = [f["code"] for f in result["findings"]]
        assert "DATA_MANIFEST_TAMPERED" in codes

    def test_tamper_fingerprint_literal(self, tmp_path: Path):
        identity = _make_identity()
        manifest = _make_manifest(identity, fingerprint="TAMPERED_HASH_VALUE")
        path = _write(tmp_path, manifest)
        result = verify_data_plane_manifest(path)
        assert result["status"] == "FAIL"
        codes = [f["code"] for f in result["findings"]]
        assert "DATA_MANIFEST_TAMPERED" in codes

    def test_tamper_remove_identity_field(self, tmp_path: Path):
        identity = _make_identity()
        fp = compute_data_manifest_fingerprint(identity)
        identity.pop("current_state")  # remove a required field after fingerprinting
        manifest = _make_manifest(identity, fingerprint=fp)
        path = _write(tmp_path, manifest)
        result = verify_data_plane_manifest(path)
        assert result["status"] == "FAIL"

    def test_tamper_code_sha(self, tmp_path: Path):
        identity = _make_identity()
        fp = compute_data_manifest_fingerprint(identity)
        identity["code_identity"]["sha"] = "z" * 40  # mutate after fingerprinting
        manifest = _make_manifest(identity, fingerprint=fp)
        path = _write(tmp_path, manifest)
        result = verify_data_plane_manifest(path)
        assert result["status"] == "FAIL"
        codes = [f["code"] for f in result["findings"]]
        assert "DATA_MANIFEST_TAMPERED" in codes

    def test_wrong_schema_version(self, tmp_path: Path):
        identity = _make_identity(schema_version=99)
        manifest = _make_manifest(identity)
        manifest["schema_version"] = 99  # envelope version mismatch
        path = _write(tmp_path, manifest)
        result = verify_data_plane_manifest(path)
        assert result["status"] == "FAIL"
        codes = [f["code"] for f in result["findings"]]
        assert "UNSUPPORTED_DATA_MANIFEST_SCHEMA" in codes


# ===========================================================================
# 6. UNKNOWN/MALFORMED FIELDS
# ===========================================================================

class TestMalformedManifests:
    """Unknown structure or malformed mandatory fields must never PASS."""

    def test_missing_identity_block_fails(self, tmp_path: Path):
        manifest = {
            "schema_version": 1,
            "created_at": "2026-09-25T19:00:00+00:00",
            "fingerprint": "abc",
        }
        path = _write(tmp_path, manifest)
        result = verify_data_plane_manifest(path)
        assert result["status"] == "FAIL"
        codes = [f["code"] for f in result["findings"]]
        assert "MISSING_IDENTITY_BLOCK" in codes

    def test_wrong_kind_fails(self, tmp_path: Path):
        identity = _make_identity(kind="WRONG_KIND")
        path = _write(tmp_path, _make_manifest(identity))
        result = verify_data_plane_manifest(path)
        assert result["status"] == "FAIL"
        codes = [f["code"] for f in result["findings"]]
        assert "WRONG_KIND" in codes

    def test_corrupt_json_fails(self, tmp_path: Path):
        path = tmp_path / "DATA_PLANE_MANIFEST.json"
        path.write_text("{not: valid json}", encoding="utf-8")
        result = verify_data_plane_manifest(path)
        assert result["status"] == "FAIL"
        codes = [f["code"] for f in result["findings"]]
        assert "DATA_MANIFEST_CORRUPT" in codes

    def test_missing_file_not_available(self, tmp_path: Path):
        result = verify_data_plane_manifest(tmp_path / "NONEXISTENT.json")
        assert result["status"] == "NOT_AVAILABLE"
        assert result["ready"] is False
        assert result["prepared"] is False

    def test_none_path_not_available(self):
        result = verify_data_plane_manifest(None)
        assert result["status"] == "NOT_AVAILABLE"
        assert result["ready"] is False

    def test_empty_identity_block_fails(self, tmp_path: Path):
        manifest = {
            "schema_version": 1,
            "created_at": "2026-09-25T19:00:00+00:00",
            "identity": {},
            "fingerprint": compute_data_manifest_fingerprint({}),
            "operational_roots": {"workspace": "/fake", "code": "/fake"},
        }
        path = _write(tmp_path, manifest)
        result = verify_data_plane_manifest(path)
        assert result["status"] == "FAIL"

    def test_identity_not_dict_fails(self, tmp_path: Path):
        manifest = {
            "schema_version": 1,
            "created_at": "2026-09-25T19:00:00+00:00",
            "identity": "not a dict",
            "fingerprint": "abc",
        }
        path = _write(tmp_path, manifest)
        result = verify_data_plane_manifest(path)
        assert result["status"] == "FAIL"
        codes = [f["code"] for f in result["findings"]]
        assert "MISSING_IDENTITY_BLOCK" in codes


# ===========================================================================
# 7. SINGLE PARSER PATH — DataPlaneManifestView
# ===========================================================================

class TestSingleParserPath:
    """DataPlaneManifestView extracts the same fields from raw JSON as verify_data_plane_manifest.

    All consumers must use the same verifier — no side-path parsing.
    """

    def test_view_extracts_correct_firms_sha(self):
        identity = _make_identity(firms_sha="1" * 40)
        raw = _make_manifest(identity)
        view = DataPlaneManifestView(raw)
        assert view.firms_component_sha == "1" * 40

    def test_view_extracts_correct_dmc_sha(self):
        identity = _make_identity(dmc_sha="2" * 40)
        raw = _make_manifest(identity)
        view = DataPlaneManifestView(raw)
        assert view.dmc_component_sha == "2" * 40

    def test_view_extracts_model_sha(self):
        identity = _make_identity(model_sha="3" * 64)
        raw = _make_manifest(identity)
        view = DataPlaneManifestView(raw)
        assert view.model_sha == "3" * 64

    def test_view_extracts_topography_identity(self):
        identity = _make_identity(topo_sha="4" * 64)
        raw = _make_manifest(identity)
        view = DataPlaneManifestView(raw)
        assert view.topography_identity == "4" * 64

    def test_view_extracts_baseline_identity(self):
        identity = _make_identity(baseline_sha="5" * 64)
        raw = _make_manifest(identity)
        view = DataPlaneManifestView(raw)
        assert view.baseline_identity == "5" * 64

    def test_view_extracts_expected_current_state(self):
        identity = _make_identity()
        raw = _make_manifest(identity)
        view = DataPlaneManifestView(raw)
        assert view.expected_current_state == {"firms": "ABSENT", "dmc": "ABSENT"}

    def test_view_authorization_flags_false_by_default(self):
        identity = _make_identity()
        raw = _make_manifest(identity)
        view = DataPlaneManifestView(raw)
        assert view.writers_authorized is False
        assert view.attempt2_authorized is False
        assert view.telegram_authorized is False
        assert view.schedule_authorized is False

    def test_view_readiness_status(self):
        identity = _make_identity(readiness="PREPARED")
        raw = _make_manifest(identity)
        view = DataPlaneManifestView(raw)
        assert view.data_readiness_status == "PREPARED"

    def test_verifier_result_matches_view(self, tmp_path: Path):
        """verify_data_plane_manifest result fields must match DataPlaneManifestView extraction."""
        identity = _make_identity(
            firms_sha="a" * 40,
            dmc_sha="b" * 40,
            model_sha="c" * 64,
            topo_sha="d" * 64,
            baseline_sha="e" * 64,
        )
        path = _write(tmp_path, _make_manifest(identity))
        result = verify_data_plane_manifest(path)
        assert result["firms_component_sha"] == "a" * 40
        assert result["dmc_component_sha"] == "b" * 40
        assert result["model_sha"] == "c" * 64
        assert result["topography_identity"] == "d" * 64
        assert result["baseline_identity"] == "e" * 64

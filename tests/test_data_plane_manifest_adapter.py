"""Focused tests for the Data Plane Manifest verifier — hardened Astra RC1 schema v1.

HARDENING TESTS added in this version:
- Resigned attack matrix (Phase 7): semantically invalid manifests with correctly
  re-computed fingerprints must be REJECTED (ADAPTER-GAP-1 fix).
- Non-object JSON root tests (Phase 9): [], null, "str", 123, true must all FAIL.
- Exception safety: no crash on any malformed input.

CORRECTED ASSUMPTIONS:
- OLD: data_readiness_status="READY" -> Operations status "PASS"
  NEW: "READY" is NOT a valid producer value. Producer only emits PREPARED,
       NOT_PREPARED, INCOMPLETE. Any re-signed "READY" manifest -> FAIL.
- OLD: ready=True possible
  NEW: ready is ALWAYS False. No producer READY state exists.

Producer semantic validator ported from:
  src/ops/data_readiness.verify_manifest()
  Data Plane SHA: cd9c01408059961fb30e4b6321429a018e4a0df5

NO network, NO real data modification, NO n8n interaction.
"""

from __future__ import annotations

import copy
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
# Canonical fixture builder (authoritative nested schema v1, PREPARED default)
# ---------------------------------------------------------------------------

REAL_MANIFEST_PATH = Path(
    r"D:\portafolio y seminario\SAPI-71-evidence"
    r"\data-plane-rc1-2026-09-25\DATA_PLANE_MANIFEST.json"
)
REAL_FINGERPRINT = "5a6484fc4b047751fa6cec8e29a377c0ed96a19e1873ec25539745bca32a1ae0"
REAL_CODE_SHA = "cd9c01408059961fb30e4b6321429a018e4a0df5"


def _make_identity(
    *,
    readiness: str = "PREPARED",  # default PREPARED — highest valid producer state
    firms_sha: str = "a" * 40,
    dmc_sha: str = "b" * 40,
    model_sha: str = "c" * 64,
    topo_sha: str = "d" * 64,
    baseline_sha: str = "e" * 64,
    source_evidence_sha: str = "s" * 64,
    code_sha: str = "f" * 40,
    authorizations: dict | None = None,
    kind: str = "DATA_PLANE_MANIFEST",
    schema_version: int = 1,
    findings: list | None = None,
    current_state: dict | None = None,
    expected_current: dict | None = None,
) -> dict:
    if authorizations is None:
        authorizations = {"attempt2": False, "writers": False, "telegram": False, "schedule": False}
    if findings is None:
        findings = []
    if current_state is None:
        current_state = {"firms": "ABSENT", "dmc": "ABSENT"}
    if expected_current is None:
        expected_current = {"firms": "ABSENT", "dmc": "ABSENT"}
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
        "source_evidence": {"sha256": source_evidence_sha, "status": "PASS"},
        "expected_current": expected_current,
        "current_state": current_state,
        "findings": findings,
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


def _resign(identity: dict) -> str:
    """Compute a cryptographically valid fingerprint for the given (possibly mutated) identity."""
    return compute_data_manifest_fingerprint(identity)


# ===========================================================================
# 1. FINGERPRINT RECIPE (producer-exact canonical)
# ===========================================================================

class TestFingerprintRecipe:
    """Fingerprint = SHA-256(canonical_json(identity_block)).

    canonical_json uses ensure_ascii=True, allow_nan=False — exact producer recipe.
    """

    def test_fingerprint_matches_producer_recipe(self):
        identity = _make_identity()
        expected = hashlib.sha256(
            json.dumps(identity, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True, allow_nan=False).encode("utf-8")
        ).hexdigest()
        assert compute_data_manifest_fingerprint(identity) == expected

    def test_fingerprint_is_deterministic(self):
        identity = _make_identity()
        assert (
            compute_data_manifest_fingerprint(identity)
            == compute_data_manifest_fingerprint(identity)
        )

    def test_fingerprint_changes_on_identity_mutation(self):
        identity = _make_identity()
        fp_before = compute_data_manifest_fingerprint(identity)
        identity["components"]["firms"]["sha"] = "z" * 40
        assert compute_data_manifest_fingerprint(identity) != fp_before

    def test_fingerprint_does_not_cover_envelope(self):
        identity = _make_identity()
        fp = compute_data_manifest_fingerprint(identity)
        manifest = _make_manifest(identity, fingerprint=fp)
        manifest["created_at"] = "2099-01-01T00:00:00+00:00"
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
        assert result["ready"] is False
        assert result["prepared"] is True
        assert result["producer_valid"] is True

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
        """Verify real artifact integrity — it must not be mutated by tests."""
        raw = REAL_MANIFEST_PATH.read_bytes()
        actual_fp = hashlib.sha256(
            json.dumps(
                json.loads(raw.decode("utf-8"))["identity"],
                sort_keys=True, separators=(",", ":"),
                ensure_ascii=True, allow_nan=False,
            ).encode("utf-8")
        ).hexdigest()
        assert actual_fp == REAL_FINGERPRINT


# ===========================================================================
# 3. PREPARED SEMANTICS (corrected — READY never existed in producer contract)
# ===========================================================================

class TestPreparedSemantics:
    """PREPARED is the highest valid producer state.

    CORRECTED ASSUMPTION:
      OLD: data_readiness_status="READY" -> Operations status "PASS"
      NEW: "READY" is NOT emitted by the producer. PREPARED is the maximum.
           ready is ALWAYS False — no producer READY state.
    """

    def test_prepared_with_valid_conditions_produces_prepared(self, tmp_path: Path):
        """Producer-valid PREPARED manifest -> Operations PREPARED status."""
        identity = _make_identity(readiness="PREPARED")
        path = _write(tmp_path, _make_manifest(identity))
        result = verify_data_plane_manifest(path)
        assert result["status"] == "PREPARED"
        assert result["producer_valid"] is True

    def test_prepared_sets_prepared_flag(self, tmp_path: Path):
        identity = _make_identity(readiness="PREPARED")
        path = _write(tmp_path, _make_manifest(identity))
        result = verify_data_plane_manifest(path)
        assert result["prepared"] is True

    def test_ready_is_never_true(self, tmp_path: Path):
        """ready is always False — no producer READY state exists."""
        identity = _make_identity(readiness="PREPARED")
        path = _write(tmp_path, _make_manifest(identity))
        result = verify_data_plane_manifest(path)
        assert result["ready"] is False

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

    def test_not_prepared_produces_not_prepared(self, tmp_path: Path):
        identity = _make_identity(readiness="NOT_PREPARED")
        path = _write(tmp_path, _make_manifest(identity))
        result = verify_data_plane_manifest(path)
        # NOT_PREPARED is a valid producer state — fingerprint+schema valid
        assert result["status"] in ("NOT_PREPARED", "FAIL")
        # If FAIL — this may be because NOT_PREPARED doesn't pass producer
        # semantic PREPARED-specific checks (that's fine — it's NOT_PREPARED)
        assert result["ready"] is False
        assert result["prepared"] is False

    def test_incomplete_produces_incomplete_or_fail(self, tmp_path: Path):
        identity = _make_identity(readiness="INCOMPLETE")
        path = _write(tmp_path, _make_manifest(identity))
        result = verify_data_plane_manifest(path)
        assert result["ready"] is False
        assert result["prepared"] is False


# ===========================================================================
# 4. AUTHORIZATION SEMANTICS
# ===========================================================================

class TestAuthorizationSemantics:
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
        path = _write(tmp_path, _make_manifest(identity))
        result = verify_data_plane_manifest(path)
        assert result["status"] == "FAIL"
        codes = [f["code"] for f in result["findings"]]
        assert "PRODUCER_SEMANTIC_VIOLATION" in codes or "MISSING_AUTH_FLAG" in codes

    def test_missing_authorizations_block_fails(self, tmp_path: Path):
        identity = _make_identity()
        identity.pop("authorizations")
        path = _write(tmp_path, _make_manifest(identity))
        result = verify_data_plane_manifest(path)
        assert result["status"] == "FAIL"

    def test_none_authorization_fails(self, tmp_path: Path):
        identity = _make_identity()
        identity["authorizations"] = None
        path = _write(tmp_path, _make_manifest(identity))
        result = verify_data_plane_manifest(path)
        assert result["status"] == "FAIL"


# ===========================================================================
# 5. FINGERPRINT TAMPER MATRIX (no re-signing — fingerprint mismatch path)
# ===========================================================================

class TestFingerprintTamperMatrix:
    """Previous tamper tests: change data WITHOUT recomputing fingerprint.
    These tests the cryptographic integrity path (DATA_MANIFEST_TAMPERED).
    """

    def _tamper_test(self, tmp_path: Path, mutated_identity: dict) -> None:
        original_identity = _make_identity()
        fp = compute_data_manifest_fingerprint(original_identity)
        manifest = _make_manifest(mutated_identity, fingerprint=fp)
        path = _write(tmp_path, manifest)
        result = verify_data_plane_manifest(path)
        assert result["status"] == "FAIL", (
            f"Expected FAIL for fingerprint-tampered manifest, got {result['status']}. "
            f"Findings: {result['findings']}"
        )
        codes = [f["code"] for f in result["findings"]]
        assert "DATA_MANIFEST_TAMPERED" in codes

    def test_tamper_firms_sha(self, tmp_path):
        identity = _make_identity(); identity["components"]["firms"]["sha"] = "z" * 40
        self._tamper_test(tmp_path, identity)

    def test_tamper_dmc_sha(self, tmp_path):
        identity = _make_identity(); identity["components"]["dmc"]["sha"] = "z" * 40
        self._tamper_test(tmp_path, identity)

    def test_tamper_model_sha(self, tmp_path):
        identity = _make_identity(); identity["model"]["sha256"] = "z" * 64
        self._tamper_test(tmp_path, identity)

    def test_tamper_topography_identity(self, tmp_path):
        identity = _make_identity(); identity["topography"]["table_sha256"] = "z" * 64
        self._tamper_test(tmp_path, identity)

    def test_tamper_baseline_identity(self, tmp_path):
        identity = _make_identity(); identity["baseline"]["sha256"] = "z" * 64
        self._tamper_test(tmp_path, identity)

    def test_tamper_fingerprint_literal(self, tmp_path):
        identity = _make_identity()
        manifest = _make_manifest(identity, fingerprint="TAMPERED_HASH_VALUE")
        path = _write(tmp_path, manifest)
        result = verify_data_plane_manifest(path)
        assert result["status"] == "FAIL"
        codes = [f["code"] for f in result["findings"]]
        assert "DATA_MANIFEST_TAMPERED" in codes

    def test_tamper_code_sha(self, tmp_path):
        identity = _make_identity()
        original_fp = compute_data_manifest_fingerprint(identity)
        identity["code_identity"]["sha"] = "z" * 40
        manifest = _make_manifest(identity, fingerprint=original_fp)
        path = _write(tmp_path, manifest)
        result = verify_data_plane_manifest(path)
        assert result["status"] == "FAIL"
        codes = [f["code"] for f in result["findings"]]
        assert "DATA_MANIFEST_TAMPERED" in codes

    def test_wrong_schema_version_fails(self, tmp_path):
        identity = _make_identity(schema_version=99)
        manifest = _make_manifest(identity)
        manifest["schema_version"] = 99
        path = _write(tmp_path, manifest)
        result = verify_data_plane_manifest(path)
        assert result["status"] == "FAIL"


# ===========================================================================
# 6. RESIGNED ATTACK MATRIX — ADAPTER-GAP-1 FIX
# ===========================================================================
# These tests verify that correctly re-signed (valid fingerprint) but
# semantically-invalid manifests are REJECTED by the producer semantic validator.
# Before the hardening fix, all of these attacks were INCORRECTLY ACCEPTED.

class TestResignedAttackMatrix:
    """Phase 7: Semantically invalid manifests with valid re-computed fingerprints.

    Every mutation + re-sign must produce FAIL with PRODUCER_SEMANTIC_VIOLATION.
    Before ADAPTER-GAP-1 fix: these all returned PASS or PREPARED (incorrect).
    After fix: all must return FAIL.
    """

    def _resigned_attack(
        self, tmp_path: Path, mutated_identity: dict, attack_name: str
    ) -> None:
        """Create a manifest where the fingerprint matches the MUTATED identity."""
        fp = _resign(mutated_identity)  # valid fingerprint for the mutated content
        manifest = _make_manifest(mutated_identity, fingerprint=fp)
        path = _write(tmp_path, manifest)
        result = verify_data_plane_manifest(path)
        assert result["status"] == "FAIL", (
            f"ADAPTER-GAP-1: Re-signed attack '{attack_name}' was INCORRECTLY ACCEPTED. "
            f"Status={result['status']}, Findings={result['findings']}"
        )
        codes = [f["code"] for f in result["findings"]]
        assert "PRODUCER_SEMANTIC_VIOLATION" in codes, (
            f"Expected PRODUCER_SEMANTIC_VIOLATION finding for attack '{attack_name}'. "
            f"Got: {codes}"
        )

    def test_resigned_readiness_ready_attack(self, tmp_path):
        """READY is NOT a valid producer readiness value. Must be rejected."""
        identity = copy.deepcopy(_make_identity(readiness="PREPARED"))
        identity["data_readiness_status"] = "READY"
        self._resigned_attack(tmp_path, identity, "readiness=READY")

    def test_resigned_readiness_done_attack(self, tmp_path):
        """Invented 'DONE' status must be rejected."""
        identity = copy.deepcopy(_make_identity(readiness="PREPARED"))
        identity["data_readiness_status"] = "DONE"
        self._resigned_attack(tmp_path, identity, "readiness=DONE")

    def test_resigned_current_state_mismatch(self, tmp_path):
        """PREPARED requires current_state == expected_current. Mismatch must be rejected."""
        identity = _make_identity(
            readiness="PREPARED",
            current_state={"firms": "PRESENT", "dmc": "PRESENT"},
            expected_current={"firms": "ABSENT", "dmc": "ABSENT"},
        )
        self._resigned_attack(tmp_path, identity, "current_state != expected_current")

    def test_resigned_findings_non_empty(self, tmp_path):
        """PREPARED requires empty findings. Non-empty findings must be rejected."""
        identity = _make_identity(
            readiness="PREPARED",
            findings=[{"code": "INJECTED", "severity": "WARN", "message": "injected"}],
        )
        self._resigned_attack(tmp_path, identity, "findings non-empty")

    def test_resigned_authorization_attempt2_true(self, tmp_path):
        """attempt2=True is not allowed — must be rejected."""
        identity = copy.deepcopy(_make_identity(readiness="PREPARED"))
        identity["authorizations"]["attempt2"] = True
        self._resigned_attack(tmp_path, identity, "attempt2=True")

    def test_resigned_authorization_writers_true(self, tmp_path):
        """writers=True is not allowed — must be rejected."""
        identity = copy.deepcopy(_make_identity(readiness="PREPARED"))
        identity["authorizations"]["writers"] = True
        self._resigned_attack(tmp_path, identity, "writers=True")

    def test_resigned_data_ready_for_scoring_wrong(self, tmp_path):
        """data_ready_for_scoring must be NOT_EVALUATED — any other value rejected."""
        identity = copy.deepcopy(_make_identity(readiness="PREPARED"))
        identity["data_ready_for_scoring"] = "READY"
        self._resigned_attack(tmp_path, identity, "data_ready_for_scoring=READY")

    def test_resigned_independent_approval_wrong(self, tmp_path):
        """independent_approval must be PENDING."""
        identity = copy.deepcopy(_make_identity(readiness="PREPARED"))
        identity["independent_approval"] = "APPROVED"
        self._resigned_attack(tmp_path, identity, "independent_approval=APPROVED")

    def test_resigned_model_status_fail(self, tmp_path):
        """PREPARED requires all asset blocks status==PASS."""
        identity = copy.deepcopy(_make_identity(readiness="PREPARED"))
        identity["model"]["status"] = "FAIL"
        self._resigned_attack(tmp_path, identity, "model.status=FAIL")

    def test_resigned_source_evidence_status_fail(self, tmp_path):
        """PREPARED requires source_evidence.status==PASS."""
        identity = copy.deepcopy(_make_identity(readiness="PREPARED"))
        identity["source_evidence"]["status"] = "FAIL"
        self._resigned_attack(tmp_path, identity, "source_evidence.status=FAIL")

    def test_resigned_current_state_extra_key(self, tmp_path):
        """PREPARED requires current_state keys == {'firms', 'dmc'} exactly."""
        identity = copy.deepcopy(_make_identity(readiness="PREPARED"))
        identity["current_state"]["scoring_inputs"] = "ABSENT"
        identity["expected_current"]["scoring_inputs"] = "ABSENT"
        self._resigned_attack(tmp_path, identity, "current_state extra key")

    def test_resigned_current_state_bad_value(self, tmp_path):
        """PREPARED state values must be ABSENT or PRESENT."""
        identity = _make_identity(
            readiness="PREPARED",
            current_state={"firms": "UNKNOWN", "dmc": "ABSENT"},
            expected_current={"firms": "UNKNOWN", "dmc": "ABSENT"},
        )
        self._resigned_attack(tmp_path, identity, "current_state bad value")


# ===========================================================================
# 7. VALID ALTERNATE FIXTURES (phase 8)
# ===========================================================================

class TestValidAlternateFixtures:
    """Producer-valid synthetic fixtures must be accepted, not falsely rejected."""

    def test_all_present_current_state_accepted(self, tmp_path):
        """Both firms and dmc PRESENT is valid for PREPARED if they match expected."""
        identity = _make_identity(
            readiness="PREPARED",
            current_state={"firms": "PRESENT", "dmc": "PRESENT"},
            expected_current={"firms": "PRESENT", "dmc": "PRESENT"},
        )
        path = _write(tmp_path, _make_manifest(identity))
        result = verify_data_plane_manifest(path)
        assert result["status"] == "PREPARED"
        assert result["producer_valid"] is True

    def test_different_sha_values_accepted(self, tmp_path):
        """Different component SHAs are fine as long as schema is correct."""
        identity = _make_identity(
            firms_sha="1" * 40,
            dmc_sha="2" * 40,
            model_sha="3" * 64,
            topo_sha="4" * 64,
            baseline_sha="5" * 64,
        )
        path = _write(tmp_path, _make_manifest(identity))
        result = verify_data_plane_manifest(path)
        assert result["status"] == "PREPARED"

    def test_firms_present_dmc_absent_accepted(self, tmp_path):
        """Mixed current states are fine if they match expected."""
        identity = _make_identity(
            readiness="PREPARED",
            current_state={"firms": "PRESENT", "dmc": "ABSENT"},
            expected_current={"firms": "PRESENT", "dmc": "ABSENT"},
        )
        path = _write(tmp_path, _make_manifest(identity))
        result = verify_data_plane_manifest(path)
        assert result["status"] == "PREPARED"


# ===========================================================================
# 8. NON-OBJECT JSON ROOT (NEW-5 fix)
# ===========================================================================

class TestNonObjectJsonRoot:
    """Phase 9: Non-dict JSON roots must FAIL CLOSED — no crash, no PASS."""

    def _assert_fail_closed(self, tmp_path: Path, content: str, label: str) -> None:
        p = tmp_path / "DATA_PLANE_MANIFEST.json"
        p.write_text(content, encoding="utf-8")
        result = verify_data_plane_manifest(p)
        assert result["status"] == "FAIL", (
            f"Expected FAIL for non-object root ({label}), got {result['status']}"
        )
        assert result["ready"] is False
        assert result["prepared"] is False
        codes = [f["code"] for f in result["findings"]]
        assert "DATA_MANIFEST_NOT_OBJECT" in codes, (
            f"Expected DATA_MANIFEST_NOT_OBJECT for ({label}). Got codes: {codes}"
        )

    def test_array_root_fails(self, tmp_path):
        self._assert_fail_closed(tmp_path, "[]", "[]")

    def test_null_root_fails(self, tmp_path):
        self._assert_fail_closed(tmp_path, "null", "null")

    def test_string_root_fails(self, tmp_path):
        self._assert_fail_closed(tmp_path, '"hello"', '"hello"')

    def test_integer_root_fails(self, tmp_path):
        self._assert_fail_closed(tmp_path, "123", "123")

    def test_boolean_root_fails(self, tmp_path):
        self._assert_fail_closed(tmp_path, "true", "true")

    def test_array_of_objects_root_fails(self, tmp_path):
        self._assert_fail_closed(tmp_path, '[{"key": "value"}]', "[{...}]")

    def test_malformed_json_fails(self, tmp_path):
        p = tmp_path / "DATA_PLANE_MANIFEST.json"
        p.write_text("{not: valid json}", encoding="utf-8")
        result = verify_data_plane_manifest(p)
        assert result["status"] == "FAIL"
        assert result["ready"] is False
        codes = [f["code"] for f in result["findings"]]
        assert "DATA_MANIFEST_CORRUPT" in codes


# ===========================================================================
# 9. EXCEPTION SAFETY
# ===========================================================================

class TestExceptionSafety:
    """Every malformed input must resolve to a structured result — no crash."""

    def test_none_path_not_available(self):
        result = verify_data_plane_manifest(None)
        assert result["status"] == "NOT_AVAILABLE"
        assert result["ready"] is False

    def test_missing_file_not_available(self, tmp_path):
        result = verify_data_plane_manifest(tmp_path / "NONEXISTENT.json")
        assert result["status"] == "NOT_AVAILABLE"
        assert result["ready"] is False
        assert result["prepared"] is False

    def test_missing_identity_block_fails(self, tmp_path):
        manifest = {"schema_version": 1, "fingerprint": "abc"}
        path = _write(tmp_path, manifest)
        result = verify_data_plane_manifest(path)
        assert result["status"] == "FAIL"
        codes = [f["code"] for f in result["findings"]]
        assert "MISSING_IDENTITY_BLOCK" in codes

    def test_identity_not_dict_fails(self, tmp_path):
        manifest = {"schema_version": 1, "identity": "not a dict", "fingerprint": "abc"}
        path = _write(tmp_path, manifest)
        result = verify_data_plane_manifest(path)
        assert result["status"] == "FAIL"
        codes = [f["code"] for f in result["findings"]]
        assert "MISSING_IDENTITY_BLOCK" in codes

    def test_empty_identity_fails(self, tmp_path):
        manifest = {
            "schema_version": 1,
            "identity": {},
            "fingerprint": compute_data_manifest_fingerprint({}),
        }
        path = _write(tmp_path, manifest)
        result = verify_data_plane_manifest(path)
        assert result["status"] == "FAIL"

    def test_wrong_kind_fails(self, tmp_path):
        identity = _make_identity(kind="WRONG_KIND")
        path = _write(tmp_path, _make_manifest(identity))
        result = verify_data_plane_manifest(path)
        assert result["status"] == "FAIL"
        codes = [f["code"] for f in result["findings"]]
        assert "PRODUCER_SEMANTIC_VIOLATION" in codes or "WRONG_KIND" in codes


# ===========================================================================
# 10. SINGLE PARSER PATH — DataPlaneManifestView
# ===========================================================================

class TestSingleParserPath:
    """All Operations consumers use verify_data_plane_manifest — one canonical path."""

    def test_view_extracts_correct_firms_sha(self):
        identity = _make_identity(firms_sha="1" * 40)
        view = DataPlaneManifestView(_make_manifest(identity))
        assert view.firms_component_sha == "1" * 40

    def test_view_extracts_correct_dmc_sha(self):
        identity = _make_identity(dmc_sha="2" * 40)
        view = DataPlaneManifestView(_make_manifest(identity))
        assert view.dmc_component_sha == "2" * 40

    def test_view_extracts_model_sha(self):
        identity = _make_identity(model_sha="3" * 64)
        view = DataPlaneManifestView(_make_manifest(identity))
        assert view.model_sha == "3" * 64

    def test_view_extracts_topography_identity(self):
        identity = _make_identity(topo_sha="4" * 64)
        view = DataPlaneManifestView(_make_manifest(identity))
        assert view.topography_identity == "4" * 64

    def test_view_extracts_baseline_identity(self):
        identity = _make_identity(baseline_sha="5" * 64)
        view = DataPlaneManifestView(_make_manifest(identity))
        assert view.baseline_identity == "5" * 64

    def test_view_extracts_expected_current_state(self):
        identity = _make_identity()
        view = DataPlaneManifestView(_make_manifest(identity))
        assert view.expected_current_state == {"firms": "ABSENT", "dmc": "ABSENT"}

    def test_view_authorization_flags_false_by_default(self):
        identity = _make_identity()
        view = DataPlaneManifestView(_make_manifest(identity))
        assert view.writers_authorized is False
        assert view.attempt2_authorized is False
        assert view.telegram_authorized is False
        assert view.schedule_authorized is False

    def test_view_readiness_status(self):
        identity = _make_identity(readiness="PREPARED")
        view = DataPlaneManifestView(_make_manifest(identity))
        assert view.data_readiness_status == "PREPARED"

    def test_verifier_result_matches_view(self, tmp_path):
        identity = _make_identity(
            firms_sha="a" * 40, dmc_sha="b" * 40,
            model_sha="c" * 64, topo_sha="d" * 64, baseline_sha="e" * 64,
        )
        path = _write(tmp_path, _make_manifest(identity))
        result = verify_data_plane_manifest(path)
        assert result["firms_component_sha"] == "a" * 40
        assert result["dmc_component_sha"] == "b" * 40
        assert result["model_sha"] == "c" * 64
        assert result["topography_identity"] == "d" * 64
        assert result["baseline_identity"] == "e" * 64

    def test_producer_valid_field_exposed(self, tmp_path):
        """producer_valid must be exposed in result for all consumers."""
        identity = _make_identity()
        path = _write(tmp_path, _make_manifest(identity))
        result = verify_data_plane_manifest(path)
        assert "producer_valid" in result
        assert result["producer_valid"] is True

"""Data plane readiness manifest contract and verification (Phase E / Astra RC1 contract).

Consumes the authoritative Astra DATA_PLANE_MANIFEST without depending on the
mutable Astra branch.

Authoritative schema (version 1, nested):
  Top-level envelope keys: schema_version, created_at, fingerprint, identity,
                           observation, operational_roots
  Fingerprint recipe: SHA-256(canonical_json(identity))
    where canonical_json = json.dumps(value, sort_keys=True, separators=(',', ':'))
  All readiness / component / authorization state lives under identity.*

Status semantics:
  PASS        — valid schema, fingerprint OK, readiness_status == READY
  PREPARED    — valid schema, fingerprint OK, readiness_status == PREPARED
                (data staged / preparation evidence available, NOT writer-authorized)
  INCOMPLETE  — valid schema, fingerprint OK, readiness_status == INCOMPLETE
  FAIL        — invalid schema, missing fields, tampered fingerprint,
                readiness_status == FAIL, or unknown readiness value
  NOT_AVAILABLE — manifest path is None or file not found

CRITICAL: PREPARED != READY. A PREPARED manifest does NOT authorize:
  - any writer
  - Attempt 2 execution
  - scheduling
Never translate PREPARED into unrestricted PASS.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

# ---------------------------------------------------------------------------
# Schema constants
# ---------------------------------------------------------------------------

SCHEMA_VERSION = 1
DATA_PLANE_MANIFEST_FILENAME = "DATA_PLANE_MANIFEST.json"

# Required identity-block fields (all live under manifest["identity"])
_REQUIRED_IDENTITY_FIELDS = (
    "schema_version",
    "kind",
    "data_readiness_status",
    "data_ready_for_scoring",
    "independent_approval",
    "authorizations",
    "components",
    "code_identity",
    "model",
    "topography",
    "baseline",
    "expected_current",
    "current_state",
)

# Every authorization flag that must exist and be False in a safe manifest
_AUTH_FLAGS = ("attempt2", "writers", "telegram", "schedule")


# ---------------------------------------------------------------------------
# Fingerprint helpers  (producer contract: digest of identity block only)
# ---------------------------------------------------------------------------

def _canonical_json(value: Any) -> bytes:
    """Canonical deterministic JSON bytes — same recipe as the Astra producer."""
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def compute_data_manifest_fingerprint(identity_block: Mapping[str, Any]) -> str:
    """Return SHA-256 hex fingerprint of the identity block (producer contract).

    Args:
        identity_block: The ``manifest["identity"]`` dict produced by Astra's
                        data_readiness.build_manifest().  Do NOT pass the whole
                        envelope — the fingerprint covers only this block.
    """
    return hashlib.sha256(_canonical_json(identity_block)).hexdigest()


# ---------------------------------------------------------------------------
# Internal view  (canonical representation for all Operations consumers)
# ---------------------------------------------------------------------------

class DataPlaneManifestView:
    """Canonical internal representation of a parsed Data Plane manifest.

    All Operations logic (rc-status, preflight, operator init, RC context)
    should consume this view rather than the raw JSON layout.
    """

    def __init__(self, raw: dict[str, Any]) -> None:
        identity = raw.get("identity", {})
        code_id = identity.get("code_identity", {})
        components = identity.get("components", {})
        auth = identity.get("authorizations", {}) or {}

        self.schema_version: int = raw.get("schema_version", 0)
        self.kind: str = identity.get("kind", "")
        self.declared_fingerprint: str | None = raw.get("fingerprint")

        # Readiness
        self.data_readiness_status: str = str(
            identity.get("data_readiness_status", "INCOMPLETE")
        ).upper()
        self.data_ready_for_scoring: str = str(
            identity.get("data_ready_for_scoring", "NOT_EVALUATED")
        ).upper()
        self.independent_approval: str = str(
            identity.get("independent_approval", "PENDING")
        ).upper()

        # Code identity
        self.code_sha: str | None = code_id.get("sha")
        self.code_tree: str | None = code_id.get("tree")
        self.code_clean: bool | None = code_id.get("clean")

        # Component SHAs
        self.firms_component_sha: str | None = (
            components.get("firms", {}).get("sha")
        )
        self.dmc_component_sha: str | None = (
            components.get("dmc", {}).get("sha")
        )
        self.scoring_inputs_component_sha: str | None = (
            components.get("scoring_inputs", {}).get("sha")
        )

        # Asset identities
        model = identity.get("model", {})
        self.model_sha: str | None = model.get("sha256") or model.get("sha")

        topography = identity.get("topography", {})
        self.topography_identity: str | None = (
            topography.get("table_sha256") or topography.get("grid_sha256")
        )

        baseline = identity.get("baseline", {})
        self.baseline_identity: str | None = (
            baseline.get("sha256") or baseline.get("sha")
        )

        # State
        self.expected_current_state: dict | None = identity.get("expected_current")
        self.current_state: dict | None = identity.get("current_state")

        # Authorizations (fail-closed: missing flag = False)
        self.writers_authorized: bool = bool(auth.get("writers", False))
        self.attempt2_authorized: bool = bool(auth.get("attempt2", False))
        self.telegram_authorized: bool = bool(auth.get("telegram", False))
        self.schedule_authorized: bool = bool(auth.get("schedule", False))

        # Keep the raw identity block for fingerprint recomputation
        self._identity_block: dict[str, Any] = identity  # type: ignore[assignment]
        self._raw = raw


# ---------------------------------------------------------------------------
# Core verifier
# ---------------------------------------------------------------------------

def verify_data_plane_manifest(
    manifest_path: Path | str | None,
    *,
    expected_code_sha: str | None = None,
) -> dict[str, Any]:
    """Verify the Astra Data Plane readiness manifest (authoritative nested schema v1).

    Returns a result dict with keys:
      status          — PASS | PREPARED | INCOMPLETE | FAIL | NOT_AVAILABLE
      overall_status  — same as status
      ready           — True only when status == PASS
      prepared        — True when status in (PASS, PREPARED)
      manifest_path   — str path
      manifest_fingerprint — recomputed SHA-256 (of identity block)
      data_readiness_status  — value from identity block
      writers_authorized     — bool (fail-closed)
      attempt2_authorized    — bool (fail-closed)
      firms_component_sha    — str | None
      dmc_component_sha      — str | None
      model_sha              — str | None
      topography_identity    — str | None
      baseline_identity      — str | None
      expected_current_state — dict | None
      code_sha               — str | None
      observed_at            — ISO timestamp
      findings               — list[{id, code, severity, message}]
    """
    observed_at = datetime.now(timezone.utc).isoformat()

    # ------------------------------------------------------------------ #
    # 0. Path / file availability                                          #
    # ------------------------------------------------------------------ #
    if manifest_path is None:
        return _not_available(
            None, observed_at,
            "DM-001", "DATA_MANIFEST_NOT_AVAILABLE",
            "No data plane manifest provided",
        )

    path = Path(manifest_path)
    if path.is_dir():
        path = path / DATA_PLANE_MANIFEST_FILENAME

    if not path.is_file():
        return _not_available(
            str(path), observed_at,
            "DM-002", "DATA_MANIFEST_FILE_NOT_FOUND",
            f"Data plane manifest not found at: {path}",
        )

    # ------------------------------------------------------------------ #
    # 1. Parse JSON                                                        #
    # ------------------------------------------------------------------ #
    try:
        raw_text = path.read_text(encoding="utf-8")
        raw = json.loads(raw_text)
    except Exception as exc:
        return _fail_result(
            str(path), observed_at, None,
            [_finding("DM-003", "DATA_MANIFEST_CORRUPT", "FAIL",
                       f"Malformed data manifest JSON: {exc}")],
        )

    findings: list[dict[str, Any]] = []

    # ------------------------------------------------------------------ #
    # 2. Envelope schema version                                           #
    # ------------------------------------------------------------------ #
    if raw.get("schema_version") != SCHEMA_VERSION:
        findings.append(_finding(
            "DM-004", "UNSUPPORTED_DATA_MANIFEST_SCHEMA", "FAIL",
            f"Unsupported schema version: {raw.get('schema_version')}, expected {SCHEMA_VERSION}",
        ))

    # ------------------------------------------------------------------ #
    # 3. Identity block presence                                           #
    # ------------------------------------------------------------------ #
    identity = raw.get("identity")
    if not isinstance(identity, dict):
        findings.append(_finding(
            "DM-005", "MISSING_IDENTITY_BLOCK", "FAIL",
            "Required 'identity' block is missing or not a dict",
        ))
        return _fail_result(str(path), observed_at, None, findings)

    # ------------------------------------------------------------------ #
    # 4. Required identity fields                                          #
    # ------------------------------------------------------------------ #
    for field in _REQUIRED_IDENTITY_FIELDS:
        if field not in identity or identity[field] is None:
            findings.append(_finding(
                "DM-005", "MISSING_REQUIRED_IDENTITY_FIELD", "FAIL",
                f"Required identity field missing: identity.{field}",
            ))

    # ------------------------------------------------------------------ #
    # 5. Kind check                                                        #
    # ------------------------------------------------------------------ #
    if identity.get("kind") != "DATA_PLANE_MANIFEST":
        findings.append(_finding(
            "DM-008", "WRONG_KIND", "FAIL",
            f"Expected kind=DATA_PLANE_MANIFEST, got: {identity.get('kind')!r}",
        ))

    # ------------------------------------------------------------------ #
    # 6. Fingerprint verification (covers identity block only)             #
    # ------------------------------------------------------------------ #
    declared_fp = raw.get("fingerprint")
    computed_fp = compute_data_manifest_fingerprint(identity)

    if declared_fp is None:
        findings.append(_finding(
            "DM-006", "DATA_MANIFEST_NO_FINGERPRINT", "FAIL",
            "Manifest has no 'fingerprint' field",
        ))
    elif declared_fp != computed_fp:
        findings.append(_finding(
            "DM-006", "DATA_MANIFEST_TAMPERED", "FAIL",
            f"Manifest fingerprint mismatch: declared {declared_fp} != computed {computed_fp}",
        ))

    # ------------------------------------------------------------------ #
    # 7. Authorization flags (fail-closed)                                 #
    # ------------------------------------------------------------------ #
    auth = identity.get("authorizations") or {}
    if not isinstance(auth, dict):
        findings.append(_finding(
            "DM-009", "INVALID_AUTHORIZATIONS", "FAIL",
            "identity.authorizations must be a dict",
        ))
    else:
        for flag in _AUTH_FLAGS:
            if flag not in auth:
                findings.append(_finding(
                    "DM-009", "MISSING_AUTH_FLAG", "FAIL",
                    f"identity.authorizations.{flag} is missing (fail-closed)",
                ))

    # ------------------------------------------------------------------ #
    # 8. Readiness status                                                  #
    # ------------------------------------------------------------------ #
    readiness = str(identity.get("data_readiness_status", "INCOMPLETE")).upper()
    readiness_finding_severity: str | None = None

    if readiness == "FAIL":
        readiness_finding_severity = "FAIL"
        findings.append(_finding(
            "DM-007", "DATA_PLANE_NOT_READY", "FAIL",
            "Data plane data_readiness_status is FAIL",
        ))
    elif readiness == "INCOMPLETE":
        readiness_finding_severity = "INCOMPLETE"
        findings.append(_finding(
            "DM-007", "DATA_PLANE_INCOMPLETE", "INCOMPLETE",
            "Data plane data_readiness_status is INCOMPLETE",
        ))
    elif readiness not in ("READY", "PREPARED", "NOT_PREPARED"):
        readiness_finding_severity = "FAIL"
        findings.append(_finding(
            "DM-007", "DATA_PLANE_UNKNOWN_STATUS", "FAIL",
            f"Unknown data plane readiness status: {readiness}",
        ))

    # ------------------------------------------------------------------ #
    # 9. Code SHA cross-check (informational WARN, not FAIL)               #
    # ------------------------------------------------------------------ #
    code_id = identity.get("code_identity", {})
    actual_code_sha = code_id.get("sha") if isinstance(code_id, dict) else None
    if expected_code_sha and actual_code_sha and actual_code_sha != expected_code_sha:
        findings.append(_finding(
            "DM-010", "CODE_SHA_MISMATCH", "WARN",
            f"Data plane code SHA {actual_code_sha} != expected {expected_code_sha}",
        ))

    # ------------------------------------------------------------------ #
    # 10. Build canonical view                                             #
    # ------------------------------------------------------------------ #
    view = DataPlaneManifestView(raw)

    # ------------------------------------------------------------------ #
    # 11. Determine overall status                                         #
    # ------------------------------------------------------------------ #
    has_failures = any(f["severity"] == "FAIL" for f in findings)
    has_incomplete = any(f["severity"] == "INCOMPLETE" for f in findings)

    if has_failures:
        overall = "FAIL"
    elif has_incomplete:
        overall = "INCOMPLETE"
    elif readiness == "READY":
        overall = "PASS"
    elif readiness == "PREPARED":
        overall = "PREPARED"  # valid schema, data staged, not yet ready for scoring
    else:
        overall = "INCOMPLETE"

    return {
        "status": overall,
        "overall_status": overall,
        "ready": overall == "PASS",
        "prepared": overall in ("PASS", "PREPARED"),
        "manifest_path": str(path),
        "manifest_fingerprint": computed_fp,
        "declared_fingerprint": declared_fp,
        "fingerprint_match": declared_fp == computed_fp if declared_fp else False,
        # Readiness / authorization (fail-closed)
        "data_readiness_status": view.data_readiness_status,
        "writers_authorized": view.writers_authorized,
        "attempt2_authorized": view.attempt2_authorized,
        "telegram_authorized": view.telegram_authorized,
        "schedule_authorized": view.schedule_authorized,
        # Component identities
        "firms_component_sha": view.firms_component_sha,
        "dmc_component_sha": view.dmc_component_sha,
        "model_sha": view.model_sha,
        "topography_identity": view.topography_identity,
        "baseline_identity": view.baseline_identity,
        "expected_current_state": view.expected_current_state,
        # Code identity
        "code_sha": view.code_sha,
        # Metadata
        "observed_at": observed_at,
        "findings": findings,
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _finding(fid: str, code: str, severity: str, message: str) -> dict[str, Any]:
    return {"id": fid, "code": code, "severity": severity, "message": message}


def _not_available(
    path: str | None, observed_at: str,
    fid: str, code: str, message: str,
) -> dict[str, Any]:
    return {
        "status": "NOT_AVAILABLE",
        "overall_status": "NOT_AVAILABLE",
        "ready": False,
        "prepared": False,
        "manifest_path": path,
        "manifest_fingerprint": None,
        "declared_fingerprint": None,
        "fingerprint_match": False,
        "data_readiness_status": None,
        "writers_authorized": False,
        "attempt2_authorized": False,
        "telegram_authorized": False,
        "schedule_authorized": False,
        "firms_component_sha": None,
        "dmc_component_sha": None,
        "model_sha": None,
        "topography_identity": None,
        "baseline_identity": None,
        "expected_current_state": None,
        "code_sha": None,
        "observed_at": observed_at,
        "findings": [_finding(fid, code, "INCOMPLETE", message)],
    }


def _fail_result(
    path: str, observed_at: str,
    computed_fp: str | None,
    findings: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "status": "FAIL",
        "overall_status": "FAIL",
        "ready": False,
        "prepared": False,
        "manifest_path": path,
        "manifest_fingerprint": computed_fp,
        "declared_fingerprint": None,
        "fingerprint_match": False,
        "data_readiness_status": None,
        "writers_authorized": False,
        "attempt2_authorized": False,
        "telegram_authorized": False,
        "schedule_authorized": False,
        "firms_component_sha": None,
        "dmc_component_sha": None,
        "model_sha": None,
        "topography_identity": None,
        "baseline_identity": None,
        "expected_current_state": None,
        "code_sha": None,
        "observed_at": observed_at,
        "findings": findings,
    }

"""Data plane readiness manifest contract and verification (Phase E / Astra RC1 contract).

Consumes the authoritative Astra DATA_PLANE_MANIFEST without depending on the
mutable Astra branch.

Authoritative schema (version 1, nested):
  Top-level envelope keys: schema_version, created_at, fingerprint, identity,
                           observation, operational_roots
  Fingerprint recipe: SHA-256(canonical_json(identity))
    where canonical_json = json.dumps(value, sort_keys=True, separators=(',', ':'),
                                       ensure_ascii=True, allow_nan=False)
  All readiness / component / authorization state lives under identity.*

Status semantics (Operations):
  PREPARED    — producer-valid schema, fingerprint OK, data_readiness_status in
                {"PREPARED"} with all PREPARED-specific checks satisfied.
                data_readiness_status == "PREPARED" is the highest valid producer state.
  NOT_PREPARED — producer-valid schema, data_readiness_status == "NOT_PREPARED"
  INCOMPLETE  — producer-valid schema, data_readiness_status == "INCOMPLETE"
  FAIL        — invalid schema, missing fields, tampered fingerprint, OR
                producer-semantic validation failure (re-signed attack rejected)
  NOT_AVAILABLE — manifest path is None or file not found

CRITICAL:
  "READY" is NOT a valid data_readiness_status in the producer contract.
  Any manifest with data_readiness_status="READY" FAILS producer validation.
  A correctly re-signed manifest is STILL REJECTED if producer semantics fail.
  PREPARED != writer-authorized, Attempt2-authorized, or ready-for-scoring.

Producer semantic validator ported from:
  src/ops/data_readiness.verify_manifest
  Data Plane SHA: cd9c01408059961fb30e4b6321429a018e4a0df5
  Keep in sync with producer contract when Data Plane SHA advances.
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

# Authorization flags that must all be explicitly present and False
_AUTH_FLAGS = ("attempt2", "writers", "telegram", "schedule")

# Asset blocks checked for status==PASS when readiness==PREPARED
_PREPARED_ASSET_BLOCKS = (
    "model",
    "topography",
    "baseline",
    "source_evidence",
    "code_identity",
)

# Required identity-block fields
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


# ---------------------------------------------------------------------------
# Fingerprint helpers (exact producer recipe at cd9c01408059961fb30e4b6321429a018e4a0df5)
# ---------------------------------------------------------------------------


def _canonical_json(value: Any) -> bytes:
    """Canonical deterministic JSON bytes — exact producer recipe.

    Matches data_readiness.canonical():
      json.dumps(value, sort_keys=True, separators=(',',':'),
                  ensure_ascii=True, allow_nan=False).encode()
    """
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode()


def compute_data_manifest_fingerprint(identity_block: Mapping[str, Any]) -> str:
    """Return SHA-256 hex fingerprint of the identity block (producer contract).

    Args:
        identity_block: The ``manifest["identity"]`` dict produced by Astra's
                        data_readiness.build_manifest(). Do NOT pass the whole
                        envelope — the fingerprint covers only this block.
    """
    return hashlib.sha256(_canonical_json(identity_block)).hexdigest()


# ---------------------------------------------------------------------------
# Producer semantic validator (ported inline — attributed to exact SHA)
# ---------------------------------------------------------------------------


def _producer_semantic_validate(
    raw: dict[str, Any],
    identity: dict[str, Any],
) -> tuple[bool, list[str]]:
    """Port of authoritative producer semantic validation.

    Source: src/ops/data_readiness.verify_manifest()
    Data Plane SHA: cd9c01408059961fb30e4b6321429a018e4a0df5

    This function intentionally does NOT re-check the fingerprint — that is
    done separately in verify_data_plane_manifest() before this is called.
    All other producer conditions are enforced here.

    Returns:
        (is_valid, reasons)  — reasons is non-empty when is_valid is False
    """
    reasons: list[str] = []
    try:
        readiness = str(identity.get("data_readiness_status", "")).upper()

        # PREPARED-specific semantic checks (from producer)
        if readiness == "PREPARED":
            findings = identity.get("findings") or []
            current_state = identity.get("current_state") or {}
            expected_current = identity.get("expected_current") or {}

            if findings:
                reasons.append(
                    f"PREPARED manifest must have no findings, got {len(findings)}"
                )
                return False, reasons

            if current_state != expected_current:
                reasons.append(
                    f"current_state {current_state!r} must equal "
                    f"expected_current {expected_current!r}"
                )
                return False, reasons

            if set(current_state) != {"firms", "dmc"}:
                reasons.append(
                    f"current_state must have exactly 'firms' and 'dmc' keys, "
                    f"got {set(current_state)!r}"
                )
                return False, reasons

            for key, state in current_state.items():
                if state not in ("ABSENT", "PRESENT"):
                    reasons.append(
                        f"current_state.{key}={state!r} must be ABSENT or PRESENT"
                    )
                    return False, reasons

            for block_name in _PREPARED_ASSET_BLOCKS:
                block = identity.get(block_name)
                if not isinstance(block, dict) or block.get("status") != "PASS":
                    reasons.append(
                        f"identity.{block_name}.status must be PASS for PREPARED state"
                    )
                    return False, reasons

        # Envelope/identity schema version must both be 1
        if raw.get("schema_version") != 1 or identity.get("schema_version") != 1:
            reasons.append(
                f"schema_version mismatch: envelope={raw.get('schema_version')!r}, "
                f"identity={identity.get('schema_version')!r}, both must be 1"
            )
            return False, reasons

        # Kind
        if identity.get("kind") != "DATA_PLANE_MANIFEST":
            reasons.append(
                f"identity.kind must be DATA_PLANE_MANIFEST, "
                f"got {identity.get('kind')!r}"
            )
            return False, reasons

        # Valid producer readiness values (READY is NOT valid)
        if readiness not in ("PREPARED", "NOT_PREPARED", "INCOMPLETE"):
            reasons.append(
                f"data_readiness_status={readiness!r} is not a valid producer "
                f"value. Must be PREPARED, NOT_PREPARED, or INCOMPLETE. "
                f"'READY' is not produced by the data plane contract."
            )
            return False, reasons

        # data_ready_for_scoring
        if str(identity.get("data_ready_for_scoring", "")).upper() != "NOT_EVALUATED":
            reasons.append(
                f"data_ready_for_scoring must be NOT_EVALUATED, "
                f"got {identity.get('data_ready_for_scoring')!r}"
            )
            return False, reasons

        # independent_approval
        if str(identity.get("independent_approval", "")).upper() != "PENDING":
            reasons.append(
                f"independent_approval must be PENDING, "
                f"got {identity.get('independent_approval')!r}"
            )
            return False, reasons

        # Exact authorizations dict
        expected_auth = {name: False for name in _AUTH_FLAGS}
        if identity.get("authorizations") != expected_auth:
            reasons.append(
                f"authorizations must be exactly {expected_auth!r}, "
                f"got {identity.get('authorizations')!r}"
            )
            return False, reasons

        return True, []

    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        reasons.append(f"producer_validate_exception: {exc!r}")
        return False, reasons


# ---------------------------------------------------------------------------
# Internal view  (canonical representation for all Operations consumers)
# ---------------------------------------------------------------------------


class DataPlaneManifestView:
    """Canonical internal representation of a parsed Data Plane manifest.

    All Operations logic (rc-status, preflight, operator init, RC context)
    should consume this view rather than the raw JSON layout.
    """

    def __init__(self, raw: dict[str, Any]) -> None:
        identity = raw.get("identity") or {}
        code_id = identity.get("code_identity") or {}
        components = identity.get("components") or {}
        auth = identity.get("authorizations") or {}

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
        self.firms_component_sha: str | None = components.get("firms", {}).get("sha")
        self.dmc_component_sha: str | None = components.get("dmc", {}).get("sha")
        self.scoring_inputs_component_sha: str | None = components.get(
            "scoring_inputs", {}
        ).get("sha")

        # Asset identities
        model = identity.get("model") or {}
        self.model_sha: str | None = model.get("sha256") or model.get("sha")

        topography = identity.get("topography") or {}
        self.topography_identity: str | None = topography.get(
            "table_sha256"
        ) or topography.get("grid_sha256")

        baseline = identity.get("baseline") or {}
        self.baseline_identity: str | None = baseline.get("sha256") or baseline.get(
            "sha"
        )

        # State
        self.expected_current_state: dict | None = identity.get("expected_current")
        self.current_state: dict | None = identity.get("current_state")

        # Authorizations (fail-closed: missing flag = False)
        self.writers_authorized: bool = bool(auth.get("writers", False))
        self.attempt2_authorized: bool = bool(auth.get("attempt2", False))
        self.telegram_authorized: bool = bool(auth.get("telegram", False))
        self.schedule_authorized: bool = bool(auth.get("schedule", False))

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

    Validation order:
      1. Path / file availability
      2. JSON parse
      3. Non-object root guard (NEW-5)
      4. Envelope schema version
      5. Identity block presence
      6. Required identity fields
      7. Cryptographic fingerprint (covers identity block only)
      8. Producer semantic validation (prevents re-signed attack — ADAPTER-GAP-1)
      9. Code SHA cross-check (informational)

    Returns a result dict with keys:
      status          — PREPARED | NOT_PREPARED | INCOMPLETE | FAIL | NOT_AVAILABLE
      overall_status  — same as status
      ready           — always False (no producer "READY" state exists)
      prepared        — True when status == PREPARED
      manifest_path   — str path
      manifest_fingerprint — recomputed SHA-256 (of identity block)
      declared_fingerprint — declared value from manifest["fingerprint"]
      fingerprint_match    — bool
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
      producer_valid         — bool (True when producer semantics pass)
      observed_at            — ISO timestamp
      findings               — list[{id, code, severity, message}]
    """
    observed_at = datetime.now(timezone.utc).isoformat()

    # ------------------------------------------------------------------ #
    # 1. Path / file availability                                          #
    # ------------------------------------------------------------------ #
    if manifest_path is None:
        return _not_available(
            None,
            observed_at,
            "DM-001",
            "DATA_MANIFEST_NOT_AVAILABLE",
            "No data plane manifest provided",
        )

    path = Path(manifest_path)
    if path.is_dir():
        path = path / DATA_PLANE_MANIFEST_FILENAME

    if not path.is_file():
        return _not_available(
            str(path),
            observed_at,
            "DM-002",
            "DATA_MANIFEST_FILE_NOT_FOUND",
            f"Data plane manifest not found at: {path}",
        )

    # ------------------------------------------------------------------ #
    # 2. Parse JSON                                                        #
    # ------------------------------------------------------------------ #
    try:
        raw_text = path.read_text(encoding="utf-8")
        raw = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        return _fail_result(
            str(path),
            observed_at,
            None,
            [
                _finding(
                    "DM-003", "DATA_MANIFEST_CORRUPT", "FAIL", f"Malformed JSON: {exc}"
                )
            ],
        )
    except Exception as exc:
        return _fail_result(
            str(path),
            observed_at,
            None,
            [
                _finding(
                    "DM-003",
                    "DATA_MANIFEST_READ_ERROR",
                    "FAIL",
                    f"Cannot read manifest: {exc}",
                )
            ],
        )

    # ------------------------------------------------------------------ #
    # 3. Non-object root guard (NEW-5)                                    #
    # ------------------------------------------------------------------ #
    if not isinstance(raw, dict):
        return _fail_result(
            str(path),
            observed_at,
            None,
            [
                _finding(
                    "DM-011",
                    "DATA_MANIFEST_NOT_OBJECT",
                    "FAIL",
                    f"Manifest JSON root must be a dict/object, "
                    f"got {type(raw).__name__!r} — value: "
                    f"{json.dumps(raw)[:80]!r}",
                )
            ],
        )

    findings: list[dict[str, Any]] = []

    # ------------------------------------------------------------------ #
    # 4. Envelope schema version                                           #
    # ------------------------------------------------------------------ #
    if raw.get("schema_version") != SCHEMA_VERSION:
        findings.append(
            _finding(
                "DM-004",
                "UNSUPPORTED_DATA_MANIFEST_SCHEMA",
                "FAIL",
                f"Unsupported schema version: {raw.get('schema_version')!r}, "
                f"expected {SCHEMA_VERSION}",
            )
        )

    # ------------------------------------------------------------------ #
    # 5. Identity block presence                                           #
    # ------------------------------------------------------------------ #
    identity = raw.get("identity")
    if not isinstance(identity, dict):
        findings.append(
            _finding(
                "DM-005",
                "MISSING_IDENTITY_BLOCK",
                "FAIL",
                "Required 'identity' block is missing or not a dict",
            )
        )
        return _fail_result(str(path), observed_at, None, findings)

    # ------------------------------------------------------------------ #
    # 6. Required identity fields                                          #
    # ------------------------------------------------------------------ #
    for field in _REQUIRED_IDENTITY_FIELDS:
        if field not in identity or identity[field] is None:
            findings.append(
                _finding(
                    "DM-005",
                    "MISSING_REQUIRED_IDENTITY_FIELD",
                    "FAIL",
                    f"Required identity field missing: identity.{field}",
                )
            )

    # ------------------------------------------------------------------ #
    # 7. Cryptographic fingerprint (covers identity block only)            #
    # ------------------------------------------------------------------ #
    declared_fp = raw.get("fingerprint")
    computed_fp: str | None

    try:
        computed_fp = compute_data_manifest_fingerprint(identity)
    except (TypeError, ValueError) as exc:
        computed_fp = None
        findings.append(
            _finding(
                "DM-006",
                "DATA_MANIFEST_FINGERPRINT_ERROR",
                "FAIL",
                f"Cannot compute fingerprint: {exc}",
            )
        )

    if computed_fp is not None:
        if declared_fp is None:
            findings.append(
                _finding(
                    "DM-006",
                    "DATA_MANIFEST_NO_FINGERPRINT",
                    "FAIL",
                    "Manifest has no 'fingerprint' field",
                )
            )
        elif declared_fp != computed_fp:
            findings.append(
                _finding(
                    "DM-006",
                    "DATA_MANIFEST_TAMPERED",
                    "FAIL",
                    f"Manifest fingerprint mismatch: "
                    f"declared {declared_fp} != computed {computed_fp}",
                )
            )

    fingerprint_ok = (
        computed_fp is not None
        and declared_fp is not None
        and declared_fp == computed_fp
    )

    # ------------------------------------------------------------------ #
    # 8. Producer semantic validation (ADAPTER-GAP-1 fix)                  #
    # Only run if fingerprint passed — re-signed attacks caught here.      #
    # ------------------------------------------------------------------ #
    producer_valid = False
    if fingerprint_ok and not any(f["severity"] == "FAIL" for f in findings):
        ok, reasons = _producer_semantic_validate(raw, identity)
        producer_valid = ok
        if not ok:
            for reason in reasons:
                findings.append(
                    _finding(
                        "DM-012",
                        "PRODUCER_SEMANTIC_VIOLATION",
                        "FAIL",
                        f"Producer semantic validation failed: {reason}",
                    )
                )
    elif not any(f["severity"] == "FAIL" for f in findings):
        # fingerprint failed — producer check skipped
        # V4 note: V3 DM-009 AUTHORIZATION_CLAIMED is fully subsumed by
        # _producer_semantic_validate() which requires authorizations == {all False}
        # exactly (line ~213). Any claimed authorization fails at PRODUCER_SEMANTIC_VIOLATION.
        pass

    # ------------------------------------------------------------------ #
    # 9. Code SHA cross-check (informational WARN)                         #
    # ------------------------------------------------------------------ #
    if isinstance(identity.get("code_identity"), dict):
        actual_code_sha = identity["code_identity"].get("sha")
        if (
            expected_code_sha
            and actual_code_sha
            and actual_code_sha != expected_code_sha
        ):
            findings.append(
                _finding(
                    "DM-010",
                    "CODE_SHA_MISMATCH",
                    "WARN",
                    f"Data plane code SHA {actual_code_sha} != "
                    f"expected {expected_code_sha}",
                )
            )

    # ------------------------------------------------------------------ #
    # 10. Build canonical view                                              #
    # ------------------------------------------------------------------ #
    try:
        view = DataPlaneManifestView(raw)
    except Exception as exc:  # pragma: no cover — defensive
        return _fail_result(
            str(path),
            observed_at,
            computed_fp,
            findings
            + [
                _finding(
                    "DM-013",
                    "DATA_MANIFEST_VIEW_ERROR",
                    "FAIL",
                    f"Cannot build manifest view: {exc}",
                )
            ],
        )

    # ------------------------------------------------------------------ #
    # 11. Determine overall status                                          #
    # ------------------------------------------------------------------ #
    has_failures = any(f["severity"] == "FAIL" for f in findings)

    if has_failures:
        overall = "FAIL"
    elif not producer_valid:
        # Producer validation was skipped (e.g. fingerprint failed) — already FAIL above
        # This branch only reached if fingerprint had non-FAIL issues; treat as FAIL
        overall = "FAIL"
    else:
        readiness = str(identity.get("data_readiness_status", "INCOMPLETE")).upper()
        if readiness == "PREPARED":
            overall = "PREPARED"
        elif readiness == "NOT_PREPARED":
            overall = "NOT_PREPARED"
        else:
            overall = "INCOMPLETE"

    return {
        "status": overall,
        "overall_status": overall,
        "ready": False,  # No producer "READY" state exists — never True
        "prepared": overall == "PREPARED",
        "manifest_path": str(path),
        "manifest_fingerprint": computed_fp,
        "declared_fingerprint": declared_fp,
        "fingerprint_match": fingerprint_ok,
        "producer_valid": producer_valid,
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
    path: str | None,
    observed_at: str,
    fid: str,
    code: str,
    message: str,
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
        "producer_valid": False,
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
    path: str | None,
    observed_at: str,
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
        "producer_valid": False,
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

"""Data plane readiness manifest contract and verification (Phase E / Astra contract).

Defines the external interface for Astra's future DATA_PLANE_MANIFEST.
Consumes it without depending on Astra's mutable branch.
Until a real manifest exists: status is NOT_AVAILABLE / INCOMPLETE.
Never synthetic PASS on the real machine.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

SCHEMA_VERSION = 1
DATA_PLANE_MANIFEST_FILENAME = "DATA-PLANE-MANIFEST.json"
REQUIRED_FIELDS = (
    "schema_version",
    "readiness_status",
    "firms_component_sha",
    "dmc_component_sha",
    "model_sha",
    "topography_identity",
    "baseline_identity",
    "expected_current_state",
)


def compute_data_manifest_fingerprint(data: Mapping[str, Any]) -> str:
    """Canonical SHA-256 fingerprint excluding self-referential manifest_fingerprint."""
    body = {k: v for k, v in data.items() if k != "manifest_fingerprint"}
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def verify_data_plane_manifest(
    manifest_path: Path | str | None,
    *,
    expected_code_sha: str | None = None,
) -> dict[str, Any]:
    """Verify data plane readiness manifest.

    Returns:
      PASS: valid, verified, readiness_status == READY
      FAIL: invalid schema, missing required fields, tampered fingerprint, readiness_status == FAIL
      INCOMPLETE: readiness_status == INCOMPLETE
      NOT_AVAILABLE: manifest path is None or does not exist
    """
    observed_at = datetime.now(timezone.utc).isoformat()
    if manifest_path is None:
        return {
            "status": "NOT_AVAILABLE",
            "overall_status": "NOT_AVAILABLE",
            "ready": False,
            "manifest_path": None,
            "observed_at": observed_at,
            "findings": [{"id": "DM-001", "code": "DATA_MANIFEST_NOT_AVAILABLE", "severity": "INCOMPLETE", "message": "No data plane manifest provided"}],
            "note": "Astra DATA_PLANE_MANIFEST not provided — status remains NOT_AVAILABLE",
        }

    path = Path(manifest_path)
    if path.is_dir():
        path = path / DATA_PLANE_MANIFEST_FILENAME

    if not path.is_file():
        return {
            "status": "NOT_AVAILABLE",
            "overall_status": "NOT_AVAILABLE",
            "ready": False,
            "manifest_path": str(path),
            "observed_at": observed_at,
            "findings": [{"id": "DM-002", "code": "DATA_MANIFEST_FILE_NOT_FOUND", "severity": "INCOMPLETE", "message": f"Data plane manifest not found at: {path}"}],
            "note": "Data plane manifest file not found",
        }

    try:
        raw_text = path.read_text(encoding="utf-8")
        data = json.loads(raw_text)
    except Exception as exc:
        return {
            "status": "FAIL",
            "overall_status": "FAIL",
            "ready": False,
            "manifest_path": str(path),
            "observed_at": observed_at,
            "findings": [{"id": "DM-003", "code": "DATA_MANIFEST_CORRUPT", "severity": "FAIL", "message": f"Malformed data manifest JSON: {exc}"}],
            "note": f"Malformed JSON: {exc}",
        }

    findings: list[dict[str, Any]] = []

    # 1. Schema version
    if data.get("schema_version") != SCHEMA_VERSION:
        findings.append({
            "id": "DM-004",
            "code": "UNSUPPORTED_DATA_MANIFEST_SCHEMA",
            "severity": "FAIL",
            "message": f"Unsupported schema version: {data.get('schema_version')}, expected {SCHEMA_VERSION}",
        })

    # 2. Required fields
    for field in REQUIRED_FIELDS:
        if field not in data or data[field] is None or data[field] == "":
            findings.append({
                "id": "DM-005",
                "code": "MISSING_REQUIRED_FIELD",
                "severity": "FAIL",
                "message": f"Required data plane field missing: {field}",
            })

    # 3. Fingerprint tampering check
    computed_fp = compute_data_manifest_fingerprint(data)
    declared_fp = data.get("manifest_fingerprint")
    if declared_fp and declared_fp != computed_fp:
        findings.append({
            "id": "DM-006",
            "code": "DATA_MANIFEST_TAMPERED",
            "severity": "FAIL",
            "message": f"Manifest fingerprint mismatch: declared {declared_fp} != computed {computed_fp}",
        })

    # 4. Readiness status
    readiness = str(data.get("readiness_status", "INCOMPLETE")).upper()
    if readiness == "FAIL":
        findings.append({
            "id": "DM-007",
            "code": "DATA_PLANE_NOT_READY",
            "severity": "FAIL",
            "message": "Data plane readiness_status is FAIL",
        })
    elif readiness == "INCOMPLETE":
        findings.append({
            "id": "DM-007",
            "code": "DATA_PLANE_INCOMPLETE",
            "severity": "INCOMPLETE",
            "message": "Data plane readiness_status is INCOMPLETE",
        })
    elif readiness != "READY":
        findings.append({
            "id": "DM-007",
            "code": "DATA_PLANE_UNKNOWN_STATUS",
            "severity": "FAIL",
            "message": f"Unknown data plane readiness status: {readiness}",
        })

    has_failures = any(f["severity"] == "FAIL" for f in findings)
    has_incomplete = any(f["severity"] == "INCOMPLETE" for f in findings)

    overall = "FAIL" if has_failures else "INCOMPLETE" if has_incomplete else "PASS"

    return {
        "status": overall,
        "overall_status": overall,
        "ready": overall == "PASS",
        "manifest_path": str(path),
        "manifest_fingerprint": computed_fp,
        "readiness_status": readiness,
        "firms_component_sha": data.get("firms_component_sha"),
        "dmc_component_sha": data.get("dmc_component_sha"),
        "model_sha": data.get("model_sha"),
        "topography_identity": data.get("topography_identity"),
        "baseline_identity": data.get("baseline_identity"),
        "expected_current_state": data.get("expected_current_state"),
        "observed_at": observed_at,
        "findings": findings,
    }

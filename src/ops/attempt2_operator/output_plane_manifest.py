"""Output plane manifest contract and acceptance verification (Phase F / Claude contract).

Defines the interface for post-score acceptance evidence from the Output Plane.
The Operations Plane records:
- output contract version
- accepted score artifact path and SHA-256
- output manifest fingerprint
without implementing presentation logic.
If unavailable: INCOMPLETE / NOT_AVAILABLE (does not fail operator core).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

SCHEMA_VERSION = 1
OUTPUT_PLANE_MANIFEST_FILENAME = "OUTPUT-PLANE-MANIFEST.json"
REQUIRED_FIELDS = (
    "schema_version",
    "output_contract_version",
    "accepted_score_artifact_path",
    "accepted_score_artifact_sha256",
)


def compute_output_manifest_fingerprint(data: Mapping[str, Any]) -> str:
    """Canonical SHA-256 fingerprint excluding self-referential manifest_fingerprint."""
    body = {k: v for k, v in data.items() if k != "manifest_fingerprint"}
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_output_plane_manifest(
    manifest_path: Path | str | None,
    *,
    score_artifact_path: Path | str | None = None,
) -> dict[str, Any]:
    """Verify output plane manifest against score artifact.

    Returns:
      PASS: valid, verified, score artifact SHA matches
      FAIL: schema violation, tampered fingerprint, or artifact hash mismatch
      INCOMPLETE: missing optional artifact
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
            "findings": [{"id": "OP-001", "code": "OUTPUT_MANIFEST_NOT_AVAILABLE", "severity": "INFO", "message": "No output plane manifest provided"}],
            "note": "Output plane manifest not provided (optional for operator core)",
        }

    path = Path(manifest_path)
    if path.is_dir():
        path = path / OUTPUT_PLANE_MANIFEST_FILENAME

    if not path.is_file():
        return {
            "status": "NOT_AVAILABLE",
            "overall_status": "NOT_AVAILABLE",
            "ready": False,
            "manifest_path": str(path),
            "observed_at": observed_at,
            "findings": [{"id": "OP-002", "code": "OUTPUT_MANIFEST_NOT_FOUND", "severity": "INFO", "message": f"Output plane manifest not found at: {path}"}],
            "note": "Output plane manifest file not found",
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
            "findings": [{"id": "OP-003", "code": "OUTPUT_MANIFEST_CORRUPT", "severity": "FAIL", "message": f"Malformed output manifest JSON: {exc}"}],
            "note": f"Malformed JSON: {exc}",
        }

    findings: list[dict[str, Any]] = []

    if data.get("schema_version") != SCHEMA_VERSION:
        findings.append({
            "id": "OP-004",
            "code": "UNSUPPORTED_OUTPUT_MANIFEST_SCHEMA",
            "severity": "FAIL",
            "message": f"Unsupported schema version: {data.get('schema_version')}, expected {SCHEMA_VERSION}",
        })

    for field in REQUIRED_FIELDS:
        if field not in data or data[field] is None or data[field] == "":
            findings.append({
                "id": "OP-005",
                "code": "MISSING_REQUIRED_FIELD",
                "severity": "FAIL",
                "message": f"Required output plane field missing: {field}",
            })

    computed_fp = compute_output_manifest_fingerprint(data)
    declared_fp = data.get("manifest_fingerprint")
    if declared_fp and declared_fp != computed_fp:
        findings.append({
            "id": "OP-006",
            "code": "TAMPERED_OUTPUT_ACCEPTANCE",
            "severity": "FAIL",
            "message": f"Output manifest fingerprint mismatch: declared {declared_fp} != computed {computed_fp}",
        })

    # Verify score artifact file if accessible
    expected_artifact_sha = data.get("accepted_score_artifact_sha256")
    target_artifact = (
        Path(score_artifact_path) if score_artifact_path else Path(data.get("accepted_score_artifact_path", ""))
    )
    if target_artifact and target_artifact.is_file():
        actual_sha = _sha256_file(target_artifact)
        if expected_artifact_sha and actual_sha != expected_artifact_sha:
            findings.append({
                "id": "OP-007",
                "code": "TAMPERED_OUTPUT_ACCEPTANCE",
                "severity": "FAIL",
                "message": f"Score artifact SHA {actual_sha} != expected {expected_artifact_sha}",
            })
    elif expected_artifact_sha and not (target_artifact and target_artifact.is_file()):
        findings.append({
            "id": "OP-008",
            "code": "SCORE_ARTIFACT_NOT_FOUND",
            "severity": "INCOMPLETE",
            "message": f"Score artifact referenced by output manifest not found: {target_artifact}",
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
        "output_contract_version": data.get("output_contract_version"),
        "accepted_score_artifact_path": str(target_artifact),
        "accepted_score_artifact_sha256": expected_artifact_sha,
        "presentation_contract_status": data.get("presentation_contract_status", "UNKNOWN"),
        "observed_at": observed_at,
        "findings": findings,
    }

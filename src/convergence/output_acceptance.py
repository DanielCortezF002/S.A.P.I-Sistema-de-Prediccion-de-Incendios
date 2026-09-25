"""Output → Operations acceptance record (convergence-owned; resolves RC1 BLOCKER 2).

The Output Plane publishes two different things:

- a PLANE readiness manifest (`sapi-output-plane-manifest-v1`, src/output/readiness.py),
  fingerprinted over the manifest minus `manifest_fingerprint` with ensure_ascii=False;
- one accepted-run ARTIFACT per accepted score (`sapi-accepted-run-v1`,
  src/output/accepted_run.py).

The Operations consumer (src/ops/attempt2_operator/output_plane_manifest.py) expects a
PER-RUN output acceptance record: `schema_version` 1, `output_contract_version`,
`accepted_score_artifact_path` / `_sha256` and its own fingerprint recipe. No producer
emitted that record, so the real plane manifest was (correctly) rejected.

This module builds that record from the two real Output artifacts after verifying both
with their producer recipes, and computes the record fingerprint with the Operations
consumer's own function, so neither frozen plane changes. The record binds the plane
manifest fingerprint, the Output code identity, the accepted-run artifact fingerprint,
inputs_fingerprint and notification identity. It is evidence, never authorization.

    python -m src.convergence.output_acceptance build
        --output-manifest <OUTPUT_PLANE_MANIFEST.json>
        --accepted-run <accepted-run.json> --expect-output-fingerprint <fp> --out <DIR>
        [--expect-artifact-fingerprint <fp>]
    python -m src.convergence.output_acceptance verify <DIR>/OUTPUT-PLANE-MANIFEST.json
        --output-manifest <...> --expect-output-fingerprint <fp>
        [--expect-artifact-fingerprint <fp>]

Exit: 0 PASS · 2 usage / unsafe destination / existing different record · 3 rejected.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Optional

from src.notifications.alert_payload import SCHEMA_VERSION as ALERT_SCHEMA_VERSION
from src.ops.attempt2_operator.output_plane_manifest import (
    OUTPUT_PLANE_MANIFEST_FILENAME,
    compute_output_manifest_fingerprint,
    verify_output_plane_manifest,
)
from src.output import accepted_run as ar
from src.output import readiness as output_readiness
from src.output.contract import OUTPUT_SCHEMA_VERSION

OUTPUT_PLANE_MANIFEST_SCHEMA = output_readiness.MANIFEST_SCHEMA_VERSION
ACCEPTANCE_RECORD_VERSION = "sapi-output-acceptance-record-v1"
EXIT_PASS, EXIT_USAGE, EXIT_REJECTED = 0, 2, 3

_HEX64 = re.compile(r"[0-9a-f]{64}")
_HEX40 = re.compile(r"[0-9a-f]{40}")
_PLANE_KEYS = {
    "manifest_schema_version",
    "output_code",
    "bridge_contract_version",
    "control_center",
    "alert_schema_version",
    "notification_identity_recipe",
    "suppression_policy_version",
    "replay_artifact_schema_version",
    "readiness",
    "authorization",
    "manifest_fingerprint",
}
_RECORD_KEYS = {
    "schema_version",
    "output_contract_version",
    "accepted_score_artifact_path",
    "accepted_score_artifact_sha256",
    "presentation_contract_status",
    "acceptance_record_version",
    "output_plane_manifest_fingerprint",
    "output_plane_manifest_sha256",
    "output_code_git_head",
    "accepted_run_artifact_fingerprint",
    "inputs_fingerprint",
    "notification_identity",
    "data_origin",
    "scoring_time",
    "authorization",
    "manifest_fingerprint",
}


def output_plane_fingerprint(manifest: Mapping[str, Any]) -> str:
    """Producer recipe of src/output/readiness.build_manifest (parity-tested)."""
    body = {k: v for k, v in manifest.items() if k != "manifest_fingerprint"}
    canonical = json.dumps(
        body, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_output_plane(
    path: Path | str,
    *,
    expected_fingerprint: Optional[str],
    require_current_sources: bool = True,
) -> tuple[list[str], Optional[dict]]:
    """(rejection reasons, manifest). The anchor is mandatory for acceptance use."""
    try:
        manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return ["output_manifest_unreadable"], None
    if not isinstance(manifest, dict):
        return ["output_manifest_not_object"], None
    reasons: list[str] = []
    if set(manifest) != _PLANE_KEYS:
        reasons.append("output_manifest_fields_mismatch")
    if manifest.get("manifest_schema_version") != OUTPUT_PLANE_MANIFEST_SCHEMA:
        reasons.append("output_manifest_schema_unsupported")
    declared = manifest.get("manifest_fingerprint")
    if not (isinstance(declared, str) and _HEX64.fullmatch(declared)):
        return sorted(set(reasons + ["output_manifest_fingerprint_malformed"])), None
    try:
        if output_plane_fingerprint(manifest) != declared:
            reasons.append("output_manifest_fingerprint_mismatch")
    except (TypeError, ValueError):
        reasons.append("output_manifest_not_canonical")
    if expected_fingerprint is None:
        reasons.append("output_manifest_anchor_missing")
    elif declared != expected_fingerprint:
        reasons.append("output_manifest_fingerprint_not_expected")
    expected_values = {
        "bridge_contract_version": OUTPUT_SCHEMA_VERSION,
        "alert_schema_version": ALERT_SCHEMA_VERSION,
        "notification_identity_recipe": f"{ALERT_SCHEMA_VERSION}/alert_fingerprint",
        "replay_artifact_schema_version": ar.ARTIFACT_SCHEMA_VERSION,
    }
    for key, value in expected_values.items():
        if manifest.get(key) != value:
            reasons.append(f"output_manifest_{key}_mismatch")
    readiness = manifest.get("readiness")
    if not (
        isinstance(readiness, dict)
        and readiness.get("status") == output_readiness.READY
        and isinstance(readiness.get("checks"), list)
        and readiness["checks"]
        and all(
            isinstance(c, dict) and c.get("status") == output_readiness.PASS
            for c in readiness["checks"]
        )
    ):
        reasons.append("output_plane_not_ready")
    if not str(manifest.get("authorization", "")).startswith("NONE"):
        reasons.append("output_manifest_claims_authorization")
    code = manifest.get("output_code")
    if not (
        isinstance(code, dict)
        and isinstance(code.get("git_head"), str)
        and _HEX40.fullmatch(code["git_head"])
        and code.get("output_sources_clean") is True
        and isinstance(code.get("sources_sha256"), str)
        and isinstance(code.get("sources"), list)
    ):
        reasons.append("output_code_identity_invalid")
    elif require_current_sources:
        try:
            current = output_readiness.sources_sha256(tuple(code["sources"]))
        except (OSError, TypeError, ValueError):
            current = None
        if current != code["sources_sha256"]:
            reasons.append("output_sources_differ_from_this_candidate")
    return sorted(set(reasons)), manifest


def build_acceptance_record(
    output_manifest_path: Path | str,
    accepted_run_path: Path | str,
    *,
    expected_output_fingerprint: str,
    expected_artifact_fingerprint: Optional[str] = None,
) -> dict:
    """Both Output artifacts verified → record in the Operations consumer contract."""
    reasons, manifest = verify_output_plane(
        output_manifest_path, expected_fingerprint=expected_output_fingerprint
    )
    run_path = Path(accepted_run_path).resolve()
    run_view = ar.load_replay(run_path, expected_artifact_fingerprint)
    if run_view.state != ar.sc.REPLAY_READY:
        reasons += [f"accepted_run:{r}" for r in run_view.reasons]
    if reasons or manifest is None:
        raise ar.ArtifactError(sorted(set(reasons)))
    doc = json.loads(run_path.read_text(encoding="utf-8"))
    record = {
        "schema_version": 1,
        "output_contract_version": manifest["bridge_contract_version"],
        "accepted_score_artifact_path": str(run_path),
        "accepted_score_artifact_sha256": _sha256_file(run_path),
        "presentation_contract_status": "VERIFIED",
        "acceptance_record_version": ACCEPTANCE_RECORD_VERSION,
        "output_plane_manifest_fingerprint": manifest["manifest_fingerprint"],
        "output_plane_manifest_sha256": _sha256_file(Path(output_manifest_path)),
        "output_code_git_head": manifest["output_code"]["git_head"],
        "accepted_run_artifact_fingerprint": doc["artifact_fingerprint"],
        "inputs_fingerprint": run_view.inputs_fingerprint,
        "notification_identity": run_view.alert.fingerprint,
        "data_origin": run_view.data_origin,
        "scoring_time": run_view.scoring_time,
        "authorization": "NONE: acceptance evidence, not authorization",
    }
    record["manifest_fingerprint"] = compute_output_manifest_fingerprint(record)
    return record


def verify_acceptance_record(
    record_path: Path | str,
    *,
    output_manifest_path: Path | str,
    expected_output_fingerprint: str,
    expected_artifact_fingerprint: Optional[str] = None,
) -> list[str]:
    """Operations consumer PASS + every bound identity re-derived from the real files."""
    consumer = verify_output_plane_manifest(record_path)
    reasons = [f"operations:{f['code']}" for f in consumer.get("findings", [])]
    if consumer.get("status") != "PASS":
        reasons.append("operations_consumer_not_pass")
    try:
        record = json.loads(Path(record_path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return sorted(set(reasons + ["record_unreadable"]))
    if not isinstance(record, dict) or set(record) != _RECORD_KEYS:
        return sorted(set(reasons + ["record_fields_mismatch"]))
    if record.get("acceptance_record_version") != ACCEPTANCE_RECORD_VERSION:
        reasons.append("record_version_unsupported")
    try:
        expected = build_acceptance_record(
            output_manifest_path,
            record["accepted_score_artifact_path"],
            expected_output_fingerprint=expected_output_fingerprint,
            expected_artifact_fingerprint=expected_artifact_fingerprint,
        )
    except ar.ArtifactError as exc:
        return sorted(set(reasons + exc.reasons))
    for key in _RECORD_KEYS - {"manifest_fingerprint"}:
        if record.get(key) != expected.get(key):
            reasons.append(f"record_{key}_mismatch")
    if record.get("manifest_fingerprint") != compute_output_manifest_fingerprint(
        record
    ):
        reasons.append("record_fingerprint_mismatch")
    return sorted(set(reasons))


def write_record(record: Mapping, out_dir: Path) -> tuple[Path, str]:
    reason = ar.unsafe_output_dir(out_dir)
    if reason:
        raise PermissionError(reason)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / OUTPUT_PLANE_MANIFEST_FILENAME
    data = (
        json.dumps(record, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    ).encode()
    if path.exists():
        if path.read_bytes() == data:
            return path, "unchanged"
        raise FileExistsError(str(path))
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_bytes(data)
    tmp.replace(path)
    return path, "written"


def _print(obj: Mapping) -> None:
    print(json.dumps(obj, ensure_ascii=True, indent=2, sort_keys=True))


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m src.convergence.output_acceptance")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("build", "verify"):
        cmd = sub.add_parser(name)
        if name == "verify":
            cmd.add_argument("record", type=Path)
        cmd.add_argument("--output-manifest", type=Path, required=True)
        cmd.add_argument("--expect-output-fingerprint", required=True)
        cmd.add_argument("--expect-artifact-fingerprint")
        if name == "build":
            cmd.add_argument("--accepted-run", type=Path, required=True)
            cmd.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "verify":
        reasons = verify_acceptance_record(
            args.record,
            output_manifest_path=args.output_manifest,
            expected_output_fingerprint=args.expect_output_fingerprint,
            expected_artifact_fingerprint=args.expect_artifact_fingerprint,
        )
        _print({"result": "REJECTED" if reasons else "PASS", "reasons": reasons})
        return EXIT_REJECTED if reasons else EXIT_PASS
    reason = ar.unsafe_output_dir(args.out)
    if reason:
        _print({"result": "REFUSED", "reason": reason})
        return EXIT_USAGE
    try:
        record = build_acceptance_record(
            args.output_manifest,
            args.accepted_run,
            expected_output_fingerprint=args.expect_output_fingerprint,
            expected_artifact_fingerprint=args.expect_artifact_fingerprint,
        )
        path, status = write_record(record, args.out)
    except ar.ArtifactError as exc:
        _print({"result": "REJECTED", "reasons": exc.reasons})
        return EXIT_REJECTED
    except (PermissionError, FileExistsError) as exc:
        _print({"result": "REFUSED", "reason": str(exc)})
        return EXIT_USAGE
    _print(
        {
            "result": "BUILT",
            "write": status,
            "path": str(path),
            "manifest_fingerprint": record["manifest_fingerprint"],
        }
    )
    return EXIT_PASS


if __name__ == "__main__":
    sys.exit(main())

"""Data → Operations handshake (convergence-owned; tracks RC1 BLOCKER 1).

The Data Plane producer (src/ops/data_readiness.py) publishes a NESTED manifest:
top-level `schema_version`, `created_at`, `identity` (the stable subtree), `fingerprint`
= sha256(canonical(identity)) with sort_keys, compact separators, ensure_ascii=True and
allow_nan=False, plus volatile `operational_roots` / `observation`. Its readiness value is
`identity.data_readiness_status` (PREPARED / NOT_PREPARED / INCOMPLETE) and every
`identity.authorizations` entry is false.

The Operations consumer at 848272f (src/ops/attempt2_operator/data_plane_manifest.py)
reads a FLAT manifest instead and rejects the real one. Antigravity owns the adapter;
this module only observes and classifies. The lanes lock (config/rc1_convergence_lanes.json)
says whether the adapter has landed, so the expected consumer verdict flips from
EXPECTED_REJECT to ACCEPTED only through an explicit, reviewed lock change.

    python -m src.convergence.data_handshake <DATA_PLANE_MANIFEST.json> [--json]

Exit: 0 verdict matches the landing state · 3 anything else · 2 usage.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Optional

from src.ops import data_readiness as producer
from src.ops.attempt2_operator.data_plane_manifest import verify_data_plane_manifest

LANES_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "rc1_convergence_lanes.json"
)
CONSUMER_PATH = (
    "src.ops.attempt2_operator.data_plane_manifest.verify_data_plane_manifest"
)
AUTHORIZATION_NAMES = ("attempt2", "writers", "telegram", "schedule")
EXIT_OK, EXIT_USAGE, EXIT_MISMATCH = 0, 2, 3

EXPECTED_REJECT = "EXPECTED_REJECT"
ACCEPTED = "ACCEPTED"
UNEXPECTED_ACCEPT = "UNEXPECTED_ACCEPT"
UNEXPECTED_REJECT = "UNEXPECTED_REJECT"
CONTRACT_VIOLATION = "CONTRACT_VIOLATION"
PRODUCER_REJECT = "PRODUCER_REJECT"
_OK = {False: EXPECTED_REJECT, True: ACCEPTED}


def load_lanes(path: Path | str = LANES_PATH) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def adapter_landed(lanes: Mapping) -> bool:
    return lanes["operations"]["adapter_sha"] is not None


def producer_fingerprint(manifest: Mapping) -> str:
    """The producer recipe itself, not a re-implementation."""
    return producer.digest(producer.canonical(manifest["identity"]))


def pin_mismatches(manifest: Mapping, lanes: Mapping) -> list[str]:
    """Producer integrity is not identity: a re-signed tamper passes verify_manifest."""
    data = lanes["data"]
    try:
        ident = manifest["identity"]
        observed = {
            "fingerprint": manifest["fingerprint"],
            "schema_version": manifest["schema_version"],
            "identity.schema_version": ident["schema_version"],
            "identity.code_identity.sha": ident["code_identity"]["sha"],
            "identity.components.firms.sha": ident["components"]["firms"]["sha"],
            "identity.components.dmc.sha": ident["components"]["dmc"]["sha"],
            "identity.model.sha256": ident["model"]["sha256"],
            "identity.baseline.sha256": ident["baseline"]["sha256"],
            "identity.data_readiness_status": ident["data_readiness_status"],
            "identity.authorizations": ident["authorizations"],
        }
    except (KeyError, TypeError):
        return ["identity_structure_invalid"]
    expected = {
        "fingerprint": data["manifest_fingerprint"],
        "schema_version": 1,
        "identity.schema_version": 1,
        "identity.code_identity.sha": data["sha"],
        "identity.components.firms.sha": data["firms_component_sha"],
        "identity.components.dmc.sha": data["dmc_component_sha"],
        "identity.model.sha256": data["model_sha256"],
        "identity.baseline.sha256": data["baseline_sha256"],
        "identity.data_readiness_status": "PREPARED",
        "identity.authorizations": {name: False for name in AUTHORIZATION_NAMES},
    }
    return sorted(f"pin:{k}" for k in expected if observed[k] != expected[k])


def adapter_contract_violations(
    verdict: Mapping, manifest: Mapping, lanes: Mapping
) -> list[str]:
    """What the landed adapter must report for the real manifest (ADAPTER_CONTRACT.json)."""
    ident = manifest["identity"]
    data = lanes["data"]
    expected = {
        "status": "PASS",
        "ready": True,
        "manifest_fingerprint": producer_fingerprint(manifest),
        "readiness_status": "PREPARED",
        "data_code_sha": data["sha"],
        "firms_component_sha": data["firms_component_sha"],
        "dmc_component_sha": data["dmc_component_sha"],
        "model_sha": data["model_sha256"],
        "baseline_identity": data["baseline_sha256"],
        "authorizations": {name: False for name in AUTHORIZATION_NAMES},
    }
    out = [f"contract:{k}" for k, v in expected.items() if verdict.get(k) != v]
    if ident["data_readiness_status"] != "PREPARED":
        out.append("contract:real_manifest_not_prepared")
    # PREPARED is data readiness, never a human or writer authorization.
    for key, value in verdict.items():
        if "authoriz" in key.lower() and key != "authorizations" and value:
            out.append(f"contract:authorization_promoted:{key}")
    return sorted(out)


def classify(
    manifest_path: Path | str,
    *,
    lanes: Optional[Mapping] = None,
    expected_code_sha: Optional[str] = None,
) -> dict[str, Any]:
    lanes = lanes or load_lanes()
    landed = adapter_landed(lanes)
    try:
        raw = json.loads(Path(manifest_path).read_bytes())
    except (OSError, UnicodeDecodeError, ValueError):
        raw = None
    if not isinstance(raw, dict):
        raw = {}  # malformed input: producer and pins both fail closed below
    producer_ok = producer.verify_manifest(copy.deepcopy(raw))
    pins = pin_mismatches(raw, lanes)
    try:
        verdict = verify_data_plane_manifest(
            manifest_path, expected_code_sha=expected_code_sha
        )
    except Exception as exc:  # consumer crash is a rejection, recorded, never a PASS
        verdict = {
            "status": "ERROR",
            "ready": False,
            "findings": [{"id": "CONSUMER_EXCEPTION", "code": type(exc).__name__}],
        }
    accepted = verdict.get("status") == "PASS"
    violations: list[str] = []
    if not producer_ok or pins:
        # Producer-invalid or unpinned content must never reach the consumer as PASS.
        classification = UNEXPECTED_ACCEPT if accepted else PRODUCER_REJECT
    elif accepted and not landed:
        classification = UNEXPECTED_ACCEPT
    elif not accepted and landed:
        classification = UNEXPECTED_REJECT
    elif accepted:
        violations = adapter_contract_violations(verdict, raw, lanes)
        classification = CONTRACT_VIOLATION if violations else ACCEPTED
    else:
        classification = EXPECTED_REJECT
    return {
        "adapter_landed": landed,
        "adapter_sha": lanes["operations"]["adapter_sha"],
        "producer": {
            "verify_manifest": "PASS" if producer_ok else "FAIL",
            "fingerprint_declared": raw.get("fingerprint"),
            "fingerprint_recomputed": _safe_fp(raw),
            "pins": pins or "MATCH",
        },
        "consumer": {
            "path": CONSUMER_PATH,
            "status": verdict.get("status"),
            "ready": verdict.get("ready"),
            "findings": [
                f"{f.get('id')}:{f.get('code')}" for f in verdict.get("findings", [])
            ],
            "manifest_fingerprint_reported": verdict.get("manifest_fingerprint"),
            "readiness_status_reported": verdict.get("readiness_status"),
        },
        "contract_violations": violations,
        "classification": classification,
        "expected_classification": _OK[landed],
        "match": classification == _OK[landed] and producer_ok and not pins,
    }


def _safe_fp(raw: Mapping) -> Optional[str]:
    try:
        return producer_fingerprint(raw)
    except (KeyError, TypeError, ValueError):
        return None


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m src.convergence.data_handshake")
    parser.add_argument("manifest")
    parser.add_argument("--expected-code-sha", default=None)
    args = parser.parse_args(argv)
    if not Path(args.manifest).is_file():
        print(json.dumps({"result": "REFUSED", "reason": "manifest_not_found"}))
        return EXIT_USAGE
    result = classify(args.manifest, expected_code_sha=args.expected_code_sha)
    print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))
    return EXIT_OK if result["match"] else EXIT_MISMATCH


if __name__ == "__main__":
    sys.exit(main())

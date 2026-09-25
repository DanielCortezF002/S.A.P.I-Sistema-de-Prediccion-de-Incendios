"""Local artifact identity checks — missing → NOT_AVAILABLE / INCOMPLETE, never PASS."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MODEL_SHA_EXPECTED = (
    "ac017bef1f42a30ac74ba3e3787368c4418798b2d562adcfba01c923cff2173f"
)
FIRMS_BASELINE_SHA_EXPECTED = (
    "a9a85db4431b3e54f936b724e4de5a7fbb0cc19f5721f5e1a344a192bf9bb271"
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_file(path: Path) -> str | None:
    try:
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _check_file(path: Path, expected: str) -> dict[str, Any]:
    if not path.exists():
        return {
            "path": str(path),
            "exists": False,
            "expected_sha256": expected,
            "observed_sha256": None,
            "match": False,
            "status": "NOT_AVAILABLE",
        }
    observed = _sha256_file(path)
    if observed is None:
        return {
            "path": str(path),
            "exists": True,
            "expected_sha256": expected,
            "observed_sha256": None,
            "match": False,
            "status": "INCOMPLETE",
        }
    match = observed.lower() == expected.lower()
    return {
        "path": str(path),
        "exists": True,
        "expected_sha256": expected,
        "observed_sha256": observed,
        "match": match,
        "status": "PASS" if match else "FAIL",
    }


def collect_artifact_identities(repo: Path) -> dict[str, Any]:
    repo = Path(repo)
    model = _check_file(repo / "models" / "prototype_model_d.pkl", MODEL_SHA_EXPECTED)
    # baseline path from project convention
    try:
        from src.procesamiento.firms_source import FIRMS_BASELINE_CSV, FIRMS_BASELINE_SHA256

        baseline_path = FIRMS_BASELINE_CSV
        expected = FIRMS_BASELINE_SHA256
    except Exception:  # noqa: BLE001
        baseline_path = (
            repo
            / "data"
            / "processed"
            / "firms"
            / "nasa_firms_baseline.csv"
        )
        expected = FIRMS_BASELINE_SHA_EXPECTED
        # also try under common path
        alt = list((repo / "data").rglob("*baseline*.csv")) if (repo / "data").exists() else []
        if not baseline_path.exists() and alt:
            baseline_path = alt[0]

    # Prefer constant expected from task if import fails path discovery
    if expected != FIRMS_BASELINE_SHA_EXPECTED:
        # still verify against project constant; surface both
        pass
    baseline = _check_file(Path(baseline_path), FIRMS_BASELINE_SHA_EXPECTED)

    statuses = [model["status"], baseline["status"]]
    if any(s == "FAIL" for s in statuses):
        overall = "FAIL"
    elif any(s in ("NOT_AVAILABLE", "INCOMPLETE") for s in statuses):
        overall = "INCOMPLETE"
    else:
        overall = "PASS"

    return {
        "model": model,
        "firms_baseline": baseline,
        "overall_status": overall,
        "observed_at": _utc_now(),
        "note": "Missing artifact is NOT_AVAILABLE/INCOMPLETE — never PASS",
    }

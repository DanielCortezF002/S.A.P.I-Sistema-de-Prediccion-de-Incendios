"""Local artifact identity checks — missing → NOT_AVAILABLE, never PASS."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.ops.attempt2_operator.paths import StoreRoots

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
            "discovery": "explicit_path",
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
            "discovery": "explicit_path",
        }
    match = observed.lower() == expected.lower()
    return {
        "path": str(path),
        "exists": True,
        "expected_sha256": expected,
        "observed_sha256": observed,
        "match": match,
        "status": "PASS" if match else "FAIL",
        "discovery": "explicit_path",
    }


def resolve_firms_baseline_path(
    roots: StoreRoots,
    *,
    explicit: Path | None = None,
) -> tuple[Path | None, list[str]]:
    """Return first existing deterministic candidate (or None)."""
    tried: list[str] = []
    candidates = [explicit] if explicit else []
    candidates.extend(roots.firms_baseline_candidates())
    for p in candidates:
        if p is None:
            continue
        tried.append(str(p))
        if p.is_file():
            return p, tried
    return None, tried


def collect_artifact_identities(
    repo: Path,
    *,
    data_root: Path | None = None,
    models_root: Path | None = None,
    firms_baseline_path: Path | None = None,
    model_path: Path | None = None,
) -> dict[str, Any]:
    roots = StoreRoots.from_repo(repo, data_root=data_root, models_root=models_root)

    # Model — explicit deterministic path
    mpath = Path(model_path) if model_path else roots.model_path()
    model = _check_file(mpath, MODEL_SHA_EXPECTED)

    # Baseline — project contract path (firms_source.FIRMS_BASELINE_CSV layout)
    expected_baseline = FIRMS_BASELINE_SHA_EXPECTED
    try:
        from src.procesamiento.firms_source import FIRMS_BASELINE_SHA256

        expected_baseline = FIRMS_BASELINE_SHA256
    except Exception:  # noqa: BLE001
        pass

    found, tried = resolve_firms_baseline_path(roots, explicit=firms_baseline_path)
    if found is None:
        baseline = {
            "path": tried[0] if tried else str(roots.code_root / "data/processed"),
            "exists": False,
            "expected_sha256": expected_baseline,
            "observed_sha256": None,
            "match": False,
            "status": "NOT_AVAILABLE",
            "discovery": "explicit_candidates",
            "candidates_tried": tried,
        }
    else:
        baseline = _check_file(found, expected_baseline)
        baseline["candidates_tried"] = tried
        baseline["discovery"] = "explicit_candidates"

    statuses = [model["status"], baseline["status"]]
    if any(s == "FAIL" for s in statuses):
        overall = "FAIL"
    elif any(s == "NOT_AVAILABLE" for s in statuses):
        overall = "NOT_AVAILABLE"
    elif any(s == "INCOMPLETE" for s in statuses):
        overall = "INCOMPLETE"
    else:
        overall = "PASS"

    return {
        "model": model,
        "firms_baseline": baseline,
        "overall_status": overall,
        "roots": {
            "code_root": str(roots.code_root),
            "data_root": str(roots.data_root),
            "models_root": str(roots.models_root),
        },
        "observed_at": _utc_now(),
        "note": "Missing artifact is NOT_AVAILABLE — never PASS. No whole-store crawl.",
    }

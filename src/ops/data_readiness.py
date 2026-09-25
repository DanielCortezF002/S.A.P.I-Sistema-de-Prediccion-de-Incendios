"""Read-only RC1 preparation evidence. No network, writers, inference or authorization."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess

import pandas as pd

from src.geo.grid import all_cells
from src.inference.scoring_inputs import pin_dmc, topography_sha256
from src.ops.dmc_live_probe import sanitized
from src.procesamiento.dem_features import load_grid_topography
from src.procesamiento.firms_source import resolve_firms_source
from src.refresh import dmc_refresh as dmc
from src.refresh.firms_refresh import FirmsPaths
from src.refresh.firms_validation import validate_publication

CODE_ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = CODE_ROOT / "config/data_plane_rc1.json"
SECRET_NAMES = ("NASA_FIRMS_API_KEY", "DMC_USUARIO", "DMC_TOKEN")


def canonical(value) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def relative(root: Path, name: str) -> Path:
    if not isinstance(name, str) or Path(name).is_absolute() or ":" in name:
        raise ValueError("Invalid policy path")
    result = (root / name).resolve()
    if not result.is_relative_to(root.resolve()):
        raise ValueError("Policy path escapes root")
    return result


def identity(path: Path, expected: str) -> dict:
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return {"status": "MISSING"}
    except OSError:
        return {"status": "UNKNOWN"}
    actual = digest(raw)
    return {
        "status": "PASS" if actual == expected else "FAIL",
        "sha256": actual,
        "expected_sha256": expected,
        "size": len(raw),
    }


def code_identity(root: Path, components: dict) -> dict:
    def git(*args):
        return (
            subprocess.check_output(
                ["git", "-C", str(root), *args], stderr=subprocess.DEVNULL, timeout=15
            )
            .decode()
            .strip()
        )

    try:
        result = {
            "sha": git("rev-parse", "HEAD"),
            "tree": git("rev-parse", "HEAD^{tree}"),
            "clean": not bool(git("status", "--porcelain", "--untracked-files=normal")),
            "components": {},
        }
        for name, component in components.items():
            sha = component["sha"]
            git("merge-base", "--is-ancestor", sha, "HEAD")
            same = all(
                git("rev-parse", f"HEAD:{file}") == git("rev-parse", f"{sha}:{file}")
                for file in component["files"]
            )
            result["components"][name] = {
                "sha": sha,
                "status": "PASS" if same else "FAIL",
            }
        result["status"] = (
            "PASS"
            if result["clean"]
            and all(c["status"] == "PASS" for c in result["components"].values())
            else "FAIL"
        )
        return result
    except (OSError, ValueError, subprocess.SubprocessError):
        return {"status": "UNKNOWN"}


def inventory(root: Path, directories: list[str]) -> dict:
    records = {}
    for directory in directories:
        base = relative(root, directory)
        if not base.is_dir():
            raise FileNotFoundError("Store root missing")
        for path in sorted(base.rglob("*")):
            if path.is_file():
                if not path.resolve().is_relative_to(root.resolve()):
                    raise ValueError("Store reference escapes workspace")
                records[path.relative_to(root).as_posix()] = digest(path.read_bytes())
    return {"files": len(records), "sha256": digest(canonical(records))}


def current_firms(root: Path, policy: dict) -> dict:
    store = relative(root, policy["stores"]["firms"])
    paths = FirmsPaths(
        pointer=store / "CURRENT.json",
        versions_dir=store / "versions",
        raw_dir=relative(root, policy["stores"]["firms_raw"]),
        baseline_csv=relative(root, policy["baseline"]["path"]),
        baseline_sha256=policy["baseline"]["sha256"],
    )
    try:
        if paths.lock.exists():
            return {"state": "UNKNOWN", "reason": "LOCK_PRESENT"}
        try:
            before = paths.pointer.read_bytes()
        except FileNotFoundError:
            return {"state": "ABSENT", "pointer_valid": None}
        source = resolve_firms_source(
            reproducibility=False,
            pointer_path=paths.pointer,
            versions_dir=paths.versions_dir,
            baseline_csv=paths.baseline_csv,
        )
        validated = validate_publication(paths)
        if before != paths.pointer.read_bytes():
            return {"state": "UNKNOWN", "reason": "CHANGED_DURING_READ"}
        return {
            "state": "PRESENT",
            "pointer_valid": True,
            "sha256": source.sha256,
            "pointer_sha256": digest(before),
            "coverage_start": source.coverage_start.isoformat(),
            "coverage_end": source.coverage_end.isoformat(),
            "rows": validated["row_count"],
        }
    except PermissionError:
        return {"state": "UNKNOWN", "reason": "UNREADABLE"}
    except Exception:
        return {"state": "INVALID", "pointer_valid": False}


def current_dmc(root: Path, policy: dict) -> dict:
    paths = dmc.DmcPaths(
        root=relative(root, policy["stores"]["dmc"]), station_id=policy["station"]
    )
    try:
        if paths.lock.exists():
            return {"state": "UNKNOWN", "reason": "LOCK_PRESENT"}
        try:
            before = paths.pointer.read_bytes()
        except FileNotFoundError:
            return {"state": "ABSENT", "pointer_valid": None}
        pointer = dmc._verify_pointer(paths, json.loads(before))
        count, starts, ends = 0, [], []
        for month, entry in sorted(pointer["months"].items()):
            raw = dmc._safe_version_path(paths, entry["relative_path"]).read_bytes()
            payload = json.loads(raw)[paths.station_id]
            prepared = dmc.prepare_month_payload(payload, paths.station_id, month)
            valid = prepared.valid
            if (
                digest(raw) != entry["sha256"]
                or len(valid) != entry["record_count"]
                or valid[0]["momento"] != entry["first_momento"]
                or valid[-1]["momento"] != entry["last_momento"]
            ):
                raise ValueError("Monthly metadata inconsistent")
            count += len(valid)
            starts.append(valid[0]["momento"])
            ends.append(valid[-1]["momento"])
        if (
            count != pointer["record_count"]
            or min(starts) != pointer["coverage_start"]
            or max(ends) != pointer["coverage_end"]
        ):
            raise ValueError("Coverage inconsistent")
        pinned = pin_dmc(
            paths.station_id,
            legacy_dir=relative(root, policy["stores"]["legacy_dmc"]),
            store_dir=paths.root,
        )
        if (
            not pinned.files
            or pinned.series.empty
            or before != paths.pointer.read_bytes()
        ):
            raise ValueError("No usable pinned DMC or concurrent mutation")
        return {
            "state": "PRESENT",
            "pointer_valid": True,
            "pointer_sha256": digest(before),
            "manifest_sha256": pointer["manifest_sha256"],
            "rows": count,
            "coverage_start": pointer["coverage_start"],
            "coverage_end": pointer["coverage_end"],
        }
    except PermissionError:
        return {"state": "UNKNOWN", "reason": "UNREADABLE"}
    except Exception:
        return {"state": "INVALID", "pointer_valid": False}


def topography(root: Path, policy: dict) -> dict:
    expected = policy["topography"]
    files = {
        name: identity(relative(root, name), sha)
        for name, sha in expected["files"].items()
    }
    if not files or any(
        item["status"] in ("MISSING", "UNKNOWN") for item in files.values()
    ):
        return {"status": "UNKNOWN", "files": files}
    if any(item["status"] != "PASS" for item in files.values()):
        return {"status": "FAIL", "files": files}
    grid = all_cells()
    grid_sha = digest(canonical(grid))
    if grid_sha != expected["grid_sha256"]:
        return {"status": "FAIL", "reason": "GRID_MISMATCH", "grid_sha256": grid_sha}
    if expected["mode"] == "dem":
        directory = relative(root, expected["directory"])
        selected = [
            sorted(directory.glob(pattern))[0]
            for pattern in ("*_utm19s.tif", "*_slope.tif", "*_aspect.tif")
        ]
        if {p.relative_to(root).as_posix() for p in selected} != set(files):
            raise ValueError("Scoring would select different rasters")
        table = load_grid_topography(grid, directory).set_index("cell_id")
    elif expected["mode"] == "frozen_table":
        table = pd.read_csv(
            io.BytesIO(relative(root, expected["table"]).read_bytes())
        ).set_index("cell_id")
    else:
        return {"status": "UNKNOWN"}
    actual = topography_sha256(table)
    return {
        "status": "PASS" if actual == expected["table_sha256"] else "FAIL",
        "origin": expected["mode"],
        "files": files,
        "grid_sha256": grid_sha,
        "table_sha256": actual,
        "cells": len(table),
        "missing_value_cells": int(table.isna().any(axis=1).sum()),
    }


def source_evidence(path: Path | None, policy: dict) -> dict:
    if path is None:
        return {"status": "UNKNOWN", "reason": "EVIDENCE_NOT_SUPPLIED"}
    expected = policy["dmc_evidence"]
    raw = path.read_bytes()
    actual = digest(raw)
    if actual != expected["sha256"]:
        return {"status": "UNKNOWN", "reason": "EVIDENCE_MISSING_OR_HASH_MISMATCH"}
    data = json.loads(raw)
    if (
        data.get("schema_version") != 1
        or data.get("status") != "COMPATIBLE"
        or data.get("exit_code") != 0
        or data["evidence"]["commit"] != policy["components"]["dmc"]["sha"]
        or data["source"]["station"] != policy["station"]
        or data["dry_run"]["publication_performed"] is not False
    ):
        return {"status": "FAIL", "reason": "EVIDENCE_CONTRACT_INVALID"}
    observed = datetime.fromisoformat(data["observed_at"])
    if observed.tzinfo is None or observed > datetime.now(timezone.utc):
        return {"status": "UNKNOWN", "reason": "INVALID_OBSERVATION_TIME"}
    return {
        "status": "PASS",
        "sha256": actual,
        "source_compatible": True,
        "observed_at": observed.isoformat(),
        "coverage": data["coverage"],
        "records": data["records"]["received"],
        "null_percentage": data["records"]["null_percentage"],
        "scope": "previous monthly observation only; no current freshness claim",
    }


def evaluate(
    workspace: Path,
    *,
    evidence: Path | None = None,
    policy: dict | None = None,
    code_root: Path = CODE_ROOT,
) -> dict:
    """Evaluate a coherent read-only observation; failures never promote readiness."""
    policy = policy if policy is not None else json.loads(POLICY_PATH.read_bytes())
    workspace = workspace.resolve()
    result = {
        "schema_version": 1,
        "observed_at_start": now(),
        "status": "INCOMPLETE",
        "code_identity": {},
        "firms": {},
        "dmc": {},
        "model": {},
        "topography": {},
        "stores": {},
        "current_state": {},
        "findings": [],
        "data_ready_for_scoring": "NOT_EVALUATED",
        "independent_approval": "PENDING",
        "authorizations": {
            name: False for name in ("attempt2", "writers", "telegram", "schedule")
        },
        "credentials_present": {
            name: bool(os.environ.get(name)) for name in SECRET_NAMES
        },
    }

    def finding(code, level):
        result["findings"].append({"code": code, "level": level})

    def check(name, action):
        try:
            return action()
        except Exception:
            finding(name + "_UNREADABLE_OR_INVALID", "INCOMPLETE")
            return {"status": "UNKNOWN"}

    try:
        if policy["schema_version"] != 1 or not policy["components"]:
            raise ValueError("Unsupported policy")
        initial = check(
            "STORES", lambda: inventory(workspace, policy["inventory_roots"])
        )
        result["code_identity"] = check(
            "CODE", lambda: code_identity(code_root, policy["components"])
        )
        result["model"] = check(
            "MODEL",
            lambda: identity(
                relative(workspace, policy["model"]["path"]), policy["model"]["sha256"]
            ),
        )
        result["topography"] = check(
            "TOPOGRAPHY", lambda: topography(workspace, policy)
        )
        result["firms"] = {
            "implementation_sha": policy["components"]["firms"]["sha"],
            "baseline": check(
                "BASELINE",
                lambda: identity(
                    relative(workspace, policy["baseline"]["path"]),
                    policy["baseline"]["sha256"],
                ),
            ),
            "current": check("FIRMS_CURRENT", lambda: current_firms(workspace, policy)),
            "source_compatible": "NOT_REPROBED",
            "source_request_performed": False,
            "attempt1": check(
                "ATTEMPT1",
                lambda: {
                    name: identity(relative(workspace, name), sha)
                    for name, sha in policy["attempt1"].items()
                },
            ),
        }
        result["dmc"] = {
            "implementation_sha": policy["components"]["dmc"]["sha"],
            "current": check("DMC_CURRENT", lambda: current_dmc(workspace, policy)),
            "source_evidence": check(
                "DMC_EVIDENCE", lambda: source_evidence(evidence, policy)
            ),
        }
        for name, item in (
            ("CODE", result["code_identity"]),
            ("MODEL", result["model"]),
            ("TOPOGRAPHY", result["topography"]),
            ("BASELINE", result["firms"]["baseline"]),
            ("DMC_EVIDENCE", result["dmc"]["source_evidence"]),
        ):
            if item.get("status") != "PASS":
                finding(
                    name + "_NOT_VERIFIED",
                    "NOT_PREPARED" if item.get("status") == "FAIL" else "INCOMPLETE",
                )
        attempt = result["firms"]["attempt1"]
        if not isinstance(attempt, dict) or any(
            not isinstance(v, dict) or v.get("status") != "PASS"
            for v in attempt.values()
        ):
            finding("ATTEMPT1_NOT_VERIFIED", "INCOMPLETE")
        for component in ("firms", "dmc"):
            state = result[component]["current"].get("state", "UNKNOWN")
            expected = policy["expected_current"][component]
            result["current_state"][component] = state
            if expected not in ("ABSENT", "PRESENT") or state == "UNKNOWN":
                finding(component.upper() + "_CURRENT_UNKNOWN", "INCOMPLETE")
            elif state != expected:
                finding(component.upper() + "_CURRENT_UNEXPECTED", "NOT_PREPARED")
        final = check("STORES", lambda: inventory(workspace, policy["inventory_roots"]))
        result["stores"] = final
        if initial != final:
            finding("STORE_CHANGED_DURING_OBSERVATION", "INCOMPLETE")
        model_after = check(
            "MODEL",
            lambda: identity(
                relative(workspace, policy["model"]["path"]), policy["model"]["sha256"]
            ),
        )
        if model_after != result["model"]:
            finding("MODEL_CHANGED_DURING_OBSERVATION", "INCOMPLETE")
        levels = {f["level"] for f in result["findings"]}
        result["status"] = (
            "NOT_PREPARED"
            if "NOT_PREPARED" in levels
            else "INCOMPLETE" if levels else "PREPARED"
        )
    except Exception:
        finding("POLICY_OR_EVALUATION_INCOMPLETE", "INCOMPLETE")
        result["status"] = "INCOMPLETE"
    result["observed_at_end"] = now()
    return sanitized(result, tuple(os.environ.get(k, "") for k in SECRET_NAMES))


def build_manifest(
    result: dict, policy: dict, *, workspace: Path, created_at: str | None = None
) -> dict:
    """Stable identity excludes observation clocks and absolute operational roots."""
    stable = {
        "schema_version": 1,
        "kind": "DATA_PLANE_MANIFEST",
        "policy_sha256": digest(canonical(policy)),
        "components": policy["components"],
        "code_identity": result["code_identity"],
        "model": result["model"],
        "topography": result["topography"],
        "baseline": result["firms"].get("baseline"),
        "stores": result["stores"],
        "store_roots_policy": policy["stores"],
        "expected_current": policy["expected_current"],
        "current_state": result["current_state"],
        "firms_current": result["firms"].get("current"),
        "dmc_current": result["dmc"].get("current"),
        "source_evidence_sha256": result["dmc"]
        .get("source_evidence", {})
        .get("sha256"),
        "source_evidence": result["dmc"].get("source_evidence", {}),
        "attempt1": result["firms"].get("attempt1", {}),
        "findings": result["findings"],
        "data_readiness_status": result["status"],
        "data_ready_for_scoring": "NOT_EVALUATED",
        "independent_approval": "PENDING",
        "authorizations": result["authorizations"],
    }
    return {
        "schema_version": 1,
        "created_at": created_at or now(),
        "identity": stable,
        "fingerprint": digest(canonical(stable)),
        "operational_roots": {
            "workspace": str(workspace.resolve()),
            "code": str(CODE_ROOT),
        },
        "observation": {
            "start": result["observed_at_start"],
            "end": result["observed_at_end"],
        },
    }


def verify_manifest(manifest: dict) -> bool:
    """Integrity check only, never writer or operational authorization."""
    try:
        stable = manifest["identity"]
        if stable["data_readiness_status"] == "PREPARED":
            if (
                stable["findings"]
                or stable["current_state"] != stable["expected_current"]
                or set(stable["current_state"]) != {"firms", "dmc"}
                or any(
                    state not in ("ABSENT", "PRESENT")
                    for state in stable["current_state"].values()
                )
                or any(
                    stable[name].get("status") != "PASS"
                    for name in (
                        "model",
                        "topography",
                        "baseline",
                        "source_evidence",
                        "code_identity",
                    )
                )
            ):
                return False
        return (
            manifest["schema_version"] == stable["schema_version"] == 1
            and stable["kind"] == "DATA_PLANE_MANIFEST"
            and stable["data_readiness_status"]
            in ("PREPARED", "NOT_PREPARED", "INCOMPLETE")
            and stable["data_ready_for_scoring"] == "NOT_EVALUATED"
            and stable["independent_approval"] == "PENDING"
            and stable["authorizations"]
            == {name: False for name in ("attempt2", "writers", "telegram", "schedule")}
            and manifest["fingerprint"] == digest(canonical(stable))
        )
    except (AttributeError, KeyError, TypeError, ValueError):
        return False


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-root", type=Path, required=True)
    parser.add_argument("--dmc-evidence", type=Path)
    parser.add_argument(
        "--manifest",
        action="store_true",
        help="Print manifest instead of readiness result",
    )
    args = parser.parse_args(argv)
    try:
        policy = json.loads(POLICY_PATH.read_bytes())
        result = evaluate(
            args.workspace_root, evidence=args.dmc_evidence, policy=policy
        )
        output = (
            build_manifest(result, policy, workspace=args.workspace_root)
            if args.manifest
            else result
        )
        output = sanitized(output, tuple(os.environ.get(k, "") for k in SECRET_NAMES))
        print(json.dumps(output, sort_keys=True, indent=2, allow_nan=False))
        return {"PREPARED": 0, "NOT_PREPARED": 65, "INCOMPLETE": 78}[result["status"]]
    except Exception:
        print(
            json.dumps(
                {
                    "schema_version": 1,
                    "status": "INCOMPLETE",
                    "reason": "CONFIG_OR_EVALUATION_INVALID",
                }
            )
        )
        return 78


if __name__ == "__main__":
    raise SystemExit(main())

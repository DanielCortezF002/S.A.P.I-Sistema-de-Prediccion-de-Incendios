"""Attempt 2 evidence builders for `attempt2_operator import-result`.

- capture-bridge: ONE GET of the bridge /score → raw body, accepted-run artifact,
  bridge.json and scoring.json, all derived from that same body (a second GET differs
  in age_hours and would never bind to the artifact).
- writer-payload: FIRMS/DMC payload from a refresh the human already ran; every
  flag is computed from the published store, never defaulted to True.
- n8n-evidence: policy-level evidence for the manual n8n phase. The inactive preview
  workflow must equal ops/n8n/build_workflow.build(), and ops/n8n/policy.js is
  evaluated with Node on the captured body and on the three fail-closed envelopes.
  The n8n runtime is never executed.

Never runs writers, starts services, reads credentials or writes into stores.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.ops.attempt2_operator.collectors.dmc_current import (  # noqa: E402
    collect_dmc_current,
)
from src.ops.attempt2_operator.collectors.firms_current import (  # noqa: E402
    collect_firms_current,
)
from src.output import accepted_run as ar  # noqa: E402

EXIT_OK, EXIT_USAGE, EXIT_REJECTED, EXIT_NETWORK = 0, 2, 3, 4

MODEL_REL = Path("models") / "prototype_model_d.pkl"
DATA_PLANE_CONFIG_REL = Path("config") / "data_plane_rc1.json"
POLICY_REL = Path("ops") / "n8n" / "policy.js"
WORKFLOW_REL = Path("ops") / "n8n" / "controlled-preview.json"
BUILDER_REL = Path("ops") / "n8n" / "build_workflow.py"

FAIL_CLOSED_ENVELOPES = {
    "prototype_unavailable": (503, {"error_type": "prototype_unavailable"}),
    "data_unavailable": (503, {"error_type": "data_unavailable"}),
    "internal_error": (500, {"error_type": "internal_error"}),
}
SCORE_PATH_CATEGORIES = ("candidate", "withheld")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_new_json(path: Path, doc: Any) -> None:
    """Exclusive create: evidence is never overwritten."""
    data = json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with open(path, "x", encoding="utf-8") as fh:
        fh.write(data)


# --- capture-bridge ------------------------------------------------------------------


def pinned_model_sha(repo: Path) -> Optional[str]:
    try:
        cfg = json.loads((repo / DATA_PLANE_CONFIG_REL).read_text(encoding="utf-8"))
        return str(cfg["model"]["sha256"]).lower()
    except (OSError, ValueError, KeyError, TypeError):
        return None


def capture_bridge(
    url: str,
    out_dir: Path,
    *,
    repo: Path = REPO_ROOT,
    session=None,
    timeout: tuple[float, float] = (3.0, 90.0),
) -> dict:
    """One GET → four files from the same body. Raises before writing anything
    if the response is not an accepted run or the model is not the pinned one."""
    reason = ar.unsafe_output_dir(out_dir)
    if reason:
        raise PermissionError(reason)
    model = repo / MODEL_REL
    if not model.is_file():
        raise ar.ArtifactError(["model_missing"])
    model_sha = _sha256_file(model)
    pinned = pinned_model_sha(repo)
    if pinned is None or model_sha != pinned:
        raise ar.ArtifactError(["model_sha_not_pinned"])

    import requests

    http = session or requests
    try:
        response = http.get(
            url,
            timeout=timeout,
            headers={"Accept": "application/json"},
            allow_redirects=False,
        )
    except requests.RequestException as exc:
        raise ConnectionError(type(exc).__name__) from None
    try:
        body = response.json()
    except ValueError:
        raise ar.ArtifactError(["response_not_json"]) from None
    if response.status_code != 200:
        kind = body.get("error_type") if isinstance(body, Mapping) else None
        allowed = {"data_unavailable", "prototype_unavailable", "internal_error"}
        raise ar.ArtifactError(
            [kind if kind in allowed else f"http_{response.status_code}"]
        )
    headers = getattr(response, "headers", {}) or {}
    captured_at = _utc_now()
    artifact = ar.build_artifact(
        body,
        data_origin=ar.DATA_OPERATIONAL,
        captured_at=captured_at,
        http_status=200,
        content_type=headers.get("content-type"),
        source_url=url,
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    artifact_path, _ = ar.write_artifact(artifact, out_dir)
    body_path = out_dir / "bridge-body.json"
    bridge_path = out_dir / "bridge.json"
    scoring_path = out_dir / "scoring.json"
    _write_new_json(body_path, body)
    _write_new_json(bridge_path, {"step": "bridge", "http_status": 200, "body": body})
    _write_new_json(
        scoring_path,
        {
            "step": "scoring",
            "cells": body["cells"],
            "inputs_fingerprint": body["inputs_fingerprint"],
            "model_sha": model_sha,
            "source": "bridge_score_single_get",
            "artifact_fingerprint": artifact["artifact_fingerprint"],
            "captured_at": captured_at,
        },
    )
    return {
        "result": "CAPTURED",
        "get_count": 1,
        "captured_at": captured_at,
        "inputs_fingerprint": body["inputs_fingerprint"],
        "artifact_fingerprint": artifact["artifact_fingerprint"],
        "model_sha": model_sha,
        "files": {
            "bridge_body": str(body_path),
            "accepted_run": str(artifact_path),
            "bridge": str(bridge_path),
            "scoring": str(scoring_path),
        },
    }


# --- writer-payload ------------------------------------------------------------------


def _parse_stdout_json(text: str) -> Optional[dict]:
    try:
        doc = json.loads(text)
    except ValueError:
        return None
    return doc if isinstance(doc, dict) else None


def _firms_paths_for(repo: Path):
    from src.refresh.firms_refresh import FirmsPaths

    default = FirmsPaths()
    if repo.resolve() == REPO_ROOT.resolve():
        return default

    def rebase(p: Path) -> Path:
        return repo / Path(p).resolve().relative_to(REPO_ROOT.resolve())

    return FirmsPaths(
        pointer=rebase(default.pointer),
        versions_dir=rebase(default.versions_dir),
        baseline_csv=rebase(default.baseline_csv),
        baseline_sha256=default.baseline_sha256,
        raw_dir=rebase(default.raw_dir),
    )


def firms_store_checks(repo: Path, current: Mapping, paths=None) -> dict:
    from src.refresh.firms_validation import validate_publication

    try:
        publication = validate_publication(paths or _firms_paths_for(repo))
        accepted = publication.get("result") == "FIRMS ACCEPTED" and publication.get(
            "sha256"
        ) == current.get("manifest_identity")
        detail = "FIRMS ACCEPTED" if accepted else "publication_not_current"
    except Exception as exc:  # noqa: BLE001 — any failure is a rejected store
        accepted, detail = False, f"rejected:{type(exc).__name__}"
    present = current.get("state") == "PRESENT"
    return {
        "schema_ok": accepted and present and current.get("schema_ok") is True,
        "hash_ok": accepted,
        "pointer_ok": accepted and present,
        "store_validation": detail,
    }


def dmc_store_checks(
    repo: Path,
    current: Mapping,
    stdout_doc: Optional[Mapping],
    exit_code: int,
    paths=None,
) -> dict:
    from src.refresh.dmc_refresh import DmcPaths, read_current

    try:
        verified = read_current(
            paths or DmcPaths(root=repo / "data" / "processed" / "dmc")
        )
        detail = "verified" if verified else "pointer_absent"
    except Exception as exc:  # noqa: BLE001
        verified, detail = None, f"rejected:{type(exc).__name__}"
    doc = stdout_doc or {}
    pointer_ok = (
        verified is not None
        and current.get("state") == "PRESENT"
        and verified.get("manifest_sha256") == doc.get("manifest_sha256")
    )
    quality_ok = (
        exit_code == 0
        and doc.get("status") in ("published", "unchanged")
        and isinstance(doc.get("row_quality"), dict)
    )
    return {
        "pointer_ok": pointer_ok,
        "quality_ok": quality_ok,
        "store_validation": detail,
    }


def writer_payload(
    phase: str,
    *,
    stdout: str,
    stderr: str,
    exit_code: int,
    started_at: str,
    finished_at: str,
    repo: Path = REPO_ROOT,
    firms_paths=None,
    dmc_paths=None,
) -> dict:
    stdout_doc = _parse_stdout_json(stdout)
    payload: dict[str, Any] = {
        "step": phase,
        "started_at": started_at,
        "finished_at": finished_at,
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "writer_stdout_status": (stdout_doc or {}).get("status"),
        "builder": "tools.ops.attempt2_evidence writer-payload",
        # Attempt1 preservation is checked by the operator toolpack, not here.
        "attempt1_check": "NOT_EVALUATED_BY_BUILDER",
    }
    if phase == "firms":
        current = collect_firms_current(repo)
        payload["firms_current_after"] = current
        payload.update(firms_store_checks(repo, current, firms_paths))
    elif phase == "dmc":
        current = collect_dmc_current(repo)
        payload["dmc_current_after"] = current
        payload.update(
            dmc_store_checks(repo, current, stdout_doc, exit_code, dmc_paths)
        )
    else:
        raise ValueError(f"unknown phase: {phase}")
    return payload


# --- n8n-evidence --------------------------------------------------------------------

_NODE_HARNESS = r"""
const fs = require('fs');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const { evaluate } = require(input.policy);
const out = {};
for (const c of input.cases) out[c.id] = evaluate(c.envelope, input.now, 'attempt2-' + c.id);
process.stdout.write(JSON.stringify(out));
"""


def _load_builder(repo: Path):
    spec = importlib.util.spec_from_file_location("sapi_n8n_build", repo / BUILDER_REL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def workflow_checks(repo: Path) -> dict:
    """The committed preview must equal what build_workflow produces from policy.js."""
    checks: dict[str, Any] = {}
    try:
        workflow = json.loads((repo / WORKFLOW_REL).read_text(encoding="utf-8"))
        expected = _load_builder(repo).build()
        policy = (repo / POLICY_REL).read_text(encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "detail": f"unreadable:{type(exc).__name__}"}
    nodes = workflow.get("nodes") or []
    types = [str(n.get("type") or "") for n in nodes]
    code = {n.get("name"): (n.get("parameters") or {}).get("jsCode", "") for n in nodes}
    checks["matches_build"] = workflow == expected
    checks["policy_embedded"] = str(code.get("Policy", "")).startswith(policy)
    checks["inactive"] = workflow.get("active") is False
    checks["manual_trigger_only"] = [t for t in types if "trigger" in t.lower()] == [
        "n8n-nodes-base.manualTrigger"
    ]
    checks["no_schedule_nodes"] = not any(
        k in t.lower() for t in types for k in ("schedule", "cron", "interval")
    )
    checks["no_telegram_nodes"] = not any("telegram" in t.lower() for t in types)
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "workflow_sha256": _sha256_file(repo / WORKFLOW_REL),
        "policy_sha256": _sha256_file(repo / POLICY_REL),
    }


def evaluate_policy(
    repo: Path, body: Mapping, *, node: str = "node", runner=subprocess.run
) -> Optional[dict]:
    """Node evaluation of policy.js; None if Node is missing or fails."""
    cases = [{"id": "score_path", "envelope": {"statusCode": 200, "body": body}}]
    for case, (status, err) in FAIL_CLOSED_ENVELOPES.items():
        cases.append({"id": case, "envelope": {"statusCode": status, "body": err}})
    stdin = json.dumps(
        {
            "policy": str((repo / POLICY_REL).resolve()),
            "now": _utc_now(),
            "cases": cases,
        }
    )
    try:
        proc = runner(
            [node, "-e", _NODE_HARNESS],
            input=stdin,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    try:
        return json.loads(proc.stdout)
    except ValueError:
        return None


def n8n_evidence(
    body: Mapping, *, repo: Path = REPO_ROOT, node: str = "node", runner=subprocess.run
) -> dict:
    wf = workflow_checks(repo)
    results = evaluate_policy(repo, body, node=node, runner=runner) or {}
    real = results.get("score_path") or {}
    score_path_ok = bool(
        wf["ok"]
        and real.get("category") in SCORE_PATH_CATEGORIES
        and real.get("alert_identity_verified") is True
        and real.get("delivery") == "NOT_SENT"
        and real.get("inputs_fingerprint") == body.get("inputs_fingerprint")
    )
    cases = {}
    for case in FAIL_CLOSED_ENVELOPES:
        r = results.get(case) or {}
        cases[case] = bool(
            r.get("category") == "error"
            and r.get("reason") == case
            and r.get("delivery") == "NOT_SENT"
        )
    all_not_sent = bool(results) and all(
        (r or {}).get("delivery") == "NOT_SENT" for r in results.values()
    )
    checks = wf.get("checks") or {}
    # False only when positively verified. A detected schedule/active workflow is True
    # (the operator then refuses it without SCHEDULE_AUTHORIZATION); unknown stays
    # None and, with score_path_ok False, the operator validator fails.
    if (
        checks.get("inactive")
        and checks.get("no_schedule_nodes")
        and checks.get("manual_trigger_only")
    ):
        schedule_enabled = False
    elif checks and (not checks.get("inactive") or not checks.get("no_schedule_nodes")):
        schedule_enabled = True
    else:
        schedule_enabled = None
    return {
        "step": "n8n",
        "schedule_enabled": schedule_enabled,
        "telegram_sent": (
            False if (all_not_sent and checks.get("no_telegram_nodes")) else None
        ),
        "score_path_ok": score_path_ok,
        "fail_closed_cases": cases,
        "evidence_kind": "N8N_POLICY_EVIDENCE",
        "n8n_runtime_executed": False,
        "node_evaluated": bool(results),
        "workflow": wf,
        "policy_results": {
            k: {
                x: v.get(x)
                for x in ("category", "reason", "delivery", "alert_identity_verified")
            }
            for k, v in results.items()
        },
    }


# --- CLI -----------------------------------------------------------------------------


def _print(doc: Mapping) -> None:
    print(json.dumps(doc, ensure_ascii=True, indent=2, sort_keys=True))


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", type=Path, default=REPO_ROOT)
    sub = parser.add_subparsers(dest="command", required=True)
    cap = sub.add_parser("capture-bridge")
    cap.add_argument("--url", required=True)
    cap.add_argument("--out", type=Path, required=True)
    wp = sub.add_parser("writer-payload")
    wp.add_argument("--phase", choices=["firms", "dmc"], required=True)
    wp.add_argument("--stdout", type=Path, required=True)
    wp.add_argument("--stderr", type=Path, required=True)
    wp.add_argument("--exit-code", type=int, required=True)
    wp.add_argument("--started-at", required=True)
    wp.add_argument("--finished-at", required=True)
    wp.add_argument("--out", type=Path, required=True)
    ne = sub.add_parser("n8n-evidence")
    ne.add_argument("--bridge-body", type=Path, required=True)
    ne.add_argument("--node", default=shutil.which("node") or "node")
    ne.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    repo = args.repo.resolve()

    if args.command == "capture-bridge":
        try:
            _print(capture_bridge(args.url, args.out, repo=repo))
        except PermissionError as exc:
            _print({"result": "REFUSED", "error": str(exc)})
            return EXIT_USAGE
        except ConnectionError as exc:
            _print({"result": "NETWORK_ERROR", "error_type": str(exc)})
            return EXIT_NETWORK
        except ar.ArtifactError as exc:
            _print({"result": "NOT_ACCEPTED", "reasons": exc.reasons})
            return EXIT_REJECTED
        except FileExistsError as exc:
            _print({"result": "REFUSED", "error": f"exists:{Path(str(exc)).name}"})
            return EXIT_USAGE
        return EXIT_OK

    if args.command == "writer-payload":
        doc = writer_payload(
            args.phase,
            stdout=args.stdout.read_text(encoding="utf-8"),
            stderr=args.stderr.read_text(encoding="utf-8"),
            exit_code=args.exit_code,
            started_at=args.started_at,
            finished_at=args.finished_at,
            repo=repo,
        )
    else:
        body = json.loads(args.bridge_body.read_text(encoding="utf-8"))
        doc = n8n_evidence(body, repo=repo, node=args.node)
    try:
        _write_new_json(args.out, doc)
    except FileExistsError:
        _print({"result": "REFUSED", "error": f"exists:{args.out.name}"})
        return EXIT_USAGE
    summary = {
        k: doc.get(k)
        for k in (
            "step",
            "exit_code",
            "schema_ok",
            "hash_ok",
            "pointer_ok",
            "quality_ok",
            "score_path_ok",
            "fail_closed_cases",
            "schedule_enabled",
            "telegram_sent",
            "n8n_runtime_executed",
        )
        if k in doc
    }
    _print({"result": "WRITTEN", "path": str(args.out), **summary})
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())

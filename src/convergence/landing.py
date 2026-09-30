"""RC1 convergence landing mechanics for the Operations Data adapter (convergence-owned).

Git is the authority. A branch name is never trusted as the adapter identity: the adapter
is a full 40-hex commit that descends from the Operations base, is contained in the
Operations branch history, is absent from the candidate and does not touch frozen
Data/Output/convergence paths. The trial merge is zero-write (`git merge-tree`); the real
merge runs only with `execute=True` and must reproduce the trial tree.

Never: network, writers, n8n, Telegram, workspace materialization, main, push.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

FULL_SHA = re.compile(r"[0-9a-f]{40}")
FP_V3_SCHEMA = "sapi-rc1-convergence-fingerprint-v3"
TEST_RESULT_SCHEMA = "sapi-rc1-convergence-test-result-v1"
LANES_REL = "config/rc1_convergence_lanes.json"
# The adapter must stay inside the Operations consumer surface.
FROZEN_PREFIXES = (
    "models/",
    "data/",
    "app/",
    "src/output/",
    "src/inference/",
    "src/refresh/",
    "src/ingesta/",
    "src/procesamiento/",
    "src/convergence/",
    "tools/n8n_bridge/",
    "ops/n8n/",
    "src/ops/data_readiness.py",
    "config/data_plane_rc1.json",
    LANES_REL,
)
SUITES: dict[str, list[str]] = {
    "A_adapter": [
        "tests/test_convergence_data_adapter_contract.py",
        "tests/test_data_plane_manifest_adapter.py",
        "tests/test_operations_plane_failure_matrix.py",
        "tests/test_operations_plane_rc1_e2e.py",
    ],
    "C_output_handshake": [
        "tests/test_convergence_output_acceptance.py",
        "tests/test_convergence_run_binding.py",
    ],
    "D_cross_plane": ["tests/test_convergence_cross_plane.py"],
    "E_output_replay": [
        "tests/test_accepted_run.py",
        "tests/test_output_pipeline.py",
        "tests/test_output_readiness.py",
        "tests/test_alert_payload.py",
    ],
    "F_operations": [
        "tests/test_attempt2_operator_e2e.py",
        "tests/test_attempt2_operator_failures.py",
        "tests/test_attempt2_operator_phase2.py",
        "tests/test_attempt2_operator_phase3.py",
        "tests/test_attempt2_operator_phase4.py",
        "tests/test_attempt2_operator_unit.py",
        "tests/test_convergence_ops_fixes.py",
        "tests/test_operational_workspace.py",
        "tests/test_workspace_safety.py",
    ],
    "G_control_center": [
        "tests/test_ops_dashboard.py",
        "tests/test_prototype_view.py",
    ],
    "H_bridge": [
        "tests/test_n8n_bridge.py",
        "tests/test_n8n_bridge_contract.py",
        "tests/test_scoring_inputs.py",
        "tests/test_prototype_service.py",
    ],
}
FULL_HOST = "I_full_host"


class LandingRefused(RuntimeError):
    def __init__(self, reasons: Sequence[str], detail: Optional[dict] = None):
        super().__init__("; ".join(reasons))
        self.reasons = list(reasons)
        self.detail = detail or {}


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=check,
    )


def _out(repo: Path, *args: str) -> str:
    return git(repo, *args).stdout.strip()


def is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    return (
        git(
            repo, "merge-base", "--is-ancestor", ancestor, descendant, check=False
        ).returncode
        == 0
    )


def load_lanes(repo: Path) -> dict:
    return json.loads((repo / LANES_REL).read_text(encoding="utf-8"))


def canonical_sha256(value: Any) -> str:
    data = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    )
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def candidate_identity(repo: Path) -> dict:
    return {
        "branch": _out(repo, "rev-parse", "--abbrev-ref", "HEAD"),
        "sha": _out(repo, "rev-parse", "HEAD"),
        "tree": _out(repo, "rev-parse", "HEAD^{tree}"),
        "parents": _out(repo, "rev-list", "--parents", "-n", "1", "HEAD").split()[1:],
        "clean": _out(repo, "status", "--porcelain", "--untracked-files=all") == "",
    }


def lane_reachability(repo: Path, lanes: Mapping) -> dict[str, bool]:
    shas = {
        "base": lanes["base"]["sha"],
        "data": lanes["data"]["sha"],
        "output": lanes["output"]["sha"],
        "operations_base": lanes["operations"]["base_sha"],
    }
    if lanes["operations"]["adapter_sha"]:
        shas["operations_adapter"] = lanes["operations"]["adapter_sha"]
    return {name: is_ancestor(repo, sha, "HEAD") for name, sha in shas.items()}


def validate_adapter(repo: Path, sha: str, lanes: Mapping) -> dict:
    """Every precondition of the future `git merge --no-ff <sha>`; never mutates."""
    if not isinstance(sha, str) or not FULL_SHA.fullmatch(sha):
        raise LandingRefused(["sha_not_full_40_lowercase_hex"])
    resolved = git(
        repo, "rev-parse", "--verify", "--quiet", f"{sha}^{{commit}}", check=False
    )
    if resolved.returncode != 0:
        raise LandingRefused(["commit_not_found"])
    if resolved.stdout.strip() != sha:
        raise LandingRefused(["sha_resolves_elsewhere"])
    base = lanes["operations"]["base_sha"]
    reasons: list[str] = []
    cand = candidate_identity(repo)
    if cand["branch"] != lanes["candidate_branch"]:
        reasons.append("wrong_candidate_branch")
    if not cand["clean"]:
        reasons.append("candidate_dirty")
    if lanes["operations"]["adapter_sha"] is not None:
        reasons.append("lanes_lock_already_records_an_adapter")
    reach = lane_reachability(repo, lanes)
    reasons += [f"lane_missing:{name}" for name, ok in reach.items() if not ok]
    if sha == base:
        reasons.append("adapter_is_the_operations_base")
    elif not is_ancestor(repo, base, sha):
        reasons.append("not_descendant_of_operations_base")
    ops_ref = f"refs/heads/{lanes['operations']['branch']}"
    if git(repo, "rev-parse", "--verify", "--quiet", ops_ref, check=False).returncode:
        reasons.append("operations_branch_missing")
    elif not is_ancestor(repo, sha, ops_ref):
        reasons.append("not_in_operations_branch_history")
    if is_ancestor(repo, sha, "HEAD"):
        reasons.append("adapter_already_merged")
    touched: list[str] = []
    commits: list[str] = []
    if "not_descendant_of_operations_base" not in reasons and sha != base:
        touched = _out(repo, "diff", "--name-only", base, sha).splitlines()
        commits = _out(repo, "rev-list", "--reverse", f"{base}..{sha}").splitlines()
        reasons += [
            f"touches_frozen_path:{p}"
            for p in touched
            if any(p == f or p.startswith(f) for f in FROZEN_PREFIXES)
        ]
        other_lanes = [lanes["data"]["sha"], lanes["output"]["sha"]]
        foreign = _out(
            repo, "rev-list", sha, f"^{base}", *[f"^{s}" for s in other_lanes]
        )
        if len(foreign.splitlines()) != len(commits):
            reasons.append("range_contains_other_lane_history")
    result = {
        "adapter_sha": sha,
        "operations_base": base,
        "candidate": cand,
        "lanes": reach,
        "adapter_commits": commits,
        "touched_paths": touched,
        "reasons": sorted(set(reasons)),
    }
    if reasons:
        raise LandingRefused(result["reasons"], result)
    return result


def trial_merge(repo: Path, sha: str, lanes: Mapping) -> dict:
    """Zero-write trial: merge-tree writes only unreachable objects, no ref/index/worktree."""
    base = lanes["operations"]["base_sha"]
    res = git(
        repo, "merge-tree", "--write-tree", "--name-only", "HEAD", sha, check=False
    )
    lines = res.stdout.splitlines()
    conflicts: list[str] = []
    if res.returncode == 1:
        for line in lines[1:]:
            if not line.strip():
                break
            conflicts.append(line.strip())
    elif res.returncode != 0:
        raise LandingRefused(["merge_tree_failed"], {"stderr": res.stderr[-2000:]})
    touched = set(_out(repo, "diff", "--name-only", base, sha).splitlines())
    candidate_changed = set(
        _out(repo, "diff", "--name-only", base, "HEAD").splitlines()
    )
    return {
        "method": "git merge-tree --write-tree HEAD <adapter> (zero-write)",
        "mergeable": res.returncode == 0,
        "trial_tree": lines[0].strip() if lines else None,
        "conflicts": sorted(set(conflicts)),
        "touched_paths": sorted(touched),
        "overlap_with_candidate_changes": sorted(touched & candidate_changed),
    }


def land_operations_adapter(
    repo: Path,
    sha: str,
    *,
    execute: bool = False,
    trailer: Optional[str] = None,
) -> dict:
    """Validate → trial → (execute) merge --no-ff → record lanes lock → assertions."""
    lanes = load_lanes(repo)
    validation = validate_adapter(repo, sha, lanes)
    trial = trial_merge(repo, sha, lanes)
    if not trial["mergeable"]:
        raise LandingRefused(["trial_merge_conflicts"], {"trial": trial})
    plan = {
        "result": "READY_TO_LAND" if not execute else None,
        "validation": validation,
        "trial": trial,
        "merge_command": ["git", "merge", "--no-ff", sha],
    }
    if not execute:
        return plan
    before = candidate_identity(repo)["sha"]
    suffix = f"\n\n{trailer}" if trailer else ""
    msg = (
        f"merge(rc1-convergence): OPERATIONS Data adapter {sha[:12]} into candidate\n\n"
        f"Operations child of {lanes['operations']['base_sha']}; resolves B1 once the "
        f"Data handshake is ACCEPTED.{suffix}"
    )
    git(repo, "merge", "--no-ff", "--no-edit", "-m", msg, sha)
    merged = candidate_identity(repo)
    if merged["tree"] != trial["trial_tree"]:
        raise LandingRefused(["merge_tree_differs_from_trial"], {"merged": merged})
    lanes_path = repo / LANES_REL
    lanes = json.loads(lanes_path.read_text(encoding="utf-8"))
    lanes["operations"]["adapter_sha"] = sha
    lanes["blockers"] = {"resolved": ["B1", "B2", "B3"], "open": []}
    lanes_path.write_text(json.dumps(lanes, indent=2) + "\n", encoding="utf-8")
    git(repo, "add", LANES_REL)
    git(
        repo,
        "commit",
        "-m",
        f"chore(convergence): record Operations adapter {sha[:12]} in lanes lock{suffix}",
    )
    after = candidate_identity(repo)
    assertions = post_merge_assertions(repo, sha, merge_parent=before)
    plan.update(result="LANDED", merged=merged, candidate=after, assertions=assertions)
    return plan


def post_merge_assertions(
    repo: Path, sha: str, *, merge_parent: Optional[str] = None
) -> dict:
    lanes = load_lanes(repo)
    checks = {f"reachable:{k}": v for k, v in lane_reachability(repo, lanes).items()}
    checks["reachable:adapter"] = is_ancestor(repo, sha, "HEAD")
    checks["lanes_lock_records_adapter"] = lanes["operations"]["adapter_sha"] == sha
    checks["clean"] = candidate_identity(repo)["clean"]
    merges = _out(
        repo, "log", "--merges", "--first-parent", "--format=%H %P", "-n", "5"
    )
    checks["adapter_is_a_no_ff_merge_parent"] = any(
        line.split()[2:] == [sha]
        and (merge_parent is None or line.split()[1] == merge_parent)
        for line in merges.splitlines()
    )
    return {"checks": checks, "pass": all(checks.values())}


# --- test orchestration and normalization ------------------------------------------------------


def _junit_outcomes(path: Path) -> dict[str, str]:
    outcomes: dict[str, str] = {}
    for case in ET.parse(path).getroot().iter("testcase"):
        node = f"{case.get('classname')}::{case.get('name')}"
        tags = {child.tag for child in case}
        outcomes[node] = (
            "failed"
            if tags & {"failure", "error"}
            else "skipped" if "skipped" in tags else "passed"
        )
    return outcomes


def run_suite(repo: Path, name: str, python: str = sys.executable) -> dict:
    with tempfile.TemporaryDirectory(prefix="sapi-conv-") as tmp:
        junit = Path(tmp) / "junit.xml"
        files = SUITES.get(name, [])
        cov = [] if name == FULL_HOST else ["--no-cov"]
        cmd = [python, "-m", "pytest", *files, "-q", "-p", "no:cacheprovider", *cov,
               f"--junitxml={junit}"]  # fmt: skip
        proc = subprocess.run(
            cmd, cwd=repo, capture_output=True, text=True, encoding="utf-8"
        )
        outcomes = _junit_outcomes(junit) if junit.is_file() else {}
    counts = {
        k: sum(1 for v in outcomes.values() if v == k)
        for k in ("passed", "skipped", "failed")
    }
    cand = candidate_identity(repo)
    return {
        "schema": TEST_RESULT_SCHEMA,
        "suite": name,
        "command": ["python", *cmd[1:-1]],
        "pass": counts["passed"],
        "skip": counts["skipped"],
        "fail": counts["failed"],
        "exit_code": proc.returncode,
        "status": (
            "PASS"
            if proc.returncode == 0 and counts["failed"] == 0 and outcomes
            else "FAIL"
        ),
        "candidate_sha": cand["sha"],
        "tree": cand["tree"],
        "outcomes": outcomes,
        "tail": proc.stdout[-1500:],
    }


def test_delta(before: Mapping, after: Mapping) -> dict:
    """Per-test comparison of two normalized results (PRE vs POST adapter)."""
    b, a = before.get("outcomes", {}), after.get("outcomes", {})
    kinds = (
        "new_pass",
        "new_fail",
        "fixed_fail",
        "new_skip",
        "removed_skip",
        "removed_test",
    )
    out: dict[str, list[str]] = {k: [] for k in kinds}
    for node in sorted(set(a) | set(b)):
        was, now = b.get(node), a.get(node)
        if now is None:
            out["removed_test"].append(node)
        elif now == "failed" and was != "failed":
            out["new_fail"].append(node)
        elif was == "failed" and now == "passed":
            out["fixed_fail"].append(node)
        elif now == "passed" and was is None:
            out["new_pass"].append(node)
        if now == "skipped" and was != "skipped":
            out["new_skip"].append(node)
        if was == "skipped" and now != "skipped":
            out["removed_skip"].append(node)
    out_counts = {k: len(v) for k, v in out.items()}
    return {"counts": out_counts, "regression": bool(out["new_fail"]), "tests": out}


def summary_identity(result: Mapping) -> dict:
    """Test identity inside fingerprint v3: counts and exit code, never time or paths."""
    return {k: result[k] for k in ("suite", "pass", "skip", "fail", "exit_code")}


def fingerprint_v3(
    repo: Path,
    *,
    data_handshake: Mapping,
    output_handshake: str,
    test_results: Sequence[Mapping],
    template: bool = False,
) -> dict:
    lanes = load_lanes(repo)
    cand = candidate_identity(repo)
    stale = [r["suite"] for r in test_results if r.get("candidate_sha") != cand["sha"]]
    problems = []
    if not template:
        if lanes["operations"]["adapter_sha"] is None:
            problems.append("adapter_not_landed")
        if data_handshake.get("classification") != "ACCEPTED" or not data_handshake.get(
            "match"
        ):
            problems.append("data_handshake_not_accepted")
        if output_handshake != "PASS":
            problems.append("output_handshake_not_pass")
        if not cand["clean"]:
            problems.append("candidate_dirty")
        if stale:
            problems.append("test_results_for_another_candidate")
        if any(r["fail"] or r["exit_code"] for r in test_results):
            problems.append("test_failures_present")
        if {r["suite"] for r in test_results} != set(SUITES) | {FULL_HOST}:
            problems.append("test_phases_incomplete")
    if problems:
        raise LandingRefused(problems)
    stable = {
        "schema": FP_V3_SCHEMA,
        "base_sha": lanes["base"]["sha"],
        "data_sha": lanes["data"]["sha"],
        "output_sha": lanes["output"]["sha"],
        "operations_base_sha": lanes["operations"]["base_sha"],
        "operations_adapter_sha": lanes["operations"]["adapter_sha"],
        "candidate_sha": cand["sha"],
        "candidate_tree": cand["tree"],
        "data_manifest_fingerprint": lanes["data"]["manifest_fingerprint"],
        "output_manifest_fingerprint": lanes["output"]["manifest_fingerprint"],
        "resolved_blockers": sorted(lanes["blockers"]["resolved"]),
        "open_blockers": sorted(lanes["blockers"]["open"]),
        "resolved_findings": sorted(lanes.get("findings", {}).get("resolved", [])),
        "open_findings": sorted(lanes.get("findings", {}).get("open", [])),
        "test_summaries": sorted(
            (summary_identity(r) for r in test_results), key=lambda r: r["suite"]
        ),
    }
    return {
        "status": "TEMPLATE_NON_FINAL" if template else "FINAL",
        "stable": stable,
        "convergence_fingerprint_v3": canonical_sha256(stable),
    }


# --- status and CLI -----------------------------------------------------------------------------


def default_manifests(repo: Path) -> dict[str, Path]:
    evidence = repo.parent / "SAPI-71-evidence"
    return {
        "data": evidence / "data-plane-rc1-2026-09-25" / "DATA_PLANE_MANIFEST.json",
        "output": evidence
        / "output-plane-rc1-2026-09-25"
        / "OUTPUT_PLANE_MANIFEST.json",
    }


def handshakes(repo: Path, data_manifest: Path, output_manifest: Path) -> dict:
    from src.convergence import data_handshake, output_acceptance

    lanes = load_lanes(repo)
    data = (
        data_handshake.classify(data_manifest, lanes=lanes)
        if data_manifest.is_file()
        else {"classification": "NOT_AVAILABLE", "match": False}
    )
    reasons, _ = output_acceptance.verify_output_plane(
        output_manifest, expected_fingerprint=lanes["output"]["manifest_fingerprint"]
    )
    return {
        "data": data,
        "output": "PASS" if not reasons else "REJECTED",
        "output_reasons": reasons,
    }


def status(repo: Path, data_manifest: Path, output_manifest: Path) -> dict:
    lanes = load_lanes(repo)
    cand = candidate_identity(repo)
    reach = lane_reachability(repo, lanes)
    ops_ref = f"refs/heads/{lanes['operations']['branch']}"
    ops_head = git(
        repo, "rev-parse", "--verify", "--quiet", ops_ref, check=False
    ).stdout.strip()
    pending = (
        _out(
            repo, "rev-list", f"{lanes['operations']['base_sha']}..{ops_head}"
        ).splitlines()
        if ops_head
        else []
    )
    hs = handshakes(repo, data_manifest, output_manifest)
    landed = lanes["operations"]["adapter_sha"] is not None
    if not all(reach.values()):
        next_action = "STOP: convergence corruption, a lane is not reachable"
    elif not cand["clean"]:
        next_action = (
            "candidate has uncommitted changes: commit or review before landing"
        )
    elif not landed and not pending:
        next_action = "WAIT FOR ANTIGRAVITY ADAPTER SHA"
    elif not landed:
        next_action = (
            "check-adapter --sha <full SHA from Antigravity>, then land with --execute"
        )
    elif hs["data"].get("classification") != "ACCEPTED" or hs["output"] != "PASS":
        next_action = (
            f"STOP: adapter landed but Data handshake is "
            f"{hs['data'].get('classification')} / Output {hs['output']}: report to owner"
        )
    else:
        next_action = "run-tests --all, then fingerprint, then hand off to Astra"
    return {
        "candidate": cand,
        "lanes_included": reach,
        "adapter_landed": landed,
        "adapter_sha": lanes["operations"]["adapter_sha"],
        "operations_branch_head": ops_head or None,
        "operations_commits_beyond_base": pending,
        "data_handshake": hs["data"].get("classification"),
        "data_handshake_matches_landing_state": hs["data"].get("match"),
        "output_handshake": hs["output"],
        "release_gate": "NOT_EVALUATED (Astra-owned)",
        "next_action": next_action,
    }


def main(argv: Optional[list[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="python scripts/rc1_converge.py")
    parser.add_argument(
        "--repo", type=Path, default=Path(__file__).resolve().parents[2]
    )
    parser.add_argument("--data-manifest", type=Path, default=None)
    parser.add_argument("--output-manifest", type=Path, default=None)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    for name in ("check-adapter", "land-operations-adapter"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--sha", required=True)
        if name == "land-operations-adapter":
            cmd.add_argument("--execute", action="store_true", help="perform the merge")
            cmd.add_argument("--trailer", default=None, help="commit trailer line")
    tests = sub.add_parser("run-tests")
    tests.add_argument("--suite", action="append", choices=[*SUITES, FULL_HOST])
    tests.add_argument("--all", action="store_true")
    tests.add_argument("--out", type=Path, required=True)
    delta = sub.add_parser("delta")
    delta.add_argument("before", type=Path)
    delta.add_argument("after", type=Path)
    fp = sub.add_parser("fingerprint")
    fp.add_argument("--tests", type=Path, required=True)
    fp.add_argument("--template", action="store_true")
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    manifests = default_manifests(repo)
    manifests["data"] = args.data_manifest or manifests["data"]
    manifests["output"] = args.output_manifest or manifests["output"]

    def emit(obj: Any) -> None:
        print(json.dumps(obj, ensure_ascii=True, indent=2, sort_keys=True))

    try:
        if args.command == "status":
            emit(status(repo, manifests["data"], manifests["output"]))
        elif args.command == "check-adapter":
            lanes = load_lanes(repo)
            emit({"validation": validate_adapter(repo, args.sha, lanes),
                  "trial": trial_merge(repo, args.sha, lanes)})  # fmt: skip
        elif args.command == "land-operations-adapter":
            result = land_operations_adapter(
                repo, args.sha, execute=args.execute, trailer=args.trailer
            )
            emit(result)
            if args.execute and not result["assertions"]["pass"]:
                return 3
        elif args.command == "run-tests":
            names = [*SUITES, FULL_HOST] if args.all else (args.suite or [])
            if not names:
                parser.error("--suite or --all required")
            results = [run_suite(repo, n) for n in names]
            args.out.write_text(
                json.dumps(results, indent=2, sort_keys=True), encoding="utf-8"
            )
            emit(
                [
                    {k: v for k, v in r.items() if k not in ("outcomes", "tail")}
                    for r in results
                ]
            )
            return 0 if all(r["status"] == "PASS" for r in results) else 3
        elif args.command == "delta":
            before, after = (
                {r["suite"]: r for r in json.loads(p.read_text("utf-8"))}
                for p in (args.before, args.after)
            )
            emit({s: test_delta(before.get(s, {}), after[s]) for s in sorted(after)})
        elif args.command == "fingerprint":
            results = json.loads(args.tests.read_text(encoding="utf-8"))
            hs = handshakes(repo, manifests["data"], manifests["output"])
            emit(fingerprint_v3(repo, data_handshake=hs["data"], output_handshake=hs["output"],
                                test_results=results, template=args.template))  # fmt: skip
    except LandingRefused as exc:
        emit({"result": "REFUSED", "reasons": exc.reasons, "detail": exc.detail})
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())

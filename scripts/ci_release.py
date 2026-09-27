"""Exact-SHA release gate orchestration; never operational authorization."""

from __future__ import annotations

import argparse
import configparser
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import shutil
import traceback
import sys
import uuid

from ci_local import BASE, RANKING, pytest_metrics
from ci_local_docker import run_docker
from ci_release_core import (
    ReleaseRunner,
    aggregate,
    compare,
    export,
    fingerprint,
    git,
    quality_delta,
    resolve,
    stable_result,
    utc,
    validate_result,
    write_json,
    redact,
    match_status,
    seal_reports,
    test_identity,
    environment_reusable,
    handshake_status,
    attach_git_metadata,
)
from ci_release_manifests import ancestry, verify

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = Path(r"D:\portafolio y seminario\SAPI-71-evidence\release-gates")
WORKER = Path(__file__).with_name("ci_release_worker.py")
MODEL = "ac017bef1f42a30ac74ba3e3787368c4418798b2d562adcfba01c923cff2173f"
FIRMS = "a9a85db4431b3e54f936b724e4de5a7fbb0cc19f5721f5e1a344a192bf9bb271"
PLANE_FINGERPRINTS = {
    "data": "5a6484fc4b047751fa6cec8e29a377c0ed96a19e1873ec25539745bca32a1ae0",
    "output": "9441f7178805f48ab6d7f563b8bd5c70e555ba621bfb6779ba2360cec61b01a3",
}


def read(path):
    return json.loads(Path(path).read_bytes())


def code_identity():
    names = sorted(Path(__file__).parent.glob("ci_*.py"))
    names.append(Path(__file__).with_name("ci_release_schema.json"))
    return {
        "commit": git(ROOT, "rev-parse", "HEAD"),
        "files": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in names},
    }


def workflow(source):
    import yaml

    doc = yaml.load(
        (source / ".github/workflows/ci.yml").read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )
    steps = doc["jobs"]["test"]["steps"]
    expected = [
        "actions/checkout@v4",
        "Set up Python",
        "Install dependencies",
        "Initialize database schema",
        "Format check",
        "Lint",
        "Run tests",
    ]
    mapped = []
    for number, step in enumerate(steps):
        name = step.get("name", step.get("uses"))
        mapped.append(
            {
                "step_id": number,
                "name": name,
                "official_command": step.get("run", step.get("uses")),
                "environment_names": sorted(step.get("env", {})),
                "mandatory": True,
                "required_services": (
                    ["postgis"]
                    if name in ("Initialize database schema", "Run tests")
                    else []
                ),
                "local_equivalent": {
                    "actions/checkout@v4": "verified Git archive",
                    "Set up Python": "isolated Python 3.14 venv",
                    "Install dependencies": "fresh pip requirements-dev.txt",
                    "Initialize database schema": "owned tmpfs PostGIS with identical SQL order",
                    "Format check": "Black baseline/candidate differential",
                    "Lint": "flake8 baseline/candidate differential",
                    "Run tests": "pytest + configured coverage + machine reports",
                }.get(name, "UNMAPPED"),
                "exact_parity": False,
                "limitation": (
                    "Local runner is not GitHub Actions; differential policy "
                    "is additional to absolute CI debt reporting"
                ),
            }
        )
    supported = (
        hashlib.sha256((source / ".github/workflows/ci.yml").read_bytes()).hexdigest()
        == hashlib.sha256(
            subprocess.check_output(
                ["git", "-C", str(ROOT), "show", BASE + ":.github/workflows/ci.yml"],
                timeout=30,
            )
        ).hexdigest()
    )
    return {
        "status": (
            "PASS"
            if supported and [s["name"] for s in mapped] == expected
            else "INCOMPLETE"
        ),
        "steps": mapped,
        "remote_github_ci": "NOT VERIFIED",
        "workflow_sha256": hashlib.sha256(
            (source / ".github/workflows/ci.yml").read_bytes()
        ).hexdigest(),
    }


def network_guard(output, port):
    directory = output / "runtime-guard"
    directory.mkdir(exist_ok=True)
    (directory / "sitecustomize.py").write_text(
        "import sys, socket\n"
        "def guard(event,args):\n"
        " if event == 'socket.getaddrinfo':\n"
        "  if args[0] not in ('localhost','127.0.0.1','::1',None):\n"
        "   raise PermissionError('RC runtime external DNS forbidden')\n"
        " if event == 'socket.connect':\n"
        "  if sys._getframe(1).f_code is getattr(socket.socketpair,'__code__',None): return\n"
        "  a=args[1]\n"
        f"  if not (isinstance(a,tuple) and a[0] in ('127.0.0.1','::1') "
        f"and (a[1]=={port} or a[1]>=32768)):\n"
        "   raise PermissionError('RC runtime external/operational socket forbidden')\n"
        "sys.addaudithook(guard)\n",
        encoding="utf-8",
    )
    return directory


def run_gate(args):
    if not args.evidence_root.resolve().is_relative_to(EVIDENCE.resolve()):
        raise ValueError(
            "Evidence must remain under the designated release-gates directory"
        )
    out = args.evidence_root.resolve() / (
        "run-" + utc().replace(":", "").replace("+", "_") + "-" + uuid.uuid4().hex[:8]
    )
    out.mkdir(parents=True)
    runner = ReleaseRunner(ROOT, out)
    write_json(
        out / "result.schema.json",
        read(Path(__file__).with_name("ci_release_schema.json")),
    )
    result = {
        "schema_version": 1,
        "kind": "RC_GATE_RESULT",
        "candidate": {},
        "baseline": {},
        "gate_identity": code_identity(),
        "environment_identity": {},
        "checks": [],
        "findings": [],
        "static_analysis": {},
        "tests": {},
        "coverage": {},
        "sentinels": {},
        "component_manifests": {},
        "ancestry": {},
        "handshake": {},
        "started_at": utc(),
        "independent_firms_approval": "PENDING",
        "authorization": False,
        "remote_github_ci": "NOT VERIFIED",
    }

    def check(identifier, status, detail=None, required=True):
        result["checks"].append(
            {"id": identifier, "status": status, "required": required, "detail": detail}
        )
        if status != "PASS" and required:
            result["findings"].append(
                {"id": identifier, "status": status, "reason": detail}
            )

    def worker(mode, location, python, extra=()):
        if (
            hashlib.sha256(WORKER.read_bytes()).hexdigest()
            != result["gate_identity"]["files"][WORKER.name]
        ):
            raise ValueError("Release worker changed during gate execution")
        target = out / (mode + "-" + location.name + ".json")
        item = runner.run(
            mode + "-" + location.name,
            [
                str(python),
                str(WORKER),
                mode,
                str(location),
                str(target),
                *map(str, extra),
            ],
        )
        return (
            read(target)
            if item["status"] == "PASS"
            else {"error": item["reason"], "status": item["status"]}
        )

    try:
        try:
            result["candidate"] = resolve(ROOT, args.candidate_sha)
            result["baseline"] = resolve(ROOT, args.baseline_sha)
        except (ValueError, subprocess.CalledProcessError):
            check(
                "RC-CODE-IDENTITY",
                "FAIL",
                "Candidate or baseline is not a resolvable full commit SHA",
            )
            raise ValueError("Invalid immutable code identity") from None
        origin = {
            "branch": git(ROOT, "branch", "--show-current"),
            "dirty": bool(git(ROOT, "status", "--porcelain")),
        }
        request = {
            "candidate": result["candidate"],
            "baseline": result["baseline"],
            "gate": result["gate_identity"],
            "python": sys.version,
            "lanes": sorted(args.require_lane),
            "manifests": {},
        }
        for kind in ("data", "output", "operations"):
            path = getattr(args, kind + "_manifest")
            request["manifests"][kind] = {
                "sha256": (
                    hashlib.sha256(path.read_bytes()).hexdigest()
                    if path and path.is_file()
                    else None
                ),
                "expected": getattr(args, "expected_" + kind + "_fingerprint"),
            }
        result["cache_identity"] = fingerprint(request)
        write_json(
            out / "request.json",
            {**request, "origin": origin, "cache_identity": result["cache_identity"]},
        )
        source, base = out / "candidate", out / "baseline"
        result["source"] = export(ROOT, args.candidate_sha, source)
        result["source"]["git_metadata"] = attach_git_metadata(
            ROOT, args.candidate_sha, source
        )
        export(ROOT, args.baseline_sha, base)
        docker_source = out / "docker-source"
        shutil.copytree(source, docker_source)
        check("RC-CODE-EXPORT", "PASS")
        # Existing convergence tests discover immutable plane evidence beside REPO.
        # Give them verified-input copies under this run, never the originals.
        for kind in ("data", "output"):
            path = getattr(args, kind + "_manifest")
            if path and path.is_file():
                folder = out / "SAPI-71-evidence" / (kind + "-plane-rc1-2026-09-25")
                folder.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, folder / (kind.upper() + "_PLANE_MANIFEST.json"))
        result["ci_steps"] = workflow(source)
        check("RC-CODE-CI-CONTRACT", result["ci_steps"]["status"])
        write_json(out / "ci-step-map.json", result["ci_steps"])
        requirements = {
            p: hashlib.sha256((source / p).read_bytes()).hexdigest()
            for p in ("requirements.txt", "requirements-dev.txt")
        }
        environment = out / "fresh-venv"
        resumed = False
        if args.resume:
            receipt_path = args.resume.resolve() / "environment-receipt.json"
            if not receipt_path.is_relative_to(EVIDENCE.resolve()):
                raise ValueError("Resume path outside evidence root")
            if receipt_path.is_file():
                try:
                    receipt = read(receipt_path)
                except (OSError, ValueError):
                    receipt = {}
                if receipt.get("cache_identity") == result["cache_identity"]:
                    old_environment = args.resume.resolve() / "fresh-venv"
                    old_python = old_environment / (
                        "Scripts/python.exe" if os.name == "nt" else "bin/python"
                    )
                    probe = runner.run(
                        "resume_environment_probe",
                        [str(old_python), "-m", "pip", "freeze", "--all"],
                    )
                    if environment_reusable(receipt, result["cache_identity"], probe):
                        environment, resumed = old_environment, True
        created = (
            {"status": "PASS"}
            if resumed
            else runner.run(
                "fresh_environment",
                [sys.executable, "-m", "venv", str(environment)],
                timeout=180,
            )
        )
        python = environment / (
            "Scripts/python.exe" if os.name == "nt" else "bin/python"
        )
        check("RC-DEPS-ENVIRONMENT", created["status"])
        if created["status"] != "PASS":
            raise RuntimeError("Environment unavailable")
        runner.root = source
        if not resumed:
            upgraded = runner.run(
                "upgrade_pip",
                [str(python), "-m", "pip", "install", "--upgrade", "pip"],
                timeout=300,
            )
            check(
                "RC-DEPS-PIP", "PASS" if upgraded["status"] == "PASS" else "INCOMPLETE"
            )
        else:
            check("RC-DEPS-PIP", "PASS")
        installed = (
            {"status": "PASS", "reason": "Verified isolated environment reused"}
            if resumed
            else runner.run(
                "install_dependencies",
                [str(python), "-m", "pip", "install", "-r", "requirements-dev.txt"],
                timeout=1800,
            )
        )
        check(
            "RC-DEPS-INSTALL",
            "PASS" if installed["status"] == "PASS" else "INCOMPLETE",
            installed["reason"],
        )
        if installed["status"] != "PASS":
            raise RuntimeError("Declared environment unavailable")
        freeze = runner.run(
            "dependency_identity", [str(python), "-m", "pip", "freeze", "--all"]
        )
        frozen = (out / freeze["evidence"]["log"]).read_text(encoding="utf-8")
        result["environment_identity"] = {
            "fresh": True,
            "python": sys.version.split()[0],
            "platform": sys.platform,
            "requirements": requirements,
            "packages_sha256": hashlib.sha256(frozen.encode()).hexdigest(),
        }
        write_json(
            out / "environment-receipt.json",
            {
                "cache_identity": result["cache_identity"],
                "packages_sha256": freeze["evidence"]["sha256"],
                "reused": resumed,
            },
        )
        tool_env = dict(runner.env)
        tool_env.update(
            PYTHONPATH=str(network_guard(out, 1)),
            COVERAGE_FILE=str(out / "host.coverage"),
        )
        runner.env = tool_env
        import_result = worker("imports", source, python)
        check(
            "RC-DEPS-IMPORTS",
            (
                "FAIL"
                if "error" in import_result or "error_class" in import_result
                else "PASS"
            ),
        )
        before, after = worker("quality", base, python), worker(
            "quality", source, python
        )
        write_json(out / "quality-baseline.json", before)
        write_json(out / "quality-candidate.json", after)
        changed = git(
            ROOT, "diff", "--name-only", args.baseline_sha, args.candidate_sha
        ).splitlines()
        result["static_analysis"] = quality_delta(before, after, changed)
        result["static_analysis"]["black_baseline_files"] = len(before["black_files"])
        result["static_analysis"]["black_candidate_files"] = len(after["black_files"])
        check(
            "RC-LINT-DELTA",
            result["static_analysis"]["status"],
            "New findings block; unchanged historical debt remains visible",
        )
        model = source / "models/prototype_model_d.pkl"
        baseline_file = (
            source
            / "artifacts/hito1/reproducibility/firms/nasa_firms_2021-08-30_2026-08-30.csv"
        )
        for label, path, expected in (
            ("model", model, MODEL),
            ("firms", baseline_file, FIRMS),
        ):
            actual = (
                hashlib.sha256(path.read_bytes()).hexdigest()
                if path.is_file()
                else None
            )
            result["sentinels"][label] = {"expected": expected, "actual": actual}
            check(
                "RC-SCI-" + label.upper(),
                match_status(actual, expected),
            )
        hito = {
            p.relative_to(source).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (source / "artifacts/hito1").rglob("*")
            if p.is_file()
        }
        original_hito = {
            p.relative_to(base).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (base / "artifacts/hito1").rglob("*")
            if p.is_file()
        }
        result["sentinels"]["hito1"] = {
            "count": len(hito),
            "match": hito == original_hito,
            "fingerprint": fingerprint(hito),
        }
        check(
            "RC-SCI-HITO1",
            "PASS" if len(hito) == 131 and hito == original_hito else "FAIL",
        )
        ranked = worker("ranking", source, python)
        result["sentinels"]["ranking"] = ranked
        check(
            "RC-SCI-RANKING",
            match_status(ranked.get("ranking"), RANKING),
        )
        for kind in ("data", "output", "operations"):
            path = getattr(args, kind + "_manifest")
            verified = verify(
                kind,
                path,
                ROOT,
                args.candidate_sha,
                getattr(args, "expected_" + kind + "_fingerprint", None),
            )
            result["component_manifests"][kind] = verified
            if path is not None:
                check(
                    "RC-MANIFEST-" + kind.upper(),
                    verified["status"],
                    verified.get("reason"),
                )
            elif kind != "operations":
                check(
                    "RC-MANIFEST-" + kind.upper(),
                    "INCOMPLETE",
                    "Required plane evidence not supplied",
                )
        required = dict(pair.split("=", 1) for pair in args.require_lane)
        result["ancestry"] = ancestry(ROOT, args.candidate_sha, required)
        for name, proof in result["ancestry"].items():
            check("RC-CODE-ANCESTRY-" + name.upper(), proof["status"])
        if args.data_manifest:
            result["handshake"] = worker(
                "handshake", source, python, (args.data_manifest,)
            )
            check(
                "RC-MANIFEST-DATA-CONSUMER",
                handshake_status(result["handshake"]),
                "Real Data producer manifest acceptance by candidate Operations consumer",
            )
        parser = configparser.ConfigParser()
        parser.read(source / "pytest.ini", encoding="utf-8")
        match = re.search(
            r"--cov-fail-under(?:=|\s+)([\d.]+)",
            parser.get("pytest", "addopts", fallback=""),
        )
        threshold = float(match.group(1)) if match else None

        def host_tests(port):
            env = dict(runner.env)
            env.update(
                PYTHONPATH=str(network_guard(out, port)),
                DATABASE_URL=f"postgresql://sapi@127.0.0.1:{port}/sapi_db",
                DATABASE_URL_DIRECT=f"postgresql://sapi@127.0.0.1:{port}/sapi_db",
            )
            tested = runner.run(
                "host_tests",
                [
                    str(python),
                    "-m",
                    "pytest",
                    "--junitxml=" + str(out / "host-junit.xml"),
                    "--cov-report=json:" + str(out / "host-coverage.json"),
                ],
                env=env,
                timeout=1800,
            )
            check("RC-TEST-HOST", tested["status"])
            try:
                metrics = pytest_metrics(
                    out / "host-junit.xml", out / "host-coverage.json"
                )
                result["tests"]["host"] = {
                    k: v for k, v in metrics.items() if k != "coverage"
                }
                result["tests"]["host"]["outcomes_fingerprint"] = test_identity(
                    out / "host-junit.xml"
                )
                result["coverage"]["host"] = {
                    **metrics["coverage"],
                    "required": threshold,
                }
                check(
                    "RC-COV-HOST",
                    (
                        "PASS"
                        if threshold is None
                        or metrics["coverage"]["percent"] >= threshold
                        else "FAIL"
                    ),
                )
            except (OSError, ValueError, KeyError):
                check("RC-TEST-HOST-REPORT", "INCOMPLETE")

        docker_state = run_docker(
            runner,
            {
                "code_sha": args.candidate_sha,
                "tree_sha": result["candidate"]["tree"],
                "dirty_state": False,
            },
            True,
            source_context=docker_source,
            host_callback=host_tests,
        )
        # Absolute Docker lint debt is reported, not confused with test/environment failure.
        docker_steps = [
            s
            for s in runner.steps
            if s["name"].startswith(("docker_", "cleanup_", "copy_docker"))
            and s["name"] not in ("docker_format", "docker_lint")
        ]
        normalized = [
            {
                **s,
                "status": (
                    "INCOMPLETE"
                    if s["status"] in ("BLOCKED", "NOT_RUN")
                    else s["status"]
                ),
            }
            for s in docker_steps
        ]
        if not any(s["name"] == "docker_tests" for s in normalized):
            normalized.append(
                {
                    "status": "INCOMPLETE",
                    "required": True,
                    "name": "docker_tests_missing",
                }
            )
        result["docker"] = {
            "status": aggregate(normalized),
            "legacy_absolute_status": docker_state,
        }
        for label in ("docker_image_identity", "docker_database_identity"):
            items = [
                s for s in runner.steps if s["name"] == label and s["status"] == "PASS"
            ]
            if items:
                result["environment_identity"][label] = (
                    (out / items[0]["evidence"]["log"])
                    .read_text(encoding="utf-8")
                    .strip()
                )
        check("RC-DOCKER-RUNTIME", result["docker"]["status"])
        db_steps = [
            s
            for s in normalized
            if s["name"] in ("docker_database_ready", "docker_schema")
        ]
        result["postgis"] = {"status": aggregate(db_steps)}
        check("RC-ENV-POSTGIS", result["postgis"]["status"])
        if not any(c["id"] == "RC-TEST-HOST" for c in result["checks"]):
            host_tests(1)
            check(
                "RC-ENV-HOST-DATABASE",
                "INCOMPLETE",
                "Host fallback cannot reproduce mandatory DB tests",
            )
        if (out / "docker-metrics.json").exists():
            metrics = read(out / "docker-metrics.json")
            result["tests"]["docker"] = {
                k: v for k, v in metrics.items() if k != "coverage"
            }
            result["tests"]["docker"]["outcomes_fingerprint"] = test_identity(
                out / "docker-junit.xml"
            )
            result["coverage"]["docker"] = {
                **metrics["coverage"],
                "required": threshold,
            }
            check(
                "RC-COV-DOCKER",
                (
                    "PASS"
                    if threshold is None or metrics["coverage"]["percent"] >= threshold
                    else "FAIL"
                ),
            )
    except (Exception, KeyboardInterrupt) as error:
        (out / "execution-error.txt").write_text(
            redact(traceback.format_exc()), encoding="utf-8"
        )
        check(
            "RC-ENV-EXECUTION",
            "FAIL" if isinstance(error, ValueError) else "INCOMPLETE",
            type(error).__name__,
        )
    mandatory = (
        "RC-CODE-EXPORT",
        "RC-CODE-CI-CONTRACT",
        "RC-DEPS-ENVIRONMENT",
        "RC-DEPS-INSTALL",
        "RC-DEPS-IMPORTS",
        "RC-LINT-DELTA",
        "RC-SCI-MODEL",
        "RC-SCI-FIRMS",
        "RC-SCI-HITO1",
        "RC-SCI-RANKING",
        "RC-MANIFEST-DATA",
        "RC-MANIFEST-OUTPUT",
        "RC-CODE-ANCESTRY-OPERATIONS",
        "RC-TEST-HOST",
        "RC-COV-HOST",
        "RC-DOCKER-RUNTIME",
        "RC-ENV-POSTGIS",
        "RC-COV-DOCKER",
    )
    for identifier in mandatory:
        if not any(c["id"] == identifier for c in result["checks"]):
            check(identifier, "INCOMPLETE", "Required check not completed")
    if "cache_identity" in result:
        for kind in ("data", "output"):
            path = getattr(args, kind + "_manifest")
            expected = request["manifests"][kind]["sha256"]
            if expected:
                copied = (
                    out
                    / "SAPI-71-evidence"
                    / (kind + "-plane-rc1-2026-09-25")
                    / (kind.upper() + "_PLANE_MANIFEST.json")
                )
                try:
                    unchanged = all(
                        hashlib.sha256(p.read_bytes()).hexdigest() == expected
                        for p in (path, copied)
                    )
                    check(
                        "RC-MANIFEST-" + kind.upper() + "-UNCHANGED",
                        "PASS" if unchanged else "FAIL",
                    )
                except OSError:
                    check("RC-MANIFEST-" + kind.upper() + "-UNCHANGED", "INCOMPLETE")
    hygiene = seal_reports(out)
    check("RC-ENV-SECRET-HYGIENE", hygiene["status"], hygiene["finding_rules"])
    result["findings"] = sorted(result["findings"], key=lambda f: f["id"])
    result["status"] = aggregate(result["checks"])
    result["stable_result_fingerprint"] = fingerprint(stable_result(result))
    result["finished_at"] = utc()
    validate_result(result)
    write_json(out / "result.json", result)
    validate_result(read(out / "result.json"))
    write_json(
        out / "RC_MANIFEST.json",
        {
            "schema_version": 1,
            "identity": stable_result(result),
            "fingerprint": result["stable_result_fingerprint"],
            "created_at": utc(),
            "authorization": False,
        },
    )
    counts = ", ".join(
        f"{state}={sum(c['status'] == state for c in result['checks'])}"
        for state in ("PASS", "FAIL", "INCOMPLETE")
    )
    summary = (
        f"SAPI RC1 LOCAL RELEASE GATE\nCandidate: {args.candidate_sha}\n"
        f"Tree: {result['candidate'].get('tree', 'NOT_AVAILABLE')}\n"
        f"Status: {result['status']}\n"
        f"Checks: {counts}\n"
        f"Findings: {', '.join(f['id'] for f in result['findings']) or 'none'}\n"
        f"Evidence: {out}\nFingerprint: {result['stable_result_fingerprint']}\n"
        "Remote GitHub CI: NOT VERIFIED\nOperational authorization: NONE\n"
    )
    summary = redact(summary)
    (out / "summary.txt").write_text(summary, encoding="utf-8")
    print(summary)
    return {"PASS": 0, "FAIL": 1, "INCOMPLETE": 2}[result["status"]]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    gate = sub.add_parser("gate")
    gate.add_argument("--candidate-sha", required=True)
    gate.add_argument("--baseline-sha", default=BASE)
    gate.add_argument("--evidence-root", type=Path, default=EVIDENCE)
    gate.add_argument("--require-lane", action="append", default=[], metavar="NAME=SHA")
    gate.add_argument(
        "--resume",
        type=Path,
        help=(
            "Prior evidence directory; reuse only identical verified environment; "
            "rerun all checks"
        ),
    )
    for kind in ("data", "output", "operations"):
        default = (
            (
                EVIDENCE.parent
                / (kind + "-plane-rc1-2026-09-25")
                / (kind.upper() + "_PLANE_MANIFEST.json")
            )
            if kind != "operations"
            else None
        )
        gate.add_argument("--" + kind + "-manifest", type=Path, default=default)
        gate.add_argument(
            "--expected-" + kind + "-fingerprint", default=PLANE_FINGERPRINTS.get(kind)
        )
    comparison = sub.add_parser("compare")
    comparison.add_argument("left", type=Path)
    comparison.add_argument("right", type=Path)
    args = parser.parse_args(argv)
    if args.mode == "compare":
        print(
            json.dumps(
                compare(read(args.left), read(args.right)), sort_keys=True, indent=2
            )
        )
        return 0
    return run_gate(args)

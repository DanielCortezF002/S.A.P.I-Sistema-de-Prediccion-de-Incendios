"""Read-only local CI fallback. Never grants merge or GitHub Actions success."""

from __future__ import annotations

import argparse
import configparser
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
BASE = "7ef8d3c9f7ecb4758718255b8e48d6468f8613ea"
RANKING = "33c2eacc49bd0cc130928b5bd182ec523e63614f0e3dd97a129a8d4657f231ff"
STATES = {"PASS", "FAIL", "SKIP", "BLOCKED", "NOT_RUN"}
SECRET_RULES = {
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "provider_token": re.compile(
        r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
        r"AKIA[A-Z0-9]{16}|sk-[A-Za-z0-9_-]{20,})"
    ),
    "bearer": re.compile(r"(?i)\bBearer\s+([A-Za-z0-9._~+/-]{8,})"),
    "assignment": re.compile(
        r"""(?ix)["']?\b(?:[a-z0-9_]*(?:api_?key|token|password|secret)|"""
        r"""authorization)["']?\s*[:=]\s*["']([^"'\r\n]{8,})["']"""
    ),
    "unquoted_assignment": re.compile(
        r"(?im)^\s*[A-Z0-9_]*(?:API_?KEY|TOKEN|PASSWORD|SECRET)\s*[:=]\s*([^\s\"']{8,})\s*$"
    ),
}
# Explicit public fixture literals, not whole-file exclusions.
PUBLIC_LITERALS = {
    "sapi_secret",
    "test-token",
    "test_token",
    "dummy-token",
    "dummy_token",
    "your_api_key",
    "your_token",
    "changeme",
    "REDACTED",
    "[REDACTED]",
}


# Reviewed public placeholders and an error-redaction unit fixture. Exact path/digest.
# A changed value is scanned again; no test or configuration file is excluded wholesale.
PUBLIC_FIXTURES = {
    (
        ".env.example",
        "aa6ec5c09ffe3ba57f527daa73e02dfaca98a5d8f9634e2c3685f57a7cb02bd0",
    ),
    (
        ".env.example",
        "a1242bd30a5f0c253f782cee9e204de79e85af5affc98761cb643e41d82f8a3a",
    ),
    (
        "tests/test_dem_ingester.py",
        "dc87f94e8f44b5018e54a588eebeaae61eebdb6c256f8f2f61b7c6ba347bca63",
    ),
}


def utc():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def findings(path, content):
    found = []
    if Path(path).name == ".env" or (
        Path(path).name.startswith(".env.")
        and not str(path).endswith((".example", ".template"))
    ):
        found.append({"path": str(path), "rule": "env_file", "finding": "[REDACTED]"})
    for rule, pattern in SECRET_RULES.items():
        for match in pattern.finditer(content):
            value = match.group(1) if match.lastindex else match.group()
            if value in PUBLIC_LITERALS:
                continue
            if re.fullmatch(r"(?:Bearer )?\$\{[A-Z0-9_]+(?::-[A-Za-z0-9_]+)?\}", value):
                continue
            fixture = (
                str(path).replace("\\", "/"),
                hashlib.sha256(value.encode()).hexdigest(),
            )
            if fixture in PUBLIC_FIXTURES:
                continue
            found.append({"path": str(path), "rule": rule, "finding": "[REDACTED]"})
            break
    return found


def sanitize(content):
    # Logs are never persisted before redaction, including multiline private keys.
    content = re.sub(
        r"-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----",
        "[REDACTED]",
        content,
        flags=re.S,
    )
    return "\n".join(
        (
            "[REDACTED sensitive line]"
            if findings("log", line)
            else re.sub(r"(\w+://)[^\s/@]+:[^\s/@]+@", r"\1[REDACTED]@", line)
        )
        for line in content.splitlines()
    )


def git(root, *args):
    return subprocess.check_output(
        ["git", "-C", str(root), *args],
        text=True,
        encoding="utf-8",
        stderr=subprocess.DEVNULL,
        timeout=30,
    ).rstrip("\r\n")


def identity(root):
    changes = git(root, "status", "--porcelain=v1", "--untracked-files=all")
    return {
        "code_sha": git(root, "rev-parse", "HEAD"),
        "tree_sha": git(root, "rev-parse", "HEAD^{tree}"),
        "branch": git(root, "branch", "--show-current"),
        "dirty_state": bool(changes),
        "dirty_paths": [line[3:] for line in changes.splitlines()],
    }


def step(
    name,
    status,
    evidence=None,
    required=True,
    command=None,
    duration=0.0,
    exit_code=None,
):
    return dict(
        name=name,
        command=command or name,
        status=status,
        duration=duration,
        exit_code=exit_code,
        evidence=evidence or {},
        required=required,
    )


def overall(steps, dirty=False):
    if any(s["status"] == "FAIL" for s in steps):
        return "FAIL"
    if (
        dirty
        or not steps
        or any(
            s["status"] not in STATES
            or (s.get("required", True) and s["status"] != "PASS")
            for s in steps
        )
    ):
        return "INCOMPLETE"
    return "PASS"


def validate_result(result):
    fields = {
        "schema_version",
        "code_sha",
        "tree_sha",
        "branch",
        "dirty_state",
        "started_at",
        "finished_at",
        "mode",
        "steps",
        "tests_passed",
        "tests_skipped",
        "tests_failed",
        "coverage",
        "docker_status",
        "secret_scan",
        "artifact_checks",
        "warnings",
        "failures",
        "overall_result",
        "merge_authorization",
        "gate",
    }
    if not fields <= result.keys() or result["schema_version"] != 1:
        raise ValueError("Malformed result fields")
    if (
        result["merge_authorization"] is not False
        or type(result["dirty_state"]) is not bool
    ):
        raise ValueError("Invalid authorization or identity state")
    if result["mode"] not in {"fast", "host", "docker", "all"}:
        raise ValueError("Invalid mode")
    for key in ("code_sha", "tree_sha"):
        if not re.fullmatch(r"[0-9a-f]{40}", result[key]):
            raise ValueError("Invalid Git identity")
    for key in ("started_at", "finished_at"):
        datetime.fromisoformat(result[key])
    for key in ("tests_passed", "tests_skipped", "tests_failed"):
        if result[key] is not None and (
            type(result[key]) is not int or result[key] < 0
        ):
            raise ValueError("Invalid test count")
    if result["secret_scan"] not in STATES or result["docker_status"] not in STATES:
        raise ValueError("Invalid check state")
    coverage = result["coverage"]
    if coverage is not None:
        if not isinstance(coverage, dict) or not isinstance(
            coverage.get("percent"), (int, float)
        ):
            raise ValueError("Invalid coverage")
        if (
            not math.isfinite(coverage["percent"])
            or not 0 <= coverage["percent"] <= 100
        ):
            raise ValueError("Invalid coverage")
    if result["overall_result"] == "PASS" and (
        result["tests_passed"] is None
        or result["tests_failed"] != 0
        or result["secret_scan"] != "PASS"
        or (result["mode"] != "fast" and coverage is None)
    ):
        raise ValueError("Missing passing-gate evidence")
    if not isinstance(result["steps"], list):
        raise ValueError("Malformed steps")
    for item in result["steps"]:
        if (
            not {
                "name",
                "command",
                "status",
                "duration",
                "exit_code",
                "evidence",
                "required",
            }
            <= item.keys()
            or item["status"] not in STATES
            or type(item["required"]) is not bool
            or not isinstance(item["duration"], (int, float))
            or item["duration"] < 0
        ):
            raise ValueError("Malformed step")
    expected = overall(result["steps"], result["dirty_state"])
    if (
        result["overall_result"] != expected
        or result["gate"] != "LOCAL_GATE_" + expected
    ):
        raise ValueError("Inconsistent gate")
    return result


def clean_env():
    keep = {
        "PATH",
        "SYSTEMROOT",
        "WINDIR",
        "COMSPEC",
        "PATHEXT",
        "TEMP",
        "TMP",
        "TMPDIR",
        "LANG",
        "LC_ALL",
    }
    env = {k: v for k, v in os.environ.items() if k.upper() in keep}
    env.update(
        PYTHONIOENCODING="utf-8",
        PYTHONDONTWRITEBYTECODE="1",
        PYTHON_DOTENV_DISABLED="1",
        DATABASE_URL="postgresql://invalid@127.0.0.1:1/ci_disabled",
        DATABASE_URL_DIRECT="postgresql://invalid@127.0.0.1:1/ci_disabled",
    )
    return env


class Runner:
    def __init__(self, root, output):
        self.root, self.output = Path(root), Path(output)
        self.env = clean_env()
        home = self.output / "isolated-home"
        home.mkdir(exist_ok=True)
        self.env.update(
            HOME=str(home), USERPROFILE=str(home), BLACK_CACHE_DIR=str(home / "black")
        )
        self.steps = []

    def check(self, action):
        start = time.monotonic()
        item = action()
        item["duration"] = time.monotonic() - start
        self.steps.append(item)
        return item

    def run(self, name, command, required=True, timeout=1200, env=None):
        start = time.monotonic()
        try:
            proc = subprocess.run(
                command,
                cwd=self.root,
                env=env or self.env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
            code, status, output = (
                proc.returncode,
                "PASS" if proc.returncode == 0 else "FAIL",
                proc.stdout + proc.stderr,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            code, status, output = None, "BLOCKED", type(exc).__name__
        log = self.output / (name + ".log")
        log.write_text(sanitize(output), encoding="utf-8")
        item = step(
            name,
            status,
            {"log": log.name, "sha256": sha(log)},
            required,
            command,
            time.monotonic() - start,
            code,
        )
        self.steps.append(item)
        return item


def check_artifact(root, relative, expected, must_exist=False):
    start = time.monotonic()
    path = root / relative
    if not path.is_file():
        return step(
            relative,
            "FAIL" if must_exist else "BLOCKED",
            {"reason": "missing artifact", "expected": expected},
            duration=time.monotonic() - start,
        )
    actual = sha(path)
    return step(
        relative,
        "PASS" if actual == expected else "FAIL",
        {"expected": expected, "actual": actual},
        duration=time.monotonic() - start,
    )


def workflow_check(root):
    import yaml

    workflow = root / ".github/workflows/ci.yml"
    # BaseLoader preserves the YAML key 'on' instead of YAML 1.1 boolean coercion.
    data = yaml.load(workflow.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    mapping = json.loads((root / "ci-parity-map.json").read_text(encoding="utf-8"))
    steps = data["jobs"]["test"]["steps"]
    names = [s.get("name", s.get("uses")) for s in steps]
    errors = []
    if names != [s["workflow_step"] for s in mapping["steps"]]:
        errors.append("CI_PARITY_GAP: unmapped workflow steps")
    for relative, expected in mapping["contracts"].items():
        path = root / relative
        digest = (
            hashlib.sha256(
                path.read_text(encoding="utf-8").replace("\r\n", "\n").encode()
            ).hexdigest()
            if path.is_file()
            else None
        )
        if digest != expected:
            errors.append("CI_PARITY_GAP: changed contract " + relative)
    for relative in (
        "src",
        "app",
        "tests",
        "requirements-dev.txt",
        "requirements.txt",
        "docker/initdb",
    ):
        if not (root / relative).exists():
            errors.append("Missing referenced path " + relative)
    if not list((root / "docker/initdb").glob("*.sql")):
        errors.append("Missing SQL scripts")
    for item in steps:
        if not (root / item.get("working-directory", ".")).is_dir():
            errors.append("Missing working directory")
    return step(
        "workflow",
        "FAIL" if errors else "PASS",
        {
            "errors": errors,
            "step_count": len(steps),
            "triggers": data["on"],
            "environment_names": sorted({k for s in steps for k in s.get("env", {})}),
            "runner": data["jobs"]["test"]["runs-on"],
            "validation_scope": "YAML syntax and pinned supported contract; no Actions execution",
        },
    )


def environment_check(root):
    versions, issues = {}, []
    for file in ("requirements.txt", "requirements-dev.txt"):
        for line in (root / file).read_text(encoding="utf-8").splitlines():
            match = re.fullmatch(r"([\w-]+)==([\w.]+)", line.strip())
            if not match:
                continue
            name, expected = match.groups()
            try:
                actual = importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                actual = None
            versions[name] = actual
            if actual != expected:
                issues.append(name)
    if sys.version_info[:2] != (3, 14):
        issues.append("Python")
    return step(
        "environment",
        "BLOCKED" if issues else "PASS",
        {
            "python": sys.version.split()[0],
            "versions": versions,
            "mismatches": issues,
            "fresh_install": False,
        },
    )


def scan_repo(root):
    paths = git(
        root, "ls-files", "--cached", "--others", "--exclude-standard", "-z"
    ).split("\0")
    # Also check ignored dotenv files, without following junctions or venvs.
    for parent, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = [
            d
            for d in dirs
            if d not in {".git", "venv", "__pycache__"}
            and not d.startswith(".venv")
            and not (Path(parent) / d).is_symlink()
            and not (
                hasattr(Path(parent) / d, "is_junction")
                and (Path(parent) / d).is_junction()
            )
        ]
        paths.extend(
            str((Path(parent) / f).relative_to(root))
            for f in files
            if f == ".env" or f.startswith(".env.")
        )
    hits, unreadable = [], []
    for relative in sorted(set(paths)):
        if not relative:
            continue
        path = root / relative
        if not path.is_file() or path.is_symlink():
            unreadable.append(relative)
            continue
        raw = path.read_bytes()
        if b"\0" in raw[:8192]:
            continue  # binary artifacts have independent identity checks
        hits.extend(findings(relative, raw.decode("utf-8", errors="replace")))
    return step(
        "secret_scan",
        "FAIL" if hits else "BLOCKED" if unreadable else "PASS",
        {
            "findings": hits,
            "unreadable": unreadable,
            "scope": "tracked and unignored files plus ignored dotenv; "
            "heuristic text scan, binaries excluded",
        },
    )


def artifact_checks(root):
    sys.path.insert(0, str(root))
    from scripts.verify_reproducibility import ALWAYS_EXPECTED, CHECKED_ARTIFACTS, _dig

    manifest = json.loads(
        (root / "artifacts/hito1/reproducibility/manifest.json").read_text(
            encoding="utf-8"
        )
    )
    checks = [
        check_artifact(root, rel, _dig(manifest, key), rel in ALWAYS_EXPECTED)
        for rel, key in CHECKED_ARTIFACTS
    ]
    checks.extend(
        [
            check_artifact(
                root,
                "models/prototype_model_d.pkl",
                "ac017bef1f42a30ac74ba3e3787368c4418798b2d562adcfba01c923cff2173f",
                True,
            ),
            check_artifact(
                root,
                "artifacts/hito1/reproducibility/firms/"
                "nasa_firms_2021-08-30_2026-08-30.csv",
                "a9a85db4431b3e54f936b724e4de5a7fbb0cc19f5721f5e1a344a192bf9bb271",
                True,
            ),
        ]
    )
    for item in checks:
        if item["name"] not in ALWAYS_EXPECTED and item["status"] == "BLOCKED":
            item["required"] = False  # repository contract explicitly allows absence
    hito_changes = git(root, "diff", BASE, "--name-only", "--", "artifacts/hito1")
    checks.append(
        step(
            "hito1_lane_integrity",
            "FAIL" if hito_changes else "PASS",
            {"changed_by_lane": bool(hito_changes), "base": BASE},
        )
    )
    return checks


def pytest_metrics(junit, coverage):
    suites = ET.parse(junit).getroot()
    cases = list(suites.iter("testcase"))
    failed = sum(
        c.find("failure") is not None or c.find("error") is not None for c in cases
    )
    skipped = sum(c.find("skipped") is not None for c in cases)
    data = json.loads(Path(coverage).read_text(encoding="utf-8"))
    if not cases:
        raise ValueError("No test cases")
    return {
        "tests_passed": len(cases) - failed - skipped,
        "tests_skipped": skipped,
        "tests_failed": failed,
        "coverage": {"percent": data["totals"]["percent_covered"]},
    }


def frozen_fingerprint():
    os.environ["SAPI_REPRODUCIBILITY_MODE"] = "1"
    sys.path.insert(0, str(ROOT))
    from src.inference.prototype_service import score_current_grid

    result = score_current_grid()
    digest = hashlib.sha256(
        "\n".join(f"{c.cell_id},{c.score!r},{c.rank}" for c in result.cells).encode()
    ).hexdigest()
    print(
        json.dumps(
            {"fingerprint": digest, "expected": RANKING, "cells": len(result.cells)}
        )
    )
    return 0 if digest == RANKING else 1


def write_network_guard(output):
    guard = output / "guard"
    guard.mkdir()
    (guard / "sitecustomize.py").write_text(
        "import sys, socket\ndef deny(event, args):\n"
        "    if event not in ('socket.connect', 'socket.getaddrinfo'):\n"
        "        return\n"
        "    # Windows stdlib socketpair connects its own ephemeral loopback pair.\n"
        "    if sys._getframe(1).f_code is getattr(socket.socketpair, '__code__', None):\n"
        "        return\n"
        "    raise PermissionError('Local CI: network disabled')\n"
        "sys.addaudithook(deny)\n",
        encoding="utf-8",
    )
    return guard


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    for mode in ("fast", "host", "docker", "all"):
        modes.add_argument("--" + mode, action="store_const", const=mode, dest="mode")
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="New evidence directory OUTSIDE checkout",
    )
    args = parser.parse_args(argv)
    output = args.output.resolve()
    if output == ROOT or ROOT in output.parents or output.exists():
        parser.error(
            "Use a new evidence directory outside the checkout (no overwrites)"
        )
    output.mkdir(parents=True)
    ident = identity(ROOT)
    result = dict(
        schema_version=1,
        **ident,
        started_at=utc(),
        finished_at=None,
        mode=args.mode,
        steps=[],
        tests_passed=None,
        tests_skipped=None,
        tests_failed=None,
        coverage=None,
        docker_status="NOT_RUN",
        secret_scan="NOT_RUN",
        artifact_checks=[],
        warnings=[
            "LOCAL FALLBACK EVIDENCE: LOCAL CI PASS != GITHUB ACTIONS PASS",
            "CI_PARITY_GAP: host does not provision Ubuntu/PostGIS or reinstall dependencies",
        ],
        failures=[],
        merge_authorization=False,
    )
    runner = Runner(ROOT, output)
    try:
        runner.steps.append(
            step("identity", "BLOCKED" if ident["dirty_state"] else "PASS", ident)
        )
        runner.check(lambda: workflow_check(ROOT))
        runner.check(lambda: environment_check(ROOT))
        scan = runner.check(lambda: scan_repo(ROOT))
        result["secret_scan"] = scan["status"]
        artifacts = artifact_checks(ROOT)
        runner.steps.extend(artifacts)
        result["artifact_checks"] = artifacts
        # Child Python processes deny network and dotenv; no inherited credentials.
        guard = write_network_guard(output)
        runner.env["PYTHONPATH"] = os.pathsep.join([str(guard), str(ROOT)])
        runner.env["COVERAGE_FILE"] = str(output / ".coverage")
        runner.run(
            "format", [sys.executable, "-m", "black", "--check", "src", "app", "tests"]
        )
        runner.run(
            "lint",
            [
                sys.executable,
                "-m",
                "flake8",
                "src",
                "app",
                "tests",
                "--max-line-length=100",
                "--extend-ignore=E203,W503",
            ],
        )
        if all(s["status"] == "PASS" for s in artifacts if s["required"]):
            runner.run(
                "frozen_fingerprint",
                [sys.executable, str(ROOT / "scripts/ci_local.py"), "_fingerprint"],
            )
        else:
            runner.steps.append(
                step(
                    "frozen_fingerprint",
                    "BLOCKED",
                    {"reason": "Frozen artifact precheck did not pass"},
                )
            )
        if args.mode in {"fast", "host", "all"}:
            test_args = [sys.executable, "-m", "pytest"]
            if args.mode == "fast":
                test_args += ["tests/test_ci_local.py", "-o", "addopts="]
            else:
                test_args += ["--cov-report=json:" + str(output / "coverage.json")]
            test_args += ["--junitxml=" + str(output / "junit.xml")]
            runner.run("tests", test_args)
            try:
                if args.mode == "fast":
                    cases = list(
                        ET.parse(output / "junit.xml").getroot().iter("testcase")
                    )
                    result.update(
                        tests_passed=sum(len(c) == 0 for c in cases),
                        tests_skipped=sum(c.find("skipped") is not None for c in cases),
                        tests_failed=sum(
                            c.find("failure") is not None or c.find("error") is not None
                            for c in cases
                        ),
                    )
                else:
                    result.update(
                        pytest_metrics(output / "junit.xml", output / "coverage.json")
                    )
                    config = configparser.ConfigParser()
                    config.read(ROOT / "pytest.ini")
                    threshold = re.search(
                        r"--cov-fail-under[= ](\d+(?:\.\d+)?)",
                        config["pytest"]["addopts"],
                    )
                    result["coverage"]["threshold"] = (
                        float(threshold[1]) if threshold else None
                    )
                runner.steps.append(step("test_metrics", "PASS"))
            except (OSError, ValueError, KeyError, ET.ParseError):
                runner.steps.append(
                    step(
                        "test_metrics",
                        "BLOCKED",
                        {"reason": "Missing or malformed machine test report"},
                    )
                )
        if args.mode in {"docker", "all"}:
            from ci_local_docker import run_docker

            result["docker_status"] = run_docker(
                runner, ident, required=args.mode == "docker"
            )
            if args.mode == "docker":
                metrics = next(
                    (s for s in runner.steps if s["name"] == "docker_metrics"), None
                )
                if metrics and metrics["status"] == "PASS":
                    result.update(metrics["evidence"])
        else:
            runner.steps.append(
                step(
                    "docker",
                    "NOT_RUN",
                    {"reason": "Not requested in this mode"},
                    required=False,
                )
            )
        if args.mode in {"host", "all"}:
            runner.steps.append(
                step(
                    "host_database",
                    "BLOCKED",
                    {"reason": "CI_PARITY_GAP: host has no CI-managed PostGIS/schema"},
                )
            )
        if args.mode == "fast":
            runner.steps.append(
                step(
                    "full_suite",
                    "NOT_RUN",
                    {"reason": "Fast mode is not canonical host evidence"},
                )
            )
    except Exception as exc:
        runner.steps.append(
            step("harness_error", "BLOCKED", {"error_class": type(exc).__name__})
        )
    after = identity(ROOT)
    if after != ident:
        runner.steps.append(
            step(
                "source_stability", "BLOCKED", {"reason": "Identity changed during run"}
            )
        )
    result["finished_at"] = utc()
    result["steps"] = runner.steps
    result["failures"] = [s["name"] for s in runner.steps if s["status"] == "FAIL"]
    result["warnings"] += [
        s["name"] + ": " + s["status"]
        for s in runner.steps
        if s["status"] in {"BLOCKED", "NOT_RUN", "SKIP"}
    ]
    if ident["dirty_state"]:
        result["warnings"].append(
            "Dirty worktree: commit/tree identify HEAD, not all executed bytes; "
            "noncanonical evidence"
        )
    result["overall_result"] = overall(runner.steps, ident["dirty_state"])
    result["gate"] = "LOCAL_GATE_" + result["overall_result"]
    validate_result(result)
    (output / "run-result.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    (output / "commands.txt").write_text(
        "\n".join(
            sanitize(
                json.dumps(
                    {
                        "step": s["name"],
                        "command": s["command"],
                        "cwd": str(ROOT),
                        "exit_code": s["exit_code"],
                    }
                )
            )
            for s in runner.steps
        ),
        encoding="utf-8",
    )
    (output / "run-summary.md").write_text(
        f"# Local CI fallback\n\n{result['gate']}\n\nCommit: {ident['code_sha']}\n"
        f"Tree: {ident['tree_sha']}\nDirty: {ident['dirty_state']}\n\n"
        "LOCAL CI PASS != GITHUB ACTIONS PASS. Merge authorization: false.\n\n"
        f"Failures: {', '.join(result['failures']) or 'none'}\n\n"
        + "\n".join(result["warnings"]),
        encoding="utf-8",
    )
    manifest = {
        p.relative_to(output).as_posix(): sha(p)
        for p in sorted(output.rglob("*"))
        if p.is_file() and "docker-context" not in p.parts
    }
    (output / "evidence-manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "gate": result["gate"],
                "evidence": str(output),
                "merge_authorization": False,
            }
        )
    )
    return {"PASS": 0, "FAIL": 1, "INCOMPLETE": 2}[result["overall_result"]]


if __name__ == "__main__":
    if sys.argv[1:2] in (["gate"], ["compare"]):
        from ci_release import main as release_main

        raise SystemExit(release_main(sys.argv[1:]))
    raise SystemExit(
        frozen_fingerprint() if sys.argv[1:] == ["_fingerprint"] else main()
    )

"""Merge gate único de S.A.P.I. (Quality Gate W0.9, Revisión 3 §3.1).

GitHub Actions es el gate PREFERIDO, no una dependencia dura. El fallback es
equivalente porque CI y fallback invocan este mismo runner: mismas
definiciones de job, mismos criterios PASS/FAIL y mismo formato de evidencia
(`gate_summary.json` + un log por job). Las diferencias de plataforma quedan
registradas en el bloque `environment` del resumen.

Jobs (se ejecutan siempre en este orden; `freeze` primero, con el árbol limpio):

  freeze                    freeze_check.py F1-F9. En modo gate cualquier SKIP
                            es FAIL; nunca --allow-dirty/--skip-remote/
                            --skip-fingerprint.
  python                    black/flake8 sobre las rutas v2 (bloqueante) +
                            pytest completo con cobertura >= 80 %. La deuda
                            legacy de lint se registra sin bloquear (H11).
  backend-unit              mvnw -B verify -DskipITs (JDK 21).
  sql-migration-validation  SQL MIGRATION VALIDATION: psql sobre PostGIS
                            desechable (sapi58_migration_integration.ps1).
                            NO es una prueba de Flyway.
  flyway-integration        REAL FLYWAY INTEGRATION VALIDATION: Flyway CLI
                            12.4.0 contra PostGIS limpio (w0_host_checks.ps1).
  container-smoke           imágenes ML y backend: /predict reproducible
                            (fingerprint 33c2...) y /health (w0_host_checks.ps1).

Los jobs con Docker delegan en scripts/w0_host_checks.ps1, el mismo script que
Daniel corre en Windows/Omen. Sin Docker o sin PowerShell el job queda
NOT_VERIFIABLE_IN_THIS_ENVIRONMENT, nunca PASS.

La evidencia se escribe FUERA del árbol de trabajo ($RUNNER_TEMP/sapi-gate/<sha>
o ../sapi-gate/<sha>) para que F8 (worktree limpio) no se ensucie; luego se copia
en un commit de evidencia que hereda el gate (`--inherit`).

Uso:
    python scripts/merge_gate.py --job freeze --job python --job backend-unit
    python scripts/merge_gate.py --job all --fresh-clone
    python scripts/merge_gate.py --inherit <sha> [--after-code-freeze]
    python scripts/merge_gate.py --evidence-valid <sha> --job flyway-integration

Códigos de salida: 0 = todo PASS, 1 = algún FAIL, 2 = sin FAIL pero algún job
NOT_VERIFIABLE_IN_THIS_ENVIRONMENT.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

PASS = "PASS"
FAIL = "FAIL"
NOT_VERIFIABLE = "NOT_VERIFIABLE_IN_THIS_ENVIRONMENT"

JOBS = {
    "freeze": {
        "docker": False,
        "kind": "freeze_check F1-F9 (SKIP = FAIL en modo gate)",
    },
    "python": {
        "docker": False,
        "kind": "lint v2 + pytest completo (cobertura >= 80 %)",
    },
    "backend-unit": {
        "docker": False,
        "kind": "mvnw -B verify -DskipITs (JDK 21)",
    },
    "sql-migration-validation": {
        "docker": True,
        "kind": "SQL MIGRATION VALIDATION (psql, no Flyway)",
        "checks": ("sql-migration-validation",),
    },
    "flyway-integration": {
        "docker": True,
        "kind": "REAL FLYWAY INTEGRATION VALIDATION (Flyway CLI 12.4.0)",
        "checks": ("flyway-integration",),
    },
    "container-smoke": {
        "docker": True,
        "kind": "imágenes ML (/predict reproducible) y backend (/health)",
        "checks": ("container-smoke-ml", "container-smoke-backend"),
    },
}

# Rutas v2 con lint bloqueante (H11). Cada PR de Sprint 2 agrega aquí sus
# archivos nuevos; el resto del repo es deuda legacy no bloqueante.
V2_LINT_PATHS = (
    "services/ml_api",
    "scripts/freeze_check.py",
    "scripts/merge_gate.py",
    "tests/test_openapi_contracts.py",
    "tests/test_ml_api.py",
    "tests/test_merge_gate.py",
    "tests/test_w0_host_checks.py",
    "tests/test_w0_host_checks_evidence.py",
    "scripts/compose_v2_preflight.py",
    "tests/test_compose_v2.py",
)
LEGACY_LINT_SCOPE = ("src", "app", "tests")
FLAKE8_ARGS = ("--max-line-length=100", "--extend-ignore=E203,W503")

HOST_CHECKS_SCRIPT = "scripts/w0_host_checks.ps1"

# Tags que el job `freeze` admite (lista finita, nunca un patrón). Prefijo
# recomendado por la Revisión 3 (H14); si Daniel elige otro, se cambia aquí
# antes de mergear PR-W0. Un tag nunca se mueve: un fix crea rcN+1.
TAG_PREFIX = "hito2-sprint2"
ALLOWED_TAGS = tuple(f"{TAG_PREFIX}-rc{n}" for n in range(1, 6)) + (
    f"{TAG_PREFIX}-final",
)

# Herencia de gate: un commit que solo toca estas rutas conserva el resultado
# del SHA validado (commits de evidencia; docs después de CODE FREEZE).
INHERIT_ALWAYS = ("artifacts/hito2/",)
INHERIT_AFTER_CODE_FREEZE = ("docs/hito2/",)

# Validez de la evidencia Docker tomada en otro SHA: si el diff toca alguna de
# estas rutas, la evidencia de ese job caduca y se vuelve a correr.
DOCKER_EVIDENCE_PATHS = {
    "sql-migration-validation": ("db/", "scripts/sapi58_migration_integration.ps1"),
    "flyway-integration": ("db/", HOST_CHECKS_SCRIPT),
    "container-smoke": (
        "Dockerfile.ml-api",
        ".dockerignore",
        "services/",
        "src/",
        "app/",
        "contracts/",
        "models/",
        "config/",
        "requirements.txt",
        "requirements-dev.txt",
        "artifacts/hito1/",
        HOST_CHECKS_SCRIPT,
    ),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def git(*args: str, cwd: Path = REPO_ROOT) -> str:
    result = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def head_sha(cwd: Path = REPO_ROOT) -> str:
    return git("rev-parse", "HEAD", cwd=cwd)


def default_out_dir(sha: str) -> Path:
    """Carpeta de evidencia fuera del árbol de trabajo."""
    runner_temp = os.environ.get("RUNNER_TEMP")
    base = Path(runner_temp) if runner_temp else REPO_ROOT.parent
    return base / "sapi-gate" / sha[:12]


def is_inside_repo(path: Path) -> bool:
    try:
        path.resolve().relative_to(REPO_ROOT.resolve())
    except ValueError:
        return False
    return True


def ordered_jobs(requested: list[str]) -> list[str]:
    if "all" in requested:
        return list(JOBS)
    unknown = sorted(set(requested) - set(JOBS))
    if unknown:
        raise SystemExit(f"jobs desconocidos: {', '.join(unknown)}")
    return [job for job in JOBS if job in requested]


def freeze_command(json_path: Path, allowed_tags: tuple[str, ...]) -> list[str]:
    command = [
        sys.executable,
        "-B",
        "scripts/freeze_check.py",
        "--json",
        str(json_path),
    ]
    for tag in allowed_tags:
        command += ["--allow-tag", tag]
    return command


def freeze_gate_status(report: dict) -> tuple[str, list[str]]:
    """Modo gate: cualquier FAIL o SKIP del freeze check es FAIL."""
    problems = [
        f"{row['check']}={row['status']}"
        for row in report.get("checks", [])
        if row.get("status") != PASS
    ]
    if not report.get("checks"):
        problems.append("reporte sin checks")
    return (FAIL if problems else PASS), problems


def inherit_violations(changed: list[str], after_code_freeze: bool) -> list[str]:
    allowed = INHERIT_ALWAYS + (INHERIT_AFTER_CODE_FREEZE if after_code_freeze else ())
    return [path for path in changed if not path.startswith(allowed)]


def stale_evidence_paths(job: str, changed: list[str]) -> list[str]:
    prefixes = DOCKER_EVIDENCE_PATHS[job]
    return [path for path in changed if path.startswith(prefixes)]


class JobRun:
    """Ejecuta los comandos de un job y deja su log en la carpeta de evidencia."""

    def __init__(self, name: str, out_dir: Path, cwd: Path) -> None:
        self.name = name
        self.cwd = cwd
        self.log_path = out_dir / f"{name}.txt"  # *.log está en .gitignore
        self.commands: list[dict] = []
        self.details: dict = {}
        self.started = time.monotonic()
        self.log_path.write_text(
            f"# {name} - {JOBS[name]['kind']}\n# utc={utc_now()}\n", encoding="utf-8"
        )

    def run(self, command: list[str], cwd: Path | None = None, env=None) -> int:
        workdir = cwd or self.cwd
        with self.log_path.open("a", encoding="utf-8") as log:
            log.write(f"\n$ {' '.join(command)}   (cwd={workdir})\n")
            log.flush()
            try:
                code = subprocess.run(
                    command, cwd=workdir, stdout=log, stderr=subprocess.STDOUT, env=env
                ).returncode
            except FileNotFoundError as exc:
                log.write(f"{exc}\n")
                code = 127
            log.write(f"exit={code}\n")
        self.commands.append({"command": command, "cwd": str(workdir), "exit": code})
        return code

    def result(self, status: str) -> dict:
        return {
            "job": self.name,
            "kind": JOBS[self.name]["kind"],
            "status": status,
            "duration_s": round(time.monotonic() - self.started, 1),
            "commands": self.commands,
            "details": self.details,
            "log": self.log_path.name,
        }


def job_freeze(run: JobRun, out_dir: Path, allowed_tags: tuple[str, ...]) -> str:
    json_path = out_dir / "freeze_check.json"
    code = run.run(freeze_command(json_path, allowed_tags))
    if not json_path.exists():
        run.details["problems"] = [f"freeze_check sin JSON (exit {code})"]
        return FAIL
    status, problems = freeze_gate_status(json.loads(json_path.read_text("utf-8")))
    run.details["problems"] = problems
    return status if code == 0 or status == FAIL else FAIL


def job_python(run: JobRun, out_dir: Path) -> str:
    py = sys.executable
    lint_black = run.run([py, "-m", "black", "--check", *V2_LINT_PATHS])
    lint_flake8 = run.run([py, "-m", "flake8", *FLAKE8_ARGS, *V2_LINT_PATHS])
    junit = out_dir / "pytest-junit.xml"
    tests = run.run([py, "-B", "-m", "pytest", "-q", f"--junitxml={junit}"])
    # Deuda legacy: informativa, no bloqueante (H11).
    legacy = subprocess.run(
        [py, "-m", "flake8", *FLAKE8_ARGS, *LEGACY_LINT_SCOPE],
        cwd=run.cwd,
        capture_output=True,
        text=True,
    )
    run.details = {
        "v2_lint_paths": list(V2_LINT_PATHS),
        "black_v2_exit": lint_black,
        "flake8_v2_exit": lint_flake8,
        "pytest_exit": tests,
        "legacy_flake8_violations_informative": len(legacy.stdout.splitlines()),
    }
    return PASS if lint_black == lint_flake8 == tests == 0 else FAIL


def job_backend_unit(run: JobRun, out_dir: Path) -> str:
    backend = run.cwd / "services" / "backend"
    if os.name == "nt":
        command = [str(backend / "mvnw.cmd"), "-B", "verify", "-DskipITs"]
    else:
        command = ["sh", "mvnw", "-B", "verify", "-DskipITs"]
    code = run.run(command, cwd=backend)
    reports = backend / "target" / "surefire-reports"
    copied = []
    if reports.is_dir():
        target = out_dir / "backend-unit-surefire"
        target.mkdir(exist_ok=True)
        for xml in sorted(reports.glob("*.xml")):
            shutil.copy2(xml, target / xml.name)
            copied.append(xml.name)
    run.details = {"surefire_reports": copied}
    return PASS if code == 0 else FAIL


def powershell_command() -> list[str] | None:
    if shutil.which("pwsh"):
        return ["pwsh", "-NoProfile", "-File"]
    if os.name == "nt" and shutil.which("powershell"):
        return ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File"]
    return None


def docker_available() -> bool:
    if not shutil.which("docker"):
        return False
    probe = subprocess.run(
        ["docker", "version", "--format", "{{.Server.Version}}"],
        capture_output=True,
        text=True,
    )
    return probe.returncode == 0 and bool(probe.stdout.strip())


def job_docker(run: JobRun, out_dir: Path) -> str:
    shell = powershell_command()
    missing = [
        name
        for name, ok in (
            ("PowerShell", shell is not None),
            ("Docker", docker_available()),
        )
        if not ok
    ]
    if missing:
        run.details = {"missing": missing}
        with run.log_path.open("a", encoding="utf-8") as log:
            log.write(f"\n{NOT_VERIFIABLE}: falta {', '.join(missing)}\n")
        return NOT_VERIFIABLE
    checks_dir = out_dir / run.name
    checks = ",".join(JOBS[run.name]["checks"])
    code = run.run(
        [*shell, HOST_CHECKS_SCRIPT, "-Check", checks, "-OutDir", str(checks_dir)]
    )
    summary = checks_dir / "summary.json"
    if summary.exists():
        run.details = json.loads(summary.read_text("utf-8-sig"))
    return PASS if code == 0 else FAIL


def tool_version(command: list[str]) -> str:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return "no disponible"
    lines = [
        line
        for line in (result.stdout + result.stderr).splitlines()
        if line.strip() and "JAVA_TOOL_OPTIONS" not in line
    ]
    return lines[0].strip() if lines else "no disponible"


def environment(cwd: Path) -> dict:
    try:
        autocrlf = git("config", "--get", "core.autocrlf", cwd=cwd)
    except subprocess.CalledProcessError:
        autocrlf = "unset"
    return {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "java": tool_version(["java", "-version"]),
        "docker": tool_version(
            ["docker", "version", "--format", "{{.Server.Version}}"]
        ),
        "git_core_autocrlf": autocrlf,
        "github_actions": os.environ.get("GITHUB_ACTIONS") == "true",
        "runner_os": os.environ.get("RUNNER_OS", ""),
        "github_run_url": (
            f"{os.environ['GITHUB_SERVER_URL']}/{os.environ['GITHUB_REPOSITORY']}"
            f"/actions/runs/{os.environ['GITHUB_RUN_ID']}"
            if os.environ.get("GITHUB_RUN_ID")
            else ""
        ),
    }


def branch_name(cwd: Path) -> str:
    """Rama del SHA validado (en un clon por SHA o en CI el HEAD puede estar suelto)."""
    branch = git("rev-parse", "--abbrev-ref", "HEAD", cwd=cwd)
    if branch != "HEAD":
        return branch
    return (
        os.environ.get("SAPI_GATE_BRANCH")
        or os.environ.get("GITHUB_REF_NAME")
        or "HEAD"
    )


def run_jobs(jobs: list[str], out_dir: Path, cwd: Path, allowed_tags) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    sha = head_sha(cwd)
    summary = {
        "schema": "sapi-merge-gate-v1",
        "sha": sha,
        "branch": branch_name(cwd),
        "started_utc": utc_now(),
        "environment": environment(cwd),
        "jobs": [],
    }
    for name in jobs:
        print(f"[{utc_now()}] {name} ...", flush=True)
        run = JobRun(name, out_dir, cwd)
        if name == "freeze":
            status = job_freeze(run, out_dir, allowed_tags)
        elif name == "python":
            status = job_python(run, out_dir)
        elif name == "backend-unit":
            status = job_backend_unit(run, out_dir)
        else:
            status = job_docker(run, out_dir)
        summary["jobs"].append(run.result(status))
        print(f"[{utc_now()}] {name}: {status}", flush=True)
    statuses = [job["status"] for job in summary["jobs"]]
    if FAIL in statuses:
        verdict = FAIL
    elif NOT_VERIFIABLE in statuses:
        verdict = NOT_VERIFIABLE
    else:
        verdict = PASS
    summary["finished_utc"] = utc_now()
    summary["verdict"] = verdict
    (out_dir / "gate_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def fresh_clone(sha: str, parent: Path) -> Path:
    """Clona el SHA en una carpeta nueva fuera del árbol, con el mismo origin."""
    target = Path(tempfile.mkdtemp(prefix="src-", dir=parent))
    subprocess.run(
        ["git", "clone", "--quiet", "--no-checkout", str(REPO_ROOT), str(target)],
        check=True,
    )
    subprocess.run(
        ["git", "-c", "advice.detachedHead=false", "checkout", "--quiet", sha],
        cwd=target,
        check=True,
    )
    origin = git("remote", "get-url", "origin")
    git("remote", "set-url", "origin", origin, cwd=target)
    return target


def exit_code(verdict: str) -> int:
    return {PASS: 0, FAIL: 1, NOT_VERIFIABLE: 2}[verdict]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--job", action="append", default=[], help="job o 'all'")
    parser.add_argument(
        "--out", type=Path, help="carpeta de evidencia (fuera del repo)"
    )
    parser.add_argument(
        "--fresh-clone",
        action="store_true",
        help="corre los jobs en un clon limpio del SHA (fallback local)",
    )
    parser.add_argument("--allow-tag", action="append", default=[])
    parser.add_argument("--inherit", metavar="SHA", help="verifica herencia de gate")
    parser.add_argument("--after-code-freeze", action="store_true")
    parser.add_argument("--evidence-valid", metavar="SHA")
    parser.add_argument("--list", action="store_true", help="lista los jobs")
    args = parser.parse_args(argv)

    if args.list:
        for name, job in JOBS.items():
            print(f"{name:<26} docker={job['docker']!s:<5} {job['kind']}")
        return 0

    if args.inherit:
        changed = git("diff", "--name-only", f"{args.inherit}..HEAD").splitlines()
        violations = inherit_violations(changed, args.after_code_freeze)
        status = PASS if not violations else FAIL
        print(f"INHERIT {status}: {args.inherit[:12]}..{head_sha()[:12]}")
        for path in violations:
            print(f"  fuera de la herencia: {path}")
        return exit_code(status)

    if args.evidence_valid:
        docker_jobs = [job for job in ordered_jobs(args.job) if JOBS[job]["docker"]]
        changed = git(
            "diff", "--name-only", f"{args.evidence_valid}..HEAD"
        ).splitlines()
        stale = {job: stale_evidence_paths(job, changed) for job in docker_jobs}
        for job, paths in stale.items():
            print(f"{job}: {'CADUCA' if paths else 'VIGENTE'} {', '.join(paths)}")
        return 1 if any(stale.values()) else 0

    jobs = ordered_jobs(args.job or ["freeze", "python", "backend-unit"])
    sha = head_sha()
    out_dir = (args.out or default_out_dir(sha)).resolve()
    if is_inside_repo(out_dir):
        raise SystemExit("la evidencia del gate debe quedar fuera del árbol de trabajo")
    allowed_tags = ALLOWED_TAGS + tuple(args.allow_tag)

    if args.fresh_clone:
        out_dir.mkdir(parents=True, exist_ok=True)
        clone = fresh_clone(sha, out_dir)
        command = [sys.executable, "-B", str(clone / "scripts" / "merge_gate.py")]
        for job in jobs:
            command += ["--job", job]
        for tag in args.allow_tag:
            command += ["--allow-tag", tag]
        command += ["--out", str(out_dir)]
        env = dict(os.environ, SAPI_GATE_BRANCH=branch_name(REPO_ROOT))
        return subprocess.run(command, cwd=clone, env=env).returncode

    summary = run_jobs(jobs, out_dir, REPO_ROOT, allowed_tags)
    print(f"GATE {summary['verdict']} sha={summary['sha'][:12]} evidencia={out_dir}")
    return exit_code(summary["verdict"])


if __name__ == "__main__":
    sys.exit(main())

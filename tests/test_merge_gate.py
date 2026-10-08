"""Tests del merge gate único (Quality Gate W0.9, Revisión 3 §3.1).

Garantizan que CI y el fallback son el mismo gate: cada job de
`.github/workflows/ci.yml` invoca `scripts/merge_gate.py` con su propio nombre,
los jobs Docker existen en `scripts/w0_host_checks.ps1`, el freeze check corre
en modo estricto, la evidencia queda fuera del árbol y la herencia de gate solo
cubre commits de evidencia (o docs después de CODE FREEZE).
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
CI_PATH = ROOT / ".github" / "workflows" / "ci.yml"
HOST_CHECKS = ROOT / "scripts" / "w0_host_checks.ps1"


def _load_merge_gate():
    spec = importlib.util.spec_from_file_location(
        "merge_gate", ROOT / "scripts" / "merge_gate.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


mg = _load_merge_gate()


@pytest.fixture(scope="module")
def ci() -> dict:
    return yaml.safe_load(CI_PATH.read_text(encoding="utf-8"))


def _gate_jobs_invoked(job: dict) -> list[str]:
    runs = " ".join(step.get("run", "") for step in job.get("steps", []))
    return re.findall(r"scripts/merge_gate\.py --job ([a-z-]+)", runs)


def test_every_ci_job_runs_the_same_named_merge_gate_job(ci):
    """CI y fallback comparten definiciones: job de CI == job de merge_gate."""
    for name, job in ci["jobs"].items():
        assert _gate_jobs_invoked(job) == [name], name
    assert set(ci["jobs"]) == set(mg.JOBS)


def test_ci_triggers_and_permissions(ci):
    """push en todas las ramas (no tags), PR, dispatch; solo lectura."""
    triggers = ci.get("on", ci.get(True))  # YAML 1.1 lee `on` como True
    assert triggers["push"] == {"branches": ["**"]}
    assert "pull_request" in triggers and "workflow_dispatch" in triggers
    assert ci["permissions"] == {"contents": "read"}
    assert "concurrency" in ci


def test_ci_does_not_apply_the_legacy_schema_nor_gate_on_legacy_lint():
    text = CI_PATH.read_text(encoding="utf-8")
    assert "docker/initdb" not in text
    assert "black --check src app tests" not in text
    assert "flake8 src app tests" not in text


def test_ci_checkouts_have_full_history(ci):
    for name, job in ci["jobs"].items():
        checkout = next(
            s for s in job["steps"] if s.get("uses", "").startswith("actions/checkout")
        )
        assert checkout["with"]["fetch-depth"] == 0, name


def test_docker_jobs_exist_in_the_host_checks_script():
    text = HOST_CHECKS.read_text(encoding="utf-8")
    known = re.search(r"\$KnownChecks = @\((.*?)\)", text, re.S).group(1)
    declared = set(re.findall(r'"([a-z-]+)"', known))
    for name, job in mg.JOBS.items():
        if job["docker"]:
            assert set(job["checks"]) <= declared, name


def test_sql_validation_and_flyway_integration_are_different_jobs():
    """C6: la validación SQL (psql) nunca se presenta como integración Flyway."""
    sql = mg.JOBS["sql-migration-validation"]
    flyway = mg.JOBS["flyway-integration"]
    assert "SQL MIGRATION VALIDATION" in sql["kind"] and "no Flyway" in sql["kind"]
    assert "REAL FLYWAY INTEGRATION VALIDATION" in flyway["kind"]
    assert set(sql["checks"]).isdisjoint(flyway["checks"])


def test_freeze_runs_first_in_any_selection():
    assert mg.ordered_jobs(["python", "freeze"])[0] == "freeze"
    assert mg.ordered_jobs(["all"]) == list(mg.JOBS)
    with pytest.raises(SystemExit):
        mg.ordered_jobs(["e2e"])


def test_freeze_command_is_strict():
    command = mg.freeze_command(Path("/tmp/out/freeze.json"), ("t-rc1",))
    for flag in ("--allow-dirty", "--skip-remote", "--skip-fingerprint"):
        assert flag not in command
    assert command[command.index("--allow-tag") + 1] == "t-rc1"


@pytest.mark.parametrize(
    "rows,expected",
    [
        ([{"check": "F1 HEAD", "status": "PASS"}], "PASS"),
        ([{"check": "F2 fingerprint Modelo D", "status": "SKIP"}], "FAIL"),
        ([{"check": "F1 refs remotos", "status": "SKIP"}], "FAIL"),
        ([{"check": "F8 worktree limpio", "status": "WARN"}], "FAIL"),
        ([{"check": "F6 db/migration", "status": "FAIL"}], "FAIL"),
        ([], "FAIL"),
    ],
)
def test_freeze_gate_treats_any_non_pass_row_as_fail(rows, expected):
    assert mg.freeze_gate_status({"checks": rows})[0] == expected


def test_allowed_tags_are_a_finite_list():
    assert len(mg.ALLOWED_TAGS) == 6
    assert all(not any(c in tag for c in "*?[") for tag in mg.ALLOWED_TAGS)
    assert mg.ALLOWED_TAGS[-1].endswith("-final")


@pytest.mark.parametrize(
    "changed,after_freeze,violations",
    [
        (["artifacts/hito2/w0/host/summary.json"], False, []),
        (["docs/hito2/cierre-sprint2.md"], False, ["docs/hito2/cierre-sprint2.md"]),
        (["docs/hito2/cierre-sprint2.md"], True, []),
        (
            ["src/inference/prototype_service.py"],
            True,
            ["src/inference/prototype_service.py"],
        ),
        (
            ["artifacts/hito1/reproducibility/manifest.json"],
            True,
            ["artifacts/hito1/reproducibility/manifest.json"],
        ),
    ],
)
def test_gate_inheritance_only_covers_evidence_and_late_docs(
    changed, after_freeze, violations
):
    assert mg.inherit_violations(changed, after_freeze) == violations


def test_docker_evidence_goes_stale_when_its_inputs_change():
    assert mg.stale_evidence_paths("flyway-integration", ["db/migration/V004__x.sql"])
    assert not mg.stale_evidence_paths("flyway-integration", ["app/app.py"])
    assert mg.stale_evidence_paths("container-smoke", ["src/inference/x.py"])
    assert not mg.stale_evidence_paths("sql-migration-validation", ["docs/x.md"])


def test_default_evidence_folder_is_outside_the_worktree(monkeypatch, tmp_path):
    monkeypatch.delenv("RUNNER_TEMP", raising=False)
    assert not mg.is_inside_repo(mg.default_out_dir("a" * 40))
    monkeypatch.setenv("RUNNER_TEMP", str(tmp_path))
    assert mg.default_out_dir("b" * 40) == tmp_path / "sapi-gate" / ("b" * 12)
    assert mg.is_inside_repo(ROOT / "artifacts")


def test_main_refuses_evidence_inside_the_worktree():
    with pytest.raises(SystemExit, match="fuera del árbol"):
        mg.main(["--job", "freeze", "--out", str(ROOT / "artifacts" / "gate")])


def test_docker_job_without_docker_is_not_verifiable_never_pass(monkeypatch, tmp_path):
    monkeypatch.setattr(mg.shutil, "which", lambda _name: None)
    run = mg.JobRun("flyway-integration", tmp_path, ROOT)
    assert mg.job_docker(run, tmp_path) == mg.NOT_VERIFIABLE
    assert run.details["missing"] == ["PowerShell", "Docker"]


def test_v2_lint_paths_exist():
    for path in mg.V2_LINT_PATHS:
        assert (ROOT / path).exists(), path

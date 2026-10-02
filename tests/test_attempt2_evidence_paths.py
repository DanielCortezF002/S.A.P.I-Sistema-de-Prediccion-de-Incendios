"""SAPI-72: Attempt 2 evidence defaults derive from the checkout, never a fixed drive."""

from __future__ import annotations

from pathlib import Path

from src.ops.attempt2_operator import run_store, tooling_paths

REPO = Path(__file__).resolve().parents[1]
EVIDENCE = REPO.parent / "SAPI-71-evidence"


def test_default_evidence_root_is_next_to_the_checkout(monkeypatch):
    monkeypatch.delenv("SAPI_ATTEMPT2_EVIDENCE_ROOT", raising=False)
    assert run_store.DEFAULT_EVIDENCE_ROOT == EVIDENCE / "attempt2"
    assert run_store.resolve_evidence_root() == EVIDENCE / "attempt2"


def test_env_and_explicit_root_take_precedence(monkeypatch, tmp_path):
    monkeypatch.setenv("SAPI_ATTEMPT2_EVIDENCE_ROOT", str(tmp_path / "env"))
    assert run_store.resolve_evidence_root() == tmp_path / "env"
    assert run_store.resolve_evidence_root(tmp_path / "cli") == tmp_path / "cli"


def test_default_planning_is_next_to_the_checkout():
    assert tooling_paths.DEFAULT_PLANNING == EVIDENCE / "planning"


def test_tools_env_takes_precedence(monkeypatch, tmp_path):
    monkeypatch.setenv("SAPI_ATTEMPT2_EVIDENCE_TOOLS", str(tmp_path))
    assert tooling_paths.evidence_tools_root() == tmp_path
    monkeypatch.setenv("SAPI_ATTEMPT2_EVIDENCE_TOOLS", str(tmp_path / "missing"))
    assert tooling_paths.evidence_tools_root() is None


def test_no_operator_module_pins_a_drive_path():
    package = REPO / "src" / "ops" / "attempt2_operator"
    offenders = [
        p.relative_to(REPO).as_posix()
        for p in package.rglob("*.py")
        if "portafolio y seminario" in p.read_text(encoding="utf-8")
    ]
    assert offenders == []

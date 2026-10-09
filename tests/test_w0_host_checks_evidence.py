"""Regresión de la escritura de evidencia de `scripts/w0_host_checks.ps1`.

Incidente df29550 (HARNESS_EVIDENCE_OUTPUT_FAILURE): la carpeta de evidencia
desapareció a mitad de la corrida (estaba en el Escritorio sincronizado por
OneDrive). `Write-Text`/`Add-Log` lanzaban excepciones: el `catch` del bucle
principal volvía a escribir y relanzaba, así que container-smoke-backend
terminó en PASS con aserciones a medias, flyway-integration en "no-assertions",
y summary.json, manifest.sha256 y el ZIP no se generaron.

Estos tests ejecutan el script real con PowerShell y un `docker` falso
(determinista: nunca construye imágenes) y verifican que:
- OutDir se crea si no existe y se reutiliza sin borrar nada si existe;
- varios checks seguidos (incluido backend -> flyway) persisten .txt y .json;
- summary.json y manifest.sha256 siempre se escriben y el manifest verifica;
- perder OutDir a mitad de la corrida es un FAIL explícito (exit 3,
  HARNESS_EVIDENCE_OUTPUT_FAILURE), nunca un PASS;
- un OutDir imposible de crear termina con exit 3, sin excepción.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "w0_host_checks.ps1"
PWSH = os.environ.get("SAPI_PWSH") or shutil.which("pwsh")

pytestmark = pytest.mark.skipif(
    PWSH is None or os.name == "nt",
    reason="requiere PowerShell (pwsh o SAPI_PWSH) y un shell POSIX para el docker falso",
)

HEALTHY_DOCKER = """#!/bin/sh
case "$*" in
  *"volume ls"*) [ -n "$SAPI_TEST_LOSE_OUTDIR" ] && rm -rf "$SAPI_TEST_LOSE_OUTDIR"; echo "";;
  *compose*) echo 2.30.0;;
  *) echo 29.0.0;;
esac
exit 0
"""

DAEMON_DOWN_DOCKER = """#!/bin/sh
echo "Cannot connect to the Docker daemon (fake)" >&2
exit 1
"""


def _fake_docker(tmp_path: Path, body: str) -> Path:
    bin_dir = tmp_path / "fakebin"
    bin_dir.mkdir()
    docker = bin_dir / "docker"
    docker.write_text(body, encoding="utf-8")
    docker.chmod(0o755)
    return bin_dir


def _run(
    checks: str, out_dir: Path, bin_dir: Path, **env_extra
) -> subprocess.CompletedProcess:
    env = dict(os.environ, PATH=f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    env.pop("SAPI_W0_FAULT_LOSE_OUTDIR_BEFORE", None)
    env.update(env_extra)
    return subprocess.run(
        [
            PWSH,
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(SCRIPT),
            "-Check",
            checks,
            "-OutDir",
            str(out_dir),
        ],
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _assert_manifest_verifies(out_dir: Path) -> list[str]:
    lines = [
        ln
        for ln in (out_dir / "manifest.sha256").read_text("utf-8-sig").splitlines()
        if ln
    ]
    names = []
    for line in lines:
        digest, name = line.split("  ", 1)
        assert hashlib.sha256((out_dir / name).read_bytes()).hexdigest() == digest, name
        names.append(name)
    assert "summary.json" in names
    return names


def _assert_check_persisted(out_dir: Path, name: str) -> dict:
    assert (out_dir / f"{name}.txt").is_file(), name
    data = _json(out_dir / f"{name}.json")
    assert data["check"] == name
    return data


def test_missing_outdir_is_created_and_evidence_persisted(tmp_path):
    out = tmp_path / "does" / "not" / "exist"
    result = _run("selftest", out, _fake_docker(tmp_path, HEALTHY_DOCKER))
    assert result.returncode == 0, result.stdout + result.stderr
    assert _assert_check_persisted(out, "selftest")["status"] == "PASS"
    summary = _json(out / "summary.json")
    assert summary["harness_evidence"]["status"] == "PASS"
    assert summary["harness_evidence"]["write_errors"] == []
    assert set(_assert_manifest_verifies(out)) >= {
        "selftest.json",
        "selftest.txt",
        "summary.json",
    }


def test_existing_outdir_is_reused_and_nothing_is_deleted(tmp_path):
    out = tmp_path / "evidence"
    out.mkdir()
    keep = out / "keep.txt"
    keep.write_text("pre-existing", encoding="utf-8")
    result = _run("selftest", out, _fake_docker(tmp_path, HEALTHY_DOCKER))
    assert result.returncode == 0, result.stdout + result.stderr
    assert keep.read_text(encoding="utf-8") == "pre-existing"
    _assert_check_persisted(out, "selftest")
    _assert_manifest_verifies(out)


def test_consecutive_checks_persist_txt_and_json(tmp_path):
    out = tmp_path / "evidence"
    result = _run("selftest,hostfacts", out, _fake_docker(tmp_path, HEALTHY_DOCKER))
    assert result.returncode in (0, 1), result.stdout + result.stderr
    for name in ("selftest", "hostfacts"):
        _assert_check_persisted(out, name)
    summary = _json(out / "summary.json")
    assert [c["check"] for c in summary["checks"]] == ["selftest", "hostfacts"]
    assert summary["harness_evidence"]["status"] == "PASS"
    _assert_manifest_verifies(out)


def test_backend_then_flyway_keep_outdir_and_persist_both(tmp_path):
    """La secuencia exacta del incidente: backend seguido de flyway."""
    out = tmp_path / "evidence"
    result = _run(
        "container-smoke-backend,flyway-integration",
        out,
        _fake_docker(tmp_path, DAEMON_DOWN_DOCKER),
    )
    assert result.returncode == 1, (
        result.stdout + result.stderr
    )  # checks FAIL, harness OK
    for name in ("container-smoke-backend", "flyway-integration"):
        data = _assert_check_persisted(out, name)
        assert data["status"] == "FAIL" and "docker" in data["failures"]
        assert "no-assertions" not in data["failures"]
    summary = _json(out / "summary.json")
    assert [c["check"] for c in summary["checks"]] == [
        "container-smoke-backend",
        "flyway-integration",
    ]
    assert summary["harness_evidence"]["status"] == "PASS"
    _assert_manifest_verifies(out)


def test_outdir_lost_mid_check_is_explicit_harness_failure(tmp_path):
    """Reproduce el incidente: OutDir desaparece durante un check que pasaría."""
    out = tmp_path / "evidence"
    result = _run(
        "selftest,hostfacts",
        out,
        _fake_docker(tmp_path, HEALTHY_DOCKER),
        SAPI_TEST_LOSE_OUTDIR=str(out),
    )
    assert result.returncode == 3, result.stdout + result.stderr
    assert "HARNESS_EVIDENCE_OUTPUT_FAILURE" in result.stdout
    hostfacts = _assert_check_persisted(out, "hostfacts")
    assert hostfacts["status"] == "FAIL"
    assert "evidence-write-error" in hostfacts["failures"]
    summary = _json(out / "summary.json")
    assert summary["overall"] == "FAIL"
    assert summary["harness_evidence"]["status"] == "FAIL"
    assert summary["harness_evidence"]["write_errors"]
    _assert_manifest_verifies(out)


def test_fault_injection_never_turns_a_passing_check_into_pass(tmp_path):
    out = tmp_path / "evidence"
    result = _run(
        "selftest",
        out,
        _fake_docker(tmp_path, HEALTHY_DOCKER),
        SAPI_W0_FAULT_LOSE_OUTDIR_BEFORE="selftest",
    )
    assert result.returncode == 3, result.stdout + result.stderr
    selftest = _json(out / "selftest.json")
    assert selftest["status"] == "FAIL"
    assert selftest["failures"] == ["evidence-write-error"]
    lost = list(tmp_path.glob("evidence.lost-*"))
    assert len(lost) == 1  # la carpeta original se movió, no se borró


def test_uncreatable_outdir_exits_3_without_crashing(tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("a file, not a folder", encoding="utf-8")
    result = _run("selftest", blocker / "out", _fake_docker(tmp_path, HEALTHY_DOCKER))
    assert result.returncode == 3, result.stdout + result.stderr
    assert "HARNESS_EVIDENCE_OUTPUT_FAILURE" in result.stdout

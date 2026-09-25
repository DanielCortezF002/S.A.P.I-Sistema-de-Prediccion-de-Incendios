"""Readiness del Output Plane y OUTPUT_PLANE_MANIFEST (src/output/readiness.py)."""

from __future__ import annotations

import hashlib
import json
import shutil

import pytest

from src.output import readiness as rd


@pytest.fixture(scope="module")
def results():
    return rd.run_checks()


def test_all_checks_pass_or_only_node_is_missing(results):
    assert [r["name"] for r in results] == [name for name, _ in rd.CHECKS]
    expected = rd.READY if shutil.which("node") else rd.INCOMPLETE
    assert rd.overall(results) == expected, results
    assert all(
        r["status"] == rd.PASS
        for r in results
        if "python_js" not in r["name"] and "n8n_policy" not in r["name"]
    )


def test_manifest_is_versioned_deterministic_and_self_fingerprinted(results):
    a, b = rd.build_manifest(results), rd.build_manifest(results)
    assert a == b
    body = {k: v for k, v in a.items() if k != "manifest_fingerprint"}
    canonical = json.dumps(
        body, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    assert a["manifest_fingerprint"] == hashlib.sha256(canonical.encode()).hexdigest()
    assert a["manifest_schema_version"] == "sapi-output-plane-manifest-v1"
    assert a["bridge_contract_version"] == "sapi-output-v1"
    assert a["alert_schema_version"] == "sapi-alert-v1"
    assert a["notification_identity_recipe"] == "sapi-alert-v1/alert_fingerprint"
    assert a["replay_artifact_schema_version"] == "sapi-accepted-run-v1"
    assert a["suppression_policy_version"] == "sapi-suppression-v1"
    assert len(a["output_code"]["sources_sha256"]) == 64
    assert a["authorization"].startswith("NONE")  # evidencia, no autorización


def test_sources_hash_ignores_line_endings(tmp_path, monkeypatch):
    (tmp_path / "a.py").write_bytes(b"x = 1\r\ny = 2\r\n")
    monkeypatch.setattr(rd, "REPO_ROOT", tmp_path)
    crlf = rd.sources_sha256(("a.py",))
    (tmp_path / "a.py").write_bytes(b"x = 1\ny = 2\n")
    assert rd.sources_sha256(("a.py",)) == crlf


def test_failed_check_means_not_ready(monkeypatch):
    def broken(ctx):
        raise rd.CheckFailed("simulado")

    monkeypatch.setattr(
        rd, "CHECKS", (("control_center_adapter", broken),) + rd.CHECKS[:1]
    )
    results = rd.run_checks()
    assert rd.overall(results) == rd.NOT_READY
    assert results[0] == {
        "name": "control_center_adapter",
        "status": "FAIL",
        "detail": "simulado",
    }


def test_missing_node_means_incomplete_not_ready(monkeypatch):
    monkeypatch.setattr(rd.shutil, "which", lambda name: None)
    monkeypatch.setattr(
        rd, "CHECKS", tuple(c for c in rd.CHECKS if "python_js" in c[0])
    )
    results = rd.run_checks()
    assert results[0]["status"] == rd.SKIP and rd.overall(results) == rd.INCOMPLETE


def test_cli_exit_code_and_manifest_file(tmp_path, capsys):
    out = tmp_path / "OUTPUT_PLANE_MANIFEST.json"
    code = rd.main(["--out", str(out)])
    printed = json.loads(capsys.readouterr().out)
    assert printed == json.loads(out.read_text(encoding="utf-8"))
    assert (
        code
        == {rd.READY: 0, rd.NOT_READY: 1, rd.INCOMPLETE: 2}[
            printed["readiness"]["status"]
        ]
    )
    assert printed["readiness"]["status"] != rd.NOT_READY

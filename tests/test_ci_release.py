"""Offline release failure matrix. Fixtures never touch operational resources."""

import json
from pathlib import Path
import subprocess
import sys

import pytest

from scripts import ci_release_core as core
from scripts import ci_release_manifests as manifests


@pytest.fixture
def repository(tmp_path):
    root = tmp_path / "repo con espacios ñ"
    root.mkdir()
    core.git(root, "init")
    core.git(root, "config", "user.email", "fixture@example.invalid")
    core.git(root, "config", "user.name", "Fixture")
    (root / "source.py").write_text("committed = 1\n", encoding="utf-8")
    core.git(root, "add", ".")
    core.git(root, "commit", "-m", "fixture")
    return root, core.git(root, "rev-parse", "HEAD")


def sample():
    result = {
        "schema_version": 1,
        "kind": "RC_GATE_RESULT",
        "candidate": {"sha": "a" * 40, "tree": "b" * 40},
        "checks": [{"id": "RC-TEST-FIXTURE", "status": "PASS", "required": True}],
        "status": "PASS",
        "cache_identity": "fixture",
    }
    result["stable_result_fingerprint"] = core.fingerprint(core.stable_result(result))
    return result


@pytest.mark.parametrize("sha", ["main", "HEAD", "abcd", "x" * 40, "a" * 39])
def test_wrong_candidate_sha(repository, sha):
    with pytest.raises(ValueError):
        core.resolve(repository[0], sha)


def test_missing_commit(repository):
    with pytest.raises(subprocess.CalledProcessError):
        core.resolve(repository[0], "0" * 40)


def test_dirty_source_cannot_substitute(repository, tmp_path):
    root, sha = repository
    (root / "source.py").write_text("DIRTY_SECRET_SUBSTITUTION", encoding="utf-8")
    (root / "untracked.txt").write_text("untracked", encoding="utf-8")
    target = tmp_path / "export con espacios"
    result = core.export(root, sha, target)
    assert result["files"] == 1
    assert (target / "source.py").read_text() == "committed = 1\n"
    assert not (target / "untracked.txt").exists()


def test_export_repeatable(repository, tmp_path):
    first = core.export(*repository, tmp_path / "one")
    second = core.export(*repository, tmp_path / "two")
    assert first == second


def test_manifest_missing(tmp_path):
    assert (
        manifests.verify("data", tmp_path / "absent", tmp_path, "a" * 40)["status"]
        == "FAIL"
    )


@pytest.mark.parametrize("kind", ["data", "output"])
def test_manifest_corrupt(kind, tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text("{", encoding="utf-8")
    assert manifests.verify(kind, path, tmp_path, "a" * 40)["status"] == "FAIL"


def test_required_lane_missing(repository):
    root, sha = repository
    assert (
        manifests.ancestry(root, sha, {"missing": "0" * 40})["missing"]["status"]
        == "FAIL"
    )
    assert (
        manifests.ancestry(root, sha, {"present": sha})["present"]["status"] == "PASS"
    )


@pytest.mark.parametrize(
    "identifier", ["RC-SCI-MODEL", "RC-SCI-RANKING", "RC-TEST-HOST", "RC-LINT-DELTA"]
)
def test_failure_never_masked(identifier):
    assert (
        core.aggregate([{"id": identifier, "status": "FAIL"}, {"status": "INCOMPLETE"}])
        == "FAIL"
    )


@pytest.mark.parametrize("state", ["INCOMPLETE", "NOT_RUN", "UNKNOWN", None])
def test_unavailable_never_passes(state):
    assert core.aggregate([{"status": state}]) == "INCOMPLETE"


def test_host_nonzero_and_docker_unavailable(tmp_path):
    runner = core.ReleaseRunner(tmp_path, tmp_path / "evidence")
    assert (
        runner.run("host", [sys.executable, "-c", "raise SystemExit(7)"])["status"]
        == "FAIL"
    )
    assert (
        runner.run("docker", [str(tmp_path / "missing.exe")])["status"] == "INCOMPLETE"
    )


def test_timeout(tmp_path):
    runner = core.ReleaseRunner(tmp_path, tmp_path / "evidence")
    result = runner.run(
        "timeout", [sys.executable, "-c", "import time; time.sleep(5)"], timeout=0.1
    )
    assert (result["status"], result["reason"]) == ("INCOMPLETE", "TIMEOUT")


def test_quality_multiset_detects_regression():
    before = {"black": ["old.py|one"], "flake8": ["old.py|E1|one"]}
    after = {"black": ["old.py|one"], "flake8": ["old.py|E1|one", "old.py|E1|one"]}
    assert core.quality_delta(before, before, ["old.py"])["status"] == "PASS"
    assert core.quality_delta(before, after, ["old.py"])["flake8"]["new"] == [
        "old.py|E1|one"
    ]
    assert core.quality_delta(before, after, ["old.py"])["status"] == "FAIL"


def test_secret_hygiene_utf8(tmp_path, monkeypatch):
    secret = "fixture secret+ñ/123456"
    monkeypatch.setenv("NASA_FIRMS_API_KEY", secret)
    value = {
        "log": secret
        + " Authorization: Bearer xyz\nCookie: private\nhttps://x.invalid/?token=abc&usuario=daniel"
    }
    path = tmp_path / "result.json"
    core.write_json(path, value)
    text = path.read_text(encoding="utf-8")
    assert (
        secret not in text and "token=abc" not in text and "Cookie: private" not in text
    )
    assert json.loads(text)


def test_corrupt_machine_result():
    result = sample()
    result["candidate"]["sha"] = "c" * 40
    with pytest.raises(ValueError):
        core.validate_result(result)


def test_checks_bound_to_fingerprint():
    result = sample()
    result["checks"][0]["id"] = "SUBSTITUTED"
    with pytest.raises(ValueError):
        core.validate_result(result)


def test_fingerprint_repeatable_excludes_clocks_paths():
    left, right = sample(), sample()
    left.update(started_at="yesterday", duration=1, evidence_path="C:/a")
    right.update(started_at="tomorrow", duration=999, evidence_path="D:/b")
    assert core.fingerprint(core.stable_result(left)) == core.fingerprint(
        core.stable_result(right)
    )
    assert core.compare(left, right) == {}


def test_resume_never_reuses_other_identity_or_corruption():
    result = sample()
    assert core.reusable(result, "fixture")
    assert not core.reusable(result, "another-sha")
    result["status"] = "FAIL"
    assert not core.reusable(result, "fixture")


def test_compare_candidate_and_findings():
    left, right = sample(), sample()
    right["candidate"]["sha"] = "c" * 40
    right["stable_result_fingerprint"] = core.fingerprint(core.stable_result(right))
    assert set(core.compare(left, right)) == {"candidate"}


@pytest.mark.parametrize("field", ["fingerprint", "model", "authorization"])
def test_data_tamper_rejected_before_history(field):
    body = {"schema_version": 1, "kind": "DATA_PLANE_MANIFEST"}
    doc = {"schema_version": 1, "identity": body, "fingerprint": core.fingerprint(body)}
    if field == "fingerprint":
        doc["fingerprint"] = "0" * 64
    else:
        body[field] = "tampered"
    with pytest.raises(ValueError):
        manifests.verify_data(doc, Path.cwd(), "a" * 40)


def test_output_wrong_fingerprint():
    doc = {
        "manifest_schema_version": "sapi-output-plane-manifest-v1",
        "manifest_fingerprint": "0" * 64,
    }
    with pytest.raises(ValueError):
        manifests.verify_output(doc, Path.cwd(), "a" * 40)

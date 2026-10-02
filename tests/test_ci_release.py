"""Offline release failure matrix. Fixtures never touch operational resources."""

import json
import copy
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
    result.update(
        {
            k: {}
            for k in (
                "baseline",
                "gate_identity",
                "environment_identity",
                "tests",
                "coverage",
                "sentinels",
                "component_manifests",
            )
        }
    )
    result.update(findings=[], authorization=False, remote_github_ci="NOT VERIFIED")
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


def test_export_git_metadata_is_exact_and_self_contained(repository, tmp_path):
    root, sha = repository
    target = tmp_path / "source"
    core.export(root, sha, target)
    core.attach_git_metadata(root, sha, target)
    assert core.resolve(target, sha) == core.resolve(root, sha)
    assert core.git(target, "status", "--porcelain") == ""
    assert core.git(target, "remote") == ""
    assert not (target / ".git/objects/info/alternates").exists()
    assert core.git(target, "rev-list", "--count", "HEAD") == "1"


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


@pytest.fixture
def data_document(monkeypatch):
    policy = {
        "components": {"firms": {"sha": "a" * 40}},
        "expected_current": {"present": False},
        "model": {"sha256": "1" * 64},
        "baseline": {"sha256": "2" * 64},
        "topography": {
            "table_sha256": "3" * 64,
            "grid_sha256": "4" * 64,
            "files": {"dem.tif": "5" * 64},
        },
    }
    body = {
        "schema_version": 1,
        "kind": "DATA_PLANE_MANIFEST",
        "code_identity": {"sha": "a" * 40, "tree": "b" * 40, "clean": True},
        "policy_sha256": core.fingerprint(policy),
        "components": policy["components"],
        "data_readiness_status": "PREPARED",
        "findings": [],
        "current_state": policy["expected_current"],
        "data_ready_for_scoring": "NOT_EVALUATED",
        "authorizations": {
            k: False for k in ("attempt2", "writers", "telegram", "schedule")
        },
        "model": {"status": "PASS", "sha256": "1" * 64},
        "baseline": {"status": "PASS", "sha256": "2" * 64},
        "topography": {
            "status": "PASS",
            "table_sha256": "3" * 64,
            "grid_sha256": "4" * 64,
            "files": {"dem.tif": {"sha256": "5" * 64}},
        },
    }
    monkeypatch.setattr(manifests, "blob", lambda *a: json.dumps(policy).encode())
    monkeypatch.setattr(
        manifests, "resolve", lambda *a: {"sha": "a" * 40, "tree": "b" * 40}
    )
    monkeypatch.setattr(manifests, "ancestry", lambda *a: {"data": {"status": "PASS"}})
    return {
        "schema_version": 1,
        "identity": body,
        "fingerprint": core.fingerprint(body),
    }


def test_data_producer_identity_recipe(data_document):
    result = manifests.verify_data(data_document, Path.cwd(), "a" * 40)
    assert result["status"] == "PASS"
    assert result["readiness"] == "PREPARED" and result["authorization"] is False


@pytest.mark.parametrize(
    "mutation", ["model", "baseline", "tree", "authorization", "readiness"]
)
def test_rehashed_wrong_identity_still_rejected(data_document, mutation):
    doc = copy.deepcopy(data_document)
    body = doc["identity"]
    if mutation in ("model", "baseline"):
        body[mutation]["sha256"] = "f" * 64
    elif mutation == "tree":
        body["code_identity"]["tree"] = "f" * 40
    elif mutation == "authorization":
        body["authorizations"]["writers"] = True
    else:
        body["data_readiness_status"] = "READY"
    doc["fingerprint"] = core.fingerprint(body)
    with pytest.raises(ValueError):
        manifests.verify_data(doc, Path.cwd(), "a" * 40)


def test_manifest_expected_fingerprint_enforced(data_document):
    with pytest.raises(ValueError):
        manifests.verify_data(data_document, Path.cwd(), "a" * 40, expected="f" * 64)


def test_candidate_missing_data_history(data_document, monkeypatch):
    monkeypatch.setattr(manifests, "ancestry", lambda *a: {"data": {"status": "FAIL"}})
    with pytest.raises(ValueError, match="history"):
        manifests.verify_data(data_document, Path.cwd(), "c" * 40)


def test_blob_tampering_detected(repository, tmp_path, monkeypatch):
    original = core.tarfile.TarFile.extractall

    def corrupt(self, target, **kwargs):
        original(self, target, **kwargs)
        (target / "source.py").write_bytes(b"substituted")

    monkeypatch.setattr(core.tarfile.TarFile, "extractall", corrupt)
    with pytest.raises(ValueError, match="exported bytes"):
        core.export(*repository, tmp_path / "tampered-export")


@pytest.mark.parametrize(
    "actual,expected,status",
    [
        ("wrong", "frozen", "FAIL"),
        ("frozen", "frozen", "PASS"),
        (None, "frozen", "INCOMPLETE"),
    ],
)
def test_frozen_identity_outcome(actual, expected, status):
    assert core.match_status(actual, expected) == status


def test_generated_report_sealing_leaves_sources_untouched(tmp_path):
    source = tmp_path / "candidate"
    source.mkdir()
    raw = "Authorization: Bearer private_fixture_123456789\n"
    (source / "test_fixture.txt").write_text(raw, encoding="utf-8")
    (tmp_path / "report.txt").write_text(raw, encoding="utf-8")
    assert core.seal_reports(tmp_path)["status"] == "PASS"
    assert "private_fixture" not in (tmp_path / "report.txt").read_text()
    assert (source / "test_fixture.txt").read_text() == raw


@pytest.fixture
def release(monkeypatch):
    import importlib

    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    return importlib.import_module("ci_release")


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ci_release.py"


def test_script_entrypoint_runs_main():
    # Without the __main__ guard `python ci_release.py gate ...` exited 0 doing nothing.
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True
    )
    assert proc.returncode == 0
    assert "gate" in proc.stdout and "compare" in proc.stdout


def test_script_entrypoint_rejects_incomplete_gate():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "gate"], capture_output=True, text=True
    )
    assert proc.returncode == 2
    assert "--candidate-sha" in proc.stderr


def test_evidence_root_default_and_env_override(release, monkeypatch, tmp_path):
    import importlib

    monkeypatch.delenv("SAPI_RELEASE_GATE_EVIDENCE", raising=False)
    assert importlib.reload(release).EVIDENCE == Path(
        r"C:\SAPI-71-evidence\release-gates"
    )
    monkeypatch.setenv("SAPI_RELEASE_GATE_EVIDENCE", str(tmp_path))
    try:
        assert importlib.reload(release).EVIDENCE == tmp_path
    finally:
        monkeypatch.delenv("SAPI_RELEASE_GATE_EVIDENCE")
        importlib.reload(release)


@pytest.mark.parametrize(
    "host,port",
    [
        ("example.invalid", 443),
        ("127.0.0.1", 5678),
        ("127.0.0.1", 8600),
        ("1.1.1.1", 443),
    ],
)
def test_network_guard_denies_external_and_operational(release, tmp_path, host, port):
    runner = core.ReleaseRunner(tmp_path, tmp_path / "evidence")
    runner.env["PYTHONPATH"] = str(release.network_guard(tmp_path, 1))
    code = (
        "import socket\ntry:\n socket.create_connection("
        + repr((host, port))
        + ",timeout=1)\nexcept PermissionError:\n pass\nelse:\n raise SystemExit(8)"
    )
    assert runner.run("network_guard", [sys.executable, "-c", code])["status"] == "PASS"


@pytest.mark.parametrize("host", [False, True])
def test_docker_partial_creation_cleans_only_owned_resources(release, tmp_path, host):
    import ci_local_docker

    source = tmp_path / "source"
    source.mkdir()
    (source / "Dockerfile.analytics").write_text("FROM fixture\n", encoding="utf-8")

    class FakeRunner(core.ReleaseRunner):
        def run(self, name, command, required=True, **kwargs):
            result = {
                "name": name,
                "status": "FAIL" if name == "docker_database" else "PASS",
                "required": required,
                "command": command,
                "evidence": {},
            }
            self.steps.append(result)
            return result

    runner = FakeRunner(source, tmp_path / "evidence")
    result = ci_local_docker.run_docker(
        runner,
        {"tree_sha": "a" * 40, "dirty_state": False},
        True,
        source_context=source,
        host_callback=(lambda port: None) if host else None,
    )
    assert result == "BLOCKED"
    cleanup = [step for step in runner.steps if step["name"].startswith("cleanup_")]
    assert len(cleanup) == (3 if host else 2)
    for step in cleanup:
        assert "sapi-ci-" in step["command"][-1]
        assert "-v" not in step["command"] and "volume" not in step["command"]


def test_database_readiness_probes_final_server_over_tcp():
    import ci_local_docker

    command = ci_local_docker.database_ready_command("sapi-ci-db-fixture")
    assert command[:4] == ["docker", "exec", "sapi-ci-db-fixture", "pg_isready"]
    # A socket-only probe also answers the image's temporary init server.
    host = command.index("-h")
    assert command[host + 1] == "127.0.0.1"


def test_test_identity_binds_cases_not_duration(tmp_path):
    report = tmp_path / "junit.xml"
    report.write_text(
        '<testsuite><testcase name="first" time="1"/></testsuite>', encoding="utf-8"
    )
    first = core.test_identity(report)
    report.write_text(
        '<testsuite><testcase name="first" time="2"/></testsuite>', encoding="utf-8"
    )
    assert core.test_identity(report) == first
    report.write_text(
        '<testsuite><testcase name="second" time="2"/></testsuite>', encoding="utf-8"
    )
    assert core.test_identity(report) != first


@pytest.mark.parametrize(
    "change", ["same", "candidate", "packages", "probe_failure", "empty"]
)
def test_environment_resume_contract(change):
    receipt = {
        "cache_identity": "candidate-tree-tooling-config",
        "packages_sha256": "packages",
    }
    probe = {"status": "PASS", "evidence": {"sha256": "packages"}}
    identity = receipt["cache_identity"]
    if change == "candidate":
        identity = "another-candidate"
    elif change == "packages":
        probe["evidence"]["sha256"] = "different"
    elif change == "probe_failure":
        probe["status"] = "FAIL"
    elif change == "empty":
        receipt = {}
    assert core.environment_reusable(receipt, identity, probe) is (change == "same")


@pytest.mark.parametrize(
    "status,prepared,ready,writers,attempt2,expected",
    [
        ("PREPARED", True, False, False, False, "PASS"),
        ("PREPARED", False, False, False, False, "INCOMPLETE"),
        ("PREPARED", True, True, False, False, "INCOMPLETE"),
        ("PREPARED", True, False, None, False, "INCOMPLETE"),
        ("PREPARED", True, False, True, False, "FAIL"),
        ("PREPARED", True, False, False, True, "FAIL"),
        ("FAIL", False, False, False, False, "INCOMPLETE"),
        ("UNKNOWN", False, False, False, False, "INCOMPLETE"),
        ("PASS", True, True, True, False, "FAIL"),
    ],
)
def test_handshake_preparation_never_implies_authorization(
    status, prepared, ready, writers, attempt2, expected
):
    report = {
        "status": status,
        "prepared": prepared,
        "ready": ready,
        "writers_authorized": writers,
        "attempt2_authorized": attempt2,
    }
    assert core.handshake_status(report) == expected


@pytest.mark.parametrize("modern", [False, True])
def test_handshake_worker_supports_both_consumer_signatures(
    tmp_path, monkeypatch, modern
):
    from types import SimpleNamespace
    from scripts import ci_release_worker as worker

    monkeypatch.setattr(sys, "path", list(sys.path))
    module = tmp_path / "src/ops/attempt2_operator/data_plane_manifest.py"
    module.parent.mkdir(parents=True)
    module.write_text("# fixture", encoding="utf-8")
    manifest = tmp_path / "input.json"
    manifest.write_text(
        json.dumps({"identity": {"code_identity": {"sha": "a" * 40}}}), encoding="utf-8"
    )

    def new_consumer(path, *, expected_code_sha):
        assert expected_code_sha == "a" * 40
        return {
            "status": "PREPARED",
            "prepared": True,
            "ready": False,
            "writers_authorized": False,
            "attempt2_authorized": False,
        }

    def old_consumer(path):
        return {"status": "FAIL", "findings": [{"id": "DM-005"}]}

    monkeypatch.setitem(
        sys.modules,
        "src.ops.attempt2_operator.data_plane_manifest",
        SimpleNamespace(
            verify_data_plane_manifest=new_consumer if modern else old_consumer
        ),
    )
    result = worker.handshake(tmp_path, manifest)
    assert core.handshake_status(result) == ("PASS" if modern else "INCOMPLETE")

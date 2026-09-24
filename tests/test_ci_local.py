"""Offline contract tests for local CI evidence and failure semantics."""

import copy
import hashlib
import json
import subprocess
import sys

import pytest

from scripts import ci_local as ci


@pytest.fixture
def result():
    return dict(
        schema_version=1,
        code_sha="a" * 40,
        tree_sha="b" * 40,
        branch="astra/ci-local-parity",
        dirty_state=False,
        started_at=ci.utc(),
        finished_at=ci.utc(),
        mode="host",
        steps=[ci.step("synthetic", "PASS")],
        tests_passed=1,
        tests_skipped=0,
        tests_failed=0,
        coverage={"percent": 90, "threshold": 80},
        docker_status="NOT_RUN",
        secret_scan="PASS",
        artifact_checks=[],
        warnings=[],
        failures=[],
        overall_result="PASS",
        gate="LOCAL_GATE_PASS",
        merge_authorization=False,
    )


def test_synthetic_pass(result):
    assert ci.validate_result(result)["overall_result"] == "PASS"


def test_failed_command_is_fail(tmp_path):
    runner = ci.Runner(tmp_path, tmp_path)
    item = runner.run("failure", [sys.executable, "-c", "raise SystemExit(7)"])
    assert item["exit_code"] == 7
    assert ci.overall(runner.steps) == "FAIL"


@pytest.mark.parametrize("required,expected", [(True, "INCOMPLETE"), (False, "PASS")])
def test_docker_unavailable_policy(required, expected):
    steps = [ci.step("host", "PASS"), ci.step("docker", "BLOCKED", required=required)]
    assert ci.overall(steps) == expected
    assert steps[1]["status"] == "BLOCKED"


def test_dirty_tree_cannot_pass(result):
    result["dirty_state"] = True
    assert ci.overall(result["steps"], True) == "INCOMPLETE"
    with pytest.raises(ValueError):
        ci.validate_result(result)


def test_identity_captures_sha_and_dirty(tmp_path):
    def git(*args):
        return subprocess.check_output(
            ["git", "-C", str(tmp_path), *args], text=True, stderr=subprocess.DEVNULL
        ).strip()

    git("init")
    (tmp_path / "file.txt").write_text("one", encoding="utf-8")
    git("add", "file.txt")
    git(
        "-c",
        "user.name=CI",
        "-c",
        "user.email=ci@example.invalid",
        "commit",
        "-m",
        "test",
    )
    ident = ci.identity(tmp_path)
    assert ident["code_sha"] == git("rev-parse", "HEAD")
    assert ident["tree_sha"] == git("rev-parse", "HEAD^{tree}")
    assert not ident["dirty_state"]
    (tmp_path / "file.txt").write_text("two", encoding="utf-8")
    assert ci.identity(tmp_path)["dirty_state"]


@pytest.mark.parametrize("label", ["api_key", "token", "password", "authorization"])
def test_secret_redaction(label):
    secret = "aB39" * 8
    content = f'{label} = "{secret}"'
    hits = ci.findings("fixture.txt", content)
    assert hits
    assert secret not in json.dumps(hits)
    assert secret not in ci.sanitize(content)


def test_bearer_private_key_env_redaction():
    secret = "cD49" * 8
    assert ci.findings("fixture", "Bearer " + secret)
    key = "-----BEGIN " + "PRIVATE KEY-----\n" + secret + "\n-----END PRIVATE KEY-----"
    assert secret not in ci.sanitize(key)
    assert ci.findings(".env", "")


def test_artifact_mismatch(tmp_path):
    (tmp_path / "model").write_bytes(b"changed")
    assert (
        ci.check_artifact(tmp_path, "model", hashlib.sha256(b"original").hexdigest())[
            "status"
        ]
        == "FAIL"
    )


@pytest.mark.parametrize("required,status", [(False, "BLOCKED"), (True, "FAIL")])
def test_missing_artifact(tmp_path, required, status):
    item = ci.check_artifact(tmp_path, "absent", "a" * 64, required)
    assert item["status"] == status
    assert ci.overall([item]) != "PASS"


@pytest.mark.parametrize("state", ["UNKNOWN", "NOT_RUN", "SKIP", "BLOCKED"])
def test_unknown_never_pass(state):
    assert ci.overall([ci.step("unknown", state)]) == "INCOMPLETE"


@pytest.mark.parametrize(
    "field", ["steps", "code_sha", "coverage", "merge_authorization"]
)
def test_malformed_result_rejected(result, field):
    del result[field]
    with pytest.raises(ValueError):
        ci.validate_result(result)


def test_merge_authorization_false(result):
    assert ci.validate_result(result)["merge_authorization"] is False
    result["merge_authorization"] = True
    with pytest.raises(ValueError):
        ci.validate_result(result)


def test_optional_unknown_is_not_pass():
    assert ci.overall([ci.step("unknown", "UNKNOWN", required=False)]) == "INCOMPLETE"


def test_empty_steps_not_pass():
    assert ci.overall([]) == "INCOMPLETE"


def test_invalid_step_rejected(result):
    result["steps"][0]["status"] = "UNKNOWN"
    with pytest.raises(ValueError):
        ci.validate_result(result)


def test_environment_drops_real_credentials(monkeypatch):
    monkeypatch.setenv("NASA_FIRMS_API_KEY", "aB39" * 8)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "cD49" * 8)
    env = ci.clean_env()
    assert "NASA_FIRMS_API_KEY" not in env
    assert "TELEGRAM_BOT_TOKEN" not in env
    assert env["PYTHON_DOTENV_DISABLED"] == "1"


def test_workflow_mapping_complete():
    assert ci.workflow_check(ci.ROOT)["status"] == "PASS"


def test_workflow_drift_detected(tmp_path):
    mapping = json.loads((ci.ROOT / "ci-parity-map.json").read_text(encoding="utf-8"))
    for relative in mapping["contracts"]:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ci.ROOT / relative).read_bytes())
    for relative in ("src", "app", "tests"):
        (tmp_path / relative).mkdir(exist_ok=True)
    (tmp_path / "ci-parity-map.json").write_text(json.dumps(mapping), encoding="utf-8")
    workflow = tmp_path / ".github/workflows/ci.yml"
    workflow.write_text(
        workflow.read_text(encoding="utf-8").replace("black --check", "black --diff"),
        encoding="utf-8",
    )
    assert ci.workflow_check(tmp_path)["status"] == "FAIL"


def test_result_roundtrip(result):
    assert ci.validate_result(json.loads(json.dumps(copy.deepcopy(result)))) == result


@pytest.mark.parametrize("value", ["unknown", {}, {"percent": float("nan")}])
def test_malformed_coverage_rejected(result, value):
    result["coverage"] = value
    with pytest.raises(ValueError):
        ci.validate_result(result)


def test_null_counts_cannot_pass(result):
    result["tests_passed"] = None
    with pytest.raises(ValueError):
        ci.validate_result(result)


def test_network_guard_allows_socketpair_but_blocks_connect(tmp_path):
    guard = ci.write_network_guard(tmp_path)
    runner = ci.Runner(tmp_path, tmp_path)
    runner.env["PYTHONPATH"] = str(guard)
    code = (
        "import socket\na,b=socket.socketpair(); a.close(); b.close()\n"
        "try:\n    socket.socket().connect(('127.0.0.1', 5678))\n"
        "except PermissionError:\n    pass\nelse:\n    raise AssertionError('network allowed')\n"
    )
    assert runner.run("guard_test", [sys.executable, "-c", code])["status"] == "PASS"


def test_placeholder_does_not_hide_new_secret():
    assert not ci.findings("fixture", 'TOKEN = "${CI_TOKEN}"')
    assert ci.findings(".env.example", 'API_KEY = "' + "xY37" * 8 + '"')


def test_clean_optional_block_stays_blocked_in_valid_result(result):
    result["steps"].append(ci.step("docker", "BLOCKED", required=False))
    result["docker_status"] = "BLOCKED"
    assert ci.validate_result(result)["docker_status"] == "BLOCKED"


def test_junit_counts_and_coverage(tmp_path):
    junit = tmp_path / "junit.xml"
    junit.write_text(
        "<testsuites><testsuite><testcase/><testcase><skipped/></testcase>"
        "<testcase><failure/></testcase></testsuite></testsuites>",
        encoding="utf-8",
    )
    coverage = tmp_path / "coverage.json"
    coverage.write_text('{"totals":{"percent_covered":81.5}}', encoding="utf-8")
    assert ci.pytest_metrics(junit, coverage) == dict(
        tests_passed=1, tests_skipped=1, tests_failed=1, coverage={"percent": 81.5}
    )

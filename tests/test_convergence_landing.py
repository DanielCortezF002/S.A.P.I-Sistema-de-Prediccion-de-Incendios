"""RC1 convergence landing helper self-tests (Phase 42).

Every repository here is a synthetic temp git repo. No real adapter SHA is fabricated and
the real convergence worktree is only read (status smoke test).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from src.convergence import landing as ld

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git unavailable")
REPO = Path(__file__).resolve().parents[1]
CANDIDATE = "claude/rc1-convergence-prep"
OPS = "antigravity/operations-rc1"


def g(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def commit(repo: Path, files: dict[str, str], msg: str) -> str:
    for rel, text in files.items():
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    g(repo, "add", "-A")
    g(repo, "commit", "-q", "-m", msg)
    return g(repo, "rev-parse", "HEAD")


@pytest.fixture(scope="module")
def template(tmp_path_factory):
    """base → data / output / ops lanes → candidate with --no-ff lane merges + lanes lock."""
    repo = tmp_path_factory.mktemp("tpl") / "repo with spaces"
    repo.mkdir()
    g(repo, "init", "-q", "-b", "main")
    g(repo, "config", "user.name", "convergence-test")
    g(repo, "config", "user.email", "convergence-test@example.invalid")
    g(repo, "config", "commit.gpgsign", "false")
    base = commit(repo, {"README.md": "base\n", "src/ops/consumer.py": "V = 1\n",
                         "docs/ops/FLOW.md": "flow\n"}, "base")  # fmt: skip
    lanes = {}
    for name, files in (
        ("data", {"src/ops/data_readiness.py": "D = 1\n"}),
        ("output", {"src/output/contract.py": "O = 1\n"}),
        ("ops", {"src/ops/rc_status.py": "S = 1\n"}),
    ):
        g(repo, "checkout", "-q", "-b", f"lane-{name}", base)
        lanes[name] = commit(repo, files, name)
    g(repo, "branch", "-q", OPS, lanes["ops"])
    g(repo, "checkout", "-q", "-b", CANDIDATE, base)
    for name in ("data", "output", "ops"):
        g(repo, "merge", "-q", "--no-ff", "--no-edit", lanes[name])
    lock = {
        "schema": "sapi-rc1-convergence-lanes-v1",
        "candidate_branch": CANDIDATE,
        "base": {"sha": base, "tree": g(repo, "rev-parse", f"{base}^{{tree}}")},
        "data": {"sha": lanes["data"], "manifest_fingerprint": "d" * 64},
        "output": {"sha": lanes["output"], "manifest_fingerprint": "e" * 64},
        "operations": {"branch": OPS, "base_sha": lanes["ops"], "adapter_sha": None},
        "blockers": {"resolved": ["B2", "B3"], "open": ["B1"]},
    }
    commit(repo, {ld.LANES_REL: json.dumps(lock, indent=2) + "\n"}, "lanes lock")
    return repo, lanes


@pytest.fixture
def world(template, tmp_path):
    repo = tmp_path / "repo with spaces"
    shutil.copytree(template[0], repo)  # git spawns are slow on Windows: build once
    return repo, dict(template[1])


def adapter(
    repo: Path, parent: str, files: dict[str, str], *, on_ops: bool = True
) -> str:
    g(repo, "checkout", "-q", "--detach", parent)
    sha = commit(repo, files, "adapter")
    if on_ops:
        g(repo, "branch", "-q", "-f", OPS, sha)
    g(repo, "checkout", "-q", CANDIDATE)
    return sha


def refused(repo: Path, sha: str, **kw) -> list[str]:
    with pytest.raises(ld.LandingRefused) as exc:
        ld.land_operations_adapter(repo, sha, **kw)
    return exc.value.reasons


@pytest.mark.parametrize("bad", ["", "xyz", "HEAD", OPS, "ABCDEF" + "0" * 34, "0" * 39])
def test_non_full_sha_refused(world, bad):
    assert refused(world[0], bad) == ["sha_not_full_40_lowercase_hex"]


def test_short_ambiguous_sha_refused(world):
    repo, lanes = world
    sha = adapter(repo, lanes["ops"], {"src/ops/consumer.py": "V = 2\n"})
    assert refused(repo, sha[:12]) == ["sha_not_full_40_lowercase_hex"]


def test_unknown_commit_refused(world):
    assert refused(world[0], "0123456789" * 4) == ["commit_not_found"]


def test_wrong_parent_refused(world):
    repo, lanes = world
    stray = adapter(
        repo, lanes["data"], {"src/ops/consumer.py": "V = 3\n"}, on_ops=False
    )
    reasons = refused(repo, stray)
    assert "not_descendant_of_operations_base" in reasons
    assert "not_in_operations_branch_history" in reasons


def test_operations_base_itself_refused(world):
    repo, lanes = world
    reasons = refused(repo, lanes["ops"])
    assert {"adapter_is_the_operations_base", "adapter_already_merged"} <= set(reasons)


def test_descendant_outside_operations_branch_refused(world):
    repo, lanes = world
    side = adapter(repo, lanes["ops"], {"src/ops/consumer.py": "V = 4\n"}, on_ops=False)
    assert refused(repo, side) == ["not_in_operations_branch_history"]


def test_dirty_candidate_refused(world):
    repo, lanes = world
    sha = adapter(repo, lanes["ops"], {"src/ops/consumer.py": "V = 5\n"})
    (repo / "scratch.txt").write_text("untracked", encoding="utf-8")
    assert refused(repo, sha) == ["candidate_dirty"]


def test_frozen_path_refused(world):
    repo, lanes = world
    sha = adapter(repo, lanes["ops"], {"src/output/contract.py": "O = 2\n"})
    assert refused(repo, sha) == ["touches_frozen_path:src/output/contract.py"]


def test_range_with_other_lane_history_refused(world):
    repo, lanes = world
    g(repo, "checkout", "-q", "--detach", lanes["ops"])
    g(repo, "merge", "-q", "--no-ff", "--no-edit", lanes["data"])
    sha = commit(repo, {"src/ops/consumer.py": "V = 6\n"}, "adapter over data lane")
    g(repo, "branch", "-q", "-f", OPS, sha)
    g(repo, "checkout", "-q", CANDIDATE)
    reasons = refused(repo, sha)
    assert "range_contains_other_lane_history" in reasons


def test_merge_conflict_refused_without_touching_candidate(world):
    repo, lanes = world
    commit(repo, {"docs/ops/FLOW.md": "convergence edit\n"}, "convergence doc fix")
    head = g(repo, "rev-parse", "HEAD")
    sha = adapter(repo, lanes["ops"], {"docs/ops/FLOW.md": "adapter edit\n"})
    with pytest.raises(ld.LandingRefused) as exc:
        ld.land_operations_adapter(repo, sha, execute=True)
    assert exc.value.reasons == ["trial_merge_conflicts"]
    assert exc.value.detail["trial"]["conflicts"] == ["docs/ops/FLOW.md"]
    assert (
        g(repo, "rev-parse", "HEAD") == head and g(repo, "status", "--porcelain") == ""
    )


def test_valid_child_dry_run_then_land(world):
    repo, lanes = world
    sha = adapter(repo, lanes["ops"], {"src/ops/consumer.py": "V = 7\n",
                                       "tests/test_consumer.py": "# t\n"})  # fmt: skip
    head = g(repo, "rev-parse", "HEAD")
    plan = ld.land_operations_adapter(repo, sha)
    assert plan["result"] == "READY_TO_LAND" and plan["trial"]["mergeable"] is True
    assert plan["trial"]["conflicts"] == [] and plan["merge_command"][-1] == sha
    assert g(repo, "rev-parse", "HEAD") == head  # dry run wrote nothing
    landed = ld.land_operations_adapter(
        repo, sha, execute=True, trailer="Co-Authored-By: t <t@e>"
    )
    assert landed["result"] == "LANDED" and landed["assertions"]["pass"] is True
    assert landed["merged"]["tree"] == plan["trial"]["trial_tree"]
    merge = g(repo, "rev-parse", "HEAD^")
    assert g(repo, "rev-list", "--parents", "-n", "1", merge).split()[1:] == [head, sha]
    lock = ld.load_lanes(repo)
    assert lock["operations"]["adapter_sha"] == sha and lock["blockers"]["open"] == []
    assert (
        g(repo, "log", "-1", "--format=%B").rstrip().endswith("Co-Authored-By: t <t@e>")
    )
    # already merged + already recorded
    reasons = refused(repo, sha)
    assert {"adapter_already_merged", "lanes_lock_already_records_an_adapter"} <= set(
        reasons
    )


def test_status_before_and_after_adapter_exists(world, monkeypatch):
    repo, lanes = world
    monkeypatch.setattr(ld, "handshakes", lambda *a: {"data": {}, "output": "PASS"})
    st = ld.status(repo, repo / "d.json", repo / "o.json")
    assert st["next_action"] == "WAIT FOR ANTIGRAVITY ADAPTER SHA"
    assert all(st["lanes_included"].values()) and st["candidate"]["clean"]
    adapter(repo, lanes["ops"], {"src/ops/consumer.py": "V = 8\n"})
    st = ld.status(repo, repo / "d.json", repo / "o.json")
    assert st["operations_commits_beyond_base"] and st["next_action"].startswith(
        "check-adapter"
    )


def test_status_stops_when_landed_adapter_fails_the_handshake(world, monkeypatch):
    repo, lanes = world
    sha = adapter(repo, lanes["ops"], {"src/ops/consumer.py": "V = 10\n"})
    ld.land_operations_adapter(repo, sha, execute=True)
    rejected = {"data": {"classification": "UNEXPECTED_REJECT"}, "output": "PASS"}
    monkeypatch.setattr(ld, "handshakes", lambda *a: rejected)
    st = ld.status(repo, repo / "d.json", repo / "o.json")
    assert st["adapter_landed"] and st["next_action"].startswith("STOP: adapter landed")
    accepted = {"data": {"classification": "ACCEPTED"}, "output": "PASS"}
    monkeypatch.setattr(ld, "handshakes", lambda *a: accepted)
    assert ld.status(repo, repo / "d.json", repo / "o.json")["next_action"].startswith(
        "run-tests"
    )


# --- normalization, delta and fingerprint v3 --------------------------------------------------


def _result(suite, outcomes, sha="a" * 40, exit_code=0):
    count = lambda k: sum(v == k for v in outcomes.values())  # noqa: E731
    return {"suite": suite, "pass": count("passed"), "skip": count("skipped"),
            "fail": count("failed"), "exit_code": exit_code, "candidate_sha": sha,
            "outcomes": outcomes}  # fmt: skip


def test_delta_classification():
    before = _result("I", {"a": "passed", "b": "failed", "c": "skipped", "d": "passed"})
    after = _result("I", {"a": "failed", "b": "passed", "c": "passed", "e": "passed",
                          "f": "skipped"})  # fmt: skip
    delta = ld.test_delta(before, after)
    assert delta["tests"] == {
        "new_pass": ["e"], "new_fail": ["a"], "fixed_fail": ["b"], "new_skip": ["f"],
        "removed_skip": ["c"], "removed_test": ["d"],
    }  # fmt: skip
    assert delta["regression"] is True


def test_junit_normalization(tmp_path):
    xml = tmp_path / "j.xml"
    xml.write_text(
        '<testsuites><testsuite><testcase classname="t" name="a"/>'
        '<testcase classname="t" name="b"><skipped/></testcase>'
        '<testcase classname="t" name="c"><failure/></testcase>'
        '<testcase classname="t" name="d"><error/></testcase></testsuite></testsuites>',
        encoding="utf-8",
    )
    assert ld._junit_outcomes(xml) == {
        "t::a": "passed", "t::b": "skipped", "t::c": "failed", "t::d": "failed"}  # fmt: skip


def test_fingerprint_v3_final_refused_before_adapter(world):
    repo, _ = world
    with pytest.raises(ld.LandingRefused) as exc:
        ld.fingerprint_v3(
            repo, data_handshake={}, output_handshake="PASS", test_results=[]
        )
    assert "adapter_not_landed" in exc.value.reasons


def test_fingerprint_v3_template_is_deterministic_and_excludes_volatile_fields(world):
    repo, _ = world
    head = g(repo, "rev-parse", "HEAD")
    r1 = [
        _result("I_full_host", {"x": "passed"}, sha=head)
        | {"tail": "12.3s", "command": ["C:/a"]}
    ]
    r2 = [
        _result("I_full_host", {"x": "passed"}, sha=head)
        | {"tail": "99s", "command": ["D:/b"]}
    ]
    a = ld.fingerprint_v3(
        repo, data_handshake={}, output_handshake="?", test_results=r1, template=True
    )
    b = ld.fingerprint_v3(
        repo, data_handshake={}, output_handshake="?", test_results=r2, template=True
    )
    assert a["status"] == "TEMPLATE_NON_FINAL" and a == b
    assert a["stable"]["operations_adapter_sha"] is None
    assert set(a["stable"]["test_summaries"][0]) == {
        "suite",
        "pass",
        "skip",
        "fail",
        "exit_code",
    }
    assert a["convergence_fingerprint_v3"] == ld.canonical_sha256(a["stable"])


def test_fingerprint_v3_final_requirements(world):
    repo, lanes = world
    sha = adapter(repo, lanes["ops"], {"src/ops/consumer.py": "V = 9\n"})
    ld.land_operations_adapter(repo, sha, execute=True)
    head = g(repo, "rev-parse", "HEAD")
    good = [_result(s, {"x": "passed"}, sha=head) for s in [*ld.SUITES, ld.FULL_HOST]]
    accepted = {"classification": "ACCEPTED", "match": True}
    fp = ld.fingerprint_v3(
        repo, data_handshake=accepted, output_handshake="PASS", test_results=good
    )
    assert fp["status"] == "FINAL" and fp["stable"]["operations_adapter_sha"] == sha
    failing = _result(ld.FULL_HOST, {"x": "failed"}, sha=head, exit_code=1)
    for kwargs, reason in [
        ({"data_handshake": {"classification": "EXPECTED_REJECT"}}, "data_handshake_not_accepted"),
        ({"output_handshake": "REJECTED"}, "output_handshake_not_pass"),
        ({"test_results": good[:-1]}, "test_phases_incomplete"),
        ({"test_results": [*good[:-1], failing]}, "test_failures_present"),
        ({"test_results": [_result(s, {"x": "passed"}) for s in [*ld.SUITES, ld.FULL_HOST]]},
         "test_results_for_another_candidate"),
    ]:  # fmt: skip
        args = {
            "data_handshake": accepted,
            "output_handshake": "PASS",
            "test_results": good,
        }
        args.update(kwargs)
        with pytest.raises(ld.LandingRefused) as exc:
            ld.fingerprint_v3(repo, **args)
        assert reason in exc.value.reasons


def test_real_candidate_status_is_read_only():
    if not (REPO / ".git").exists():
        pytest.skip("no git metadata")
    before = g(REPO, "rev-parse", "HEAD")
    st = ld.status(REPO, *ld.default_manifests(REPO).values())
    assert st["release_gate"].startswith("NOT_EVALUATED")
    assert g(REPO, "rev-parse", "HEAD") == before

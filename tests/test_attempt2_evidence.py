"""Attempt 2 evidence builders (tools/ops/attempt2_evidence.py).

SYNTHETIC only: fake HTTP sessions, the bridge serializer over a synthetic
GridScoreResult, temp repos and dry-run operator runs. No network, no stores,
no writers, no n8n runtime.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest
import requests

from src.convergence import output_acceptance as oa
from src.ops.attempt2_operator.validators import (
    validate_bridge_result,
    validate_dmc_import,
    validate_firms_import,
    validate_n8n_result,
    validate_scoring_result,
)
from src.output import accepted_run as ar
from test_convergence_output_acceptance import (  # noqa: F401 (fixture reuse)
    plane,
    real_hash_before,
)
from test_convergence_run_binding import _body, _import, _record, _run
from test_output_pipeline import NODE
from tools.ops import attempt2_evidence as ev

REPO = Path(__file__).resolve().parents[1]
MODEL_BYTES = b"synthetic-model-bytes"
URL = "http://127.0.0.1:8600/score"


class _Response:
    def __init__(self, status: int, body, content_type="application/json"):
        self.status_code = status
        self._body = body
        self.headers = {"content-type": content_type}

    def json(self):
        if isinstance(self._body, (bytes, str)):
            return json.loads(self._body)
        return self._body


class _Session:
    """Counts GETs; returns the queued responses in order."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls: list[str] = []

    def get(self, url, **kwargs):
        self.calls.append(url)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture
def model_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "models").mkdir(parents=True)
    (repo / "config").mkdir()
    (repo / "models" / "prototype_model_d.pkl").write_bytes(MODEL_BYTES)
    sha = hashlib.sha256(MODEL_BYTES).hexdigest()
    (repo / "config" / "data_plane_rc1.json").write_text(
        json.dumps({"model": {"path": "models/prototype_model_d.pkl", "sha256": sha}}),
        encoding="utf-8",
    )
    return repo


def _load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


# --- R1: capture-bridge ---------------------------------------------------------------


def test_capture_is_one_get_and_every_file_comes_from_that_body(model_repo, tmp_path):
    body = _body()
    session = _Session(_Response(200, body))
    out = ev.capture_bridge(URL, tmp_path / "cap", repo=model_repo, session=session)

    assert session.calls == [URL] and out["get_count"] == 1
    raw = _load(out["files"]["bridge_body"])
    bridge = _load(out["files"]["bridge"])
    scoring = _load(out["files"]["scoring"])
    artifact = _load(out["files"]["accepted_run"])
    assert raw == body == bridge["body"]
    assert artifact["stable"]["output"] == ar._stable_output(bridge["body"])
    assert ar.verify_artifact(artifact)[0] == []
    fp = body["inputs_fingerprint"]
    assert (
        scoring["inputs_fingerprint"]
        == fp
        == artifact["identities"]["inputs_fingerprint"]
    )
    assert scoring["cells"] == body["cells"] and len(scoring["cells"]) == 50
    assert scoring["model_sha"] == hashlib.sha256(MODEL_BYTES).hexdigest()
    assert validate_scoring_result(scoring)["operation_success"] is True
    assert validate_bridge_result(bridge)["operation_success"] is True


def test_capture_binds_to_the_run_and_a_second_get_never_does(
    plane, model_repo, tmp_path  # noqa: F811
):
    first, second = _body(), _body(age_hours=2.0)  # same grid, later clock
    out = ev.capture_bridge(
        URL, tmp_path / "cap", repo=model_repo, session=_Session(_Response(200, first))
    )
    op = _run(tmp_path)
    _import(op, "scoring", _load(out["files"]["scoring"]))
    _import(op, "bridge", _load(out["files"]["bridge"]))
    record = _record(plane, Path(out["files"]["accepted_run"]), tmp_path / "acc")
    assert (
        oa.verify_acceptance_record(
            record, output_manifest_path=plane[0], expected_output_fingerprint=plane[1]
        )
        == []
    )
    assert oa.verify_run_binding(record, op.run.root) == []
    # B3: the documented two-GET flow cannot bind.
    assert "score_artifact_not_this_bridge_result" in oa.verify_run_binding(
        record, op.run.root, bridge_body=second
    )


@pytest.mark.parametrize(
    "status,body,reason",
    [
        (503, {"error_type": "prototype_unavailable"}, "prototype_unavailable"),
        (503, {"error_type": "data_unavailable"}, "data_unavailable"),
        (500, {"error_type": "internal_error"}, "internal_error"),
        (200, b"{broken", "response_not_json"),
        (200, {"status": "ok"}, None),
    ],
)
def test_capture_fails_closed_and_writes_nothing(
    model_repo, tmp_path, status, body, reason
):
    out_dir = tmp_path / "cap"
    with pytest.raises(ar.ArtifactError) as exc:
        ev.capture_bridge(
            URL, out_dir, repo=model_repo, session=_Session(_Response(status, body))
        )
    if reason:
        assert exc.value.reasons == [reason]
    assert not out_dir.exists() or not any(out_dir.iterdir())


def test_capture_network_error(model_repo, tmp_path):
    session = _Session(requests.ConnectionError("refused"))
    with pytest.raises(ConnectionError):
        ev.capture_bridge(URL, tmp_path / "cap", repo=model_repo, session=session)


def test_capture_refuses_unpinned_model_before_any_get(model_repo, tmp_path):
    (model_repo / "models" / "prototype_model_d.pkl").write_bytes(b"other")
    session = _Session(_Response(200, _body()))
    with pytest.raises(ar.ArtifactError) as exc:
        ev.capture_bridge(URL, tmp_path / "cap", repo=model_repo, session=session)
    assert exc.value.reasons == ["model_sha_not_pinned"] and session.calls == []


def test_capture_refuses_store_dirs_and_never_overwrites(model_repo, tmp_path):
    with pytest.raises(PermissionError):
        ev.capture_bridge(
            URL, REPO / "data" / "processed" / "x", repo=model_repo, session=_Session()
        )
    body = _body()
    out_dir = tmp_path / "cap"
    ev.capture_bridge(
        URL, out_dir, repo=model_repo, session=_Session(_Response(200, body))
    )
    with pytest.raises(FileExistsError):
        ev.capture_bridge(
            URL, out_dir, repo=model_repo, session=_Session(_Response(200, body))
        )


# --- R1: writer-payload ---------------------------------------------------------------

TIMES = {
    "started_at": "2026-10-01T12:00:00+00:00",
    "finished_at": "2026-10-01T12:03:00+00:00",
}


def _firms_repo(tmp_path: Path, pointer: dict | None) -> Path:
    repo = tmp_path / "ws"
    store = repo / "data" / "processed" / "firms"
    store.mkdir(parents=True)
    if pointer is not None:
        (store / "CURRENT.json").write_text(json.dumps(pointer), encoding="utf-8")
    return repo


def test_firms_payload_accepted_only_when_publication_validates(tmp_path, monkeypatch):
    repo = _firms_repo(tmp_path, {"schema_version": 3, "sha256": "a" * 64})
    monkeypatch.setattr(
        "src.refresh.firms_validation.validate_publication",
        lambda paths: {"result": "FIRMS ACCEPTED", "sha256": "a" * 64},
    )
    stdout = json.dumps({"status": "published", "new_rows": 10})
    p = ev.writer_payload(
        "firms",
        stdout=stdout,
        stderr="",
        exit_code=0,
        repo=repo,
        firms_paths=object(),
        **TIMES,
    )
    assert (p["schema_ok"], p["hash_ok"], p["pointer_ok"]) == (True, True, True)
    assert p["firms_current_after"]["state"] == "PRESENT"
    assert validate_firms_import(
        {**p, "stdout_sha256": "x", "stderr_sha256": "y", "sanitization_status": "PASS"}
    )["operation_success"]


@pytest.mark.parametrize(
    "validator",
    [
        lambda paths: (_ for _ in ()).throw(ValueError("Hash raw inválido")),
        lambda paths: {"result": "FIRMS ACCEPTED", "sha256": "b" * 64},  # not CURRENT
    ],
)
def test_firms_flags_never_default_true(tmp_path, monkeypatch, validator):
    repo = _firms_repo(tmp_path, {"schema_version": 3, "sha256": "a" * 64})
    monkeypatch.setattr("src.refresh.firms_validation.validate_publication", validator)
    p = ev.writer_payload(
        "firms",
        stdout="{}",
        stderr="",
        exit_code=0,
        repo=repo,
        firms_paths=object(),
        **TIMES,
    )
    assert {"schema_ok", "hash_ok", "pointer_ok"} <= set(p)
    assert not (p["schema_ok"] or p["hash_ok"] or p["pointer_ok"])
    assert not validate_firms_import(
        {**p, "stdout_sha256": "x", "stderr_sha256": "y", "sanitization_status": "PASS"}
    )["operation_success"]


def test_firms_absent_current_fails(tmp_path, monkeypatch):
    repo = _firms_repo(tmp_path, None)
    monkeypatch.setattr(
        "src.refresh.firms_validation.validate_publication",
        lambda paths: (_ for _ in ()).throw(ValueError("CURRENT FIRMS ausente")),
    )
    p = ev.writer_payload(
        "firms",
        stdout="",
        stderr="",
        exit_code=0,
        repo=repo,
        firms_paths=object(),
        **TIMES,
    )
    assert p["firms_current_after"]["state"] == "ABSENT" and p["pointer_ok"] is False


def _dmc_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "ws"
    station = repo / "data" / "processed" / "dmc" / "330007"
    station.mkdir(parents=True)
    (station / "CURRENT.json").write_text(
        json.dumps({"schema_version": 1, "manifest_sha256": "m" * 64}), encoding="utf-8"
    )
    return repo


@pytest.mark.parametrize(
    "exit_code,stdout,verified,ok",
    [
        (
            0,
            {"status": "published", "row_quality": {}, "manifest_sha256": "m" * 64},
            {"manifest_sha256": "m" * 64},
            True,
        ),
        (
            0,
            {"status": "published", "row_quality": {}, "manifest_sha256": "z" * 64},
            {"manifest_sha256": "m" * 64},
            False,
        ),  # stdout ≠ verified pointer
        (65, {"status": "error"}, {"manifest_sha256": "m" * 64}, False),
        (
            0,
            {"status": "published", "row_quality": {}, "manifest_sha256": "m" * 64},
            None,
            False,
        ),  # pointer does not verify
    ],
)
def test_dmc_payload(tmp_path, monkeypatch, exit_code, stdout, verified, ok):
    repo = _dmc_repo(tmp_path)
    monkeypatch.setattr("src.refresh.dmc_refresh.read_current", lambda paths: verified)
    p = ev.writer_payload(
        "dmc",
        stdout=json.dumps(stdout),
        stderr="",
        exit_code=exit_code,
        repo=repo,
        **TIMES,
    )
    assert {"quality_ok", "pointer_ok"} <= set(p)
    result = validate_dmc_import({**p, "sanitization_status": "PASS"})
    assert result["operation_success"] is ok


# --- R5: n8n-evidence -----------------------------------------------------------------

needs_node = pytest.mark.skipif(NODE is None, reason="node not available")


def _n8n_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "n8nrepo"
    dest = repo / "ops" / "n8n"
    dest.mkdir(parents=True)
    for name in ("policy.js", "build_workflow.py", "controlled-preview.json"):
        shutil.copy2(REPO / "ops" / "n8n" / name, dest / name)
    return repo


def _edit_workflow(repo: Path, change) -> None:
    path = repo / "ops" / "n8n" / "controlled-preview.json"
    wf = json.loads(path.read_text(encoding="utf-8"))
    change(wf)
    path.write_text(json.dumps(wf), encoding="utf-8")


@needs_node
def test_n8n_policy_evidence_passes_and_is_not_runtime():
    doc = ev.n8n_evidence(_body(), repo=REPO, node=NODE)
    assert doc["workflow"]["ok"] is True
    assert doc["fail_closed_cases"] == {
        "prototype_unavailable": True,
        "data_unavailable": True,
        "internal_error": True,
    }
    assert (doc["schedule_enabled"], doc["telegram_sent"]) == (False, False)
    assert doc["score_path_ok"] is True
    assert doc["n8n_runtime_executed"] is False
    assert doc["evidence_kind"] == "N8N_POLICY_EVIDENCE"
    assert validate_n8n_result(doc)["operation_success"] is True


@needs_node
def test_altered_policy_in_workflow_fails(tmp_path):
    repo = _n8n_repo(tmp_path)

    def tamper(wf):
        for n in wf["nodes"]:
            if n["name"] == "Policy":
                n["parameters"]["jsCode"] = "// edited\n" + n["parameters"]["jsCode"]

    _edit_workflow(repo, tamper)
    doc = ev.n8n_evidence(_body(), repo=repo, node=NODE)
    assert doc["workflow"]["checks"]["policy_embedded"] is False
    assert doc["score_path_ok"] is False
    assert validate_n8n_result(doc)["operation_success"] is False


@needs_node
@pytest.mark.parametrize(
    "node_type,field",
    [
        ("n8n-nodes-base.scheduleTrigger", "schedule_enabled"),
        ("n8n-nodes-base.telegram", "telegram_sent"),
    ],
)
def test_schedule_or_telegram_node_fails(tmp_path, node_type, field):
    repo = _n8n_repo(tmp_path)
    _edit_workflow(
        repo, lambda wf: wf["nodes"].append({"name": "x", "type": node_type})
    )
    doc = ev.n8n_evidence(_body(), repo=repo, node=NODE)
    assert doc[field] is not False and doc["score_path_ok"] is False
    assert validate_n8n_result(doc)["operation_success"] is False


def test_active_workflow_is_reported_as_schedule(tmp_path):
    repo = _n8n_repo(tmp_path)
    _edit_workflow(repo, lambda wf: wf.update(active=True))
    doc = ev.n8n_evidence(_body(), repo=repo, node="definitely-not-node")
    assert doc["schedule_enabled"] is True
    assert validate_n8n_result(doc)["operation_success"] is False


@pytest.mark.parametrize("case", sorted(ev.FAIL_CLOSED_ENVELOPES))
def test_each_fail_closed_case_is_checked(case):
    body = _body()

    def runner(cmd, **kwargs):
        results = {
            "score_path": {
                "category": "withheld",
                "alert_identity_verified": True,
                "delivery": "NOT_SENT",
                "inputs_fingerprint": body["inputs_fingerprint"],
            },
            **{
                c: {"category": "error", "reason": c, "delivery": "NOT_SENT"}
                for c in ev.FAIL_CLOSED_ENVELOPES
            },
        }
        results[case] = {"category": "candidate", "reason": "x", "delivery": "NOT_SENT"}

        class P:
            returncode = 0
            stdout = json.dumps(results)

        return P()

    doc = ev.n8n_evidence(body, repo=REPO, runner=runner)
    assert doc["fail_closed_cases"][case] is False
    assert validate_n8n_result(doc)["operation_success"] is False


def test_missing_node_or_unreadable_workflow_fails_closed(tmp_path):
    doc = ev.n8n_evidence(_body(), repo=REPO, node="definitely-not-node")
    assert doc["node_evaluated"] is False and doc["score_path_ok"] is False
    assert not any(doc["fail_closed_cases"].values())
    assert validate_n8n_result(doc)["operation_success"] is False

    empty = tmp_path / "empty"
    empty.mkdir()
    doc = ev.n8n_evidence(_body(), repo=empty, node="definitely-not-node")
    assert doc["workflow"]["ok"] is False and doc["schedule_enabled"] is None
    assert validate_n8n_result(doc)["operation_success"] is False

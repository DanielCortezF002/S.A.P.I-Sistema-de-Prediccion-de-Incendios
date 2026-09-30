"""RC1 convergence: Data producer contract lock and the Data→Operations adapter contract.

The real Data manifest is read-only here; every tamper works on a temp copy. The expected
Operations verdict follows config/rc1_convergence_lanes.json: EXPECTED_REJECT while
operations.adapter_sha is null, ACCEPTED (with the full adapter contract) once the landing
helper records the real Antigravity SHA. Stubbed consumers below exercise the CLASSIFIER
only; they are not, and never stand in for, the adapter.
"""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from src.convergence import data_handshake as dh
from src.ops import data_readiness as producer

REPO = Path(__file__).resolve().parents[1]
REAL_DATA_MANIFEST = (
    REPO.parent
    / "SAPI-71-evidence"
    / "data-plane-rc1-2026-09-25"
    / "DATA_PLANE_MANIFEST.json"
)
LANES = dh.load_lanes()
IDENTITY_KEYS = {
    "schema_version", "kind", "policy_sha256", "components", "code_identity", "model",
    "topography", "baseline", "stores", "store_roots_policy", "expected_current",
    "current_state", "firms_current", "dmc_current", "source_evidence_sha256",
    "source_evidence", "attempt1", "findings", "data_readiness_status",
    "data_ready_for_scoring", "independent_approval", "authorizations",
}  # fmt: skip
NO_AUTH = {name: False for name in dh.AUTHORIZATION_NAMES}


def _real() -> dict:
    if not REAL_DATA_MANIFEST.is_file():
        pytest.skip("real Data manifest absent")
    return json.loads(REAL_DATA_MANIFEST.read_bytes())


def _synthetic_manifest(status: str = "PREPARED", **overrides) -> dict:
    ok = {"status": "PASS"}
    result = {
        "code_identity": {**ok, "sha": LANES["data"]["sha"], "clean": True},
        "model": {**ok, "sha256": LANES["data"]["model_sha256"]},
        "topography": {**ok, "cells": 50},
        "firms": {"baseline": {**ok, "sha256": LANES["data"]["baseline_sha256"]},
                  "current": {"state": "ABSENT"}, "attempt1": {}},
        "dmc": {"current": {"state": "ABSENT"}, "source_evidence": {**ok, "sha256": "e" * 64}},
        "stores": {"files": 1},
        "current_state": {"firms": "ABSENT", "dmc": "ABSENT"},
        "findings": [],
        "status": status,
        "authorizations": dict(NO_AUTH),
        "observed_at_start": "2026-09-25T00:00:00+00:00",
        "observed_at_end": "2026-09-25T00:00:01+00:00",
    }  # fmt: skip
    result.update(overrides)
    policy = {
        "components": {"firms": {"sha": LANES["data"]["firms_component_sha"]},
                       "dmc": {"sha": LANES["data"]["dmc_component_sha"]}},
        "stores": {}, "expected_current": {"firms": "ABSENT", "dmc": "ABSENT"},
    }  # fmt: skip
    return producer.build_manifest(
        result, policy, workspace=Path("."), created_at="2026-09-25T00:00:00+00:00"
    )


def _write(tmp_path: Path, doc, name="DATA_PLANE_MANIFEST.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(doc, ensure_ascii=True), encoding="utf-8")
    return path


def _landed(sha: str = "a" * 40) -> dict:
    lanes = copy.deepcopy(LANES)
    lanes["operations"]["adapter_sha"] = sha
    return lanes


def _contract_verdict(doc: dict, **overrides) -> dict:
    """What the landed adapter (13c9450) reports for a PREPARED `doc`."""
    ident = doc["identity"]
    out = {
        "status": "PREPARED", "ready": False, "prepared": True,
        "manifest_fingerprint": dh.producer_fingerprint(doc), "fingerprint_match": True,
        "data_readiness_status": ident["data_readiness_status"],
        "code_sha": ident["code_identity"]["sha"],
        "firms_component_sha": ident["components"]["firms"]["sha"],
        "dmc_component_sha": ident["components"]["dmc"]["sha"],
        "model_sha": ident["model"]["sha256"],
        "baseline_identity": ident["baseline"]["sha256"],
        **{f"{k}_authorized": v for k, v in ident["authorizations"].items()},
        "findings": [],
    }  # fmt: skip
    out.update(overrides)
    return out


# --- Phase 4: Data producer contract lock ----------------------------------------------------


def test_real_manifest_producer_contract_lock():
    raw = _real()
    assert set(raw) == {"schema_version", "created_at", "identity", "fingerprint",
                        "operational_roots", "observation"}  # fmt: skip
    ident = raw["identity"]
    assert set(ident) == IDENTITY_KEYS
    assert raw["schema_version"] == ident["schema_version"] == 1
    assert ident["kind"] == "DATA_PLANE_MANIFEST"
    assert ident["data_readiness_status"] == "PREPARED"
    assert ident["data_ready_for_scoring"] == "NOT_EVALUATED"
    assert ident["independent_approval"] == "PENDING"
    assert ident["authorizations"] == NO_AUTH
    assert ident["code_identity"]["sha"] == LANES["data"]["sha"]
    assert producer.verify_manifest(copy.deepcopy(raw)) is True
    assert (
        raw["fingerprint"]
        == dh.producer_fingerprint(raw)
        == LANES["data"]["manifest_fingerprint"]
    )
    assert dh.pin_mismatches(raw, LANES) == []


def test_fingerprint_recipe_is_the_documented_canonical_form():
    doc = _synthetic_manifest()
    spelled = json.dumps(doc["identity"], sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True, allow_nan=False).encode("utf-8")  # fmt: skip
    assert doc["fingerprint"] == hashlib.sha256(spelled).hexdigest()
    assert producer.canonical(doc["identity"]) == spelled


def test_volatile_fields_are_outside_the_fingerprint():
    a = _synthetic_manifest()
    b = copy.deepcopy(a)
    b["created_at"], b["operational_roots"] = "2030-01-01T00:00:00+00:00", {
        "code": "X:\\y z"
    }
    b["observation"] = {"start": "s", "end": "e"}
    assert producer.verify_manifest(b) is True and b["fingerprint"] == a["fingerprint"]


@pytest.mark.parametrize("status", ["PREPARED", "NOT_PREPARED", "INCOMPLETE"])
def test_producer_statuses_never_carry_authorization(status):
    doc = _synthetic_manifest(status, findings=[] if status == "PREPARED" else ["x"])
    assert producer.verify_manifest(doc) is True
    assert doc["identity"]["authorizations"] == NO_AUTH


def test_prepared_with_findings_or_authorization_is_not_producer_valid():
    doc = _synthetic_manifest(findings=["late"])
    assert producer.verify_manifest(doc) is False
    doc = _synthetic_manifest(authorizations={**NO_AUTH, "writers": True})
    assert producer.verify_manifest(doc) is False


# --- Phases 3/13: handshake negative control that flips only through the lanes lock ----------


def test_data_handshake_matches_landing_state():
    _real()
    result = dh.classify(REAL_DATA_MANIFEST)
    assert result["producer"]["verify_manifest"] == "PASS"
    assert (
        result["producer"]["fingerprint_recomputed"]
        == LANES["data"]["manifest_fingerprint"]
    )
    assert result["producer"]["pins"] == "MATCH"
    if not dh.adapter_landed(LANES):
        assert result["classification"] == dh.EXPECTED_REJECT
        assert (
            result["consumer"]["status"] == "FAIL"
            and result["consumer"]["ready"] is False
        )
        assert any(f.startswith("DM-005:") for f in result["consumer"]["findings"])
        # Pre-adapter the consumer fingerprints the flat document, not the identity subtree.
        assert (
            result["consumer"]["manifest_fingerprint_reported"]
            != LANES["data"]["manifest_fingerprint"]
        )
    else:
        assert (
            result["classification"] == dh.ACCEPTED
            and result["contract_violations"] == []
        )
        # POST-ADAPTER positive control, spelled out against the integrated verifier.
        verdict = dh.verify_data_plane_manifest(REAL_DATA_MANIFEST)
        assert verdict["status"] == "PREPARED" and verdict["prepared"] is True
        assert verdict["ready"] is False  # PREPARED is not ready for scoring
        assert verdict["fingerprint_match"] is True
        assert verdict["manifest_fingerprint"] == LANES["data"]["manifest_fingerprint"]
        assert verdict["code_sha"] == LANES["data"]["sha"]
        assert verdict["data_readiness_status"] == "PREPARED"
        assert verdict["writers_authorized"] is False
        assert verdict["attempt2_authorized"] is False
        assert (
            result["consumer"]["manifest_fingerprint_reported"]
            == LANES["data"]["manifest_fingerprint"]
        )
        assert result["consumer"]["readiness_status_reported"] == "PREPARED"
    assert result["match"] is True


def test_post_adapter_rc_sha_is_not_the_data_sha():
    """RC1 code SHA differs from the Data lane SHA; the adapter must not require equality."""
    _real()
    if not dh.adapter_landed(LANES):
        pytest.skip("adapter not landed: asserted post-landing only")
    head = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"],
                          capture_output=True, text=True, check=False).stdout.strip()  # fmt: skip
    if len(head) != 40:
        pytest.skip("no git metadata")
    assert (
        dh.classify(REAL_DATA_MANIFEST, expected_code_sha=head)["classification"]
        == dh.ACCEPTED
    )


def test_cli_exit_codes(tmp_path):
    _real()
    run = [sys.executable, "-m", "src.convergence.data_handshake"]
    ok = subprocess.run(
        [*run, str(REAL_DATA_MANIFEST)], cwd=REPO, capture_output=True, text=True
    )
    assert ok.returncode == 0, ok.stdout + ok.stderr
    assert json.loads(ok.stdout)["match"] is True
    missing = subprocess.run(
        [*run, str(tmp_path / "none.json")], cwd=REPO, capture_output=True
    )
    assert missing.returncode == 2


# --- Phase 7: classifier semantics for the future adapter (stub consumers) --------------------


def _stub(monkeypatch, verdict_fn):
    monkeypatch.setattr(dh, "verify_data_plane_manifest", lambda p, **k: verdict_fn(p))


def test_unexpected_accept_before_landing_is_flagged(monkeypatch):
    doc = _real()
    _stub(monkeypatch, lambda p: _contract_verdict(doc))
    pre = {**LANES, "operations": {**LANES["operations"], "adapter_sha": None}}
    result = dh.classify(REAL_DATA_MANIFEST, lanes=pre)
    assert result["classification"] == dh.UNEXPECTED_ACCEPT and result["match"] is False


def test_conforming_adapter_is_accepted_after_landing(monkeypatch):
    doc = _real()
    _stub(monkeypatch, lambda p: _contract_verdict(doc))
    result = dh.classify(REAL_DATA_MANIFEST, lanes=_landed())
    assert result["classification"] == dh.ACCEPTED and result["match"] is True


def test_rejecting_adapter_after_landing_is_flagged(monkeypatch):
    _real()
    _stub(monkeypatch, lambda p: {"status": "FAIL", "ready": False, "findings": []})
    assert (
        dh.classify(REAL_DATA_MANIFEST, lanes=_landed())["classification"]
        == dh.UNEXPECTED_REJECT
    )


@pytest.mark.parametrize(
    "override,violation",
    [
        ({"status": "PASS"}, "contract:status"),  # PREPARED never becomes PASS
        ({"ready": True}, "contract:ready"),  # PREPARED is not ready for scoring
        ({"data_readiness_status": "READY"}, "contract:data_readiness_status"),
        ({"manifest_fingerprint": "9" * 64}, "contract:manifest_fingerprint"),
        ({"fingerprint_match": False}, "contract:fingerprint_match"),
        ({"code_sha": "c" * 40}, "contract:code_sha"),
        ({"model_sha": "0" * 64}, "contract:model_sha"),
        ({"findings": [{"id": "X", "severity": "FAIL"}]}, "contract:findings"),
        ({"writers_authorized": True}, "contract:writers_authorized"),
        ({"attempt2_authorized": True}, "contract:attempt2_authorized"),
        (
            {"writers_authorized": True},
            "contract:authorization_promoted:writers_authorized",
        ),
        (
            {"writer_authorized": True},
            "contract:authorization_promoted:writer_authorized",
        ),
        (
            {"attempt2_authorization": "GRANTED"},
            "contract:authorization_promoted:attempt2_authorization",
        ),
    ],
)
def test_nonconforming_adapter_verdict_is_a_contract_violation(
    monkeypatch, override, violation
):
    doc = _real()
    _stub(monkeypatch, lambda p: _contract_verdict(doc, **override))
    result = dh.classify(REAL_DATA_MANIFEST, lanes=_landed())
    assert result["classification"] == dh.CONTRACT_VIOLATION
    assert violation in result["contract_violations"] and result["match"] is False


# --- Phase 14: Data manifest tamper matrix (temp copies only) --------------------------------

TAMPER = {
    "components.firms.sha": lambda i: i["components"]["firms"].__setitem__("sha", "1" * 40),
    "components.dmc.sha": lambda i: i["components"]["dmc"].__setitem__("sha", "2" * 40),
    "code_identity.sha": lambda i: i["code_identity"].__setitem__("sha", "3" * 40),
    "model.sha256": lambda i: i["model"].__setitem__("sha256", "4" * 64),
    "baseline.sha256": lambda i: i["baseline"].__setitem__("sha256", "5" * 64),
    "topography.grid_sha256": lambda i: i["topography"].__setitem__("grid_sha256", "6" * 64),
    "readiness.NOT_PREPARED": lambda i: i.__setitem__("data_readiness_status", "NOT_PREPARED"),
    "readiness.READY": lambda i: i.__setitem__("data_readiness_status", "READY"),
    "authorizations.writers": lambda i: i["authorizations"].__setitem__("writers", True),
    "authorizations.attempt2": lambda i: i["authorizations"].__setitem__("attempt2", True),
    "data_ready_for_scoring": lambda i: i.__setitem__("data_ready_for_scoring", "READY"),
    "identity.schema_version": lambda i: i.__setitem__("schema_version", 2),
    "current_state.firms": lambda i: i["current_state"].__setitem__("firms", "PRESENT"),
}  # fmt: skip


# Re-signed identity changes the producer itself accepts: the consumer has no anchor for
# them by design; the lanes-lock pins (and the recorded fingerprint) reject them.
ANCHOR_ONLY = {
    "components.firms.sha", "components.dmc.sha", "code_identity.sha",
    "model.sha256", "baseline.sha256", "topography.grid_sha256",
}  # fmt: skip
# Re-signed manifests the PRODUCER rejects but the adapter at 13c9450 still accepts
# (open finding ADAPTER-GAP-1, owner Antigravity/Astra). Remove entries as they close.
# ADAPTER-GAP-1 closed: consumer now rejects all four re-signed fields below.
KNOWN_CONSUMER_GAPS: set[str] = set()


@pytest.mark.parametrize("resign", [False, True], ids=["naive", "resigned"])
@pytest.mark.parametrize("name", sorted(TAMPER))
def test_data_tamper_rejected(tmp_path, monkeypatch, name, resign):
    doc = copy.deepcopy(_real())
    TAMPER[name](doc["identity"])
    if resign:
        doc["fingerprint"] = dh.producer_fingerprint(doc)
    path = _write(tmp_path, doc)
    result = dh.classify(path)
    # The convergence handshake never accepts a tampered manifest.
    assert result["classification"] != dh.ACCEPTED and result["match"] is False
    consumer_accepts = result["consumer"]["status"] in dh.ACCEPTED_STATUSES
    if not resign or not dh.adapter_landed(LANES):
        assert not consumer_accepts  # fingerprint mismatch / pre-adapter consumer
    elif name in ANCHOR_ONLY | KNOWN_CONSUMER_GAPS:
        assert consumer_accepts, f"{name}: gap closed upstream, update the known sets"
        assert result["classification"] == dh.UNEXPECTED_ACCEPT
    else:
        assert not consumer_accepts  # e.g. claimed authorization, NOT_PREPARED
    # Even a worst-case adapter that PASSes everything is caught by producer + pins.
    _stub(monkeypatch, lambda p: _contract_verdict(doc))
    worst = dh.classify(path, lanes=_landed())
    assert worst["classification"] == dh.UNEXPECTED_ACCEPT and worst["match"] is False


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.__setitem__("fingerprint", "0" * 64),
        lambda d: d.__setitem__("schema_version", 2),
        lambda d: d.pop("identity"),
        lambda d: d.pop("fingerprint"),
        lambda d: d["identity"].pop("authorizations"),
    ],
    ids=[
        "fingerprint",
        "schema_version",
        "no_identity",
        "no_fingerprint",
        "no_authorizations",
    ],
)
def test_malformed_variants_rejected(tmp_path, mutate):
    doc = copy.deepcopy(_real())
    mutate(doc)
    path = _write(tmp_path, doc)
    result = dh.classify(path, lanes=_landed())
    assert result["classification"] in (dh.PRODUCER_REJECT, dh.UNEXPECTED_REJECT)
    assert result["match"] is False


@pytest.mark.parametrize("payload", ["{not json", "[]", ""])
def test_unparseable_manifest_fails_closed(tmp_path, payload):
    path = tmp_path / "DATA_PLANE_MANIFEST.json"
    path.write_text(payload, encoding="utf-8")
    result = dh.classify(path, lanes=_landed())
    assert result["producer"]["verify_manifest"] == "FAIL" and result["match"] is False
    assert result["consumer"]["status"] != "PASS"


def test_real_manifest_bytes_unchanged_by_this_module():
    raw = _real()
    before = hashlib.sha256(REAL_DATA_MANIFEST.read_bytes()).hexdigest()
    dh.classify(REAL_DATA_MANIFEST)
    assert hashlib.sha256(REAL_DATA_MANIFEST.read_bytes()).hexdigest() == before
    assert raw["fingerprint"] == LANES["data"]["manifest_fingerprint"]


# --- Post-adapter semantics: PREPARED is accepted, never authorized, never init-ready ----------


@pytest.mark.parametrize("flag", dh.AUTHORIZATION_NAMES)
def test_consumer_rejects_a_resigned_authorization_claim(tmp_path, flag):
    """Convergence fix on 13c9450: a true authorization flag is FAIL, not PREPARED."""
    doc = copy.deepcopy(_real())
    doc["identity"]["authorizations"][flag] = True
    doc["fingerprint"] = dh.producer_fingerprint(doc)
    verdict = dh.verify_data_plane_manifest(_write(tmp_path, doc))
    if not dh.adapter_landed(LANES):
        assert verdict["status"] == "FAIL"
        return
    assert verdict["status"] == "FAIL" and verdict["ready"] is False
    # V4: DM-009 AUTHORIZATION_CLAIMED is subsumed by producer semantic validation.
    assert "PRODUCER_SEMANTIC_VIOLATION" in {f["code"] for f in verdict["findings"]}


def test_prepared_opens_a_real_operator_init_but_stays_unauthorized(tmp_path):
    """PREPARED may initialize a real run (RC1-OPERATIONS-FLOW.md Step 5 precedes the
    Step 7 human ATTEMPT2_AUTHORIZATION gate; ATTEMPT2-OPERATOR.md's automation boundary
    is writers/Telegram/schedule/Jira/merge, not run creation). The safety invariant is
    that the resulting run starts in state NEW with every human gate still False, so no
    writer, Telegram, schedule, or Attempt2 authorization is ever implied by init alone.
    """
    _real()
    if not dh.adapter_landed(LANES):
        pytest.skip("asserted post-landing only")
    from src.ops.attempt2_operator.operator import Attempt2Operator
    from src.ops.attempt2_operator.states import Attempt2State

    op = Attempt2Operator.init_run(
        evidence_root=tmp_path / "ev",
        expected_code_sha="c" * 40,
        data_plane_manifest=REAL_DATA_MANIFEST,
    )
    assert op.run.current_state() == Attempt2State.NEW
    gates = op.run.read_authorizations()["gates"]
    assert not any(gates.values()), gates  # no writer/Telegram/schedule/Attempt2 gate
    op_dry = Attempt2Operator.init_run(
        evidence_root=tmp_path / "dry",
        dry_run=True,
        synthetic_identity={"code_sha": "c" * 40, "tree_sha": "d" * 40},
        expected_code_sha="c" * 40,
        data_plane_manifest=REAL_DATA_MANIFEST,
    )
    assert (
        op_dry.status()["data_plane_manifest_fingerprint"]
        == LANES["data"]["manifest_fingerprint"]
    )
    assert not any(op_dry.run.read_authorizations()["gates"].values())

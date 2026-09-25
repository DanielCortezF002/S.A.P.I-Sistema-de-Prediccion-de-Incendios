"""Isolated data-plane integration; real writers only against disposable tmp stores."""

import builtins
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import io
import json
from pathlib import Path
import socket
from unittest.mock import Mock

import pandas as pd
import pytest

from src.ingesta.firms_schema import COMMON_COLUMNS, SP_SOURCE, NRT_SOURCE
from src.ingesta.nasa_firms_backfill import Availability, NasaFirmsBackfill
from src.inference import prototype_service as svc
from src.inference.scoring_inputs import topography_sha256
from src.ops import data_readiness as gate
from src.ops.dmc_live_probe import validate_payload
from src.procesamiento import firms_source
from src.refresh import dmc_refresh as dmc, firms_refresh as firms

ROOT = Path(__file__).resolve().parents[1]
DAY = date(2026, 8, 31)


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def deny(*args, **kwargs):
        raise AssertionError("No network permitted in data-plane E2E")

    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket, "create_connection", deny)
    monkeypatch.setenv("SAPI_REPRODUCIBILITY_MODE", "0")
    for name in gate.SECRET_NAMES:
        monkeypatch.delenv(name, raising=False)


def weather(start="2026-08-29 00:00:00", end="2026-08-31 23:45:00"):
    rows = [
        {
            "momento": t.strftime(dmc.MOMENTO_FORMAT),
            "temperatura": "18 °C",
            "humedadRelativa": "70 %",
            "fuerzaDelViento": "5 kt",
            "direccionDelViento": "230 °",
        }
        for t in pd.date_range(start, end, freq="15min")
    ]
    return {
        "timezone": "UTC",
        "registros": len(rows),
        "datosEstaciones": {"estacion": {"codigoNacional": "330007"}, "datos": rows},
    }


@pytest.fixture
def space(tmp_path, monkeypatch):
    policy = json.loads(gate.POLICY_PATH.read_bytes())
    policy["expected_current"] = {"firms": "PRESENT", "dmc": "PRESENT"}
    policy["attempt1"] = (
        {}
    )  # No historical live evidence required in this synthetic policy.
    raw, processed = tmp_path / "data/raw", tmp_path / "data/processed"
    raw.mkdir(parents=True)
    processed.mkdir(parents=True)
    for item, source in (
        (policy["model"], ROOT / "models/prototype_model_d.pkl"),
        (policy["baseline"], firms_source.FIRMS_REPRODUCIBILITY_CSV),
    ):
        target = tmp_path / item["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    # Use the existing authoritative frozen grid table, explicitly as test policy.
    table = svc.REPRODUCIBILITY_TOPO_CSV.read_bytes()
    (tmp_path / "topography.csv").write_bytes(table)
    policy["topography"] = {
        "mode": "frozen_table",
        "table": "topography.csv",
        "files": {"topography.csv": gate.digest(table)},
        "grid_sha256": gate.digest(gate.canonical(gate.all_cells())),
        "table_sha256": topography_sha256(
            pd.read_csv(io.BytesIO(table)).set_index("cell_id")
        ),
    }
    evidence = validate_payload(weather(), "2026-08")
    evidence["evidence"] = {"commit": policy["components"]["dmc"]["sha"]}
    evidence["observed_at"] = "2026-09-01T00:00:00+00:00"
    evidence_path = tmp_path / "synthetic-probe.json"
    evidence_path.write_bytes(gate.canonical(evidence))
    policy["dmc_evidence"]["sha256"] = gate.digest(evidence_path.read_bytes())
    # Code identity is a separate Git test; this fixture isolates data-plane contracts.
    monkeypatch.setattr(
        gate,
        "code_identity",
        lambda *_: {
            "status": "PASS",
            "sha": "synthetic-code",
            "tree": "synthetic-tree",
            "clean": True,
        },
    )
    return tmp_path, policy, evidence_path


def publish_firms(space, bad=False):
    root, policy, _ = space
    paths = firms.FirmsPaths(
        pointer=root / "data/processed/firms/CURRENT.json",
        versions_dir=root / "data/processed/firms/versions",
        raw_dir=root / "data/raw/firms_refresh",
        baseline_csv=root / policy["baseline"]["path"],
        baseline_sha256=policy["baseline"]["sha256"],
    )
    row = dict(
        zip(
            COMMON_COLUMNS,
            [
                "-33.05",
                "-71.4",
                "331",
                "0.5",
                "0.4",
                "2026-08-31",
                "0945",
                "N",
                "VIIRS",
                "n",
                "2.0NRT",
                "291",
                "4.1",
                "D",
            ],
        )
    )
    if bad:
        row["frp"] = "invalid"

    def factory(raw_dir):
        client = NasaFirmsBackfill(
            map_key="offline", raw_dir=raw_dir, request_delay_seconds=0
        )
        client.fetch_availability = lambda: {
            SP_SOURCE: Availability(
                SP_SOURCE, DAY - timedelta(days=1), DAY - timedelta(days=1)
            ),
            NRT_SOURCE: Availability(NRT_SOURCE, DAY, DAY),
        }
        response = Mock(text=pd.DataFrame([row]).to_csv(index=False))
        response.raise_for_status.return_value = None
        client.session.get = Mock(return_value=response)
        return client

    return firms.refresh(
        paths=paths,
        map_key="offline",
        today=DAY + timedelta(days=1),
        client_factory=factory,
    )


def publish_dmc(space, bad=False):
    root, _, _ = space
    payload = weather()
    if bad:
        payload["datosEstaciones"]["datos"][0]["temperatura"] = "invalid"

    def get(url, **kwargs):
        return Mock(
            status_code=200,
            json=Mock(
                return_value=(
                    payload
                    if url.endswith("/8")
                    else weather("2026-09-01", "2026-09-01 01:00")
                )
            ),
        )

    session = Mock(get=Mock(side_effect=get))
    return dmc.refresh(
        paths=dmc.DmcPaths(root=root / "data/processed/dmc"),
        session=session,
        credentials=("offline", "offline"),
        now=datetime(2026, 9, 1, 2, tzinfo=timezone.utc),
        sleep=lambda _: None,
    )


def evaluate(space):
    root, policy, evidence = space
    return gate.evaluate(root, policy=policy, evidence=evidence)


def capture(space, monkeypatch):
    root, policy, _ = space
    monkeypatch.setattr(svc, "MODEL_PATH", root / policy["model"]["path"])
    monkeypatch.setattr(svc, "DMC_RAW_DIR", root / "data/raw")
    monkeypatch.setattr(svc, "DMC_STORE_DIR", root / "data/processed/dmc")
    monkeypatch.setattr(
        firms_source,
        "FIRMS_CURRENT_POINTER",
        root / "data/processed/firms/CURRENT.json",
    )
    monkeypatch.setattr(
        firms_source, "FIRMS_VERSIONS_DIR", root / "data/processed/firms/versions"
    )
    monkeypatch.setattr(
        firms_source, "FIRMS_BASELINE_CSV", root / policy["baseline"]["path"]
    )
    monkeypatch.setattr(
        svc,
        "_pin_topography",
        lambda _: (
            "synthetic-store-existing-frozen-table",
            pd.read_csv(root / "topography.csv").set_index("cell_id"),
        ),
    )
    return svc.capture_scoring_inputs()


def test_data_plane_e2e_production_publications_scoringinputs_and_readiness(
    space, monkeypatch
):
    publish_firms(space)
    publish_dmc(space)
    inputs = capture(space, monkeypatch)
    assert inputs.firms_origin == "current"
    assert inputs.dmc_pointer_version
    assert inputs.fingerprint == capture(space, monkeypatch).fingerprint
    assert inputs.firms_sha256 and len(inputs.topography) == 50
    result = evaluate(space)
    assert result["status"] == "PREPARED", result["findings"]
    assert result["current_state"] == {"firms": "PRESENT", "dmc": "PRESENT"}
    assert result["data_ready_for_scoring"] == "NOT_EVALUATED"
    assert not any(result["authorizations"].values())


@pytest.mark.parametrize("source", ["firms", "dmc"])
def test_bad_source_blocks_publication_and_readiness(space, source):
    publisher = publish_firms if source == "firms" else publish_dmc
    with pytest.raises((firms.FirmsRefreshError, dmc.DmcRefreshError)):
        publisher(space, bad=True)
    assert evaluate(space)["status"] != "PREPARED"
    assert not list(space[0].rglob("CURRENT.json"))


@pytest.mark.parametrize(
    "defect",
    [
        "missing_model",
        "model_sha",
        "topography",
        "firms_current",
        "dmc_current",
        "firms_version_sha",
        "dmc_version_sha",
        "unknown_state",
        "evidence_sha",
        "dmc_count",
        "baseline_sha",
    ],
)
def test_negative_e2e_never_prepared(space, defect):
    root, policy, evidence = space
    publish_firms(space)
    publish_dmc(space)
    if defect == "missing_model":
        (root / policy["model"]["path"]).unlink()
    elif defect == "model_sha":
        policy["model"]["sha256"] = "0" * 64
    elif defect == "topography":
        (root / "topography.csv").write_text("tampered")
    elif defect in ("firms_current", "dmc_current"):
        suffix = (
            "firms/CURRENT.json"
            if defect == "firms_current"
            else "dmc/330007/CURRENT.json"
        )
        (root / "data/processed" / suffix).write_text('{"schema_version": 999}')
    elif defect in ("firms_version_sha", "dmc_version_sha"):
        suffix = (
            "firms/versions" if defect == "firms_version_sha" else "dmc/330007/versions"
        )
        path = next(
            p
            for p in (root / "data/processed" / suffix).iterdir()
            if p.suffix == (".csv" if defect == "firms_version_sha" else ".json")
        )
        path.write_bytes(path.read_bytes() + b" ")
    elif defect == "dmc_count":
        path = root / "data/processed/dmc/330007/CURRENT.json"
        pointer = json.loads(path.read_bytes())
        pointer["record_count"] += 1
        path.write_text(json.dumps(pointer))
    elif defect == "baseline_sha":
        policy["baseline"]["sha256"] = "0" * 64
    elif defect == "unknown_state":
        policy["expected_current"]["dmc"] = "UNKNOWN"
    else:
        evidence.write_text("{}")
    assert evaluate(space)["status"] != "PREPARED"


def test_absent_current_preparation_is_not_scoring_ready(space):
    space[1]["expected_current"] = {"firms": "ABSENT", "dmc": "ABSENT"}
    result = evaluate(space)
    assert result["status"] == "PREPARED"
    assert result["current_state"] == {"firms": "ABSENT", "dmc": "ABSENT"}
    assert result["data_ready_for_scoring"] == "NOT_EVALUATED"


def test_manifest_clock_and_root_independence_and_tamper_detection(space):
    space[1]["expected_current"] = {"firms": "ABSENT", "dmc": "ABSENT"}
    result = evaluate(space)
    first = gate.build_manifest(
        result, space[1], workspace=space[0], created_at="first"
    )
    second_result = deepcopy(result)
    second_result["observed_at_start"] = "later"
    second_result["observed_at_end"] = "later"
    second = gate.build_manifest(
        second_result, space[1], workspace=space[0] / "other", created_at="later"
    )
    assert first["fingerprint"] == second["fingerprint"]
    assert gate.verify_manifest(first) and gate.verify_manifest(second)
    unknown = deepcopy(first)
    unknown["identity"]["current_state"]["dmc"] = "UNKNOWN"
    unknown["fingerprint"] = gate.digest(gate.canonical(unknown["identity"]))
    assert not gate.verify_manifest(unknown)
    first["identity"]["model"]["sha256"] = "0" * 64
    assert not gate.verify_manifest(first)
    second["identity"]["authorizations"]["writers"] = True
    second["fingerprint"] = gate.digest(gate.canonical(second["identity"]))
    assert not gate.verify_manifest(second)


def test_gate_cannot_write_or_call_network_writers(space, monkeypatch):
    publish_firms(space)
    publish_dmc(space)
    before = gate.inventory(space[0], space[1]["inventory_roots"])
    original = builtins.open

    def guarded(file, mode="r", *args, **kwargs):
        assert not any(c in mode for c in "wax+")
        return original(file, mode, *args, **kwargs)

    def deny(*args, **kwargs):
        raise AssertionError("No publication or writes from readiness")

    monkeypatch.setattr(builtins, "open", guarded)
    for attr in ("write_bytes", "write_text", "mkdir", "unlink", "rename", "replace"):
        monkeypatch.setattr(Path, attr, deny)
    for module in (firms, dmc):
        for attr in (
            "refresh",
            "rollback",
            "_publish",
            "write_immutable",
            "atomic_write_json",
            "append_jsonl",
        ):
            monkeypatch.setattr(module, attr, deny)
    assert evaluate(space)["status"] == "PREPARED"
    assert gate.inventory(space[0], space[1]["inventory_roots"]) == before


def test_missing_evidence_unknown_code_and_secret_bearing_exception_are_safe(
    space, monkeypatch
):
    token = "secret-fixture-not-for-output"
    monkeypatch.setenv("DMC_TOKEN", token)
    monkeypatch.setattr(gate, "code_identity", lambda *_: {"status": "UNKNOWN"})

    def broken(*args):
        raise ValueError(token)

    monkeypatch.setattr(gate, "topography", broken)
    result = gate.evaluate(space[0], policy=space[1], evidence=None)
    assert result["status"] != "PREPARED"
    assert token not in json.dumps(result)
    assert result["credentials_present"]["DMC_TOKEN"] is True


def test_git_identity_rejects_unavailable_repo(tmp_path):
    assert (
        gate.code_identity(tmp_path, {"firms": {"sha": "0" * 40, "files": []}})[
            "status"
        ]
        == "UNKNOWN"
    )


def test_changed_store_cannot_report_prepared(space, monkeypatch):
    space[1]["expected_current"] = {"firms": "ABSENT", "dmc": "ABSENT"}
    actual = gate.inventory
    calls = 0

    def changed(*args):
        nonlocal calls
        calls += 1
        result = actual(*args)
        if calls == 2:
            result["sha256"] = "0" * 64
        return result

    monkeypatch.setattr(gate, "inventory", changed)
    assert evaluate(space)["status"] == "INCOMPLETE"


@pytest.mark.parametrize(
    "dirty,changed,expected",
    [(False, False, "PASS"), (True, False, "FAIL"), (False, True, "FAIL")],
)
def test_code_identity_requires_clean_tree_and_exact_component_blobs(
    monkeypatch, tmp_path, dirty, changed, expected
):
    def git(command, **kwargs):
        args = command[3:]
        if args[0] == "status":
            return b" M source.py" if dirty else b""
        if args[0] == "merge-base":
            return b""
        if args[1] == "HEAD:source.py":
            return b"different" if changed else b"blob"
        if args[1] == "commit:source.py":
            return b"blob"
        return b"identity"

    monkeypatch.setattr(gate.subprocess, "check_output", git)
    assert (
        gate.code_identity(
            tmp_path, {"component": {"sha": "commit", "files": ["source.py"]}}
        )["status"]
        == expected
    )


def test_source_evidence_reads_same_bytes_for_hash_and_parse(space, monkeypatch):
    original = Path.read_bytes
    count = 0

    def read(path):
        nonlocal count
        if path == space[2]:
            count += 1
            if count > 1:
                raise AssertionError("Evidence must be pinned once")
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", read)
    assert gate.source_evidence(space[2], space[1])["status"] == "PASS"
    assert count == 1


@pytest.mark.parametrize(
    "value",
    [
        None,
        [],
        {},
        {"identity": []},
        {"identity": {"data_readiness_status": "PREPARED", "findings": []}},
    ],
)
def test_malformed_manifest_is_never_valid(value):
    assert gate.verify_manifest(value) is False

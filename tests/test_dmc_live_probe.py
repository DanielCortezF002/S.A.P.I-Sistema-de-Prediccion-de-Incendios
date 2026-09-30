"""Offline tests: the live probe shares production validation and cannot publish."""

import builtins
from copy import deepcopy
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import socket
from unittest.mock import Mock
from urllib.parse import quote

import pandas as pd
import pytest
import requests

from src.ops import dmc_live_probe as probe
from src.refresh import dmc_refresh as dmc
from src.inference.scoring_inputs import pin_dmc

MONTH = "2026-09"
CREDS = ("fixture-user+private@example.invalid", "fixture-token/secret?&value")


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("No real network in synthetic probe tests")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)


def payload(count=200, nulls=0):
    rows = [
        {
            "momento": (datetime(2026, 9, 1) + timedelta(minutes=15 * i)).strftime(
                dmc.MOMENTO_FORMAT
            ),
            "temperatura": None if i < nulls else "18.8 °C",
            "humedadRelativa": "72 %",
            "fuerzaDelViento": "8.5 kt",
            "direccionDelViento": "230 °",
        }
        for i in range(count)
    ]
    return {
        "timezone": "UTC",
        "registros": count,
        "datosEstaciones": {"estacion": {"codigoNacional": "330007"}, "datos": rows},
    }


def fake_session(data=None, *, raw=None, status=200):
    response = Mock(
        status_code=status, headers={"Content-Type": "application/json; charset=utf-8"}
    )
    response.iter_content.return_value = [
        raw if raw is not None else json.dumps(data).encode()
    ]
    session = Mock()
    session.get.return_value = response
    return session


@pytest.mark.parametrize(
    "count,nulls,category,code",
    [
        (200, 0, "VALID", 0),
        (200, 1, "NULLS_ALLOWED_WITHIN_CONTRACT", 0),
        (100, 1, "NULLS_ALLOWED_WITHIN_CONTRACT", 0),
        (199, 2, "NULLS_EXCEED_LIMIT", 65),
        (100, 2, "NULLS_EXCEED_LIMIT", 65),
        (0, 0, "EMPTY_RESPONSE", 65),
    ],
)
def test_exact_production_null_contract(count, nulls, category, code):
    result = probe.validate_payload(payload(count, nulls), MONTH)
    assert result["validation"]["category"] == category
    assert result["exit_code"] == code
    assert result["records"]["received"] == count
    assert result["records"]["null_rows"] == nulls
    assert result["dry_run"]["publication_performed"] is False
    if code == 0:
        candidate = dmc.prepare_month_payload(payload(count, nulls), "330007", MONTH)
        assert result["validation"]["candidate_sha256"] == dmc.sha256_bytes(
            candidate.data
        )
        assert result["records"]["valid_candidate"] == count - nulls


@pytest.mark.parametrize("field", dmc.REQUIRED_NUMERIC_FIELDS)
@pytest.mark.parametrize("bad", ["missing", "bad", "", True, float("inf")])
def test_missing_and_nonnumeric(field, bad):
    document = payload()
    if bad == "missing":
        del document["datosEstaciones"]["datos"][0][field]
    else:
        document["datosEstaciones"]["datos"][0][field] = bad
    result = probe.validate_payload(document, MONTH)
    assert result["status"] == "INCOMPATIBLE"
    expected = (
        "MISSING_REQUIRED_FIELD" if bad == "missing" else "NONNUMERIC_REQUIRED_FIELD"
    )
    assert result["validation"]["category"] == expected


@pytest.mark.parametrize("document", [None, [], {}, {"timezone": "local"}])
def test_malformed_document(document):
    assert (
        probe.validate_payload(document, MONTH)["validation"]["category"]
        == "MALFORMED_RESPONSE"
    )


@pytest.mark.parametrize("field,value", [("registros", 999), ("timezone", "local")])
def test_count_and_timezone_contract(field, value):
    document = payload()
    document[field] = value
    assert probe.validate_payload(document, MONTH)["exit_code"] == 65


def test_out_of_month_is_not_accepted():
    document = payload()
    document["datosEstaciones"]["datos"][0]["momento"] = "2026-08-31 00:00:00"
    assert probe.validate_payload(document, MONTH)["exit_code"] == 65


def test_single_request_uses_production_url_and_safe_metadata():
    session = fake_session(payload())
    result = probe.probe(MONTH, credentials=CREDS, session=session)
    assert result["status"] == "COMPATIBLE"
    session.get.assert_called_once_with(
        dmc.month_source_url("330007", MONTH),
        params={"usuario": CREDS[0], "token": CREDS[1]},
        timeout=probe.TIMEOUT,
        allow_redirects=False,
        stream=True,
    )
    assert result["http"]["status"] == 200
    assert result["http"]["response_bytes"] > 0
    assert result["http"]["content_type"] == "application/json"
    session.get.return_value.close.assert_called_once()


@pytest.mark.parametrize(
    "raw,category",
    [(b"", "EMPTY_RESPONSE"), (b"<html>bad</html>", "MALFORMED_RESPONSE")],
)
def test_invalid_http_body(raw, category):
    result = probe.probe(MONTH, credentials=CREDS, session=fake_session(raw=raw))
    assert result["validation"]["category"] == category
    assert result["exit_code"] == 65


@pytest.mark.parametrize("status", [301, 401, 429, 500])
def test_http_failure_no_redirect_no_retry(status):
    session = fake_session(payload(), status=status)
    result = probe.probe(MONTH, credentials=CREDS, session=session)
    assert result["status"] == "NETWORK_UNAVAILABLE"
    assert result["exit_code"] == 69
    assert session.get.call_count == 1


def test_network_exception_redacted_without_retry():
    session = Mock()
    session.get.side_effect = requests.ConnectionError(
        "?usuario=" + quote(CREDS[0]) + "&token=" + quote(CREDS[1])
    )
    result = probe.probe(MONTH, credentials=CREDS, session=session)
    assert result["status"] == "NETWORK_UNAVAILABLE"
    assert session.get.call_count == 1
    text = json.dumps(result)
    for value in CREDS:
        assert value not in text and quote(value) not in text


def test_config_missing_never_requests():
    session = Mock()
    result = probe.probe(MONTH, credentials=("", ""), session=session)
    assert result["status"] == "CONFIG_MISSING" and result["exit_code"] == 78
    session.get.assert_not_called()


def test_response_values_and_headers_cannot_leak_credentials():
    document = payload()
    document["datosEstaciones"]["datos"][0]["temperatura"] = CREDS[1]
    session = fake_session(document)
    session.get.return_value.headers["Set-Cookie"] = CREDS[0]
    session.get.return_value.headers["Authorization"] = CREDS[1]
    result = probe.probe(MONTH, credentials=CREDS, session=session)
    text = json.dumps(result)
    assert all(value not in text and quote(value) not in text for value in CREDS)
    assert "Set-Cookie" not in text and "Authorization" not in text


def test_bounded_response(monkeypatch):
    monkeypatch.setattr(probe, "MAX_BYTES", 8)
    result = probe.probe(MONTH, credentials=CREDS, session=fake_session(payload()))
    assert result["status"] == "INCOMPLETE" and result["exit_code"] != 0


def test_deterministic_validation_and_canonical_identity():
    original = payload()
    reverse = deepcopy(original)
    reverse["datosEstaciones"]["datos"].reverse()
    first, second = [probe.validate_payload(p, MONTH) for p in (original, reverse)]
    first.pop("observed_at")
    second.pop("observed_at")
    assert first == second


def test_conflicting_duplicate_order_is_explicit_production_contract():
    document = payload(2)
    document["datosEstaciones"]["datos"][1].update(
        momento="2026-09-01 00:00:00", temperatura="25 °C"
    )
    result = probe.validate_payload(document, MONTH)
    assert result["records"]["duplicate_moments"] == 1
    assert result["records"]["conflicts"] == 1
    assert any(f["code"] == "ORDER_SENSITIVE_CONFLICTS" for f in result["findings"])


def test_probe_and_preflight_cannot_write_files_or_call_publisher(
    monkeypatch, tmp_path
):
    sentinel = tmp_path / "production"
    sentinel.mkdir()
    for name in (
        "CURRENT.json",
        "versions.json",
        "pointer_history.jsonl",
        "raw.json",
        "processed.json",
    ):
        (sentinel / name).write_bytes(b"preserved")
    before = {p.name: p.read_bytes() for p in sentinel.iterdir()}
    read_open, os_open = builtins.open, os.open

    def guarded_open(file, mode="r", *args, **kwargs):
        assert not any(flag in mode for flag in "wax+"), "Probe attempted a write"
        return read_open(file, mode, *args, **kwargs)

    def guarded_os_open(file, flags, *args, **kwargs):
        assert not flags & (
            os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND
        )
        return os_open(file, flags, *args, **kwargs)

    def forbidden(*args, **kwargs):
        raise AssertionError("Publication/filesystem mutation is forbidden")

    with monkeypatch.context() as guard:
        guard.setattr(builtins, "open", guarded_open)
        guard.setattr(os, "open", guarded_os_open)
        for name in (
            "write_bytes",
            "write_text",
            "mkdir",
            "unlink",
            "rename",
            "replace",
        ):
            guard.setattr(Path, name, forbidden)
        for name in (
            "refresh",
            "_publish",
            "write_immutable",
            "atomic_write_json",
            "append_jsonl",
            "refresh_lock",
        ):
            guard.setattr(dmc, name, forbidden)
        result = probe.probe(MONTH, credentials=CREDS, session=fake_session(payload()))
        assert result["status"] == "COMPATIBLE"
    assert {p.name: p.read_bytes() for p in sentinel.iterdir()} == before


def test_accepted_candidate_is_compatible_with_scoringinputs_without_writer(tmp_path):
    document = payload(200, 1)
    accepted = probe.validate_payload(document, MONTH)
    assert accepted["status"] == "COMPATIBLE"
    prepared = dmc.prepare_month_payload(document, "330007", MONTH)
    # Synthetic safe legacy input: exercise actual pin_dmc, never CURRENT or Model D.
    (tmp_path / "dmc_historico_330007_2026-09.json").write_bytes(prepared.data)
    pinned = pin_dmc("330007", legacy_dir=tmp_path, store_dir=None)
    assert len(pinned.series) == accepted["records"]["valid_candidate"] == 199
    assert pinned.series["momento"].min() == pd.Timestamp(
        accepted["coverage"]["start"], tz="UTC"
    )
    assert pinned.files[0].sha256 == accepted["validation"]["candidate_sha256"]


def test_cli_output_and_exit_code(monkeypatch, capsys):
    monkeypatch.setattr(dmc, "DMC_USUARIO", "")
    monkeypatch.setattr(dmc, "DMC_TOKEN", "")
    assert probe.main(["--month", MONTH]) == 78
    assert json.loads(capsys.readouterr().out)["status"] == "CONFIG_MISSING"


def test_rejected_month_preserves_received_coverage():
    result = probe.validate_payload(payload(100, 2), MONTH)
    assert result["coverage"]["received_start"] == "2026-09-01 00:00:00"
    assert result["coverage"]["received_end"] == "2026-09-02 00:45:00"
    assert result["coverage"]["start"] is None
    assert result["dry_run"]["writer_would_accept_payload"] is False


def test_cleanup_exception_cannot_leak_secrets():
    session = fake_session(payload())
    session.get.return_value.close.side_effect = RuntimeError(CREDS[1])
    result = probe.probe(MONTH, credentials=CREDS, session=session)
    assert result["status"] == "COMPATIBLE"
    assert CREDS[1] not in json.dumps(result)

"""Source/normalizer and v3 gate self-tests; synthetic payloads, sockets blocked."""

import hashlib
import io
import json
from datetime import date, datetime, timezone, timedelta

import pandas as pd
import pytest

from src.ingesta import firms_schema as schema
from src.procesamiento.firms_source import FirmsSourceError, resolve_firms_source
from src.refresh import firms_refresh as fr
from src.refresh.firms_validation import validate_publication
import test_firms_refresh as refresh_fixtures
from test_firms_refresh import (
    FakeFirms,
    _refresh,
    _pointer,
    API_COLUMNS,
    _row,
)

paths = refresh_fixtures.paths
_no_network = refresh_fixtures._no_network

START = date(2026, 8, 31)


def body():
    return API_COLUMNS + "\n" + _row(START) + "\n"


def parse(text, source=schema.NRT_SOURCE):
    return schema.parse_source_csv(text, source, START, START)


@pytest.mark.parametrize("missing", schema.COMMON_COLUMNS)
def test_every_common_column_is_required(missing):
    frame = pd.read_csv(io.StringIO(body())).drop(columns=missing)
    with pytest.raises(ValueError, match="faltan"):
        parse(frame.to_csv(index=False))


@pytest.mark.parametrize(
    "extra", ["type", "unknown", "firms_source", "request_start_date"]
)
def test_extras_and_spoofed_provenance_rejected(extra):
    frame = pd.read_csv(io.StringIO(body())).assign(**{extra: "unexpected"})
    with pytest.raises(ValueError, match="extra"):
        parse(frame.to_csv(index=False))


def test_reordered_header_normalizes_deterministically():
    frame = pd.read_csv(io.StringIO(body()), dtype=str)
    first = parse(body())
    second = parse(frame[frame.columns[::-1]].to_csv(index=False))
    pd.testing.assert_frame_equal(first, second)
    assert schema.serialize(first) == schema.serialize(second)
    assert (
        hashlib.sha256(schema.serialize(first)).hexdigest()
        == hashlib.sha256(schema.serialize(second)).hexdigest()
    )


def test_sp_type_is_preserved_and_nrt_never_gains_it():
    frame = pd.read_csv(io.StringIO(body()), dtype=str).assign(version="2", type="2")
    standard = parse(frame.to_csv(index=False), schema.SP_SOURCE)
    assert standard["type"].tolist() == ["2"]
    nrt = parse(body())
    assert "type" not in nrt
    projected = schema.project_frame(pd.concat([standard, nrt]), require_sp_type=True)
    assert "type" not in projected
    assert standard["type"].tolist() == ["2"]  # input not mutated
    assert list(projected.columns) == list(schema.OPERATIONAL_COLUMNS)


@pytest.mark.parametrize(
    "field,value",
    [
        ("latitude", "nan"),
        ("longitude", "181"),
        ("frp", "inf"),
        ("scan", "0"),
        ("track", "-1"),
        ("bright_ti4", "bad"),
        ("bright_ti5", ""),
        ("acq_time", "2400"),
        ("acq_time", "1260"),
        ("acq_date", "2026-02-30"),
        ("confidence", "100"),
        ("satellite", "N20"),
        ("instrument", "MODIS"),
        ("version", "2"),
        ("daynight", "X"),
    ],
)
def test_invalid_values_rejected(field, value):
    frame = pd.read_csv(io.StringIO(body()), dtype=str)
    frame.loc[0, field] = value
    with pytest.raises(ValueError):
        parse(frame.to_csv(index=False))


@pytest.mark.parametrize(
    "text",
    [
        "",
        "<html>error</html>",
        "a,a\n1,2\n",
        '"unterminated',
        API_COLUMNS + "\nshort,row\n",
        body().rstrip() + ",extra\n",
    ],
)
def test_malformed_csv_rejected(text):
    with pytest.raises(ValueError):
        parse(text)


@pytest.mark.parametrize("version", ["2.0NRT", "2.0RT", "2.0URT"])
def test_nrt_endpoint_documented_latency_variants(version):
    assert parse(body().replace("2.0NRT", version))["version"].tolist() == [version]


def test_empty_nrt_and_sp_and_invalid_sp_type():
    assert parse(API_COLUMNS + "\n").empty
    assert parse(API_COLUMNS + ",type\n", schema.SP_SOURCE).empty
    frame = pd.read_csv(io.StringIO(body()), dtype=str).assign(version="2", type="9")
    with pytest.raises(ValueError, match="type"):
        parse(frame.to_csv(index=False), schema.SP_SOURCE)
    with pytest.raises(ValueError, match="faltan"):
        parse(body().replace("2.0NRT", "2"), schema.SP_SOURCE)


def test_validator_selftest_accepts_and_rejects_tampering(paths):
    from scripts.validate_firms import main

    _refresh(paths, FakeFirms())
    original = paths.pointer.read_bytes()
    p = _pointer(paths)
    version = paths.versions_dir / p["relative_path"]
    assert main(paths) == 0
    original_csv = version.read_bytes()
    version.write_bytes(original_csv + b"tampered\n")
    assert main(paths) == 1
    version.write_bytes(original_csv)
    raw = __import__("pathlib").Path(p["raw_artifacts"][0]["path"])
    original_raw = raw.read_bytes()
    raw.write_bytes(original_raw.replace(b"331.0", b"332.0"))
    with pytest.raises(ValueError, match="Hash raw"):
        validate_publication(paths)
    raw.write_bytes(original_raw)
    p["projected_base_sha256"] = "0" * 64
    paths.pointer.write_text(json.dumps(p))
    assert main(paths) == 1
    paths.pointer.write_bytes(original)
    assert main(paths) == 0


@pytest.mark.parametrize(
    "key,value",
    [
        ("data_contract", "unknown"),
        ("row_count", 999),
        ("new_rows", -1),
        ("base_sha256", "bad"),
        ("raw_artifacts", []),
    ],
)
def test_resolver_rejects_v3_metadata_tampering(paths, key, value):
    _refresh(paths, FakeFirms())
    pointer = _pointer(paths)
    pointer[key] = value
    paths.pointer.write_text(json.dumps(pointer))
    with pytest.raises(FirmsSourceError):
        resolve_firms_source(
            reproducibility=False,
            pointer_path=paths.pointer,
            versions_dir=paths.versions_dir,
        )


def test_gate_verifies_second_generation_and_empty_window(paths):
    _refresh(paths, FakeFirms())
    first = _pointer(paths)
    _refresh(
        paths, FakeFirms(body=lambda *_: API_COLUMNS + "\n"), today=date(2026, 9, 8)
    )
    result = validate_publication(paths)
    assert result["new_rows"] == 0
    assert _pointer(paths)["base_relative_path"] == first["relative_path"]


def test_publication_manifest_deterministic_with_fixed_clock(paths, monkeypatch):
    # Different run timestamps legitimately change provenance; freeze that input.
    monkeypatch.setattr(
        fr, "_utcnow", lambda: datetime(2026, 9, 6, tzinfo=timezone.utc)
    )
    _refresh(paths, FakeFirms())
    first = paths.pointer.read_bytes()
    paths.pointer.unlink()  # synthetic store only, replay same immutable inputs
    _refresh(paths, FakeFirms())
    assert paths.pointer.read_bytes() == first
    assert validate_publication(paths)["result"] == "FIRMS ACCEPTED"


def test_sp_publication_retains_classification_in_hashed_raw(paths):
    from src.ingesta.nasa_firms_backfill import NasaFirmsBackfill, Availability
    from unittest.mock import Mock

    text = API_COLUMNS + ",type\n" + _row(START).replace("2.0NRT", "2") + ",2\n"

    def factory(raw_dir):
        client = NasaFirmsBackfill(map_key="offline", raw_dir=raw_dir)
        response = Mock(text=text)
        response.raise_for_status.return_value = None
        client.session.get = Mock(return_value=response)
        client.fetch_availability = lambda: {
            schema.SP_SOURCE: Availability(schema.SP_SOURCE, START, START),
            schema.NRT_SOURCE: Availability(
                schema.NRT_SOURCE, START + timedelta(days=1), START + timedelta(days=1)
            ),
        }
        return client

    result = fr.refresh(
        paths=paths,
        client_factory=factory,
        map_key="offline",
        today=START + timedelta(days=1),
    )
    raw = __import__("pathlib").Path(result.pointer["raw_artifacts"][0]["path"])
    assert pd.read_csv(raw)["type"].tolist() == [2]
    assert (
        result.pointer["raw_artifacts"][0]["sha256"]
        == hashlib.sha256(raw.read_bytes()).hexdigest()
    )
    assert validate_publication(paths)["result"] == "FIRMS ACCEPTED"


def test_v3_projection_keeps_model_d_ranking_and_scoring_metadata(paths, monkeypatch):
    from dataclasses import replace
    from src.inference import prototype_service as svc
    from src.procesamiento.firms_source import FIRMS_REPRODUCIBILITY_CSV

    base = FIRMS_REPRODUCIBILITY_CSV.read_bytes()
    paths.baseline_csv.write_bytes(base)  # byte copy to synthetic tmp_path
    paths = replace(paths, baseline_sha256=hashlib.sha256(base).hexdigest())
    _refresh(paths, FakeFirms(body=lambda *_: API_COLUMNS + "\n"))
    monkeypatch.setenv("SAPI_REPRODUCIBILITY_MODE", "1")
    monkeypatch.setattr(
        svc,
        "resolve_firms_source",
        lambda **kwargs: resolve_firms_source(
            reproducibility=False,
            pointer_path=paths.pointer,
            versions_dir=paths.versions_dir,
        ),
    )
    inputs = svc.capture_scoring_inputs()
    assert "type" not in inputs.fires
    result = svc.score_current_grid(inputs=inputs)
    ranking = hashlib.sha256(
        "\n".join(f"{c.cell_id},{c.score!r},{c.rank}" for c in result.cells).encode()
    ).hexdigest()
    assert ranking == "33c2eacc49bd0cc130928b5bd182ec523e63614f0e3dd97a129a8d4657f231ff"
    assert result.firms_origin == "current"
    assert result.firms_coverage_end == date(2026, 9, 5)
    assert result.firms_status == svc.FIRMS_STATUS_CURRENT
    assert (
        result.firms_lag_days == (result.forecast_time.date() - date(2026, 9, 5)).days
    )
    assert result.inputs_fingerprint == inputs.fingerprint
    assert result.scoring_inputs["firms"]["sha256"] == _pointer(paths)["sha256"]


def test_gate_rebuild_rejects_csv_even_if_its_hash_is_updated(paths):
    _refresh(paths, FakeFirms())
    p = _pointer(paths)
    version = paths.versions_dir / p["relative_path"]
    data = version.read_bytes().replace(b"331.0", b"332.0")
    version.write_bytes(data)
    p["sha256"] = hashlib.sha256(data).hexdigest()
    paths.pointer.write_text(json.dumps(p))
    with pytest.raises(ValueError, match="no coincide con base y raw"):
        validate_publication(paths)


@pytest.mark.parametrize("bad_type", ["0", "null"])
def test_historical_nrt_classification_is_not_fabricated(bad_type):
    frame = parse(body()).assign(type=bad_type)
    with pytest.raises(ValueError, match="NRT no puede"):
        schema.project_frame(frame)


def test_sp_type_missing_in_delta_cannot_use_operational_contract():
    frame = parse(body()).assign(firms_source=schema.SP_SOURCE, version="2")
    with pytest.raises(ValueError, match="Falta clasificación"):
        schema.project_frame(frame, require_sp_type=True)

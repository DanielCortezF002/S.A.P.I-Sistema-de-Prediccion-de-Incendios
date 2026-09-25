"""TR-K / NM-02: offline publication regressions in disposable synthetic stores."""

from collections import Counter
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import socket
from unittest.mock import Mock

import pandas as pd
import pytest

from src.ingesta import firms_schema as schema
from src.ingesta.nasa_firms_backfill import Availability, NasaFirmsBackfill
from src.procesamiento.firms_source import resolve_firms_source
from src.refresh import firms_refresh as fr
from src.refresh.firms_validation import validate_publication

START = date(2026, 8, 31)
PERMUTATIONS = ((0, 1, 2), (2, 1, 0), (1, 2, 0))


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("Real network forbidden in review remediation tests")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(
        fr, "_utcnow", lambda: datetime(2026, 9, 6, tzinfo=timezone.utc)
    )


def row(day=START, **changes):
    values = dict(
        zip(
            schema.COMMON_COLUMNS,
            (
                "-33.05",
                "-71.4",
                "331.0",
                "0.5",
                "0.4",
                day.isoformat(),
                "0945",
                "N",
                "VIIRS",
                "n",
                "2.0NRT",
                "291.0",
                "4.1",
                "D",
            ),
        )
    )
    return {**values, **changes}


def csv_text(rows):
    return pd.DataFrame(rows).to_csv(index=False, lineterminator="\n")


def new_paths(root):
    root.mkdir(parents=True, exist_ok=True)
    baseline = csv_text(
        [
            row(
                START - timedelta(days=2),
                version="2",
                type="2",
                firms_source=schema.SP_SOURCE,
                request_start_date="2026-08-26",
            )
        ]
    )
    data = baseline.replace("\n", "\r\n").encode()
    path = root / "baseline.csv"
    path.write_bytes(data)
    return fr.FirmsPaths(
        pointer=root / "firms/CURRENT.json",
        versions_dir=root / "firms/versions",
        raw_dir=root / "raw",
        baseline_csv=path,
        baseline_sha256=hashlib.sha256(data).hexdigest(),
    )


def factory_for(payloads, availability, calls, frame_order=None):
    def factory(raw_dir):
        client = NasaFirmsBackfill(
            map_key="offline", raw_dir=raw_dir, request_delay_seconds=0
        )
        client.fetch_availability = lambda: availability

        def respond(url, timeout):
            source = next(source for source in payloads if "/" + source + "/" in url)
            calls.append(source)
            response = Mock(text=payloads[source])
            response.raise_for_status.return_value = None
            return response

        client.session.get = respond
        if frame_order is not None:
            # Real parser/raw persistence still run. Only the returned batch order differs;
            # this freezes raw bytes/path/clock when comparing the COMPLETE manifest.
            download = client.download_window

            def reordered(window):
                path, frame = download(window)
                return path, frame.iloc[list(frame_order)].reset_index(drop=True)

            client.download_window = reordered
        return client

    return factory


def publish_nrt(paths, rows, frame_order=None):
    availability = {
        schema.SP_SOURCE: Availability(
            schema.SP_SOURCE, date(2012, 1, 20), START - timedelta(days=1)
        ),
        schema.NRT_SOURCE: Availability(schema.NRT_SOURCE, START, START),
    }
    return fr.refresh(
        paths=paths,
        map_key="offline",
        today=START + timedelta(days=1),
        client_factory=factory_for(
            {schema.NRT_SOURCE: csv_text(rows)}, availability, [], frame_order
        ),
    )


def publication_files(paths):
    return {
        p.relative_to(paths.pointer.parent).as_posix(): p.read_bytes()
        for p in paths.pointer.parent.rglob("*")
        if p.is_file()
    }


@pytest.mark.parametrize("existing_current", [False, True])
@pytest.mark.parametrize(
    "defect",
    [
        "latitude",
        "longitude",
        "acq_date",
        "acq_time",
        "frp",
        "confidence",
        "extra_type",
    ],
)
def test_trk_mixed_valid_sp_and_broken_nrt_cannot_publish(
    tmp_path, existing_current, defect
):
    paths = new_paths(tmp_path / "store")
    if existing_current:
        publish_nrt(paths, [row()])
    first_day = START + timedelta(days=int(existing_current))
    nrt_day = first_day + timedelta(days=1)
    standard = row(first_day, version="2", type="2")
    broken = row(nrt_day)
    if defect == "extra_type":
        broken["type"] = "2"
    else:
        del broken[defect]
    calls = []
    availability = {
        schema.SP_SOURCE: Availability(schema.SP_SOURCE, first_day, first_day),
        schema.NRT_SOURCE: Availability(schema.NRT_SOURCE, nrt_day, nrt_day),
    }
    before, baseline = publication_files(paths), paths.baseline_csv.read_bytes()
    with pytest.raises(fr.FirmsRefreshError) as error:
        fr.refresh(
            paths=paths,
            map_key="offline",
            today=nrt_day + timedelta(days=1),
            client_factory=factory_for(
                {
                    schema.SP_SOURCE: csv_text([standard]),
                    schema.NRT_SOURCE: csv_text([broken]),
                },
                availability,
                calls,
            ),
        )
    assert error.value.exit_code == fr.EXIT_DATA
    assert calls == [schema.SP_SOURCE, schema.NRT_SOURCE]
    assert (
        publication_files(paths) == before
    )  # no partial version, sidecar, history or CURRENT
    assert paths.pointer.exists() == existing_current
    assert not paths.lock.exists()
    assert paths.baseline_csv.read_bytes() == baseline
    raw = list(paths.raw_dir.rglob(schema.SP_SOURCE + "/*.csv"))
    assert len(raw) == 1
    assert pd.read_csv(raw[0], dtype=str)["type"].tolist() == ["2"]


def tied_rows():
    # Same old numeric sort/dedupe key, distinct persisted observations/tokens.
    return [
        row(),
        row(frp="9.9"),
        row(confidence="h", latitude="-33.050", acq_time="945"),
    ]


def records(frame):
    return Counter(tuple(record) for record in frame.itertuples(index=False, name=None))


def test_nm02_build_version_total_order_preserves_every_tied_record(tmp_path):
    paths = new_paths(tmp_path / "store")
    rows = tied_rows()
    outputs = []
    expected = schema.project_frame(
        schema.parse_source_csv(csv_text(rows), schema.NRT_SOURCE, START, START)
    )
    for order in PERMUTATIONS:
        frame = schema.parse_source_csv(
            csv_text([rows[i] for i in order]), schema.NRT_SOURCE, START, START
        )
        version, count = fr.build_version_bytes(
            paths.baseline_csv.read_bytes(), frame, START - timedelta(days=1), START
        )
        outputs.append(version)
        assert count == len(rows)
        actual = schema.validate_operational(version).iloc[1:]
        assert records(actual) == records(expected)
    assert len(set(outputs)) == 1
    assert len({hashlib.sha256(data).hexdigest() for data in outputs}) == 1


def test_nm02_response_permutations_publish_identical_content_without_row_loss(
    tmp_path,
):
    rows, versions, identities, contents, counts = tied_rows(), [], [], [], []
    for number, order in enumerate(PERMUTATIONS):
        paths = new_paths(tmp_path / str(number))
        outcome = publish_nrt(paths, [rows[i] for i in order])
        pointer = outcome.pointer
        source = resolve_firms_source(
            reproducibility=False,
            pointer_path=paths.pointer,
            versions_dir=paths.versions_dir,
            baseline_csv=paths.baseline_csv,
        )
        versions.append(source.path.read_bytes())
        contents.append(pd.read_csv(source.path, dtype=str).to_csv(index=False))
        counts.append(outcome.new_rows)
        # Raw bytes/per-run paths legitimately differ: verify, never erase their provenance.
        raw = pointer["raw_artifacts"][0]
        assert (
            hashlib.sha256(Path(raw["path"]).read_bytes()).hexdigest() == raw["sha256"]
        )
        assert "type" not in pd.read_csv(raw["path"], dtype=str).columns
        identities.append(
            {
                k: v
                for k, v in pointer.items()
                if k not in {"raw_files", "raw_artifacts"}
            }
        )
        assert validate_publication(paths)["result"] == "FIRMS ACCEPTED"
    assert len(set(versions)) == 1
    assert len({hashlib.sha256(data).hexdigest() for data in versions}) == 1
    assert len(set(contents)) == 1
    assert all(identity == identities[0] for identity in identities)
    assert counts == [len(rows)] * len(PERMUTATIONS)
    actual = schema.validate_operational(versions[0]).iloc[1:]
    expected = schema.project_frame(
        schema.parse_source_csv(csv_text(rows), schema.NRT_SOURCE, START, START)
    )
    assert records(actual) == records(expected)


def test_nm02_complete_manifest_identical_when_raw_path_bytes_and_clock_are_frozen(
    tmp_path,
):
    paths = new_paths(tmp_path / "store")
    pointers, sidecars, versions = [], [], []
    for order in PERMUTATIONS:
        outcome = publish_nrt(paths, tied_rows(), frame_order=order)
        pointers.append(paths.pointer.read_bytes())
        version = paths.versions_dir / outcome.pointer["relative_path"]
        versions.append(version.read_bytes())
        sidecars.append(version.with_suffix(".json").read_bytes())
        assert validate_publication(paths)["result"] == "FIRMS ACCEPTED"
        # Only reset the synthetic fixture's pointer, never operational CURRENT.
        paths.pointer.unlink()
    assert len(set(pointers)) == len(set(sidecars)) == len(set(versions)) == 1
    assert json.loads(pointers[0])["new_rows"] == 3


def test_mixed_sp_nrt_same_detection_prefers_sp_and_preserves_raw_classification(tmp_path):
    paths = new_paths(tmp_path / "store")
    standard = row(version="2", type="2")
    near_real_time = row(frp="9.9")
    availability = {
        source: Availability(source, START, START)
        for source in (schema.SP_SOURCE, schema.NRT_SOURCE)
    }
    outcome = fr.refresh(
        paths=paths,
        map_key="offline",
        today=START + timedelta(days=1),
        client_factory=factory_for(
            {
                schema.SP_SOURCE: csv_text([standard]),
                schema.NRT_SOURCE: csv_text([near_real_time]),
            },
            availability,
            [],
        ),
    )
    assert outcome.new_rows == 1
    frame = pd.read_csv(
        paths.versions_dir / outcome.pointer["relative_path"], dtype=str
    ).iloc[1:]
    assert set(frame["firms_source"]) == {schema.SP_SOURCE}
    assert set(frame["frp"]) == {"4.1"}
    for raw in outcome.pointer["raw_artifacts"]:
        source_frame = pd.read_csv(raw["path"], dtype=str)
        if Path(raw["path"]).parent.name == schema.SP_SOURCE:
            assert source_frame["type"].tolist() == ["2"]
        else:
            assert "type" not in source_frame
    assert validate_publication(paths)["result"] == "FIRMS ACCEPTED"


def test_nm02_only_exact_repetitions_are_consolidated_raw_stays_complete(tmp_path):
    paths = new_paths(tmp_path / "store")
    rows = tied_rows()
    outcome = publish_nrt(paths, rows + [rows[0]])
    assert (
        outcome.new_rows == 3
    )  # one exact repetition, all three distinct observations
    raw = Path(outcome.pointer["raw_artifacts"][0]["path"])
    assert raw.read_text(encoding="utf-8") == csv_text(rows + [rows[0]])
    assert len(pd.read_csv(raw)) == 4
    actual = schema.validate_operational(
        (paths.versions_dir / outcome.pointer["relative_path"]).read_bytes()
    ).iloc[1:]
    expected = schema.project_frame(
        schema.parse_source_csv(csv_text(rows), schema.NRT_SOURCE, START, START)
    )
    assert records(actual) == records(expected)
    assert validate_publication(paths)["result"] == "FIRMS ACCEPTED"


def test_cross_product_permutations_have_one_sp_and_identical_resolved_bytes(tmp_path, monkeypatch):
    from src.ingesta.nasa_firms_backfill import DateWindow

    versions, contents, hashes = [], [], []
    sources = (schema.SP_SOURCE, schema.NRT_SOURCE)
    for index, source_order in enumerate((sources, sources[::-1], sources)):
        paths = new_paths(tmp_path / str(index))
        # Same legacy key after rounding and zero-padding, different lexical tokens.
        standard = row(version="2", type="2", latitude="-33.050001", acq_time="945")
        nrt = row()
        unrelated = row(latitude="-33.1")
        nrt_rows = [nrt, unrelated, nrt] if index != 2 else [unrelated, nrt, nrt]
        monkeypatch.setattr(fr, "build_windows", lambda *args, order=source_order: [
            DateWindow(source, START, START) for source in order
        ])
        outcome = fr.refresh(
            paths=paths, map_key="offline", today=START + timedelta(days=1),
            client_factory=factory_for(
                {schema.SP_SOURCE: csv_text([standard, standard]),
                 schema.NRT_SOURCE: csv_text(nrt_rows)},
                {s: Availability(s, START, START) for s in sources}, [],
            ),
        )
        source = resolve_firms_source(reproducibility=False, pointer_path=paths.pointer,
                                      versions_dir=paths.versions_dir, baseline_csv=paths.baseline_csv)
        data = source.path.read_bytes()
        actual = schema.validate_operational(data).iloc[1:]
        shared = actual[pd.to_numeric(actual.latitude).round(5).eq(-33.05)]
        assert len(shared) == 1
        assert shared.firms_source.tolist() == [schema.SP_SOURCE]
        assert outcome.new_rows == 2
        assert validate_publication(paths)["result"] == "FIRMS ACCEPTED"
        versions.append(data)
        hashes.append(outcome.pointer["sha256"])
        contents.append(actual.to_csv(index=False))
    assert len(set(versions)) == len(set(hashes)) == len(set(contents)) == 1


def test_sp_type_distinctions_survive_projection_with_multiplicity(tmp_path):
    from src.ingesta.nasa_firms_backfill import reconcile_source_observations

    paths = new_paths(tmp_path / "store")
    sp = schema.parse_source_csv(csv_text([row(version="2", type="0"),
                                         row(version="2", type="2")]),
                                 schema.SP_SOURCE, START, START)
    nrt = schema.parse_source_csv(csv_text([row()]), schema.NRT_SOURCE, START, START)
    combined = pd.concat([sp, nrt, sp.iloc[[0]]], ignore_index=True)
    retained = reconcile_source_observations(combined)
    assert sorted(retained["type"].tolist()) == ["0", "2"]
    data, added = fr.build_version_bytes(paths.baseline_csv.read_bytes(), combined,
                                        START - timedelta(days=1), START)
    assert added == 2
    assert len(schema.validate_operational(data)) == 3

"""Offline regression for the 2026-09-24 live-schema failure.

Header matches the five preserved live responses. All rows below are SYNTHETIC.
No network or real-store writes; publishing uses only synthetic temporary stores.
"""
import hashlib
import io
import socket
from datetime import date
from pathlib import Path
from unittest.mock import Mock

import pandas as pd
import pytest

from src.ingesta.nasa_firms_backfill import NasaFirmsBackfill, DateWindow, NRT_SOURCE
from src.procesamiento.episodes import assign_episodes, first_arrival_by_cell
from src.procesamiento.raw_parser import parse_nasa_csv
from src.refresh import firms_refresh as fr


HEADER = (Path(__file__).parent / "fixtures/firms_snpp_nrt_20260924_header.csv").read_text().strip()
SYNTHETIC_ROW = "-33.05,-71.4,331.0,0.5,0.4,2026-08-31,1745,N,VIIRS,n,2.0NRT,291.0,4.1,D"
BODY = HEADER + "\n" + SYNTHETIC_ROW + "\n"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def deny(*args, **kwargs):
        raise AssertionError("Network forbidden in schema characterization")
    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket, "create_connection", deny)


def client_for(tmp_path, body):
    client = NasaFirmsBackfill(map_key="synthetic-offline-key", raw_dir=tmp_path)
    response = Mock(text=body, status_code=200, headers={"Content-Type": "text/csv"})
    response.raise_for_status.return_value = None
    client.session.get = Mock(return_value=response)
    return client


def test_observed_header_is_14_columns_without_type():
    assert len(HEADER.split(",")) == 14
    assert "type" not in HEADER.split(",")


def test_download_accepts_nrt_without_inventing_type(tmp_path):
    path, frame = client_for(tmp_path, BODY).download_window(
        DateWindow(NRT_SOURCE, date(2026, 8, 31), date(2026, 8, 31)))
    assert path.read_text() == BODY
    assert "type" not in frame.columns
    assert list(frame.columns) == HEADER.split(",") + ["firms_source", "request_start_date"]
    assert frame["firms_source"].tolist() == [NRT_SOURCE]


@pytest.mark.parametrize("missing", ["latitude", "longitude", "acq_date", "acq_time", "satellite", "instrument"])
def test_required_detection_columns_still_rejected(tmp_path, missing):
    frame = pd.read_csv(io.StringIO(BODY)).drop(columns=missing)
    with pytest.raises(ValueError, match="faltan"):
        client_for(tmp_path, frame.to_csv(index=False)).download_window(
            DateWindow(NRT_SOURCE, date(2026, 8, 31), date(2026, 8, 31)))
    assert not list(tmp_path.rglob("*.csv"))


def test_refresh_publishes_nrt_without_type_and_preserves_baseline(tmp_path):
    # SP supplies type in a historical mixed baseline; never add it to NRT.
    base_header = HEADER + ",type,firms_source,request_start_date"
    base_row = SYNTHETIC_ROW.replace("2026-08-31", "2026-08-30").replace("2.0NRT", "2")
    base = (base_header + "\n" + base_row + ",0,VIIRS_SNPP_SP,2026-08-30\n").encode()
    baseline = tmp_path / "baseline.csv"
    baseline.write_bytes(base)
    paths = fr.FirmsPaths(pointer=tmp_path / "firms/CURRENT.json",
        versions_dir=tmp_path / "firms/versions", baseline_csv=baseline,
        baseline_sha256=hashlib.sha256(base).hexdigest(), raw_dir=tmp_path / "raw")
    def factory(raw_dir):
        client = client_for(raw_dir, BODY)
        from src.ingesta.nasa_firms_backfill import Availability, SP_SOURCE
        client.fetch_availability = lambda: {
            SP_SOURCE: Availability(SP_SOURCE, date(2021, 1, 1), date(2026, 8, 30)),
            NRT_SOURCE: Availability(NRT_SOURCE, date(2026, 8, 31), date(2026, 8, 31)),
        }
        return client
    result = fr.refresh(paths=paths, client_factory=factory, map_key="synthetic-offline-key", today=date(2026, 9, 1))
    assert result.status == "published"
    assert baseline.read_bytes() == base
    assert paths.pointer.exists() and paths.history.exists()
    assert not paths.lock.exists()
    published = pd.read_csv(paths.versions_dir / result.pointer["relative_path"])
    assert "type" not in published.columns and len(published) == 2
    assert len(list(paths.raw_dir.rglob("*.csv"))) == 1
    from scripts.validate_firms import main
    assert main(paths) == 0



def test_parser_and_arrivals_do_not_require_type(tmp_path):
    path = tmp_path / "nrt.csv"
    path.write_text(BODY)
    parsed = parse_nasa_csv(path)
    assert len(parsed) == 1 and "type" not in parsed.columns
    plain = pd.read_csv(io.StringIO(BODY))
    # Synthetic SP classification is used ONLY to demonstrate unused-field invariance.
    classified = plain.assign(type=2, firms_source="VIIRS_SNPP_SP", version="2")
    pd.testing.assert_frame_equal(first_arrival_by_cell(assign_episodes(plain)),
                                  first_arrival_by_cell(assign_episodes(classified)))

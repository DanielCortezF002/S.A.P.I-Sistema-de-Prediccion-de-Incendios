"""Pruebas del cliente NasaFirmsBackfill, ventanas y CLI (cobertura SAPI-45)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
import requests

from scripts.backfill_nasa_firms import main as backfill_main
from src.ingesta.nasa_firms_backfill import (
    NRT_SOURCE,
    SP_SOURCE,
    Availability,
    DateWindow,
    NasaFirmsBackfill,
    _REQUIRED_COLUMNS,
    build_windows,
    deduplicate_detections,
    five_year_start,
    select_boundary_sample,
    split_windows,
)

_SAMPLE_CSV = (
    "latitude,longitude,acq_date,acq_time,satellite,instrument\n"
    "-33.10000,-71.20000,2026-06-03,945,N,VIIRS\n"
)
_AVAILABILITY_CSV = (
    "data_id,min_date,max_date\n"
    f"{SP_SOURCE},2012-01-20,2026-06-05\n"
    f"{NRT_SOURCE},2026-06-01,2026-08-30\n"
)


def test_five_year_start_on_leap_day_boundary() -> None:
    assert five_year_start(date(2024, 2, 29)) == date(2019, 2, 28)


def test_split_windows_empty_when_range_inverted() -> None:
    assert split_windows(SP_SOURCE, date(2026, 6, 10), date(2026, 6, 1)) == []


def test_select_boundary_sample_near_sp_nrt_transition() -> None:
    availability = {
        SP_SOURCE: Availability(SP_SOURCE, date(2012, 1, 20), date(2026, 6, 5)),
        NRT_SOURCE: Availability(NRT_SOURCE, date(2026, 6, 1), date(2026, 8, 30)),
    }
    windows = build_windows(date(2026, 5, 28), date(2026, 6, 12), availability)
    sample = select_boundary_sample(windows, limit=4)

    assert len(sample) == 4
    sources = {window.source for window in sample}
    assert SP_SOURCE in sources
    assert NRT_SOURCE in sources


def test_select_boundary_sample_rejects_zero_limit() -> None:
    with pytest.raises(ValueError, match="limit debe ser mayor que cero"):
        select_boundary_sample([], limit=0)


def test_select_boundary_sample_fills_remaining_slots_from_all_windows() -> None:
    windows = [
        DateWindow(SP_SOURCE, date(2026, 1, 1), date(2026, 1, 7)),
        DateWindow(SP_SOURCE, date(2026, 1, 8), date(2026, 1, 14)),
        DateWindow(SP_SOURCE, date(2026, 1, 15), date(2026, 1, 21)),
        DateWindow(SP_SOURCE, date(2026, 1, 22), date(2026, 1, 28)),
    ]
    sample = select_boundary_sample(windows, limit=4)
    assert len(sample) == 4
    assert all(window.source == SP_SOURCE for window in sample)


def test_deduplicate_empty_returns_copy_without_removal() -> None:
    empty = pd.DataFrame(columns=list(_REQUIRED_COLUMNS | {"firms_source"}))
    result, removed = deduplicate_detections(empty)
    assert result.empty
    assert removed == 0


def test_deduplicate_missing_required_columns_raises() -> None:
    bad = pd.DataFrame({"latitude": [-33.1]})
    with pytest.raises(ValueError, match="columnas requeridas"):
        deduplicate_detections(bad)


def test_client_init_requires_map_key() -> None:
    with pytest.raises(ValueError, match="NASA_FIRMS_API_KEY"):
        NasaFirmsBackfill(map_key="")


def test_client_init_rejects_negative_delay() -> None:
    with pytest.raises(ValueError, match="request_delay_seconds"):
        NasaFirmsBackfill(map_key="k", request_delay_seconds=-0.1)


def test_client_area_uses_valparaiso_bbox() -> None:
    client = NasaFirmsBackfill(map_key="test-key")
    assert client.area.count(",") == 3


def test_get_with_retry_recovers_from_429() -> None:
    sleeps: list[float] = []
    rate_limited = MagicMock()
    rate_limited.status_code = 429
    rate_limited.headers = {"Retry-After": "1"}
    ok = MagicMock()
    ok.status_code = 200
    ok.headers = {}
    ok.raise_for_status = MagicMock()

    client = NasaFirmsBackfill(map_key="k", sleep_fn=sleeps.append)
    client.session.get = MagicMock(side_effect=[rate_limited, ok])

    response = client._get_with_retry("https://example.test")
    assert response is ok
    assert sleeps


def test_get_with_retry_raises_after_four_failures() -> None:
    client = NasaFirmsBackfill(map_key="k", sleep_fn=lambda _: None)
    client.session.get = MagicMock(side_effect=requests.ConnectionError("reset"))

    with pytest.raises(RuntimeError, match="4 intentos"):
        client._get_with_retry("https://example.test")


def test_fetch_availability_parses_official_csv() -> None:
    client = NasaFirmsBackfill(map_key="k", sleep_fn=lambda _: None)
    response = MagicMock()
    response.status_code = 200
    response.headers = {}
    response.text = _AVAILABILITY_CSV
    response.raise_for_status = MagicMock()
    client.session.get = MagicMock(return_value=response)

    availability = client.fetch_availability()

    assert availability[SP_SOURCE].max_date == date(2026, 6, 5)
    assert availability[NRT_SOURCE].min_date == date(2026, 6, 1)


def test_fetch_availability_raises_when_source_missing() -> None:
    client = NasaFirmsBackfill(map_key="k", sleep_fn=lambda _: None)
    response = MagicMock()
    response.status_code = 200
    response.headers = {}
    response.text = "data_id,min_date,max_date\nVIIRS_SNPP_SP,2012-01-20,2026-06-05\n"
    response.raise_for_status = MagicMock()
    client.session.get = MagicMock(return_value=response)

    with pytest.raises(ValueError, match="incompleta"):
        client.fetch_availability()


def test_window_url_rejects_more_than_five_days() -> None:
    client = NasaFirmsBackfill(map_key="k")
    window = DateWindow(SP_SOURCE, date(2021, 8, 30), date(2021, 9, 10))
    with pytest.raises(ValueError, match="DAY_RANGE"):
        client.window_url(window)


def test_download_window_persists_raw_csv_and_tags_metadata(tmp_path: Path) -> None:
    client = NasaFirmsBackfill(
        map_key="k",
        raw_dir=tmp_path / "raw",
        processed_dir=tmp_path / "processed",
        sleep_fn=lambda _: None,
    )
    response = MagicMock()
    response.status_code = 200
    response.headers = {}
    response.text = _SAMPLE_CSV
    response.raise_for_status = MagicMock()
    client.session.get = MagicMock(return_value=response)

    window = DateWindow(SP_SOURCE, date(2026, 6, 1), date(2026, 6, 3))
    raw_path, frame = client.download_window(window)

    assert raw_path.exists()
    assert frame.iloc[0]["firms_source"] == SP_SOURCE
    assert frame.iloc[0]["request_start_date"] == "2026-06-01"


def test_download_window_raises_when_csv_missing_columns(tmp_path: Path) -> None:
    client = NasaFirmsBackfill(map_key="k", raw_dir=tmp_path, sleep_fn=lambda _: None)
    response = MagicMock()
    response.status_code = 200
    response.headers = {}
    response.text = "latitude,longitude\n-33,-71\n"
    response.raise_for_status = MagicMock()
    client.session.get = MagicMock(return_value=response)

    with pytest.raises(ValueError, match="Respuesta FIRMS inválida"):
        client.download_window(DateWindow(SP_SOURCE, date(2026, 6, 1), date(2026, 6, 1)))


def test_run_consolidates_windows_and_writes_manifest(tmp_path: Path) -> None:
    client = NasaFirmsBackfill(
        map_key="k",
        raw_dir=tmp_path / "raw",
        processed_dir=tmp_path / "processed",
        request_delay_seconds=0.0,
        sleep_fn=lambda _: None,
    )
    duplicate_nrt = _SAMPLE_CSV
    duplicate_sp = _SAMPLE_CSV.replace("VIIRS\n", "VIIRS\n")  # misma fila, otra fuente

    def _fake_get(url: str, timeout: int = 60) -> MagicMock:
        response = MagicMock()
        response.status_code = 200
        response.headers = {}
        response.text = duplicate_sp if SP_SOURCE in url else duplicate_nrt
        response.raise_for_status = MagicMock()
        return response

    client.session.get = MagicMock(side_effect=_fake_get)
    windows = [
        DateWindow(SP_SOURCE, date(2026, 6, 1), date(2026, 6, 1)),
        DateWindow(NRT_SOURCE, date(2026, 6, 2), date(2026, 6, 2)),
    ]

    result = client.run(windows)

    assert result.requested_windows == 2
    assert result.raw_records == 2
    assert result.unique_records == 1
    assert result.duplicates_removed == 1
    assert result.consolidated_path.exists()
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["unique_records"] == 1
    assert len(manifest["sha256"]) == 64


def test_run_sleeps_between_windows_when_delay_configured(tmp_path: Path) -> None:
    sleeps: list[float] = []
    client = NasaFirmsBackfill(
        map_key="k",
        raw_dir=tmp_path / "raw",
        processed_dir=tmp_path / "processed",
        request_delay_seconds=2.0,
        sleep_fn=sleeps.append,
    )
    response = MagicMock()
    response.status_code = 200
    response.headers = {}
    response.text = _SAMPLE_CSV
    response.raise_for_status = MagicMock()
    client.session.get = MagicMock(return_value=response)

    windows = [
        DateWindow(SP_SOURCE, date(2026, 6, 1), date(2026, 6, 1)),
        DateWindow(NRT_SOURCE, date(2026, 6, 2), date(2026, 6, 2)),
    ]
    client.run(windows)

    assert sleeps == [2.0]


def test_run_raises_on_empty_window_list(tmp_path: Path) -> None:
    client = NasaFirmsBackfill(map_key="k", raw_dir=tmp_path, processed_dir=tmp_path)
    with pytest.raises(ValueError, match="No hay ventanas"):
        client.run([])


def test_cli_sample_boundary_windows_executes_mocked_backfill(tmp_path: Path) -> None:
    fake_result = MagicMock()
    fake_result.requested_windows = 2
    fake_result.raw_records = 2
    fake_result.unique_records = 2
    fake_result.duplicates_removed = 0
    fake_result.consolidated_path = tmp_path / "out.csv"
    fake_result.manifest_path = tmp_path / "out_manifest.json"

    fake_client = MagicMock()
    fake_client.fetch_availability.return_value = {
        SP_SOURCE: Availability(SP_SOURCE, date(2012, 1, 20), date(2026, 6, 5)),
        NRT_SOURCE: Availability(NRT_SOURCE, date(2026, 6, 1), date(2026, 8, 30)),
    }
    fake_client.run.return_value = fake_result

    argv = [
        "backfill_nasa_firms.py",
        "--start-date",
        "2026-05-30",
        "--end-date",
        "2026-06-10",
        "--sample-boundary-windows",
        "2",
    ]
    with patch("sys.argv", argv):
        with patch("scripts.backfill_nasa_firms.NasaFirmsBackfill", return_value=fake_client):
            assert backfill_main() == 0

    fake_client.run.assert_called_once()
    selected = fake_client.run.call_args[0][0]
    assert len(selected) == 2


def test_cli_rejects_end_date_before_start() -> None:
    argv = [
        "backfill_nasa_firms.py",
        "--start-date",
        "2026-06-10",
        "--end-date",
        "2026-06-01",
        "--confirm-full-run",
    ]
    with patch("sys.argv", argv):
        with pytest.raises(SystemExit, match="end-date"):
            backfill_main()

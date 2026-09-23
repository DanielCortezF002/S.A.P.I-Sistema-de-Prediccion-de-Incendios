"""Guard de escritura sobre la línea base FIRMS congelada (SAPI-71).

Ningún writer FIRMS (`NasaFirmsBackfill`, `ParallelIngester`) puede
sobrescribir `data/processed/nasa_firms_2021-08-30_2026-08-30.csv`, su
manifest ni el snapshot del Hito 1. Todo el módulo corre sin red: un
fixture autouse hace fallar cualquier conexión de socket, y otro verifica
que el sha256 de los archivos congelados reales no cambie en ningún test.
Los casos de symlink/hardlink usan una copia en `tmp_path`, nunca el
baseline real, para que un guard roto no pueda dañarlo.
"""

from __future__ import annotations

import hashlib
import os
import socket
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import src.procesamiento.firms_source as firms_source
from src.ingesta.nasa_firms_backfill import SP_SOURCE, DateWindow, NasaFirmsBackfill
from src.ingesta.parallel_ingester import ParallelIngester
from src.procesamiento.firms_source import (
    FIRMS_BASELINE_CSV,
    FIRMS_REPRODUCIBILITY_CSV,
    FROZEN_FIRMS_PATHS,
    FrozenFirmsWriteError,
    ensure_writable_firms_path,
    is_frozen_firms_path,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
# Derivada de FIRMS_BASELINE_CSV: la ruta literal vive solo en firms_source.py
# (test_no_hardcoded_firms_baseline_path_outside_firms_source).
BASELINE_RELATIVE = FIRMS_BASELINE_CSV.relative_to(REPO_ROOT).as_posix()
BASELINE_WINDOWS = [
    DateWindow(SP_SOURCE, date(2021, 8, 30), date(2021, 9, 3)),
    DateWindow(SP_SOURCE, date(2026, 8, 26), date(2026, 8, 30)),
]
_SAMPLE_CSV = (
    "latitude,longitude,acq_date,acq_time,satellite,instrument\n"
    "-33.10000,-71.20000,2026-06-03,945,N,VIIRS\n"
)


def _sha256(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    def _refuse(*_args, **_kwargs):
        raise AssertionError("llamada de red real en un test del guard FIRMS")

    monkeypatch.setattr(socket.socket, "connect", _refuse)
    monkeypatch.setattr(socket, "create_connection", _refuse)


@pytest.fixture(autouse=True)
def _frozen_files_unchanged():
    before = {path: _sha256(path) for path in FROZEN_FIRMS_PATHS}
    yield
    after = {path: _sha256(path) for path in FROZEN_FIRMS_PATHS}
    assert after == before


def _client_that_must_not_download(**kwargs) -> NasaFirmsBackfill:
    client = NasaFirmsBackfill(map_key="k", sleep_fn=lambda _: None, **kwargs)
    client.session.get = MagicMock(side_effect=AssertionError("no debe descargar"))
    return client


# --- Rutas del baseline real -------------------------------------------------


@pytest.mark.parametrize(
    "frozen", FROZEN_FIRMS_PATHS, ids=lambda p: f"{p.parent.name}/{p.name}"
)
def test_absolute_frozen_paths_are_rejected(frozen):
    with pytest.raises(FrozenFirmsWriteError, match="congelado"):
        ensure_writable_firms_path(frozen)


@pytest.mark.parametrize(
    "relative",
    [
        BASELINE_RELATIVE,
        "./" + BASELINE_RELATIVE,
        f"data/raw/../processed/./{FIRMS_BASELINE_CSV.name}",
        "tests/../" + BASELINE_RELATIVE,
    ],
)
def test_relative_and_equivalent_paths_to_baseline_are_rejected(monkeypatch, relative):
    monkeypatch.chdir(REPO_ROOT)
    assert is_frozen_firms_path(relative)
    with pytest.raises(FrozenFirmsWriteError):
        ensure_writable_firms_path(relative)


@pytest.mark.skipif(os.name != "nt", reason="rutas case-insensitive solo en Windows")
def test_case_variant_of_baseline_is_rejected_on_windows():
    assert is_frozen_firms_path(str(FIRMS_BASELINE_CSV).upper())


def test_other_outputs_next_to_baseline_are_allowed():
    for allowed in (
        FIRMS_BASELINE_CSV.with_name("nasa_firms_2026-08-31_2026-09-05.csv"),
        FIRMS_BASELINE_CSV.parent / "firms" / "versions" / FIRMS_BASELINE_CSV.name,
        FIRMS_REPRODUCIBILITY_CSV.with_name("otro.csv"),
    ):
        ensure_writable_firms_path(allowed)


# --- NasaFirmsBackfill -------------------------------------------------------


def test_backfill_run_over_real_baseline_is_rejected_before_network(tmp_path):
    """El bug: el período 2021-08-30..2026-08-30 produce exactamente el
    nombre del baseline en DATA_PROCESSED_DIR."""
    client = _client_that_must_not_download(
        raw_dir=tmp_path / "raw", processed_dir=FIRMS_BASELINE_CSV.parent
    )

    with pytest.raises(FrozenFirmsWriteError):
        client.run(BASELINE_WINDOWS)

    client.session.get.assert_not_called()
    assert not (tmp_path / "raw").exists()


def test_backfill_run_with_relative_processed_dir_is_rejected(monkeypatch, tmp_path):
    monkeypatch.chdir(REPO_ROOT)
    client = _client_that_must_not_download(
        raw_dir=tmp_path / "raw",
        processed_dir=Path("data") / "raw" / ".." / "processed",
    )

    with pytest.raises(FrozenFirmsWriteError):
        client.run(BASELINE_WINDOWS)

    client.session.get.assert_not_called()


@pytest.fixture
def fake_frozen(monkeypatch, tmp_path) -> Path:
    """Baseline de juguete: permite probar symlink/hardlink sin exponer el real."""
    frozen = tmp_path / "frozen" / "baseline.csv"
    frozen.parent.mkdir()
    frozen.write_text("contenido congelado\n", encoding="utf-8")
    monkeypatch.setattr(firms_source, "FROZEN_FIRMS_PATHS", (frozen,))
    return frozen


def _output_for(processed: Path, window: DateWindow) -> Path:
    stem = f"nasa_firms_{window.start_date.isoformat()}_{window.end_date.isoformat()}"
    return processed / f"{stem}.csv"


@pytest.mark.parametrize("link", ["hardlink", "symlink"])
def test_backfill_output_linked_to_frozen_file_is_rejected(tmp_path, fake_frozen, link):
    window = DateWindow(SP_SOURCE, date(2026, 6, 1), date(2026, 6, 5))
    processed = tmp_path / "processed"
    processed.mkdir()
    output = _output_for(processed, window)
    try:
        (os.link if link == "hardlink" else os.symlink)(fake_frozen, output)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"{link} no disponible en este sistema: {exc}")
    before = fake_frozen.read_bytes()
    client = _client_that_must_not_download(
        raw_dir=tmp_path / "raw", processed_dir=processed
    )

    with pytest.raises(FrozenFirmsWriteError):
        client.run([window])

    client.session.get.assert_not_called()
    assert fake_frozen.read_bytes() == before


def test_download_window_to_frozen_raw_path_is_rejected_before_network(
    tmp_path, monkeypatch
):
    window = DateWindow(SP_SOURCE, date(2026, 6, 1), date(2026, 6, 5))
    client = _client_that_must_not_download(raw_dir=tmp_path / "raw")
    raw_path = tmp_path / "raw" / SP_SOURCE / "2026-06-01_2026-06-05.csv"
    monkeypatch.setattr(firms_source, "FROZEN_FIRMS_PATHS", (raw_path,))

    with pytest.raises(FrozenFirmsWriteError):
        client.download_window(window)

    client.session.get.assert_not_called()
    assert not raw_path.exists()


def test_backfill_run_to_allowed_output_still_works(tmp_path):
    client = NasaFirmsBackfill(
        map_key="k",
        raw_dir=tmp_path / "raw",
        processed_dir=tmp_path / "processed",
        request_delay_seconds=0.0,
        sleep_fn=lambda _: None,
    )
    response = MagicMock(status_code=200, headers={}, text=_SAMPLE_CSV)
    client.session.get = MagicMock(return_value=response)
    window = DateWindow(SP_SOURCE, date(2026, 6, 1), date(2026, 6, 5))

    result = client.run([window])

    assert result.consolidated_path == _output_for(tmp_path / "processed", window)
    assert result.consolidated_path.exists()
    assert result.manifest_path.exists()
    assert result.unique_records == 1


# --- ParallelIngester --------------------------------------------------------


def test_parallel_ingester_firms_rejects_frozen_output_before_network(
    monkeypatch, tmp_path
):
    ingester = ParallelIngester(raw_dir=tmp_path)
    monkeypatch.setattr("src.ingesta.parallel_ingester.NASA_FIRMS_API_KEY", "k")
    download = MagicMock(side_effect=AssertionError("no debe descargar"))
    monkeypatch.setattr(ingester, "_download_with_retry", download)
    # Congela exactamente el archivo que este ingester escribiría hoy.
    today = datetime.now(timezone.utc).date().isoformat()
    out_path = tmp_path / f"nasa_firms_{today}.csv"
    monkeypatch.setattr(firms_source, "FROZEN_FIRMS_PATHS", (out_path,))

    with pytest.raises(FrozenFirmsWriteError):
        ingester._ingest_nasa_firms()

    download.assert_not_called()
    assert not out_path.exists()


def test_parallel_ingester_fallback_rejects_frozen_output(monkeypatch, tmp_path):
    ingester = ParallelIngester(raw_dir=tmp_path)
    fallback = MagicMock(side_effect=AssertionError("no debe consultar staging"))
    monkeypatch.setattr(ingester, "_recuperar_payload_fallback", fallback)
    out_path = tmp_path / "nasa_firms_2026-09-23.csv"
    monkeypatch.setattr(firms_source, "FROZEN_FIRMS_PATHS", (out_path,))

    with pytest.raises(FrozenFirmsWriteError):
        ingester._degrade_source(
            "nasa_firms", "staging_incendios", out_path, RuntimeError("x")
        )

    fallback.assert_not_called()
    assert not out_path.exists()

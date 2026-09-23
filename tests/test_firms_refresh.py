"""Refresco FIRMS versionado (src/refresh/firms_refresh.py, SAPI-71 Fase B).

Todo corre sobre una línea base de juguete en `tmp_path` (CRLF, como la
real) y una API FIRMS simulada: ningún test toca red (socket bloqueado) ni
`data/`. Un fixture verifica además que los archivos FIRMS congelados
reales no cambien.
"""

from __future__ import annotations

import hashlib
import io
import json
import socket
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest
import requests

import src.refresh.firms_refresh as fr
from src.ingesta.nasa_firms_backfill import NRT_SOURCE, SP_SOURCE, NasaFirmsBackfill
from src.procesamiento.episodes import assign_episodes, first_arrival_by_cell
from src.procesamiento.firms_source import (
    FIRMS_BASELINE_COVERAGE,
    FIRMS_REPRODUCIBILITY_CSV,
    FROZEN_FIRMS_PATHS,
    POINTER_SCHEMA_VERSION,
    resolve_firms_source,
)
from src.procesamiento.temporal_features import historial_firms_features

MAP_KEY = "clave-secreta-de-prueba-123"
API_COLUMNS = (
    "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,"
    "instrument,confidence,version,bright_ti5,frp,daynight,type"
)
BASE_HEADER = API_COLUMNS + ",firms_source,request_start_date"
BASE_END = FIRMS_BASELINE_COVERAGE[1]  # 2026-08-30
TODAY = BASE_END + timedelta(days=7)  # cobertura objetivo: hasta 2026-09-05


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    def _refuse(*_args, **_kwargs):
        raise AssertionError("llamada de red real en un test de refresco FIRMS")

    monkeypatch.setattr(socket.socket, "connect", _refuse)
    monkeypatch.setattr(socket, "create_connection", _refuse)


@pytest.fixture(autouse=True)
def _frozen_files_unchanged():
    def _hashes():
        return {
            p: _sha(p.read_bytes()) if p.is_file() else None for p in FROZEN_FIRMS_PATHS
        }

    before = _hashes()
    yield
    assert _hashes() == before


@pytest.fixture
def paths(tmp_path) -> fr.FirmsPaths:
    base = (
        BASE_HEADER + "\r\n"
        "-33.1,-71.2,330.1,0.5,0.4,2026-08-29,1850,N,VIIRS,n,2,290.1,3.2,D,0,"
        "VIIRS_SNPP_NRT,2026-08-26\r\n"
    ).encode("utf-8")
    baseline = tmp_path / "baseline.csv"
    baseline.write_bytes(base)
    return fr.FirmsPaths(
        pointer=tmp_path / "firms" / "CURRENT.json",
        versions_dir=tmp_path / "firms" / "versions",
        baseline_csv=baseline,
        baseline_sha256=_sha(base),
        raw_dir=tmp_path / "raw",
    )


def _row(day: date, lat: float = -33.05, time: int = 1745) -> str:
    return f"{lat},-71.4,331.0,0.5,0.4,{day.isoformat()},{time},N,VIIRS,n,2.0NRT,291.0,4.1,D,0"


class FakeFirms:
    """API FIRMS simulada: disponibilidad + una detección por día pedido."""

    def __init__(self, rows_per_day: int = 1, body=None, fail: Exception | None = None):
        self.rows_per_day = rows_per_day
        self.body = body  # callable(start, day_range) -> str, reemplaza al default
        self.fail = fail
        self.calls: list[str] = []

    def get(self, url: str, timeout: int = 60):
        self.calls.append(url)
        if self.fail is not None:
            raise self.fail
        response = MagicMock(status_code=200, headers={})
        response.raise_for_status = MagicMock()
        if "data_availability" in url:
            response.text = (
                "data_id,min_date,max_date\n"
                f"{SP_SOURCE},2012-01-20,2026-06-05\n"
                f"{NRT_SOURCE},2026-06-01,2026-09-22\n"
            )
            return response
        day_range, start = url.rstrip("/").split("/")[-2:]
        start_day = date.fromisoformat(start)
        if self.body is not None:
            response.text = self.body(start_day, int(day_range))
            return response
        lines = [API_COLUMNS]
        for offset in range(int(day_range)):
            for n in range(self.rows_per_day):
                lines.append(
                    _row(start_day + timedelta(days=offset), lat=-33.05 - n * 0.1)
                )
        response.text = "\n".join(lines) + "\n"
        return response


def _refresh(paths, fake: FakeFirms, today: date = TODAY, **kwargs):
    def factory(raw_dir: Path) -> NasaFirmsBackfill:
        client = NasaFirmsBackfill(
            map_key=MAP_KEY,
            raw_dir=raw_dir,
            request_delay_seconds=0,
            sleep_fn=lambda _: None,
        )
        client.session.get = fake.get
        return client

    return fr.refresh(
        paths=paths, client_factory=factory, map_key=MAP_KEY, today=today, **kwargs
    )


def _pointer(paths) -> dict:
    return json.loads(paths.pointer.read_text(encoding="utf-8"))


# --- Publicación -------------------------------------------------------------


def test_first_refresh_extends_baseline_and_publishes_pointer(paths):
    base = paths.baseline_csv.read_bytes()

    outcome = _refresh(paths, FakeFirms())

    assert outcome.status == "published"
    assert outcome.coverage_end == TODAY - timedelta(days=1)
    assert outcome.new_rows == 6  # 2026-08-31 .. 2026-09-05
    pointer = _pointer(paths)
    required = {
        "schema_version",
        "relative_path",
        "sha256",
        "coverage_start",
        "coverage_end",
        "created_at",
    }
    assert required <= set(pointer)
    assert pointer["schema_version"] == POINTER_SCHEMA_VERSION
    assert pointer["base_sha256"] == _sha(base)
    assert pointer["base_origin"] == "baseline"
    version = paths.versions_dir / pointer["relative_path"]
    data = version.read_bytes()
    assert data.startswith(base)  # la base queda byte a byte intacta
    assert b"\n" not in data.replace(b"\r\n", b"")  # mismo fin de línea que la base
    assert _sha(data) == pointer["sha256"]
    assert pointer["row_count"] == len(pd.read_csv(io.BytesIO(data))) == 7
    # El lector de inferencia acepta el puntero publicado.
    source = resolve_firms_source(
        reproducibility=False,
        pointer_path=paths.pointer,
        versions_dir=paths.versions_dir,
    )
    assert source.origin == "current"
    assert source.coverage_end == date(2026, 9, 5)
    assert (paths.versions_dir / f"{version.stem}.json").is_file()
    history = paths.history.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["event"] for line in history] == ["publish"]
    assert pointer["raw_files"] and all(Path(f).is_file() for f in pointer["raw_files"])
    assert not paths.lock.exists()


def test_refresh_is_idempotent_and_skips_network_when_up_to_date(paths):
    _refresh(paths, FakeFirms())
    pointer_bytes = paths.pointer.read_bytes()
    versions = sorted(paths.versions_dir.iterdir())
    fake = FakeFirms()

    outcome = _refresh(paths, fake)

    assert outcome.status == "up_to_date"
    assert fake.calls == []
    assert paths.pointer.read_bytes() == pointer_bytes
    assert sorted(paths.versions_dir.iterdir()) == versions


def test_next_refresh_builds_on_current_version(paths):
    _refresh(paths, FakeFirms())
    first = _pointer(paths)
    first_bytes = (paths.versions_dir / first["relative_path"]).read_bytes()

    outcome = _refresh(paths, FakeFirms(), today=TODAY + timedelta(days=2))

    second = _pointer(paths)
    assert outcome.new_rows == 2
    assert second["base_sha256"] == first["sha256"]
    assert second["base_origin"] == "current"
    assert (
        (paths.versions_dir / second["relative_path"])
        .read_bytes()
        .startswith(first_bytes)
    )
    assert (paths.versions_dir / first["relative_path"]).read_bytes() == first_bytes


def test_header_only_response_extends_coverage_without_rows(paths):
    outcome = _refresh(paths, FakeFirms(body=lambda *_: API_COLUMNS + "\n"))

    pointer = _pointer(paths)
    assert outcome.status == "published" and outcome.new_rows == 0
    assert pointer["coverage_end"] == "2026-09-05"
    assert pointer["sha256"] == paths.baseline_sha256


def test_repeated_detections_in_a_response_are_deduplicated(paths):
    def body(start, day_range):
        return (
            "\n".join([API_COLUMNS, _row(start), _row(start)]) + "\n"
        )  # misma, 2 veces

    outcome = _refresh(paths, FakeFirms(body=body))
    assert outcome.new_rows == 2  # una por ventana (2026-08-31..09-04, 2026-09-05)
    rows = pd.read_csv(paths.versions_dir / _pointer(paths)["relative_path"])
    keys = rows[["latitude", "longitude", "acq_date", "acq_time"]]
    assert not keys.duplicated().any()


# --- Fallos: nunca se publica nada ------------------------------------------


def _assert_nothing_published(paths):
    assert not paths.pointer.exists()
    assert (
        not list(paths.versions_dir.glob("*.csv"))
        if paths.versions_dir.exists()
        else True
    )
    assert not paths.lock.exists()


@pytest.mark.parametrize(
    "body",
    [
        lambda *_: "",
        lambda *_: "<html>Service Unavailable</html>\n",
        lambda *_: "Invalid MAP_KEY.\n",
    ],
    ids=["cuerpo_vacio", "html", "map_key_invalida"],
)
def test_invalid_response_is_data_error_and_publishes_nothing(paths, body):
    with pytest.raises(fr.FirmsRefreshError) as err:
        _refresh(paths, FakeFirms(body=body))
    assert err.value.exit_code == fr.EXIT_DATA
    _assert_nothing_published(paths)


def test_rows_for_already_published_days_are_rejected(paths):
    def body(start, day_range):
        return f"{API_COLUMNS}\n{_row(BASE_END)}\n"

    with pytest.raises(fr.FirmsRefreshError, match="ya publicados") as err:
        _refresh(paths, FakeFirms(body=body))
    assert err.value.exit_code == fr.EXIT_DATA
    _assert_nothing_published(paths)


def test_network_failure_keeps_current_and_redacts_key(paths):
    _refresh(paths, FakeFirms())
    pointer_bytes = paths.pointer.read_bytes()
    failure = requests.ConnectionError(f"https://firms/api/area/csv/{MAP_KEY}/x")

    with pytest.raises(fr.FirmsRefreshError) as err:
        _refresh(paths, FakeFirms(fail=failure), today=TODAY + timedelta(days=3))

    assert err.value.exit_code == fr.EXIT_NETWORK
    assert MAP_KEY not in str(err.value)
    assert paths.pointer.read_bytes() == pointer_bytes
    assert not paths.lock.exists()


def test_missing_credentials_fail_before_lock_and_network(paths):
    factory = MagicMock()
    with pytest.raises(fr.FirmsRefreshError) as err:
        fr.refresh(paths=paths, client_factory=factory, map_key="", today=TODAY)
    assert err.value.exit_code == fr.EXIT_CONFIG
    factory.assert_not_called()
    assert not paths.lock.exists() and not paths.pointer.exists()


def test_concurrent_refresh_is_rejected(paths):
    paths.lock.parent.mkdir(parents=True)
    paths.lock.write_text(
        json.dumps(
            {
                "pid": 1,
                "host": "otro",
                "started_at": datetime.now(timezone.utc).isoformat(),
            }
        ),
        encoding="utf-8",
    )
    fake = FakeFirms()
    with pytest.raises(fr.FirmsRefreshError) as err:
        _refresh(paths, fake)
    assert err.value.exit_code == fr.EXIT_LOCKED
    assert fake.calls == []
    assert paths.lock.exists()  # el lock ajeno no se toca


def test_tampered_baseline_is_never_extended(paths):
    paths.baseline_csv.write_bytes(paths.baseline_csv.read_bytes() + b"x\r\n")
    with pytest.raises(fr.FirmsRefreshError, match="sha256") as err:
        _refresh(paths, FakeFirms())
    assert err.value.exit_code == fr.EXIT_DATA
    _assert_nothing_published(paths)


def test_existing_version_with_other_content_is_not_overwritten(paths, monkeypatch):
    monkeypatch.setattr(fr, "_version_name", lambda *_: "fija.csv")
    paths.versions_dir.mkdir(parents=True)
    (paths.versions_dir / "fija.csv").write_bytes(b"otro contenido\n")

    with pytest.raises(fr.FirmsRefreshError, match="inmutables") as err:
        _refresh(paths, FakeFirms())

    assert err.value.exit_code == fr.EXIT_DATA
    assert (paths.versions_dir / "fija.csv").read_bytes() == b"otro contenido\n"
    assert not paths.pointer.exists()


def test_crash_before_pointer_publish_keeps_previous_current(paths, monkeypatch):
    _refresh(paths, FakeFirms())
    pointer_bytes = paths.pointer.read_bytes()

    def _boom(*_args, **_kwargs):
        raise OSError("disco lleno")

    monkeypatch.setattr(fr, "_publish", _boom)
    with pytest.raises(OSError):
        _refresh(paths, FakeFirms(), today=TODAY + timedelta(days=2))

    assert paths.pointer.read_bytes() == pointer_bytes
    assert not paths.lock.exists()


# --- Rollback, cleanup, status, CLI ------------------------------------------


def test_rollback_to_previous_version_and_to_baseline(paths):
    _refresh(paths, FakeFirms())
    first = _pointer(paths)
    _refresh(paths, FakeFirms(), today=TODAY + timedelta(days=2))

    fr.rollback(first["relative_path"], paths=paths)
    assert _pointer(paths)["sha256"] == first["sha256"]

    fr.rollback("baseline", paths=paths)
    assert not paths.pointer.exists()
    events = [
        json.loads(x)["event"] for x in paths.history.read_text("utf-8").splitlines()
    ]
    assert events == ["publish", "publish", "rollback", "rollback"]


@pytest.mark.parametrize(
    "target,code",
    [("../fuera.csv", fr.EXIT_USAGE), ("no_existe.csv", fr.EXIT_USAGE)],
)
def test_rollback_rejects_invalid_targets(paths, target, code):
    with pytest.raises(fr.FirmsRefreshError) as err:
        fr.rollback(target, paths=paths)
    assert err.value.exit_code == code


def test_rollback_rejects_tampered_version(paths):
    _refresh(paths, FakeFirms())
    first = _pointer(paths)
    _refresh(paths, FakeFirms(), today=TODAY + timedelta(days=2))
    current = paths.pointer.read_bytes()
    (paths.versions_dir / first["relative_path"]).write_bytes(b"alterado\n")

    with pytest.raises(fr.FirmsRefreshError, match="sha256") as err:
        fr.rollback(first["relative_path"], paths=paths)

    assert err.value.exit_code == fr.EXIT_DATA
    assert paths.pointer.read_bytes() == current


def test_cleanup_never_deletes_current_or_its_base(paths):
    for day in range(5):
        _refresh(paths, FakeFirms(), today=TODAY + timedelta(days=day))
    names = [
        json.loads(p.read_text("utf-8"))["relative_path"]
        for p in sorted(paths.versions_dir.glob("*.json"))
    ]
    current = _pointer(paths)
    later = datetime.now(timezone.utc) + timedelta(days=3)

    dry = fr.cleanup(paths=paths, keep=0, now=later)
    assert dry["applied"] is False
    assert len(list(paths.versions_dir.glob("*.csv"))) == 5  # dry-run no borra

    result = fr.cleanup(paths=paths, keep=0, apply=True, now=later)

    remaining = {p.name for p in paths.versions_dir.glob("*.csv")}
    base = next(
        json.loads(p.read_text("utf-8"))["relative_path"]
        for p in paths.versions_dir.glob("*.json")
        if json.loads(p.read_text("utf-8"))["sha256"] == current["base_sha256"]
    )
    assert current["relative_path"] in remaining and base in remaining
    assert set(result["deleted"]) == set(names) - {current["relative_path"], base}
    assert (
        resolve_firms_source(
            reproducibility=False,
            pointer_path=paths.pointer,
            versions_dir=paths.versions_dir,
        ).origin
        == "current"
    )


def test_cleanup_respects_grace_period(paths):
    for day in range(3):
        _refresh(paths, FakeFirms(), today=TODAY + timedelta(days=day))
    result = fr.cleanup(paths=paths, keep=0, apply=True)  # reemplazadas hace segundos
    assert result["deleted"] == []


def test_status_reports_origin_and_lag(paths):
    assert fr.status(paths=paths, today=TODAY)["origin"] == "baseline"
    _refresh(paths, FakeFirms())
    info = fr.status(paths=paths, today=TODAY)
    assert info["origin"] == "current"
    assert info["days_behind_today"] == 1


def test_cli_without_credentials_exits_78_without_traceback(monkeypatch, capsys):
    monkeypatch.setattr(fr, "NASA_FIRMS_API_KEY", "")
    assert fr.main(["refresh"]) == fr.EXIT_CONFIG
    assert "NASA_FIRMS_API_KEY" in capsys.readouterr().err


# --- Estabilidad científica del prefijo --------------------------------------


def test_appending_later_days_leaves_features_before_coverage_end_identical(tmp_path):
    """Con la línea base real (snapshot versionado del Hito 1): agregar
    detecciones posteriores a coverage_end no cambia ningún arribo previo,
    así que las features FIRMS de cualquier T <= coverage_end son idénticas."""
    base = FIRMS_REPRODUCIBILITY_CSV.read_bytes()
    lines = [_row(BASE_END + timedelta(days=d), lat=-33.05) for d in (1, 1, 2)]
    new_rows = pd.read_csv(io.StringIO(API_COLUMNS + "\n" + "\n".join(lines) + "\n"))
    new_rows["firms_source"] = NRT_SOURCE
    new_rows["request_start_date"] = "2026-08-31"
    data, added = fr.build_version_bytes(
        base, new_rows, BASE_END, BASE_END + timedelta(days=5)
    )
    assert added == 3 and data.startswith(base)

    def _arrivals(raw: bytes) -> dict:
        arrivals = first_arrival_by_cell(assign_episodes(pd.read_csv(io.BytesIO(raw))))
        return {cell: g["first_arrival"] for cell, g in arrivals.groupby("cell_id")}

    before, after = _arrivals(base), _arrivals(data)
    empty = pd.Series([], dtype="datetime64[ns, UTC]")
    for t in (pd.Timestamp("2026-08-30T18:00Z"), pd.Timestamp("2025-02-01T00:00Z")):
        for cell in set(before) | set(after):
            assert historial_firms_features(
                cell, t, before.get(cell, empty)
            ) == historial_firms_features(cell, t, after.get(cell, empty))

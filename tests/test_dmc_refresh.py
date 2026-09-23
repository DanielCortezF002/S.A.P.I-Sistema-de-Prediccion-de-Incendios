"""Refresco DMC versionado por mes (src/refresh/dmc_refresh.py, SAPI-71 Fase B).

API DMC simulada con la forma verificada en la llamada real del
23-09-2026 (raíz sin envoltorio, `timezone: "UTC"`, lecturas cada 15 min,
valores como strings con unidad). Ningún test toca red (socket bloqueado)
ni `data/`: todo escribe en `tmp_path`.
"""

from __future__ import annotations

import json
import random
import socket
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests

import src.refresh.atomic as atomic
import src.refresh.dmc_refresh as dmc
from src.config import DATA_RAW_DIR
from src.procesamiento.raw_parser import parse_dmc_json

STATION = dmc.DMC_STATION_ID
CREDS = ("usuario-prueba", "token-secreto-XYZ")
NOW = datetime(2026, 9, 23, 15, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    def _refuse(*_args, **_kwargs):
        raise AssertionError("llamada de red real en un test de refresco DMC")

    monkeypatch.setattr(socket.socket, "connect", _refuse)
    monkeypatch.setattr(socket, "create_connection", _refuse)


@pytest.fixture
def paths(tmp_path) -> dmc.DmcPaths:
    return dmc.DmcPaths(root=tmp_path / "dmc")


def _record(moment: datetime, temp: float = 18.8) -> dict:
    return {
        "momento": moment.strftime(dmc.MOMENTO_FORMAT),
        "temperatura": f"{temp} °C",
        "humedadRelativa": "72 %",
        "fuerzaDelViento": "8.5 kt",
        "direccionDelViento": "230 °",
        "temperatura02Mts": None,
    }


def _records(start: str, end: str, temp: float = 18.8) -> list[dict]:
    cursor, stop, out = datetime.fromisoformat(start), datetime.fromisoformat(end), []
    while cursor <= stop:
        out.append(_record(cursor, temp))
        cursor += timedelta(minutes=15)
    return out


def _payload(records, created="23-09-2026 15:25", tz="UTC", registros=None) -> dict:
    return {
        "organismo": "DMC",
        "pais": "Chile",
        "producto": "Datos Recientes de la estación automática últimas 12 horas",
        "fechaCreacion": created,
        "timezone": tz,
        "registros": len(records) if registros is None else registros,
        "status": "Estación con datos disponibles recientemente",
        "datosEstaciones": {
            "estacion": {"codigoNacional": STATION, "nombreEstacion": "Rodelillo"},
            "datos": records,
        },
    }


class FakeDmc:
    """Responde por mes (`/{año}/{mes}` al final de la URL)."""

    def __init__(self, by_month: dict, status: int = 200, fail=None):
        self.by_month = by_month  # "YYYY-MM" -> payload | callable | Exception
        self.status = status
        self.fail = fail
        self.calls: list[str] = []

    def get(self, url, params=None, timeout=None):
        year, month = url.rstrip("/").split("/")[-2:]
        key = f"{year}-{int(month):02d}"
        self.calls.append(key)
        assert params == {"usuario": CREDS[0], "token": CREDS[1]}
        if self.fail is not None:
            raise self.fail
        body = self.by_month[key]
        if isinstance(body, Exception):
            raise body
        response = MagicMock(status_code=self.status)
        if callable(body):
            response.json.side_effect = body
        else:
            response.json.return_value = json.loads(json.dumps(body))
        return response


AUG = _records("2026-08-31T22:00", "2026-08-31T23:45")
SEP = _records("2026-09-01T00:00", "2026-09-01T03:00")


def _run(paths, fake, now=NOW, **kwargs):
    return dmc.refresh(
        paths=paths,
        session=fake,
        credentials=CREDS,
        now=now,
        sleep=lambda _: None,
        **kwargs,
    )


def _pointer(paths) -> dict:
    return json.loads(paths.pointer.read_text(encoding="utf-8"))


def _stored(paths, month) -> list[dict]:
    entry = _pointer(paths)["months"][month]
    document = json.loads(
        (paths.versions_dir / entry["relative_path"]).read_text("utf-8")
    )
    return document[STATION]["datosEstaciones"]["datos"]


def _files(root: Path) -> list[str]:
    return sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())


# --- Publicación, merge, orden, dedupe ---------------------------------------


def test_first_run_fetches_previous_and_current_month(paths):
    fake = FakeDmc({"2026-08": _payload(AUG), "2026-09": _payload(SEP)})

    outcome = _run(paths, fake)

    assert outcome.status == "published"
    assert fake.calls == ["2026-08", "2026-09"]
    pointer = _pointer(paths)
    assert sorted(pointer["months"]) == ["2026-08", "2026-09"]
    assert pointer["coverage_start"] == "2026-08-31 22:00:00"
    assert pointer["coverage_end"] == "2026-09-01 03:00:00"
    assert pointer["record_count"] == len(AUG) + len(SEP) == outcome.new_records
    for month, expected in (("2026-08", AUG), ("2026-09", SEP)):
        version = paths.versions_dir / pointer["months"][month]["relative_path"]
        parsed = parse_dmc_json(version)  # el mismo parser que la inferencia
        assert len(parsed) == len(expected)
        assert set(parsed["codigo_estacion"]) == {STATION}
    assert (paths.pointers_dir / f"{pointer['manifest_sha256'][:12]}.json").is_file()
    assert not paths.lock.exists()


def test_merge_never_loses_previously_downloaded_observations(paths):
    """El mes en curso solo trae lo que la API tenga hoy; lo ya bajado de
    ese mismo mes (y de meses anteriores) se conserva."""
    _run(paths, FakeDmc({"2026-08": _payload(AUG), "2026-09": _payload(SEP)}))
    later = _records("2026-09-01T02:00", "2026-09-01T06:00")  # solapa 02:00-03:00

    outcome = _run(
        paths, FakeDmc({"2026-09": _payload(later)}), now=NOW + timedelta(hours=4)
    )

    stored = [r["momento"] for r in _stored(paths, "2026-09")]
    expected = sorted({r["momento"] for r in SEP + later})
    assert stored == expected
    assert outcome.new_records == len(expected) - len(SEP)
    assert len(_stored(paths, "2026-08")) == len(AUG)  # mes no re-consultado, intacto


def test_records_are_sorted_and_duplicates_collapsed(paths):
    shuffled = SEP[::-1] + SEP[:3]  # orden inverso + 3 repetidos idénticos
    random.Random(7).shuffle(shuffled)
    _run(
        paths,
        FakeDmc(
            {
                "2026-08": _payload(AUG),
                "2026-09": _payload(shuffled, registros=len(shuffled)),
            }
        ),
    )
    moments = [r["momento"] for r in _stored(paths, "2026-09")]
    assert moments == sorted(set(moments)) and len(moments) == len(SEP)


def test_conflicting_value_keeps_published_reading(paths):
    _run(paths, FakeDmc({"2026-08": _payload(AUG), "2026-09": _payload(SEP)}))
    history_lines = paths.history.read_text("utf-8").splitlines()
    changed = [dict(SEP[0], temperatura="99.9 °C")] + SEP[1:]

    outcome = _run(paths, FakeDmc({"2026-09": _payload(changed)}))

    assert outcome.status == "unchanged" and outcome.conflicts == 1
    assert _stored(paths, "2026-09")[0]["temperatura"] == "18.8 °C"
    assert paths.history.read_text("utf-8").splitlines() == history_lines


def test_same_input_twice_is_idempotent_and_byte_identical(paths, tmp_path):
    responses = {"2026-08": _payload(AUG), "2026-09": _payload(SEP)}
    _run(paths, FakeDmc(responses))
    pointer_bytes, files = paths.pointer.read_bytes(), _files(paths.root)
    # Misma data, otro fechaCreacion (campo volátil de la API).
    again = {m: dict(p, fechaCreacion="23-09-2026 18:00") for m, p in responses.items()}

    outcome = _run(paths, FakeDmc(again), now=NOW + timedelta(minutes=30))

    assert outcome.status == "unchanged"
    assert paths.pointer.read_bytes() == pointer_bytes
    assert _files(paths.root) == files
    other = dmc.DmcPaths(root=tmp_path / "otro")
    _run(other, FakeDmc(again))
    assert _pointer(other)["manifest_sha256"] == _pointer(paths)["manifest_sha256"]


def test_month_rollover_fetches_from_last_published_month(paths):
    _run(paths, FakeDmc({"2026-08": _payload(AUG), "2026-09": _payload(SEP)}))
    october = _records("2026-10-01T00:00", "2026-10-01T09:00")
    fake = FakeDmc({"2026-09": _payload(SEP), "2026-10": _payload(october)})

    _run(paths, fake, now=datetime(2026, 10, 1, 9, 30, tzinfo=timezone.utc))

    assert fake.calls == ["2026-09", "2026-10"]
    assert sorted(_pointer(paths)["months"]) == ["2026-08", "2026-09", "2026-10"]


# --- Vacíos, JSON corrupto, formato ------------------------------------------


def _assert_nothing_published(paths):
    assert not paths.pointer.exists()
    assert not paths.lock.exists()


@pytest.mark.parametrize(
    "august",
    [
        _payload([]),
        "Sin Información",
        {"error": "sin datos"},
    ],
    ids=["datos_vacio", "texto_sin_informacion", "objeto_sin_datos"],
)
def test_empty_response_publishes_nothing(paths, august):
    with pytest.raises(dmc.DmcRefreshError) as err:
        _run(paths, FakeDmc({"2026-08": august, "2026-09": _payload(SEP)}))
    assert err.value.exit_code == dmc.EXIT_DATA
    _assert_nothing_published(paths)


def test_empty_current_month_is_tolerated_only_at_month_start(paths):
    fake = FakeDmc(
        {
            "2026-09": _payload(
                AUG[:0] + _records("2026-09-30T20:00", "2026-09-30T23:45")
            ),
            "2026-10": _payload([]),
        }
    )
    outcome = _run(paths, fake, now=datetime(2026, 10, 1, 2, 0, tzinfo=timezone.utc))
    assert outcome.status == "published"
    assert sorted(_pointer(paths)["months"]) == ["2026-09"]

    later = datetime(
        2026, 10, 1, 7, 0, tzinfo=timezone.utc
    )  # fuera de la gracia de 6 h
    with pytest.raises(dmc.DmcRefreshError, match="vacía"):
        _run(
            paths,
            FakeDmc(
                {
                    "2026-09": _payload(_stored(paths, "2026-09")),
                    "2026-10": _payload([]),
                }
            ),
            now=later,
        )


def _bad_json():
    raise json.JSONDecodeError("Expecting value", "<html>", 0)


@pytest.mark.parametrize(
    "september,match",
    [
        (_bad_json, "JSON DMC inválido"),
        (_payload(SEP, tz="America/Santiago"), "timezone"),
        (_payload(SEP, registros=len(SEP) + 5), "incompleta"),
        (_payload(SEP + [_record(datetime(2026, 10, 1))]), "otro mes"),
        (_payload(SEP + [{"temperatura": "1 °C"}]), "momento válido"),
        (_payload(SEP + [{"momento": "01-09-2026 00:00"}]), "momento válido"),
    ],
    ids=[
        "json_corrupto",
        "timezone",
        "registros",
        "otro_mes",
        "sin_momento",
        "formato",
    ],
)
def test_invalid_payload_is_rejected_before_publishing(paths, september, match):
    with pytest.raises(dmc.DmcRefreshError, match=match) as err:
        _run(paths, FakeDmc({"2026-08": _payload(AUG), "2026-09": september}))
    assert err.value.exit_code == dmc.EXIT_DATA
    _assert_nothing_published(paths)


# --- Credenciales, red, lock -------------------------------------------------


@pytest.mark.parametrize("creds", [("", ""), ("u", ""), ("", "t")])
def test_missing_credentials_fail_before_any_write_or_request(paths, creds):
    fake = FakeDmc({})
    with pytest.raises(dmc.DmcRefreshError, match="DMC_USUARIO") as err:
        dmc.refresh(paths=paths, session=fake, credentials=creds, now=NOW)
    assert err.value.exit_code == dmc.EXIT_CONFIG
    assert fake.calls == [] and not paths.root.exists()


def test_network_down_keeps_last_valid_version_and_redacts_token(paths):
    _run(paths, FakeDmc({"2026-08": _payload(AUG), "2026-09": _payload(SEP)}))
    pointer_bytes = paths.pointer.read_bytes()
    boom = requests.ConnectionError(
        f"https://dmc/...?usuario={CREDS[0]}&token={CREDS[1]}"
    )
    sleeps = []

    with pytest.raises(dmc.DmcRefreshError) as err:
        dmc.refresh(
            paths=paths,
            session=FakeDmc({}, fail=boom),
            credentials=CREDS,
            now=NOW + timedelta(hours=1),
            sleep=sleeps.append,
        )

    assert err.value.exit_code == dmc.EXIT_NETWORK
    assert CREDS[1] not in str(err.value) and CREDS[0] not in str(err.value)
    assert sleeps == [1, 2]  # 3 intentos acotados
    assert paths.pointer.read_bytes() == pointer_bytes
    assert not paths.lock.exists()


def test_http_error_is_not_retried_and_publishes_nothing(paths):
    fake = FakeDmc({"2026-08": _payload(AUG), "2026-09": _payload(SEP)}, status=401)
    with pytest.raises(dmc.DmcRefreshError, match="HTTP 401") as err:
        _run(paths, fake)
    assert err.value.exit_code == dmc.EXIT_NETWORK
    assert fake.calls == ["2026-08"]
    _assert_nothing_published(paths)


def test_transient_5xx_is_retried(paths):
    fake = FakeDmc({"2026-08": _payload(AUG), "2026-09": _payload(SEP)})
    statuses = iter([503, 200, 200])
    original = fake.get

    def flaky(url, params=None, timeout=None):
        response = original(url, params, timeout)
        response.status_code = next(statuses)
        return response

    fake.get = flaky
    assert _run(paths, fake).status == "published"


def test_failure_in_a_later_month_keeps_previous_current(paths):
    _run(paths, FakeDmc({"2026-08": _payload(AUG), "2026-09": _payload(SEP)}))
    pointer_bytes = paths.pointer.read_bytes()
    october = _records("2026-10-01T00:00", "2026-10-01T09:00")
    fake = FakeDmc({"2026-09": _payload(SEP), "2026-10": _payload(october, tz="CLT")})

    with pytest.raises(dmc.DmcRefreshError):
        _run(paths, fake, now=datetime(2026, 10, 1, 9, 30, tzinfo=timezone.utc))

    assert paths.pointer.read_bytes() == pointer_bytes


def test_second_concurrent_writer_fails_cleanly(paths):
    """Dos escritores reales: el segundo sale con 75 sin llamar a la API
    mientras el primero tiene el lock; el primero termina bien."""
    inside, release = threading.Event(), threading.Event()
    slow = FakeDmc({"2026-08": _payload(AUG), "2026-09": _payload(SEP)})
    original = slow.get

    def blocking_get(url, params=None, timeout=None):
        inside.set()
        assert release.wait(5)
        return original(url, params, timeout)

    slow.get = blocking_get
    result = {}
    worker = threading.Thread(target=lambda: result.update(o=_run(paths, slow)))
    worker.start()
    try:
        assert inside.wait(5)
        second = FakeDmc({"2026-08": _payload(AUG), "2026-09": _payload(SEP)})
        with pytest.raises(dmc.DmcRefreshError) as err:
            _run(paths, second)
        assert err.value.exit_code == dmc.EXIT_LOCKED
        assert second.calls == []
    finally:
        release.set()
        worker.join(10)
    assert result["o"].status == "published"
    assert not paths.lock.exists()


# --- Atomicidad ----------------------------------------------------------------


def test_crash_before_replace_leaves_previous_version_and_no_temp(paths, monkeypatch):
    _run(paths, FakeDmc({"2026-08": _payload(AUG), "2026-09": _payload(SEP)}))
    pointer_bytes, files = paths.pointer.read_bytes(), _files(paths.root)
    more = _records("2026-09-01T00:00", "2026-09-01T05:00")

    def _boom(*_args, **_kwargs):
        raise OSError("fallo simulado justo antes de publicar")

    monkeypatch.setattr(atomic.os, "replace", _boom)
    with pytest.raises(OSError):
        _run(paths, FakeDmc({"2026-09": _payload(more)}), now=NOW + timedelta(hours=2))

    assert paths.pointer.read_bytes() == pointer_bytes
    assert _files(paths.root) == files  # sin versión nueva ni temporales
    assert not paths.lock.exists()


def test_crash_between_version_and_pointer_keeps_current(paths, monkeypatch):
    _run(paths, FakeDmc({"2026-08": _payload(AUG), "2026-09": _payload(SEP)}))
    pointer_bytes = paths.pointer.read_bytes()
    more = _records("2026-09-01T00:00", "2026-09-01T05:00")
    monkeypatch.setattr(dmc, "_publish", MagicMock(side_effect=OSError("disco lleno")))

    with pytest.raises(OSError):
        _run(paths, FakeDmc({"2026-09": _payload(more)}), now=NOW + timedelta(hours=2))

    assert paths.pointer.read_bytes() == pointer_bytes
    assert (
        dmc.read_current(paths)["manifest_sha256"]
        == json.loads(pointer_bytes)["manifest_sha256"]
    )


def test_tampered_published_version_blocks_refresh(paths):
    _run(paths, FakeDmc({"2026-08": _payload(AUG), "2026-09": _payload(SEP)}))
    entry = _pointer(paths)["months"]["2026-09"]
    (paths.versions_dir / entry["relative_path"]).write_text("{}", encoding="utf-8")
    fake = FakeDmc({"2026-09": _payload(SEP)})

    with pytest.raises(dmc.DmcRefreshError, match="sha256") as err:
        _run(paths, fake)

    assert err.value.exit_code == dmc.EXIT_DATA and fake.calls == []
    assert dmc.status(paths=paths)["origin"] == "invalid_pointer"


# --- Rollback, status, CLI, aislamiento --------------------------------------


def test_rollback_republishes_previous_pointer(paths):
    _run(paths, FakeDmc({"2026-08": _payload(AUG), "2026-09": _payload(SEP)}))
    first = _pointer(paths)["manifest_sha256"]
    more = _records("2026-09-01T00:00", "2026-09-01T05:00")
    _run(paths, FakeDmc({"2026-09": _payload(more)}), now=NOW + timedelta(hours=2))
    assert _pointer(paths)["manifest_sha256"] != first

    dmc.rollback(first[:12], paths=paths)

    assert _pointer(paths)["manifest_sha256"] == first
    events = [
        json.loads(x)["event"] for x in paths.history.read_text("utf-8").splitlines()
    ]
    assert events == ["publish", "publish", "rollback"]


@pytest.mark.parametrize("target", ["../x", "no-hex!", "", "abcdef123456"])
def test_rollback_rejects_invalid_or_unknown_ids(paths, target):
    with pytest.raises(dmc.DmcRefreshError) as err:
        dmc.rollback(target, paths=paths)
    assert err.value.exit_code == dmc.EXIT_USAGE


def test_status_reports_coverage_and_age(paths):
    assert dmc.status(paths=paths)["origin"] == "none"
    _run(paths, FakeDmc({"2026-08": _payload(AUG), "2026-09": _payload(SEP)}))
    info = dmc.status(paths=paths, now=NOW)
    assert info["origin"] == "current" and info["coverage_end"] == "2026-09-01 03:00:00"
    assert info["hours_behind_now"] == 540.0


def test_cli_missing_credentials_exits_78_without_leaking(monkeypatch, capsys):
    monkeypatch.setattr(dmc, "DMC_USUARIO", "")
    monkeypatch.setattr(dmc, "DMC_TOKEN", "")
    assert dmc.main(["refresh"]) == dmc.EXIT_CONFIG
    assert "DMC_USUARIO" in capsys.readouterr().err


def test_refresh_storage_is_invisible_to_the_scoring_loader(paths):
    """Nada de lo refrescado entra todavía al scoring: se guarda fuera de
    data/raw/ y con nombres que no calzan con los globs del loader."""
    default_root = dmc.DmcPaths().root.resolve()
    assert DATA_RAW_DIR.resolve() not in default_root.parents
    _run(paths, FakeDmc({"2026-08": _payload(AUG), "2026-09": _payload(SEP)}))
    names = [p.name for p in paths.root.rglob("*.json")]
    assert not any(n.startswith(("dmc_historico_", "dmc_meteo_")) for n in names)


def test_station_matches_model_d_station():
    from src.inference.prototype_service import STATION_ID

    assert dmc.DMC_STATION_ID == STATION_ID

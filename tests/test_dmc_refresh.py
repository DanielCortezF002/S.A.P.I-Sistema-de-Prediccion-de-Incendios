"""Refresco DMC versionado por mes (src/refresh/dmc_refresh.py, SAPI-71 Fase B).

API DMC simulada con la forma verificada en la llamada real del
23-09-2026 (raíz sin envoltorio, `timezone: "UTC"`, lecturas cada 15 min,
valores como strings con unidad). Ningún test toca red (socket bloqueado)
ni `data/`: todo escribe en `tmp_path`.
"""

from __future__ import annotations

import json
import random
import re
import socket
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock

import pytest
import requests

import src.refresh.atomic as atomic
import src.refresh.dmc_refresh as dmc
from src.config import DATA_RAW_DIR
from src.procesamiento.raw_parser import parse_dmc_json
from src.refresh.lock import refresh_lock

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
        (_payload(SEP, registros="3000"), "no es un entero"),
        (_payload(SEP, registros=3000.0), "no es un entero"),
        (dict(_payload(SEP), datosEstaciones={"datos": "Sin Información"}), "datos"),
        (dict(_payload(SEP), datosEstaciones=[]), "datos"),
    ],
    ids=[
        "json_corrupto",
        "timezone",
        "registros",
        "otro_mes",
        "sin_momento",
        "formato",
        "registros_texto",
        "registros_float",
        "datos_no_lista",
        "datos_estaciones_no_dict",
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


def test_version_name_taken_with_other_bytes_fails_with_65(paths):
    """Guarda de inmutabilidad: si el nombre de la versión ya existe con
    otros bytes (corrupción externa o colisión de sha12), aborta con 65."""
    merged, _, _ = dmc.merge_records([], AUG)
    data = dmc.canonical_month_bytes(
        STATION, {"codigoNacional": STATION, "nombreEstacion": "Rodelillo"}, merged
    )
    name = f"dmc_{STATION}_2026-08_{atomic.sha256_bytes(data)[:12]}.json"
    paths.versions_dir.mkdir(parents=True, exist_ok=True)
    (paths.versions_dir / name).write_bytes(b'{"corrupto": true}\n')
    fake = FakeDmc({"2026-08": _payload(AUG), "2026-09": _payload(SEP)})

    with pytest.raises(dmc.DmcRefreshError, match="inmutables") as err:
        _run(paths, fake)

    assert err.value.exit_code == dmc.EXIT_DATA
    assert fake.calls == ["2026-08"]  # aborta antes de pedir el mes en curso
    _assert_nothing_published(paths)


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


def test_rollback_under_a_held_lock_exits_75_without_republishing(paths):
    """El rollback también es escritor: con el lock tomado sale 75 y deja
    `CURRENT.json` como estaba."""
    _run(paths, FakeDmc({"2026-08": _payload(AUG), "2026-09": _payload(SEP)}))
    first = _pointer(paths)["manifest_sha256"]
    more = _records("2026-09-01T00:00", "2026-09-01T05:00")
    _run(paths, FakeDmc({"2026-09": _payload(more)}), now=NOW + timedelta(hours=2))
    published = paths.pointer.read_bytes()
    assert _pointer(paths)["manifest_sha256"] != first

    with refresh_lock(paths.lock):
        with pytest.raises(dmc.DmcRefreshError) as err:
            dmc.rollback(first[:12], paths=paths)

    assert err.value.exit_code == dmc.EXIT_LOCKED
    assert paths.pointer.read_bytes() == published


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


# --- Hardening pre-refresh: F8 credenciales en errores de red ----------------

# Credenciales con @ + / = %, espacio y un escape ya presente: sus formas
# URL-encoded difieren de la cruda, que es lo que `redact` no veía.
SPECIAL_CREDS = ("sapi+qa@dmc.cl", "tok+en/42= %ab")


def _secret_forms(secret: str) -> set[str]:
    from urllib.parse import quote, quote_plus

    encoded = {quote_plus(secret), quote(secret, safe=""), quote(secret)}
    lowered = {
        re.sub(r"%[0-9A-F]{2}", lambda m: m.group().lower(), form) for form in encoded
    }
    return {secret} | encoded | lowered


class _LeakyNetwork:
    """Sesión que falla como urllib3/requests reales: el texto de la
    excepción trae la URL preparada por `requests`, con las credenciales
    URL-encoded en el querystring. Sin sockets."""

    def __init__(self, exc_type):
        self.exc_type = exc_type
        self.calls = 0

    def get(self, url, params=None, timeout=None):
        self.calls += 1
        prepared = requests.Request("GET", url, params=params).prepare().url
        raise self.exc_type(
            "HTTPSConnectionPool(host='climatologia.meteochile.gob.cl', port=443): "
            f"Max retries exceeded with url: {prepared} (Caused by NewConnectionError)"
        )


def _assert_no_secret(text: str, creds=SPECIAL_CREDS) -> None:
    for secret in creds:
        for form in _secret_forms(secret):
            assert form not in text, f"credencial expuesta como {form!r}"


def test_encoded_credentials_really_differ_from_raw():
    """Precondición del test: si las formas coincidieran, no probaría nada."""
    prepared = str(
        requests.Request(
            "GET",
            "https://x/y",
            params={"usuario": SPECIAL_CREDS[0], "token": SPECIAL_CREDS[1]},
        )
        .prepare()
        .url
    )
    assert SPECIAL_CREDS[0] not in prepared and SPECIAL_CREDS[1] not in prepared
    assert "sapi%2Bqa%40dmc.cl" in prepared and "tok%2Ben%2F42%3D+%25ab" in prepared


@pytest.mark.parametrize(
    "exc_type",
    [requests.ConnectionError, requests.Timeout, requests.exceptions.SSLError],
)
def test_network_error_never_exposes_raw_or_encoded_credentials(
    paths, caplog, exc_type
):
    caplog.set_level("DEBUG")
    session: Any = _LeakyNetwork(exc_type)

    with pytest.raises(dmc.DmcRefreshError) as err:
        dmc.refresh(
            paths=paths,
            session=session,
            credentials=SPECIAL_CREDS,
            now=NOW,
            sleep=lambda _: None,
        )

    message = str(err.value)
    assert err.value.exit_code == dmc.EXIT_NETWORK
    assert session.calls == dmc.MAX_ATTEMPTS
    assert exc_type.__name__ in message  # el tipo útil se conserva
    assert "tras 3 intentos" in message
    _assert_no_secret(message)
    _assert_no_secret(caplog.text)
    assert err.value.__cause__ is None and err.value.__context__ is None
    _assert_nothing_published(paths)


def test_cli_error_payload_never_exposes_credentials(paths, monkeypatch, capsys):
    """Lo que la CLI imprime (el payload JSON de stderr) tampoco las trae."""
    real_refresh = dmc.refresh
    monkeypatch.setattr(dmc, "DMC_USUARIO", SPECIAL_CREDS[0])
    monkeypatch.setattr(dmc, "DMC_TOKEN", SPECIAL_CREDS[1])
    monkeypatch.setattr(
        dmc,
        "refresh",
        lambda **kw: real_refresh(
            paths=paths,
            session=cast(Any, _LeakyNetwork(requests.ConnectionError)),
            credentials=SPECIAL_CREDS,
            now=NOW,
            sleep=lambda _: None,
            **kw,
        ),
    )

    assert dmc.main(["refresh"]) == dmc.EXIT_NETWORK

    out = capsys.readouterr()
    payload = json.loads(out.err)
    assert payload["status"] == "error" and "ConnectionError" in payload["error"]
    _assert_no_secret(out.err)
    _assert_no_secret(out.out)


# --- Hardening pre-refresh: F4a/F4b rollback verificado ------------------------


def _two_pointers(paths) -> str:
    """Publica dos punteros; devuelve el manifest_sha256 del primero (que ya
    no es el vigente). Su versión de 2026-09 solo la referencia él."""
    _run(paths, FakeDmc({"2026-08": _payload(AUG), "2026-09": _payload(SEP)}))
    first = _pointer(paths)["manifest_sha256"]
    more = _records("2026-09-01T00:00", "2026-09-01T05:00")
    _run(paths, FakeDmc({"2026-09": _payload(more)}), now=NOW + timedelta(hours=2))
    assert _pointer(paths)["manifest_sha256"] != first
    return first


def _stored_pointer(paths, manifest: str) -> dict:
    return json.loads(
        (paths.pointers_dir / f"{manifest[:12]}.json").read_text(encoding="utf-8")
    )


def _plant_pointer(paths, pointer, *, rehash: bool = True) -> str:
    """Escribe un puntero en pointers/ y devuelve su id. Con `rehash`, el
    manifest se recalcula para que solo falle lo que el test altera."""
    if rehash:
        pointer = dict(pointer, manifest_sha256=dmc._manifest_sha(pointer["months"]))
    to = pointer["manifest_sha256"][:12]
    (paths.pointers_dir / f"{to}.json").write_text(json.dumps(pointer), "utf-8")
    return to


def _rollback_is_rejected(paths, to: str, match: str) -> None:
    current, history = paths.pointer.read_bytes(), paths.history.read_bytes()
    with pytest.raises(dmc.DmcRefreshError, match=match) as err:
        dmc.rollback(to, paths=paths)
    assert err.value.exit_code == dmc.EXIT_DATA
    assert paths.pointer.read_bytes() == current  # CURRENT intacto
    assert paths.history.read_bytes() == history  # sin línea de rollback
    assert dmc.status(paths=paths)["origin"] == "current"
    assert not paths.lock.exists()


def test_rollback_to_valid_pointer_republishes_it(paths):
    first = _two_pointers(paths)

    pointer = dmc.rollback(first[:12], paths=paths)

    assert pointer["manifest_sha256"] == first
    current = dmc.read_current(paths)
    assert current is not None and current["manifest_sha256"] == first
    last = json.loads(paths.history.read_text("utf-8").splitlines()[-1])
    assert last["event"] == "rollback" and last["manifest_sha256"] == first


def test_rollback_rejects_tampered_manifest(paths):
    """F4a: meses alterados con el manifest_sha256 original."""
    first = _two_pointers(paths)
    tampered = _stored_pointer(paths, first)
    tampered["months"]["2026-08"]["record_count"] += 1
    to = _plant_pointer(paths, tampered, rehash=False)
    assert to == first[:12]

    _rollback_is_rejected(paths, to, "manifest_sha256 no coincide")


@pytest.mark.parametrize(
    "relative_path",
    [
        "../CURRENT.json",
        "..",
        "sub/version.json",
        "..\\CURRENT.json",
        "C:version.json",
        "/etc/passwd",
        "",
        42,
    ],
)
def test_rollback_rejects_paths_outside_versions(paths, relative_path):
    """F4a: el manifest calza, solo la ruta sale de versions/."""
    first = _two_pointers(paths)
    pointer = _stored_pointer(paths, first)
    pointer["months"]["2026-09"]["relative_path"] = relative_path
    to = _plant_pointer(paths, pointer)

    _rollback_is_rejected(paths, to, "ruta fuera de versions/")


def test_rollback_rejects_symlink_escaping_versions(paths, tmp_path):
    first = _two_pointers(paths)
    outside = tmp_path / "fuera.json"
    outside.write_bytes(b"{}")
    link = paths.versions_dir / "enlace.json"
    try:
        link.symlink_to(outside)
    except OSError as exc:  # Windows sin privilegio de symlink
        pytest.skip(f"symlink no disponible: {exc}")
    pointer = _stored_pointer(paths, first)
    pointer["months"]["2026-09"]["relative_path"] = "enlace.json"
    to = _plant_pointer(paths, pointer)

    _rollback_is_rejected(paths, to, "ruta fuera de versions/")


def test_rollback_rejects_missing_version(paths):
    """F4b: antes salía FileNotFoundError (exit 1) sin JSON."""
    first = _two_pointers(paths)
    name = _stored_pointer(paths, first)["months"]["2026-09"]["relative_path"]
    (paths.versions_dir / name).unlink()

    _rollback_is_rejected(paths, first[:12], "no existe la versión")


def test_rollback_rejects_version_with_wrong_sha(paths):
    first = _two_pointers(paths)
    name = _stored_pointer(paths, first)["months"]["2026-09"]["relative_path"]
    (paths.versions_dir / name).write_bytes(b'{"alterada": true}\n')

    _rollback_is_rejected(paths, first[:12], "sha256 de .* no coincide")


@pytest.mark.parametrize(
    "content",
    [
        b"{no es json",
        b"\xff\xfe\x00",
        b"[]",
        b"null",
        b'{"months": {}}',
    ],
    ids=["json_roto", "no_utf8", "lista", "null", "sin_claves"],
)
def test_rollback_rejects_corrupt_pointer_file(paths, content):
    """F4b: puntero ilegible o sin estructura -> 65, nunca exit 1."""
    first = _two_pointers(paths)
    (paths.pointers_dir / f"{first[:12]}.json").write_bytes(content)

    _rollback_is_rejected(paths, first[:12], "inválido")


@pytest.mark.parametrize(
    "field, value, match",
    [
        ("schema_version", dmc.POINTER_SCHEMA_VERSION + 1, "schema_version"),
        ("station_id", "999999", "station_id"),
        ("months", [], "months"),
    ],
)
def test_rollback_rejects_pointer_with_wrong_structure(paths, field, value, match):
    first = _two_pointers(paths)
    pointer = dict(_stored_pointer(paths, first), **{field: value})
    to = _plant_pointer(paths, pointer, rehash=False)

    _rollback_is_rejected(paths, to, match)


def test_rollback_rejects_pointer_filed_under_another_id(paths):
    """Un puntero válido copiado con otro nombre no se republica."""
    first = _two_pointers(paths)
    content = (paths.pointers_dir / f"{first[:12]}.json").read_bytes()
    (paths.pointers_dir / "abc123.json").write_bytes(content)

    _rollback_is_rejected(paths, "abc123", "no corresponde al identificador")


def test_cli_invalid_rollback_prints_structured_error(paths, monkeypatch, capsys):
    first = _two_pointers(paths)
    (paths.pointers_dir / f"{first[:12]}.json").write_bytes(b"{no es json")
    real_rollback = dmc.rollback
    monkeypatch.setattr(
        dmc, "rollback", lambda to, **kw: real_rollback(to, paths=paths, **kw)
    )

    assert dmc.main(["rollback", "--to", first[:12]]) == dmc.EXIT_DATA

    err = capsys.readouterr().err
    assert "Traceback" not in err
    assert json.loads(err)["status"] == "error"


# --- Hardening pre-refresh: F5 calidad de filas ------------------------------


def _month_rows(month: str, total: int, nulls: int = 0, field="temperatura") -> list:
    start = datetime.fromisoformat(f"{month}-01T00:00")
    rows = [_record(start + timedelta(minutes=15 * i)) for i in range(total)]
    for record in rows[:nulls]:
        record[field] = None
    return rows


@pytest.mark.parametrize(
    "total, nulls, field",
    [
        (100, 0, "temperatura"),
        (100, 1, "temperatura"),  # exactamente 1 %
        (200, 2, "humedadRelativa"),  # exactamente 1 %
    ],
    ids=["0pct", "1pct_100", "1pct_200"],
)
def test_null_rows_up_to_threshold_are_published_and_observable(
    paths, total, nulls, field
):
    sep = _month_rows("2026-09", total, nulls, field)
    outcome = _run(paths, FakeDmc({"2026-08": _payload(AUG), "2026-09": _payload(sep)}))

    expected = {
        "total_rows": total,
        "null_rows": nulls,
        "discard_rate": nulls / total,
        "threshold": 0.01,
    }
    assert outcome.status == "published"
    assert outcome.row_quality["2026-09"] == expected
    last = json.loads(paths.history.read_text("utf-8").splitlines()[-1])
    assert last["row_quality"]["2026-09"] == expected
    entry = _pointer(paths)["months"]["2026-09"]
    parsed = parse_dmc_json(paths.versions_dir / entry["relative_path"])
    assert entry["record_count"] == total and len(parsed) == total - nulls
    assert _stored(paths, "2026-09") == sep  # nada se convierte en silencio


@pytest.mark.parametrize(
    "total, nulls", [(100, 2), (199, 2), (10, 1)], ids=["2pct", "1.005pct", "10pct"]
)
def test_null_rows_above_threshold_publish_nothing(paths, total, nulls):
    rows = _month_rows("2026-08", total, nulls)
    fake = FakeDmc({"2026-08": _payload(rows), "2026-09": _payload(SEP)})

    with pytest.raises(dmc.DmcRefreshError, match="threshold=0.01") as err:
        _run(paths, fake)

    assert err.value.exit_code == dmc.EXIT_DATA
    assert f"{nulls} de {total} filas" in str(err.value)
    assert fake.calls == ["2026-08"]
    _assert_nothing_published(paths)
    assert not paths.versions_dir.exists() and not paths.history.exists()


@pytest.mark.parametrize(
    "field, value",
    [
        ("temperatura", "sin dato"),
        ("temperatura", ""),
        ("humedadRelativa", "N/A"),
        ("humedadRelativa", True),
        ("temperatura", float("nan")),
        ("temperatura", float("inf")),
        ("temperatura", {"valor": 1}),
        ("temperatura", [18.8]),
    ],
)
def test_present_non_numeric_value_is_always_rejected(paths, field, value):
    rows = _month_rows("2026-08", 1000)
    rows[500][field] = value  # una sola fila: 0,1 %
    fake = FakeDmc({"2026-08": _payload(rows), "2026-09": _payload(SEP)})

    with pytest.raises(dmc.DmcRefreshError, match="no es numérico") as err:
        _run(paths, fake)

    assert err.value.exit_code == dmc.EXIT_DATA
    _assert_nothing_published(paths)
    assert not paths.versions_dir.exists()


def test_missing_required_field_is_rejected(paths):
    rows = _month_rows("2026-08", 100)
    del rows[3]["humedadRelativa"]
    with pytest.raises(dmc.DmcRefreshError, match="sin campo 'humedadRelativa'"):
        _run(paths, FakeDmc({"2026-08": _payload(rows), "2026-09": _payload(SEP)}))
    _assert_nothing_published(paths)


def test_null_within_threshold_plus_non_numeric_is_rejected(paths):
    rows = _month_rows("2026-08", 200, nulls=1)  # 0,5 %: tolerado por sí solo
    rows[1]["humedadRelativa"] = "error sensor"
    with pytest.raises(dmc.DmcRefreshError, match="no es numérico"):
        _run(paths, FakeDmc({"2026-08": _payload(rows), "2026-09": _payload(SEP)}))
    _assert_nothing_published(paths)
    assert not paths.versions_dir.exists()


def test_rejected_month_leaves_existing_store_byte_identical(paths):
    """Con un almacén ya publicado, un mes que supera el umbral no deja
    versión, puntero ni historial nuevos."""
    _run(paths, FakeDmc({"2026-08": _payload(AUG), "2026-09": _payload(SEP)}))
    before = {
        p: (paths.station_dir / p).read_bytes() for p in _files(paths.station_dir)
    }
    worse = _records("2026-09-01T00:00", "2026-09-01T05:00")
    for record in worse[:3]:
        record["humedadRelativa"] = None

    with pytest.raises(dmc.DmcRefreshError, match="no se publica nada"):
        _run(paths, FakeDmc({"2026-09": _payload(worse)}), now=NOW + timedelta(hours=1))

    after = {p: (paths.station_dir / p).read_bytes() for p in _files(paths.station_dir)}
    assert after == before


def test_version_is_rejected_if_parser_drops_uncounted_rows(paths, monkeypatch):
    """Invariante de relectura: parse_dmc_json conserva exactamente las
    filas no nulas. Si descartara otra (p. ej. por un cambio del parser),
    la versión no se publica."""
    real_parse = dmc.parse_dmc_json
    monkeypatch.setattr(dmc, "parse_dmc_json", lambda p: real_parse(p).iloc[1:])

    with pytest.raises(dmc.DmcRefreshError, match="parse_dmc_json conserva") as err:
        _run(paths, FakeDmc({"2026-08": _payload(AUG), "2026-09": _payload(SEP)}))

    assert err.value.exit_code == dmc.EXIT_DATA
    _assert_nothing_published(paths)

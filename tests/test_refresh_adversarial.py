"""Pruebas adversariales para SAPI-71 (Fase B / Preparación de Validación).

Pruebas offline discriminantes de integridad, atomicidad, rollback,
idempotencia y fallos controlados en los motores de refresco FIRMS y DMC.

Usar tests/sapi71_offline_runner.py para bloqueo de red y .env antes de imports.
Las pruebas corren en tmp_path con credenciales sintéticas. No modifican archivos congelados ni datos operacionales.
"""

from __future__ import annotations

import io
import json
import socket
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest

import src.inference.scoring_inputs as scoring_inputs
import src.procesamiento.firms_source as firms_source
import src.refresh.atomic as atomic
import src.refresh.dmc_refresh as dmc
import src.refresh.firms_refresh as fr
from src.inference.scoring_inputs import DMC_POINTER_SCHEMA_VERSION, PinnedInputError
from src.procesamiento.firms_source import (
    FIRMS_BASELINE_COVERAGE,
    PROJECTED_POINTER_SCHEMA_VERSION,
    FirmsSourceError,
    resolve_firms_source,
)
from src.refresh.lock import RefreshLockedError, refresh_lock

# --- Constantes y fixtures compartidas ----------------------------------------

MAP_KEY = "dummy-map-key-adversarial-test"
STATION = dmc.DMC_STATION_ID
CREDS = ("usuario-test", "token-test")
NOW = datetime(2026, 9, 23, 15, 0, tzinfo=timezone.utc)

API_COLUMNS = (
    "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,"
    "instrument,confidence,version,bright_ti5,frp,daynight"
)
BASE_HEADER = API_COLUMNS + ",type,firms_source,request_start_date"
BASE_END = FIRMS_BASELINE_COVERAGE[1]  # 2026-08-30
TODAY = BASE_END + timedelta(days=7)


def _sha(data: bytes) -> str:
    return atomic.sha256_bytes(data)


@pytest.fixture(autouse=True)
def _block_all_network(monkeypatch):
    """Defensa durante la prueba; usar el runner para bloquear antes de imports."""
    def _refuse(*_args, **_kwargs):
        raise AssertionError("Intento de conexión de red en prueba adversarial offline")

    monkeypatch.setattr(socket.socket, "connect", _refuse)
    monkeypatch.setattr(socket, "create_connection", _refuse)


# --- Fixtures sintéticas para FIRMS ---

@pytest.fixture
def firms_paths(tmp_path) -> fr.FirmsPaths:
    base_content = (
        BASE_HEADER + "\r\n"
        "-33.1,-71.2,330.1,0.5,0.4,2026-08-29,1850,N,VIIRS,n,2,290.1,3.2,D,0,"
        "VIIRS_SNPP_SP,2026-08-26\r\n"
    ).encode("utf-8")
    baseline = tmp_path / "baseline.csv"
    baseline.write_bytes(base_content)
    return fr.FirmsPaths(
        pointer=tmp_path / "firms" / "CURRENT.json",
        versions_dir=tmp_path / "firms" / "versions",
        baseline_csv=baseline,
        baseline_sha256=_sha(base_content),
        raw_dir=tmp_path / "firms_raw",
    )


def _firms_row(day: date, lat: float = -33.05, time: int = 1745) -> str:
    return f"{lat},-71.4,331.0,0.5,0.4,{day.isoformat()},{time},N,VIIRS,n,2.0NRT,291.0,4.1,D"


class FakeFirmsClient:
    """Mock determinista de NasaFirmsBackfill para pruebas offline."""
    def __init__(self, rows_by_date: dict[date, list[str]] | None = None, fail_after_windows: int = -1):
        self.rows_by_date = rows_by_date or {}
        self.fail_after_windows = fail_after_windows
        self.downloaded_count = 0

    def fetch_availability(self):
        from src.ingesta.nasa_firms_backfill import Availability, NRT_SOURCE, SP_SOURCE
        return {
            SP_SOURCE: Availability(SP_SOURCE, date(2021, 1, 1), date(2026, 8, 30)),
            NRT_SOURCE: Availability(NRT_SOURCE, date(2026, 8, 25), date(2026, 9, 20)),
        }

    def download_window(self, window, target_path: Path | None = None):
        from src.ingesta.nasa_firms_backfill import NRT_SOURCE
        if self.fail_after_windows >= 0 and self.downloaded_count >= self.fail_after_windows:
            raise RuntimeError("Fallo simulado en descarga FIRMS")
        self.downloaded_count += 1
        lines = [API_COLUMNS]
        for offset in range(window.day_range):
            current_day = window.start_date + timedelta(days=offset)
            if current_day in self.rows_by_date:
                lines.extend(self.rows_by_date[current_day])
            else:
                lines.append(_firms_row(current_day))
        csv_text = "\n".join(lines) + "\n"
        df = pd.read_csv(io.StringIO(csv_text))
        df["firms_source"] = NRT_SOURCE
        df["request_start_date"] = window.start_date.isoformat()
        if target_path is None:
            target_path = Path(f"mock_raw_{window.start_date.isoformat()}.csv")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(csv_text, encoding="utf-8")
        return target_path, df


# --- Fixtures sintéticas para DMC ---

@pytest.fixture
def dmc_paths(tmp_path) -> dmc.DmcPaths:
    return dmc.DmcPaths(root=tmp_path / "dmc")


def _dmc_record(moment: datetime, temp: float = 18.8) -> dict:
    return {
        "momento": moment.strftime(dmc.MOMENTO_FORMAT),
        "temperatura": f"{temp} °C",
        "humedadRelativa": "70 %",
        "fuerzaDelViento": "8.5 kt",
        "direccionDelViento": "230 °",
    }


def _dmc_records_range(start: str, end: str, temp: float = 18.8) -> list[dict]:
    cursor = datetime.fromisoformat(start)
    stop = datetime.fromisoformat(end)
    records = []
    while cursor <= stop:
        records.append(_dmc_record(cursor, temp))
        cursor += timedelta(minutes=15)
    return records


def _dmc_payload(records: list[dict], tz="UTC") -> dict:
    return {
        "organismo": "DMC",
        "pais": "Chile",
        "producto": "Datos Recientes",
        "timezone": tz,
        "registros": len(records),
        "datosEstaciones": {
            "estacion": {"codigoNacional": STATION, "nombreEstacion": "Rodelillo"},
            "datos": records,
        },
    }


class FakeDmcSession:
    """Mock determinista de requests.Session para DMC."""
    def __init__(self, payloads_by_month: dict[str, dict | Exception]):
        self.payloads = payloads_by_month
        self.calls = []

    def get(self, url: str, params=None, timeout=None):
        year, month = url.rstrip("/").split("/")[-2:]
        month_key = f"{year}-{int(month):02d}"
        self.calls.append(month_key)
        if month_key not in self.payloads:
            resp = MagicMock(status_code=404)
            resp.json.side_effect = ValueError("Not found")
            return resp
        item = self.payloads[month_key]
        if isinstance(item, Exception):
            raise item
        resp = MagicMock(status_code=200)
        resp.json.return_value = json.loads(json.dumps(item))
        return resp


# ==============================================================================
# ADV-01: Falla atómica en DMC multi-mes y recuperación posterior idempotente
# ==============================================================================


def test_adv01_dmc_multimonth_partial_failure_atomic_recovery(dmc_paths):
    """ADV-01: Cuando un refresco multimes falla en el último mes:
    1) CURRENT.json permanece intacto en su estado previo (o ausente si es la primera corrida).
    2) Las versiones mensuales escritas antes del fallo quedan aisladas en versions/.
    3) Una corrida posterior exitosa se recupera sin colisión de versiones inmutables y
       conmuta CURRENT.json de forma atómica.
    """
    aug_records = _dmc_records_range("2026-08-31T20:00", "2026-08-31T23:45")
    sep_records_v1 = _dmc_records_range("2026-09-01T00:00", "2026-09-01T03:00")
    sep_records_v2 = _dmc_records_range("2026-09-01T00:00", "2026-09-01T06:00")
    oct_records = _dmc_records_range("2026-10-01T00:00", "2026-10-01T04:00")

    # Corrida 1: Publica estado inicial (agosto y septiembre v1)
    session1 = FakeDmcSession({
        "2026-08": _dmc_payload(aug_records),
        "2026-09": _dmc_payload(sep_records_v1),
    })
    outcome1 = dmc.refresh(paths=dmc_paths, session=session1, credentials=CREDS, now=NOW, sleep=lambda _: None)
    assert outcome1.status == "published"
    initial_pointer_bytes = dmc_paths.pointer.read_bytes()
    initial_pointer = json.loads(initial_pointer_bytes.decode("utf-8"))
    assert set(initial_pointer["months"].keys()) == {"2026-08", "2026-09"}
    initial_sep_file = dmc_paths.versions_dir / initial_pointer["months"]["2026-09"]["relative_path"]
    assert initial_sep_file.exists()

    # Corrida 2 (Adversarial): El tiempo avanza a Octubre.
    # Septiembre trae lecturas adicionales (v2) y se escribe una versión inmutable NUEVA en disco,
    # pero Octubre falla con un error de dominio NETWORK simulado (no HTTP 500).
    now_october = datetime(2026, 10, 1, 10, 0, tzinfo=timezone.utc)
    session2_failing = FakeDmcSession({
        "2026-09": _dmc_payload(sep_records_v2),
        "2026-10": dmc.DmcRefreshError("Fallo simulado 500 en Octubre", dmc.EXIT_NETWORK),
    })

    with pytest.raises(dmc.DmcRefreshError) as exc_info:
        dmc.refresh(paths=dmc_paths, session=session2_failing, credentials=CREDS, now=now_october, sleep=lambda _: None)

    assert exc_info.value.exit_code == dmc.EXIT_NETWORK

    # Verificación 1: Se generó efectivamente una versión mensual nueva en versions/ antes del fallo
    all_sep_files = list(dmc_paths.versions_dir.glob(f"dmc_{STATION}_2026-09_*.json"))
    assert len(all_sep_files) == 2, "Debe existir la versión v1 inicial y la nueva v2 escrita antes de fallar"
    new_sep_file = [f for f in all_sep_files if f != initial_sep_file][0]
    assert new_sep_file.exists()

    # Verificación 2: CURRENT.json no cambió ni 1 solo byte (aislado del fallo)
    assert dmc_paths.pointer.read_bytes() == initial_pointer_bytes
    current_check = json.loads(dmc_paths.pointer.read_text(encoding="utf-8"))
    assert current_check["months"]["2026-09"]["relative_path"] == initial_sep_file.name

    # Verificación 3: El historial solo tiene el evento inicial
    history_lines = dmc_paths.history.read_text(encoding="utf-8").splitlines()
    assert len(history_lines) == 1
    assert json.loads(history_lines[0])["event"] == "publish"
    # Verificación 4: El lock fue liberado
    assert not dmc_paths.lock.exists()

    # Corrida 3 (Recuperación / Replay idempotente): El servicio se restablece y Octubre responde bien.
    # La versión de septiembre ya existe en disco con esos bytes idénticos (escritura inmutable idempotente).
    session3_ok = FakeDmcSession({
        "2026-09": _dmc_payload(sep_records_v2),
        "2026-10": _dmc_payload(oct_records),
    })
    outcome3 = dmc.refresh(paths=dmc_paths, session=session3_ok, credentials=CREDS, now=now_october, sleep=lambda _: None)

    assert outcome3.status == "published"
    recovered_pointer = json.loads(dmc_paths.pointer.read_text(encoding="utf-8"))
    assert set(recovered_pointer["months"].keys()) == {"2026-08", "2026-09", "2026-10"}
    assert recovered_pointer["months"]["2026-09"]["relative_path"] == new_sep_file.name
    assert recovered_pointer["coverage_end"] == "2026-10-01 04:00:00"

    # En el historial ahora hay exactamente 2 publicaciones
    history_lines_after = dmc_paths.history.read_text(encoding="utf-8").splitlines()
    assert len(history_lines_after) == 2

    # Fourth execution: a completed refresh is idempotent, including its audit trail.
    pointer_before_replay = dmc_paths.pointer.read_bytes()
    history_before_replay = dmc_paths.history.read_bytes()
    versions_before_replay = {p.name: p.read_bytes() for p in dmc_paths.versions_dir.iterdir()}
    replay = dmc.refresh(
        paths=dmc_paths,
        session=FakeDmcSession({"2026-10": _dmc_payload(oct_records)}),
        credentials=CREDS, now=now_october, sleep=lambda _: None,
    )
    assert replay.status == "unchanged"
    assert dmc_paths.pointer.read_bytes() == pointer_before_replay
    assert dmc_paths.history.read_bytes() == history_before_replay
    assert {p.name: p.read_bytes() for p in dmc_paths.versions_dir.iterdir()} == versions_before_replay
    assert not dmc_paths.lock.exists()


# ==============================================================================
# ADV-04: Rollback con store desincronizado (versiones eliminadas o corruptas)
# ==============================================================================


def test_adv04a_firms_rollback_missing_csv_version_fails_usage(firms_paths):
    """ADV-04a: En FIRMS, si el sidecar .json existe pero el archivo .csv
    asociado fue eliminado, rollback debe abortar con EXIT_USAGE (2) sin alterar CURRENT.
    """
    def factory(raw_dir: Path):
        client = MagicMock()
        client.fetch_availability.return_value = FakeFirmsClient().fetch_availability()
        from src.ingesta.nasa_firms_backfill import NRT_SOURCE

        def download(window):
            raw_csv = raw_dir / f"test_{window.start_date.isoformat()}.csv"
            raw_csv.parent.mkdir(parents=True, exist_ok=True)
            day_str = window.start_date.isoformat()
            row_str = f"-33.05,-71.4,331.0,0.5,0.4,{day_str},1745,N,VIIRS,n,2.0NRT,291.0,4.1,D\n"
            raw_csv.write_text(API_COLUMNS + "\n" + row_str, encoding="utf-8")
            df = pd.read_csv(io.StringIO(API_COLUMNS + "\n" + row_str))
            df["firms_source"] = NRT_SOURCE
            df["request_start_date"] = day_str
            return raw_csv, df

        client.download_window.side_effect = download
        return client

    # Publicar versión 1
    fr.refresh(paths=firms_paths, client_factory=factory, map_key=MAP_KEY, today=BASE_END + timedelta(days=2))
    ptr_v1 = json.loads(firms_paths.pointer.read_text(encoding="utf-8"))

    # Publicar versión 2
    fr.refresh(paths=firms_paths, client_factory=factory, map_key=MAP_KEY, today=BASE_END + timedelta(days=4))
    ptr_v2_bytes = firms_paths.pointer.read_bytes()

    # Adversarial: Borrar el archivo .csv de la versión 1, dejando intacto el sidecar .json
    v1_csv = firms_paths.versions_dir / ptr_v1["relative_path"]
    assert v1_csv.exists()
    v1_csv.unlink()

    # Intentar rollback a versión 1
    with pytest.raises(fr.FirmsRefreshError) as exc_info:
        fr.rollback(ptr_v1["relative_path"], paths=firms_paths)

    # Contrato: falta el archivo -> EXIT_USAGE (2)
    assert exc_info.value.exit_code == fr.EXIT_USAGE
    # CURRENT.json permanece intacto en versión 2
    assert firms_paths.pointer.read_bytes() == ptr_v2_bytes
    # El historial no registra rollback fallido
    events = [json.loads(line)["event"] for line in firms_paths.history.read_text("utf-8").splitlines()]
    assert events == ["publish", "publish"]


def test_adv04b_dmc_rollback_missing_version_fails_data(dmc_paths):
    """ADV-04b: En DMC, si un puntero en pointers/ hace referencia a una versión
    mensual cuyo archivo fue eliminado, rollback debe abortar con EXIT_DATA (65)
    y el CURRENT vigente (Publicación 2) debe mantenerse intacto y plenamente verificable.
    """
    aug = _dmc_records_range("2026-08-31T22:00", "2026-08-31T23:45")
    sep1 = _dmc_records_range("2026-09-01T00:00", "2026-09-01T02:00")
    sep2 = _dmc_records_range("2026-09-01T00:00", "2026-09-01T06:00")

    # Publicación 1 (August + September v1)
    s1 = FakeDmcSession({"2026-08": _dmc_payload(aug), "2026-09": _dmc_payload(sep1)})
    dmc.refresh(paths=dmc_paths, session=s1, credentials=CREDS, now=NOW, sleep=lambda _: None)
    ptr1 = json.loads(dmc_paths.pointer.read_text(encoding="utf-8"))
    sha12_target = ptr1["manifest_sha256"][:12]
    v_sep1_file = dmc_paths.versions_dir / ptr1["months"]["2026-09"]["relative_path"]

    # Publicación 2 (September updated to v2 with additional records)
    s2 = FakeDmcSession({"2026-09": _dmc_payload(sep2)})
    dmc.refresh(paths=dmc_paths, session=s2, credentials=CREDS, now=NOW + timedelta(hours=4), sleep=lambda _: None)
    ptr2_bytes = dmc_paths.pointer.read_bytes()
    ptr2 = json.loads(ptr2_bytes.decode("utf-8"))
    v_sep2_file = dmc_paths.versions_dir / ptr2["months"]["2026-09"]["relative_path"]
    assert v_sep1_file != v_sep2_file, "Publicación 2 debe tener un archivo de versión de septiembre distinto"

    # Adversarial: Borrar ÚNICAMENTE el archivo de versión sep1 que necesita la Publicación 1
    # La Publicación 2 usa sep2 y aug, los cuales permanecen intactos en disco.
    v_sep1_file.unlink()
    assert not v_sep1_file.exists()
    assert v_sep2_file.exists()

    # Verificar que el CURRENT vigente (Publicación 2) es 100% íntegro y verificable
    current_verified = dmc.read_current(paths=dmc_paths)
    assert current_verified is not None
    assert current_verified["manifest_sha256"] == ptr2["manifest_sha256"]

    # Intentar rollback hacia Publicación 1
    with pytest.raises(dmc.DmcRefreshError) as exc_info:
        dmc.rollback(sha12_target, paths=dmc_paths)

    # Contrato: _verify_pointer detecta versión faltante -> EXIT_DATA (65)
    assert exc_info.value.exit_code == dmc.EXIT_DATA
    # CURRENT.json permanece intacto en Publicación 2
    assert dmc_paths.pointer.read_bytes() == ptr2_bytes
    # Y el reader/pipeline sigue verificando CURRENT exitosamente
    current_after = dmc.read_current(paths=dmc_paths)
    assert current_after is not None
    assert current_after["manifest_sha256"] == ptr2["manifest_sha256"]
    # No se añadió rollback a pointer_history
    events = [json.loads(line)["event"] for line in dmc_paths.history.read_text("utf-8").splitlines()]
    assert events == ["publish", "publish"]


# ==============================================================================
# ADV-06: Verificación anti-tamper en el Reader (scoring_inputs / capture)
# ==============================================================================


def test_adv06a_reader_firms_rejects_schema_version_mismatch(tmp_path):
    """ADV-06a: El lector FIRMS debe rechazar con FirmsSourceError un CURRENT.json
    con schema_version desconocido (evita procesar esquemas no soportados).
    """
    ptr_file = tmp_path / "CURRENT.json"
    ptr_file.write_text(
        json.dumps({
            "schema_version": 999,
            "relative_path": "version.csv",
            "sha256": "0" * 64,
            "coverage_start": "2026-08-30",
            "coverage_end": "2026-09-05",
        }),
        encoding="utf-8",
    )
    with pytest.raises(FirmsSourceError, match="esquema no soportado"):
        resolve_firms_source(reproducibility=False, pointer_path=ptr_file, versions_dir=tmp_path)


def test_adv06b_reader_dmc_rejects_schema_version_mismatch(tmp_path):
    """ADV-06b: El lector DMC debe rechazar con PinnedInputError un CURRENT.json
    con schema_version distinto de POINTER_SCHEMA_VERSION.
    """
    station_dir = tmp_path / STATION
    station_dir.mkdir(parents=True)
    ptr_file = station_dir / "CURRENT.json"
    ptr_file.write_text(
        json.dumps({
            "schema_version": 999,
            "station_id": STATION,
            "months": {},
            "manifest_sha256": "0" * 64,
        }),
        encoding="utf-8",
    )
    with pytest.raises(PinnedInputError, match="schema_version"):
        scoring_inputs.pin_dmc(STATION, legacy_dir=tmp_path / "legacy", store_dir=tmp_path)


def test_adv06c_reader_zero_byte_current_json_fails_closed(tmp_path):
    """ADV-06c: Si CURRENT.json existe pero tiene 0 bytes (archivo truncado por caída
    del sistema previa), el reader no debe explotar con unhandled exception sino
    fallar de forma controlada (FirmsSourceError / PinnedInputError).
    """
    # 1. FIRMS
    firms_ptr = tmp_path / "firms_CURRENT.json"
    firms_ptr.write_bytes(b"")
    with pytest.raises(FirmsSourceError):
        resolve_firms_source(reproducibility=False, pointer_path=firms_ptr, versions_dir=tmp_path)

    # 2. DMC
    station_dir = tmp_path / STATION
    station_dir.mkdir(parents=True, exist_ok=True)
    dmc_ptr = station_dir / "CURRENT.json"
    dmc_ptr.write_bytes(b"")
    with pytest.raises(PinnedInputError):
        scoring_inputs.pin_dmc(STATION, legacy_dir=tmp_path / "legacy", store_dir=tmp_path)


def test_adv06d_reader_firms_rejects_content_tamper_hash_mismatch(firms_paths):
    """Valid v3 publication/read first, then mutate CSV bytes only."""
    from test_remediation_red_defects import _make_firms_factory

    outcome = fr.refresh(
        paths=firms_paths, client_factory=_make_firms_factory(), map_key=MAP_KEY,
        today=BASE_END + timedelta(days=2),
    )
    source = resolve_firms_source(
        reproducibility=False, pointer_path=firms_paths.pointer,
        versions_dir=firms_paths.versions_dir,
    )
    assert source.origin == "current"
    csv_file = firms_paths.versions_dir / outcome.pointer["relative_path"]
    assert source.path == csv_file
    original = csv_file.read_bytes()
    assert _sha(original) == outcome.pointer["sha256"]
    pointer_before = firms_paths.pointer.read_bytes()
    tampered = original.replace(b"-33.05", b"-33.99")
    assert tampered != original
    csv_file.write_bytes(tampered)
    assert firms_paths.pointer.read_bytes() == pointer_before
    with pytest.raises(FirmsSourceError, match="no coincide con el puntero FIRMS"):
        resolve_firms_source(
            reproducibility=False, pointer_path=firms_paths.pointer,
            versions_dir=firms_paths.versions_dir,
        )


def test_adv06e_reader_dmc_rejects_content_tamper_hash_mismatch(tmp_path):
    """ADV-06e: Anti-tamper en DMC: el puntero CURRENT.json tiene un manifest canónico
    consistente con sus meses, pero los bytes de una versión mensual en versions/
    fueron alterados posteriormente. pin_dmc debe detectar la corrupción de integridad
    y rechazar con PinnedInputError.
    """
    station_dir = tmp_path / STATION
    versions_dir = station_dir / "versions"
    versions_dir.mkdir(parents=True)

    records = _dmc_records_range("2026-08-31T20:00", "2026-08-31T23:00")
    valid_doc = {STATION: _dmc_payload(records)}
    valid_bytes = json.dumps(valid_doc).encode("utf-8")
    real_sha = _sha(valid_bytes)

    version_name = f"dmc_{STATION}_2026-08_{real_sha[:12]}.json"
    version_file = versions_dir / version_name
    version_file.write_bytes(valid_bytes)

    months = {
        "2026-08": {
            "relative_path": version_name,
            "sha256": real_sha,
            "record_count": len(records),
            "first_momento": records[0]["momento"],
            "last_momento": records[-1]["momento"],
        }
    }
    manifest = scoring_inputs._canonical_sha(months)

    ptr_file = station_dir / "CURRENT.json"
    ptr_file.write_text(
        json.dumps({
            "schema_version": DMC_POINTER_SCHEMA_VERSION,
            "station_id": STATION,
            "months": months,
            "manifest_sha256": manifest,
            "coverage_start": records[0]["momento"],
            "coverage_end": records[-1]["momento"],
            "record_count": len(records),
            "created_at": NOW.isoformat(),
            "source": "dmc",
        }),
        encoding="utf-8",
    )

    # Positive controls through the writer's pointer reader and actual scoring reader.
    verified = dmc.read_current(paths=dmc.DmcPaths(root=tmp_path))
    assert verified["manifest_sha256"] == manifest
    pinned = scoring_inputs.pin_dmc(
        STATION, legacy_dir=tmp_path / "legacy", store_dir=tmp_path
    )
    assert not pinned.series.empty
    pointer_before = ptr_file.read_bytes()

    # Change bytes only, preserving pointer/manifest.
    tampered_bytes = valid_bytes.replace(b"18.8", b"99.9")
    assert tampered_bytes != valid_bytes
    version_file.write_bytes(tampered_bytes)
    assert ptr_file.read_bytes() == pointer_before

    with pytest.raises(PinnedInputError, match="sha256"):
        scoring_inputs.pin_dmc(STATION, legacy_dir=tmp_path / "legacy", store_dir=tmp_path)



# ==============================================================================
# ADV-02: Resiliencia ante CURRENT.json preexistente corrupto en el pipeline
# ==============================================================================


def test_adv02a_firms_refresh_and_status_with_corrupt_current(firms_paths):
    """ADV-02a: Si CURRENT.json preexistente en FIRMS tiene 0 bytes o JSON corrupto:
    1) status() reporta 'invalid_pointer' de forma controlada.
    2) refresh() aborta con EXIT_DATA (65) sin sobreescribir a ciegas ni llamar a la API.
    """
    firms_paths.pointer.parent.mkdir(parents=True, exist_ok=True)
    firms_paths.pointer.write_bytes(b"")  # 0 bytes

    # status() debe manejarlo de forma segura
    st = fr.status(paths=firms_paths)
    assert st["origin"] == "invalid_pointer"
    assert "error" in st

    # refresh() debe fallar con EXIT_DATA
    factory = MagicMock()
    with pytest.raises(fr.FirmsRefreshError) as exc_info:
        fr.refresh(paths=firms_paths, client_factory=factory, map_key=MAP_KEY, today=TODAY)
    assert exc_info.value.exit_code == fr.EXIT_DATA
    factory.assert_not_called()


def test_adv02b_dmc_refresh_and_status_with_corrupt_current(dmc_paths):
    """ADV-02b: Homólogo en DMC: si CURRENT.json tiene contenido corrupto:
    1) status() reporta 'invalid_pointer'.
    2) refresh() aborta con EXIT_DATA (65) antes de pedir meses a la API.
    """
    dmc_paths.pointer.parent.mkdir(parents=True, exist_ok=True)
    dmc_paths.pointer.write_text("{json roto", encoding="utf-8")

    st = dmc.status(paths=dmc_paths)
    assert st["origin"] == "invalid_pointer"
    assert "error" in st

    session = FakeDmcSession({})
    with pytest.raises(dmc.DmcRefreshError) as exc_info:
        dmc.refresh(paths=dmc_paths, session=session, credentials=CREDS, now=NOW, sleep=lambda _: None)
    assert exc_info.value.exit_code == dmc.EXIT_DATA
    assert session.calls == []


# ==============================================================================
# ADV-03: Lock huérfano con payload corrupto / archivo de 0 bytes
# ==============================================================================


def test_adv03_corrupt_lock_treated_as_stale_and_breakable(tmp_path):
    """ADV-03: Si un archivo .refresh.lock existe pero tiene 0 bytes o contenido no JSON
    (e.g. creado por un touch o proceso que crasheó al inicializarse):
    1) Un proceso sin break_stale=True lo clasifica como huérfano y falla con RefreshLockedError.
    2) Un proceso con break_stale=True lo rompe limpiamente y toma el lock sin lanzar JSONDecodeError.
    """
    lock_file = tmp_path / ".refresh.lock"
    lock_file.write_bytes(b"")  # Archivo vacío

    # 1. Sin break_stale debe rechazar
    with pytest.raises(RefreshLockedError, match="huérfano"):
        with refresh_lock(lock_file, break_stale=False):
            pass

    assert lock_file.exists()  # El lock huérfano sigue ahí

    # 2. Con break_stale=True debe romperlo y tomarlo
    with refresh_lock(lock_file, break_stale=True) as info:
        assert lock_file.exists()
        assert info["pid"] > 0
        holder = json.loads(lock_file.read_text(encoding="utf-8"))
        assert holder["pid"] == info["pid"]

    # Al salir del contextmanager, el lock se libera
    assert not lock_file.exists()

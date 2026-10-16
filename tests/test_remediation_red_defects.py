"""Pruebas discriminantes de defectos (RED) para SAPI-71.

Evidencias reproducibles y ejecutables de B1/B2/B3 confirmados por la
auditoría independiente de Astra:
- B1: Rollback FIRMS insuficientemente validado (sidecar corrupto publicado a CURRENT).
- B2: Fallos de decodificación DMC (UnicodeDecodeError y JSONDecodeError escapan del dominio).
- B3: Clasificación DATA -> NETWORK en FIRMS (FirmsRefreshError atrapado como RuntimeError).

Usar tests/sapi71_offline_runner.py para aislamiento previo a los imports.
ADV-05 se caracteriza por separado; no forma parte del gate RED del bloque A.
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
import src.refresh.atomic as atomic
import src.refresh.dmc_refresh as dmc
import src.refresh.firms_refresh as fr
from src.inference.scoring_inputs import (
    DMC_POINTER_SCHEMA_VERSION,
    PinnedInputError,
)
from src.procesamiento.firms_source import (
    FIRMS_BASELINE_COVERAGE,
    PROJECTED_POINTER_SCHEMA_VERSION,
    FirmsSourceError,
    resolve_firms_source,
)

MAP_KEY = "dummy-map-key-red-test"
STATION = dmc.DMC_STATION_ID
CREDS = ("usuario-test", "token-test")
NOW = datetime(2026, 9, 23, 15, 0, tzinfo=timezone.utc)

API_COLUMNS = (
    "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,"
    "instrument,confidence,version,bright_ti5,frp,daynight"
)
BASE_HEADER = API_COLUMNS + ",type,firms_source,request_start_date"
BASE_END = FIRMS_BASELINE_COVERAGE[1]  # 2026-08-30


def _sha(data: bytes) -> str:
    return atomic.sha256_bytes(data)


@pytest.fixture(autouse=True)
def _block_all_network(monkeypatch):
    """Defensa adicional durante la prueba; el runner bloquea red antes de imports."""
    def _refuse(*_args, **_kwargs):
        raise AssertionError("Intento de conexión de red en prueba de defecto offline")

    monkeypatch.setattr(socket.socket, "connect", _refuse)
    monkeypatch.setattr(socket, "create_connection", _refuse)


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


def _make_firms_factory(raw_rows_by_date: dict[date, str] | None = None):
    def factory(raw_dir: Path):
        client = MagicMock()
        from src.ingesta.nasa_firms_backfill import Availability, NRT_SOURCE, SP_SOURCE
        client.fetch_availability.return_value = {
            SP_SOURCE: Availability(SP_SOURCE, date(2021, 1, 1), date(2026, 8, 30)),
            NRT_SOURCE: Availability(NRT_SOURCE, date(2026, 8, 25), date(2026, 9, 20)),
        }

        def download_window(window):
            raw_csv = raw_dir / f"test_{window.start_date.isoformat()}.csv"
            raw_csv.parent.mkdir(parents=True, exist_ok=True)
            lines = [API_COLUMNS]
            for offset in range(window.day_range):
                d = window.start_date + timedelta(days=offset)
                if raw_rows_by_date and d in raw_rows_by_date:
                    lines.append(raw_rows_by_date[d])
                else:
                    lines.append(f"-33.05,-71.4,331.0,0.5,0.4,{d.isoformat()},1745,N,VIIRS,n,2.0NRT,291.0,4.1,D")
            content = "\n".join(lines) + "\n"
            raw_csv.write_text(content, encoding="utf-8")
            df = pd.read_csv(io.StringIO(content))
            df["firms_source"] = NRT_SOURCE
            df["request_start_date"] = window.start_date.isoformat()
            return raw_csv, df

        client.download_window.side_effect = download_window
        return client

    return factory


# ==============================================================================
# DEFECT B1: Rollback FIRMS insuficientemente validado
# Archivo: src/refresh/firms_refresh.py (líneas 379-404)
# ==============================================================================


def test_b1_firms_rollback_unvalidated_sidecar_published_to_current(firms_paths):
    """B1 RED: rollback() en FIRMS valida que el archivo .csv exista y coincida
    con el sha256 del sidecar, pero NO valida la estructura ni metadatos del sidecar.

    Comportamiento anómalo en producto:
    1. Si un sidecar tiene el sha256 correcto pero le faltan campos obligatorios
       (ej. coverage_start) o tiene schema_version inválido, rollback() lo acepta
       y lo publica en CURRENT.json.
    2. Al llamar al reader resolve_firms_source(), este falla con FirmsSourceError.

    Invariante esperada:
    rollback() DEBE validar integralmente el sidecar ANTES de conmutar CURRENT.json,
    abortando con FirmsRefreshError(EXIT_DATA=65) y dejando CURRENT.json y el historial
    completamente intactos.
    """
    factory = _make_firms_factory()

    # Publicar Versión 1 (hasta 2026-08-31)
    outcome1 = fr.refresh(paths=firms_paths, client_factory=factory, map_key=MAP_KEY, today=BASE_END + timedelta(days=2))
    v1_name = outcome1.pointer["relative_path"]
    v1_sidecar_file = firms_paths.versions_dir / f"{Path(v1_name).stem}.json"
    assert v1_sidecar_file.exists()

    # Publicar Versión 2 (hasta 2026-09-02)
    fr.refresh(paths=firms_paths, client_factory=factory, map_key=MAP_KEY, today=BASE_END + timedelta(days=4))
    v2_pointer_bytes = firms_paths.pointer.read_bytes()
    history_bytes = firms_paths.history.read_bytes()
    v1_csv = firms_paths.versions_dir / v1_name
    csv_bytes = v1_csv.read_bytes()
    assert _sha(csv_bytes) == outcome1.pointer["sha256"]
    current_before = resolve_firms_source(
        reproducibility=False, pointer_path=firms_paths.pointer,
        versions_dir=firms_paths.versions_dir,
    )
    assert current_before.path.name == json.loads(v2_pointer_bytes)["relative_path"]

    # Corromper estructuralmente el sidecar de la Versión 1:
    # Conservar el sha256 válido del CSV para pasar el único check existente en rollback(),
    # pero eliminar el campo obligatorio 'coverage_start'.
    sidecar_data = json.loads(v1_sidecar_file.read_text(encoding="utf-8"))
    del sidecar_data["coverage_start"]
    v1_sidecar_file.write_text(json.dumps(sidecar_data), encoding="utf-8")
    assert sidecar_data["sha256"] == _sha(v1_csv.read_bytes()) == _sha(csv_bytes)

    # Invariante requerida: rollback debe rechazar el sidecar incompleto con EXIT_DATA (65)
    # y preservar CURRENT.json en la Versión 2.
    with pytest.raises(fr.FirmsRefreshError) as exc_info:
        fr.rollback(v1_name, paths=firms_paths)

    assert exc_info.value.exit_code == fr.EXIT_DATA, (
        f"Se esperaba EXIT_DATA (65) al intentar rollback a sidecar inválido, "
        f"pero se obtuvo {exc_info.value.exit_code}"
    )
    assert firms_paths.pointer.read_bytes() == v2_pointer_bytes
    assert firms_paths.history.read_bytes() == history_bytes
    assert v1_csv.read_bytes() == csv_bytes
    current_after = resolve_firms_source(
        reproducibility=False, pointer_path=firms_paths.pointer,
        versions_dir=firms_paths.versions_dir,
    )
    assert current_after == current_before
    assert not firms_paths.lock.exists()


def test_b1_firms_rollback_toctou_mutation_rejected(firms_paths, monkeypatch):
    """B1 TOCTOU: Comprueba que rollback() nunca publique contenido distinto del validado
    y no realice lecturas inseguras posteriores en disco.

    En el producto anterior con doble lectura (TOCTOU):
    1. _resolve_pointer() validaba el sidecar en disco.
    2. Una alteración en disco ocurrida tras la validación era leída por sidecar.read_text().
    3. CURRENT.json recibía metadatos corruptos/mutados sin validar.

    Invariante corregida:
    - Se lee y parsea el sidecar una sola vez en un snapshot inmutable.
    - Se valida ese snapshot con validate_pointer_dict().
    - Se publica exactamente el mismo snapshot validado.
    - Si el archivo en disco es alterado o eliminado después de ser leído por rollback(),
      la publicación utiliza el snapshot validado en memoria: nunca se publica el contenido
      corrupto y la inferencia resuelve la versión de forma íntegra.
    """
    factory = _make_firms_factory()

    # Publicar Versión 1 (hasta 2026-08-31)
    outcome1 = fr.refresh(
        paths=firms_paths,
        client_factory=factory,
        map_key=MAP_KEY,
        today=BASE_END + timedelta(days=2),
    )
    v1_name = outcome1.pointer["relative_path"]
    v1_sidecar_file = firms_paths.versions_dir / f"{Path(v1_name).stem}.json"
    assert v1_sidecar_file.exists()
    v1_pointer = outcome1.pointer

    # Publicar Versión 2 (hasta 2026-09-02)
    fr.refresh(
        paths=firms_paths,
        client_factory=factory,
        map_key=MAP_KEY,
        today=BASE_END + timedelta(days=4),
    )

    # Interceptar validate_pointer_dict para simular una alteración TOCTOU en disco
    # ocurrida justo durante el procesamiento de validación:
    import src.procesamiento.firms_source as fs

    real_validate = fs.validate_pointer_dict

    def hook_and_mutate_disk(pointer, versions_dir, source_name="CURRENT.json"):
        # Alterar el archivo físico en disco para simular mutación concurrente:
        mutated_on_disk = dict(pointer)
        mutated_on_disk["row_count"] = 999999
        mutated_on_disk["sha256"] = "0" * 64
        v1_sidecar_file.write_text(json.dumps(mutated_on_disk), encoding="utf-8")
        return real_validate(pointer, versions_dir, source_name=source_name)

    monkeypatch.setattr(fs, "validate_pointer_dict", hook_and_mutate_disk)

    # Rollback a v1 debe usar el snapshot validado en memoria y tener éxito:
    res = fr.rollback(v1_name, paths=firms_paths)
    assert res["relative_path"] == v1_name
    assert res["row_count"] == v1_pointer["row_count"]
    assert res["sha256"] == v1_pointer["sha256"]

    # Invariante crítica: CURRENT.json NUNCA debe contener los datos mutados en disco
    published = json.loads(firms_paths.pointer.read_text(encoding="utf-8"))
    assert published["row_count"] != 999999, "Vulnerabilidad TOCTOU: se publicó el contenido mutado de disco"
    assert published["sha256"] != "0" * 64
    assert published["row_count"] == v1_pointer["row_count"]
    assert published["sha256"] == v1_pointer["sha256"]

    # El reader activo resuelve con éxito la versión publicada
    current_resolved = resolve_firms_source(
        reproducibility=False,
        pointer_path=firms_paths.pointer,
        versions_dir=firms_paths.versions_dir,
    )
    assert current_resolved.path.name == v1_name
    assert not firms_paths.lock.exists()


def test_b1_firms_rollback_rejects_wrong_sha_and_preserves_current(firms_paths):
    """Verifica que rollback() rechace un sidecar con SHA incorrecto respecto al CSV,
    retornando EXIT_DATA=65 y preservando CURRENT.json e historial intactos."""
    factory = _make_firms_factory()

    outcome1 = fr.refresh(
        paths=firms_paths,
        client_factory=factory,
        map_key=MAP_KEY,
        today=BASE_END + timedelta(days=2),
    )
    v1_name = outcome1.pointer["relative_path"]
    v1_sidecar_file = firms_paths.versions_dir / f"{Path(v1_name).stem}.json"

    fr.refresh(
        paths=firms_paths,
        client_factory=factory,
        map_key=MAP_KEY,
        today=BASE_END + timedelta(days=4),
    )
    v2_pointer_bytes = firms_paths.pointer.read_bytes()
    history_bytes = firms_paths.history.read_bytes()

    # Corromper el hash esperado en el sidecar
    sidecar_data = json.loads(v1_sidecar_file.read_text(encoding="utf-8"))
    sidecar_data["sha256"] = "a" * 64
    v1_sidecar_file.write_text(json.dumps(sidecar_data), encoding="utf-8")

    with pytest.raises(fr.FirmsRefreshError) as exc_info:
        fr.rollback(v1_name, paths=firms_paths)

    assert exc_info.value.exit_code == fr.EXIT_DATA
    assert firms_paths.pointer.read_bytes() == v2_pointer_bytes
    assert firms_paths.history.read_bytes() == history_bytes


def test_b1_firms_rollback_rejects_escaping_path_and_preserves_current(firms_paths):
    """Verifica que rollback() rechace un sidecar que intente escapar de versions/,
    retornando EXIT_DATA=65 y preservando CURRENT.json e historial intactos."""
    factory = _make_firms_factory()

    outcome1 = fr.refresh(
        paths=firms_paths,
        client_factory=factory,
        map_key=MAP_KEY,
        today=BASE_END + timedelta(days=2),
    )
    v1_name = outcome1.pointer["relative_path"]
    v1_sidecar_file = firms_paths.versions_dir / f"{Path(v1_name).stem}.json"

    fr.refresh(
        paths=firms_paths,
        client_factory=factory,
        map_key=MAP_KEY,
        today=BASE_END + timedelta(days=4),
    )
    v2_pointer_bytes = firms_paths.pointer.read_bytes()
    history_bytes = firms_paths.history.read_bytes()

    # Manipular el sidecar para que apunte fuera de versions/
    sidecar_data = json.loads(v1_sidecar_file.read_text(encoding="utf-8"))
    sidecar_data["relative_path"] = "../baseline.csv"
    v1_sidecar_file.write_text(json.dumps(sidecar_data), encoding="utf-8")

    with pytest.raises(fr.FirmsRefreshError) as exc_info:
        fr.rollback(v1_name, paths=firms_paths)

    assert exc_info.value.exit_code == fr.EXIT_DATA
    assert firms_paths.pointer.read_bytes() == v2_pointer_bytes
    assert firms_paths.history.read_bytes() == history_bytes



def _assert_dmc_rejected(store_dir, boundary):
    if boundary == "pin_dmc":
        with pytest.raises(PinnedInputError):
            scoring_inputs.pin_dmc(
                STATION, legacy_dir=store_dir / "legacy", store_dir=store_dir
            )
        return

    # Narrow source-body test, NOT a full prototype_service import/integration test.
    # Compile the actual class/function unchanged. No stubs of pin_dmc or decoder.
    # This avoids unrelated rasterio imports and loading the scientific model.
    import ast
    from src.procesamiento.raw_parser import DmcFormatError

    path = Path(__file__).resolve().parents[1] / "src/inference/prototype_service.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    wanted = {"PrototypeUnavailableError", "capture_scoring_inputs"}
    nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))
             and n.name in wanted]
    assert {n.name for n in nodes} == wanted
    module = ast.Module(body=[ast.ImportFrom(module="__future__",
        names=[ast.alias(name="annotations")], level=0), *nodes], type_ignores=[])
    ast.fix_missing_locations(module)
    calls = []

    def model_boundary():
        calls.append("model")
        return None, None, None

    scope = {
        "datetime": datetime, "timezone": timezone, "pd": pd,
        "_reproducibility_mode": lambda: False, "_pin_model": model_boundary,
        "pin_dmc": scoring_inputs.pin_dmc, "STATION_ID": STATION,
        "DMC_RAW_DIR": store_dir / "legacy", "DMC_STORE_DIR": store_dir,
        "DmcFormatError": DmcFormatError, "PinnedInputError": PinnedInputError,
    }
    exec(compile(module, str(path), "exec"), scope)
    with pytest.raises(scope["PrototypeUnavailableError"]) as caught:
        scope["capture_scoring_inputs"]()
    assert calls == ["model"]
    assert isinstance(caught.value.__cause__, PinnedInputError)


# ==============================================================================
# DEFECT B2: Fallos de decodificación DMC fuera del manejo esperado
# Archivos: src/inference/scoring_inputs.py (líneas 133, 154) y src/procesamiento/raw_parser.py (línea 70)
# ==============================================================================


@pytest.mark.parametrize("boundary", ["pin_dmc", "capture_body"])
def test_b2_dmc_version_non_utf8_escapes_domain_boundary(tmp_path, boundary):
    """B2 RED (UTF-8): parse_dmc_bytes() llama a raw.decode('utf-8') sin protección.
    En scoring_inputs._read_versioned_months(), la llamada a parse_dmc_bytes() no está
    dentro de un bloque try/except.

    Comportamiento anómalo en producto:
    Un archivo mensual con hash válido en el manifest pero bytes no-UTF-8 hace que
    UnicodeDecodeError escape directamente sin convertirse en PinnedInputError.

    Invariante esperada:
    Cualquier fallo de decodificación o parseo en el almacén versionado debe capturarse
    y elevarse como PinnedInputError en el boundary de scoring.
    """
    station_dir = tmp_path / STATION
    versions_dir = station_dir / "versions"
    versions_dir.mkdir(parents=True)

    # Bytes no-UTF-8 pero con hash coherente en el manifest
    bad_bytes = b"\x80\xff\xfe\x00\x01\x02datos_binarios_invalidos"
    bad_sha = _sha(bad_bytes)
    version_name = f"dmc_{STATION}_2026-08_{bad_sha[:12]}.json"
    (versions_dir / version_name).write_bytes(bad_bytes)

    months = {
        "2026-08": {
            "relative_path": version_name,
            "sha256": bad_sha,
            "record_count": 10,
            "first_momento": "2026-08-31 20:00:00",
            "last_momento": "2026-08-31 22:00:00",
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
            "coverage_start": "2026-08-31 20:00:00",
            "coverage_end": "2026-08-31 22:00:00",
        }),
        encoding="utf-8",
    )

    # Invariante requerida: debe elevar PinnedInputError, no propagar UnicodeDecodeError
    _assert_dmc_rejected(tmp_path, boundary)


@pytest.mark.parametrize("boundary", ["pin_dmc", "capture_body"])
def test_b2_dmc_version_invalid_json_escapes_domain_boundary(tmp_path, boundary):
    """B2 RED (JSON): Similarmente, un archivo mensual con sintaxis JSON inválida
    (ej. JSON truncado) hace que json.decoder.JSONDecodeError escape sin ser
    atrapado como PinnedInputError.
    """
    station_dir = tmp_path / STATION
    versions_dir = station_dir / "versions"
    versions_dir.mkdir(parents=True)

    bad_json_bytes = b'{"organismo": "DMC", "incompleto": true, '
    bad_sha = _sha(bad_json_bytes)
    version_name = f"dmc_{STATION}_2026-08_{bad_sha[:12]}.json"
    (versions_dir / version_name).write_bytes(bad_json_bytes)

    months = {
        "2026-08": {
            "relative_path": version_name,
            "sha256": bad_sha,
            "record_count": 5,
            "first_momento": "2026-08-31 20:00:00",
            "last_momento": "2026-08-31 21:00:00",
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
            "coverage_start": "2026-08-31 20:00:00",
            "coverage_end": "2026-08-31 21:00:00",
        }),
        encoding="utf-8",
    )

    # Invariante requerida: debe elevar PinnedInputError, no propagar JSONDecodeError
    _assert_dmc_rejected(tmp_path, boundary)


# ==============================================================================
# DEFECT B3: Clasificación DATA -> NETWORK
# Archivo: src/refresh/firms_refresh.py (líneas 318-321)
# ==============================================================================


def test_b3_firms_coverage_gap_misclassified_as_exit_network(firms_paths):
    """B3 RED: FirmsRefreshError hereda de RuntimeError.
    En _download_new_rows (líneas 243-248), cuando faltan días en la disponibilidad
    de FIRMS, se lanza:
        raise FirmsRefreshError("... la cobertura no puede tener huecos.", EXIT_DATA)

    Sin embargo, en refresh() (líneas 318-321):
        except RuntimeError as exc:
            raise FirmsRefreshError(..., EXIT_NETWORK)

    Como FirmsRefreshError ES una subclase de RuntimeError, refresh() atrapa
    el error de datos con EXIT_DATA (65) y lo re-empaqueta erróneamente con EXIT_NETWORK (69).

    Invariante esperada:
    Un fallo de integridad de datos / hueco de cobertura DEBE mantener EXIT_DATA (65).
    """
    def factory_with_gap(raw_dir: Path):
        client = MagicMock()
        from src.ingesta.nasa_firms_backfill import Availability, NRT_SOURCE, SP_SOURCE
        # SP termina el 2026-08-30, pero NRT solo empieza el 2026-09-04.
        # Los días 2026-08-31 a 2026-09-03 quedan descubiertos (hueco).
        client.fetch_availability.return_value = {
            SP_SOURCE: Availability(SP_SOURCE, date(2021, 1, 1), date(2026, 8, 30)),
            NRT_SOURCE: Availability(NRT_SOURCE, date(2026, 9, 4), date(2026, 9, 10)),
        }
        return client

    # Intentar refrescar para hoy = 2026-09-07 (target_end = 2026-09-06)
    with pytest.raises(fr.FirmsRefreshError) as exc_info:
        fr.refresh(
            paths=firms_paths,
            client_factory=factory_with_gap,
            map_key=MAP_KEY,
            today=date(2026, 9, 7),
        )

    # Invariante requerida: la causa es un hueco en los datos -> EXIT_DATA (65)
    # En el producto actual, este assert FALLA con: assert 69 == 65
    assert exc_info.value.exit_code == fr.EXIT_DATA, (
        f"Defecto B3 confirmado: un hueco de cobertura reportó exit_code={exc_info.value.exit_code} "
        f"(EXIT_NETWORK=69) en lugar de EXIT_DATA=65"
    )

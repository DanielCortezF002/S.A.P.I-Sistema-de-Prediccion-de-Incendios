"""ScoringInputs: entradas fijadas al inicio de cada scoring (SAPI-71 Fase B).

Entorno "operacional" de prueba 100% versionado en git (corre en CI):
legacy DMC = snapshot Hito 1 (`dmc_historico_330007_2026-08.json` +
`dmc_meteo_2026-09-01.json`, última lectura 2026-09-01 01:30), línea base
FIRMS = snapshot Hito 1 (mismo sha256), modelo = `models/prototype_model_d.pkl`.
Los almacenes versionados (FIRMS `CURRENT.json`, DMC `CURRENT.json`) viven en
`tmp_path` y se publican con los writers reales. Sin red.
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

import src.inference.prototype_service as svc
import src.procesamiento.firms_source as firms_source
import src.refresh.dmc_refresh as dmc
import src.refresh.firms_refresh as fr
from src.geo.grid import all_cells
from src.inference.scoring_inputs import DMC_STORE_DIR, PinnedInputError, pin_dmc
from src.procesamiento.firms_source import (
    FIRMS_BASELINE_SHA256,
    FIRMS_REPRODUCIBILITY_CSV,
    POINTER_SCHEMA_VERSION,
)
from src.refresh.atomic import atomic_write_json

MODEL_D_FINGERPRINT = "33c2eacc49bd0cc130928b5bd182ec523e63614f0e3dd97a129a8d4657f231ff"
LEGACY_END = pd.Timestamp("2026-09-01 01:30:00", tz="UTC")
TARGET = all_cells()[0]  # VP-001


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _ranking_fingerprint(result) -> str:
    lines = "\n".join(f"{c.cell_id},{c.score!r},{c.rank}" for c in result.cells)
    return _sha(lines.encode())


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    def _refuse(*_args, **_kwargs):
        raise AssertionError("llamada de red real en un test de ScoringInputs")

    monkeypatch.setattr(socket.socket, "connect", _refuse)
    monkeypatch.setattr(socket, "create_connection", _refuse)


@pytest.fixture
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("SAPI_REPRODUCIBILITY_MODE", "0")
    monkeypatch.setattr(svc, "DMC_RAW_DIR", svc.REPRODUCIBILITY_DMC_DIR)
    monkeypatch.setattr(svc, "DMC_STORE_DIR", tmp_path / "dmc")
    monkeypatch.setattr(svc, "DEM_TERRAIN_DIR", tmp_path / "sin_dem")
    firms_dir = tmp_path / "firms"
    monkeypatch.setattr(
        firms_source, "FIRMS_CURRENT_POINTER", firms_dir / "CURRENT.json"
    )
    monkeypatch.setattr(firms_source, "FIRMS_VERSIONS_DIR", firms_dir / "versions")
    monkeypatch.setattr(firms_source, "FIRMS_BASELINE_CSV", FIRMS_REPRODUCIBILITY_CSV)
    return tmp_path


# --- Publicación con los writers reales --------------------------------------


def _detection(day: date) -> dict:
    lat = (TARGET["min_lat"] + TARGET["max_lat"]) / 2
    lon = (TARGET["min_lon"] + TARGET["max_lon"]) / 2
    return {
        "latitude": round(lat, 5),
        "longitude": round(lon, 5),
        "bright_ti4": 340.0,
        "scan": 0.4,
        "track": 0.4,
        "acq_date": day.isoformat(),
        "acq_time": 1800,
        "satellite": "N",
        "instrument": "VIIRS",
        "confidence": "n",
        "version": "2.0NRT",
        "bright_ti5": 295.0,
        "frp": 5.0,
        "daynight": "D",
        "type": 0,
        "firms_source": "VIIRS_SNPP_NRT",
        "request_start_date": day.isoformat(),
    }


def publish_firms(env: Path, detections: int) -> dict:
    """Versión FIRMS = línea base + `detections` en VP-001 el 2026-08-31."""
    base = FIRMS_REPRODUCIBILITY_CSV.read_bytes()
    rows = pd.DataFrame([_detection(date(2026, 8, 31))] * detections)
    if not detections:
        rows = pd.DataFrame(columns=list(_detection(date(2026, 8, 31))))
    data, _ = fr.build_version_bytes(base, rows, date(2026, 8, 30), date(2026, 8, 31))
    sha = _sha(data)
    name = f"firms_2021-08-30_2026-08-31_{sha[:12]}.csv"
    versions = env / "firms" / "versions"
    versions.mkdir(parents=True, exist_ok=True)
    (versions / name).write_bytes(data)
    pointer = {
        "schema_version": POINTER_SCHEMA_VERSION,
        "relative_path": name,
        "sha256": sha,
        "coverage_start": "2021-08-30",
        "coverage_end": "2026-08-31",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    atomic_write_json(env / "firms" / "CURRENT.json", pointer)
    return pointer


def _dmc_payload(records: list[dict]) -> dict:
    return {
        "timezone": "UTC",
        "registros": len(records),
        "fechaCreacion": "x",
        "datosEstaciones": {"estacion": {"codigoNacional": "330007"}, "datos": records},
    }


def _readings(start: str, end: str, temp: float = 15.0) -> list[dict]:
    cursor, stop, out = pd.Timestamp(start), pd.Timestamp(end), []
    while cursor <= stop:
        out.append(
            {
                "momento": cursor.strftime("%Y-%m-%d %H:%M:%S"),
                "temperatura": f"{temp} °C",
                "humedadRelativa": "60 %",
                "fuerzaDelViento": "5.0 kt",
                "direccionDelViento": "200 °",
            }
        )
        cursor += pd.Timedelta(minutes=15)
    return out


def publish_dmc(env: Path, by_month: dict, now: datetime) -> dict:
    """Publica con `dmc_refresh.refresh` real y una API simulada."""

    def get(url, params=None, timeout=None):
        year, month = url.rstrip("/").split("/")[-2:]
        response = MagicMock(status_code=200)
        response.json.return_value = _dmc_payload(by_month[f"{year}-{int(month):02d}"])
        return response

    session = MagicMock()
    session.get.side_effect = get
    dmc.refresh(
        paths=dmc.DmcPaths(root=env / "dmc"),
        session=session,
        credentials=("u", "t"),
        now=now,
        sleep=lambda _: None,
    )
    return json.loads((env / "dmc" / "330007" / "CURRENT.json").read_text("utf-8"))


def _delete_versions(folder: Path) -> None:
    for path in folder.glob("*"):
        path.unlink()


# --- H. Regresión Model D ------------------------------------------------------


def test_reproducibility_mode_keeps_model_d_fingerprint(monkeypatch):
    monkeypatch.setenv("SAPI_REPRODUCIBILITY_MODE", "1")
    result = svc.score_current_grid()
    assert len(result.cells) == 50
    assert result.cells[0].cell_id == "VP-001"
    assert round(result.cells[0].score, 12) == 0.131293368748
    assert _ranking_fingerprint(result) == MODEL_D_FINGERPRINT


_LOCAL_DATA = (
    svc.DMC_RAW_DIR / "dmc_historico_330007_2026-08.json"
).exists() and firms_source.FIRMS_BASELINE_CSV.exists()


@pytest.mark.skipif(
    not _LOCAL_DATA, reason="requiere data/raw y data/processed locales"
)
def test_operational_mode_without_current_keeps_model_d_fingerprint(monkeypatch):
    monkeypatch.setenv("SAPI_REPRODUCIBILITY_MODE", "0")
    assert not firms_source.FIRMS_CURRENT_POINTER.exists()
    assert not (DMC_STORE_DIR / "330007" / "CURRENT.json").exists()
    result = svc.score_current_grid()
    assert _ranking_fingerprint(result) == MODEL_D_FINGERPRINT
    files = result.scoring_inputs["dmc"]["files"]
    assert {f["origin"] for f in files} == {"legacy"}
    assert result.scoring_inputs["firms"]["origin"] == "baseline"


# --- A. TOCTOU FIRMS -----------------------------------------------------------


def _target_count(result) -> int:
    return next(
        c.historical_count for c in result.cells if c.cell_id == TARGET["cell_id"]
    )


def test_firms_pointer_switch_after_capture_does_not_affect_the_run(env):
    pointer_a = publish_firms(env, detections=0)
    inputs = svc.capture_scoring_inputs()
    assert inputs.firms_pointer_version == pointer_a["relative_path"]

    pointer_b = publish_firms(env, detections=3)  # CURRENT -> B
    (env / "firms" / "versions" / pointer_a["relative_path"]).unlink()  # A ya no existe

    result = svc.score_current_grid(inputs=inputs)

    assert result.scoring_inputs["firms"]["sha256"] == pointer_a["sha256"]
    fresh = svc.score_current_grid()
    assert fresh.scoring_inputs["firms"]["sha256"] == pointer_b["sha256"]
    assert (
        _target_count(fresh) == _target_count(result) + 1
    )  # B sí suma el arribo nuevo


# --- B. TOCTOU DMC -------------------------------------------------------------


def test_dmc_pointer_switch_after_capture_does_not_affect_the_run(env):
    now = datetime(2026, 9, 1, 7, tzinfo=timezone.utc)
    pointer_a = publish_dmc(
        env,
        {
            "2026-08": _readings("2026-08-31 23:00", "2026-08-31 23:45"),
            "2026-09": _readings("2026-09-01 02:00", "2026-09-01 06:00"),
        },
        now,
    )
    inputs = svc.capture_scoring_inputs()
    assert inputs.forecast_time == pd.Timestamp("2026-09-01 06:00", tz="UTC")
    assert inputs.dmc_pointer_version == pointer_a["manifest_sha256"]

    publish_dmc(
        env,
        {"2026-09": _readings("2026-09-01 02:00", "2026-09-01 12:00")},
        now + timedelta(hours=6),
    )
    _delete_versions(env / "dmc" / "330007" / "versions")  # ni A ni B quedan en disco

    result = svc.score_current_grid(inputs=inputs)

    assert result.forecast_time == pd.Timestamp("2026-09-01 06:00", tz="UTC")
    assert (
        result.scoring_inputs["dmc"]["pointer_version"] == pointer_a["manifest_sha256"]
    )
    with pytest.raises(
        svc.PrototypeUnavailableError, match="Meteorología DMC inválida"
    ):
        svc.capture_scoring_inputs()  # una captura nueva sí ve B (y sus archivos faltan)


# --- Invariante: después de capturar no se vuelve a tocar el disco ----------


def test_scoring_with_inputs_never_reads_disk_or_pointers(env, monkeypatch):
    publish_firms(env, detections=1)
    publish_dmc(
        env,
        {
            "2026-08": _readings("2026-08-31 23:00", "2026-08-31 23:45"),
            "2026-09": _readings("2026-09-01 02:00", "2026-09-01 06:00"),
        },
        datetime(2026, 9, 1, 7, tzinfo=timezone.utc),
    )
    inputs = svc.capture_scoring_inputs()
    expected = svc.score_current_grid(inputs=inputs)

    def _forbidden(*_args, **_kwargs):
        raise AssertionError("el scoring volvió a leer disco tras fijar ScoringInputs")

    for target, attr in [
        (Path, "read_bytes"),
        (Path, "read_text"),
        (Path, "open"),
        (Path, "glob"),
        (Path, "exists"),
        (pd, "read_csv"),
        (svc.joblib, "load"),
        (svc, "resolve_firms_source"),
        (svc, "pin_dmc"),
        (svc, "load_grid_topography"),
        (svc, "read_pinned"),
    ]:
        monkeypatch.setattr(target, attr, _forbidden)
    monkeypatch.setattr("builtins.open", _forbidden)

    result = svc.score_current_grid(inputs=inputs)

    assert _ranking_fingerprint(result) == _ranking_fingerprint(expected)
    assert result.inputs_fingerprint == inputs.fingerprint


# --- C. Tampering ----------------------------------------------------------------


def test_tampered_firms_version_aborts_capture(env):
    pointer = publish_firms(env, detections=1)
    version = env / "firms" / "versions" / pointer["relative_path"]
    version.write_bytes(version.read_bytes() + b"x\r\n")
    with pytest.raises(svc.PrototypeUnavailableError, match="sha256"):
        svc.capture_scoring_inputs()


def test_bytes_changed_between_resolution_and_read_abort(env, monkeypatch):
    """El puntero se valida (resolve) y el archivo cambia antes de fijar
    sus bytes: la captura aborta en vez de usar bytes no validados."""
    pointer = publish_firms(env, detections=1)
    version = env / "firms" / "versions" / pointer["relative_path"]
    real_resolve = svc.resolve_firms_source

    def resolve_then_tamper(**kwargs):
        source = real_resolve(**kwargs)
        version.write_bytes(
            version.read_bytes().replace(b"VIIRS_SNPP_NRT", b"XXXXX_XXXX_XXX", 1)
        )
        return source

    monkeypatch.setattr(svc, "resolve_firms_source", resolve_then_tamper)
    with pytest.raises(
        svc.PrototypeUnavailableError, match="cambió después de publicarse"
    ):
        svc.capture_scoring_inputs()


def test_modified_frozen_baseline_aborts_capture(env, monkeypatch):
    fake_baseline = env / "baseline.csv"
    fake_baseline.write_bytes(FIRMS_REPRODUCIBILITY_CSV.read_bytes() + b"x\r\n")
    monkeypatch.setattr(firms_source, "FIRMS_BASELINE_CSV", fake_baseline)
    with pytest.raises(svc.PrototypeUnavailableError, match="Histórico FIRMS inválido"):
        svc.capture_scoring_inputs()


def test_tampered_dmc_version_aborts_capture(env):
    pointer = publish_dmc(
        env,
        {
            "2026-08": _readings("2026-08-31 23:00", "2026-08-31 23:45"),
            "2026-09": _readings("2026-09-01 02:00", "2026-09-01 06:00"),
        },
        datetime(2026, 9, 1, 7, tzinfo=timezone.utc),
    )
    name = pointer["months"]["2026-09"]["relative_path"]
    version = env / "dmc" / "330007" / "versions" / name
    version.write_bytes(version.read_bytes().replace(b"15.0", b"45.0", 1))
    with pytest.raises(svc.PrototypeUnavailableError, match="sha256"):
        svc.capture_scoring_inputs()


def test_tampered_dmc_pointer_manifest_aborts_capture(env):
    publish_dmc(
        env,
        {
            "2026-08": _readings("2026-08-31 23:00", "2026-08-31 23:45"),
            "2026-09": _readings("2026-09-01 02:00", "2026-09-01 06:00"),
        },
        datetime(2026, 9, 1, 7, tzinfo=timezone.utc),
    )
    current = env / "dmc" / "330007" / "CURRENT.json"
    pointer = json.loads(current.read_text("utf-8"))
    pointer["months"].pop("2026-08")  # manifest_sha256 ya no calza
    current.write_text(json.dumps(pointer), encoding="utf-8")
    with pytest.raises(svc.PrototypeUnavailableError, match="manifest"):
        svc.capture_scoring_inputs()


# --- D. Modo reproducible ------------------------------------------------------


def test_reproducibility_mode_ignores_operational_pointers(env, monkeypatch):
    publish_firms(env, detections=3)
    publish_dmc(
        env,
        {
            "2026-08": _readings("2026-08-31 23:00", "2026-08-31 23:45"),
            "2026-09": _readings("2026-09-01 02:00", "2026-09-01 12:00"),
        },
        datetime(2026, 9, 1, 13, tzinfo=timezone.utc),
    )
    monkeypatch.setenv("SAPI_REPRODUCIBILITY_MODE", "1")

    inputs = svc.capture_scoring_inputs()
    result = svc.score_current_grid(inputs=inputs)

    assert inputs.reproducibility_mode is True
    assert (
        inputs.firms_origin == "reproducibility"
        and inputs.firms_pointer_version is None
    )
    assert inputs.dmc_pointer_version is None
    assert {f.origin for f in inputs.dmc_files} == {"reproducibility"}
    assert inputs.topography_origin == "reproducibility"
    assert inputs.forecast_time == pd.Timestamp("2026-09-01 00:00", tz="UTC")
    assert _ranking_fingerprint(result) == MODEL_D_FINGERPRINT


# --- E. Solapamiento legacy / versionado ---------------------------------------


def test_legacy_and_versioned_overlap_is_not_double_counted(env):
    # El almacén repite lecturas legacy (22:00 del 31-08 a 01:30 del 01-09)
    # con OTRA temperatura y agrega lecturas posteriores (01:45 a 03:00).
    publish_dmc(
        env,
        {
            "2026-08": _readings("2026-08-31 22:00", "2026-08-31 23:45", temp=40.0),
            "2026-09": _readings("2026-09-01 00:00", "2026-09-01 03:00", temp=40.0),
        },
        datetime(2026, 9, 1, 4, tzinfo=timezone.utc),
    )
    legacy_only = pin_dmc(
        "330007", legacy_dir=svc.REPRODUCIBILITY_DMC_DIR, store_dir=None
    )
    pinned = pin_dmc(
        "330007", legacy_dir=svc.REPRODUCIBILITY_DMC_DIR, store_dir=env / "dmc"
    )

    series = pinned.series
    assert not series["momento"].duplicated().any()
    assert pinned.legacy_coverage_end == LEGACY_END
    before = series[series["momento"] <= LEGACY_END].reset_index(drop=True)
    pd.testing.assert_frame_equal(
        before, legacy_only.series.reset_index(drop=True)
    )  # legacy gana
    after = series[series["momento"] > LEGACY_END]
    assert list(after["momento"].dt.strftime("%H:%M")) == [
        "01:45",
        "02:00",
        "02:15",
        "02:30",
        "02:45",
        "03:00",
    ]
    assert (after["temperatura"] == 40.0).all()
    assert len(series) == len(legacy_only.series) + 6


# --- F. Determinismo -----------------------------------------------------------


def test_same_inputs_give_same_fingerprint_and_result(env):
    publish_firms(env, detections=2)
    publish_dmc(
        env,
        {
            "2026-08": _readings("2026-08-31 23:00", "2026-08-31 23:45"),
            "2026-09": _readings("2026-09-01 02:00", "2026-09-01 06:00"),
        },
        datetime(2026, 9, 1, 7, tzinfo=timezone.utc),
    )
    first, second = svc.capture_scoring_inputs(), svc.capture_scoring_inputs()

    assert first.fingerprint == second.fingerprint
    assert first.manifest() == second.manifest()
    assert first.captured_at <= second.captured_at
    assert _ranking_fingerprint(
        svc.score_current_grid(inputs=first)
    ) == _ranking_fingerprint(svc.score_current_grid(inputs=second))


def test_fingerprint_changes_when_an_input_changes(env):
    before = svc.capture_scoring_inputs().fingerprint
    publish_firms(env, detections=1)
    assert svc.capture_scoring_inputs().fingerprint != before


# --- G. Metadata -----------------------------------------------------------------


def test_metadata_matches_exactly_the_inputs_used(env):
    firms_pointer = publish_firms(env, detections=1)
    dmc_pointer = publish_dmc(
        env,
        {
            "2026-08": _readings("2026-08-31 23:00", "2026-08-31 23:45"),
            "2026-09": _readings("2026-09-01 02:00", "2026-09-01 06:00"),
        },
        datetime(2026, 9, 1, 7, tzinfo=timezone.utc),
    )
    inputs = svc.capture_scoring_inputs()

    assert inputs.model_sha256 == _sha(svc.MODEL_PATH.read_bytes())
    assert inputs.model_version == "prototype_model_d_v1"
    assert inputs.firms_origin == "current"
    assert inputs.firms_sha256 == firms_pointer["sha256"]
    assert (inputs.firms_coverage_start, inputs.firms_coverage_end) == (
        date(2021, 8, 30),
        date(2026, 8, 31),
    )
    assert inputs.firms_lag_days == 1
    assert len(inputs.fires) == len(
        pd.read_csv(
            io.BytesIO(
                (
                    env / "firms" / "versions" / firms_pointer["relative_path"]
                ).read_bytes()
            )
        )
    )

    legacy = [f for f in inputs.dmc_files if f.origin == "legacy"]
    versioned = [f for f in inputs.dmc_files if f.origin == "versioned"]
    assert [f.name for f in legacy] == [
        "dmc_historico_330007_2026-08.json",
        "dmc_meteo_2026-09-01.json",
    ]
    for f in legacy:
        assert f.sha256 == _sha((svc.REPRODUCIBILITY_DMC_DIR / f.name).read_bytes())
    assert [f.sha256 for f in versioned] == [
        dmc_pointer["months"][m]["sha256"] for m in sorted(dmc_pointer["months"])
    ]
    assert inputs.dmc_pointer_version == dmc_pointer["manifest_sha256"]
    assert inputs.dmc_coverage_start == inputs.meteo_series["momento"].min()
    assert inputs.dmc_coverage_end == pd.Timestamp("2026-09-01 06:00", tz="UTC")
    assert inputs.weather_timestamp == inputs.meteo_row["meteo_actual_momento"]

    manifest = svc.score_current_grid(inputs=inputs).scoring_inputs
    assert manifest == inputs.manifest()
    assert manifest["firms"]["sha256"] == firms_pointer["sha256"]
    assert manifest["dmc"]["manifest_sha256"] == inputs.dmc_manifest_sha256
    assert "captured_at" not in manifest


def test_baseline_capture_records_frozen_hash(env):
    inputs = svc.capture_scoring_inputs()
    assert inputs.firms_origin == "baseline" and inputs.firms_pointer_version is None
    assert inputs.firms_sha256 == FIRMS_BASELINE_SHA256
    assert inputs.dmc_pointer_version is None
    assert {f.origin for f in inputs.dmc_files} == {"legacy"}


def test_missing_pinned_file_is_explicit(tmp_path):
    from src.inference.scoring_inputs import read_pinned

    with pytest.raises(PinnedInputError, match="No existe"):
        read_pinned(tmp_path / "x.csv", role="firms", origin="current")


def test_store_location_matches_dmc_writer():
    assert DMC_STORE_DIR == dmc.DmcPaths().root

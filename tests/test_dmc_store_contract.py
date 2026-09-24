"""Contrato del almacén DMC: writer (src/refresh/dmc_refresh.py) ↔ reader
(src/inference/scoring_inputs.py).

`scoring_inputs` NO importa los writers a propósito, así que duplica cuatro
invariantes del almacén: la raíz, la versión de esquema, la serialización del
manifest y la validación de punteros/versiones. Estos tests existen para que
un cambio en el writer rompa aquí si deja al reader incompatible, en vez de
romper en producción con `PrototypeUnavailableError`.

Ningún test toca red ni `data/`: se publica con el writer real y una API
simulada, siempre bajo `tmp_path`.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import src.inference.scoring_inputs as si
import src.refresh.dmc_refresh as dmc

STATION = dmc.DMC_STATION_ID
NOW = datetime(2026, 9, 23, 15, 0, tzinfo=timezone.utc)


def _readings(day: str, count: int) -> list[dict]:
    base = datetime.fromisoformat(day).replace(tzinfo=None)
    return [
        {
            "momento": (base.replace(hour=h)).strftime(dmc.MOMENTO_FORMAT),
            "temperatura": f"{18 + h} °C",
            "humedadRelativa": "72 %",
            "fuerzaDelViento": "8.5 kt",
            "direccionDelViento": "230 °",
        }
        for h in range(count)
    ]


def _payload(records: list[dict]) -> dict:
    return {
        "timezone": "UTC",
        "registros": len(records),
        "fechaCreacion": "23-09-2026 15:25",
        "datosEstaciones": {
            "estacion": {"codigoNacional": STATION, "nombreEstacion": "Rodelillo"},
            "datos": records,
        },
    }


@pytest.fixture
def published(tmp_path) -> tuple[dmc.DmcPaths, dict, Path]:
    """Publica dos meses con el writer real; devuelve (paths, puntero, legacy vacío)."""
    by_month = {
        "2026-08": _readings("2026-08-31", 3),
        "2026-09": _readings("2026-09-01", 5),
    }

    def get(url, params=None, timeout=None):
        year, month = url.rstrip("/").split("/")[-2:]
        response = MagicMock(status_code=200)
        response.json.return_value = _payload(by_month[f"{year}-{int(month):02d}"])
        return response

    session = MagicMock()
    session.get.side_effect = get
    paths = dmc.DmcPaths(root=tmp_path / "dmc")
    dmc.refresh(
        paths=paths,
        session=session,
        credentials=("u", "t"),
        now=NOW,
        sleep=lambda _: None,
    )
    legacy = tmp_path / "legacy_vacio"
    legacy.mkdir()
    return paths, json.loads(paths.pointer.read_text(encoding="utf-8")), legacy


def test_pointer_schema_version_is_shared():
    """Si el writer sube de esquema, el reader deja de aceptar sus punteros."""
    assert si.DMC_POINTER_SCHEMA_VERSION == dmc.POINTER_SCHEMA_VERSION


def test_store_root_is_shared():
    """El reader no importa `DmcPaths`: duplica la ruta por convención."""
    assert si.DMC_STORE_DIR == dmc.DmcPaths().root


def test_manifest_hash_is_computed_identically(published):
    """Dos implementaciones independientes del mismo hash de manifest."""
    _, pointer, _ = published
    months = pointer["months"]
    assert si._canonical_sha(months) == dmc._manifest_sha(months)
    assert si._canonical_sha(months) == pointer["manifest_sha256"]


def test_reader_consumes_what_the_writer_publishes(published):
    """Round-trip: nombres de versión, manifest y conteo de lecturas."""
    paths, pointer, legacy = published

    pin = si.pin_dmc(STATION, legacy_dir=legacy, store_dir=paths.root)

    assert pin.pointer_version == pointer["manifest_sha256"]
    assert {f.name for f in pin.files} == {
        entry["relative_path"] for entry in pointer["months"].values()
    }
    assert {f.origin for f in pin.files} == {"versioned"}
    assert len(pin.series) == pointer["record_count"]
    assert pin.legacy_coverage_end is None  # legacy vacío: entra todo el almacén


def _grid(start: str, count: int) -> list[dict]:
    """`count` lecturas cada 15 min desde `start` (mismo mes)."""
    base = datetime.fromisoformat(start)
    return [
        {
            "momento": (base + timedelta(minutes=15 * i)).strftime(dmc.MOMENTO_FORMAT),
            "temperatura": f"{18 + i % 7} °C",
            "humedadRelativa": "72 %",
            "fuerzaDelViento": "8.5 kt",
            "direccionDelViento": "230 °",
        }
        for i in range(count)
    ]


def test_record_count_and_coverage_are_the_valid_rows_the_reader_consumes(tmp_path):
    """Semántica fijada del puntero v1 con la política de 1 % de nulos.

    100 lecturas por mes y exactamente 1 `null` por mes (= 1 %, se publica),
    puesto en el borde de la cobertura: la primera lectura de agosto y la
    última de septiembre. El writer debe publicar `record_count` = lecturas
    válidas y `coverage_*` = primer/último momento válido, y el reader debe
    fijar exactamente esas lecturas.
    """
    aug = _grid("2026-08-30T00:00", 100)
    sep = _grid("2026-09-01T00:00", 100)
    aug[0]["temperatura"] = None
    sep[-1]["humedadRelativa"] = None
    by_month = {"2026-08": aug, "2026-09": sep}

    def get(url, params=None, timeout=None):
        year, month = url.rstrip("/").split("/")[-2:]
        response = MagicMock(status_code=200)
        response.json.return_value = _payload(by_month[f"{year}-{int(month):02d}"])
        return response

    session = MagicMock()
    session.get.side_effect = get
    paths = dmc.DmcPaths(root=tmp_path / "dmc")
    outcome = dmc.refresh(
        paths=paths,
        session=session,
        credentials=("u", "t"),
        now=NOW,
        sleep=lambda _: None,
    )
    legacy = tmp_path / "legacy_vacio"
    legacy.mkdir()
    pointer = json.loads(paths.pointer.read_text(encoding="utf-8"))

    # writer: publica y describe solo lo válido
    assert outcome.status == "published"
    assert outcome.row_quality["2026-08"]["null_rows"] == 1
    assert outcome.row_quality["2026-09"]["discard_rate"] == 0.01
    assert pointer["schema_version"] == 1 == si.DMC_POINTER_SCHEMA_VERSION
    assert pointer["months"]["2026-08"]["record_count"] == 99
    assert pointer["months"]["2026-09"]["record_count"] == 99
    assert pointer["record_count"] == 198
    assert pointer["coverage_start"] == aug[1]["momento"]
    assert pointer["coverage_end"] == sep[-2]["momento"]

    # reader: fija exactamente record_count lecturas y la misma cobertura
    pin = si.pin_dmc(STATION, legacy_dir=legacy, store_dir=paths.root)
    assert len(pin.series) == pointer["record_count"]
    moments = pin.series["momento"]
    assert moments.min().strftime(dmc.MOMENTO_FORMAT) == pointer["coverage_start"]
    assert moments.max().strftime(dmc.MOMENTO_FORMAT) == pointer["coverage_end"]


def test_both_sides_reject_an_unknown_schema(published):
    """Simetría de rechazo: ninguno acepta un esquema que no conoce."""
    paths, pointer, legacy = published
    paths.pointer.write_text(
        json.dumps(dict(pointer, schema_version=dmc.POINTER_SCHEMA_VERSION + 1)),
        encoding="utf-8",
    )

    with pytest.raises(dmc.DmcRefreshError) as writer_err:
        dmc.read_current(paths)
    with pytest.raises(si.PinnedInputError):
        si.pin_dmc(STATION, legacy_dir=legacy, store_dir=paths.root)

    assert writer_err.value.exit_code == dmc.EXIT_DATA

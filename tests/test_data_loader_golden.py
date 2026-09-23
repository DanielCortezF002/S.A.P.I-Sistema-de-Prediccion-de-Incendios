"""Test de oro de los loaders DMC/FIRMS que alimentan al Modelo D.

Los valores esperados se calcularon el 22-09-2026 con el código ANTERIOR a
la centralización de FIRMS (firms_source.py) y a la defensa de formato de
parse_dmc_json, sobre los snapshots versionados en git
(artifacts/hito1/reproducibility/). Si alguno cambia, cambió lo que el
Modelo D recibe como entrada -- eso exige revisión científica, no
actualizar el número.

La serialización canónica (isoformat + repr de floats, fila por fila) no
depende de la versión de pandas, a diferencia de hash_pandas_object.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from src.procesamiento.episodes import assign_episodes, first_arrival_by_cell
from src.procesamiento.firms_source import (
    FIRMS_BASELINE_CSV,
    FIRMS_REPRODUCIBILITY_CSV,
    resolve_firms_source,
)
from src.procesamiento.raw_parser import parse_dmc_json
from src.procesamiento.regional_meteo import load_regional_meteo_series

REPO_ROOT = Path(__file__).resolve().parent.parent
REPRO_DIR = REPO_ROOT / "artifacts" / "hito1" / "reproducibility"
REPRO_DMC_DIR = REPRO_DIR / "dmc"
MANIFEST = REPRO_DIR / "manifest.json"

# Publicado de forma independiente en artifacts/hito1/reproducibility/manifest.json
# (cadena_de_proveniencia.1_nasa_firms) el 09-09-2026.
GOLDEN_FIRMS_SHA256 = "a9a85db4431b3e54f936b724e4de5a7fbb0cc19f5721f5e1a344a192bf9bb271"
GOLDEN_METEO = {
    "rows": 3626,
    "min": "2026-08-01T00:00:00+00:00",
    "max": "2026-09-01T01:30:00+00:00",
    "sha256": "418723e6bdbdd396bb4eaf4a1ee741eae045596c55858337e7617ff6e8d681a7",
}
GOLDEN_ARRIVALS = {
    "rows": 128,
    "cells": 39,
    "sha256": "4066c228f81a8323e27c584faaecec39777d9a970bdbf66bc4e5c52ac1ff46b6",
}

pytestmark = pytest.mark.skipif(
    not (REPRO_DMC_DIR.is_dir() and FIRMS_REPRODUCIBILITY_CSV.exists()),
    reason="Requiere los snapshots versionados de artifacts/hito1/reproducibility/.",
)


def _canonical_meteo_sha(series: pd.DataFrame) -> str:
    digest = hashlib.sha256()
    for row in series.itertuples(index=False):
        digest.update(
            f"{row.station_id}|{row.momento.isoformat()}|{row.temperatura!r}|"
            f"{row.humedad_relativa!r}|{row.velocidad_viento_kmh!r}\n".encode()
        )
    return digest.hexdigest()


def _canonical_arrivals_sha(arrivals: pd.DataFrame) -> str:
    digest = hashlib.sha256()
    for row in arrivals.sort_values(["cell_id", "first_arrival"]).itertuples(
        index=False
    ):
        digest.update(
            f"{row.cell_id}|{pd.Timestamp(row.first_arrival).isoformat()}\n".encode()
        )
    return digest.hexdigest()


def test_golden_firms_hash_matches_published_manifest() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    published = manifest["cadena_de_proveniencia"]["1_nasa_firms"][
        "snapshot_reproducibilidad_R3"
    ]["sha256"]
    assert published == GOLDEN_FIRMS_SHA256


def test_reproducibility_firms_source_is_golden_file() -> None:
    source = resolve_firms_source(reproducibility=True)
    assert source.path == FIRMS_REPRODUCIBILITY_CSV
    assert hashlib.sha256(source.path.read_bytes()).hexdigest() == GOLDEN_FIRMS_SHA256


@pytest.mark.skipif(
    not FIRMS_BASELINE_CSV.exists(), reason="data/processed/ no versionado en git."
)
def test_operational_baseline_is_byte_identical_to_snapshot() -> None:
    assert (
        hashlib.sha256(FIRMS_BASELINE_CSV.read_bytes()).hexdigest()
        == GOLDEN_FIRMS_SHA256
    )


def test_golden_first_arrivals_from_firms() -> None:
    fires = pd.read_csv(resolve_firms_source(reproducibility=True).path)
    arrivals = first_arrival_by_cell(assign_episodes(fires))
    assert len(arrivals) == GOLDEN_ARRIVALS["rows"]
    assert arrivals["cell_id"].nunique() == GOLDEN_ARRIVALS["cells"]
    assert _canonical_arrivals_sha(arrivals) == GOLDEN_ARRIVALS["sha256"]


def test_golden_regional_meteo_series() -> None:
    series = load_regional_meteo_series("330007", raw_dir=REPRO_DMC_DIR)
    assert len(series) == GOLDEN_METEO["rows"]
    assert series["momento"].min().isoformat() == GOLDEN_METEO["min"]
    assert series["momento"].max().isoformat() == GOLDEN_METEO["max"]
    assert _canonical_meteo_sha(series) == GOLDEN_METEO["sha256"]


def test_format_guard_accepts_every_versioned_dmc_snapshot() -> None:
    files = sorted(REPRO_DMC_DIR.glob("*.json"))
    assert files
    for path in files:
        assert not parse_dmc_json(path).empty, path.name


_RAW_DMC_FILES = sorted((REPO_ROOT / "data" / "raw").glob("dmc_*.json"))


@pytest.mark.skipif(not _RAW_DMC_FILES, reason="data/raw/ no versionado en git.")
def test_format_guard_accepts_every_local_dmc_file() -> None:
    """Los archivos operacionales locales (no versionados) también deben
    pasar la defensa: el guard no puede rechazar datos reales existentes."""
    for path in _RAW_DMC_FILES:
        parse_dmc_json(path)

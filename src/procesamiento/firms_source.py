"""Resolución centralizada de la fuente NASA FIRMS.

Antes de este módulo, la ruta `data/processed/nasa_firms_2021-08-30_2026-08-30.csv`
estaba escrita a mano en `src/inference/prototype_service.py` y en seis
scripts de análisis. Este módulo es la única fuente de verdad sobre qué CSV
FIRMS se lee, y distingue dos usos que NO deben mezclarse:

- `FIRMS_BASELINE_CSV`: la línea base CONGELADA con la que se construyó
  `temporal_dataset_h6.parquet` y se entrenó/evaluó el Modelo D. Los
  scripts de dataset, experimentos y reportes la importan directamente --
  su resultado científico está atado a este archivo exacto y nunca deben
  seguir un puntero "vigente".
- `resolve_firms_source()`: lo que usa la INFERENCIA
  (`score_current_grid()`). Hoy devuelve la misma línea base; cuando exista
  un refresco incremental (Fase 2), podrá devolver una versión más nueva
  publicada mediante `data/processed/firms/CURRENT.json`.

Prioridad de `resolve_firms_source()`:
1. `SAPI_REPRODUCIBILITY_MODE=1` -> snapshot congelado del Hito 1
   (`artifacts/hito1/reproducibility/firms/`), sin cambios respecto a antes.
2. `CURRENT.json` presente -> la versión que apunta, SOLO si el puntero es
   válido, el archivo vive dentro de `data/processed/firms/versions/` y su
   sha256 coincide. Cualquier inconsistencia falla de forma explícita
   (`FirmsSourceError`), nunca cae en silencio a otra fuente.
3. Sin puntero -> `FIRMS_BASELINE_CSV`.

Este módulo no descarga nada, no llama a APIs y no escribe archivos.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]

FIRMS_BASELINE_CSV = (
    REPO_ROOT / "data" / "processed" / "nasa_firms_2021-08-30_2026-08-30.csv"
)
# Período SOLICITADO al backfill que generó la línea base (nombre del
# archivo y artifacts/hito1/reproducibility/manifest.json). No es la fecha
# de la última detección: "no hubo detecciones" y "no se consultó" son
# cosas distintas.
FIRMS_BASELINE_COVERAGE = (date(2021, 8, 30), date(2026, 8, 30))

# Mismo archivo que la línea base (mismo sha256, ver
# artifacts/hito1/reproducibility/manifest.json), versionado en git.
FIRMS_REPRODUCIBILITY_CSV = (
    REPO_ROOT
    / "artifacts"
    / "hito1"
    / "reproducibility"
    / "firms"
    / "nasa_firms_2021-08-30_2026-08-30.csv"
)

FIRMS_CURRENT_DIR = REPO_ROOT / "data" / "processed" / "firms"
FIRMS_CURRENT_POINTER = FIRMS_CURRENT_DIR / "CURRENT.json"
FIRMS_VERSIONS_DIR = FIRMS_CURRENT_DIR / "versions"
POINTER_SCHEMA_VERSION = 1

FirmsOrigin = Literal["reproducibility", "current", "baseline"]


class FirmsSourceError(RuntimeError):
    """El puntero FIRMS vigente existe pero es inválido o inconsistente."""


# Archivos FIRMS congelados que ningún writer puede tocar (SAPI-71): la línea
# base científica, su manifest de proveniencia (mismo `stem`, que es
# exactamente lo que `NasaFirmsBackfill.run()` escribiría para el período
# 2021-08-30..2026-08-30) y el snapshot del Hito 1 (mismo sha256).
FROZEN_FIRMS_PATHS: tuple[Path, ...] = (
    FIRMS_BASELINE_CSV,
    FIRMS_BASELINE_CSV.with_name(f"{FIRMS_BASELINE_CSV.stem}_manifest.json"),
    FIRMS_REPRODUCIBILITY_CSV,
)


class FrozenFirmsWriteError(RuntimeError):
    """Se intentó escribir sobre un archivo FIRMS congelado. Nunca se
    captura para seguir con otra ruta: la operación debe abortar."""


def _canonical(path: Path) -> str:
    return os.path.normcase(os.path.realpath(os.path.abspath(path)))


def is_frozen_firms_path(path: str | os.PathLike) -> bool:
    """True si `path` (relativa al cwd o absoluta, con `..`, symlinks o
    distinta capitalización en Windows) es uno de `FROZEN_FIRMS_PATHS`, o
    si ya existe y es el mismo archivo físico (hardlink)."""
    candidate = Path(path)
    canonical = _canonical(candidate)
    for frozen in FROZEN_FIRMS_PATHS:
        if canonical == _canonical(frozen):
            return True
        try:
            if (
                candidate.exists()
                and frozen.exists()
                and os.path.samefile(candidate, frozen)
            ):
                return True
        except OSError:
            continue
    return False


def ensure_writable_firms_path(path: str | os.PathLike) -> None:
    """Llamar ANTES de cualquier escritura (y de la red) sobre una salida
    FIRMS. Lanza `FrozenFirmsWriteError` si `path` es un archivo congelado;
    no escribe, no cambia la ruta y no ofrece alternativa."""
    if is_frozen_firms_path(path):
        raise FrozenFirmsWriteError(
            f"Escritura rechazada: {path} es un archivo FIRMS congelado "
            "(línea base científica de Model D, su manifest o el snapshot del "
            "Hito 1). No se escribió nada. Use otro destino."
        )


@dataclass(frozen=True)
class FirmsSource:
    path: Path
    origin: FirmsOrigin
    coverage_start: date
    coverage_end: date
    # Solo se conoce (y se verifica) para versiones publicadas vía puntero.
    sha256: Optional[str] = None


def reproducibility_mode_enabled() -> bool:
    """Se lee en cada llamada, nunca al importar (ver prototype_service)."""
    return os.getenv("SAPI_REPRODUCIBILITY_MODE") == "1"


def _sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve_pointer(pointer_path: Path, versions_dir: Path) -> FirmsSource:
    try:
        pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FirmsSourceError(
            f"Puntero FIRMS ilegible en {pointer_path.name}: {exc}"
        ) from exc

    if (
        not isinstance(pointer, dict)
        or pointer.get("schema_version") != POINTER_SCHEMA_VERSION
    ):
        raise FirmsSourceError(
            f"Puntero FIRMS con esquema no soportado en {pointer_path.name}."
        )

    try:
        relative = str(pointer["path"])
        expected_sha = str(pointer["sha256"])
        coverage_start = date.fromisoformat(pointer["coverage_start"])
        coverage_end = date.fromisoformat(pointer["coverage_end"])
    except (KeyError, TypeError, ValueError) as exc:
        raise FirmsSourceError(
            f"Puntero FIRMS incompleto en {pointer_path.name}: {exc}"
        ) from exc

    # El puntero solo puede apuntar dentro de versions/ -- nunca a la línea
    # base, a artifacts/ ni a una ruta arbitraria del filesystem.
    versions_root = versions_dir.resolve()
    target = (versions_root / relative).resolve()
    if target.parent != versions_root:
        raise FirmsSourceError(
            f"Puntero FIRMS fuera de {versions_dir.name}/: {relative!r}."
        )
    if not target.is_file():
        raise FirmsSourceError(
            f"El puntero FIRMS apunta a un archivo inexistente: {relative!r}."
        )
    if coverage_end < coverage_start:
        raise FirmsSourceError(
            "Puntero FIRMS con coverage_end anterior a coverage_start."
        )

    actual_sha = _sha256_of(target)
    if actual_sha != expected_sha:
        raise FirmsSourceError(
            f"sha256 de {relative!r} no coincide con el puntero FIRMS "
            f"(esperado {expected_sha[:12]}..., real {actual_sha[:12]}...)."
        )

    return FirmsSource(
        path=target,
        origin="current",
        coverage_start=coverage_start,
        coverage_end=coverage_end,
        sha256=actual_sha,
    )


def resolve_firms_source(
    *,
    reproducibility: Optional[bool] = None,
    pointer_path: Optional[Path] = None,
    versions_dir: Optional[Path] = None,
    baseline_csv: Optional[Path] = None,
) -> FirmsSource:
    """Fuente FIRMS que debe usar la inferencia. Los parámetros opcionales
    existen para tests; en uso normal se llama sin argumentos.

    No verifica que la línea base o el snapshot existan -- eso lo decide el
    llamador (el prototipo lanza `PrototypeUnavailableError` con un mensaje
    claro, igual que antes de este módulo).
    """
    if reproducibility is None:
        reproducibility = reproducibility_mode_enabled()
    if reproducibility:
        start, end = FIRMS_BASELINE_COVERAGE
        return FirmsSource(
            path=FIRMS_REPRODUCIBILITY_CSV,
            origin="reproducibility",
            coverage_start=start,
            coverage_end=end,
        )

    pointer_path = pointer_path or FIRMS_CURRENT_POINTER
    if pointer_path.exists():
        return _resolve_pointer(pointer_path, versions_dir or FIRMS_VERSIONS_DIR)

    start, end = FIRMS_BASELINE_COVERAGE
    return FirmsSource(
        path=baseline_csv or FIRMS_BASELINE_CSV,
        origin="baseline",
        coverage_start=start,
        coverage_end=end,
    )

"""Entradas fijadas de una corrida de scoring (SAPI-71 Fase B, anti-TOCTOU).

Cada archivo que usa una corrida (modelo, FIRMS, DMC y, en modo
reproducible, la topografía congelada) se lee UNA sola vez: sus bytes se
hashean y se parsean desde esa misma copia en memoria. Después de
construir `ScoringInputs`, el scoring no vuelve a abrir paths, a leer
`CURRENT.json` ni a listar directorios; un refresco que publique una
versión nueva a mitad de corrida no cambia nada, y un archivo cuyo hash no
coincide con lo declarado aborta la captura (`PinnedInputError`) en vez de
mezclar bytes de dos versiones.

DMC combina dos bloques (precedencia documentada en `pin_dmc`):
- legacy: `dmc_historico_*` / `dmc_meteo_*` de `data/raw/` (o el snapshot
  del Hito 1 en modo reproducible), historia congelada;
- versioned: el almacén de `src/refresh/dmc_refresh.py`
  (`data/processed/dmc/<estación>/CURRENT.json`), del que solo se toman
  lecturas POSTERIORES a la última lectura legacy.

Este módulo solo lee. No importa los writers de `src/refresh/`.
"""

from __future__ import annotations

import hashlib
import io
import json
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from src.config import DATA_PROCESSED_DIR
from src.procesamiento.firms_source import FirmsSource
from src.procesamiento.raw_parser import parse_dmc_bytes
from src.procesamiento.regional_meteo import regional_meteo_files, series_from_parsed

# Misma ubicación que `src.refresh.dmc_refresh.DmcPaths().root` (ver test).
DMC_STORE_DIR = DATA_PROCESSED_DIR / "dmc"
DMC_POINTER_SCHEMA_VERSION = 1


class PinnedInputError(RuntimeError):
    """Una entrada no existe, o sus bytes no son los que declaraba su
    puntero. La captura aborta; nunca se sigue con otra versión."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_sha(payload: Any) -> str:
    return sha256_bytes(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    )


@dataclass(frozen=True)
class PinnedFile:
    role: str  # "model" | "firms" | "dmc" | "topography"
    origin: str  # "model" | "baseline" | "current" | "reproducibility" | "legacy" | "versioned"
    name: str
    sha256: str
    size: int

    def as_dict(self) -> dict:
        return {
            "role": self.role,
            "origin": self.origin,
            "name": self.name,
            "sha256": self.sha256,
            "size": self.size,
        }


def read_pinned(
    path: Path, *, role: str, origin: str, expected_sha256: Optional[str] = None
) -> tuple[PinnedFile, bytes]:
    """Lee `path` una vez. Si se conoce el hash esperado y no coincide,
    lanza `PinnedInputError`: el archivo cambió desde que se declaró."""
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        raise PinnedInputError(f"No existe {role} en {path.name}.") from None
    digest = sha256_bytes(data)
    if expected_sha256 is not None and digest != expected_sha256:
        raise PinnedInputError(
            f"{role} {path.name}: sha256 {digest[:12]}... no coincide con el declarado "
            f"{expected_sha256[:12]}... (cambió después de publicarse)."
        )
    return PinnedFile(role, origin, path.name, digest, len(data)), data


# --- DMC ---------------------------------------------------------------------


@dataclass(frozen=True)
class DmcPin:
    files: tuple[PinnedFile, ...]
    series: pd.DataFrame = field(repr=False, compare=False)
    pointer_version: Optional[str]
    legacy_coverage_end: Optional[pd.Timestamp]

    @property
    def manifest_sha256(self) -> str:
        return _canonical_sha([f.as_dict() for f in self.files])


def _read_versioned_months(
    station_id: str, store_dir: Path
) -> tuple[list[PinnedFile], list[pd.DataFrame], Optional[str]]:
    station_dir = store_dir / station_id
    pointer_path = station_dir / "CURRENT.json"
    try:
        raw_pointer = (
            pointer_path.read_bytes()
        )  # el puntero también se lee una sola vez
    except FileNotFoundError:
        return [], [], None
    try:
        pointer = json.loads(raw_pointer.decode("utf-8"))
        months = pointer["months"]
        if pointer.get("schema_version") != DMC_POINTER_SCHEMA_VERSION:
            raise ValueError(f"schema_version {pointer.get('schema_version')!r}")
        if _canonical_sha(months) != pointer["manifest_sha256"]:
            raise ValueError("manifest_sha256 no coincide con sus meses")
    except (KeyError, TypeError, ValueError) as exc:
        raise PinnedInputError(f"Puntero DMC inválido: {exc}") from None
    files, frames = [], []
    for month in sorted(months):
        entry = months[month]
        name = str(entry["relative_path"])
        if Path(name).name != name:
            raise PinnedInputError(f"Puntero DMC fuera de versions/: {name!r}.")
        pinned, data = read_pinned(
            station_dir / "versions" / name,
            role="dmc",
            origin="versioned",
            expected_sha256=str(entry["sha256"]),
        )
        files.append(pinned)
        frames.append(parse_dmc_bytes(data, name))
    return files, frames, str(pointer["manifest_sha256"])


def pin_dmc(station_id: str, *, legacy_dir: Path, store_dir: Optional[Path]) -> DmcPin:
    """Serie DMC fijada.

    Precedencia legacy > versioned: el bloque legacy se usa completo (es la
    historia con la que se construyeron dataset y fingerprint). Del almacén
    versionado solo entran lecturas con `momento` estrictamente posterior a
    la última lectura legacy; una lectura del almacén con el mismo
    (estación, momento) que una legacy nunca se suma dos veces. Con
    `store_dir=None` (modo reproducible) el almacén ni se consulta.
    """
    files: list[PinnedFile] = []
    legacy_frames = []
    for path in regional_meteo_files(station_id, legacy_dir):
        pinned, data = read_pinned(
            path,
            role="dmc",
            origin="reproducibility" if store_dir is None else "legacy",
        )
        files.append(pinned)
        legacy_frames.append(parse_dmc_bytes(data, path.name))
    legacy = series_from_parsed(legacy_frames, station_id)
    legacy_end = legacy["momento"].max() if not legacy.empty else None

    pointer_version = None
    series = legacy
    if store_dir is not None:
        versioned_files, versioned_frames, pointer_version = _read_versioned_months(
            station_id, store_dir
        )
        files.extend(versioned_files)
        versioned = series_from_parsed(versioned_frames, station_id)
        if legacy_end is not None and not versioned.empty:
            versioned = versioned[versioned["momento"] > legacy_end]
        if not versioned.empty:
            series = (
                pd.concat([legacy, versioned], ignore_index=True)
                .sort_values("momento")
                .reset_index(drop=True)
            )
    return DmcPin(tuple(files), series, pointer_version, legacy_end)


# --- FIRMS -------------------------------------------------------------------


@dataclass(frozen=True)
class FirmsPin:
    file: PinnedFile
    source: FirmsSource
    fires: pd.DataFrame = field(repr=False, compare=False)

    @property
    def pointer_version(self) -> Optional[str]:
        return self.source.path.name if self.source.origin == "current" else None


def pin_firms(source: FirmsSource, *, expected_sha256: Optional[str]) -> FirmsPin:
    """Lee UNA vez el CSV ya resuelto y lo verifica contra el sha256 del
    puntero (versión publicada) o de la línea base congelada."""
    pinned, data = read_pinned(
        source.path,
        role="firms",
        origin=source.origin,
        expected_sha256=source.sha256 or expected_sha256,
    )
    return FirmsPin(pinned, source, pd.read_csv(io.BytesIO(data)))


# --- ScoringInputs -----------------------------------------------------------


@dataclass(frozen=True)
class ScoringInputs:
    """Todo lo que una corrida de scoring usa, fijado en `captured_at`.

    Los campos de metadata describen exactamente las entradas; los de
    payload (modelo, series, tablas) son las copias en memoria que usará
    el scoring y no participan de la igualdad ni del fingerprint.
    """

    captured_at: datetime
    reproducibility_mode: bool
    forecast_time: pd.Timestamp
    weather_timestamp: pd.Timestamp
    model: PinnedFile
    model_version: str
    firms: PinnedFile
    firms_coverage_start: date
    firms_coverage_end: date
    firms_lag_days: int
    firms_status: str
    firms_pointer_version: Optional[str]
    dmc_files: tuple[PinnedFile, ...]
    dmc_manifest_sha256: str
    dmc_coverage_start: pd.Timestamp
    dmc_coverage_end: pd.Timestamp
    dmc_pointer_version: Optional[str]
    topography_origin: str
    topography_sha256: str
    # --- payload en memoria (no se vuelve a leer de disco) ---
    model_object: Any = field(repr=False, compare=False)
    model_metadata: dict = field(repr=False, compare=False)
    meteo_series: pd.DataFrame = field(repr=False, compare=False)
    meteo_row: pd.Series = field(repr=False, compare=False)
    fires: pd.DataFrame = field(repr=False, compare=False)
    topography: pd.DataFrame = field(repr=False, compare=False)

    @property
    def model_sha256(self) -> str:
        return self.model.sha256

    @property
    def firms_sha256(self) -> str:
        return self.firms.sha256

    @property
    def firms_origin(self) -> str:
        return self.firms.origin

    def manifest(self) -> dict:
        """Descripción determinista de las entradas (sin `captured_at`)."""
        return {
            "reproducibility_mode": self.reproducibility_mode,
            "forecast_time": self.forecast_time.isoformat(),
            "weather_timestamp": self.weather_timestamp.isoformat(),
            "model": {**self.model.as_dict(), "model_version": self.model_version},
            "firms": {
                **self.firms.as_dict(),
                "coverage_start": self.firms_coverage_start.isoformat(),
                "coverage_end": self.firms_coverage_end.isoformat(),
                "lag_days": self.firms_lag_days,
                "status": self.firms_status,
                "pointer_version": self.firms_pointer_version,
            },
            "dmc": {
                "files": [f.as_dict() for f in self.dmc_files],
                "manifest_sha256": self.dmc_manifest_sha256,
                "coverage_start": self.dmc_coverage_start.isoformat(),
                "coverage_end": self.dmc_coverage_end.isoformat(),
                "pointer_version": self.dmc_pointer_version,
            },
            "topography": {
                "origin": self.topography_origin,
                "sha256": self.topography_sha256,
            },
        }

    @property
    def fingerprint(self) -> str:
        return _canonical_sha(self.manifest())


def topography_sha256(topography: pd.DataFrame) -> str:
    """Hash de la tabla topográfica efectivamente usada (índice cell_id)."""
    return sha256_bytes(topography.to_csv(lineterminator="\n").encode("utf-8"))

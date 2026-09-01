"""Backfill histórico de focos térmicos NASA FIRMS.

La API Area permite como máximo cinco días por solicitud. Este módulo divide
el período requerido en ventanas válidas, consulta SP y NRT según su
disponibilidad publicada y consolida ambas fuentes de forma idempotente.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import time
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Callable, Iterable

import pandas as pd
import requests

from src.config import DATA_PROCESSED_DIR, DATA_RAW_DIR, NASA_FIRMS_API_KEY, VALPARAISO_BBOX

FIRMS_API_BASE = "https://firms.modaps.eosdis.nasa.gov/api"
SP_SOURCE = "VIIRS_SNPP_SP"
NRT_SOURCE = "VIIRS_SNPP_NRT"
MAX_DAYS_PER_REQUEST = 5

_REQUIRED_COLUMNS = {
    "latitude",
    "longitude",
    "acq_date",
    "acq_time",
    "satellite",
    "instrument",
}
_DEDUPE_COLUMNS = [
    "latitude",
    "longitude",
    "acq_date",
    "acq_time",
    "satellite",
    "instrument",
]


@dataclass(frozen=True)
class Availability:
    """Rango temporal publicado por FIRMS para una fuente."""

    source: str
    min_date: date
    max_date: date


@dataclass(frozen=True)
class DateWindow:
    """Solicitud inclusiva de hasta cinco días."""

    source: str
    start_date: date
    end_date: date

    @property
    def day_range(self) -> int:
        return (self.end_date - self.start_date).days + 1


@dataclass(frozen=True)
class BackfillResult:
    """Resumen verificable de una ejecución."""

    requested_windows: int
    raw_records: int
    unique_records: int
    duplicates_removed: int
    consolidated_path: Path
    manifest_path: Path


def five_year_start(today: date) -> date:
    """Retorna la misma fecha cinco años atrás, incluyendo 29-feb."""

    try:
        return today.replace(year=today.year - 5)
    except ValueError:
        return today.replace(year=today.year - 5, day=28)


def split_windows(source: str, start_date: date, end_date: date) -> list[DateWindow]:
    """Divide un rango inclusivo en solicitudes FIRMS de máximo cinco días."""

    if end_date < start_date:
        return []

    windows: list[DateWindow] = []
    cursor = start_date
    while cursor <= end_date:
        window_end = min(cursor + timedelta(days=MAX_DAYS_PER_REQUEST - 1), end_date)
        windows.append(DateWindow(source, cursor, window_end))
        cursor = window_end + timedelta(days=1)
    return windows


def build_windows(
    start_date: date,
    end_date: date,
    availability: dict[str, Availability],
) -> list[DateWindow]:
    """Construye ventanas SP/NRT recortadas a la disponibilidad oficial.

    Los rangos se conservan para ambas fuentes si se solapan. La deduplicación
    posterior prioriza SP, que es el producto científico consolidado.
    """

    windows: list[DateWindow] = []
    for source in (SP_SOURCE, NRT_SOURCE):
        available = availability[source]
        source_start = max(start_date, available.min_date)
        source_end = min(end_date, available.max_date)
        windows.extend(split_windows(source, source_start, source_end))

    source_priority = {SP_SOURCE: 0, NRT_SOURCE: 1}
    return sorted(
        windows,
        key=lambda item: (item.start_date, source_priority[item.source]),
    )


def select_boundary_sample(windows: Iterable[DateWindow], limit: int = 4) -> list[DateWindow]:
    """Selecciona pocas ventanas alrededor de la transición SP/NRT."""

    if limit < 1:
        raise ValueError("limit debe ser mayor que cero")

    all_windows = list(windows)
    sp_windows = [window for window in all_windows if window.source == SP_SOURCE]
    nrt_windows = [window for window in all_windows if window.source == NRT_SOURCE]

    sp_count = min(len(sp_windows), (limit + 1) // 2)
    nrt_count = min(len(nrt_windows), limit - sp_count)
    selected = (
        (sp_windows[-sp_count:] if sp_count else [])
        + (nrt_windows[:nrt_count] if nrt_count else [])
    )

    if len(selected) < limit:
        selected_ids = set(selected)
        selected.extend(
            window for window in all_windows if window not in selected_ids
        )

    source_priority = {SP_SOURCE: 0, NRT_SOURCE: 1}
    return sorted(
        selected[:limit],
        key=lambda item: (item.start_date, source_priority[item.source]),
    )


def deduplicate_detections(data: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Elimina detecciones repetidas entre ventanas y entre SP/NRT.

    Una detección se identifica por sensor, instante y coordenadas. Si existe
    en ambos productos se conserva SP.
    """

    if data.empty:
        return data.copy(), 0

    missing = _REQUIRED_COLUMNS.difference(data.columns)
    if missing:
        raise ValueError(f"CSV FIRMS sin columnas requeridas: {sorted(missing)}")

    normalized = data.copy()
    normalized["_source_priority"] = (
        normalized["firms_source"].map({SP_SOURCE: 0, NRT_SOURCE: 1}).fillna(2)
    )
    normalized["_latitude_key"] = pd.to_numeric(
        normalized["latitude"], errors="coerce"
    ).round(5)
    normalized["_longitude_key"] = pd.to_numeric(
        normalized["longitude"], errors="coerce"
    ).round(5)
    normalized["_time_key"] = (
        normalized["acq_time"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(4)
    )

    dedupe_keys = [
        "_latitude_key",
        "_longitude_key",
        "acq_date",
        "_time_key",
        "satellite",
        "instrument",
    ]
    normalized = normalized.sort_values("_source_priority", kind="stable")
    before = len(normalized)
    normalized = normalized.drop_duplicates(subset=dedupe_keys, keep="first")
    removed = before - len(normalized)

    helper_columns = [
        "_source_priority",
        "_latitude_key",
        "_longitude_key",
        "_time_key",
    ]
    return normalized.drop(columns=helper_columns).reset_index(drop=True), removed


class NasaFirmsBackfill:
    """Cliente acotable para backfill histórico VIIRS S-NPP."""

    def __init__(
        self,
        map_key: str = NASA_FIRMS_API_KEY,
        raw_dir: Path | None = None,
        processed_dir: Path | None = None,
        request_delay_seconds: float = 0.25,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        if not map_key:
            raise ValueError("NASA_FIRMS_API_KEY no configurada")
        if request_delay_seconds < 0:
            raise ValueError("request_delay_seconds no puede ser negativo")

        self.map_key = map_key
        self.raw_dir = raw_dir or DATA_RAW_DIR / "nasa_firms_backfill"
        self.processed_dir = processed_dir or DATA_PROCESSED_DIR
        self.request_delay_seconds = request_delay_seconds
        self.sleep_fn = sleep_fn
        self.session = requests.Session()

    @property
    def area(self) -> str:
        """Bounding box FIRMS en orden west,south,east,north."""

        return (
            f"{VALPARAISO_BBOX['min_lon']},{VALPARAISO_BBOX['min_lat']},"
            f"{VALPARAISO_BBOX['max_lon']},{VALPARAISO_BBOX['max_lat']}"
        )

    def _get_with_retry(self, url: str) -> requests.Response:
        """GET con backoff y respeto de Retry-After para 429."""

        last_error: Exception | None = None
        for attempt in range(4):
            try:
                response = self.session.get(url, timeout=60)
                if response.status_code == 429:
                    retry_after = float(response.headers.get("Retry-After", 10))
                    self.sleep_fn(max(retry_after, 2**attempt))
                    continue
                response.raise_for_status()
                return response
            except requests.RequestException as exc:
                last_error = exc
                if attempt < 3:
                    self.sleep_fn(2**attempt)

        raise RuntimeError("NASA FIRMS no respondió después de 4 intentos") from last_error

    def fetch_availability(self) -> dict[str, Availability]:
        """Consulta límites SP y NRT publicados por FIRMS."""

        url = f"{FIRMS_API_BASE}/data_availability/csv/{self.map_key}/all"
        response = self._get_with_retry(url)
        rows = csv.DictReader(io.StringIO(response.text))
        availability: dict[str, Availability] = {}
        for row in rows:
            source = row.get("data_id", "")
            if source in {SP_SOURCE, NRT_SOURCE}:
                availability[source] = Availability(
                    source=source,
                    min_date=date.fromisoformat(row["min_date"]),
                    max_date=date.fromisoformat(row["max_date"]),
                )

        missing = {SP_SOURCE, NRT_SOURCE}.difference(availability)
        if missing:
            raise ValueError(f"Disponibilidad FIRMS incompleta: {sorted(missing)}")
        return availability

    def window_url(self, window: DateWindow) -> str:
        """Construye la URL posicional oficial para una ventana."""

        if not 1 <= window.day_range <= MAX_DAYS_PER_REQUEST:
            raise ValueError("FIRMS DAY_RANGE debe estar entre 1 y 5")
        return (
            f"{FIRMS_API_BASE}/area/csv/{self.map_key}/{window.source}/"
            f"{self.area}/{window.day_range}/{window.start_date.isoformat()}"
        )

    def download_window(self, window: DateWindow) -> tuple[Path, pd.DataFrame]:
        """Descarga y conserva sin modificar el CSV de una ventana."""

        response = self._get_with_retry(self.window_url(window))
        frame = pd.read_csv(io.StringIO(response.text))
        missing = _REQUIRED_COLUMNS.difference(frame.columns)
        if missing:
            raise ValueError(f"Respuesta FIRMS inválida: faltan {sorted(missing)}")

        source_dir = self.raw_dir / window.source
        source_dir.mkdir(parents=True, exist_ok=True)
        raw_path = source_dir / (
            f"{window.start_date.isoformat()}_{window.end_date.isoformat()}.csv"
        )
        raw_path.write_text(response.text, encoding="utf-8")

        frame["firms_source"] = window.source
        frame["request_start_date"] = window.start_date.isoformat()
        return raw_path, frame

    def run(self, windows: Iterable[DateWindow]) -> BackfillResult:
        """Ejecuta exclusivamente las ventanas recibidas y consolida."""

        selected = list(windows)
        if not selected:
            raise ValueError("No hay ventanas FIRMS para ejecutar")

        frames: list[pd.DataFrame] = []
        raw_files: list[str] = []
        for index, window in enumerate(selected):
            raw_path, frame = self.download_window(window)
            raw_files.append(str(raw_path))
            frames.append(frame)
            if index < len(selected) - 1 and self.request_delay_seconds:
                self.sleep_fn(self.request_delay_seconds)

        combined = pd.concat(frames, ignore_index=True)
        deduplicated, removed = deduplicate_detections(combined)
        deduplicated = deduplicated.sort_values(
            ["acq_date", "acq_time", "latitude", "longitude"],
            kind="stable",
        ).reset_index(drop=True)

        self.processed_dir.mkdir(parents=True, exist_ok=True)
        first_date = min(window.start_date for window in selected)
        last_date = max(window.end_date for window in selected)
        stem = f"nasa_firms_{first_date.isoformat()}_{last_date.isoformat()}"
        consolidated_path = self.processed_dir / f"{stem}.csv"
        manifest_path = self.processed_dir / f"{stem}_manifest.json"
        deduplicated.to_csv(consolidated_path, index=False)

        checksum = hashlib.sha256(consolidated_path.read_bytes()).hexdigest()
        manifest = {
            "requested_windows": len(selected),
            "request_delay_seconds": self.request_delay_seconds,
            "raw_records": len(combined),
            "unique_records": len(deduplicated),
            "duplicates_removed": removed,
            "min_detection_date": (
                str(deduplicated["acq_date"].min()) if not deduplicated.empty else None
            ),
            "max_detection_date": (
                str(deduplicated["acq_date"].max()) if not deduplicated.empty else None
            ),
            "records_by_source": {
                str(key): int(value)
                for key, value in deduplicated["firms_source"].value_counts().items()
            },
            "raw_files": raw_files,
            "sha256": checksum,
        }
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return BackfillResult(
            requested_windows=len(selected),
            raw_records=len(combined),
            unique_records=len(deduplicated),
            duplicates_removed=removed,
            consolidated_path=consolidated_path,
            manifest_path=manifest_path,
        )

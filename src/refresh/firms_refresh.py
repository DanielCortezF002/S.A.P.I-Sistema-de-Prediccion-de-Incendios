"""Refresco FIRMS manual, versionado, atómico e idempotente (SAPI-71 Fase B).

    python -m src.refresh.firms_refresh refresh [--break-stale-lock]
    python -m src.refresh.firms_refresh status
    python -m src.refresh.firms_refresh rollback --to <archivo.csv | baseline>
    python -m src.refresh.firms_refresh cleanup [--keep N] [--grace-hours H] [--apply]

Cada versión nueva = bytes EXACTOS de la versión vigente (la línea base
congelada la primera vez, verificada por sha256) + detecciones con
`acq_date` estrictamente posterior a su `coverage_end`. Nunca reescribe
filas previas: `assign_episodes` recorre las detecciones en orden temporal,
así que agregar solo días posteriores deja idénticos los arribos (y las
features) de cualquier T ya cubierto. La reconciliación SP/NRT de días ya
publicados queda fuera: sería un "rebase" explícito, no un refresco.

Orden de publicación: versión inmutable (temp + fsync + os.replace) ->
re-lectura y verificación -> sidecar `<versión>.json` -> `CURRENT.json`
atómico -> línea en `pointer_history.jsonl`. Un fallo antes del último
paso deja `CURRENT.json` intacto.

Códigos de salida: 0 publicado / al día, 2 uso, 65 datos inválidos,
69 red no disponible, 75 bloqueado por otro refresco, 78 sin credenciales.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional, Sequence

import pandas as pd

from src.config import DATA_RAW_DIR, NASA_FIRMS_API_KEY
from src.ingesta.nasa_firms_backfill import (
    NasaFirmsBackfill,
    build_windows,
    deduplicate_detections,
)
from src.procesamiento.firms_source import (
    FIRMS_BASELINE_CSV,
    FIRMS_BASELINE_SHA256,
    FIRMS_CURRENT_POINTER,
    FIRMS_VERSIONS_DIR,
    POINTER_SCHEMA_VERSION,
    FirmsSourceError,
    FrozenFirmsWriteError,
    ensure_writable_firms_path,
    resolve_firms_source,
)
from src.refresh.atomic import (
    ImmutableVersionError,
    append_jsonl,
    atomic_write_json,
    sha256_bytes,
    write_immutable,
)
from src.refresh.lock import RefreshLockedError, refresh_lock
from src.refresh.redact import redact

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_DATA = 65
EXIT_NETWORK = 69
EXIT_LOCKED = 75
EXIT_CONFIG = 78

GENERATOR = "src.refresh.firms_refresh"
RAW_REFRESH_DIR = DATA_RAW_DIR / "firms_refresh"


class FirmsRefreshError(RuntimeError):
    def __init__(self, message: str, exit_code: int) -> None:
        super().__init__(message)
        self.exit_code = exit_code


@dataclass(frozen=True)
class FirmsPaths:
    """Rutas inyectables para tests; por defecto, las de producción."""

    pointer: Path = FIRMS_CURRENT_POINTER
    versions_dir: Path = FIRMS_VERSIONS_DIR
    baseline_csv: Path = FIRMS_BASELINE_CSV
    baseline_sha256: str = FIRMS_BASELINE_SHA256
    raw_dir: Path = RAW_REFRESH_DIR

    @property
    def lock(self) -> Path:
        return self.pointer.parent / ".refresh.lock"

    @property
    def history(self) -> Path:
        return self.pointer.parent / "pointer_history.jsonl"


@dataclass
class RefreshOutcome:
    status: str  # "published" | "up_to_date"
    coverage_start: date
    coverage_end: date
    new_rows: int = 0
    pointer: Optional[dict] = None
    detail: dict = field(default_factory=dict)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --- Base vigente ------------------------------------------------------------


@dataclass(frozen=True)
class _Base:
    origin: str
    relative_path: Optional[str]
    data: bytes
    sha256: str
    coverage_start: date
    coverage_end: date


def _load_base(paths: FirmsPaths) -> _Base:
    """Lee UNA vez los bytes de la versión vigente y los verifica."""
    try:
        source = resolve_firms_source(
            reproducibility=False,
            pointer_path=paths.pointer,
            versions_dir=paths.versions_dir,
            baseline_csv=paths.baseline_csv,
        )
    except FirmsSourceError as exc:
        raise FirmsRefreshError(
            f"Puntero FIRMS vigente inválido: {exc}", EXIT_DATA
        ) from exc
    try:
        data = source.path.read_bytes()
    except OSError as exc:
        raise FirmsRefreshError(
            f"No se pudo leer la base FIRMS: {exc}", EXIT_DATA
        ) from exc
    actual = sha256_bytes(data)
    expected = source.sha256 if source.origin == "current" else paths.baseline_sha256
    if actual != expected:
        raise FirmsRefreshError(
            f"sha256 de la base FIRMS ({source.origin}) no coincide: "
            f"esperado {expected[:12]}..., real {actual[:12]}...",
            EXIT_DATA,
        )
    return _Base(
        origin=source.origin,
        relative_path=source.path.name if source.origin == "current" else None,
        data=data,
        sha256=actual,
        coverage_start=source.coverage_start,
        coverage_end=source.coverage_end,
    )


# --- Construcción de la versión ---------------------------------------------


def _header_and_terminator(data: bytes) -> tuple[list[str], str]:
    first, sep, _ = data.partition(b"\n")
    if not sep:
        raise FirmsRefreshError("La base FIRMS no tiene cabecera CSV.", EXIT_DATA)
    terminator = "\r\n" if first.endswith(b"\r") else "\n"
    header = first.rstrip(b"\r").decode("utf-8").split(",")
    if not data.endswith(terminator.encode()):
        raise FirmsRefreshError(
            "La base FIRMS no termina en salto de línea.", EXIT_DATA
        )
    return header, terminator


def build_version_bytes(
    base: bytes, new_rows: pd.DataFrame, previous_end: date, new_end: date
) -> tuple[bytes, int]:
    """Base intacta + filas nuevas con `previous_end < acq_date <= new_end`,
    serializadas con las columnas y el fin de línea de la base."""
    header, terminator = _header_and_terminator(base)
    if new_rows.empty:
        return base, 0
    missing = [col for col in header if col not in new_rows.columns]
    if missing:
        raise FirmsRefreshError(
            f"Respuesta FIRMS sin columnas de la base: {missing}", EXIT_DATA
        )
    acq = pd.to_datetime(new_rows["acq_date"], errors="coerce").dt.date
    outside = new_rows[acq.isna() | (acq <= previous_end) | (acq > new_end)]
    if not outside.empty:
        raise FirmsRefreshError(
            f"{len(outside)} detecciones fuera de ({previous_end}, {new_end}]: "
            "no se reescriben días ya publicados.",
            EXIT_DATA,
        )
    ordered = new_rows.sort_values(
        ["acq_date", "acq_time", "latitude", "longitude"], kind="stable"
    )
    body = ordered.to_csv(
        index=False, header=False, columns=header, lineterminator=terminator
    ).encode("utf-8")
    data = base + body
    parsed = pd.read_csv(io.BytesIO(data))
    base_rows = len(pd.read_csv(io.BytesIO(base)))
    if list(parsed.columns) != header or len(parsed) != base_rows + len(ordered):
        raise FirmsRefreshError("La versión construida no se relee íntegra.", EXIT_DATA)
    return data, len(ordered)


def _download_new_rows(
    client: NasaFirmsBackfill, start: date, end: date
) -> tuple[pd.DataFrame, date, list[str]]:
    """Descarga (start..end] recortado a la disponibilidad publicada.
    Devuelve filas deduplicadas, el último día efectivamente consultado y
    los CSV crudos guardados como evidencia."""
    availability = client.fetch_availability()
    available_end = max(item.max_date for item in availability.values())
    end = min(end, available_end)
    if end < start:
        return pd.DataFrame(), start - timedelta(days=1), []
    windows = build_windows(start, end, availability)
    covered = {
        window.start_date + timedelta(days=offset)
        for window in windows
        for offset in range(window.day_range)
    }
    missing_days = [
        start + timedelta(days=offset)
        for offset in range((end - start).days + 1)
        if start + timedelta(days=offset) not in covered
    ]
    if missing_days:
        raise FirmsRefreshError(
            f"FIRMS no publica datos para {len(missing_days)} día(s) del rango "
            f"(primero {missing_days[0]}): la cobertura no puede tener huecos.",
            EXIT_DATA,
        )
    frames, raw_files = [], []
    for index, window in enumerate(windows):
        raw_path, frame = client.download_window(window)
        raw_files.append(str(raw_path))
        frames.append(frame)
        if index < len(windows) - 1 and client.request_delay_seconds:
            client.sleep_fn(client.request_delay_seconds)
    combined = pd.concat(frames, ignore_index=True)
    deduplicated, _ = deduplicate_detections(combined)
    return deduplicated, end, raw_files


# --- Publicación -------------------------------------------------------------


def _version_name(start: date, end: date, sha: str) -> str:
    return f"firms_{start.isoformat()}_{end.isoformat()}_{sha[:12]}.csv"


def _sidecar(paths: FirmsPaths, name: str) -> Path:
    return paths.versions_dir / f"{Path(name).stem}.json"


def _publish(paths: FirmsPaths, pointer: dict, event: str) -> None:
    atomic_write_json(paths.pointer, pointer)
    append_jsonl(
        paths.history,
        {"event": event, "at": _utcnow().isoformat(), **pointer},
    )


def refresh(
    *,
    paths: FirmsPaths = FirmsPaths(),
    client_factory: Optional[Callable[[Path], NasaFirmsBackfill]] = None,
    map_key: Optional[str] = None,
    today: Optional[date] = None,
    break_stale: bool = False,
) -> RefreshOutcome:
    if map_key is None:
        map_key = NASA_FIRMS_API_KEY  # leída al llamar, no al importar
    if not map_key:
        raise FirmsRefreshError(
            "NASA_FIRMS_API_KEY no configurada: se inyecta en runtime (.env / env_file), "
            "nunca en la imagen.",
            EXIT_CONFIG,
        )
    today = today or _utcnow().date()
    # El día en curso está incompleto: la cobertura llega hasta ayer (UTC).
    target_end = today - timedelta(days=1)
    try:
        with refresh_lock(paths.lock, break_stale=break_stale):
            base = _load_base(paths)
            start = base.coverage_end + timedelta(days=1)
            if start > target_end:
                return RefreshOutcome(
                    "up_to_date", base.coverage_start, base.coverage_end
                )
            run_id = _utcnow().strftime("%Y%m%dT%H%M%SZ")
            factory = client_factory or (
                lambda raw_dir: NasaFirmsBackfill(map_key=map_key, raw_dir=raw_dir)
            )
            client = factory(paths.raw_dir / run_id)
            try:
                new_rows, new_end, raw_files = _download_new_rows(
                    client, start, target_end
                )
            except RuntimeError as exc:  # _get_with_retry agotado
                raise FirmsRefreshError(
                    f"NASA FIRMS no disponible: {redact(exc, [map_key])}", EXIT_NETWORK
                ) from None
            except (ValueError, pd.errors.EmptyDataError, pd.errors.ParserError) as exc:
                raise FirmsRefreshError(
                    f"Respuesta FIRMS inválida: {redact(exc, [map_key])}", EXIT_DATA
                ) from None
            if new_end < start:
                return RefreshOutcome(
                    "up_to_date",
                    base.coverage_start,
                    base.coverage_end,
                    detail={"reason": "FIRMS aún no publica días posteriores"},
                )
            data, added = build_version_bytes(
                base.data, new_rows, base.coverage_end, new_end
            )
            sha = sha256_bytes(data)
            name = _version_name(base.coverage_start, new_end, sha)
            version_path = paths.versions_dir / name
            try:
                ensure_writable_firms_path(version_path)
                write_immutable(version_path, data)
            except (FrozenFirmsWriteError, ImmutableVersionError) as exc:
                raise FirmsRefreshError(str(exc), EXIT_DATA) from None
            pointer = {
                "schema_version": POINTER_SCHEMA_VERSION,
                "source": "firms",
                "relative_path": name,
                "sha256": sha,
                "coverage_start": base.coverage_start.isoformat(),
                "coverage_end": new_end.isoformat(),
                "created_at": _utcnow().isoformat(),
                "row_count": len(pd.read_csv(io.BytesIO(data))),
                "new_rows": added,
                "base_sha256": base.sha256,
                "base_origin": base.origin,
                "raw_files": raw_files,
                "generator": GENERATOR,
            }
            atomic_write_json(_sidecar(paths, name), pointer)
            _publish(paths, pointer, "publish")
            return RefreshOutcome(
                "published",
                base.coverage_start,
                new_end,
                new_rows=added,
                pointer=pointer,
            )
    except RefreshLockedError as exc:
        raise FirmsRefreshError(str(exc), EXIT_LOCKED) from None


def rollback(
    to: str, *, paths: FirmsPaths = FirmsPaths(), break_stale: bool = False
) -> dict:
    """Vuelve a una versión ya publicada (re-verificada) o a la línea base."""
    try:
        with refresh_lock(paths.lock, break_stale=break_stale):
            if to == "baseline":
                paths.pointer.unlink(missing_ok=True)
                record = {"relative_path": None, "origin": "baseline"}
                append_jsonl(
                    paths.history,
                    {"event": "rollback", "at": _utcnow().isoformat(), **record},
                )
                return record
            if Path(to).name != to or not to.endswith(".csv"):
                raise FirmsRefreshError(f"Versión inválida: {to!r}", EXIT_USAGE)
            version, sidecar = paths.versions_dir / to, _sidecar(paths, to)
            if not version.is_file() or not sidecar.is_file():
                raise FirmsRefreshError(f"No existe la versión {to!r}", EXIT_USAGE)
            pointer = json.loads(sidecar.read_text(encoding="utf-8"))
            if sha256_bytes(version.read_bytes()) != pointer.get("sha256"):
                raise FirmsRefreshError(f"sha256 de {to!r} no coincide.", EXIT_DATA)
            _publish(paths, pointer, "rollback")
            return pointer
    except RefreshLockedError as exc:
        raise FirmsRefreshError(str(exc), EXIT_LOCKED) from None


def _read_pointer(paths: FirmsPaths) -> Optional[dict]:
    if not paths.pointer.exists():
        return None
    return json.loads(paths.pointer.read_text(encoding="utf-8"))


def cleanup(
    *,
    paths: FirmsPaths = FirmsPaths(),
    keep: int = 3,
    grace: timedelta = timedelta(hours=24),
    apply: bool = False,
    now: Optional[datetime] = None,
) -> dict:
    """Borra versiones viejas. Nunca la vigente, su base (destino de
    rollback) ni las `keep` más recientes; solo las reemplazadas hace más
    de `grace`. Sin `apply=True` solo informa (dry-run)."""
    now = now or _utcnow()
    try:
        with refresh_lock(paths.lock):
            sidecars = {}
            for path in sorted(paths.versions_dir.glob("*.json")):
                meta = json.loads(path.read_text(encoding="utf-8"))
                sidecars[meta["relative_path"]] = meta
            ordered = sorted(sidecars.values(), key=lambda m: m["created_at"])
            current = _read_pointer(paths) or {}
            protected = {current.get("relative_path")}
            protected |= {
                m["relative_path"]
                for m in ordered
                if m["sha256"] == current.get("base_sha256")
            }
            protected |= (
                {m["relative_path"] for m in ordered[-keep:]} if keep > 0 else set()
            )
            deletable, kept = [], []
            for index, meta in enumerate(ordered):
                later = ordered[index + 1 :]
                superseded_at = (
                    datetime.fromisoformat(later[0]["created_at"]) if later else None
                )
                old_enough = superseded_at is not None and now - superseded_at > grace
                name = meta["relative_path"]
                (deletable if name not in protected and old_enough else kept).append(
                    name
                )
            if apply:
                for name in deletable:
                    (paths.versions_dir / name).unlink(missing_ok=True)
                    _sidecar(paths, name).unlink(missing_ok=True)
                    append_jsonl(
                        paths.history,
                        {
                            "event": "cleanup",
                            "at": now.isoformat(),
                            "relative_path": name,
                        },
                    )
            return {
                "applied": apply,
                "deleted" if apply else "would_delete": deletable,
                "kept": kept,
            }
    except RefreshLockedError as exc:
        raise FirmsRefreshError(str(exc), EXIT_LOCKED) from None


def status(*, paths: FirmsPaths = FirmsPaths(), today: Optional[date] = None) -> dict:
    today = today or _utcnow().date()
    try:
        source = resolve_firms_source(
            reproducibility=False,
            pointer_path=paths.pointer,
            versions_dir=paths.versions_dir,
            baseline_csv=paths.baseline_csv,
        )
    except FirmsSourceError as exc:
        return {"origin": "invalid_pointer", "error": str(exc)}
    return {
        "origin": source.origin,
        "file": source.path.name,
        "coverage_start": source.coverage_start.isoformat(),
        "coverage_end": source.coverage_end.isoformat(),
        "days_behind_today": (today - source.coverage_end).days,
        "locked": paths.lock.exists(),
    }


# --- CLI ---------------------------------------------------------------------


def _outcome_json(outcome: RefreshOutcome) -> dict:
    return {
        "status": outcome.status,
        "coverage_start": outcome.coverage_start.isoformat(),
        "coverage_end": outcome.coverage_end.isoformat(),
        "new_rows": outcome.new_rows,
        "version": (outcome.pointer or {}).get("relative_path"),
        **outcome.detail,
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m src.refresh.firms_refresh")
    sub = parser.add_subparsers(dest="command", required=True)
    p_refresh = sub.add_parser("refresh", help="Extiende FIRMS hasta ayer (UTC).")
    p_refresh.add_argument("--break-stale-lock", action="store_true")
    sub.add_parser("status", help="Fuente FIRMS vigente y su desfase.")
    p_rollback = sub.add_parser(
        "rollback", help="Vuelve a una versión o a la línea base."
    )
    p_rollback.add_argument(
        "--to", required=True, help="archivo en versions/ o 'baseline'"
    )
    p_rollback.add_argument("--break-stale-lock", action="store_true")
    p_cleanup = sub.add_parser(
        "cleanup", help="Borra versiones viejas (dry-run por defecto)."
    )
    p_cleanup.add_argument("--keep", type=int, default=3)
    p_cleanup.add_argument("--grace-hours", type=float, default=24.0)
    p_cleanup.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)

    try:
        if args.command == "refresh":
            result = _outcome_json(refresh(break_stale=args.break_stale_lock))
        elif args.command == "status":
            result = status()
        elif args.command == "rollback":
            result = rollback(args.to, break_stale=args.break_stale_lock)
        else:
            result = cleanup(
                keep=args.keep,
                grace=timedelta(hours=args.grace_hours),
                apply=args.apply,
            )
    except FirmsRefreshError as exc:
        print(
            json.dumps(
                {"status": "error", "error": redact(exc, [NASA_FIRMS_API_KEY])},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return exc.exit_code
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())

"""Refresco DMC manual, versionado por mes, atómico e idempotente (SAPI-71 Fase B).

    python -m src.refresh.dmc_refresh refresh [--break-stale-lock]
    python -m src.refresh.dmc_refresh status
    python -m src.refresh.dmc_refresh rollback --to <manifest_sha12>

Contrato verificado con una llamada real (23-09-2026, estación 330007):
`getDatosRecientesEma/{estacion}/{año}/{mes}` devuelve el mes EN CURSO
hasta ~25 min antes (2.169 lecturas cada 15 min, orden ascendente, sin
`momento` repetidos, `timezone: "UTC"`, raíz sin envoltorio de estación),
compatible con `parse_dmc_json` al envolverla como `{estacion: respuesta}`.

Almacenamiento (fuera de `data/raw/`, así que `load_regional_meteo_series`
NO lo lee: nada de esto llega todavía al scoring):

    data/processed/dmc/<estacion>/versions/dmc_<estacion>_<YYYY-MM>_<sha12>.json
    data/processed/dmc/<estacion>/pointers/<manifest_sha12>.json
    data/processed/dmc/<estacion>/CURRENT.json
    data/processed/dmc/<estacion>/pointer_history.jsonl

Cada versión mensual es un JSON DMC canónico (`{estacion: {timezone,
datosEstaciones: {estacion, datos}}}`, claves ordenadas, lecturas por
`momento` ascendente) sin campos volátiles como `fechaCreacion`, así que la
misma entrada produce siempre los mismos bytes. Merge por mes: lecturas ya
publicadas ∪ lecturas nuevas, clave (estación, `momento` UTC). Si un
`momento` ya publicado llega con otro contenido, gana el publicado
(append-only) y el conflicto se informa en la corrida (salida de la CLI).
Queda fuera del manifest para no romper la idempotencia: por eso una
corrida cuyo único cambio es un conflicto termina en `unchanged` y no
escribe nada, tampoco en `pointer_history.jsonl`, que solo recibe una
línea cuando se publica o se hace rollback. Los archivos legacy de
`data/raw/` nunca se escriben.

Códigos de salida: 0 publicado / sin cambios, 2 uso, 65 datos inválidos o
vacíos, 69 red o HTTP no exitoso, 75 bloqueado, 78 sin credenciales.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Optional, Sequence

import requests

from src.config import DATA_PROCESSED_DIR, DMC_API_BASE_URL, DMC_TOKEN, DMC_USUARIO
from src.procesamiento.raw_parser import DmcFormatError, parse_dmc_json
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

# Única estación que usa Model D (= prototype_service.STATION_ID, ver test).
DMC_STATION_ID = "330007"
POINTER_SCHEMA_VERSION = 1
GENERATOR = "src.refresh.dmc_refresh"
# Al empezar un mes, el mes en curso puede venir vacío legítimamente.
EMPTY_CURRENT_MONTH_GRACE = timedelta(hours=6)
MAX_ATTEMPTS = 3
REQUEST_TIMEOUT = 60
PAUSE_BETWEEN_MONTHS = 1.2
MOMENTO_FORMAT = "%Y-%m-%d %H:%M:%S"


class DmcRefreshError(RuntimeError):
    def __init__(self, message: str, exit_code: int) -> None:
        super().__init__(message)
        self.exit_code = exit_code


@dataclass(frozen=True)
class DmcPaths:
    """Rutas inyectables para tests; por defecto, las de producción."""

    root: Path = DATA_PROCESSED_DIR / "dmc"
    station_id: str = DMC_STATION_ID

    @property
    def station_dir(self) -> Path:
        return self.root / self.station_id

    @property
    def versions_dir(self) -> Path:
        return self.station_dir / "versions"

    @property
    def pointers_dir(self) -> Path:
        return self.station_dir / "pointers"

    @property
    def pointer(self) -> Path:
        return self.station_dir / "CURRENT.json"

    @property
    def history(self) -> Path:
        return self.station_dir / "pointer_history.jsonl"

    @property
    def lock(self) -> Path:
        return self.root / ".refresh.lock"


@dataclass
class RefreshOutcome:
    status: str  # "published" | "unchanged"
    pointer: dict
    months_fetched: list[str] = field(default_factory=list)
    new_records: int = 0
    conflicts: int = 0


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _month_key(day: date) -> str:
    return f"{day.year}-{day.month:02d}"


def months_to_fetch(coverage_end: Optional[datetime], now: datetime) -> list[str]:
    """Desde el mes de la última lectura publicada (o el mes anterior en
    la primera corrida) hasta el mes en curso, inclusive."""
    first = (
        coverage_end.date()
        if coverage_end
        else (now.replace(day=1) - timedelta(days=1)).date()
    )
    months, cursor = [], first.replace(day=1)
    while cursor <= now.date():
        months.append(_month_key(cursor))
        cursor = (cursor + timedelta(days=32)).replace(day=1)
    return months


# --- Descarga y validación ----------------------------------------------------


def _fetch_month(
    session: requests.Session,
    station: str,
    month: str,
    credentials: tuple[str, str],
    sleep: Callable[[float], None],
) -> Any:
    year, mon = month.split("-")
    url = (
        f"{DMC_API_BASE_URL}/application/servicios/getDatosRecientesEma/"
        f"{station}/{int(year)}/{int(mon)}"
    )
    params = {"usuario": credentials[0], "token": credentials[1]}
    last: Optional[str] = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            response = session.get(url, params=params, timeout=REQUEST_TIMEOUT)
        except requests.RequestException as exc:
            last = f"{type(exc).__name__}: {exc}"
        else:
            if response.status_code >= 500:
                last = f"HTTP {response.status_code}"
            elif response.status_code != 200:
                raise DmcRefreshError(
                    f"DMC respondió HTTP {response.status_code} para {month}.",
                    EXIT_NETWORK,
                )
            else:
                try:
                    return response.json()
                except ValueError as exc:
                    raise DmcRefreshError(
                        f"JSON DMC inválido para {month}: {type(exc).__name__}",
                        EXIT_DATA,
                    ) from None
        if attempt < MAX_ATTEMPTS - 1:
            sleep(2**attempt)
    raise DmcRefreshError(
        f"DMC no disponible para {month} tras {MAX_ATTEMPTS} intentos: "
        f"{redact(last, credentials)}",
        EXIT_NETWORK,
    )


def validate_month_payload(payload: Any, month: str) -> tuple[dict, list[dict]]:
    """(estacion, lecturas) de una respuesta mensual; lanza DmcRefreshError
    si no tiene la forma verificada o trae lecturas fuera del mes.

    `registros` ausente se acepta: el documento canónico no lo lleva y
    `validate_version_bytes` relee ese documento con esta misma función. Si
    viene, debe ser un entero y calzar con `len(datos)`.
    """
    if not isinstance(payload, dict):
        raise DmcRefreshError(
            f"Respuesta DMC {month}: se esperaba un objeto, llegó {type(payload).__name__} "
            f"({str(payload)[:40]!r}).",
            EXIT_DATA,
        )
    if payload.get("timezone") != "UTC":
        raise DmcRefreshError(
            f"Respuesta DMC {month}: timezone {payload.get('timezone')!r}, se esperaba 'UTC'.",
            EXIT_DATA,
        )
    stations = payload.get("datosEstaciones")
    records = stations.get("datos") if isinstance(stations, dict) else None
    if not isinstance(stations, dict) or not isinstance(records, list):
        raise DmcRefreshError(
            f"Respuesta DMC {month} sin datosEstaciones.datos.", EXIT_DATA
        )
    declared = payload.get("registros")
    if "registros" in payload and not isinstance(declared, int):
        raise DmcRefreshError(
            f"Respuesta DMC {month}: registros={declared!r} no es un entero.",
            EXIT_DATA,
        )
    if isinstance(declared, int) and declared != len(records):
        raise DmcRefreshError(
            f"Respuesta DMC {month} incompleta: registros={declared}, datos={len(records)}.",
            EXIT_DATA,
        )
    for record in records:
        momento = record.get("momento") if isinstance(record, dict) else None
        try:
            parsed = datetime.strptime(str(momento), MOMENTO_FORMAT)
        except ValueError:
            raise DmcRefreshError(
                f"Respuesta DMC {month}: lectura sin momento válido ({momento!r}).",
                EXIT_DATA,
            ) from None
        if _month_key(parsed.date()) != month:
            raise DmcRefreshError(
                f"Respuesta DMC {month}: lectura de otro mes ({momento}).", EXIT_DATA
            )
    estacion = stations.get("estacion")
    return (estacion if isinstance(estacion, dict) else {}), records


# --- Merge y serialización canónica ------------------------------------------


def merge_records(
    existing: list[dict], incoming: list[dict]
) -> tuple[list[dict], int, int]:
    """(lecturas fusionadas ordenadas por momento, nuevas, conflictos).
    Clave: `momento` (la estación es fija por archivo). Lo publicado gana."""
    by_moment = {record["momento"]: record for record in existing}
    added = conflicts = 0
    for record in incoming:
        key = record["momento"]
        if key not in by_moment:
            by_moment[key] = record
            added += 1
        elif by_moment[key] != record:
            conflicts += 1
    return [by_moment[key] for key in sorted(by_moment)], added, conflicts


def canonical_month_bytes(station: str, estacion: dict, records: list[dict]) -> bytes:
    document = {
        station: {
            "timezone": "UTC",
            "datosEstaciones": {"estacion": estacion, "datos": records},
        }
    }
    text = json.dumps(
        document, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return (text + "\n").encode("utf-8")


def validate_version_bytes(
    data: bytes, station: str, month: str, expected: int
) -> None:
    """Relee el documento final con el MISMO parser que usa la inferencia
    antes de publicarlo."""
    document = json.loads(data.decode("utf-8"))
    _, records = validate_month_payload(document[station], month)
    if len(records) != expected:
        raise DmcRefreshError(f"Versión {month} no se relee íntegra.", EXIT_DATA)
    with tempfile.TemporaryDirectory() as tmp:
        probe = Path(tmp) / "version.json"
        probe.write_bytes(data)
        try:
            parsed = parse_dmc_json(probe)
        except (DmcFormatError, ValueError) as exc:
            raise DmcRefreshError(
                f"Versión {month} rechazada por parse_dmc_json: {exc}", EXIT_DATA
            )
    if expected and parsed.empty:
        raise DmcRefreshError(f"Versión {month} sin lecturas utilizables.", EXIT_DATA)


# --- Puntero -----------------------------------------------------------------


def _manifest_sha(months: dict) -> str:
    return sha256_bytes(
        json.dumps(months, sort_keys=True, separators=(",", ":")).encode()
    )


def read_current(paths: DmcPaths) -> Optional[dict]:
    """Puntero vigente, verificando el sha256 de cada versión mensual."""
    if not paths.pointer.exists():
        return None
    try:
        pointer = json.loads(paths.pointer.read_text(encoding="utf-8"))
        months = pointer["months"]
        if pointer.get("schema_version") != POINTER_SCHEMA_VERSION:
            raise ValueError(f"schema_version {pointer.get('schema_version')!r}")
        if _manifest_sha(months) != pointer["manifest_sha256"]:
            raise ValueError("manifest_sha256 no coincide")
        for month, entry in months.items():
            name = entry["relative_path"]
            if Path(name).name != name:
                raise ValueError(f"ruta fuera de versions/: {name!r}")
            if (
                sha256_bytes((paths.versions_dir / name).read_bytes())
                != entry["sha256"]
            ):
                raise ValueError(f"sha256 de {name} no coincide")
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise DmcRefreshError(
            f"Puntero DMC vigente inválido: {exc}", EXIT_DATA
        ) from None
    return pointer


def _month_records(paths: DmcPaths, entry: dict) -> tuple[dict, list[dict]]:
    document = json.loads(
        (paths.versions_dir / entry["relative_path"]).read_text("utf-8")
    )
    stations = document[paths.station_id]["datosEstaciones"]
    return stations.get("estacion", {}), stations["datos"]


def _publish(paths: DmcPaths, pointer: dict, event: str, **extra: Any) -> None:
    atomic_write_json(paths.pointer, pointer)
    record = {"event": event, "at": _utcnow().isoformat(), **extra, **pointer}
    append_jsonl(paths.history, record)


# --- Refresco ------------------------------------------------------------------


def refresh(
    *,
    paths: DmcPaths = DmcPaths(),
    session: Optional[requests.Session] = None,
    credentials: Optional[tuple[str, str]] = None,
    now: Optional[datetime] = None,
    sleep: Callable[[float], None] = time.sleep,
    break_stale: bool = False,
) -> RefreshOutcome:
    if credentials is None:
        credentials = (DMC_USUARIO, DMC_TOKEN)  # leídas al llamar, no al importar
    if not all(credentials):
        raise DmcRefreshError(
            "DMC_USUARIO / DMC_TOKEN no configurados: se inyectan en runtime "
            "(.env / env_file), nunca en la imagen.",
            EXIT_CONFIG,
        )
    now = now or _utcnow()
    session = session or requests.Session()
    try:
        with refresh_lock(paths.lock, break_stale=break_stale):
            current = read_current(paths)
            months = dict((current or {}).get("months", {}))
            coverage_end = (
                datetime.strptime(current["coverage_end"], MOMENTO_FORMAT)
                if current
                else None
            )
            fetched, added_total, conflicts_total = [], 0, 0
            for index, month in enumerate(months_to_fetch(coverage_end, now)):
                if index:
                    sleep(PAUSE_BETWEEN_MONTHS)
                payload = _fetch_month(
                    session, paths.station_id, month, credentials, sleep
                )
                estacion, incoming = validate_month_payload(payload, month)
                if not incoming:
                    month_start = datetime.strptime(month + "-01", "%Y-%m-%d").replace(
                        tzinfo=timezone.utc
                    )
                    if month == _month_key(now.date()) and now - month_start < (
                        EMPTY_CURRENT_MONTH_GRACE
                    ):
                        continue  # inicio de mes: todavía no hay lecturas
                    raise DmcRefreshError(
                        f"Respuesta DMC vacía para {month}: no se publica nada.",
                        EXIT_DATA,
                    )
                existing_estacion, existing = (
                    _month_records(paths, months[month])
                    if month in months
                    else ({}, [])
                )
                merged, added, conflicts = merge_records(existing, incoming)
                data = canonical_month_bytes(
                    paths.station_id, existing_estacion or estacion, merged
                )
                validate_version_bytes(data, paths.station_id, month, len(merged))
                sha = sha256_bytes(data)
                name = f"dmc_{paths.station_id}_{month}_{sha[:12]}.json"
                write_immutable(paths.versions_dir / name, data)
                months[month] = {
                    "relative_path": name,
                    "sha256": sha,
                    "record_count": len(merged),
                    "first_momento": merged[0]["momento"],
                    "last_momento": merged[-1]["momento"],
                }
                fetched.append(month)
                added_total += added
                conflicts_total += conflicts
            if not months:
                raise DmcRefreshError(
                    "DMC no devolvió ninguna lectura publicable.", EXIT_DATA
                )
            manifest = _manifest_sha(months)
            if current and manifest == current["manifest_sha256"]:
                return RefreshOutcome("unchanged", current, fetched, 0, conflicts_total)
            ordered = sorted(months)
            pointer = {
                "schema_version": POINTER_SCHEMA_VERSION,
                "source": "dmc",
                "station_id": paths.station_id,
                "months": months,
                "manifest_sha256": manifest,
                "coverage_start": months[ordered[0]]["first_momento"],
                "coverage_end": months[ordered[-1]]["last_momento"],
                "record_count": sum(entry["record_count"] for entry in months.values()),
                "created_at": _utcnow().isoformat(),
                "base_manifest_sha256": (current or {}).get("manifest_sha256"),
                "generator": GENERATOR,
            }
            atomic_write_json(paths.pointers_dir / f"{manifest[:12]}.json", pointer)
            _publish(paths, pointer, "publish", conflicts=conflicts_total)
            return RefreshOutcome(
                "published", pointer, fetched, added_total, conflicts_total
            )
    except RefreshLockedError as exc:
        raise DmcRefreshError(str(exc), EXIT_LOCKED) from None
    except ImmutableVersionError as exc:
        raise DmcRefreshError(str(exc), EXIT_DATA) from None


def rollback(
    to: str, *, paths: DmcPaths = DmcPaths(), break_stale: bool = False
) -> dict:
    """Republica un puntero anterior (`pointers/<manifest_sha12>.json`),
    re-verificando el sha256 de cada versión mensual que referencia."""
    if not to or Path(to).name != to or not all(c in "0123456789abcdef" for c in to):
        raise DmcRefreshError(f"Identificador de puntero inválido: {to!r}", EXIT_USAGE)
    try:
        with refresh_lock(paths.lock, break_stale=break_stale):
            source = paths.pointers_dir / f"{to}.json"
            if not source.is_file():
                raise DmcRefreshError(f"No existe el puntero {to!r}", EXIT_USAGE)
            pointer = json.loads(source.read_text(encoding="utf-8"))
            for entry in pointer["months"].values():
                data = (paths.versions_dir / entry["relative_path"]).read_bytes()
                if sha256_bytes(data) != entry["sha256"]:
                    raise DmcRefreshError(
                        f"sha256 de {entry['relative_path']} no coincide.", EXIT_DATA
                    )
            _publish(paths, pointer, "rollback")
            return pointer
    except RefreshLockedError as exc:
        raise DmcRefreshError(str(exc), EXIT_LOCKED) from None


def status(*, paths: DmcPaths = DmcPaths(), now: Optional[datetime] = None) -> dict:
    now = now or _utcnow()
    try:
        current = read_current(paths)
    except DmcRefreshError as exc:
        return {"origin": "invalid_pointer", "error": str(exc)}
    if current is None:
        return {"origin": "none", "locked": paths.lock.exists()}
    end = datetime.strptime(current["coverage_end"], MOMENTO_FORMAT).replace(
        tzinfo=timezone.utc
    )
    return {
        "origin": "current",
        "station_id": current["station_id"],
        "months": sorted(current["months"]),
        "coverage_start": current["coverage_start"],
        "coverage_end": current["coverage_end"],
        "record_count": current["record_count"],
        "hours_behind_now": round((now - end).total_seconds() / 3600, 2),
        "manifest_sha256": current["manifest_sha256"],
        "locked": paths.lock.exists(),
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m src.refresh.dmc_refresh")
    sub = parser.add_subparsers(dest="command", required=True)
    p_refresh = sub.add_parser("refresh", help="Recupera el mes en curso y fusiona.")
    p_refresh.add_argument("--break-stale-lock", action="store_true")
    sub.add_parser("status", help="Puntero DMC vigente y su antigüedad.")
    p_rollback = sub.add_parser("rollback", help="Republica un puntero anterior.")
    p_rollback.add_argument("--to", required=True, help="manifest_sha12 en pointers/")
    p_rollback.add_argument("--break-stale-lock", action="store_true")
    args = parser.parse_args(argv)

    try:
        if args.command == "refresh":
            outcome = refresh(break_stale=args.break_stale_lock)
            result = {
                "status": outcome.status,
                "months_fetched": outcome.months_fetched,
                "new_records": outcome.new_records,
                "conflicts": outcome.conflicts,
                "coverage_end": outcome.pointer["coverage_end"],
                "manifest_sha256": outcome.pointer["manifest_sha256"],
            }
        elif args.command == "status":
            result = status()
        else:
            result = rollback(args.to, break_stale=args.break_stale_lock)
    except DmcRefreshError as exc:
        message = redact(exc, [DMC_USUARIO, DMC_TOKEN])
        print(
            json.dumps({"status": "error", "error": message}, ensure_ascii=False),
            file=sys.stderr,
        )
        return exc.exit_code
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())

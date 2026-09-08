"""Backfill idempotente del histórico mensual DMC — estación 330007
(Rodelillo), Fase 3 (aprobada 2026-09-07).

Acotado al período de solapamiento con el backfill FIRMS ya existente:
2021-08-30 -> 2026-08-29. Este período NO se eligió mirando qué días
tuvieron incendios — es la intersección de disponibilidad entre ambas
fuentes (ver docs/auditoria-consistencia-2026-09-06.md, Fase 3).

Descarga 1 mes calendario por request desde
  GET {DMC_API_BASE_URL}/application/servicios/getDatosRecientesEma/{station}/{año}/{mes}
y lo guarda en data/raw/dmc_historico_{station}_{YYYY}-{MM}.json con el
mismo envoltorio `{"<station>": <respuesta cruda>}` que ya usan los 4
archivos de muestra existentes (compatible con
`src.procesamiento.raw_parser.parse_dmc_json`).

Idempotencia: si el archivo del mes ya existe, se vuelve a pedir el MISMO
mes a la API y se compara solo el contenido real (`datosEstaciones.datos`,
por `momento`/`temperatura`/`humedadRelativa`/`fuerzaDelViento`) contra lo
guardado — nunca el payload completo, porque `fechaCreacion` cambia en
cada respuesta aunque los datos sean idénticos.
  - Idéntico  -> skip, no se toca el archivo.
  - Distinto  -> CONFLICTO: se registra en el manifest y la respuesta nueva
                 se guarda aparte (sufijo `_conflicto_<fecha>`), nunca se
                 sobrescribe el archivo existente en silencio.

Uso: python scripts/backfill_dmc_historico.py
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests

from src.config import DMC_API_BASE_URL, DMC_TOKEN, DMC_USUARIO

STATION_ID = "330007"
PERIOD_START = date(2021, 8, 30)
PERIOD_END = date(2026, 8, 29)
REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = REPO_ROOT / "data" / "raw"
REPORT_PATH = REPO_ROOT / "reports" / "backfill_dmc_330007_manifest.json"
SLEEP_BETWEEN_REQUESTS = 1.2
MAX_RETRIES = 3
RETRY_BACKOFF = (2, 5, 10)


def _months_in_range(start: date, end: date) -> list[tuple[int, int]]:
    months = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        months.append((y, m))
        m += 1
        if m == 13:
            m = 1
            y += 1
    return months


def _fetch_month(station: str, year: int, month: int):
    """Devuelve el dict de la respuesta, o el string 'Sin Información' tal
    cual lo entrega la API cuando no hay datos para ese mes."""
    url = f"{DMC_API_BASE_URL}/application/servicios/getDatosRecientesEma/{station}/{year}/{month}"
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            r = requests.get(url, params={"usuario": DMC_USUARIO, "token": DMC_TOKEN}, timeout=30)
            r.raise_for_status()
            return r.json()
        except Exception as exc:  # noqa: BLE001 - se reintenta cualquier fallo de red/parseo
            last_exc = exc
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_BACKOFF[attempt])
    raise RuntimeError(f"Fallo tras {MAX_RETRIES} intentos para {year}-{month:02d}: {last_exc}")


def _records_of(payload) -> list[dict]:
    if isinstance(payload, str) or payload is None:
        return []
    return payload.get("datosEstaciones", {}).get("datos", [])


def _records_equal(a: list[dict], b: list[dict]) -> bool:
    def _key(recs):
        return sorted(
            (r.get("momento"), r.get("temperatura"), r.get("humedadRelativa"), r.get("fuerzaDelViento"))
            for r in recs
        )

    return _key(a) == _key(b)


def run_backfill() -> dict:
    months = _months_in_range(PERIOD_START, PERIOD_END)
    resultado = {
        "station_id": STATION_ID,
        "period_start": str(PERIOD_START),
        "period_end": str(PERIOD_END),
        "meses_solicitados": [f"{y}-{m:02d}" for y, m in months],
        "meses_nuevos_ok": [],
        "meses_ya_existentes_identicos": [],
        "meses_conflicto": [],
        "meses_sin_datos": [],
        "meses_fallidos": [],
        "n_registros_totales": 0,
        "n_duplicados_momento": 0,
        "min_timestamp": None,
        "max_timestamp": None,
        "hashes_archivos": {},
    }

    all_momentos: list[str] = []

    for y, m in months:
        mes_str = f"{y}-{m:02d}"
        out_path = RAW_DIR / f"dmc_historico_{STATION_ID}_{mes_str}.json"

        try:
            payload = _fetch_month(STATION_ID, y, m)
        except RuntimeError as exc:
            resultado["meses_fallidos"].append({"mes": mes_str, "error": str(exc)})
            time.sleep(SLEEP_BETWEEN_REQUESTS)
            continue

        if isinstance(payload, str):
            resultado["meses_sin_datos"].append({"mes": mes_str, "respuesta": payload})
            time.sleep(SLEEP_BETWEEN_REQUESTS)
            continue

        records = _records_of(payload)
        momentos = [r.get("momento") for r in records]
        resultado["n_duplicados_momento"] += len(momentos) - len(set(momentos))

        if out_path.exists():
            existing = json.loads(out_path.read_text(encoding="utf-8"))
            existing_records = _records_of(existing.get(STATION_ID))
            if _records_equal(existing_records, records):
                resultado["meses_ya_existentes_identicos"].append(mes_str)
                all_momentos.extend(v for v in momentos if v)
                resultado["n_registros_totales"] += len(existing_records)
                resultado["hashes_archivos"][mes_str] = hashlib.sha256(out_path.read_bytes()).hexdigest()
            else:
                conflict_path = (
                    RAW_DIR / f"dmc_historico_{STATION_ID}_{mes_str}_conflicto_{date.today().isoformat()}.json"
                )
                conflict_path.write_text(
                    json.dumps({STATION_ID: payload}, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                resultado["meses_conflicto"].append(
                    {
                        "mes": mes_str,
                        "archivo_existente": str(out_path),
                        "archivo_nuevo_para_revision": str(conflict_path),
                        "n_registros_existente": len(existing_records),
                        "n_registros_nuevo": len(records),
                    }
                )
            time.sleep(SLEEP_BETWEEN_REQUESTS)
            continue

        out_path.write_text(json.dumps({STATION_ID: payload}, ensure_ascii=False, indent=2), encoding="utf-8")
        resultado["meses_nuevos_ok"].append(mes_str)
        resultado["n_registros_totales"] += len(records)
        all_momentos.extend(v for v in momentos if v)
        resultado["hashes_archivos"][mes_str] = hashlib.sha256(out_path.read_bytes()).hexdigest()
        time.sleep(SLEEP_BETWEEN_REQUESTS)

    if all_momentos:
        resultado["min_timestamp"] = min(all_momentos)
        resultado["max_timestamp"] = max(all_momentos)

    return resultado


def main() -> None:
    resultado = run_backfill()
    REPORT_PATH.parent.mkdir(exist_ok=True)
    REPORT_PATH.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    print(f"\nEscrito {REPORT_PATH}")


if __name__ == "__main__":
    main()

"""Telemetría DMC Rodelillo (330007) desde el último JSON en data/raw.

No importa `src.procesamiento` (contrato de arquitectura). Parsea el mismo
formato real de getDatosRecientesEma que ya valida el pipeline.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Optional

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RAW_DIR = _REPO_ROOT / "data" / "raw"
_STATION = "330007"
_STATION_LABEL = "DMC Rodelillo"


@dataclass(frozen=True)
class DmcLiveSnapshot:
    """Última observación usable de Rodelillo + delta vs la anterior."""

    station_code: str
    station_label: str
    momento: Optional[datetime]
    temperatura: Optional[float]
    humedad_relativa: Optional[float]
    velocidad_viento_kmh: Optional[float]
    direccion_viento_deg: Optional[float]
    delta_temp: Optional[float]
    delta_humedad: Optional[float]
    delta_viento: Optional[float]
    source_path: Optional[str]
    available: bool
    detail: str


def _clean_float(val: object) -> Optional[float]:
    if val is None or val == "":
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if not isinstance(val, str):
        return None
    match = re.search(r"[-+]?\d*\.?\d+", val.replace(",", "."))
    return float(match.group()) if match else None


def _extract_records(contenido: dict) -> list[dict]:
    if "error" in contenido:
        return []
    datos = contenido.get("datosEstaciones", {})
    if isinstance(datos, dict):
        regs = datos.get("datos", [])
        if isinstance(regs, list):
            return regs
    return []


def _latest_dmc_path() -> Optional[Path]:
    if not _RAW_DIR.exists():
        return None
    files = sorted(_RAW_DIR.glob("dmc_meteo_*.json"))
    return files[-1] if files else None


@lru_cache(maxsize=1)
def load_rodelillo_snapshot() -> DmcLiveSnapshot:
    """Lee el JSON más reciente; sin archivo o sin estación → available=False."""
    path = _latest_dmc_path()
    if path is None:
        return DmcLiveSnapshot(
            station_code=_STATION,
            station_label=_STATION_LABEL,
            momento=None,
            temperatura=None,
            humedad_relativa=None,
            velocidad_viento_kmh=None,
            direccion_viento_deg=None,
            delta_temp=None,
            delta_humedad=None,
            delta_viento=None,
            source_path=None,
            available=False,
            detail="Sin archivo dmc_meteo_*.json en data/raw",
        )

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return DmcLiveSnapshot(
            station_code=_STATION,
            station_label=_STATION_LABEL,
            momento=None,
            temperatura=None,
            humedad_relativa=None,
            velocidad_viento_kmh=None,
            direccion_viento_deg=None,
            delta_temp=None,
            delta_humedad=None,
            delta_viento=None,
            source_path=str(path),
            available=False,
            detail=f"No se pudo leer {path.name}: {exc}",
        )

    contenido = raw.get(_STATION)
    if not isinstance(contenido, dict):
        return DmcLiveSnapshot(
            station_code=_STATION,
            station_label=_STATION_LABEL,
            momento=None,
            temperatura=None,
            humedad_relativa=None,
            velocidad_viento_kmh=None,
            direccion_viento_deg=None,
            delta_temp=None,
            delta_humedad=None,
            delta_viento=None,
            source_path=str(path),
            available=False,
            detail=f"Estación {_STATION} ausente en {path.name}",
        )

    rows: list[tuple[datetime, float, float, float, Optional[float]]] = []
    for reg in _extract_records(contenido):
        momento = reg.get("momento")
        try:
            ts = datetime.strptime(str(momento), "%Y-%m-%d %H:%M:%S")
        except (TypeError, ValueError):
            continue
        temp = _clean_float(reg.get("temperatura"))
        hum = _clean_float(reg.get("humedadRelativa"))
        viento_kt = _clean_float(reg.get("fuerzaDelViento"))
        viento = round(viento_kt * 1.852, 2) if viento_kt is not None else None
        direccion = _clean_float(reg.get("direccionDelViento"))
        if temp is None or hum is None or viento is None:
            continue
        rows.append((ts, temp, hum, viento, direccion))

    if not rows:
        return DmcLiveSnapshot(
            station_code=_STATION,
            station_label=_STATION_LABEL,
            momento=None,
            temperatura=None,
            humedad_relativa=None,
            velocidad_viento_kmh=None,
            direccion_viento_deg=None,
            delta_temp=None,
            delta_humedad=None,
            delta_viento=None,
            source_path=str(path),
            available=False,
            detail=f"Sin registros válidos de {_STATION} en {path.name}",
        )

    rows.sort(key=lambda r: r[0])
    last = rows[-1]
    prev = rows[-2] if len(rows) >= 2 else None
    return DmcLiveSnapshot(
        station_code=_STATION,
        station_label=_STATION_LABEL,
        momento=last[0],
        temperatura=last[1],
        humedad_relativa=last[2],
        velocidad_viento_kmh=last[3],
        direccion_viento_deg=last[4],
        delta_temp=(last[1] - prev[1]) if prev else None,
        delta_humedad=(last[2] - prev[2]) if prev else None,
        delta_viento=(last[3] - prev[3]) if prev else None,
        source_path=str(path),
        available=True,
        detail=f"Última observación {last[0].strftime('%Y-%m-%d %H:%M')} · {path.name}",
    )

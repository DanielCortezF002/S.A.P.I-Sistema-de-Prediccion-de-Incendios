"""Última observación DMC Rodelillo (330007) para la interfaz, sin acceso a red.

Módulo de solo lectura para la defensa del Sprint 2 (OCC-UI-DMC-LATEST-OBSERVATION).
Resolución D2 (F2, 30-10-2026): la interfaz Streamlit ya no consulta la API de la
Dirección Meteorológica de Chile (DMC). Muestra la última observación de la estación
Rodelillo (330007) que el pipeline de ingesta gobernado ya dejó en `data/raw`
(lector `app.data.dmc_live.load_rodelillo_snapshot`, patrón preexistente en main).

Reglas de integridad y arquitectura:
- Sin red y sin credenciales: este módulo no importa clientes HTTP ni lee las
  credenciales de la API de DMC. La única ruta de datos remotos de la interfaz es el
  backend (ver `test_app_reaches_remote_data_only_through_backend_client`).
- Solo lectura: NO escribe archivos de ingesta, snapshots ni punteros CURRENT.
- NO recalculación de ranking: las observaciones son informativas y no alteran los scores
  históricos del 01-09-2026.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

from app.data.dmc_live import DmcLiveSnapshot, load_rodelillo_snapshot

RODELILLO_CODIGO = "330007"
RODELILLO_NOMBRE = "Rodelillo, Ad."
CHILE_TZ = ZoneInfo("America/Santiago")

# Umbrales explícitos de frescura (horas desde el momento de la observación):
# - RECIENTE: <= 2 h
# - CON RETRASO: > 2 h y <= 6 h
# - DESACTUALIZADO: > 6 h
FRESHNESS_RECENT_HOURS = 2.0
FRESHNESS_DELAYED_HOURS = 6.0

STATUS_RECIENTE = "RECIENTE"
STATUS_CON_RETRASO = "CON RETRASO"
STATUS_DESACTUALIZADO = "DESACTUALIZADO"
STATUS_NO_DISPONIBLE = "NO DISPONIBLE"

_KMH_PER_KT = 1.852


def _classify_freshness(age_hours: Optional[float]) -> str:
    """Clasifica el estado de frescura según umbrales operacionales explícitos."""
    if age_hours is None:
        return STATUS_NO_DISPONIBLE
    if age_hours <= FRESHNESS_RECENT_HOURS:
        return STATUS_RECIENTE
    if age_hours <= FRESHNESS_DELAYED_HOURS:
        return STATUS_CON_RETRASO
    return STATUS_DESACTUALIZADO


def observation_from_snapshot(
    snapshot: DmcLiveSnapshot, now_utc: Optional[datetime] = None
) -> dict[str, Any]:
    """Convierte la última observación ingerida en el diccionario que consume la vista.

    El campo `momento` de getDatosRecientesEma viene en UTC (sin zona); se interpreta así.
    """
    now_utc = now_utc or datetime.now(timezone.utc)
    now_cl = now_utc.astimezone(CHILE_TZ)
    base: dict[str, Any] = {
        "ok": False,
        "status": STATUS_NO_DISPONIBLE,
        "temperatura_c": None,
        "humedad_pct": None,
        "viento_kmh": None,
        "viento_kt": None,
        "momento_utc": None,
        "momento_cl": None,
        "age_hours": None,
        "checked_at_cl": now_cl.strftime("%H:%M:%S"),
        "checked_at_utc": now_utc.strftime("%H:%M:%S UTC"),
        "estacion_id": snapshot.station_code,
        "estacion_nombre": RODELILLO_NOMBRE,
        "fuente": "Última ingesta del pipeline (data/raw)",
        "error": None,
    }
    if not snapshot.available or snapshot.momento is None:
        base["error"] = snapshot.detail
        return base

    dt_obs_utc = snapshot.momento.replace(tzinfo=timezone.utc)
    age_hours = max(0.0, (now_utc - dt_obs_utc).total_seconds() / 3600.0)
    viento_kmh = snapshot.velocidad_viento_kmh
    base.update(
        {
            "ok": True,
            "status": _classify_freshness(age_hours),
            "temperatura_c": snapshot.temperatura,
            "humedad_pct": snapshot.humedad_relativa,
            "viento_kmh": round(viento_kmh, 1) if viento_kmh is not None else None,
            "viento_kt": (
                round(viento_kmh / _KMH_PER_KT, 1) if viento_kmh is not None else None
            ),
            "momento_utc": dt_obs_utc.strftime("%d-%m-%Y %H:%M UTC"),
            "momento_cl": dt_obs_utc.astimezone(CHILE_TZ).strftime("%d-%m-%Y %H:%M %Z"),
            "age_hours": round(age_hours, 1),
        }
    )
    return base


def load_rodelillo_observation() -> dict[str, Any]:
    """Última observación de Rodelillo ya ingerida por el pipeline (sin red)."""
    return observation_from_snapshot(load_rodelillo_snapshot())


def reload_rodelillo_observation() -> dict[str, Any]:
    """Vuelve a leer `data/raw` (por si el pipeline dejó una ingesta más nueva)."""
    load_rodelillo_snapshot.cache_clear()
    return load_rodelillo_observation()

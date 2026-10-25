"""Consulta meteorológica en vivo de DMC Rodelillo (330007).

Módulo de solo lectura para la defensa del Sprint 2 (OCC-UI-DMC-LATEST-OBSERVATION).
Consulta la última observación disponible de la estación meteorológica automática (EMA)
Rodelillo (330007) de la Dirección Meteorológica de Chile (DMC).

Reglas de integridad y arquitectura:
- Consulta de solo lectura: NO escribe archivos de ingesta, snapshots ni punteros CURRENT.
- NO recalculación de ranking: las observaciones son informativas y no alteran los scores
  históricos del 01-09-2026.
- Secretos: las credenciales (DMC_USUARIO, DMC_TOKEN) se manejan exclusivamente en el
  servidor y se filtran de cualquier mensaje de error o representación pública.
- Caché controlada de 5 minutos (@st.cache_data(ttl=300)) con opción de refresco manual.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

import requests
import streamlit as st

RODELILLO_CODIGO = "330007"
RODELILLO_NOMBRE = "Rodelillo, Ad."
_TIMEOUT_SECONDS = 5
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


def _clean_float(valor: Optional[str]) -> Optional[float]:
    """Extrae el número de un string con unidad embebida (ej. '21.9 °C', '5.4 kt')."""
    if not valor or not isinstance(valor, str):
        return None
    match = re.search(r"[-+]?\d*\.?\d+", valor.replace(",", "."))
    return float(match.group()) if match else None


def _get_credentials() -> tuple[str, str, str]:
    """Obtiene credenciales y URL base de DMC sin exponerlas."""
    base_url = os.getenv("DMC_API_BASE_URL", "https://climatologia.meteochile.gob.cl")
    usuario = os.getenv("DMC_USUARIO", "")
    token = os.getenv("DMC_TOKEN", "")

    # Fallback a src.config si no están en os.environ directamente
    if not (usuario and token):
        try:
            import src.config as cfg

            usuario = usuario or getattr(cfg, "DMC_USUARIO", "")
            token = token or getattr(cfg, "DMC_TOKEN", "")
            base_url = getattr(cfg, "DMC_API_BASE_URL", base_url)
        except Exception:
            pass

    return base_url.rstrip("/"), usuario, token


def _sanitize_error(error_msg: str) -> str:
    """Elimina tokens, usuarios o URLs completas con query parameters de los errores."""
    cleaned = re.sub(r"(usuario|token)=[^\s&'\"]+", r"\1=***", str(error_msg))
    cleaned = re.sub(r"https?://[^\s'\"]+", "[URL_DMC]", cleaned)
    return cleaned


def _classify_freshness(age_hours: Optional[float]) -> str:
    """Clasifica el estado de frescura según umbrales operacionales explícitos."""
    if age_hours is None:
        return STATUS_NO_DISPONIBLE
    if age_hours <= FRESHNESS_RECENT_HOURS:
        return STATUS_RECIENTE
    if age_hours <= FRESHNESS_DELAYED_HOURS:
        return STATUS_CON_RETRASO
    return STATUS_DESACTUALIZADO


@st.cache_data(ttl=300, show_spinner=False)
def fetch_rodelillo_live(codigo: str = RODELILLO_CODIGO) -> dict[str, Any]:
    """Consulta la última observación DMC de forma segura y cacheada.

    Nunca lanza excepciones no controladas. Siempre retorna un diccionario con
    el estado, métricas y marcas de tiempo en hora local de Chile y UTC.
    """
    now_utc = datetime.now(timezone.utc)
    now_cl = now_utc.astimezone(CHILE_TZ)
    checked_cl = now_cl.strftime("%H:%M:%S")
    checked_utc = now_utc.strftime("%H:%M:%S UTC")

    base_url, usuario, token = _get_credentials()
    if not (usuario and token):
        return {
            "ok": False,
            "status": STATUS_NO_DISPONIBLE,
            "temperatura_c": None,
            "humedad_pct": None,
            "viento_kmh": None,
            "viento_kt": None,
            "momento_utc": None,
            "momento_cl": None,
            "age_hours": None,
            "checked_at_cl": checked_cl,
            "checked_at_utc": checked_utc,
            "estacion_id": codigo,
            "estacion_nombre": RODELILLO_NOMBRE,
            "error": "Credenciales DMC no configuradas en el servidor.",
        }

    try:
        url = f"{base_url}/application/servicios/getDatosRecientesEma/{codigo}"
        resp = requests.get(
            url,
            params={"usuario": usuario, "token": token},
            timeout=_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        payload = resp.json()
    except requests.exceptions.Timeout:
        return {
            "ok": False,
            "status": STATUS_NO_DISPONIBLE,
            "temperatura_c": None,
            "humedad_pct": None,
            "viento_kmh": None,
            "viento_kt": None,
            "momento_utc": None,
            "momento_cl": None,
            "age_hours": None,
            "checked_at_cl": checked_cl,
            "checked_at_utc": checked_utc,
            "estacion_id": codigo,
            "estacion_nombre": RODELILLO_NOMBRE,
            "error": f"Tiempo de espera agotado ({_TIMEOUT_SECONDS}s) al consultar DMC.",
        }
    except requests.exceptions.RequestException as exc:
        return {
            "ok": False,
            "status": STATUS_NO_DISPONIBLE,
            "temperatura_c": None,
            "humedad_pct": None,
            "viento_kmh": None,
            "viento_kt": None,
            "momento_utc": None,
            "momento_cl": None,
            "age_hours": None,
            "checked_at_cl": checked_cl,
            "checked_at_utc": checked_utc,
            "estacion_id": codigo,
            "estacion_nombre": RODELILLO_NOMBRE,
            "error": f"Error de conexión con DMC: {_sanitize_error(str(exc))}",
        }
    except ValueError as exc:
        return {
            "ok": False,
            "status": STATUS_NO_DISPONIBLE,
            "temperatura_c": None,
            "humedad_pct": None,
            "viento_kmh": None,
            "viento_kt": None,
            "momento_utc": None,
            "momento_cl": None,
            "age_hours": None,
            "checked_at_cl": checked_cl,
            "checked_at_utc": checked_utc,
            "estacion_id": codigo,
            "estacion_nombre": RODELILLO_NOMBRE,
            "error": "Respuesta no válida de DMC (formato JSON no reconocido).",
        }

    datos = payload.get("datosEstaciones", {}).get("datos", [])
    if not isinstance(datos, list) or not datos:
        return {
            "ok": False,
            "status": STATUS_NO_DISPONIBLE,
            "temperatura_c": None,
            "humedad_pct": None,
            "viento_kmh": None,
            "viento_kt": None,
            "momento_utc": None,
            "momento_cl": None,
            "age_hours": None,
            "checked_at_cl": checked_cl,
            "checked_at_utc": checked_utc,
            "estacion_id": codigo,
            "estacion_nombre": RODELILLO_NOMBRE,
            "error": "Respuesta de DMC recibida sin registros meteorológicos.",
        }

    reciente = datos[0]
    temp = _clean_float(reciente.get("temperatura"))
    hum = _clean_float(reciente.get("humedadRelativa"))
    viento_kt = _clean_float(reciente.get("fuerzaDelViento"))
    viento_kmh = round(viento_kt * 1.852, 1) if viento_kt is not None else None

    # Parseo de fecha/hora de la observación
    momento_raw = reciente.get("momento")
    momento_utc_str = None
    momento_cl_str = None
    age_hours = None

    if momento_raw:
        try:
            # En la API DMC getDatosRecientesEma, momento es UTC
            dt_obs_utc = datetime.strptime(str(momento_raw).strip(), "%Y-%m-%d %H:%M:%S").replace(
                tzinfo=timezone.utc
            )
            dt_obs_cl = dt_obs_utc.astimezone(CHILE_TZ)
            momento_utc_str = dt_obs_utc.strftime("%d-%m-%Y %H:%M UTC")
            momento_cl_str = dt_obs_cl.strftime("%d-%m-%Y %H:%M %Z")
            age_hours = max(0.0, (now_utc - dt_obs_utc).total_seconds() / 3600.0)
        except ValueError:
            momento_utc_str = str(momento_raw)
            momento_cl_str = str(momento_raw)

    status = _classify_freshness(age_hours)

    if temp is None and hum is None:
        return {
            "ok": False,
            "status": STATUS_NO_DISPONIBLE,
            "temperatura_c": None,
            "humedad_pct": None,
            "viento_kmh": None,
            "viento_kt": None,
            "momento_utc": momento_utc_str,
            "momento_cl": momento_cl_str,
            "age_hours": age_hours,
            "checked_at_cl": checked_cl,
            "checked_at_utc": checked_utc,
            "estacion_id": codigo,
            "estacion_nombre": RODELILLO_NOMBRE,
            "error": "Variables meteorológicas principales no informadas en el registro.",
        }

    return {
        "ok": True,
        "status": status,
        "temperatura_c": temp,
        "humedad_pct": hum,
        "viento_kmh": viento_kmh,
        "viento_kt": viento_kt,
        "momento_utc": momento_utc_str,
        "momento_cl": momento_cl_str,
        "age_hours": round(age_hours, 1) if age_hours is not None else None,
        "checked_at_cl": checked_cl,
        "checked_at_utc": checked_utc,
        "estacion_id": codigo,
        "estacion_nombre": RODELILLO_NOMBRE,
        "error": None,
    }


def refresh_rodelillo_live(codigo: str = RODELILLO_CODIGO) -> dict[str, Any]:
    """Limpia la caché de 5 min y fuerza una nueva consulta a DMC."""
    fetch_rodelillo_live.clear()
    return fetch_rodelillo_live(codigo)

"""Clima en vivo de la estación DMC 330007 (Rodelillo).

Card independiente del sistema de riesgo por celdas (demo_seed) — NO se
mezcla con top_risk_cell(), format_top_risk_banner_html() ni ningún cálculo
de nivel_riesgo/probabilidad. Es puramente informativo.

No importa nada de src.ingesta ni src.procesamiento a propósito: el Data
Contract del proyecto prohíbe que app/ importe esos módulos (ver
tests/test_architecture.py). parallel_ingester._ingest_dmc ya sabe hablar
con getDatosRecientesEma, pero está pensado para ingesta batch (escribe a
archivo, itera todas las estaciones, cae a staging PostGIS si falla —
inexistente en modo demo_seed) con un timeout de 30s sin reintentos reales
pese a su docstring. Nada de eso sirve para una tarjeta síncrona en la
carga de la página, así que el request y el parseo se reimplementan acá,
chico y propio — mismo contrato de URL y misma conversión de unidades
(kt→km/h) que ya documenta src/config.py, sin importar el módulo real.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Optional

import requests
import streamlit as st

from src.config import DMC_API_BASE_URL, DMC_TOKEN, DMC_USUARIO

RODELILLO_CODIGO = "330007"
_TIMEOUT_SECONDS = 5  # no el default de requests (sin límite) — ver hallazgo 05-09-2026


def _clean_float(valor: Optional[str]) -> Optional[float]:
    """Extrae el número de un string con unidad embebida (ej. "22.1 °C")."""
    if not valor or not isinstance(valor, str):
        return None
    match = re.search(r"[-+]?\d*\.?\d+", valor.replace(",", "."))
    return float(match.group()) if match else None


@st.cache_data(ttl=300, show_spinner=False)
def fetch_rodelillo_live(codigo: str = RODELILLO_CODIGO) -> dict[str, Any]:
    """Consulta getDatosRecientesEma en vivo para una estación DMC.

    Nunca lanza: cualquier fallo (credenciales ausentes, timeout, red,
    HTTP de error, JSON o estructura inesperada) vuelve como
    ``{"ok": False, "error": ...}`` — la tarjeta se renderiza siempre, con
    dato real o con aviso de error, nunca con un traceback ni la página
    cargando indefinidamente.

    Cacheado 5 minutos (``@st.cache_data(ttl=300)``): Streamlit re-ejecuta
    ``main()`` completo en cada rerun (cambiar de fecha, clic en el mapa,
    etc.), no solo al cargar la página una vez — sin este TTL, esos reruns
    golpearían la API de DMC en cada interacción del usuario. Efecto
    secundario conocido y aceptado: si la API falla, ese resultado también
    queda cacheado 5 minutos — no hay botón manual para forzar un reintento
    antes de que venza el TTL (decisión de producto, no técnica, 05-09-2026).
    """
    checked_at = datetime.now().strftime("%H:%M:%S")
    if not (DMC_USUARIO and DMC_TOKEN):
        return {
            "ok": False,
            "error": "DMC_USUARIO / DMC_TOKEN no configurados (ver src/config.py)",
            "checked_at": checked_at,
        }
    try:
        response = requests.get(
            f"{DMC_API_BASE_URL}/application/servicios/getDatosRecientesEma/{codigo}",
            params={"usuario": DMC_USUARIO, "token": DMC_TOKEN},
            timeout=_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.exceptions.Timeout:
        return {
            "ok": False,
            "error": f"Tiempo de espera agotado ({_TIMEOUT_SECONDS}s) consultando DMC",
            "checked_at": checked_at,
        }
    except requests.exceptions.RequestException as exc:
        return {"ok": False, "error": f"Error de red consultando DMC: {exc}", "checked_at": checked_at}
    except ValueError as exc:  # respuesta 200 pero JSON inválido
        return {"ok": False, "error": f"Respuesta de DMC no es JSON válido: {exc}", "checked_at": checked_at}

    datos = payload.get("datosEstaciones", {}).get("datos", [])
    if not isinstance(datos, list) or not datos:
        return {"ok": False, "error": "Respuesta de DMC sin registros", "checked_at": checked_at}

    # La API entrega el registro más reciente primero (verificado 05-09-2026
    # contra la estación 330007: datos[0]["momento"] > datos[-1]["momento"]).
    reciente = datos[0]
    temperatura = _clean_float(reciente.get("temperatura"))
    humedad = _clean_float(reciente.get("humedadRelativa"))
    viento_kt = _clean_float(reciente.get("fuerzaDelViento"))

    if temperatura is None or humedad is None:
        return {
            "ok": False,
            "error": "Campos de temperatura/humedad ausentes o ilegibles en la respuesta de DMC",
            "checked_at": checked_at,
        }

    return {
        "ok": True,
        "temperatura_c": temperatura,
        "humedad_pct": humedad,
        "viento_kmh": round(viento_kt * 1.852, 1) if viento_kt is not None else None,
        "momento": reciente.get("momento"),
        "checked_at": checked_at,
    }

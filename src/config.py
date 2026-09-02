"""Configuración centralizada del sistema S.A.P.I."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql://sapi:sapi_secret@localhost:5432/sapi_db",
)
DATABASE_URL_DIRECT: str = os.getenv("DATABASE_URL_DIRECT", DATABASE_URL)

NASA_FIRMS_API_KEY: str = os.getenv("NASA_FIRMS_API_KEY", "")
DMC_API_BASE_URL: str = os.getenv(
    "DMC_API_BASE_URL",
    "https://climatologia.meteochile.gob.cl",
)
# Contrato API DMC — getDatosRecientesEma (validado spike 30-08-2026, estación 330007).
#
# Reciente (últimas ~12 h, ingesta diaria en parallel_ingester._ingest_dmc):
#   GET {DMC_API_BASE_URL}/application/servicios/getDatosRecientesEma/{codigoEstacion}
#       ?usuario={DMC_USUARIO}&token={DMC_TOKEN}
#
# Histórico mensual (SAPI-28 opción B; muestra en data/raw/dmc_historico_330007_2025-02.json):
#   GET {DMC_API_BASE_URL}/application/servicios/getDatosRecientesEma/{codigoEstacion}/{año}/{mes}
#       ?usuario={DMC_USUARIO}&token={DMC_TOKEN}
#   Cadencia: lecturas cada ~15 min del mes solicitado (doc. MeteoChile getDocumento/2).
#   Nota: el campo JSON "producto" puede seguir diciendo "últimas 12 horas" aunque el
#   payload sea histórico mensual; confiar en "momento" de cada fila, no en ese texto.
#
# Estructura de respuesta (misma forma reciente e histórico):
#   raíz: organismo, pais, fechaCreacion, timezone, producto, registros (int = conteo),
#         status, datosEstaciones{ estacion{...}, datos[...] }
#   Cada elemento de datosEstaciones.datos[] incluye, entre otros:
#     momento          -> "YYYY-MM-DD HH:MM:SS" (UTC según timezone de cabecera)
#     temperatura      -> string con unidad, ej. "18.8 °C"
#     humedadRelativa  -> string con unidad, ej. "72 %"
#     fuerzaDelViento  -> string con unidad, ej. "8.5 kt"
#     presionEstacion  -> string con unidad, ej. "973.7 hPas."
#     (más campos opcionales/null: temperatura02Mts, aguaCaidaDelMinuto, etc.)
#
# Los valores meteorológicos vienen como strings con unidad embebida, NO como float.
# Requieren parseo numérico antes de cualquier comparación (p. ej. regla 30-30-30:
# T>30°C, HR<30%, viento>30 km/h). Ver src/procesamiento/raw_parser._clean_float.
#
# Archivos raw multi-estación (ingesta diaria) usan dict por código:
#   {"330007": {<respuesta API>}, "330004": {...}, ...}
# El histórico de muestra sigue el mismo envoltorio para compatibilidad con raw_parser.
#
# La API de climatología DMC autentica por querystring (?usuario=...&token=...),
# no por header. Registro en: https://climatologia.meteochile.gob.cl/application/usuario/registroUsuario
DMC_USUARIO: str = os.getenv("DMC_USUARIO", "")
DMC_TOKEN: str = os.getenv("DMC_TOKEN", "")
CONAF_DATA_URL: str = os.getenv("CONAF_DATA_URL", "https://www.conaf.cl")

# DEM (Copernicus GLO-30) vía OpenTopography — API_Key gratuita, ver .env.
# Contrato: GET https://portal.opentopography.org/API/globaldem
#   ?demtype=COP30&south=..&north=..&west=..&east=..&outputFormat=GTiff&API_Key=..
# Verificado 2026-09-01 contra opentopography.org/developers y el código
# fuente de bmi-topography (demtype COP30 confirmado como código válido).
OPENTOPO_API_KEY: str = os.getenv("OPENTOPO_API_KEY", "")
OPENTOPO_DEM_TYPE: str = os.getenv("OPENTOPO_DEM_TYPE", "COP30")
# Límites del tier gratuito (no-académico), mismo chequeo del 2026-09-01:
OPENTOPO_MAX_AREA_KM2 = 450
OPENTOPO_DAILY_CALL_LIMIT = 50

DATA_RAW_DIR: Path = BASE_DIR / os.getenv("DATA_RAW_DIR", "data/raw")
DATA_PROCESSED_DIR: Path = BASE_DIR / os.getenv("DATA_PROCESSED_DIR", "data/processed")
DATA_PREDICTIONS_DIR: Path = BASE_DIR / os.getenv("DATA_PREDICTIONS_DIR", "data/predictions")
MODELS_DIR: Path = BASE_DIR / os.getenv("MODELS_DIR", "models")

CACHE_CONTINGENCY_DAYS: int = int(os.getenv("CACHE_CONTINGENCY_DAYS", "7"))
GRID_CELL_SIZE_KM: float = float(os.getenv("GRID_CELL_SIZE_KM", "1.0"))
GRID_MAX_CELLS: int = int(os.getenv("GRID_MAX_CELLS", "50") or "50")
CONAF_SEED_PATH: Path = BASE_DIR / os.getenv("CONAF_SEED_PATH", "data/raw/conaf_historico_seed.json")

VALPARAISO_BBOX = {
    "min_lon": -71.75,
    "max_lon": -70.25,
    "min_lat": -33.65,
    "max_lat": -32.00,
}

# Bbox acotado exclusivo para el DEM (Copernicus GLO-30 / COP30).
# NO reusar VALPARAISO_BBOX de arriba: cubre ~25.500 km², muy por encima
# del límite de OPENTOPO_MAX_AREA_KM2 (450 km²) por llamada del tier
# gratuito de OpenTopography para datasets de 30m — la llamada fallaría.
# Este bbox cubre el corredor de interfaz urbano-forestal del portafolio
# (Viña del Mar, Quilpué, Villa Alemana) con margen, dentro del límite:
#   ancho ≈ 23 km × alto ≈ 17 km ≈ 390 km² (< 450 km²), una sola llamada.
# Centros de comuna de referencia (búsqueda geográfica, 2026-09-01):
# Viña del Mar (-33.02451, -71.55181), Villa Alemana (-33.04419, -71.37255);
# Quilpué queda geográficamente entre ambas. No se verificó el límite
# administrativo exacto de cada comuna, solo que sus centros y un margen
# de ~3 km alrededor quedan cubiertos.
VALPARAISO_DEM_BBOX = {
    "min_lon": -71.59,
    "max_lon": -71.34,
    "min_lat": -33.11,
    "max_lat": -32.96,
}

# Códigos de estación DMC confirmados contra getCatastroEstacionesGeo
# (consultado 2026-08-29, ver .env para credenciales). El catastro real
# devuelve 77 estaciones con numeroRegion=5 (Valparaíso); de esas, se
# tomó una por cada comuna del corredor de interfaz urbano-forestal que
# define el portafolio (Alcances Técnicos: Viña del Mar, Quilpué, Villa
# Alemana) — verificado que las 3 comunas objetivo quedan cubiertas
# exactamente, sin solapamiento. Cada comuna tenía más de una estación
# disponible; esta es una selección razonable, no la única válida —
# no se verificó elevación real ni cercanía exacta a zona de interfaz
# de cada estación individual, solo pertenencia a la comuna correcta.
# Si se requiere mayor densidad espacial, ampliar desde el catastro completo.
DMC_ESTACIONES_VALPARAISO: list[str] = [
    s for s in os.getenv("DMC_ESTACIONES_VALPARAISO", "").split(",") if s
]

RISK_THRESHOLDS = {"bajo": 0.33, "medio": 0.66, "alto": 1.0}

# Modo de datos del dashboard (SAPI-44). Valores soportados:
#   demo_seed         — escenario sembrado en memoria (Hito 1 / demo académica)
#   postgis_inference — predicciones desde PostGIS + inference_engine (Sprint 2)
SAPI_DATA_MODE: str = os.getenv("SAPI_DATA_MODE", "demo_seed").strip() or "demo_seed"


def get_backend_database_url() -> str:
    """Retorna URL de conexión directa para procesos batch e ingesta."""
    return DATABASE_URL_DIRECT or DATABASE_URL

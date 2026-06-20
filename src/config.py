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
CONAF_DATA_URL: str = os.getenv("CONAF_DATA_URL", "https://www.conaf.cl")

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

RISK_THRESHOLDS = {"bajo": 0.33, "medio": 0.66, "alto": 1.0}


def get_backend_database_url() -> str:
    """Retorna URL de conexión directa para procesos batch e ingesta."""
    return DATABASE_URL_DIRECT or DATABASE_URL

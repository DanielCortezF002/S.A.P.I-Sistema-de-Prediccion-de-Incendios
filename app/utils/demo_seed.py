"""Generador in-memory del seed demo: 50 celdas × N días sin PostGIS.

Replica la lógica de scripts/generate_seed.py usando Shapely + GeoPandas,
de modo que el dashboard funcione en modo demo sin Docker ni base de datos.
"""

from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

# ──────────────────────────────────────────────
# Parámetros de grilla (alineados con generate_seed.py)
# ──────────────────────────────────────────────
BASE_LON = -71.535
BASE_LAT = -33.062
COLS = 10
ROWS = 5
STEP_LON = 0.010
STEP_LAT = 0.009
DEMO_START = date(2025, 2, 9)
DEMO_END = date(2025, 2, 15)
DEMO_DAYS = (DEMO_END - DEMO_START).days + 1
REGLA_CELLS = (38, 49)

ZONAS: dict[str, dict[str, tuple[float, float]]] = {
    "costa":          {"temp": (16.0, 23.0), "hr": (62.0, 88.0), "viento": (18.0, 38.0)},
    "urbano":         {"temp": (19.0, 27.0), "hr": (42.0, 62.0), "viento": (8.0,  28.0)},
    "precordillera":  {"temp": (22.0, 31.0), "hr": (22.0, 48.0), "viento": (6.0,  35.0)},
}


# ──────────────────────────────────────────────
# Helpers (copiados de generate_seed.py)
# ──────────────────────────────────────────────

def _zone_for_col(col: int) -> str:
    if col <= 1:
        return "costa"
    if col <= 6:
        return "urbano"
    return "precordillera"


def _day_progress(day_index: int) -> float:
    if DEMO_DAYS <= 1:
        return 1.0
    return day_index / (DEMO_DAYS - 1)


def _interp(zone: str, col: int, spread: float, progress: float) -> tuple[float, float, float]:
    z = ZONAS[zone]
    t_mid = (z["temp"][0] + z["temp"][1]) / 2
    h_mid = (z["hr"][0] + z["hr"][1]) / 2
    t = t_mid + spread + progress * 4.0
    h = h_mid - spread * 2 - progress * 12.0
    w = (z["viento"][0] + z["viento"][1]) / 2 + col * 0.4 + progress * 3.0
    t = max(z["temp"][0], min(z["temp"][1], round(t, 1)))
    h = max(z["hr"][0],   min(z["hr"][1],   round(h, 1)))
    w = max(z["viento"][0], min(z["viento"][1], round(w, 1)))
    return t, h, w


def _regla_30_30_30(temp: float, hr: float, viento: float) -> int:
    return 1 if temp > 30 and hr < 30 and viento > 30 else 0


def _nivel(prob: float) -> str:
    if prob < 0.33:
        return "bajo"
    if prob < 0.66:
        return "medio"
    return "alto"


def _prob_from_meteo(temp: float, hr: float, viento: float, regla: int, zone: str) -> float:
    if regla:
        return 0.97
    base = {"costa": 0.20, "urbano": 0.44, "precordillera": 0.58}
    score = base[zone]
    score += max(0, (temp - 20) / 120)
    score += max(0, (48 - hr) / 250)
    score += min(0.06, viento / 400)
    caps = {"costa": 0.32, "urbano": 0.62, "precordillera": 0.64}
    return round(min(caps[zone], max(0.10, score)), 2)


# ──────────────────────────────────────────────
# Generación principal
# ──────────────────────────────────────────────

def _build_point_geometry(lon: float, lat: float) -> Point:
    """Punto central de la celda (Shapely Point en EPSG:4326)."""
    return Point(lon, lat)


def _generate_rows_for_day(fecha: date, day_index: int) -> list[dict]:
    """Genera 50 filas de datos para un día, devuelve lista de dicts."""
    progress = _day_progress(day_index)
    is_peak = fecha == DEMO_END
    rows: list[dict] = []
    idx = 1
    for row in range(ROWS):
        for col in range(COLS):
            zone = _zone_for_col(col)
            lon = round(BASE_LON + col * STEP_LON, 5)
            lat = round(BASE_LAT + row * STEP_LAT, 5)
            spread = (row - ROWS / 2) * 0.12
            temp, hr, viento = _interp(zone, col, spread, progress)

            if is_peak and idx in REGLA_CELLS:
                temp, hr, viento = 32.5, 24.0, 34.0

            regla = _regla_30_30_30(temp, hr, viento)
            prob = _prob_from_meteo(temp, hr, viento, regla, zone)

            # 2025-02-09: día base — todos los radios en verde (bajo riesgo)
            if day_index == 0:
                prob = round(min(0.30, prob * 0.40), 2)
                regla = 0

            nivel = _nivel(prob)
            cell_id = f"VP-{idx:03d}"

            rows.append({
                "cell_id":          cell_id,
                "fecha":            fecha,
                "probabilidad":     prob,
                "nivel_riesgo":     nivel,
                "temperatura":      temp,
                "humedad_relativa": hr,
                "velocidad_viento": viento,
                "regla_30_30_30":   regla,
                "modelo_version":   "demo-seed-v1",
                "geometry":         _build_point_geometry(lon, lat),
            })
            idx += 1
    return rows


@lru_cache(maxsize=DEMO_DAYS + 1)
def get_demo_gdf(fecha: date | None = None) -> gpd.GeoDataFrame:
    """Devuelve GeoDataFrame sintético para la fecha solicitada.

    Si la fecha no está en la ventana demo, usa DEMO_END (día más crítico).
    Resultado cacheado por fecha para no recalcular en cada rerun de Streamlit.
    """
    target = fecha if fecha is not None else DEMO_END
    if not (DEMO_START <= target <= DEMO_END):
        target = DEMO_END

    day_index = (target - DEMO_START).days
    rows = _generate_rows_for_day(target, day_index)
    df = pd.DataFrame(rows)
    gdf = gpd.GeoDataFrame(df, geometry="geometry", crs="EPSG:4326")
    return gdf


def get_all_demo_dates() -> list[date]:
    """Lista de fechas disponibles en el seed demo."""
    return [DEMO_START + timedelta(days=i) for i in range(DEMO_DAYS)]

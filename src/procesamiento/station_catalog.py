"""Catálogo de estaciones DMC del corredor Valparaíso y utilidades geográficas."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

from src.config import DMC_ESTACIONES_VALPARAISO

# Coordenadas WGS84 desde getCatastroEstacionesGeo (sesión 2026-08-29, región 5).
# 330007 verificado también en datosEstaciones.estacion del histórico feb-2025.
_CATASTRO_COORDS: dict[str, tuple[str, float, float]] = {
    "330004": ("Quilpué", -33.04722, -71.45861),
    "330005": ("Villa Alemana", -33.04583, -71.37139),
    "330007": ("Rodelillo, Ad.", -33.06528, -71.55639),
}

@dataclass(frozen=True)
class DmcStation:
    """Estación automática DMC con posición para join espacial."""

    codigo: str
    nombre: str
    latitud: float
    longitud: float


def default_station_catalog() -> dict[str, DmcStation]:
    """Catálogo de estaciones configuradas en DMC_ESTACIONES_VALPARAISO."""
    catalog: dict[str, DmcStation] = {}
    for codigo in DMC_ESTACIONES_VALPARAISO:
        if codigo in _CATASTRO_COORDS:
            nombre, lat, lon = _CATASTRO_COORDS[codigo]
            catalog[codigo] = DmcStation(codigo=codigo, nombre=nombre, latitud=lat, longitud=lon)
    return catalog


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia geodésica aproximada en kilómetros (WGS84)."""
    radius_km = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * radius_km * math.asin(math.sqrt(a))


def select_nearest_station(
    lat: float,
    lon: float,
    candidate_codes: Iterable[str],
    catalog: dict[str, DmcStation],
) -> tuple[str, float]:
    """Elige estación más cercana entre candidatos con datos para el mes.

    Desempate: si dos estaciones tienen la misma distancia Haversine (±1 mm),
    gana la de menor ``codigo`` lexicográfico (p. ej. 330004 antes que 330007).
    """
    scored: list[tuple[float, str]] = []
    for codigo in candidate_codes:
        station = catalog.get(codigo)
        if station is None:
            continue
        dist = haversine_km(lat, lon, station.latitud, station.longitud)
        scored.append((dist, codigo))

    if not scored:
        raise ValueError("candidate_codes vacío o sin entradas en catálogo")

    dist, codigo = min(scored, key=lambda item: (round(item[0], 9), item[1]))
    return codigo, dist

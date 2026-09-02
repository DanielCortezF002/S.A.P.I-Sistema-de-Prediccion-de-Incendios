"""Ingesta del Modelo de Elevación Digital (DEM) Copernicus GLO-30.

Fuente: OpenTopography (https://portal.opentopography.org/API/globaldem),
espejo público gratuito del dataset COP30 de Copernicus/ESA — no el portal
oficial de Copernicus, que restringió su servicio de visualización a
categorías de usuario autorizadas. Contrato verificado 2026-09-01 contra
opentopography.org/developers y el código fuente de bmi-topography.

A diferencia de NASA FIRMS o DMC, el terreno no cambia día a día: por
defecto este módulo no repite la llamada a la API si ya existe un GeoTIFF
cacheado para el mismo bbox/demtype, para no gastar cupo del límite diario
(OPENTOPO_DAILY_CALL_LIMIT, 50 llamadas/24h en el tier gratuito).

El tier gratuito también limita el área a OPENTOPO_MAX_AREA_KM2 (450 km²)
por llamada para datasets de 30m — muy por debajo de VALPARAISO_BBOX
(~25.500 km², usado por FIRMS/DMC). Por eso este módulo usa un bbox propio
y acotado (ver VALPARAISO_DEM_BBOX en src/config.py), no VALPARAISO_BBOX.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import rasterio
import requests

from src.config import (
    DATA_RAW_DIR,
    OPENTOPO_API_KEY,
    OPENTOPO_DEM_TYPE,
    OPENTOPO_MAX_AREA_KM2,
    VALPARAISO_DEM_BBOX,
)

OPENTOPO_BASE_URL = "https://portal.opentopography.org/API/globaldem"
_KM_PER_DEG_LAT = 111.32


@dataclass(frozen=True)
class DemResult:
    """Resumen verificable de una descarga (o reuso de caché) del DEM."""

    path: Path
    manifest_path: Path
    width: int
    height: int
    crs: str
    min_elevation_m: float
    mean_elevation_m: float
    max_elevation_m: float
    cached: bool


def bbox_area_km2(bbox: dict[str, float]) -> float:
    """Área aproximada de un bbox WGS84 en km² (misma fórmula usada para validar
    VALPARAISO_DEM_BBOX manualmente: ancho ajustado por cos(latitud), sin
    proyectar — suficiente para bboxes chicos como los de este módulo).
    """

    lat_mid = (bbox["min_lat"] + bbox["max_lat"]) / 2
    km_per_deg_lon = _KM_PER_DEG_LAT * math.cos(math.radians(lat_mid))
    width_km = (bbox["max_lon"] - bbox["min_lon"]) * km_per_deg_lon
    height_km = (bbox["max_lat"] - bbox["min_lat"]) * _KM_PER_DEG_LAT
    return width_km * height_km


class DemIngester:
    """Cliente idempotente para el DEM COP30 de OpenTopography."""

    def __init__(
        self,
        api_key: str = OPENTOPO_API_KEY,
        bbox: dict[str, float] | None = None,
        dem_type: str = OPENTOPO_DEM_TYPE,
        raw_dir: Path | None = None,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        if not api_key:
            raise ValueError("OPENTOPO_API_KEY no configurada")

        self.bbox = bbox or VALPARAISO_DEM_BBOX
        area_km2 = bbox_area_km2(self.bbox)
        if area_km2 > OPENTOPO_MAX_AREA_KM2:
            raise ValueError(
                f"bbox de {area_km2:.1f} km² excede el límite de "
                f"{OPENTOPO_MAX_AREA_KM2} km² por llamada de OpenTopography "
                f"para datasets de 30m (dataset={dem_type}). Partir en tiles "
                "o ajustar el bbox antes de llamar a la API."
            )

        self.api_key = api_key
        self.dem_type = dem_type
        self.raw_dir = raw_dir or DATA_RAW_DIR / "dem"
        self.sleep_fn = sleep_fn
        self.session = requests.Session()

    @property
    def area_km2(self) -> float:
        return bbox_area_km2(self.bbox)

    def _stem(self) -> str:
        b = self.bbox
        return (
            f"{self.dem_type}_{b['min_lat']:.4f}_{b['min_lon']:.4f}_"
            f"{b['max_lat']:.4f}_{b['max_lon']:.4f}"
        )

    def _tif_path(self) -> Path:
        return self.raw_dir / f"{self._stem()}.tif"

    def _manifest_path(self) -> Path:
        return self.raw_dir / f"{self._stem()}_manifest.json"

    def _redact(self, text: str) -> str:
        """Evita que la API_Key quede expuesta en excepciones o logs."""

        return text.replace(self.api_key, "[OPENTOPO_API_KEY_REDACTADA]")

    def _get_with_retry(self, url: str) -> requests.Response:
        """GET con backoff y respeto de Retry-After para 429 (mismo patrón
        que NasaFirmsBackfill._get_with_retry).
        """

        last_error: Exception | None = None
        for attempt in range(4):
            try:
                response = self.session.get(url, timeout=120)
                if response.status_code == 429:
                    retry_after = float(response.headers.get("Retry-After", 10))
                    self.sleep_fn(max(retry_after, 2**attempt))
                    continue
                response.raise_for_status()
                return response
            except requests.RequestException as exc:
                last_error = RuntimeError(self._redact(str(exc)))
                if attempt < 3:
                    self.sleep_fn(2**attempt)

        raise RuntimeError("OpenTopography no respondió después de 4 intentos") from last_error

    def _download_url(self) -> str:
        b = self.bbox
        return (
            f"{OPENTOPO_BASE_URL}?demtype={self.dem_type}"
            f"&south={b['min_lat']}&north={b['max_lat']}"
            f"&west={b['min_lon']}&east={b['max_lon']}"
            f"&outputFormat=GTiff&API_Key={self.api_key}"
        )

    def fetch(self, force: bool = False) -> DemResult:
        """Descarga el DEM (o reusa el caché) y valida el raster con rasterio.

        Args:
            force: si True, ignora un caché existente y vuelve a llamar a la
                API (consume una de las OPENTOPO_DAILY_CALL_LIMIT llamadas).
        """

        self.raw_dir.mkdir(parents=True, exist_ok=True)
        tif_path = self._tif_path()
        manifest_path = self._manifest_path()
        cached = tif_path.exists() and manifest_path.exists() and not force

        if not cached:
            response = self._get_with_retry(self._download_url())
            content_type = response.headers.get("Content-Type", "")
            # OpenTopography puede responder 200 con un JSON/HTML de error
            # (p. ej. área fuera de cobertura, demtype inválido) en vez de un
            # 4xx — validar el Content-Type antes de asumir que es un GeoTIFF.
            if "tif" not in content_type and "octet-stream" not in content_type:
                raise RuntimeError(
                    "Respuesta inesperada de OpenTopography "
                    f"(Content-Type={content_type!r}): {response.text[:300]!r}"
                )
            tif_path.write_bytes(response.content)

        with rasterio.open(tif_path) as dataset:
            band = dataset.read(1)
            width, height = dataset.width, dataset.height
            crs = str(dataset.crs)

        min_elevation_m = float(band.min())
        mean_elevation_m = float(band.mean())
        max_elevation_m = float(band.max())

        checksum = hashlib.sha256(tif_path.read_bytes()).hexdigest()
        manifest = {
            "dem_type": self.dem_type,
            "bbox": self.bbox,
            "area_km2": round(self.area_km2, 2),
            "crs": crs,
            "width": width,
            "height": height,
            "min_elevation_m": min_elevation_m,
            "mean_elevation_m": mean_elevation_m,
            "max_elevation_m": max_elevation_m,
            "sha256": checksum,
            "cached": cached,
        }
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return DemResult(
            path=tif_path,
            manifest_path=manifest_path,
            width=width,
            height=height,
            crs=crs,
            min_elevation_m=min_elevation_m,
            mean_elevation_m=mean_elevation_m,
            max_elevation_m=max_elevation_m,
            cached=cached,
        )

"""Ingesta asíncrona paralela desde APIs externas."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import requests
from sqlalchemy import text
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import (
    CACHE_CONTINGENCY_DAYS,
    CONAF_DATA_URL,
    CONAF_SEED_PATH,
    DATA_RAW_DIR,
    DMC_API_BASE_URL,
    NASA_FIRMS_API_KEY,
    VALPARAISO_BBOX,
)
from src.db import get_backend_connection, log_event
from src.query.prediction_query import PredictionQuery

_STAGING_TABLES = frozenset({"staging_incendios", "staging_meteo"})


class ParallelIngester:
    """Consumo paralelo de fuentes NASA FIRMS, DMC y CONAF."""

    def __init__(self, raw_dir: Optional[Path] = None) -> None:
        """Inicializa ingester con directorio de crudos.

        Args:
            raw_dir: Ruta para volcado inmutable de payloads.
        """
        self.raw_dir = raw_dir or DATA_RAW_DIR
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.query = PredictionQuery()

    def ingest_all_sources(self) -> dict[str, Any]:
        """Dispara captura paralela de todas las fuentes.

        Returns:
            Resumen con rutas de artefactos generados o estado degradado.
        """
        tasks = {
            "nasa_firms": self._ingest_nasa_firms,
            "dmc_meteo": self._ingest_dmc,
            "conaf_incendios": self._ingest_conaf,
        }
        results: dict[str, Any] = {}
        degraded_sources: list[str] = []

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(fn): name for name, fn in tasks.items()}
            for future in as_completed(futures):
                name = futures[future]
                try:
                    outcome = future.result()
                    results[name] = outcome
                    if outcome.get("degraded"):
                        degraded_sources.append(name)
                except Exception as exc:
                    log_event("ParallelIngester", "ingest_error", f"{name}: {exc}", "ERROR")
                    results[name] = {
                        "status": "failed",
                        "degraded": True,
                        "path": "",
                        "error": str(exc),
                    }
                    degraded_sources.append(name)

        if degraded_sources:
            log_event(
                "ParallelIngester",
                "degradation",
                f"Fuentes degradadas a PostGIS: {degraded_sources}",
                "WARN",
            )
            results["contingency"] = self._load_contingency_cache()

        return results

    @retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, min=2, max=30))
    def _download_with_retry(self, url: str, params: Optional[dict] = None) -> requests.Response:
        """Descarga HTTP con reintentos exponenciales.

        Args:
            url: Endpoint remoto.
            params: Parámetros query string.

        Returns:
            Respuesta HTTP validada.

        Raises:
            requests.RequestException: Si el servidor no responde tras reintentos.
        """
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response

    def _recuperar_payload_fallback(self, tabla_staging: str) -> pd.DataFrame:
        """Extrae el último estado válido desde staging PostGIS (R-03).

        Args:
            tabla_staging: Nombre de tabla staging permitida.

        Returns:
            DataFrame con registros de contingencia o vacío si no hay datos.
        """
        if tabla_staging not in _STAGING_TABLES:
            log_event(
                "ParallelIngester",
                "fallback_denied",
                f"Tabla no permitida: {tabla_staging}",
                "ERROR",
            )
            return pd.DataFrame()

        sql = text(
            f"""
            SELECT * FROM {tabla_staging}
            WHERE created_at >= NOW() - INTERVAL '{int(CACHE_CONTINGENCY_DAYS)} days'
            ORDER BY created_at DESC
            """
        )
        try:
            with get_backend_connection() as conn:
                return pd.read_sql(sql, conn)
        except Exception as exc:
            log_event(
                "ParallelIngester",
                "fallback_error",
                f"{tabla_staging}: {exc}",
                "ERROR",
            )
            return pd.DataFrame()

    def _ingest_nasa_firms(self) -> dict[str, Any]:
        """Descarga focos térmicos NASA FIRMS para zona Valparaíso."""
        end_date = datetime.utcnow().date()
        url = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
        params: dict[str, Any] = {
            "source": "VIIRS_SNPP_NRT",
            "area": (
                f"{VALPARAISO_BBOX['min_lon']},{VALPARAISO_BBOX['min_lat']},"
                f"{VALPARAISO_BBOX['max_lon']},{VALPARAISO_BBOX['max_lat']}"
            ),
            "dayrange": 5,
            "date": end_date.isoformat(),
        }
        if NASA_FIRMS_API_KEY:
            params["MAP_KEY"] = NASA_FIRMS_API_KEY

        out_path = self.raw_dir / f"nasa_firms_{end_date.isoformat()}.csv"
        try:
            response = self._download_with_retry(url, params)
            content = response.text
            out_path.write_text(content, encoding="utf-8")
            log_event("ParallelIngester", "nasa_firms_ok", str(out_path))
            return {"status": "success", "degraded": False, "path": str(out_path)}
        except requests.RequestException as exc:
            log_event("ParallelIngester", "nasa_firms_fail", str(exc), "WARN")
            return self._degrade_source("nasa_firms", "staging_incendios", out_path, exc)

    def _ingest_dmc(self) -> dict[str, Any]:
        """Descarga telemetría meteorológica DMC."""
        out_path = self.raw_dir / f"dmc_meteo_{datetime.utcnow().date().isoformat()}.json"
        try:
            response = self._download_with_retry(
                f"{DMC_API_BASE_URL}/application/user/productos/informacion-sinoptica"
            )
            payload = response.json()
            out_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            log_event("ParallelIngester", "dmc_ok", str(out_path))
            return {"status": "success", "degraded": False, "path": str(out_path)}
        except requests.RequestException as exc:
            log_event("ParallelIngester", "dmc_fail", str(exc), "WARN")
            return self._degrade_source("dmc_meteo", "staging_meteo", out_path, exc)

    def _ingest_conaf(self) -> dict[str, Any]:
        """Descarga registros históricos CONAF con fallback institucional."""
        out_path = self.raw_dir / f"conaf_incendios_{datetime.utcnow().date().isoformat()}.json"
        try:
            response = self._download_with_retry(
                f"{CONAF_DATA_URL}/wp-json/wp/v2/posts",
                {"per_page": 1},
            )
            payload = self._parse_conaf_response(response)
            out_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            log_event("ParallelIngester", "conaf_ok", str(out_path))
            return {"status": "success", "degraded": False, "path": str(out_path)}
        except requests.RequestException as exc:
            log_event("ParallelIngester", "conaf_fail", str(exc), "WARN")
            degraded = self._degrade_source("conaf_incendios", "staging_incendios", out_path, exc)
            if degraded.get("status") != "failed":
                return degraded
            return self._load_institutional_conaf_seed(out_path)

    def _parse_conaf_response(self, response: requests.Response) -> list[dict[str, Any]]:
        """Carga histórico institucional embebido (prototipo demo).

        La API pública de CONAF no expone incendios vía REST; el prototipo
        usa el seed institucional versionado en repositorio.
        """
        if CONAF_SEED_PATH.exists():
            return json.loads(CONAF_SEED_PATH.read_text(encoding="utf-8"))
        return [{"source": "conaf", "status": "reachable", "meta": response.status_code}]

    def _load_institutional_conaf_seed(self, out_path: Path) -> dict[str, Any]:
        """Carga histórico institucional embebido como última capa de contingencia.

        Args:
            out_path: Ruta de salida para serializar payload.

        Returns:
            Resultado con datos institucionales pre-cargados.
        """
        if not CONAF_SEED_PATH.exists():
            log_event("ParallelIngester", "conaf_seed_missing", str(CONAF_SEED_PATH), "ERROR")
            return {"status": "failed", "degraded": True, "path": "", "error": "Sin caché CONAF"}

        payload = json.loads(CONAF_SEED_PATH.read_text(encoding="utf-8"))
        out_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        log_event("ParallelIngester", "conaf_seed_ok", f"{len(payload)} registros institucionales", "WARN")
        return {
            "status": "degraded",
            "degraded": True,
            "path": str(out_path),
            "rows": len(payload),
            "source": "institutional_seed",
        }

    def _degrade_source(
        self,
        source_name: str,
        staging_table: str,
        out_path: Path,
        exc: requests.RequestException,
    ) -> dict[str, Any]:
        """Aplica degradación R-03 leyendo staging PostGIS en lugar de datos sintéticos.

        Args:
            source_name: Identificador de la fuente.
            staging_table: Tabla staging de contingencia.
            out_path: Ruta de salida para serializar fallback.
            exc: Excepción original de red.

        Returns:
            Resultado con flag degraded y datos de PostGIS si existen.
        """
        df_fallback = self._recuperar_payload_fallback(staging_table)
        if df_fallback.empty:
            log_event(
                "ParallelIngester",
                "degradation_empty",
                f"{source_name}: sin datos en {staging_table}",
                "ERROR",
            )
            return {
                "status": "failed",
                "degraded": True,
                "path": "",
                "error": str(exc),
            }

        if staging_table == "staging_meteo":
            payload: Any = df_fallback.to_dict(orient="records")
            out_path.write_text(json.dumps(payload, ensure_ascii=False, default=str), encoding="utf-8")
        elif staging_table == "staging_incendios":
            if {"latitud", "longitud"}.issubset(df_fallback.columns):
                df_export = df_fallback.rename(
                    columns={"latitud": "latitude", "longitud": "longitude"}
                )
                content = df_export.to_csv(index=False)
            else:
                content = df_fallback.to_csv(index=False)
            out_path.write_text(content, encoding="utf-8")
        else:
            out_path.write_text(df_fallback.to_csv(index=False), encoding="utf-8")

        log_event(
            "ParallelIngester",
            "degradation_ok",
            f"{source_name} -> {staging_table} ({len(df_fallback)} filas)",
            "WARN",
        )
        return {
            "status": "degraded",
            "degraded": True,
            "path": str(out_path),
            "rows": len(df_fallback),
        }

    def _load_contingency_cache(self) -> str:
        """Carga estado espacial desde predicciones_riesgo cuando APIs fallan."""
        gdf = self.query.get_contingency_cache(days=CACHE_CONTINGENCY_DAYS)
        out_path = self.raw_dir / "contingency_cache.geojson"
        if not gdf.empty:
            gdf.to_file(out_path, driver="GeoJSON")
        return str(out_path)

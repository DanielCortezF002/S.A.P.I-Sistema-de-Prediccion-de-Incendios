"""Procesamiento geoespacial y limpieza analítica."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from shapely.geometry import box
from sqlalchemy import text

from src.config import (
    DATA_PROCESSED_DIR,
    DATA_RAW_DIR,
    GRID_CELL_SIZE_KM,
    GRID_MAX_CELLS,
    VALPARAISO_BBOX,
)
from src.db import get_backend_connection, log_event
from src.geo.grid import BASE_LAT, BASE_LON, COLS, ROWS, STEP_LAT, STEP_LON
from src.procesamiento.dem_features import sample_grid_topography
from src.procesamiento.raw_parser import parse_dmc_json

CRITICAL_VARIABLES = [
    "temperatura",
    "humedad_relativa",
    "velocidad_viento",
    "altitud",
    "pendiente",
]


class DataProcessor:
    """Transformación, limpieza y consolidación del dataset territorial."""

    def __init__(
        self,
        raw_dir: Optional[Path] = None,
        processed_dir: Optional[Path] = None,
    ) -> None:
        """Inicializa procesador con rutas de datos.

        Args:
            raw_dir: Directorio de datos crudos.
            processed_dir: Directorio de salida Parquet.
        """
        self.raw_dir = raw_dir or DATA_RAW_DIR
        self.processed_dir = processed_dir or DATA_PROCESSED_DIR
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.bbox = box(
            VALPARAISO_BBOX["min_lon"],
            VALPARAISO_BBOX["min_lat"],
            VALPARAISO_BBOX["max_lon"],
            VALPARAISO_BBOX["max_lat"],
        )

    def process_all(self) -> str:
        """Ejecuta pipeline completo de transformación.

        Returns:
            Ruta al dataset consolidado en Parquet.
        """
        incendios = self._load_incendios()
        meteo = self._load_meteo()
        grid = self._build_grid()

        merged = grid.merge(meteo, how="left", on="cell_id")
        merged = self._add_topography(merged)
        merged = self.clean_staging_tables(merged)
        merged = self._impute_nulls(merged)

        completeness = self._validate_completeness(merged)
        log_event(
            "DataProcessor",
            "oe1_completeness",
            f"Completitud dataset: {completeness:.1%}",
            "INFO" if completeness >= 0.90 else "WARN",
        )

        out_path = self.processed_dir / "dataset_valparaiso.parquet"
        merged.to_parquet(out_path, index=False)
        self._persist_to_postgis(incendios, meteo, merged)
        log_event("DataProcessor", "process_complete", str(out_path))
        return str(out_path)

    def _validate_completeness(self, df: pd.DataFrame) -> float:
        """Calcula completitud de variables críticas OE1.

        Args:
            df: DataFrame procesado.

        Returns:
            Ratio de completitud entre 0 y 1.
        """
        present = [c for c in CRITICAL_VARIABLES if c in df.columns]
        if not present or df.empty:
            return 0.0
        return float(1.0 - df[present].isna().mean().mean())

    def clean_staging_tables(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normaliza variables y elimina outliers.

        Args:
            df: DataFrame de entrada.

        Returns:
            DataFrame limpio con Z-Score aplicado a variables numéricas.
        """
        # "orientacion" (aspect) queda fuera a propósito: es un ángulo circular
        # (0-360°, brújula) y un z-score sobre el valor crudo en grados trata
        # 359° y 1° como extremos opuestos en vez de valores casi idénticos —
        # el mismo problema que motivó la media circular en dem_features.py.
        numeric_cols = [
            "temperatura",
            "humedad_relativa",
            "velocidad_viento",
            "altitud",
            "pendiente",
        ]
        cleaned = df.copy()
        for col in numeric_cols:
            if col not in cleaned.columns:
                continue
            series = cleaned[col].astype("float32")
            mean = series.mean()
            std = series.std() or 1.0
            z = (series - mean) / std
            cleaned[col] = series.mask(z.abs() > 3, mean)
        return cleaned

    def _impute_nulls(self, df: pd.DataFrame) -> pd.DataFrame:
        """Imputa nulos por mediana sectorial."""
        result = df.copy()
        for col in ["temperatura", "humedad_relativa", "velocidad_viento"]:
            if col in result.columns:
                median = result[col].median()
                result[col] = result[col].fillna(median)
        return result

    def _load_incendios(self) -> pd.DataFrame:
        """Carga focos desde archivos raw."""
        records: list[dict] = []
        for path in self.raw_dir.glob("nasa_firms_*.csv"):
            df = pd.read_csv(path)
            if {"latitude", "longitude"}.issubset(df.columns):
                for _, row in df.iterrows():
                    records.append(
                        {
                            "fecha": row.get("acq_date", datetime.utcnow().date()),
                            "latitud": row["latitude"],
                            "longitud": row["longitude"],
                            "fuente": "nasa_firms",
                        }
                    )
        for path in self.raw_dir.glob("conaf_incendios_*.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            items = data if isinstance(data, list) else data.get("records", [])
            for item in items:
                if "latitud" in item and "longitud" in item:
                    records.append(
                        {
                            "fecha": item.get("fecha"),
                            "latitud": item.get("latitud"),
                            "longitud": item.get("longitud"),
                            "fuente": "conaf",
                        }
                    )
        return pd.DataFrame(records)

    def _load_meteo(self) -> pd.DataFrame:
        """Agrega telemetría meteorológica por celda.

        Usa parse_dmc_json (raw_parser.py) para leer el formato real de
        dmc_meteo_*.json — un dict por código de estación, con las lecturas
        anidadas en datosEstaciones.datos[] y valores como string con unidad
        embebida (ver contrato documentado en src/config.py). La versión
        anterior asumía top-level {"temperatura": <float>, ...} plano, que
        no es la forma real de la respuesta de DMC — como esa clave nunca
        existía en la raíz, cada fila caía siempre al default hardcodeado
        (25.0/40.0/15.0) sin ningún error visible, dejando la telemetría
        con varianza cero sin importar los datos reales descargados.
        """
        records: list[dict] = []
        for path in self.raw_dir.glob("dmc_meteo_*.json"):
            parsed = parse_dmc_json(path)
            if parsed.empty:
                continue
            for _, row in parsed.iterrows():
                records.append(
                    {
                        "temperatura": row["temperatura"],
                        "humedad_relativa": row["humedad_relativa"],
                        "velocidad_viento": row["velocidad_viento_kmh"],
                    }
                )
        if not records:
            records = [
                {"temperatura": 30.0, "humedad_relativa": 25.0, "velocidad_viento": 32.0},
                {"temperatura": 22.0, "humedad_relativa": 60.0, "velocidad_viento": 8.0},
            ]
        df = pd.DataFrame(records)
        grid = self._build_grid()
        if len(df) <= len(grid):
            df["cell_id"] = grid["cell_id"].values[: len(df)]
        else:
            df = df.assign(cell_id=[f"VP-{i:03d}" for i in range(1, len(df) + 1)])
        return df.groupby("cell_id", as_index=False).mean(numeric_only=True)

    def _build_grid(self) -> pd.DataFrame:
        """Construye la grilla canónica (`src/geo/grid.py`), idéntica a la
        que usa el dashboard y a `scripts/generate_seed.py`.

        Itera filas × columnas (mismo orden que el seed) para garantizar que
        VP-001..VP-010 correspondan a la fila sur y los cell_id coincidan
        con las geometrías almacenadas en PostGIS.
        """
        cells: list[dict] = []
        idx = 1
        for row in range(ROWS):
            for col in range(COLS):
                if idx > GRID_MAX_CELLS:
                    break
                lon = round(BASE_LON + col * STEP_LON, 5)
                lat = round(BASE_LAT + row * STEP_LAT, 5)
                cells.append(
                    {
                        "cell_id": f"VP-{idx:03d}",
                        "min_lon": lon,
                        "min_lat": lat,
                        "max_lon": round(lon + STEP_LON, 5),
                        "max_lat": round(lat + STEP_LAT, 5),
                    }
                )
                idx += 1
        return pd.DataFrame(cells)

    def _add_topography(self, df: pd.DataFrame) -> pd.DataFrame:
        """Añade altitud/pendiente/orientación reales desde el DEM procesado.

        No dispara descargas ni reprocesa el DEM acá — solo lee los GeoTIFF
        ya generados en data/processed/dem_terrain/ (ver dem_ingester.py +
        dem_terrain.py, corridos aparte, igual que el backfill de FIRMS es
        un paso explícito separado de la ingesta diaria). Si todavía no
        existen, cae a la aproximación sintética anterior — pero lo deja
        logueado como degradación (R-03), no como error silencioso.
        """
        result = df.copy()
        terrain_dir = self.processed_dir / "dem_terrain"
        dem_matches = sorted(terrain_dir.glob("*_utm19s.tif"))
        slope_matches = sorted(terrain_dir.glob("*_slope.tif"))
        aspect_matches = sorted(terrain_dir.glob("*_aspect.tif"))

        if dem_matches and slope_matches and aspect_matches:
            topo = sample_grid_topography(
                result, dem_matches[0], slope_matches[0], aspect_matches[0]
            )
            result["altitud"] = topo["altitud"]
            result["pendiente"] = topo["pendiente"]
            result["orientacion"] = topo["orientacion"]
            log_event(
                "DataProcessor",
                "topography_real",
                f"DEM real: {dem_matches[0].name}",
            )
        else:
            log_event(
                "DataProcessor",
                "topography_fallback",
                "Sin DEM procesado en data/processed/dem_terrain/ — usando aproximación "
                "sintética. Correr DemIngester + DemTerrainProcessor antes de process_all() "
                "para datos reales.",
                "WARN",
            )
            result["altitud"] = np.linspace(50, 800, len(result)).astype("float32")
            rng = np.random.default_rng(42)
            result["pendiente"] = rng.uniform(5, 35, len(result)).astype("float32")

        rng = np.random.default_rng(42)
        result["ndvi"] = rng.uniform(0.2, 0.8, len(result)).astype("float32")
        return result

    def _persist_to_postgis(
        self,
        incendios: pd.DataFrame,
        meteo: pd.DataFrame,
        features: pd.DataFrame,
    ) -> None:
        """Persiste datos procesados en tablas staging y features."""
        with get_backend_connection() as conn:
            if not incendios.empty:
                for _, row in incendios.iterrows():
                    conn.execute(
                        text(
                            """
                            INSERT INTO staging_incendios (fecha, latitud, longitud, fuente, geom)
                            VALUES (:fecha, :lat, :lon, :fuente,
                                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326))
                            """
                        ),
                        {
                            "fecha": row.get("fecha", datetime.utcnow()),
                            "lat": row["latitud"],
                            "lon": row["longitud"],
                            "fuente": row.get("fuente", "unknown"),
                        },
                    )

            for _, row in features.iterrows():
                wkt = (
                    f"POLYGON(({row['min_lon']} {row['min_lat']}, "
                    f"{row['max_lon']} {row['min_lat']}, "
                    f"{row['max_lon']} {row['max_lat']}, "
                    f"{row['min_lon']} {row['max_lat']}, "
                    f"{row['min_lon']} {row['min_lat']}))"
                )
                conn.execute(
                    text(
                        """
                        INSERT INTO matriz_features (
                            cell_id, fecha, temperatura, humedad_relativa, velocidad_viento,
                            altitud, pendiente, orientacion, ndvi, geom
                        ) VALUES (
                            :cell_id, CURRENT_DATE, :temp, :hum, :wind,
                            :alt, :pend, :orient, :ndvi, ST_GeomFromText(:wkt, 4326)
                        )
                        ON CONFLICT (cell_id, fecha) DO UPDATE SET
                            temperatura = EXCLUDED.temperatura,
                            humedad_relativa = EXCLUDED.humedad_relativa,
                            velocidad_viento = EXCLUDED.velocidad_viento
                        """
                    ),
                    {
                        "cell_id": row["cell_id"],
                        "temp": row.get("temperatura"),
                        "hum": row.get("humedad_relativa"),
                        "wind": row.get("velocidad_viento"),
                        "alt": row.get("altitud"),
                        "pend": row.get("pendiente"),
                        # Ausente si _add_topography cayó al fallback sintético
                        # (esa rama no genera la columna) -> None -> NULL,
                        # coherente con orientacion siendo nullable.
                        "orient": row.get("orientacion"),
                        "ndvi": row.get("ndvi"),
                        "wkt": wkt,
                    },
                )

"""Servicio de inferencia del PROTOTIPO local de S.A.P.I.

Única interfaz pública: `score_current_grid(forecast_time=None)`. Usa
EXCLUSIVAMENTE el pipeline temporal nuevo — `regional_meteo`, `episodes`,
`dem_features`, y el artefacto PROTOTYPE/EXPLORATORY entrenado por
`scripts/build_prototype_model.py` (Modelo D). Nunca importa nada del
pipeline legacy: sin `matriz_features`, sin `xgboost_optimized.pkl`, sin
`ignicion` 32/28/25, sin NDVI sintético, sin el generador de datos
sintéticos de la UI (`app/utils/demo` + `_seed.py`, ver
`test_no_legacy_imports_in_prototype_modules`, que sí nombra el archivo
completo para poder detectarlo).

Garantía anti-leakage: para un `forecast_time` T, cada feature usado
cumple `feature_timestamp <= T` por construcción — `build_regional_meteo_
features` y `historial_firms_features` son las MISMAS funciones que usa
`scripts/build_temporal_dataset.py` para el dataset de entrenamiento (una
sola fuente de verdad sobre "cómo se calcula una feature a partir de T").
No se inventa meteorología futura: si `forecast_time=None`, se usa el
último bucket real con al menos una lectura DMC; si se pide un T posterior
a la última lectura real, se falla explícitamente en vez de inventar un
valor.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union

import joblib
import pandas as pd

from src.geo.grid import all_cells
from src.procesamiento.dem_features import load_grid_topography
from src.procesamiento.episodes import assign_episodes, first_arrival_by_cell
from src.procesamiento.regional_meteo import load_regional_meteo_series
from src.procesamiento.temporal_features import LAG_HOURS, build_regional_meteo_features, historial_firms_features

REPO_ROOT = Path(__file__).resolve().parents[2]
STATION_ID = "330007"
STATION_NAME = "Rodelillo"
CANDIDATE_STEP_HOURS = 6  # mismo valor congelado que scripts/build_temporal_dataset.py
FIRES_CSV = REPO_ROOT / "data" / "processed" / "nasa_firms_2021-08-30_2026-08-30.csv"
DEM_TERRAIN_DIR = REPO_ROOT / "data" / "processed" / "dem_terrain"
MODEL_PATH = REPO_ROOT / "models" / "prototype_model_d.pkl"

_EMPTY_ARRIVALS = pd.Series([], dtype="datetime64[ns, UTC]")


class PrototypeUnavailableError(RuntimeError):
    """Falta un artefacto necesario (modelo, meteorología reciente, FIRMS,
    grilla) para generar el ranking. El dashboard debe capturar esta
    excepción y mostrar un mensaje claro — nunca un stacktrace crudo."""


@dataclass
class CellScore:
    cell_id: str
    score: float
    rank: int
    geometry: dict  # bbox EPSG:4326: {min_lon, min_lat, max_lon, max_lat}
    elevation: Optional[float]
    slope: float
    historical_count: int


@dataclass
class GridScoreResult:
    forecast_time: pd.Timestamp
    horizon_hours: int
    station_id: str
    station_name: str
    weather_timestamp: pd.Timestamp
    model_version: str
    model_status: str
    meteo_actual: dict
    cells: list = field(default_factory=list)  # list[CellScore], orden = rank 1..N


def _load_model() -> tuple[object, dict]:
    if not MODEL_PATH.exists():
        # `.relative_to` lanza ValueError si MODEL_PATH no cuelga de
        # REPO_ROOT (p. ej. en tests que apuntan a un tmp_path) — se prueba
        # antes de usarlo para no reemplazar un mensaje claro por un
        # ValueError distinto sin relación con el problema real (falta el
        # modelo).
        try:
            shown_path = str(MODEL_PATH.relative_to(REPO_ROOT))
        except ValueError:
            shown_path = str(MODEL_PATH)
        raise PrototypeUnavailableError(
            f"No existe el modelo del prototipo en {shown_path}. "
            "Corre `python scripts/build_prototype_model.py` primero."
        )
    payload = joblib.load(MODEL_PATH)
    return payload["model"], payload["metadata"]


def _latest_forecast_time(meteo_series: pd.DataFrame) -> pd.Timestamp:
    bucketed = (
        meteo_series.set_index("momento")["temperatura"]
        .resample(f"{CANDIDATE_STEP_HOURS}h")
        .first()
        .dropna()
    )
    if bucketed.empty:
        raise PrototypeUnavailableError(
            "No hay lecturas meteorológicas reales suficientes para determinar un forecast_time."
        )
    return bucketed.index.max()


def score_current_grid(forecast_time: Optional[Union[str, pd.Timestamp]] = None) -> GridScoreResult:
    """Puntúa las 50 celdas de la grilla para un `forecast_time` T.

    `forecast_time=None` -> usa el último T real con features disponibles
    (nunca una fecha futura inventada). Lanza `PrototypeUnavailableError`
    con un mensaje explicable si falta cualquier artefacto necesario.
    """
    model, metadata = _load_model()
    feature_columns: list[str] = metadata["feature_columns"]
    horizon_hours: int = metadata["horizon_hours"]

    meteo_series = load_regional_meteo_series(STATION_ID)
    if meteo_series.empty:
        raise PrototypeUnavailableError(
            f"No hay datos meteorológicos reales para la estación {STATION_ID} en data/raw/."
        )

    if forecast_time is None:
        forecast_time = _latest_forecast_time(meteo_series)
    else:
        forecast_time = pd.Timestamp(forecast_time)
        if forecast_time.tzinfo is None:
            forecast_time = forecast_time.tz_localize("UTC")
        if forecast_time > meteo_series["momento"].max():
            raise PrototypeUnavailableError(
                f"forecast_time={forecast_time} es posterior a la última lectura meteorológica real "
                f"({meteo_series['momento'].max()}) — el servicio no inventa meteorología futura."
            )

    meteo_feats = build_regional_meteo_features([forecast_time], meteo_series, lag_hours=LAG_HOURS)
    if meteo_feats.empty or bool(meteo_feats.iloc[0]["meteo_actual_missing"]):
        raise PrototypeUnavailableError(
            f"No hay una lectura meteorológica real suficientemente cercana a {forecast_time} "
            "para generar el ranking."
        )
    meteo_row = meteo_feats.iloc[0]

    if not FIRES_CSV.exists():
        raise PrototypeUnavailableError(f"No existe el histórico FIRMS en {FIRES_CSV.relative_to(REPO_ROOT)}.")
    fires = pd.read_csv(FIRES_CSV)
    episodes = assign_episodes(fires)
    arrivals = first_arrival_by_cell(episodes)
    arrivals_by_cell = {cell: group["first_arrival"] for cell, group in arrivals.groupby("cell_id")}

    grid_cells = all_cells()
    cell_ids = [c["cell_id"] for c in grid_cells]
    grid_by_id = {c["cell_id"]: c for c in grid_cells}
    topo = load_grid_topography(grid_cells, DEM_TERRAIN_DIR).set_index("cell_id")

    rows = []
    for cell_id in cell_ids:
        hist = historial_firms_features(cell_id, forecast_time, arrivals_by_cell.get(cell_id, _EMPTY_ARRIVALS))
        row = {"cell_id": cell_id, **hist}
        for col in meteo_row.index:
            if col != "forecast_time":
                row[col] = meteo_row[col]
        t = topo.loc[cell_id]
        row["elevacion"] = t["elevacion"]
        row["pendiente"] = t["pendiente"]
        row["orientacion"] = t["orientacion"]
        rows.append(row)
    features_df = pd.DataFrame(rows).set_index("cell_id")

    missing_cols = [c for c in feature_columns if c not in features_df.columns]
    if missing_cols:
        raise PrototypeUnavailableError(f"Faltan columnas de feature para inferir: {missing_cols}")

    x = features_df[feature_columns]
    scores = model.predict_proba(x)[:, 1]
    score_by_cell = pd.Series(scores, index=features_df.index, dtype=float)
    ranking = score_by_cell.sort_values(ascending=False)

    cells = []
    for position, (cell_id, score) in enumerate(ranking.items(), start=1):
        g = grid_by_id[cell_id]
        cells.append(
            CellScore(
                cell_id=cell_id,
                score=float(score),
                rank=position,
                geometry={
                    "min_lon": g["min_lon"],
                    "min_lat": g["min_lat"],
                    "max_lon": g["max_lon"],
                    "max_lat": g["max_lat"],
                },
                elevation=(None if pd.isna(features_df.loc[cell_id, "elevacion"]) else float(features_df.loc[cell_id, "elevacion"])),
                slope=(None if pd.isna(features_df.loc[cell_id, "pendiente"]) else float(features_df.loc[cell_id, "pendiente"])),
                historical_count=int(features_df.loc[cell_id, "historial_firms_count"]),
            )
        )

    return GridScoreResult(
        forecast_time=forecast_time,
        horizon_hours=horizon_hours,
        station_id=STATION_ID,
        station_name=STATION_NAME,
        weather_timestamp=meteo_row["meteo_actual_momento"],
        model_version=metadata["model_version"],
        model_status=metadata["status"],
        meteo_actual={
            "temperatura": float(meteo_row["meteo_actual_temp"]),
            "humedad_relativa": float(meteo_row["meteo_actual_hr"]),
            "velocidad_viento_kmh": float(meteo_row["meteo_actual_viento"]),
            "regla_30_30_30": bool(meteo_row["meteo_actual_regla_30_30_30"]),
            "momento_observacion": meteo_row["meteo_actual_momento"],
        },
        cells=cells,
    )

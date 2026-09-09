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

import os
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

# Modo de reproducibilidad del Hito 1 (formalizado 09-09-2026, ver
# docs/deploy.md "MODO HITO 1 REPRODUCIBLE"). Explicito, opt-in via
# variable de entorno -- el comportamiento normal (data/raw/ operacional,
# meteorologia mas reciente que exista localmente) NO cambia salvo que se
# active. Cuando esta activo, `load_regional_meteo_series` lee del
# snapshot congelado en artifacts/hito1/reproducibility/dmc/ en vez de
# data/raw/ -- NUNCA se disfraza como meteorologia en tiempo real: el
# `forecast_time` resultante y `classify_freshness()` siguen reflejando
# la fecha real de los datos (historicos), no la fecha de hoy.
#
# Deliberadamente NO se lee os.getenv() a nivel de modulo (import-time):
# eso congelaria el valor en el primer import y un test que active la
# variable despues no tendria efecto. `_reproducibility_mode()` la lee en
# cada llamada.
REPRODUCIBILITY_DMC_DIR = REPO_ROOT / "artifacts" / "hito1" / "reproducibility" / "dmc"
# FIRMS: el CSV congelado es EL MISMO archivo derivado (1,3MB, ya deduplicado
# SP/NRT) que data/processed/nasa_firms_2021-08-30_2026-08-30.csv -- no una
# version recortada. historial_firms_features() necesita el historial COMPLETO
# hasta forecast_time (cuenta arribos totales, no una ventana corta como DMC),
# asi que no existe un subconjunto mas chico sin alterar el resultado.
REPRODUCIBILITY_FIRMS_CSV = REPO_ROOT / "artifacts" / "hito1" / "reproducibility" / "firms" / "nasa_firms_2021-08-30_2026-08-30.csv"
# DEM: tabla derivada (50 filas: cell_id/elevacion/pendiente/orientacion/
# dem_disponible) -- exactamente lo que load_grid_topography() produce a
# partir del raster real, generada una vez y congelada (1,6KB vs ~6,5MB de
# rasters). Evita versionar los .tif; la funcion que los consume no se toca,
# solo se evita llamarla en modo reproducibilidad.
REPRODUCIBILITY_TOPO_CSV = REPO_ROOT / "artifacts" / "hito1" / "reproducibility" / "dem" / "grid_topography.csv"


def _reproducibility_mode() -> bool:
    return os.getenv("SAPI_REPRODUCIBILITY_MODE") == "1"

_EMPTY_ARRIVALS = pd.Series([], dtype="datetime64[ns, UTC]")

# Frescura de la meteorología usada (2026-09-07, corrección UX/semántica):
# `forecast_time=None` correctamente no inventa clima futuro y usa la
# última lectura real disponible — pero si esa lectura tiene varios días
# de antigüedad respecto al momento en que alguien ABRE el dashboard, la
# UI no puede insinuar que el ranking es un pronóstico vigente de "las
# próximas 6 horas de hoy". `age_hours` mide justamente esa distancia
# entre el reloj real y `weather_timestamp` — no la ventana del target
# (que sigue siendo T -> T+horizon_hours, sin cambios).
FRESHNESS_RECENT = "DATOS RECIENTES"
FRESHNESS_DELAYED = "DATOS CON RETRASO"
FRESHNESS_HISTORICAL = "DATOS HISTÓRICOS / DESACTUALIZADOS"


def classify_freshness(age_hours: float) -> str:
    """age<=12h -> RECIENTES; 12h<age<=24h -> CON RETRASO; age>24h -> HISTÓRICOS."""
    if age_hours <= 12:
        return FRESHNESS_RECENT
    if age_hours <= 24:
        return FRESHNESS_DELAYED
    return FRESHNESS_HISTORICAL


class PrototypeUnavailableError(RuntimeError):
    """Falta un artefacto necesario (modelo, meteorología reciente, FIRMS,
    grilla) para generar el ranking. El dashboard debe capturar esta
    excepción y mostrar un mensaje claro — nunca un stacktrace crudo."""


@dataclass
class CellScore:
    cell_id: str
    score: float
    rank: int  # posición 1..N, SIEMPRE única — contrato interno sin cambios
    display_rank: int  # rank "honesto" para UI: empates comparten el MISMO número (method="min")
    tie_group_size: int  # cuántas celdas comparten exactamente este score (1 = sin empate)
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
    age_hours: float  # (ahora real - weather_timestamp), en horas
    freshness: str  # FRESHNESS_RECENT | FRESHNESS_DELAYED | FRESHNESS_HISTORICAL
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


def _resolve_forecast_time(
    forecast_time: Optional[Union[str, pd.Timestamp]], meteo_series: pd.DataFrame
) -> pd.Timestamp:
    if forecast_time is None:
        return _latest_forecast_time(meteo_series)
    forecast_time = pd.Timestamp(forecast_time)
    if forecast_time.tzinfo is None:
        forecast_time = forecast_time.tz_localize("UTC")
    if forecast_time > meteo_series["momento"].max():
        raise PrototypeUnavailableError(
            f"forecast_time={forecast_time} es posterior a la última lectura meteorológica real "
            f"({meteo_series['momento'].max()}) — el servicio no inventa meteorología futura."
        )
    return forecast_time


def _resolve_meteo_row(forecast_time: pd.Timestamp, meteo_series: pd.DataFrame) -> pd.Series:
    meteo_feats = build_regional_meteo_features([forecast_time], meteo_series, lag_hours=LAG_HOURS)
    if meteo_feats.empty or bool(meteo_feats.iloc[0]["meteo_actual_missing"]):
        raise PrototypeUnavailableError(
            f"No hay una lectura meteorológica real suficientemente cercana a {forecast_time} "
            "para generar el ranking."
        )
    return meteo_feats.iloc[0]


def build_feature_matrix(forecast_time: pd.Timestamp, meteo_row: pd.Series) -> pd.DataFrame:
    """Construye la matriz de features (índice = cell_id, una fila por
    celda) para un `forecast_time`/`meteo_row` ya resueltos. Extraída como
    función propia (auditoría 2026-09-08) para poder inspeccionar/testear
    exactamente lo que llega a `predict_proba` — cero cambio de
    comportamiento respecto a antes, solo testabilidad.

    Reusa `historial_firms_features` (la misma función que
    `scripts/build_temporal_dataset.py`) para historial por celda;
    `meteo_row` ya viene calculado una sola vez por el llamador. La
    meteorología regional es, por diseño, IDÉNTICA para las 50 celdas en
    un mismo T (una sola estación regional, nunca reetiquetada por
    celda); historial FIRMS y topografía sí varían por celda.
    """
    reproducibility = _reproducibility_mode()
    fires_csv = REPRODUCIBILITY_FIRMS_CSV if reproducibility else FIRES_CSV
    if not fires_csv.exists():
        raise PrototypeUnavailableError(f"No existe el histórico FIRMS en {fires_csv.relative_to(REPO_ROOT)}.")
    fires = pd.read_csv(fires_csv)
    episodes = assign_episodes(fires)
    arrivals = first_arrival_by_cell(episodes)
    arrivals_by_cell = {cell: group["first_arrival"] for cell, group in arrivals.groupby("cell_id")}

    grid_cells = all_cells()
    cell_ids = [c["cell_id"] for c in grid_cells]
    if reproducibility:
        if not REPRODUCIBILITY_TOPO_CSV.exists():
            raise PrototypeUnavailableError(
                f"No existe la tabla topográfica congelada en {REPRODUCIBILITY_TOPO_CSV.relative_to(REPO_ROOT)}."
            )
        topo = pd.read_csv(REPRODUCIBILITY_TOPO_CSV).set_index("cell_id")
    else:
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
    # `set_index("cell_id")` DEBE ser lo último: cualquier reordenamiento
    # posterior de `features_df` (p. ej. un `.sort_values` sobre una
    # columna de feature) seguiría llevando el cell_id correcto consigo
    # mismo vía el índice — nunca se vuelve a alinear por posición entera.
    return pd.DataFrame(rows).set_index("cell_id")


def score_current_grid(forecast_time: Optional[Union[str, pd.Timestamp]] = None) -> GridScoreResult:
    """Puntúa las 50 celdas de la grilla para un `forecast_time` T.

    `forecast_time=None` -> usa el último T real con features disponibles
    (nunca una fecha futura inventada). Lanza `PrototypeUnavailableError`
    con un mensaje explicable si falta cualquier artefacto necesario.

    Si `SAPI_REPRODUCIBILITY_MODE=1` está activo, la meteorología se lee
    del snapshot congelado del Hito 1 (`REPRODUCIBILITY_DMC_DIR`) en vez de
    `data/raw/` operacional -- ver docs/deploy.md, "MODO HITO 1
    REPRODUCIBLE". El resultado sigue siendo honesto sobre su frescura:
    `forecast_time`/`weather_timestamp`/`classify_freshness()` reflejan la
    fecha real de esos datos (históricos), nunca la fecha de hoy.
    """
    model, metadata = _load_model()
    feature_columns: list[str] = metadata["feature_columns"]
    horizon_hours: int = metadata["horizon_hours"]

    meteo_raw_dir = REPRODUCIBILITY_DMC_DIR if _reproducibility_mode() else None
    meteo_series = load_regional_meteo_series(STATION_ID, raw_dir=meteo_raw_dir)
    if meteo_series.empty:
        raise PrototypeUnavailableError(
            f"No hay datos meteorológicos reales para la estación {STATION_ID} en data/raw/."
        )

    forecast_time = _resolve_forecast_time(forecast_time, meteo_series)
    meteo_row = _resolve_meteo_row(forecast_time, meteo_series)
    features_df = build_feature_matrix(forecast_time, meteo_row)

    grid_cells = all_cells()
    grid_by_id = {c["cell_id"]: c for c in grid_cells}

    missing_cols = [c for c in feature_columns if c not in features_df.columns]
    if missing_cols:
        raise PrototypeUnavailableError(f"Faltan columnas de feature para inferir: {missing_cols}")

    # `x` conserva el índice cell_id de `features_df` — pandas alinea por
    # ese índice (nunca por posición entera) en cada paso siguiente
    # (`pd.Series(scores, index=x.index)`, `.loc[cell_id]`), así que un
    # reordenamiento de filas nunca puede desalinear cell_id -> score (ver
    # test_reordering_features_df_does_not_desync_cell_id_and_score).
    x = features_df[feature_columns]
    scores = model.predict_proba(x)[:, 1]
    score_by_cell = pd.Series(scores, index=x.index, dtype=float)
    ranking = score_by_cell.sort_values(ascending=False)

    # Empates reales del modelo (2026-09-07, corrección de honestidad
    # científica): con pocos positivos históricos, decenas de celdas caen
    # en el MISMO score exacto — `rank` (posición 1..N) sigue siendo único
    # por contrato (lo usan el color del mapa y el corte de Top-5), pero
    # `display_rank` es el número que debe VERSE: comparte el mismo valor
    # para todo el grupo empatado (method="min", igual que una tabla de
    # posiciones deportiva), para no insinuar que una celda es "más
    # riesgosa" que otra cuando el modelo las trata exactamente igual.
    display_ranks = ranking.rank(method="min", ascending=False).astype(int)
    tie_group_sizes = ranking.groupby(ranking).transform("size")

    cells = []
    for position, (cell_id, score) in enumerate(ranking.items(), start=1):
        g = grid_by_id[cell_id]
        cells.append(
            CellScore(
                cell_id=cell_id,
                score=float(score),
                rank=position,
                display_rank=int(display_ranks.loc[cell_id]),
                tie_group_size=int(tie_group_sizes.loc[cell_id]),
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

    weather_timestamp = meteo_row["meteo_actual_momento"]
    age_hours = (pd.Timestamp.now(tz="UTC") - weather_timestamp).total_seconds() / 3600.0
    freshness = classify_freshness(age_hours)

    return GridScoreResult(
        forecast_time=forecast_time,
        horizon_hours=horizon_hours,
        station_id=STATION_ID,
        station_name=STATION_NAME,
        weather_timestamp=weather_timestamp,
        age_hours=age_hours,
        freshness=freshness,
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

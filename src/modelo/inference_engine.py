"""Inferencia diaria XGBoost sobre matriz_features en PostGIS."""

from __future__ import annotations

import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import geopandas as gpd
import joblib
import pandas as pd
from sqlalchemy import text

from src.config import MODELS_DIR, RISK_THRESHOLDS
from src.db import get_backend_engine, get_engine
from src.modelo.baseline import BaselineModel
from src.procesamiento.features import FeatureEngineer
from src.query.prediction_query import PredictionQuery

MODEL_PATH = MODELS_DIR / "xgboost_optimized.pkl"
FEATURE_COLUMNS = BaselineModel.FEATURE_COLUMNS
MODEL_VERSION = "xgboost_optimized_v1"


def load_trained_model() -> dict[str, Any]:
    """Carga el modelo serializado XGBoost y sus metadatos."""
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"No se encontró el modelo en {MODEL_PATH}. "
            "Entrena y serializa el artefacto antes de inferir."
        )
    payload = joblib.load(MODEL_PATH)
    if isinstance(payload, dict) and "model" in payload:
        return payload
    return {"model": payload, "feature_columns": FEATURE_COLUMNS}


def _prepare_feature_matrix(gdf_features: gpd.GeoDataFrame) -> pd.DataFrame:
    """Alinea columnas de entrada al contrato del modelo entrenado."""
    df = gdf_features.copy()
    if "velocidad_viento" not in df.columns and "velocidad_viento_kmh" in df.columns:
        df["velocidad_viento"] = df["velocidad_viento_kmh"]

    engineered = FeatureEngineer().compute_environmental_features(df)
    matrix = pd.DataFrame(index=engineered.index)
    for col in FEATURE_COLUMNS:
        matrix[col] = engineered[col] if col in engineered.columns else 0.0
    return matrix.fillna(0.0)


def _classify_risk(probability: float) -> str:
    if probability < RISK_THRESHOLDS["bajo"]:
        return "bajo"
    if probability < RISK_THRESHOLDS["medio"]:
        return "medio"
    return "alto"


def run_daily_inference(fecha: str | date) -> gpd.GeoDataFrame:
    """Lee features desde PostGIS, ejecuta inferencia XGBoost y guarda en predicciones_riesgo."""
    fecha_str = fecha.isoformat() if isinstance(fecha, date) else str(fecha)
    engine = get_engine()

    query = text(
        """
        SELECT cell_id, fecha, temperatura, humedad_relativa, velocidad_viento,
               regla_30_30_30, altitud, pendiente, ndvi,
               lag_temp_24h, lag_temp_48h, geom
        FROM matriz_features
        WHERE fecha = :fecha
        ORDER BY cell_id
        """
    )
    with engine.connect() as conn:
        gdf_features = gpd.read_postgis(
            query,
            con=conn,
            params={"fecha": fecha_str},
            geom_col="geom",
        )

    if gdf_features.empty:
        raise ValueError(f"No se encontraron registros en matriz_features para la fecha {fecha_str}")

    payload = load_trained_model()
    model = payload["model"]
    feature_cols = payload.get("feature_columns", FEATURE_COLUMNS)
    x = _prepare_feature_matrix(gdf_features)
    if hasattr(model, "feature_names_in_"):
        x_model = x[list(model.feature_names_in_)].fillna(0.0)
    else:
        x_model = x[[c for c in feature_cols if c in x.columns]].fillna(0.0)

    if hasattr(model, "predict_proba"):
        probs = model.predict_proba(x_model)[:, 1]
    else:
        probs = model.predict(x_model)

    gdf_features = gdf_features.copy()
    gdf_features["probabilidad"] = pd.Series(probs, index=gdf_features.index).round(4)
    gdf_features["nivel_riesgo"] = gdf_features["probabilidad"].apply(_classify_risk)
    gdf_features["fecha"] = pd.to_datetime(fecha_str).date()
    gdf_features["modelo_version"] = MODEL_VERSION
    gdf_features["created_at"] = datetime.now(timezone.utc)

    backend_engine = get_backend_engine()
    with backend_engine.begin() as conn:
        conn.execute(
            text("DELETE FROM predicciones_riesgo WHERE fecha = :fecha"),
            {"fecha": fecha_str},
        )

    cols_to_save = [
        "cell_id",
        "fecha",
        "probabilidad",
        "nivel_riesgo",
        "temperatura",
        "humedad_relativa",
        "velocidad_viento",
        "regla_30_30_30",
        "modelo_version",
        "geom",
        "created_at",
    ]
    gdf_out = gdf_features[cols_to_save].copy()
    gdf_out.to_postgis(
        name="predicciones_riesgo",
        con=backend_engine,
        if_exists="append",
        index=False,
    )

    print(
        f"Inferencia completada: {len(gdf_out)} celdas persistidas en 'predicciones_riesgo'."
    )
    return gdf_out

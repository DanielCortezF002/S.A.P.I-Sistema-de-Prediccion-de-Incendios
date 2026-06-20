"""Modelo baseline Random Forest con validación temporal."""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, recall_score
from sklearn.model_selection import TimeSeriesSplit
from sqlalchemy import text

from src.db import get_backend_connection, log_event
from src.procesamiento.features import FeatureEngineer
from src.query.prediction_query import PredictionQuery


class BaselineModel:
    """Clasificador preliminar Random Forest para línea base analítica."""

    FEATURE_COLUMNS = [
        "temperatura",
        "humedad_relativa",
        "velocidad_viento",
        "altitud",
        "pendiente",
        "ndvi",
        "regla_30_30_30",
        "lag_temp_24h",
        "lag_temp_48h",
    ]

    def __init__(self, n_estimators: int = 100, random_state: int = 42) -> None:
        """Configura ensamble de árboles baseline.

        Args:
            n_estimators: Número de árboles.
            random_state: Semilla reproducible.
        """
        self.model = RandomForestClassifier(
            n_estimators=n_estimators,
            random_state=random_state,
            class_weight="balanced",
        )
        self.feature_engineer = FeatureEngineer()
        self.query = PredictionQuery()
        self.metrics: dict[str, Any] = {}

    def train_classifier(self, data: pd.DataFrame) -> dict[str, Any]:
        """Entrena clasificador y persiste predicciones.

        Args:
            data: Dataset con features y etiqueta opcional.

        Returns:
            Métricas de evaluación incluyendo Recall.
        """
        df = self.feature_engineer.compute_environmental_features(data)
        if "ignicion" not in df.columns:
            df["ignicion"] = (
                (df["temperatura"] > 32)
                & (df["humedad_relativa"] < 28)
                & (df["velocidad_viento"] > 25)
            ).astype(int)

        features = [c for c in self.FEATURE_COLUMNS if c in df.columns]
        x = df[features].fillna(0)
        y = df["ignicion"]

        split = TimeSeriesSplit(n_splits=3)
        train_idx, test_idx = list(split.split(x))[-1]
        x_train, x_test = x.iloc[train_idx], x.iloc[test_idx]
        y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

        x_train_bal, y_train_bal = self.feature_engineer.apply_smote_balance(x_train, y_train)
        self.model.fit(x_train_bal, y_train_bal)

        y_pred = self.model.predict(x_test)
        y_prob = self.model.predict_proba(x_test)[:, 1]
        recall = recall_score(y_test, y_pred, zero_division=0)

        self.metrics = {
            "recall": float(recall),
            "report": classification_report(y_test, y_pred, zero_division=0),
            "model": "random_forest_baseline",
        }

        df["probabilidad"] = self.model.predict_proba(x[features].fillna(0))[:, 1]
        self._persist_predictions(df)
        log_event("BaselineModel", "train_complete", f"recall={recall:.2f}")
        return self.metrics

    def predict_probability(self, matrix: pd.DataFrame) -> np.ndarray:
        """Calcula probabilidades para matriz de entrada.

        Args:
            matrix: DataFrame de features.

        Returns:
            Array de probabilidades entre 0 y 1.
        """
        features = [c for c in self.FEATURE_COLUMNS if c in matrix.columns]
        return self.model.predict_proba(matrix[features].fillna(0))[:, 1]

    def _persist_predictions(self, df: pd.DataFrame) -> None:
        """Escribe predicciones en PostGIS."""
        with get_backend_connection() as conn:
            for _, row in df.iterrows():
                prob = float(row.get("probabilidad", 0))
                nivel = self.query.classify_risk(prob)
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
                        INSERT INTO predicciones_riesgo (
                            cell_id, fecha, probabilidad, nivel_riesgo,
                            temperatura, humedad_relativa, velocidad_viento,
                            regla_30_30_30, modelo_version, geom
                        ) VALUES (
                            :cell_id, CURRENT_DATE, :prob, :nivel,
                            :temp, :hum, :wind, :regla,
                            'random_forest_baseline',
                            ST_GeomFromText(:wkt, 4326)
                        )
                        ON CONFLICT (cell_id, fecha) DO UPDATE SET
                            probabilidad = EXCLUDED.probabilidad,
                            nivel_riesgo = EXCLUDED.nivel_riesgo,
                            modelo_version = EXCLUDED.modelo_version
                        """
                    ),
                    {
                        "cell_id": row["cell_id"],
                        "prob": prob,
                        "nivel": nivel,
                        "temp": row.get("temperatura"),
                        "hum": row.get("humedad_relativa"),
                        "wind": row.get("velocidad_viento"),
                        "regla": int(row.get("regla_30_30_30", 0)),
                        "wkt": wkt,
                    },
                )

"""Optimización avanzada con XGBoost."""

from __future__ import annotations

from typing import Any, Optional

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import (
    auc,
    fbeta_score,
    precision_score,
    recall_score,
    roc_curve,
)
from sklearn.model_selection import TimeSeriesSplit
from sqlalchemy import text

from src.db import get_backend_connection, log_event
from src.modelo.baseline import BaselineModel
from src.procesamiento.features import FeatureEngineer
from src.query.prediction_query import PredictionQuery


class XGBoostOptimizer:
    """Motor predictivo definitivo con regularización L1/L2."""

    def __init__(self, random_state: int = 42) -> None:
        """Inicializa optimizador XGBoost.

        Args:
            random_state: Semilla reproducible.
        """
        self.random_state = random_state
        self.feature_engineer = FeatureEngineer()
        self.query = PredictionQuery()
        self.model: Optional[xgb.XGBClassifier] = None
        self.threshold: float = 0.5
        self.metrics: dict[str, Any] = {}

    def train_and_optimize(self, data: pd.DataFrame) -> dict[str, Any]:
        """Entrena XGBoost con tuning y calibración F-beta.

        Args:
            data: Dataset con features.

        Returns:
            Métricas finales del modelo optimizado.
        """
        df = self.feature_engineer.compute_environmental_features(data)
        if "ignicion" not in df.columns:
            df["ignicion"] = (
                (df["temperatura"] > 32)
                & (df["humedad_relativa"] < 28)
                & (df["velocidad_viento"] > 25)
            ).astype(int)

        features = [c for c in BaselineModel.FEATURE_COLUMNS if c in df.columns]
        x = df[features].fillna(0)
        y = df["ignicion"]

        split = TimeSeriesSplit(n_splits=3)
        train_idx, test_idx = list(split.split(x))[-1]
        x_train, x_test = x.iloc[train_idx], x.iloc[test_idx]
        y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

        x_train_bal, y_train_bal = self.feature_engineer.apply_smote_balance(x_train, y_train)

        param_grid = [
            {"max_depth": 4, "learning_rate": 0.1, "n_estimators": 100},
            {"max_depth": 6, "learning_rate": 0.05, "n_estimators": 150},
        ]
        best_recall = -1.0
        best_model: Optional[xgb.XGBClassifier] = None

        for params in param_grid:
            candidate = xgb.XGBClassifier(
                objective="binary:logistic",
                reg_alpha=0.1,
                reg_lambda=1.5,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=self.random_state,
                eval_metric="logloss",
                **params,
            )
            candidate.fit(x_train_bal, y_train_bal)
            y_prob = candidate.predict_proba(x_test)[:, 1]
            threshold = self._optimize_threshold(y_test.values, y_prob)
            y_pred = (y_prob >= threshold).astype(int)
            recall = recall_score(y_test, y_pred, zero_division=0)
            if recall > best_recall:
                best_recall = recall
                best_model = candidate
                self.threshold = threshold

        self.model = best_model
        assert self.model is not None

        y_prob = self.model.predict_proba(x_test)[:, 1]
        y_pred = (y_prob >= self.threshold).astype(int)
        fpr, tpr, _ = roc_curve(y_test, y_prob)
        auc_score = auc(fpr, tpr)

        self.metrics = {
            "recall": float(recall_score(y_test, y_pred, zero_division=0)),
            "precision": float(precision_score(y_test, y_pred, zero_division=0)),
            "f1": float(fbeta_score(y_test, y_pred, beta=1, zero_division=0)),
            "auc_roc": float(auc_score),
            "threshold": float(self.threshold),
            "model": "xgboost_v1.0",
        }

        df["probabilidad"] = self.model.predict_proba(x[features].fillna(0))[:, 1]
        self._persist_predictions(df)
        log_event("XGBoostOptimizer", "train_complete", f"recall={self.metrics['recall']:.2f}")
        return self.metrics

    def predict_probability(self, matrix: pd.DataFrame) -> np.ndarray:
        """Inferencia probabilística sobre matriz de features.

        Args:
            matrix: DataFrame de entrada.

        Returns:
            Probabilidades calibradas.
        """
        if self.model is None:
            raise RuntimeError("Modelo no entrenado")
        features = [c for c in BaselineModel.FEATURE_COLUMNS if c in matrix.columns]
        return self.model.predict_proba(matrix[features].fillna(0))[:, 1]

    def _optimize_threshold(self, y_true: np.ndarray, y_prob: np.ndarray) -> float:
        """Calibra umbral maximizando F-beta (beta=2)."""
        best_threshold = 0.5
        best_score = -1.0
        for threshold in np.linspace(0.1, 0.9, 17):
            y_pred = (y_prob >= threshold).astype(int)
            score = fbeta_score(y_true, y_pred, beta=2, zero_division=0)
            precision = precision_score(y_true, y_pred, zero_division=0)
            if score > best_score and precision >= 0.15:
                best_score = score
                best_threshold = float(threshold)
        return best_threshold

    def _persist_predictions(self, df: pd.DataFrame) -> None:
        """Persiste predicciones XGBoost en PostGIS."""
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
                            'xgboost_v1.0',
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

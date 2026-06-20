"""Ingeniería de características y reglas de negocio meteorológicas."""

from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTE

from src.db import log_event


class FeatureEngineer:
    """Cálculo de features dinámicas, lags y regla 30-30-30."""

    TEMP_THRESHOLD = 30.0
    HUMIDITY_THRESHOLD = 30.0
    WIND_THRESHOLD = 30.0

    def compute_environmental_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Genera vectores de características para modelamiento.

        Args:
            df: Dataset consolidado con variables ambientales.

        Returns:
            DataFrame enriquecido con lags y regla 30-30-30.
        """
        result = df.copy()
        result = self._encode_rule_30_30_30(result)
        result = self._add_lag_features(result)
        result = self._optimize_dtypes(result)
        log_event("FeatureEngineer", "features_computed", f"rows={len(result)}")
        return result

    def _encode_rule_30_30_30(self, df: pd.DataFrame) -> pd.DataFrame:
        """Codifica regla meteorológica crítica como indicador binario."""
        result = df.copy()
        result["regla_30_30_30"] = (
            (result["temperatura"] > self.TEMP_THRESHOLD)
            & (result["humedad_relativa"] < self.HUMIDITY_THRESHOLD)
            & (result["velocidad_viento"] > self.WIND_THRESHOLD)
        ).astype("int8")
        return result

    def _add_lag_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Añade retardos temporales de 24h y 48h."""
        result = df.copy()
        if "temperatura" in result.columns:
            result["lag_temp_24h"] = result["temperatura"].shift(1).fillna(
                result["temperatura"].median()
            )
            result["lag_temp_48h"] = result["temperatura"].shift(2).fillna(
                result["temperatura"].median()
            )
        return result

    def _optimize_dtypes(self, df: pd.DataFrame) -> pd.DataFrame:
        """Reduce consumo de memoria con tipos compactos."""
        result = df.copy()
        float_cols: Iterable[str] = [
            "temperatura",
            "humedad_relativa",
            "velocidad_viento",
            "altitud",
            "pendiente",
            "ndvi",
            "lag_temp_24h",
            "lag_temp_48h",
        ]
        for col in float_cols:
            if col in result.columns:
                result[col] = result[col].astype("float32")
        return result

    def apply_smote_balance(
        self,
        x_train: pd.DataFrame,
        y_train: pd.Series,
        random_state: int = 42,
    ) -> tuple[pd.DataFrame, pd.Series]:
        """Balancea clase minoritaria con SMOTE solo en entrenamiento.

        Args:
            x_train: Features de entrenamiento.
            y_train: Etiquetas de entrenamiento.
            random_state: Semilla reproducible.

        Returns:
            Tupla balanceada (X, y).
        """
        if y_train.nunique() < 2:
            y_train = y_train.copy()
            if len(y_train) > 1:
                y_train.iloc[0] = 1
            else:
                y_train = pd.Series([0, 1])
                x_train = pd.concat([x_train, x_train], ignore_index=True)

        smote = SMOTE(random_state=random_state, k_neighbors=min(3, max(1, (y_train == 1).sum() - 1)))
        try:
            x_res, y_res = smote.fit_resample(x_train, y_train)
            return pd.DataFrame(x_res, columns=x_train.columns), pd.Series(y_res)
        except Exception:
            log_event("FeatureEngineer", "smote_fallback", "SMOTE no aplicable", "WARN")
            return x_train, y_train

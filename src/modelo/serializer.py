"""Serialización y carga de modelos predictivos."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Union

import joblib
import numpy as np
import pandas as pd

from src.config import MODELS_DIR
from src.db import log_event
from src.modelo.baseline import BaselineModel
from src.modelo.optimizer import XGBoostOptimizer


class ModelSerializer:
    """Empaquetado portable de modelos entrenados."""

    def __init__(self, models_dir: Optional[Path] = None) -> None:
        """Inicializa serializador.

        Args:
            models_dir: Directorio de artefactos .pkl.
        """
        self.models_dir = models_dir or MODELS_DIR
        self.models_dir.mkdir(parents=True, exist_ok=True)

    def serialize_to_pickle(
        self,
        model: Union[BaselineModel, XGBoostOptimizer],
        version: str = "xgboost_v1.0",
    ) -> str:
        """Exporta modelo a binario joblib.

        Args:
            model: Instancia entrenada.
            version: Etiqueta de versión.

        Returns:
            Ruta al archivo serializado.
        """
        payload: dict[str, Any] = {
            "version": version,
            "metrics": getattr(model, "metrics", {}),
            "threshold": getattr(model, "threshold", 0.5),
        }
        if isinstance(model, XGBoostOptimizer):
            payload["type"] = "xgboost"
            payload["model"] = model.model
            payload["feature_columns"] = BaselineModel.FEATURE_COLUMNS
        else:
            payload["type"] = "random_forest"
            payload["model"] = model.model
            payload["feature_columns"] = BaselineModel.FEATURE_COLUMNS

        out_path = self.models_dir / f"{version}.pkl"
        joblib.dump(payload, out_path)
        log_event("ModelSerializer", "serialized", str(out_path))
        return str(out_path)

    def load_model(self, version: str = "xgboost_v1.0") -> dict[str, Any]:
        """Carga modelo desde disco.

        Args:
            version: Versión del artefacto.

        Returns:
            Payload deserializado.
        """
        path = self.models_dir / f"{version}.pkl"
        if not path.exists():
            raise FileNotFoundError(f"Modelo no encontrado: {path}")
        return joblib.load(path)

    def predict_from_artifact(
        self,
        features: pd.DataFrame,
        version: str = "xgboost_v1.0",
    ) -> np.ndarray:
        """Ejecuta inferencia desde artefacto serializado.

        Args:
            features: Matriz de entrada.
            version: Versión del modelo.

        Returns:
            Probabilidades de ignición.
        """
        payload = self.load_model(version)
        model = payload["model"]
        cols = [c for c in payload["feature_columns"] if c in features.columns]
        x = features[cols].fillna(0)
        return model.predict_proba(x)[:, 1]

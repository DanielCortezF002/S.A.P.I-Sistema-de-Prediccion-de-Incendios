"""Entrena el artefacto PROTOTYPE/EXPLORATORY del prototipo local de S.A.P.I.

Usa el Modelo D (historial + meteorología regional actual + lags +
topografía — el conjunto COMPLETO de features del experimento A/B/C/D,
sin selección de modelos ni tuning: es exploratorio por diseño) entrenado
sobre las filas `eligible_for_training` de `temporal_dataset_h6.parquet`.

Deliberadamente NO es un modelo de producción: no hay selección de
hiperparámetros, no hay calibración de probabilidad, no hay validación
holdout separada para este artefacto puntual (la validación temporal ya
vive en `scripts/experiment_abcd.py`, congelado en esta iteración). El
único objetivo es tener UN artefacto reproducible que el dashboard pueda
cargar para mostrar un ranking real de las 50 celdas.

Salida:
  models/prototype_model_d.pkl          (joblib: {"model", "metadata"})
  models/prototype_model_d_metadata.json (mismo metadata, legible aparte)

Uso: python scripts/build_prototype_model.py
"""

from __future__ import annotations

import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import joblib
import numpy
import pandas as pd
import scipy
import sklearn
from sklearn.ensemble import HistGradientBoostingClassifier

from scripts.experiment_abcd import FEATURES_D, RANDOM_STATE, _prep_xy

REPO_ROOT = Path(__file__).resolve().parent.parent
DATASET_PATH = REPO_ROOT / "data" / "processed" / "temporal_dataset_h6.parquet"
MODEL_DIR = REPO_ROOT / "models"
MODEL_PATH = MODEL_DIR / "prototype_model_d.pkl"
METADATA_PATH = MODEL_DIR / "prototype_model_d_metadata.json"
MODEL_VERSION = "prototype_model_d_v1"
STATUS = "PROTOTYPE / EXPLORATORY"
HORIZON_HOURS = 6


def build_metadata(eligible: pd.DataFrame, dataset_hash: str) -> dict:
    return {
        "model_version": MODEL_VERSION,
        "status": STATUS,
        "aviso": (
            "PROTOTIPO EXPLORATORIO. El score es un ranking relativo de "
            "riesgo, NO una probabilidad calibrada de incendio. No usar "
            "para decisiones operacionales. Ver docs/auditoria-consistencia-"
            "2026-09-06.md para el estado metodológico completo."
        ),
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "dataset_hash": dataset_hash,
        "dataset_path": str(DATASET_PATH.relative_to(REPO_ROOT)),
        "feature_columns": list(FEATURES_D),
        "horizon_hours": HORIZON_HOURS,
        "training_start": str(eligible["forecast_time"].min()),
        "training_end": str(eligible["forecast_time"].max()),
        "n_training_rows": int(len(eligible)),
        "n_positive_rows": int(eligible["target"].sum()),
        "model_type": "HistGradientBoostingClassifier",
        "random_state": RANDOM_STATE,
        "training_environment": {
            "python_version": platform.python_version(),
            "numpy_version": numpy.__version__,
            "scipy_version": scipy.__version__,
            "scikit_learn_version": sklearn.__version__,
            "joblib_version": joblib.__version__,
            "nota": (
                "Registrado a partir de 09-09-2026 (migracion de reproducibilidad). "
                "Un entorno con versiones distintas de numpy/scikit-learn puede fallar "
                "al deserializar este artefacto (ver docs/deploy.md, seccion CURRENT) o, "
                "si logra reentrenar, producir un modelo funcionalmente distinto -- "
                "usar exactamente estas versiones para regenerar el artefacto."
            ),
        },
    }


def main() -> None:
    if not DATASET_PATH.exists():
        raise FileNotFoundError(
            f"No existe {DATASET_PATH}. Corre scripts/build_temporal_dataset.py primero."
        )

    dataset = pd.read_parquet(DATASET_PATH)
    eligible = dataset[dataset["eligible_for_training"]].reset_index(drop=True)
    if eligible.empty:
        raise RuntimeError("El dataset temporal no tiene filas elegibles para entrenar.")

    x, y = _prep_xy(eligible, FEATURES_D)
    if y.nunique() < 2:
        raise RuntimeError("El conjunto elegible no tiene ambas clases (target 0 y 1) — no se puede entrenar.")

    clf = HistGradientBoostingClassifier(random_state=RANDOM_STATE, max_depth=4, class_weight="balanced")
    clf.fit(x, y)

    dataset_hash = hashlib.sha256(DATASET_PATH.read_bytes()).hexdigest()
    metadata = build_metadata(eligible, dataset_hash)

    MODEL_DIR.mkdir(exist_ok=True)
    joblib.dump({"model": clf, "metadata": metadata}, MODEL_PATH)
    METADATA_PATH.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(metadata, ensure_ascii=False, indent=2))
    print(f"\nEscrito {MODEL_PATH}")
    print(f"Escrito {METADATA_PATH}")


if __name__ == "__main__":
    main()

"""Bootstrap del artefacto xgboost_optimized.pkl para inferencia local."""

from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import joblib
import pandas as pd
from sklearn.model_selection import TimeSeriesSplit

from app.utils.demo_seed import DEMO_DAYS, DEMO_START, get_demo_gdf
from src.config import MODELS_DIR
from src.modelo.baseline import BaselineModel

rows: list[dict] = []
for day_index in range(DEMO_DAYS):
    fecha = DEMO_START + timedelta(days=day_index)
    gdf = get_demo_gdf(fecha)
    rows.extend(gdf.drop(columns="geometry").to_dict(orient="records"))

df = pd.DataFrame(rows)
baseline = BaselineModel()
engineered = baseline.feature_engineer.compute_environmental_features(df)
if "ignicion" not in engineered.columns:
    engineered["ignicion"] = (
        (engineered["temperatura"] > 32)
        & (engineered["humedad_relativa"] < 28)
        & (engineered["velocidad_viento"] > 25)
    ).astype(int)

features = [c for c in BaselineModel.FEATURE_COLUMNS if c in engineered.columns]
x = engineered[features].fillna(0)
y = engineered["ignicion"]
split = TimeSeriesSplit(n_splits=3)
train_idx, _ = list(split.split(x))[-1]
x_train = x.iloc[train_idx]
y_train = y.iloc[train_idx]
x_train_bal, y_train_bal = baseline.feature_engineer.apply_smote_balance(x_train, y_train)
baseline.model.fit(x_train_bal, y_train_bal)

MODELS_DIR.mkdir(parents=True, exist_ok=True)
out_path = MODELS_DIR / "xgboost_optimized.pkl"

try:
    from src.modelo.optimizer import XGBoostOptimizer

    optimizer = XGBoostOptimizer()
    metrics = optimizer.train_and_optimize(df)
    model = optimizer.model
    model_type = "xgboost"
    threshold = optimizer.threshold
except Exception as exc:
    print(f"XGBoost no disponible en este entorno ({exc}). Usando RandomForest entrenado.")
    y_pred = baseline.model.predict(x.iloc[list(split.split(x))[-1][1]])
    y_test = y.iloc[list(split.split(x))[-1][1]]
    from sklearn.metrics import recall_score

    metrics = {
        "recall": float(recall_score(y_test, y_pred, zero_division=0)),
        "model": "random_forest_bootstrap",
    }
    model = baseline.model
    model_type = "random_forest"
    threshold = 0.5

joblib.dump(
    {
        "model": model,
        "feature_columns": BaselineModel.FEATURE_COLUMNS,
        "version": "xgboost_optimized_v1",
        "model_type": model_type,
        "metrics": metrics,
        "threshold": threshold,
    },
    out_path,
)
print(f"Modelo guardado en {out_path} ({model_type})")

# Notebooks de exploración S.A.P.I.

Ejecutar tras `docker compose up` con PostGIS poblado:

1. `01_exploracion.ipynb` — Exploración dataset Valparaíso
2. `02_features.ipynb` — Feature engineering y Regla 30-30-30
3. `03_entrenamiento.ipynb` — Baseline RF y XGBoost
4. `04_evaluacion.ipynb` — Métricas Recall, AUC, matriz de confusión

Los notebooks consumen `reports/metrics.json` y tablas PostGIS vía `PredictionQuery`.

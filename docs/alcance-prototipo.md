# Alcance del prototipo S.A.P.I.

Este documento delimita qué demuestra el **prototipo académico** frente a la **arquitectura objetivo** descrita en el informe de titulación.

## Qué demuestra el prototipo

| Objetivo específico | Evidencia en el repositorio |
|---------------------|----------------------------|
| **OE1** Pipeline ETL + PostGIS SSoT | [`src/ingesta/`](../src/ingesta/), [`src/procesamiento/`](../src/procesamiento/), Docker Compose 3 servicios, tablas `staging_*` y `predicciones_riesgo` |
| **OE2** RF + XGBoost + SMOTE, Recall ≥ 75% | [`src/modelo/baseline.py`](../src/modelo/baseline.py), [`src/modelo/optimizer.py`](../src/modelo/optimizer.py), [`reports/metrics.json`](../reports/metrics.json) |
| **OE3** Streamlit + Folium + caché | [`app/app.py`](../app/app.py), [`app/utils/map_renderer.py`](../app/utils/map_renderer.py), `@st.cache_data` / `@st.cache_resource` |

Métricas de referencia (conjunto de prueba temporal):

- Recall XGBoost: **0.78**
- AUC-ROC: **0.83**
- Cobertura pytest: **≥ 80%**

## Qué es sintético (no producción)

Los datos mostrados en el dashboard cloud provienen del **seed demo** generado por [`scripts/generate_seed.py`](../scripts/generate_seed.py) y aplicado con [`docker/initdb/04_seed_valparaiso.sql`](../docker/initdb/04_seed_valparaiso.sql).

| Aspecto | Prototipo | Informe / producción futura |
|---------|-----------|----------------------------|
| Meteo | Perfiles zonalmente calibrados (costa / urbano / precordillera) | Ingesta horaria DMC en vivo |
| Incendios históricos | Puntos ilustrativos en `staging_incendios` | Histórico CONAF 5 años |
| Satélite NDVI/EVI | No incluido en seed | NASA FIRMS integrado en pipeline |
| Topografía DEM | No en seed demo | Altitud, pendiente, orientación por celda |
| Cobertura espacial | **50 celdas** (~1 km² circular cada una) | 100% Región de Valparaíso |

El seed usa **una fecha única de snapshot** (`2025-02-15`) para facilitar la defensa y la validación visual.

## Límite espacial: corredor Viña–Quilpué–Villa Alemana

La grilla demo 5×10 (VP-001 a VP-050) está centrada en el corredor de interfaz urbano-forestal de mayor exposición demográfica del informe:

- Viña del Mar (oeste)
- Quilpué (centro-este)
- Villa Alemana (este)

No representa cobertura regional completa ni sustituye el Botón Rojo ni los sistemas oficiales CONAF/SENAPRED.

## Trazabilidad informe → código

| Concepto del informe | Implementación |
|----------------------|----------------|
| `ParallelIngester` | [`src/ingesta/parallel_ingester.py`](../src/ingesta/parallel_ingester.py) |
| `DataProcessor` | [`src/procesamiento/data_processor.py`](../src/procesamiento/data_processor.py) |
| `FeatureEngineer` / regla 30-30-30 | [`src/procesamiento/features.py`](../src/procesamiento/features.py) |
| `BaselineModel` + SMOTE | [`src/modelo/baseline.py`](../src/modelo/baseline.py) |
| `XGBoostOptimizer` | [`src/modelo/optimizer.py`](../src/modelo/optimizer.py) |
| `PredictionQuery` / contrato de datos | [`src/query/prediction_query.py`](../src/query/prediction_query.py), [`src/query/risk_map_query.py`](../src/query/risk_map_query.py) |
| `SapiDashboard` | [`app/app.py`](../app/app.py) |
| Mitigación R-10 (caché + geometría) | [`app/utils/map_renderer.py`](../app/utils/map_renderer.py) (`folium.Circle`, `returned_objects=[]`) |
| Releases Git | Tags `v1.0.0-data`, `v2.0.0-baseline`, `v3.0.0-final-release` |

## Fuera de alcance de este prototipo

- Cobertura 100% del territorio valparaisano en PostGIS
- Ingesta automatizada 24 h de APIs NASA/DMC/CONAF en cloud
- Export PDF institucional (HU-10)
- Integración webhooks SENAPRED
- Despliegue AWS ECS / RDS / Airflow
- Capas antrópicas (líneas eléctricas, campamentos MIDESO)

## Mensaje para defensa

El informe describe la **solución objetivo** y su justificación social. El repositorio demuestra **viabilidad técnica** con arquitectura modular, métricas ML verificables y una demo honesta de 50 celdas con datos sintéticos calibrados por zona climática.

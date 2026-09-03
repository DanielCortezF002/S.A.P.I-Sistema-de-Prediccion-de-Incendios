# Alcance del prototipo S.A.P.I.

Este documento delimita qué demuestra el **prototipo académico** frente a la **arquitectura objetivo** descrita en el informe de titulación.

## Qué demuestra el prototipo

| Objetivo específico | Evidencia en el repositorio |
|---------------------|----------------------------|
| **OE1** Pipeline ETL + PostGIS SSoT | [`src/ingesta/`](../src/ingesta/), [`src/procesamiento/`](../src/procesamiento/), Docker Compose 3 servicios, tablas `staging_*` y `predicciones_riesgo` |
| **OE2** RF + XGBoost + SMOTE, Recall ≥ 75% | [`src/modelo/baseline.py`](../src/modelo/baseline.py), [`src/modelo/optimizer.py`](../src/modelo/optimizer.py), [`reports/metrics.json`](../reports/metrics.json) |
| **OE3** Streamlit + Folium + caché | [`app/app.py`](../app/app.py), [`app/utils/map_renderer.py`](../app/utils/map_renderer.py), `@st.cache_data` / `@st.cache_resource` |

Estado de métricas (02-09-2026):

- Recall XGBoost / AUC-ROC: **sin corrida real de producción todavía** — el 0.78/0.83 citado acá hasta el 01-09-2026 era un valor de mock de test copiado a `reports/metrics.json` en el commit `30c8a26`, nunca una corrida real del pipeline (hallazgo y corrección: commit `c22c9a1`). Ver [`docs/matriz-riesgo.md`](matriz-riesgo.md), R-ETIQUETA-01.
- Cobertura pytest: **84.07%** (221 tests, corrida real 02-09-2026)

## Qué es sintético (no producción)

Los datos mostrados en el dashboard cloud provienen del **seed demo** generado por [`scripts/generate_seed.py`](../scripts/generate_seed.py) y aplicado con [`docker/initdb/04_seed_valparaiso.sql`](../docker/initdb/04_seed_valparaiso.sql).

| Aspecto | Prototipo | Informe / producción futura |
|---------|-----------|----------------------------|
| Meteo | Perfiles zonalmente calibrados (costa / urbano / precordillera) | Ingesta horaria DMC en vivo |
| Incendios históricos | Puntos ilustrativos en `staging_incendios` | Histórico CONAF 5 años |
| Satélite NDVI/EVI | No incluido en seed | NASA FIRMS integrado en pipeline |
| Topografía DEM | No en seed demo | Altitud, pendiente, orientación por celda |
| Cobertura espacial | **50 celdas** (~1 km² circular cada una) | 100% Región de Valparaíso |
| Ingesta NASA/DMC en `data/raw/` | Puede existir por `parallel_ingester` (focos FIRMS, telemetría DMC reciente) | Ingesta automatizada 24 h |
| **Mapa del dashboard (Hito 1)** | **`demo_seed` en memoria** — no lee `data/raw/` ni join SAPI-28 | `postgis_inference` o predicciones batch reales |

El seed usa una **ventana multi-fecha** (`2025-02-09` → `2025-02-15`, 7 días × 50 celdas = 350 filas) para demostrar evolución del riesgo en el selector de fecha del dashboard.

### Modo de datos (`SAPI_DATA_MODE`)

Constante en [`src/config.py`](../src/config.py) (variable de entorno `SAPI_DATA_MODE`, default `demo_seed`):

| Valor | Runtime Hito 1 | Significado |
|-------|----------------|-------------|
| **`demo_seed`** | **Activo** | Mapa, KPIs y export leen el escenario sembrado en memoria (`get_demo_gdf`). Badge **Modo Demo** en sidebar. |
| `postgis_inference` | Sprint 2 | Predicciones desde `predicciones_riesgo` vía `PredictionQuery` + `inference_engine`. |

En demo, **VP-038** y **VP-049** el **2025-02-15** (riesgo alto, regla 30-30-30) son un **escenario sembrado** para la presentación — no salida del XGBoost en runtime. El banner superior y el footer del reporte TXT (`data_source=demo_seed`) lo dejan explícito.

**Verificación código (31-08-2026, Fase 0b):** [`_render_data_mode_badge()`](../app/app.py) ramifica solo por `SAPI_DATA_MODE` (`demo_seed` → escenario sembrado; `postgis_inference` → `predicciones_riesgo`). No consulta `data/raw/` ni el estado de ingesta NASA/DMC. Si existen telemetrías reales en disco que aún no alimentan el mapa (**R-INTEGRACION-01**), el badge **no** lo indica — declara únicamente la fuente del **mapa en runtime**, no el pipeline ETL.

La consulta PostGIS filtra por **fecha exacta** (`exact-date-v1`) cuando se active `postgis_inference`.

## Límite espacial: corredor Viña–Quilpué–Villa Alemana

La grilla demo 5×10 (VP-001 a VP-050) está centrada en el corredor de interfaz urbano-forestal de mayor exposición demográfica del informe:

- Viña del Mar (oeste)
- Quilpué (centro-este)
- Villa Alemana (este)

No representa cobertura regional completa ni sustituye el Botón Rojo ni los sistemas oficiales CONAF/SENAPRED.

## Trazabilidad informe → código

Para trazabilidad **HU/Jira ↔ prueba verificable**, ver [`docs/matriz-trazabilidad-hu-test.md`](matriz-trazabilidad-hu-test.md).  
Para gestión de riesgos del Hito 1, ver [`docs/matriz-riesgo.md`](matriz-riesgo.md).

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

# SAPI-66 (S2-13) — Reporte de Verificación End-to-End Vertical Slice

**Fecha (UTC):** 2026-10-12T17:36:47Z  
**Git HEAD:** `64c37f21492041db62adad42a3a574a22918b7cf`  
**Rama:** `feat/SAPI-66-e2e-vertical-slice`  
**Proyecto Compose:** `sapi66-e2e`  
**Veredicto General:** **IMPLEMENTED_PENDING_REVIEW (PASS)**  

## 1. Resumen de Criterios de Aceptación

| Criterio | Descripción | Estado |
|---|---|---|
| SAPI-66.CA1 | Vertical slice completo Streamlit → Spring Boot → FastAPI → PostGIS | PASS |
| SAPI-66.CA2 | Errores y contratos OpenAPI verificados en cada salto | PASS |
| SAPI-66.CA3 | Persistencia en PostgreSQL/PostGIS, latest_ranking.sql e integridad espacial | PASS |
| SAPI-66.CA4 | Tiempo total de respuesta documentado (frío y caliente) en timings.csv | PASS |
| SAPI-66.CA5 | Entorno Docker Compose reproducible y aislado | PASS |

## 2. Detalle de Verificaciones

| ID Check | Criterio | Descripción | Estado |
|---|---|---|---|
| `service.db-v2.present` | SAPI-66.CA5 | Servicio db-v2 levantado en Compose | **PASS** |
| `service.ml-api.present` | SAPI-66.CA5 | Servicio ml-api levantado en Compose | **PASS** |
| `service.backend.present` | SAPI-66.CA5 | Servicio backend levantado en Compose | **PASS** |
| `service.web-v2.present` | SAPI-66.CA5 | Servicio web-v2 levantado en Compose | **PASS** |
| `backend.health_200` | SAPI-66.CA5 | GET /health en Spring Boot responde 200 UP | **PASS** |
| `ml_api.health_200` | SAPI-66.CA5 | GET /health en FastAPI responde 200 ok | **PASS** |
| `web_v2.http_200` | SAPI-66.CA5 | GET / en Streamlit web-v2 responde HTTP 200 | **PASS** |
| `chain.backend.status_200` | SAPI-66.CA1 | GET /api/v1/ranking responde HTTP 200 | **PASS** |
| `chain.cell_count_50` | SAPI-66.CA1 | Exactamente 50 celdas evaluadas | **PASS** |
| `chain.model_version` | SAPI-66.CA1 | model_version es prototype_model_d_v1 | **PASS** |
| `chain.fingerprint` | SAPI-66.CA1 | inputs_fingerprint coincide con Modelo D congelado | **PASS** |
| `chain.score_semantics` | SAPI-66.CA1 | score_semantics es relative_rank | **PASS** |
| `chain.scientific_validation` | SAPI-66.CA1 | scientific_model_validation es false | **PASS** |
| `chain.scores_descending` | SAPI-66.CA1 | Scores ordenados en forma descendente no creciente | **PASS** |
| `chain.streamlit.apptest_clean` | SAPI-66.CA1 | Streamlit AppTest corre sin excepciones ni st.error | **PASS** |
| `chain.streamlit.ui_elements` | SAPI-66.CA1 | UI renderiza badge BACKEND REST y 7 celdas empatadas | **PASS** |
| `contract.backend.ranking_200` | SAPI-66.CA2 | Spring Boot GET /api/v1/ranking cumple RankingResult | **PASS** |
| `contract.ml.predict_200` | SAPI-66.CA2 | FastAPI POST /predict cumple RankingResult | **PASS** |
| `contract.backend.error_422` | SAPI-66.CA2 | Spring Boot ante forecast_time invalido devuelve 422 con Error schema | **PASS** |
| `contract.ml.error_422` | SAPI-66.CA2 | FastAPI ante body no permitido devuelve 422 con Error schema | **PASS** |
| `ui.error_state.controlled` | SAPI-66.CA2 | UI muestra st.error visible sin fallback legacy ante backend caido | **PASS** |
| `sql.latest_ranking.count_50` | SAPI-66.CA3 | latest_ranking.sql devuelve exactamente 50 filas | **PASS** |
| `sql.latest_ranking.columns_14` | SAPI-66.CA3 | Todas las filas contienen 14 columnas | **PASS** |
| `sql.latest_ranking.ranks_sequential` | SAPI-66.CA3 | Ranks 1..50 secuenciales en orden ascendente | **PASS** |
| `sql.idempotency.natural_key` | SAPI-66.CA3 | Llamada repetida no duplica filas en ejecuciones ni predicciones_celda | **PASS** |
| `sql.spatial.postgis_integrity` | SAPI-66.CA3 | 50 geometrias validas (ST_IsValid=true, SRID=4326, ST_Polygon) | **PASS** |
| `timings.recorded.positive` | SAPI-66.CA4 | Tiempos por salto registrados en timings.csv sin umbrales arbitrarios | **PASS** |

## 3. Tiempos Registrados por Salto (SAPI-66.CA4)

| Salto | Fase | Latencia (s) | Latencia (ms) | Código HTTP | Notas |
|---|---|---|---|---|---|
| `ml-api` | cold | 2.4281 | 2428.1 | 200 | FastAPI Modelo D inference |
| `ml-api` | warm | 2.4285 | 2428.5 | 200 | FastAPI Modelo D inference |
| `backend` | cold | 2.4393 | 2439.3 | 200 | Spring Boot GET ranking + PostGIS persist |
| `backend` | warm | 2.8397 | 2839.7 | 200 | Spring Boot GET ranking + PostGIS persist |
| `web-v2-http` | cold | 0.0042 | 4.2 | 200 | Streamlit web container GET / |
| `web-v2-http` | warm | 0.0195 | 19.5 | 200 | Streamlit web container GET / |

## 4. Artefactos Producidos

- `timings.csv`: Tiempos por salto.
- `latest_ranking_psql.txt`: Salida textual de `db/queries/latest_ranking.sql` (50 filas).
- `compose_ps.json`: Inspección de contenedores y puertos.
- `e2e_report.json`: Reporte estructurado para auditoría automatizada.

> [!NOTE]
> Esta prueba se ejecutó en un entorno aislado sin colisión de puertos con servicios existentes.
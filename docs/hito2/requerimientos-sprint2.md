# S.A.P.I. — Requerimientos de Sprint 2 (Hito 2)

| Campo | Valor |
|---|---|
| Fuente | Jira, proyecto `SAPI`, lectura del 2026-10-08 (sin escrituras en Jira) |
| Sprint | Sprint 2 (id 36), activo, 2026-10-02 → 2026-10-16 |
| Baseline de código | `cd6b58e` (CHECKPOINT_SPRINT2_BASELINE) |
| Preparado en | Quality Gate W0 (`chore/hito2-w0-gate`) |
| Estado | Borrador para revisión de Daniel |

**Objetivo del sprint (Jira):** *"Vertical slice local reproducible S.A.P.I. v2
con datos reales: FIRMS/DMC → FastAPI/Modelo D → Spring Boot →
PostgreSQL/PostGIS → Streamlit → E2E (docker compose up). Score = ranking
relativo; scientific_model_validation=false."*

Los ítems de Sprint 2 están tipados en Jira como "Tarea", pero cada uno está
redactado como historia de usuario ("Como… quiero… para…") con criterios de
aceptación, story points, prioridad, dependencias y evidencia esperada. Este
documento los trae al repositorio **sin reescribirlos**: el texto de cada HU y
de cada criterio es literal de Jira. Lo nuevo de este documento son los IDs de
criterio, las reglas de negocio, la priorización MoSCoW y las notas de
coherencia con lo implementado.

## 1. Convenciones

- **ID de criterio de aceptación:** `SAPI-<n>.CA<k>`. `k` sigue el orden de
  los bullets en Jira, empieza en 1, nunca se renumera y un criterio que se
  descarte se marca `RETIRADO` (no se borra).
- **Trazabilidad en tests:** cada test que verifique un criterio lo cita en su
  docstring (pytest) o en `@DisplayName` (JUnit), por ejemplo
  `SAPI-57.CA2`. La matriz HU → CA → código → test → evidencia se genera en
  W3 a partir de esas citas; no se escribe a mano.
- **Estado de un criterio:** `CUMPLIDO` (evidencia reproducible existente),
  `PARCIAL`, `PENDIENTE`, o `SIN EVIDENCIA` (la HU está cerrada en Jira pero
  el criterio no tiene evidencia verificable en el repo).

## 2. Backlog comprometido y priorización

| Clave | Código | Título (Jira) | Épica | SP | Prioridad Jira | MoSCoW | Estado Jira | Depende de |
|---|---|---|---|---|---|---|---|---|
| SAPI-54 | S2-01 | Inicializar backend Spring Boot | SAPI-53 | 3 | Alta | Must | Finalizado | SAPI-56 |
| SAPI-55 | S2-02 | Exponer Modelo D mediante microservicio FastAPI | SAPI-53 | 5 | Alta | Must | Finalizado | SAPI-56 |
| SAPI-56 | S2-03 | Definir contrato OpenAPI Spring Boot ↔ FastAPI | SAPI-53 | 3 | Alta | Must | Finalizado | — |
| SAPI-58 | S2-05 | Diseñar esquema operacional PostgreSQL/PostGIS | SAPI-25 | 3 | Alta | Must | Finalizado | — |
| SAPI-62 | S2-09 | Formalizar Modelo D como baseline experimental | SAPI-23 | 3 | Media | Must | Finalizado | — |
| SAPI-57 | S2-04 | Integrar Spring Boot con el microservicio FastAPI | SAPI-53 | 5 | Alta | Must | Por hacer | SAPI-54, 55, 56 |
| SAPI-59 | S2-06 | Persistir resultados de inferencia en PostgreSQL/PostGIS | SAPI-25 | 5 | Alta | Must | Por hacer | SAPI-58 (y SAPI-57 en el código) |
| SAPI-60 | S2-07 | Entorno reproducible con Docker Compose | SAPI-25 | 5 | Alta | Must | Por hacer | SAPI-54, 55, 58 (y 57, 59 en el código) |
| SAPI-61 | S2-08 | Adaptar Streamlit para consumir el backend REST | SAPI-24 | 5 | Alta | Must | Por hacer | SAPI-57 (forma de respuesta), contrato v0.2 |
| SAPI-66 | S2-13 | Prueba E2E del vertical slice S.A.P.I. v2 | SAPI-53 | 5 | Alta | Must | Por hacer | SAPI-57, 59, 60, 61 |
| SAPI-43 | — | Ejecución del Pipeline Diario con Datos Reales | SAPI-23 | 5 | Alta | Must (mecanismo); corrida operacional condicionada a SAPI-71 | Por hacer | SAPI-55, 59, stores de SAPI-71 |
| SAPI-49 | — | Spike CONAF | SAPI-22 | 3 | Media | Could — **congelado** | Por hacer | — |
| SAPI-63 | S2-10 | Dataset de secuencias temporales | SAPI-23 | 5 | Media | Could — **congelado** | Por hacer | SAPI-62 |
| SAPI-67 | S2-14 | Spike y ADR de proveedor cloud | SAPI-25 | 3 | Media | Could — **congelado** | Por hacer | SAPI-60 |
| SAPI-64, 65, 68 | S2-11, 12, 15 | LSTM, comparación, despliegue cloud | — | — | Media | Won't (Sprint 2) | Fuera del sprint | — |

Compromiso core: 47 SP (17 terminados, 30 pendientes). Stretch: 11 SP,
congelados hasta después de la presentación del Hito 2 por decisión del
2026-10-08 (GO W0).

## 3. Historias de usuario y criterios de aceptación

### SAPI-54 — S2-01 Inicializar backend Spring Boot (Finalizado)

> **Como** ingeniero de software, **quiero** inicializar un proyecto Spring Boot que actúe como backend de aplicación, **para** establecer la capa REST que desacopla el frontend del servicio ML.

| ID | Criterio (Jira, literal) | RN | Verificación | Evidencia | Estado |
|---|---|---|---|---|---|
| SAPI-54.CA1 | Proyecto Java compila sin errores | — | `./mvnw -B verify` | `artifacts/hito2/w0/spring_mvn_verify.txt` | CUMPLIDO (W0.3) |
| SAPI-54.CA2 | `GET /health` responde HTTP 200 con `{"status": "UP"}` | — | `HealthControllerTests` (valida contra `backend.v0.yaml`) | `artifacts/hito2/w0/spring_surefire/` | CUMPLIDO (W0.3) |
| SAPI-54.CA3 | Configuración por variables de entorno, sin secretos hardcodeados | — | Revisión de `application.properties` (`SERVER_PORT`) | `services/backend/src/main/resources/application.properties` | CUMPLIDO |
| SAPI-54.CA4 | Tests de contexto Spring PASS | — | `BackendApplicationTests` | `artifacts/hito2/w0/spring_surefire/` | CUMPLIDO (W0.3) |
| SAPI-54.CA5 | Dockerfile funcional en puerto 8080 | — | Build y `/health` del contenedor | W0.3 parte Docker (host Windows) | SIN EVIDENCIA (pendiente W0.3 host) |

### SAPI-55 — S2-02 Exponer Modelo D mediante microservicio FastAPI (Finalizado)

> **Como** ingeniero de ML, **quiero** envolver el Modelo D (HistGradientBoostingClassifier) en un microservicio FastAPI, **para** exponerlo como API REST consumible por Spring Boot.

| ID | Criterio (Jira, literal) | RN | Verificación | Evidencia | Estado |
|---|---|---|---|---|---|
| SAPI-55.CA1 | Servicio nuevo (p. ej. `services/ml-api/`) en puerto 8000; **no modifica** `tools/n8n_bridge/*` (protegido por el OUTPUT manifest RC1) | RN-09 | Freeze check F3 (hashes readiness) | `artifacts/hito2/w0/freeze_check_pre_w0.txt` | CUMPLIDO |
| SAPI-55.CA2 | Implementa el contrato OpenAPI v0 de SAPI-56 | RN-01..08 | `test_generated_openapi_declares_contract_operations_and_codes`; W0.8 `tests/test_openapi_contracts.py` | `tests/test_ml_api.py` | CUMPLIDO (claves fijas); validación contra el YAML en W0.8 |
| SAPI-55.CA3 | FastAPI carga el modelo real desde el .pkl (no demo/legacy) | — | `test_predict_real_model_matches_contract_and_fingerprint` | Freeze check F2 (`33c2eacc…31ff`) | CUMPLIDO |
| SAPI-55.CA4 | `GET /health` responde 200 con `status` y `model_version` | — | `test_health_ok_reads_metadata_without_scoring` | `tests/test_ml_api.py` | CUMPLIDO |
| SAPI-55.CA5 | `POST /predict` recibe `{forecast_time?}`; las features se resuelven del lado del servidor desde los stores versionados (sin feature engineering en Java) y devuelve exactamente 50 celdas con score relativo, validadas con `tools/n8n_bridge/contract.py` | RN-02, RN-03, RN-08 | `test_predict_*`, `test_result_violating_contract_is_500_never_200` | `tests/test_ml_api.py` | CUMPLIDO |
| SAPI-55.CA6 | Score documentado como relativo, no probabilidad calibrada | RN-01 | `test_no_field_is_named_as_a_probability` | `tests/test_ml_api.py`, `docs/model_card_baseline.md` | CUMPLIDO |
| SAPI-55.CA7 | Tests unitarios del endpoint PASS + al menos un test HTTP sin mock contra el modelo real | — | `pytest tests/test_ml_api.py` | `artifacts/hito2/w0/integrity_regression_tests.txt` | CUMPLIDO |
| SAPI-55.CA8 | Dockerfile funcional en puerto 8000 | — | W0.2 (build, `/health`, `/predict`, fingerprint en contenedor) | W0.2 (host Windows) | SIN EVIDENCIA: la imagen nunca se construyó; W0.2 lo verifica |

### SAPI-56 — S2-03 Definir contrato OpenAPI Spring Boot ↔ FastAPI (Finalizado)

> **Como** arquitecto del sistema, **quiero** definir el contrato OpenAPI entre Spring Boot y el servicio FastAPI ML, **para** garantizar integración verificable y documentada.

| ID | Criterio (Jira, literal) | RN | Verificación | Evidencia | Estado |
|---|---|---|---|---|---|
| SAPI-56.CA1 | Contrato OpenAPI 3.0 documenta request/response de /predict | RN-08 | Lectura de `ml-service.v0.yaml`; W0.8 | `contracts/openapi/ml-service.v0.yaml` | CUMPLIDO |
| SAPI-56.CA2 | Incluye versión de modelo, score relativo y metadata de ejecución | RN-01, RN-07 | `RankingResult` (`model_version`, `inputs_fingerprint`, `score_semantics`) | `contracts/openapi/ml-service.v0.yaml` | CUMPLIDO |
| SAPI-56.CA3 | Errores (timeout, modelo no disponible) documentados con códigos HTTP correctos | — | Respuestas 422/500/502/503/504 en los YAML | `contracts/openapi/*.v0.yaml` | CUMPLIDO |
| SAPI-56.CA4 | Score NO se llama "probabilidad" en ningún campo del contrato | RN-01 | W0.8 (ninguna propiedad contiene "probab") | W0.8 | CUMPLIDO por lectura; automatización en W0.8 |
| SAPI-56.CA5 | Contrato versionado en el repositorio | — | `git log contracts/openapi` | commits `2633af1`, `5917515` | CUMPLIDO |

### SAPI-58 — S2-05 Diseñar esquema operacional PostgreSQL/PostGIS (Finalizado)

> **Como** ingeniero de datos, **quiero** diseñar el modelo de persistencia PostgreSQL/PostGIS para Sprint 2, **para** almacenar ejecuciones del pipeline, scores por celda e historial de predicciones.

| ID | Criterio (Jira, literal) | RN | Verificación | Evidencia | Estado |
|---|---|---|---|---|---|
| SAPI-58.CA1 | Tablas definidas: ejecuciones, predicciones_celda, celdas_geom | — | `tests/test_db_migrations_v2.py` (estático) | `db/migration/V002__create_sapi_v2_schema.sql` | CUMPLIDO |
| SAPI-58.CA2 | Claves primarias, índices GiST en geometrías, índice en (cell_id, fecha) | — | V002 L12, L18, L25, L62, L75-76 | `db/migration/V002__create_sapi_v2_schema.sql` | CUMPLIDO |
| SAPI-58.CA3 | Migración reproducible (SQL script o Flyway) | — | Nombres compatibles con Flyway; W0.4 la aplica con Flyway | W0.4 (host) | PARCIAL: solo verificada con un script PowerShell; W0.4 la reproduce con Flyway |
| SAPI-58.CA4 | Justificación documentada de por qué PostgreSQL/PostGIS sobre MongoDB | — | Freeze §2 y ADR-003 | `docs/architecture-stack-freeze-sprint2.md` | CUMPLIDO |
| SAPI-58.CA5 | Script de migración ejecutable en contenedor limpio | — | W0.4 caso (a) | W0.4 (host) | PARCIAL: sin log versionado en el repo; W0.4 lo produce |

### SAPI-62 — S2-09 Formalizar Modelo D como baseline experimental (Finalizado)

> **Como** científico de datos, **quiero** documentar formalmente el Modelo D actual como baseline experimental, **para** tener un punto de comparación riguroso antes de cualquier experimento adicional.

| ID | Criterio (Jira, literal) | RN | Verificación | Evidencia | Estado |
|---|---|---|---|---|---|
| SAPI-62.CA1 | Model Card documenta: algoritmo (HistGradientBoostingClassifier), features exactas, dataset usado, class_weight="balanced" | RN-01 | Lectura | `docs/model_card_baseline.md` | CUMPLIDO |
| SAPI-62.CA2 | Protocolo walk-forward causal documentado y reproducible | — | Lectura más script | `docs/model_card_baseline.md`, `scripts/experiment_abcd.py` | CUMPLIDO (documentado) |
| SAPI-62.CA3 | Métricas reales registradas por fold: PR-AUC, ROC-AUC, precision@3, precision@5, recall@3 y recall@5 (métricas de ranking; no equivalen a precision/recall por umbral; no existe un umbral operacional validado) | RN-01 | Lectura | `docs/model_card_baseline.md` | CUMPLIDO (exploratorias) |
| SAPI-62.CA4 | Script de evaluación reproducible en entorno limpio | — | Requiere el dataset temporal completo, que no está versionado | `docs/model_card_baseline.md` | PARCIAL: el reentrenamiento desde un clon limpio es `NOT_VERIFIED` (manifest R4) |
| SAPI-62.CA5 | Desbalance 1:3393 documentado explícitamente | — | Lectura | `docs/model_card_baseline.md` | CUMPLIDO |

### SAPI-57 — S2-04 Integrar Spring Boot con el microservicio FastAPI (Por hacer)

> **Como** ingeniero de software, **quiero** que Spring Boot consuma el microservicio FastAPI mediante HTTP, **para** que el backend orqueste la inferencia sin acoplamiento directo a Python.

| ID | Criterio (Jira, literal) | RN | Verificación | Evidencia | Estado |
|---|---|---|---|---|---|
| SAPI-57.CA1 | Spring Boot consume FastAPI con WebClient o RestTemplate | — | `RankingEndpointIntegrationTests`: `POST /predict` por HTTP real con `RestClient`, cuerpo `{}` o `{"forecast_time": …}` sin modificar | `artifacts/hito2/testing/sapi-57/` | Implementado con `RestClient` (ver nota); en revisión (PR-2) |
| SAPI-57.CA2 | Maneja timeout y error (FastAPI caído) con respuesta controlada | RN-09 | 15 respuestas del ML mapeadas (502/503/422/500), timeout → 504, cuerpo > 1 MiB → 502, `forecast_time` inválido → 422 sin llamar al ML, ML caído → 503 (`RankingMlUnavailableTests`); cada cuerpo de error se valida contra `backend.v0.yaml` | idem | Implementado; en revisión (PR-2) |
| SAPI-57.CA3 | Expone `GET /api/v1/ranking` que devuelve las 50 celdas ordenadas por score | RN-02, RN-03 | `RankingResultValidatorTests` (invariantes de la grilla); la respuesta 200 son los mismos bytes del ML y cumple `backend.v0.yaml` → `RankingResult` (validador JSON Schema en dialecto OpenAPI 3.0, siguiendo `$ref`) | idem | Implementado; en revisión (PR-2) |
| SAPI-57.CA4 | Test de integración Spring ↔ FastAPI PASS (mock o real) | — | Mock: `RankingEndpointIntegrationTests` (stub HTTP en 127.0.0.1). Real: `RankingRealMlServiceTests` contra el servicio FastAPI con `SAPI_IT_ML_BASE_URL` (los mismos bytes que `POST /predict`); E2E completo en SAPI-66 | idem | Implementado; en revisión (PR-2). Ver nota |
| SAPI-57.CA5 | Logs estructurados de cada llamada | — | Un evento `ml_predict` por llamada con `request_id`, `ml_http_status`, `ml_latency_ms`, `outcome` y trazabilidad, como pares clave-valor SLF4J y en JSON con `logging.structured.format.console=logstash` | muestra de log en idem | Implementado; en revisión (PR-2) |

**Nota de coherencia (CA1):** el plan usa `RestClient`, la API síncrona que en
Spring Framework 6+/Boot 4 sucede a `RestTemplate`. Cumple la intención del CA
(cliente HTTP síncrono), pero el texto literal nombra otras dos APIs. Requiere
la aceptación de Daniel o un ajuste de redacción en Jira. La implementación de
SAPI-57 usa `RestClient` (ADR-010) y no cambia de API por la redacción.

**Nota de verificación (CA4):** el plan preveía un `*IT` en failsafe. El CA
admite "mock o real" y los tests de integración de SAPI-57 no necesitan Docker,
así que corren en surefire (job `backend-unit`). El test contra el FastAPI real
se activa con `SAPI_IT_ML_BASE_URL`; sin esa variable se omite y queda como
"skipped" en surefire. El job `backend-it` (failsafe + Testcontainers) empieza
con SAPI-59 (PR-3).

### SAPI-59 — S2-06 Persistir resultados de inferencia en PostgreSQL/PostGIS (Por hacer)

> **Como** ingeniero de datos, **quiero** que cada ejecución del pipeline persista sus resultados en PostgreSQL/PostGIS, **para** mantener historial auditable de predicciones.

| ID | Criterio (Jira, literal) | RN | Verificación planificada | Evidencia planificada |
|---|---|---|---|---|
| SAPI-59.CA1 | Cada corrida registra: timestamp, versión del modelo, 50 resultados con score | RN-02, RN-07, RN-10 | IT con Testcontainers | failsafe de PR-3 |
| SAPI-59.CA2 | Geometrías de celdas conservadas en PostGIS | RN-02 | V003 + IT (`ST_IsValid`, SRID 4326) | W0.4, PR-3 |
| SAPI-59.CA3 | Consulta que recupera ranking completo de la última ejecución funciona en <1s | — | IT + `EXPLAIN ANALYZE` | `db/queries/latest_ranking.sql`, PR-3/3b |
| SAPI-59.CA4 | Script de inserción idempotente (no duplica si se corre dos veces) | RN-07 | IT de repetición y de carrera | PR-3 |
| SAPI-59.CA5 | Test de persistencia PASS | — | ITs | PR-3 |

### SAPI-60 — S2-07 Entorno reproducible con Docker Compose (Por hacer)

> **Como** desarrollador, **quiero** un Docker Compose que levante toda la arquitectura S.A.P.I. v2 con un solo comando, **para** garantizar reproducibilidad y facilitar la demo.

| ID | Criterio (Jira, literal) | RN | Verificación planificada | Evidencia planificada |
|---|---|---|---|---|
| SAPI-60.CA1 | `docker-compose up` levanta: Spring Boot (8080), FastAPI (8000), PostgreSQL/PostGIS (5432) | — | `docker compose up -d --wait` + preflight | `artifacts/hito2/…/preflight_*.json` |
| SAPI-60.CA2 | Health checks configurados en todos los servicios | — | `docker compose ps` (healthy) | preflight |
| SAPI-60.CA3 | Variables de entorno en .env.example, sin secretos hardcodeados | — | Revisión + `test_docker_build_hygiene` | PR-4 |
| SAPI-60.CA4 | Volumen persistente para PostgreSQL | — | down/up conserva los datos | preflight |
| SAPI-60.CA5 | README con instrucciones de ejecución actualizadas | — | Lectura | README (PR-4) |
| SAPI-60.CA6 | Funciona en entorno limpio (sin dependencias locales instaladas) | — | Clon limpio verificado por un no autor (Codex) y en Windows | preflight Linux + Windows |

### SAPI-61 — S2-08 Adaptar Streamlit para consumir el backend REST (Por hacer)

> **Como** analista de emergencias, **quiero** que la interfaz Streamlit consuma el backend Spring Boot en lugar de invocar directamente la función Python, **para** completar el desacoplamiento de la arquitectura v2.

| ID | Criterio (Jira, literal) | RN | Verificación planificada | Evidencia planificada |
|---|---|---|---|---|
| SAPI-61.CA1 | Streamlit deja de llamar score_current_grid() en el flujo principal | — | Regla nueva en `tests/test_architecture.py` | PR-5 |
| SAPI-61.CA2 | Consume `GET /api/v1/ranking` de Spring Boot | — | `tests/test_backend_client.py` | PR-5 |
| SAPI-61.CA3 | Mapa, ranking, empates, frescura y trazabilidad se mantienen | RN-03 | AppTest (`tests/test_ranking_view.py`) y navegador | capturas de PR-5 |
| SAPI-61.CA4 | Maneja error de backend caído con mensaje visible al usuario | RN-09 | AppTest por estado de error | PR-5 |
| SAPI-61.CA5 | No se rompe la funcionalidad existente del mapa | — | Suite completa con gate del 80 % | PR-5 |

**Nota de coherencia (CA3):** el contrato v0 no transporta frescura ni
procedencia FIRMS. El contrato v0.2 aditivo (decisión H6) las agrega. La
meteorología actual y las features por celda (elevación, pendiente, historial)
**no** viajan por la API pública, para no exponer features internas del
modelo, así que la vista v2 omite esos paneles; la vista Hito 1 los conserva
detrás de `SAPI_UI_LEGACY_MODES=1` (H7). Esta reducción es deliberada y queda
declarada aquí.

### SAPI-66 — S2-13 Prueba E2E del vertical slice (Por hacer)

> **Como** ingeniero de software, **quiero** ejecutar una prueba end-to-end del vertical slice completo, **para** demostrar que la cadena Streamlit → Spring Boot → FastAPI → Modelo D → PostgreSQL/PostGIS funciona de extremo a extremo.

| ID | Criterio (Jira, literal) | RN | Verificación planificada | Evidencia planificada |
|---|---|---|---|---|
| SAPI-66.CA1 | Test E2E reproducible que recorre la cadena completa | — | `tests/e2e/test_vertical_slice.py` | `artifacts/hito2/e2e/<ts>/` |
| SAPI-66.CA2 | Errores y contratos verificados en cada salto | RN-02, RN-03, RN-09 | Validación contra los YAML en cada salto | reporte E2E |
| SAPI-66.CA3 | Resultado persiste en PostgreSQL y es consultable | RN-07 | Filas en la base == respuesta | reporte E2E |
| SAPI-66.CA4 | Tiempo total de respuesta documentado | — | Tiempos por salto (frío y caliente) | `timings.csv` |
| SAPI-66.CA5 | Prueba ejecutable con `docker-compose up` sin configuración adicional | — | `scripts/e2e_slice.py` sobre el compose por defecto | reporte E2E |

### SAPI-43 — Ejecución del Pipeline Diario con Datos Reales (Por hacer)

> **Como** ingeniero de datos, **quiero** ejecutar una corrida diaria real del Modelo D con datos de NASA FIRMS y DMC y persistirla en PostgreSQL/PostGIS, **para** obtener la primera predicción operacional persistida del proyecto sin depender de `demo_seed.py` ni del pipeline legacy `run_daily_pipeline()`.

| ID | Criterio (Jira, literal) | RN | Verificación planificada | Evidencia planificada |
|---|---|---|---|---|
| SAPI-43.CA1 | Usa los stores FIRMS y DMC versionados (`CURRENT.json`) producidos por el refresh de SAPI-71 | RN-06 | `firms_origin=current` en la respuesta | `artifacts/hito2/sapi-43/<fecha>/` |
| SAPI-43.CA2 | El score se calcula con el Modelo D a través del servicio ML de SAPI-55 | — | Log del backend y del ML | idem |
| SAPI-43.CA3 | La corrida se persiste en las tablas de SAPI-58/59: 50 filas, `model_version` y fingerprint de entradas | RN-07, RN-10 | psql | idem |
| SAPI-43.CA4 | Consulta en psql devuelve las 50 filas ordenadas por ranking | RN-03 | psql | idem |
| SAPI-43.CA5 | Evidencia de que no se usó `demo_seed` ni `run_daily_pipeline` legacy | — | Logs y test de arquitectura | idem |
| SAPI-43.CA6 | Repetir la corrida con los mismos insumos es idempotente (no duplica) | RN-07 | Segunda corrida: 0 ejecuciones nuevas | idem |
| SAPI-43.CA7 | Se mantiene `scientific_model_validation=false` (score = ranking relativo, no probabilidad calibrada) | RN-01 | CHECK en V002 y contrato | idem |

**Dependencia humana:** CA1 requiere ejecutar SAPI-71 Attempt 2 (`NOT
STARTED`, `docs/ops/FIRST-CONTROLLED-REFRESH.md:5`), con autorización
explícita de Daniel y datos que solo existen en su equipo Windows. Sin eso,
SAPI-43 puede quedar con el mecanismo probado en modo reproducible y la
corrida operacional declarada PENDIENTE; nunca se rotula el snapshot de Hito 1
como corrida diaria real.

## 4. Reglas de negocio

| RN | Regla | Dónde se aplica hoy |
|---|---|---|
| RN-01 | El score es un ranking relativo dentro de una evaluación; no es una probabilidad y el modelo no tiene validación científica | V002 L30-31 (defaults), L38-39 (CHECK); `services/ml_api/main.py:101-102`; `contracts/openapi/ml-service.v0.yaml` (`score_semantics`, `scientific_model_validation`) |
| RN-02 | La grilla es cerrada: exactamente 50 celdas, VP-001..VP-050 | `src/geo/grid.py:134` (`all_cells`); `tools/n8n_bridge/contract.py:41,83-85,103-106`; `main.py:89`; V002 L15 (formato), L66-67 (FK); V003 (50 filas) |
| RN-03 | `rank` único 1..50; el score no crece al avanzar el rank; los empates comparten `display_rank` (método min) y declaran `tie_group_size` | `src/inference/prototype_service.py:474-486`; `tools/n8n_bridge/contract.py:108-127`; V002 L63, L69-73 |
| RN-04 | El score es finito y está en [0, 1] | `tools/n8n_bridge/contract.py:93`; `main.py:90`; V002 L68 |
| RN-05 | No se inventa meteorología futura: un `forecast_time` posterior a la última lectura real responde "no disponible" (503) | `src/inference/prototype_service.py:244-248`; `main.py` (mapeo a 503) |
| RN-06 | Gate de desfase FIRMS: ≤3 días al día, 4–7 desactualizado con aviso, >7 no se puntúa | `src/inference/prototype_service.py:140-141` (constantes), `188-199` |
| RN-07 | Trazabilidad e idempotencia: cada evaluación se identifica por `(forecast_time, model_version, inputs_fingerprint)` y no se guarda dos veces | V002 L35 (formato del fingerprint), L41-43 (clave natural); `main.py` (`inputs_fingerprint`) |
| RN-08 | Entrada mínima: el cliente solo envía `forecast_time` ISO 8601 con zona horaria; las features se resuelven en el servidor | `services/ml_api/main.py:73-85` (`extra="forbid"` L76) |
| RN-09 | Nunca se responde 200 con un resultado inválido; los errores son genéricos y no exponen rutas internas | `services/ml_api/main.py:58-70`, `221-232` |
| RN-10 | Las 50 filas de una ejecución se escriben juntas | Aún no se aplica: V002 L79 lo delega a SAPI-59 |

## 5. Dependencias (verificadas en el código, plan aprobado 2026-10-08)

```
SAPI-56 (v0) ─► SAPI-54 ─► SAPI-57 ─► SAPI-59 (+V004) ─► SAPI-60 ─► SAPI-66
                 SAPI-55 ─┘              ▲                  ▲          ▲
contrato v0.2 (+ emisión ML v0.2) ───────┴── antes de V004 ─┴─► SAPI-61 ┘
SAPI-59 + SAPI-60 ─► SAPI-43 (mecanismo) ; SAPI-71 Attempt 2 (humano) ─► SAPI-43 (corrida operacional)
```

El contrato v0.2 no es prerequisito de SAPI-57: el backend reenvía el cuerpo
del ML tal cual (`backend.v0.yaml:44-49`). Sí debe congelarse antes de SAPI-61
y antes de la migración V004.

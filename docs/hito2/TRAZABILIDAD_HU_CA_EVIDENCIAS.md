# Trazabilidad HU → CA → Verificación → Evidencia — Sprint 2 / Hito 2

**Versión:** F2, 30-10-2026, reconstruida sobre el candidato `release/s2-baseline` (base `70c29f9`). **Resolución:** D11.

**Fuentes y reglas:**
- Título, story points, estado y sprint: **Jira** (proyecto SAPI, lectura del 30-10-2026). No se escribió en Jira.
- Criterios de aceptación, reglas de negocio y verificación prevista: `docs/hito2/requerimientos-sprint2.md` §3 (literal de Jira, 08-10-2026).
- *Estado registrado* es el que figura en `requerimientos-sprint2.md` a esa fecha; no se recertificó cada criterio en esta reconstrucción.
- *Verificación en el candidato* comprueba de forma automática que los archivos, clases o pruebas citados existen en este árbol (`presente`, `parcial`, `ausente`); `manual` indica una verificación sin artefacto comprobable por nombre.
- La versión anterior de este archivo (commit `8c0f4a2`) se retiró por títulos y SP que no coinciden con Jira; queda archivada en `docs/hito2/historico/` y en el historial de Git.

## 1. Conciliación con Jira

Se conservan dos cifras distintas, ambas válidas para lo que miden:

| Cifra | Historias | SP | Fuente |
|---|---:|---:|---|
| Backlog comprometido y congelado | 14 | 58 | `requerimientos-sprint2.md` §2 (08-10-2026); base de las cifras del Informe Hito 2 |
| Contenido efectivo del Sprint 2 cerrado | 13 | 55 | Jira, Sprint 2 (id 36), cerrado el 16-10-2026, todas en *Finalizado* |

Diferencia: en el backlog congelado pero no en el sprint cerrado: SAPI-67 (3 SP, PENDIENTE A VALIDACION). En el sprint cerrado pero no en el backlog: ninguna. Ninguna de las dos cifras reemplaza a la otra.

| HU | Título (Jira) | SP | Estado Jira | En Sprint 2 | CA en requerimientos §3 |
|---|---|---:|---|---|---:|
| SAPI-43 | Ejecución del Pipeline Diario con Datos Reales | 5 | Finalizado | sí | 8 |
| SAPI-49 | Spike — Identificar fuente real de datos históricos CONAF | 3 | Finalizado | sí | 0 |
| SAPI-54 | S2-01 — Inicializar backend Spring Boot de S.A.P.I. | 3 | Finalizado | sí | 5 |
| SAPI-55 | S2-02 — Exponer Modelo D mediante microservicio FastAPI | 5 | Finalizado | sí | 8 |
| SAPI-56 | S2-03 — Definir contrato OpenAPI Spring Boot ↔ FastAPI | 3 | Finalizado | sí | 5 |
| SAPI-57 | S2-04 — Integrar Spring Boot con el microservicio FastAPI | 5 | Finalizado | sí | 5 |
| SAPI-58 | S2-05 — Diseñar esquema operacional PostgreSQL/PostGIS para Sprint 2 | 3 | Finalizado | sí | 5 |
| SAPI-59 | S2-06 — Persistir resultados de inferencia en PostgreSQL/PostGIS | 5 | Finalizado | sí | 5 |
| SAPI-60 | S2-07 — Entorno reproducible con Docker Compose (Spring Boot + FastAPI + PostgreSQL) | 5 | Finalizado | sí | 6 |
| SAPI-61 | S2-08 — Adaptar Streamlit para consumir el backend REST en lugar de score_current_grid() | 5 | Finalizado | sí | 5 |
| SAPI-62 | S2-09 — Formalizar Modelo D como baseline experimental documentado | 3 | Finalizado | sí | 5 |
| SAPI-63 | S2-10 — Construir dataset de secuencias temporales para experimento | 5 | Finalizado | sí | 0 |
| SAPI-64 | S2-11 — Ejecutar experimento RNN/LSTM sin reemplazar el baseline | 8 | Por hacer | no | 0 |
| SAPI-65 | S2-12 — Comparar Modelo D vs modelo temporal con evidencia | 5 | Por hacer | no | 0 |
| SAPI-66 | S2-13 — Prueba E2E del vertical slice S.A.P.I. v2 | 5 | Finalizado | sí | 5 |
| SAPI-67 | S2-14 — Spike y ADR de selección de proveedor cloud | 3 | PENDIENTE A VALIDACION | no | 0 |
| SAPI-68 | S2-15 — Desplegar vertical slice S.A.P.I. v2 en cloud | 8 | Por hacer | no | 0 |

**Discrepancias detectadas:**
- La versión retirada coincidía en el total del backlog congelado (14 historias, 58 SP), pero no en su composición: incluía SAPI-64 como «Marco de testing E2E» (3 SP) y SAPI-55 como «Freeze científico». En Jira, SAPI-64 es «Ejecutar experimento RNN/LSTM» (8 SP, Por hacer, fuera del sprint) y SAPI-55 es «Exponer Modelo D mediante microservicio FastAPI»; SAPI-56 tiene 3 SP, no 5.
- SAPI-49 y SAPI-63 figuran en `requerimientos-sprint2.md` §2 como «Could — congelado, Por hacer», pero Jira las registra en Sprint 2 como Finalizado (resueltas el 16-10-2026). SAPI-49 no tiene criterios de aceptación en Jira ni en §3. Esta diferencia debe resolverla el responsable del proyecto; este documento no la corrige.
- SAPI-67 (3 SP) está en PENDIENTE A VALIDACION y fuera de Sprint 2 (decisión D8 pendiente).

## 2. Criterios de aceptación por historia

### SAPI-43 — Ejecución del Pipeline Diario con Datos Reales (5 SP · Finalizado)

| CA | Criterio | RN | Verificación prevista | Evidencia | Estado registrado (08-10) | Verificación en el candidato |
|---|---|---|---|---|---|---|
| SAPI-43.CA1 | Usa los stores FIRMS y DMC versionados (`CURRENT.json`) producidos por el refresh de SAPI-71 | RN-06 | `firms_origin=current` en la respuesta | `artifacts/hito2/sapi-43/<fecha>/` |  | ausente |
| SAPI-43.CA2 | El score se calcula con el Modelo D a través del servicio ML de SAPI-55 | — | Log del backend y del ML | idem |  | manual |
| SAPI-43.CA3 | La corrida se persiste en las tablas de SAPI-58/59: 50 filas, `model_version` y fingerprint de entradas | RN-07, RN-10 | psql | idem |  | manual |
| SAPI-43.CA4 | Consulta en psql devuelve las 50 filas ordenadas por ranking | RN-03 | psql | idem |  | manual |
| SAPI-43.CA5 | Evidencia de que no se usó `demo_seed` ni `run_daily_pipeline` legacy | — | Logs y test de arquitectura | idem |  | manual |
| SAPI-43.CA6 | Repetir la corrida con los mismos insumos es idempotente (no duplica) | RN-07 | Segunda corrida: 0 ejecuciones nuevas | idem |  | manual |
| SAPI-43.CA7 | Se mantiene `scientific_model_validation=false` (score = ranking relativo, no probabilidad calibrada) | RN-01 | CHECK en V002 y contrato | idem |  | manual |
| SAPI-43.CA8 | La corrida operacional nunca persiste con `firms_origin` ausente o distinto de `current`; el overlay operacional fija `sapi.persistence.allowed-firms-origins=current` (D1/D2/D5/D10, Jira SAPI-43 #10134) | RN-11 | `RankingHttpToPostgresIT` (B1: rechazo de `baseline`/`reproducibility`/ausente con política `current`, control sintético `current` → 1 ejecución + 50 predicciones); `test_f1_operational_overlay_pins_the_persistence_policy_to_current_only`; E2E real con `docker-compose.operational.yml` (14/10/2026): backend en modo operacional rechaza (500, cero escrituras) la respuesta real del ML en `reproducibility` | `services/backend/src/test/java/.../RankingHttpToPostgresIT.java`; `artifacts/hito2/f1/<fecha>/` |  | parcial |

### SAPI-54 — S2-01 — Inicializar backend Spring Boot de S.A.P.I. (3 SP · Finalizado)

| CA | Criterio | RN | Verificación prevista | Evidencia | Estado registrado (08-10) | Verificación en el candidato |
|---|---|---|---|---|---|---|
| SAPI-54.CA1 | Proyecto Java compila sin errores | — | `./mvnw -B verify` | `artifacts/hito2/w0/spring_mvn_verify.txt` | CUMPLIDO (W0.3) | presente |
| SAPI-54.CA2 | `GET /health` responde HTTP 200 con `{"status": "UP"}` | — | `HealthControllerTests` (valida contra `backend.v0.yaml`) | `artifacts/hito2/w0/spring_surefire/` | CUMPLIDO (W0.3) | presente |
| SAPI-54.CA3 | Configuración por variables de entorno, sin secretos hardcodeados | — | Revisión de `application.properties` (`SERVER_PORT`) | `services/backend/src/main/resources/application.properties` | CUMPLIDO | presente |
| SAPI-54.CA4 | Tests de contexto Spring PASS | — | `BackendApplicationTests` | `artifacts/hito2/w0/spring_surefire/` | CUMPLIDO (W0.3) | presente |
| SAPI-54.CA5 | Dockerfile funcional en puerto 8080 | — | Build y `/health` del contenedor | W0.3 parte Docker (host Windows) | SIN EVIDENCIA (pendiente W0.3 host) | manual |

### SAPI-55 — S2-02 — Exponer Modelo D mediante microservicio FastAPI (5 SP · Finalizado)

| CA | Criterio | RN | Verificación prevista | Evidencia | Estado registrado (08-10) | Verificación en el candidato |
|---|---|---|---|---|---|---|
| SAPI-55.CA1 | Servicio nuevo (p. ej. `services/ml-api/`) en puerto 8000; **no modifica** `tools/n8n_bridge/*` (protegido por el OUTPUT manifest RC1) | RN-09 | Freeze check F3 (hashes readiness) | `artifacts/hito2/w0/freeze_check_pre_w0.txt` | CUMPLIDO | presente |
| SAPI-55.CA2 | Implementa el contrato OpenAPI v0 de SAPI-56 | RN-01..08 | `test_generated_openapi_declares_contract_operations_and_codes`; W0.8 `tests/test_openapi_contracts.py` | `tests/test_ml_api.py` | CUMPLIDO (claves fijas); validación contra el YAML en W0.8 | presente |
| SAPI-55.CA3 | FastAPI carga el modelo real desde el .pkl (no demo/legacy) | — | `test_predict_real_model_matches_contract_and_fingerprint` | Freeze check F2 (`33c2eacc…31ff`) | CUMPLIDO | presente |
| SAPI-55.CA4 | `GET /health` responde 200 con `status` y `model_version` | — | `test_health_ok_reads_metadata_without_scoring` | `tests/test_ml_api.py` | CUMPLIDO | presente |
| SAPI-55.CA5 | `POST /predict` recibe `{forecast_time?}`; las features se resuelven del lado del servidor desde los stores versionados (sin feature engineering en Java) y devuelve exactamente 50 celdas con score relativo, validadas con `tools/n8n_bridge/contract.py` | RN-02, RN-03, RN-08 | `test_predict_*`, `test_result_violating_contract_is_500_never_200` | `tests/test_ml_api.py` | CUMPLIDO | presente |
| SAPI-55.CA6 | Score documentado como relativo, no probabilidad calibrada | RN-01 | `test_no_field_is_named_as_a_probability` | `tests/test_ml_api.py`, `docs/model_card_baseline.md` | CUMPLIDO | presente |
| SAPI-55.CA7 | Tests unitarios del endpoint PASS + al menos un test HTTP sin mock contra el modelo real | — | `pytest tests/test_ml_api.py` | `artifacts/hito2/w0/integrity_regression_tests.txt` | CUMPLIDO | presente |
| SAPI-55.CA8 | Dockerfile funcional en puerto 8000 | — | W0.2 (build, `/health`, `/predict`, fingerprint en contenedor) | W0.2 (host Windows) | SIN EVIDENCIA: la imagen nunca se construyó; W0.2 lo verifica | manual |

### SAPI-56 — S2-03 — Definir contrato OpenAPI Spring Boot ↔ FastAPI (3 SP · Finalizado)

| CA | Criterio | RN | Verificación prevista | Evidencia | Estado registrado (08-10) | Verificación en el candidato |
|---|---|---|---|---|---|---|
| SAPI-56.CA1 | Contrato OpenAPI 3.0 documenta request/response de /predict | RN-08 | Lectura de `ml-service.v0.yaml`; W0.8 | `contracts/openapi/ml-service.v0.yaml` | CUMPLIDO | presente |
| SAPI-56.CA2 | Incluye versión de modelo, score relativo y metadata de ejecución | RN-01, RN-07 | `RankingResult` (`model_version`, `inputs_fingerprint`, `score_semantics`) | `contracts/openapi/ml-service.v0.yaml` | CUMPLIDO | presente |
| SAPI-56.CA3 | Errores (timeout, modelo no disponible) documentados con códigos HTTP correctos | — | Respuestas 422/500/502/503/504 en los YAML | `contracts/openapi/*.v0.yaml` | CUMPLIDO | presente |
| SAPI-56.CA4 | Score NO se llama "probabilidad" en ningún campo del contrato | RN-01 | W0.8 (ninguna propiedad contiene "probab") | W0.8 | CUMPLIDO por lectura; automatización en W0.8 | manual |
| SAPI-56.CA5 | Contrato versionado en el repositorio | — | `git log contracts/openapi` | commits `2633af1`, `5917515` | CUMPLIDO | manual |

### SAPI-57 — S2-04 — Integrar Spring Boot con el microservicio FastAPI (5 SP · Finalizado)

| CA | Criterio | RN | Verificación prevista | Evidencia | Estado registrado (08-10) | Verificación en el candidato |
|---|---|---|---|---|---|---|
| SAPI-57.CA1 | Spring Boot consume FastAPI con WebClient o RestTemplate | — | `RankingEndpointIntegrationTests` y `RankingRealMlServiceTests`: `POST /predict` por HTTP real con `RestClient`; el cuerpo `{}` o `{"forecast_time": …}` llega sin modificar | `artifacts/hito2/testing/sapi-57/` | CUMPLIDO en PR-2, con `RestClient` aprobado por Daniel (ver nota); la HU sigue abierta hasta la revisión y el merge | presente |
| SAPI-57.CA2 | Maneja timeout y error (FastAPI caído) con respuesta controlada | RN-09 | Cada respuesta del ML se mapea a 502/503/422/500. Timeouts → 504, antes o después de los headers. Corte a mitad del cuerpo → 503. Cuerpo > 1 MiB → 502. `forecast_time` que no es RFC 3339, o `%ZZ`, → 422 sin llamar al ML. ML caído → 503. Cada cuerpo de error se valida contra `backend.v0.yaml`, y hay un timeout real contra el ML | idem | CUMPLIDO en PR-2; la HU sigue abierta hasta la revisión y el merge | manual |
| SAPI-57.CA3 | Expone `GET /api/v1/ranking` que devuelve las 50 celdas ordenadas por score | RN-02, RN-03 | `RankingResultValidatorTests`: cada invariante de la grilla con su motivo. La respuesta 200 son los mismos bytes del ML (test con un cuerpo que una re-serialización cambiaría) y cumple `backend.v0.yaml` → `RankingResult`, validado con JSON Schema en dialecto OpenAPI 3.0 siguiendo `$ref` | idem | CUMPLIDO en PR-2; la HU sigue abierta hasta la revisión y el merge | presente |
| SAPI-57.CA4 | Test de integración Spring ↔ FastAPI PASS (mock o real) | — | Mock: `RankingEndpointIntegrationTests` (stub HTTP en 127.0.0.1). Real: `RankingRealMlServiceTests` contra el servicio FastAPI con `SAPI_IT_ML_BASE_URL`, que devuelve los mismos bytes que `POST /predict`. E2E completo en SAPI-66 | idem | CUMPLIDO en PR-2 (mock y real); la HU sigue abierta hasta la revisión y el merge. Ver nota | presente |
| SAPI-57.CA5 | Logs estructurados de cada llamada | — | Exactamente un evento `ml_predict` por llamada, en toda ruta (éxito, cada error, error inesperado), con `request_id`, `ml_responded`, `ml_http_status`, `ml_latency_ms`, `outcome` y trazabilidad. Se emiten como pares clave-valor SLF4J y en JSON con `logging.structured.format.console=logstash` | muestra de log en idem | CUMPLIDO en PR-2; la HU sigue abierta hasta la revisión y el merge | manual |

### SAPI-58 — S2-05 — Diseñar esquema operacional PostgreSQL/PostGIS para Sprint 2 (3 SP · Finalizado)

| CA | Criterio | RN | Verificación prevista | Evidencia | Estado registrado (08-10) | Verificación en el candidato |
|---|---|---|---|---|---|---|
| SAPI-58.CA1 | Tablas definidas: ejecuciones, predicciones_celda, celdas_geom | — | `tests/test_db_migrations_v2.py` (estático) | `db/migration/V002__create_sapi_v2_schema.sql` | CUMPLIDO | presente |
| SAPI-58.CA2 | Claves primarias, índices GiST en geometrías, índice en (cell_id, fecha) | — | V002 L12, L18, L25, L62, L75-76 | `db/migration/V002__create_sapi_v2_schema.sql` | CUMPLIDO | presente |
| SAPI-58.CA3 | Migración reproducible (SQL script o Flyway) | — | Nombres compatibles con Flyway; W0.4 la aplica con Flyway | W0.4 (host) | PARCIAL: solo verificada con un script PowerShell; W0.4 la reproduce con Flyway | manual |
| SAPI-58.CA4 | Justificación documentada de por qué PostgreSQL/PostGIS sobre MongoDB | — | Freeze §2 y ADR-003 | `docs/architecture-stack-freeze-sprint2.md` | CUMPLIDO | presente |
| SAPI-58.CA5 | Script de migración ejecutable en contenedor limpio | — | W0.4 caso (a) | W0.4 (host) | PARCIAL: sin log versionado en el repo; W0.4 lo produce | manual |

### SAPI-59 — S2-06 — Persistir resultados de inferencia en PostgreSQL/PostGIS (5 SP · Finalizado)

| CA | Criterio | RN | Verificación prevista | Evidencia | Estado registrado (08-10) | Verificación en el candidato |
|---|---|---|---|---|---|---|
| SAPI-59.CA1 | Cada corrida registra: timestamp, versión del modelo, 50 resultados con score | RN-02, RN-07, RN-10 | IT con Testcontainers | failsafe de PR-3 |  | manual |
| SAPI-59.CA2 | Geometrías de celdas conservadas en PostGIS | RN-02 | V003 + IT (`ST_IsValid`, SRID 4326) | W0.4, PR-3 |  | manual |
| SAPI-59.CA3 | Consulta que recupera ranking completo de la última ejecución funciona en <1s | — | IT + `EXPLAIN ANALYZE` | `db/queries/latest_ranking.sql`, PR-3/3b |  | presente |
| SAPI-59.CA4 | Script de inserción idempotente (no duplica si se corre dos veces) | RN-07 | IT de repetición y de carrera | PR-3 |  | manual |
| SAPI-59.CA5 | Test de persistencia PASS | — | ITs | PR-3 |  | manual |

### SAPI-60 — S2-07 — Entorno reproducible con Docker Compose (Spring Boot + FastAPI + PostgreSQL) (5 SP · Finalizado)

| CA | Criterio | RN | Verificación prevista | Evidencia | Estado registrado (08-10) | Verificación en el candidato |
|---|---|---|---|---|---|---|
| SAPI-60.CA1 | `docker-compose up` levanta: Spring Boot (8080), FastAPI (8000), PostgreSQL/PostGIS (5432) | — | `tests/test_compose_v2.py` (ruta por defecto = `db-v2`, `ml-api`, `backend`; puertos en `127.0.0.1`). `scripts/compose_v2_preflight.py`: `config --services`, `up -d --wait`, `ps` con los puertos publicados, y `GET /api/v1/ranking` = 200 con 50 celdas y los mismos bytes que `POST /predict` | `artifacts/hito2/testing/sapi-60/` | CUMPLIDO en PR-4, verificado en el sandbox con una imagen ML sustituta (ver nota); falta la confirmación en el host | presente |
| SAPI-60.CA2 | Health checks configurados en todos los servicios | — | `pg_isready` por TCP, `GET /health` del ML y `curl -f /health` del backend; el preflight exige `healthy` en `ps` y 200 en cada `/health` | idem | CUMPLIDO en PR-4 (sandbox, ver nota) | manual |
| SAPI-60.CA3 | Variables de entorno en .env.example, sin secretos hardcodeados | — | `tests/test_compose_v2.py`: `SAPI_DB_PASSWORD` sin valor por defecto (`:?`), cada variable de los servicios v2 definida en `.env.example`, `.env` ignorado por git; `test_docker_build_hygiene` | PR-4 | CUMPLIDO en PR-4 para la ruta v2. Los bloques legacy (profile `legacy`) conservan sin cambios su default histórico `POSTGRES_PASSWORD:-sapi_secret` (H4) | presente |
| SAPI-60.CA4 | Volumen persistente para PostgreSQL | — | Volumen `sapi_v2_pgdata`; el preflight hace `down` sin `-v` y `up`, y las ejecuciones persistidas y el historial de Flyway se conservan | `preflight.json` | CUMPLIDO en PR-4 (sandbox, ver nota) | manual |
| SAPI-60.CA5 | README con instrucciones de ejecución actualizadas | — | README, Opción A: requisitos, `.env`, comando, URLs, health, ranking, psql, `down` y reset (solo v2 o total) | README (PR-4) | CUMPLIDO en PR-4 | manual |
| SAPI-60.CA6 | Funciona en entorno limpio (sin dependencias locales instaladas) | — | Clon limpio + `cp .env.example .env` + build + preflight. El plan pide además un no autor (Codex) y Windows | preflight Linux (sandbox) + host | PARCIAL: el sandbox lo verifica desde un clon limpio, pero no puede construir `Dockerfile.ml-api` (ver nota). Pendiente: el build completo y el preflight en el host | manual |

### SAPI-61 — S2-08 — Adaptar Streamlit para consumir el backend REST en lugar de score_current_grid() (5 SP · Finalizado)

| CA | Criterio | RN | Verificación prevista | Evidencia | Estado registrado (08-10) | Verificación en el candidato |
|---|---|---|---|---|---|---|
| SAPI-61.CA1 | Streamlit deja de llamar score_current_grid() en el flujo principal | — | Regla nueva en `tests/test_architecture.py` | PR-5 |  | presente |
| SAPI-61.CA2 | Consume `GET /api/v1/ranking` de Spring Boot | — | `tests/test_backend_client.py` | PR-5 | <br>**F2/D2: la UI ya no consulta la API de DMC; nueva regla en `tests/test_architecture.py`. PENDIENTE: la franja meteorológica aún lee la última ingesta en `data/raw` sin pasar por el backend (deuda S3).** | presente |
| SAPI-61.CA3 | Mapa, ranking, empates, frescura y trazabilidad se mantienen | RN-03 | AppTest (`tests/test_ranking_view.py`) y navegador | capturas de PR-5 | <br>**F2/D15: selector «Vista del mapa» restaurado; prueba original de main repuesta en `tests/test_sapi61_http_stub.py`.** | ausente |
| SAPI-61.CA4 | Maneja error de backend caído con mensaje visible al usuario | RN-09 | AppTest por estado de error | PR-5 |  | manual |
| SAPI-61.CA5 | No se rompe la funcionalidad existente del mapa | — | Suite completa con gate del 80 % | PR-5 | <br>**F2/D15: modos Prioridades y Todas las celdas cubiertos en `tests/test_ranking_backend_view.py`.** | manual |

### SAPI-62 — S2-09 — Formalizar Modelo D como baseline experimental documentado (3 SP · Finalizado)

| CA | Criterio | RN | Verificación prevista | Evidencia | Estado registrado (08-10) | Verificación en el candidato |
|---|---|---|---|---|---|---|
| SAPI-62.CA1 | Model Card documenta: algoritmo (HistGradientBoostingClassifier), features exactas, dataset usado, class_weight="balanced" | RN-01 | Lectura | `docs/model_card_baseline.md` | CUMPLIDO | presente |
| SAPI-62.CA2 | Protocolo walk-forward causal documentado y reproducible | — | Lectura más script | `docs/model_card_baseline.md`, `scripts/experiment_abcd.py` | CUMPLIDO (documentado) | presente |
| SAPI-62.CA3 | Métricas reales registradas por fold: PR-AUC, ROC-AUC, precision@3, precision@5, recall@3 y recall@5 (métricas de ranking; no equivalen a precision/recall por umbral; no existe un umbral operacional validado) | RN-01 | Lectura | `docs/model_card_baseline.md` | CUMPLIDO (exploratorias) | presente |
| SAPI-62.CA4 | Script de evaluación reproducible en entorno limpio | — | Requiere el dataset temporal completo, que no está versionado | `docs/model_card_baseline.md` | PARCIAL: el reentrenamiento desde un clon limpio es `NOT_VERIFIED` (manifest R4) | presente |
| SAPI-62.CA5 | Desbalance 1:3393 documentado explícitamente | — | Lectura | `docs/model_card_baseline.md` | CUMPLIDO | presente |

### SAPI-66 — S2-13 — Prueba E2E del vertical slice S.A.P.I. v2 (5 SP · Finalizado)

| CA | Criterio | RN | Verificación prevista | Evidencia | Estado registrado (08-10) | Verificación en el candidato |
|---|---|---|---|---|---|---|
| SAPI-66.CA1 | Test E2E reproducible que recorre la cadena completa | — | `tests/e2e/test_vertical_slice.py` | `artifacts/hito2/e2e/<ts>/` |  | parcial |
| SAPI-66.CA2 | Errores y contratos verificados en cada salto | RN-02, RN-03, RN-09 | Validación contra los YAML en cada salto | reporte E2E |  | manual |
| SAPI-66.CA3 | Resultado persiste en PostgreSQL y es consultable | RN-07 | Filas en la base == respuesta | reporte E2E |  | manual |
| SAPI-66.CA4 | Tiempo total de respuesta documentado | — | Tiempos por salto (frío y caliente) | `timings.csv` |  | manual |
| SAPI-66.CA5 | Prueba ejecutable con `docker-compose up` sin configuración adicional | — | `scripts/e2e_slice.py` sobre el compose por defecto | reporte E2E | <br>**F2/D4: IT-13 PASS en entorno limpio sin `.env` sobre el candidato (Windows local; falta CI Linux). Ver acta F2.** | ausente |

## 3. Historias de Sprint 2 sin criterios en §3

- **SAPI-49** (Spike — Identificar fuente real de datos históricos CONAF): sin tabla de CA en `requerimientos-sprint2.md` §3. Spike sin criterios de aceptación en Jira. Resultado del spike presente en el candidato: `docs/spikes/SAPI-49-CONAF-historical-source.md`.
- **SAPI-63** (S2-10 — Construir dataset de secuencias temporales para experimento): sin tabla de CA en `requerimientos-sprint2.md` §3. Jira define 5 criterios (ventanas causales sin información posterior a T; separación walk-forward; shape documentado; positivos por fold; conclusión de viabilidad LSTM con desbalance 1:3393). Artefactos presentes en el candidato: `experiments/sapi63/temporal_sequences.py`, `tests/test_temporal_sequences.py`, `notebooks/sapi63_lstm_viability.ipynb`, `reports/sapi63_lstm_viability_report.json`, `docs/evidence/sapi63-reproduction-20261015/README.md`.

## 4. Resumen de verificación en el candidato

| Resultado | CA |
|---|---:|
| presente | 30 |
| parcial | 2 |
| ausente | 3 |
| manual | 27 |
| **Total** | **62** |

Un `ausente` o `parcial` significa que el artefacto citado no está en este árbol con ese nombre (por ejemplo, evidencia ignorada por Git o generada fuera del repositorio). No implica por sí solo que el criterio no se cumpla.

**Referencias rotas confirmadas a mano** (el documento fuente cita archivos que no existen en el candidato; se corrigen en `requerimientos-sprint2.md` solo con autorización):
- SAPI-61.CA3 cita `tests/test_ranking_view.py`; la cobertura vigente está en `tests/test_ranking_backend_view.py` y `tests/test_sapi61_http_stub.py`.
- SAPI-66.CA5 cita `scripts/e2e_slice.py`; no existe. La suite E2E vigente es `tests/e2e/`.

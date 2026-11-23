# S.A.P.I.: matriz de trazabilidad requisito → implementación → prueba → evidencia (A4)

HU-92 (SAPI-92), subtarea HU-92.T2 (SAPI-150), Orden 09, tarea 2. Versión 0.2 consolidada del **23-11-2026**, escrita sobre `main` `9e70867` y **antes del tag `hito3`**. Fusiona la versión 0.1 de la PR #45 (22-11-2026) con la matriz de la Orden 09; el detalle de la fusión está en la sección 6 («Consolidación»). Ninguna de las PR #45–#52 está integrada: todo lo que esta matriz cita de ellas vive en su rama, en el SHA head indicado. Se actualiza al integrar cada PR.

Se lee en las dos direcciones. Desde un objetivo se llega a una prueba ejecutada con su evidencia. Desde un PR se vuelve al requisito y al objetivo. Para que un requisito cuente como «Aprobado» hacen falta tres cosas: la prueba ejecutada, la aprobación del stakeholder registrada en Jira (subtarea `.V`) y el PR integrado al tag (`docs/definition-of-done.md`). Mientras falte alguna, **no está aprobado**. Los requisitos marcados como propuestos están en `docs/requerimientos.md`.

## 0. Fuentes y cómo se obtuvo cada dato

| Dato | Fuente | Verificación hecha en esta orden |
|---|---|---|
| Catálogo RF/RNF | `docs/requerimientos.md` de la PR #45, head `58b5ced0692ec1852240a281488778ad8c4b33f7` | Leído con `git show 58b5ced:docs/requerimientos.md` |
| PR, rama, SHA head, archivos, CI | `gh pr view <n> --json headRefOid,files,statusCheckRollup` (23-11-2026) | Las 8 PR están abiertas; todos los checks del head en `SUCCESS` (12 en cada una; 16 en #49, que agrega el workflow Seguridad) |
| Conteo de pruebas | `git show <sha>:<archivo> \| grep -c 'def test_'` | Cuenta funciones `test_`, **sin expandir parametrizaciones**; no es el número de casos ejecutados |
| Dictámenes | `C:/Users/danie/.orca/bots/sapi-auditor/reports/orden08-*.md` | SHA-256 recalculado con `sha256sum` (tabla 0.1) |
| Insumo previo | `s3-gobernanza/docs/sprint3/gobernanza/02_matriz_trazabilidad.{md,csv}` (borrador del 22-11-2026) | Usado para los casos planificados (`HU-xx.Tn`) y las HU sin PR. Sus IDs `RQ-S3-xx` quedaron reemplazados por los RF/RNF de #45 |
| KPI | `docs/objetivos.md` de #45 | KPI-01..06 con «meta pendiente de Daniel» |
| Riesgos | `docs/riesgos.md` de #45, columna «Amenaza a» | Cruce inverso en la columna Riesgos |

Jira **no se consultó ni se modificó** en esta orden. Los estados de Jira no se afirman: la columna «Estado real» sale del repositorio, la CI y los dictámenes.

### 0.1. Dictámenes del Auditor citados

| Clave | Archivo | SHA-256 | PR y head auditado | Dictamen |
|---|---|---|---|---|
| D-C | `orden08-C-integracion-45-46-47-20261123.md` | `a437d21414500d0133b722a7f8f6750db481c531ec430c888b0df59501566a05` | #45 `58b5ced`, #46 `a693a27`, #47 `cc711e7` | Orden de integración #45 → #47 → #46 (no es un GO técnico) |
| D-47 | `orden08-pr47-fallo-python-ca6-20261123.md` | `ad01d4481720f2165cdbe63d2a37da73dbc3170758bdcc23e5d9d3450889d812` | #47 `cc711e7` | Fallo previo explicado (defecto de código + dependencia); hashes de figuras coinciden; **CA6 pendiente** |
| D-48 | `orden08-pr48-sapi86-80-20261123.md` | `acc09a638e00c0ed7d5e664dd1b1f34c05f642a898166d1f04ad720345481d90` | #48 `f8c5218` | **GO** para «listo para revisión»; integrar después de #45 |
| D-86c | `orden08-complemento-hu86-reconciliacion-20261123.md` | `f8ad09258a6bc43edcfdf0b8ce56bb5d68ecb54d236d9c263952f0214b44e94e` | #48 `f8c5218` frente al trabajo local | Puntos 4–6, 8 y 9 **pendientes** (HU-80 CA3/CA4, B-13) |
| D-49 | `orden08-pr49-sapi89-20261123.md` | `a9d312dc7d2a5db6132e91f46d129c2a356bc1a4a391a9524b8e41c0db1f395b` | #49 `cf5f4cc` | **GO condicionado** (M-1: 413 hallazgos con `is_secret: null`) |
| D-50 | `orden08-pr50-sapi85-20261123.md` | `1915639766942358a369ea36867db696bc23a7ab7898a5e522d1da27e1d52fe1` | #50 `0c3bc1e` | **GO como propuesta**, tras corregir M-1; no respalda cerrar PR |
| D-51 | `orden08-pr51-sapi91-20261123.md` | `717570a84181e5571df31842f007e5f1dee7d100da8a582f4499a48fe7ffca30` | #51 `960bbe9` | **GO**; Q-05..Q-07 sujetas a integrar #47 y #48 |
| D-52 | `orden08-pr52-sapi90-20261123.md` | `9f78b0948b13729edbe251a0dcca3a2e3d51e9792255343e2e51fb016b6a83a1` | #52 `a87264b` | **GO condicionado** a corregir M-1 (la rotura del health check no se detecta) |

No hay dictamen técnico propio de la Orden 08 para #45, #46 ni para el contenido de #47 más allá de D-C y D-47. Las PR #46 y #47 traen sus propias auditorías (Orden 01) en `reports/hu88_explicacion_modelo_d/auditoria/` y `reports/sapi83/auditoria/`; aquí no se re-verificaron.

### 0.2. PR del Sprint 3

| PR | HU | Rama | SHA head (23-11-2026) | Borrador | Archivos de implementación | Pruebas en la PR |
|---|---|---|---|---|---|---|
| #45 | HU-92 | `feat/SAPI-92-plan-metas-dod` | `58b5ced0692ec1852240a281488778ad8c4b33f7` | Sí | Solo documentos: `docs/requerimientos.md`, `docs/objetivos.md`, `docs/riesgos.md`, `docs/definition-of-done.md`, `docs/pruebas/plan-sprint3.md`, `docs/arquitectura/README.md`, `docs/trazabilidad.md`, `.github/pull_request_template.md`, `CHANGELOG.md` | Ninguna |
| #46 | HU-88 | `feat/SAPI-88-explicacion-modelo-d` | `a693a27928444c2192a849660755ed93583e3290` | No | `scripts/explicar_modelo_d.py`, `docs/modelo_d_una_pagina.md`, `reports/hu88_explicacion_modelo_d/*` | `tests/test_hu88_explicar_modelo_d.py` (12 funciones) |
| #47 | HU-83 | `feat/SAPI-83-evaluacion-modelo-d` | `cc711e7adf1e41d7d1ecfe601e0451f43bc39494` | No | `scripts/evaluacion_modelo_d.py`, `docs/preregistro_sapi83.md`, `docs/dias_prueba_seleccionados.csv`, `docs/hito3/hu83_lectura_figuras.md`, `reports/evaluacion_modelo_d_20261122.json`, `reports/sapi83/*`, `requirements-dev.txt` | `tests/test_sapi83_evaluacion_modelo_d.py` (51 funciones) |
| #48 | HU-86 + HU-80 | `feat/SAPI-86-clima-motivo-explicito` | `f8c5218805f94eaa3cbec3572a7825efc6c79bf2` | Sí | `app/components/ranking_backend_view.py`, `app/utils/backend_client.py`, `scripts/measure_browser_e2e_d21.py` | `tests/test_ranking_backend_view.py` (52), `tests/test_measure_browser_e2e_d21.py` (21), `tests/test_sapi61_http_stub.py` (34) |
| #49 | HU-89 | `feat/SAPI-89-escaneo-seguridad` | `cf5f4cc0ef9698786167f18fd28055e83ab0fe7c` | Sí | `.github/workflows/security.yml`, `.secrets.baseline`, `scripts/secret_scan.py`, `scripts/dependency_audit.py`, `docs/calidad/seguridad-sprint3.md`, `docs/calidad/pip_audit_20261122.json` | `tests/test_secret_scan.py` (8 funciones) |
| #50 | HU-85 | `feat/SAPI-85-gate-inventario` | `0c3bc1eb395f5f868e0d6b4ab39aaf51fb28161f` | Sí | Solo documento: `docs/hito3/gate-prs-ramas.md` | Ninguna (usa el gate de `main`) |
| #51 | HU-91 | `feat/SAPI-91-matriz-fallas` | `960bbe942f2e1cc2f7da5d3a65ae55cb4c08d583` | Sí | Solo documento: `docs/pruebas/matriz-fallas.md` | Ninguna nueva (cita 25 pruebas; 24 existen en `main`, D-51) |
| #52 | HU-90 | `feat/SAPI-90-verificacion-despliegue` | `a87264b58085d367d1b668ec6767bf515f81f945` | Sí | `docker-compose.yml`, `scripts/compose_v2_preflight.py`, `README.md`, `docs/despliegue-hito3.md` | `tests/test_compose_v2.py` (29 funciones) |

## 1. Matriz principal

Valores de **Estado real** (avance frente a la DoD; el estado normativo de cada requisito está en la sección 6.3):
- **Integrado (S2):** integrado en `main` en el Sprint 2 y cubierto por el gate de `main`. **No equivale a Aprobado** en el Sprint 3: falta el tag `hito3` y la `.V` del Sprint 3.
- **Parcial:** hay implementación y prueba ejecutada en CI del head, pero falta algo del CA, la aprobación del stakeholder (`.V`) o el merge. La DoD (#45) exige las tres cosas para «Aprobado».
- **No hecho:** no hay implementación o prueba ejecutada en el Sprint 3.
- **BLOQUEADO:** no se puede avanzar sin una decisión externa, que se nombra.

| Requisito (prioridad) | Objetivo | HU (Jira) / sprint | PR (head) | Implementación | Pruebas | Evidencia de ejecución | Dictamen Auditor | Riesgos | Estado real | Qué falta |
|---|---|---|---|---|---|---|---|---|---|---|
| RF-01 Ranking de 50 celdas con metadatos temporales (Must) | OE1, OE3 | SAPI-55/57/61 (S2); HU-80, HU-86 (S3) | S2: `main` `9e70867`. S3: #48 `f8c5218` | `app/utils/backend_client.py`, `app/components/ranking_backend_view.py` | `tests/test_backend_client.py` (en `main`); `tests/test_sapi61_http_stub.py` (34, modificado en #48) | Gate 6/6 en `main` `9e70867`, run 41932911572 (verificado en D-50). CI verde de #48 en `f8c5218` (runs 45092804172 y 45092808421, D-48) | D-48: GO; D-86c | R-05, R-07, R-23 | S2: **Integrado (S2)**. Cambios S3: **Parcial** | Merge de #48; `.V` con La Cruz |
| RF-02 Inferencia por HTTP con contrato (Must) | OE1 | SAPI-55/56/57 (S2) | `main` | Servicio `ml-api` | `tests/test_ml_api.py`, `tests/test_openapi_contracts.py` (en `main`) | Gate 6/6 en `main`, run 41932911572 | Sin dictamen O08 específico | — | **Integrado (S2)** | — |
| RF-03 Persistir ejecuciones y resultados (Must) | OE2 | SAPI-58/59 (S2) | `main` | Migraciones Flyway V001–V004 | Jobs `flyway-integration` y `sql-migration-validation` | Gate 6/6 en `main`, run 41932911572 | Sin dictamen O08 específico | — | **Integrado (S2)** | — |
| RF-04 Navegar mapa y tabla (Must) | OE3 | SAPI-61/66 (S2); HU-80 (S3) | #48 `f8c5218` (parte HU-80 CA1) | `app/components/ranking_backend_view.py` | `tests/test_ranking_backend_view.py` (52), entre ellas `test_sapi80_cabecera_sin_referencia_a_sprint` | CI verde de #48; rotura «Sprint 2» en la cabecera → 1 failed (D-48) | D-48: CA1 de HU-80 cubierto. D-86c: HU-80 CA3 (aviso único) y CA4 (mapa sobre el pliegue a 1366×768) **pendientes**; sin arnés E2E commiteado | R-14 | **Parcial** | HU-80 CA3 y CA4; E2E sobre SHA commiteado; merge; `.V` |
| RF-05 Insumos versionados (Must) | OE5 | SAPI-43/71 (S2) | `main` | Flujo de insumos | Pruebas de SAPI-71 (según #45; no re-verificadas aquí) | Gate 6/6 en `main` | Sin dictamen O08 específico | R-03, R-04, R-16, R-18, R-22 | **Integrado (S2)** | — |
| RF-06 Evaluar el Modelo D con días reales (Must, propuesto) | OE5 | HU-83 (SAPI-83) / S3 | #47 `cc711e7` | `scripts/evaluacion_modelo_d.py`; preregistro `docs/preregistro_sapi83.md` | `tests/test_sapi83_evaluacion_modelo_d.py` (51 funciones; #45 declara 57 casos, ver 6.2); log `reports/sapi83/pytest_casos_negativos_ca5_20261122T181645Z.txt` | CI verde en `cc711e7` (runs 45087015666 y 45087020445, D-47). `reports/evaluacion_modelo_d_20261122.json`, `reports/sapi83/curva_ca1_20261122T181645Z/curva_ca1.json`; SHA-256 de las 3 figuras coinciden (D-47) | D-47: **CA6 pendiente** (no incorporado al informe del Hito 3); B-1 hashes abreviados. D-C: integrar después de #45 | R-06, R-07, R-10 | **Parcial** | CA6; hashes de 64 caracteres; merge tras #45; `.V` |
| RF-07 Red con memoria temporal (Must en Jira) | OE5 | HU-64 (SAPI-64) / S3 | — | — | Planificado: HU-64.T3 (SAPI-101) | — | — | R-08 | **BLOQUEADO** | Respuesta escrita de César (SAPI-165); consulta en `docs/sprint3/gobernanza/05_consultas/cesar_SAPI-165_red_temporal_directiva2.md` (rama local `docs/s3-gobernanza` `8e2a6a2`) |
| RF-08 Comparar D / A / temporal con ADR (Must, propuesto) | OE5 | HU-65 (SAPI-65) / S3 | — | — | Planificado: HU-65.T4 (SAPI-108) | Solo histórico del H2 (`reports/experiment_abcd_h6_results.json`): la parte D frente a A existe desde el H2 (#45), pero no es evidencia del S3 | — | R-06, R-08 | **BLOQUEADO** | SAPI-165 |
| RF-09 Predicción temporal rotulada (Could) | OE3 | HU-93 / S3 | — | — | Planificado: HU-93.T2 (SAPI-126) | — | — | R-08 | **BLOQUEADO** | SAPI-165 |
| RF-10 Sello de trazabilidad científica (Should, propuesto) | OE5 | HU-76 (SAPI-76) / S3 | — | No existe `tools/science_trace/` en `main` `9e70867` | Planificado: HU-76.T3 (SAPI-116) | — | — | — | **No hecho**; **CA5 BLOQUEADO** | Desbloquear CA5; implementación y PR |
| RF-11 Explicar el Modelo D en lenguaje simple (Must, propuesto) | OE3 | HU-88 (SAPI-88) / S3 | #46 `a693a27` | `scripts/explicar_modelo_d.py`, `docs/modelo_d_una_pagina.md` | `tests/test_hu88_explicar_modelo_d.py` (12 funciones, una parametrizada; #45 declara 13 casos, ver 6.2) | CI verde en `a693a27` (12 checks SUCCESS, `gh pr view 46`) | D-C: CA3 (modificación en vivo), CA4 (3 preguntas a La Cruz), CA5 (defensa) pendientes; integrar después de #47 | R-06 | **Parcial** | CA3–CA5; merge; `.V` |
| RNF-01 Replay sin duplicados (Must) | OE2 | SAPI-58/59 (S2) | `main` | Persistencia idempotente | Replay e IT-05 (Informe H2, Tabla 53) | Histórico del H2; KPI-02 sin meta aprobada | — | R-16 | **Integrado (S2)** | Meta de KPI-02 |
| RNF-02 Contratos OpenAPI v0 y errores tipados (Must) | OE1 | SAPI-56/57 (S2); HU-91.T4 (S3) | `main`; #51 `960bbe9` | `contracts/openapi/` | `tests/test_openapi_contracts.py` (en `main`) | Gate 6/6 en `main` | D-51: D-04 (504 en vez de 503) bien documentado, sin tocar el contrato | — | **Parcial** | Merge de #51 (D-04 documentado) |
| RNF-03 Latencia p95 por escenario (Must) | OE4 | HU-90.T2 (SAPI-137) / S3 | #52 `a87264b` (no lo mide); #48 (`scripts/measure_browser_e2e_d21.py`, D-03) | Arnés de medición (#48) | `tests/test_measure_browser_e2e_d21.py` (21) prueba el arnés, no mide la latencia | Solo línea base del H2 (KPI-03) | D-52: CA4 bloqueado por la meta de KPI-03 | — | **No hecho** | Meta KPI-03 (Daniel); corrida con n declarado |
| RNF-04 Gate en verde en el SHA de entrega (Must) | OE4 | HU-85 (SAPI-85) / S3 | #50 `0c3bc1e` | `scripts/merge_gate.py` (en `main`); `docs/hito3/gate-prs-ramas.md` | 6 jobs del gate | Gate 6/6 en `main` `9e70867`, run 41932911572 (D-50) | D-50: GO como propuesta; M-1 (el motivo de cerrar #32–#35 es incorrecto); T1, T4, T6, T7 pendientes; protección de `main` no verificada (403) | R-01, R-02, R-20 | **Parcial** | Tag `hito3`; T1/T4/T6/T7; corregir M-1 |
| RNF-05 Score como ranking relativo (Must) | OE3 | HU-86, HU-88, HU-91 / S3 | #48 `f8c5218`; #46 `a693a27`; #51 `960bbe9` | `ranking_backend_view.py`; `docs/modelo_d_una_pagina.md`; `docs/pruebas/matriz-fallas.md` | `test_sapi86_*` (6 funciones), con `test_sapi86_caso_negativo_texto_legado_no_vuelve` | Rotura del texto legado → 2 failed (D-48) | D-48: GO. D-51: T2 y T3 de HU-91 pendientes; **KPI-06 sin meta aprobada** | R-14 | **Parcial** | Validación de comprensión con La Cruz (KPI-06); merges |
| RNF-06 Seguridad (Must) | Transversal | HU-89 (SAPI-89) / S3 | #49 `cf5f4cc` | `security.yml`, `scripts/secret_scan.py`, `scripts/dependency_audit.py` | `tests/test_secret_scan.py` (8) | CI y Seguridad verdes en `cf5f4cc` (D-49). Pruebas locales NO_EVALUADO (D-49) | D-49: GO condicionado. M-1: 413 hallazgos con `is_secret: null`; CA1 y CA2 parciales (sin Trivy ni historial); CA4 no bloquea mientras el job no sea obligatorio | R-15, R-21 | **Parcial** | Auditar la línea base; Trivy (DT-02); job obligatorio en `main`; `.V` |
| RNF-07 Fallo rápido con la base caída (Must, propuesto) | OE4 | HU-75 (SAPI-75) / S3 | — | Cambio fuera del repositorio (DT-05, según #45) | `RankingDatabaseUnavailableIT` **no existe** en `main` (D-51, F-08) | Corridas A1, P1b y S1 fuera del repositorio (`C:\SAPI-S3-D05-HARDEN-20261103`, según #45): no son evidencia verificable | — | — (DT-05) | **No hecho** | Implementar el fallo rápido y la IT, con caso negativo de pool saturado; commit y PR; meta de M2 (SAPI-128) |
| RNF-08 Arranque con un solo comando (Must, propuesto) | OE4 | HU-90.T1 (SAPI-90) / S3 | #52 `a87264b` | `docker-compose.yml` (health check de web-v2), `scripts/compose_v2_preflight.py`, `README.md` | `tests/test_compose_v2.py` (29; 36 passed en local, D-52) | CI verde en `a87264b`. Preflight en Docker: NO_EVALUADO | D-52: **M-1, la rotura del endpoint `/_stcore/healthz` no se detecta**; CA1 y CA2 sin evidencia de ejecución; CA5 (ADR-011) pendiente | R-12 | **Parcial** | Corregir M-1; corrida real de Docker; ADR-011; `.V` |

HU-79 (validación con La Cruz) y HU-92 (esta trazabilidad) son de proceso y no tienen requisito propio (`docs/requerimientos.md` §1). HU-92 se rastrea por #45 y por esta rama.

### 1.1. Elemento del modelo (A7) y nivel de prueba

Tomado de la versión 0.1 de #45 (`58b5ced`); el modelo está en `docs/arquitectura/README.md` §2 y §3 de esa PR.

| Requisito | Elemento del modelo (A7) | Nivel de prueba | Caso de prueba planificado |
|---|---|---|---|
| RF-01 | C4 nivel 2: Streamlit → Spring Boot → FastAPI | Unitaria e integración | `test_backend_client.py`, `test_sapi61_http_stub.py` |
| RF-02 | C4 nivel 2: ml-api | Unitaria y contrato | `test_ml_api.py`, `test_openapi_contracts.py` |
| RF-03 | Modelo de datos PostGIS (V001–V004) | Integración | Pruebas Flyway y SQL |
| RF-04 | C4 nivel 3: vista Streamlit | Unitaria y E2E | `test_ranking_backend_view.py`; E2E de SAPI-66 (en el S2 solo local, PR #41; DT-01) |
| RF-05 | Flujo de insumos | Unitaria | Pruebas de SAPI-71 (139 sintéticas, según #45) |
| RF-06 | Script `evaluacion_modelo_d.py` | Unitaria y científica | `test_sapi83_evaluacion_modelo_d.py`, con negativos de fuga de umbral y reproducción |
| RF-07 | — | — | HU-64.T3 (SAPI-101) |
| RF-08 | ADR D frente a A | — | HU-65.T4 (SAPI-108) |
| RF-09 | — | — | HU-93.T2 (SAPI-126) |
| RF-10 | `tools/science_trace/` (no existe en `main`) | — | HU-76.T3 (SAPI-116) |
| RF-11 | Script `explicar_modelo_d.py` (herramienta de repositorio, **sin vista en el modelo**) | Unitaria | `test_hu88_explicar_modelo_d.py`, con tope de iteraciones y hash antes y después |
| RNF-01 | Modelo de datos | Integración | Replay e IT-05 |
| RNF-02 | Contratos `contracts/openapi/` | Contrato | `test_openapi_contracts.py`; IT-09, IT-09b, IT-09c |
| RNF-03 | C4 nivel 2 | Eficiencia | CP-RNF-03 (Selenium, n declarado) |
| RNF-04 | CI | Integración | `scripts/merge_gate.py`, 6 jobs; IT-13 |
| RNF-05 | Vista y documento de una página | Unitaria y aceptación | `test_sapi86_*`; validación de comprensión (HU-91.T3, HU-79) |
| RNF-06 | Workflow `security.yml` (herramienta de repositorio, **sin vista en el modelo**) | Seguridad | `test_secret_scan.py` (8 casos, 2 negativos) |
| RNF-07 | Backend Spring Boot | Fiabilidad | `RankingDatabaseUnavailableIT`; A1, P1b, S1 |
| RNF-08 | Docker Compose | E2E | IT-13; health checks |

## 2. KPI

| KPI | Requisito | Estado |
|---|---|---|
| KPI-01 | RF-01, RF-03 | **NO APROBADA**: meta pendiente de Daniel |
| KPI-02 | RNF-01 | **NO APROBADA**: meta pendiente de Daniel |
| KPI-03 | RNF-03 | **NO APROBADA**: meta pendiente de Daniel; bloquea HU-90 CA4 (D-52) |
| KPI-04 | RNF-04 | **NO APROBADA**: meta pendiente de Daniel |
| KPI-05 | RF-06, RF-08 | **NO APROBADA**: meta pendiente de Daniel; puede reformularse con OE5 comparativo |
| KPI-06 | RNF-05 | **NO APROBADA**: meta pendiente de Daniel (D-51) |

Ninguna medición previa al sellado se usa como meta cumplida.

## 3. Los tres controles de A4 (rúbrica de Matías)

La rúbrica del Hito 3 (§A4) pide responder sin preparación: Must sin prueba ejecutada = 0; pruebas sin requerimiento = 0; HU «Hechas» sin criterio de aceptación o sin aprobación de un stakeholder = 0.

| Control | Meta | Valor al 23-11-2026 | Cómo se contó |
|---|---|---|---|
| Must sin prueba ejecutada | 0 | **4 de 17 Must**: RF-07 y RF-08 (bloqueados por SAPI-165), RNF-03 (meta KPI-03 pendiente) y RNF-07 (sin commit). RNF-08 tiene pruebas unitarias ejecutadas, pero su prueba de aceptación en Docker no (D-52) | 17 Must del catálogo de #45: RF-01..08, RF-11 y RNF-01..08. Se cuenta como ejecutada una prueba con CI verde en `main` o en el head de la PR |
| Pruebas sin requisito | 0 | **0** en las 7 suites que traen o modifican las PR #46–#52 | Cada suite de la tabla 0.2 cae en una fila de la tabla 1. Las 137 entradas de `tests/` en `main` heredadas del S1 y el S2 **no se recruzaron**; su trazabilidad histórica está en `docs/hito2/TRAZABILIDAD_HU_CA_EVIDENCIAS.md` |
| HU «Hechas» sin CA o sin aprobación de un stakeholder | 0 | **0 HU cumplen hoy la DoD de «Hecha»**; las 8 PR están abiertas y todos los dictámenes marcan la `.V` como pendiente | Estado de Jira **no consultado** en esta orden. Si Jira muestra alguna HU del S3 en Finalizado, ese caso es un incumplimiento de este control y hay que corregirlo |

Controles adicionales (de la versión 0.1 de #45, al 22-11-2026):

| Control | Valor | Comentario |
|---|---|---|
| Must sin elemento del modelo | 2: RF-11 y RNF-06 | Los demás Must aparecen en un contenedor o componente de `docs/arquitectura/README.md` (§2 y §3). RF-11 (script de explicación) y RNF-06 (workflow de seguridad) son herramientas de repositorio, no componentes desplegados: falta agregarlos como vista de desarrollo |
| HU sin sprint | 0, según #45 | #45 afirma que todas están en el sprint 37 de Jira. En la Orden 09 Jira **no se consultó**: el dato no se re-verificó |
| Riesgos sin requisito u objetivo afectado | 0 | Ver `docs/riesgos.md` (columna «Amenaza a») |

## 4. Cómo verificar una fila

```bash
gh pr view 47 --json headRefOid,files,statusCheckRollup
git show cc711e7:tests/test_sapi83_evaluacion_modelo_d.py | grep -c 'def test_'
sha256sum C:/Users/danie/.orca/bots/sapi-auditor/reports/orden08-*.md
# PR que citan la HU (GitHub): is:pr SAPI-83
grep -rn "SAPI-83\|RF-06" tests/ docs/      # pruebas y documentos que la citan
git branch -r | grep -v "SAPI-"             # ramas sin ID de ticket (ver docs/hito3/gate-prs-ramas.md)
```

## 5. Limitaciones

- Si las PR cambian de head, los SHA de la tabla 0.2 quedan obsoletos. Hay que volver a obtenerlos con `gh`.
- Este archivo ya fusiona la versión 0.1 de #45 (22-11-2026) con la matriz de la Orden 09 (sección 6). No hay otra versión vigente.
- Las filas del Sprint 2 se apoyan en el gate de `main` y en `docs/trazabilidad.md` de #45. En esta orden no se ejecutaron sus pruebas.
- Los dictámenes son de SAPI-Auditor (revisión de IA). No sustituyen la revisión de Daniel ni la aceptación del stakeholder.

## 6. Consolidación

Fusión hecha el 23-11-2026 por decisión del Director (Orden 09). Se compararon las dos versiones por contenido y por evidencia, no por ruta. Jira no se consultó ni se modificó.

### 6.1. Origen

| Versión | Commit (SHA completo) | Rama | Fecha del commit |
|---|---|---|---|
| A: versión 0.1 de la PR #45 (base de este commit) | `58b5ced0692ec1852240a281488778ad8c4b33f7` | `feat/SAPI-92-plan-metas-dod` (head confirmado con `git ls-remote origin` y `gh pr view 45` el 23-11-2026) | 22-11-2026 22:09 -0300 |
| B: matriz de la Orden 09 | `3d70ae13cae2b6fffaaae3551309e6370ff5f3ad` | `docs/SAPI-92-matriz-trazabilidad-o09` | 23-11-2026 00:55 -0300 |

Base común de ambas: `main` `9e70867bc303e954f03f06964ba505bf839a7957`. La estructura de este archivo es la de B, que es posterior y cita SHA, runs de CI y dictámenes con SHA-256. De A se conservan el paso del objetivo al modelo (tabla 1.1), la regla de «Aprobado» de la DoD, los controles adicionales de la sección 3 y los comandos de la sección 4.

### 6.2. Discrepancias y cómo se resolvieron

| # | Tema | A (#45, 22-11) | B (O09, 23-11) | Resolución |
|---|---|---|---|---|
| 1 | Etiqueta de las filas del S2 | «Aprobado (S2)» | «Aprobado (S2)» | Cambiada a «Integrado (S2)» en las dos. La DoD de #45 exige `.V` y tag para «Aprobado» y no existe el tag `hito3`. No se declara aprobado ningún Must |
| 2 | Must sin prueba ejecutada | RF-07, RNF-03, RNF-07, RNF-08 | RF-07, RF-08, RNF-03, RNF-07 | Se conserva B. RF-08 no tiene prueba del S3 (A lo omitía). RNF-08 tiene `test_compose_v2.py` con CI verde en #52 `a87264b`, que A no conocía; su aceptación en Docker sigue NO EJECUTADO (D-52) |
| 3 | RF-08 | «No hecho»; la parte D frente a A existe desde el H2 | BLOQUEADO (SAPI-165) | BLOQUEADO, por orden del Director y porque `docs/requerimientos.md` de #45 declara bloqueada la parte temporal. Se anota en la fila que la comparación D frente a A del H2 existe, pero no es evidencia del S3 |
| 4 | RNF-08 | «No hecho»: falta README y corrida en Linux | Parcial: #52 agrega `README.md`, `docker-compose.yml` y 29 pruebas | Se conserva B (evidencia posterior y verificable en `a87264b`). La corrida en Linux y en Docker sigue sin hacerse: NO EJECUTADO |
| 5 | RNF-02, el 504 por timeout | No documentado (D-04, HU-91.T4) | Documentado en #51 `960bbe9` (D-51) | Se conserva B. Queda Parcial hasta integrar #51 |
| 6 | Cantidad de pruebas de HU-83 | 57 casos | 51 funciones `test_` | Sin resolver: B cuenta funciones con `grep` sin expandir la parametrización (verificado: 51 funciones y 1 `parametrize` en `cc711e7`). Los 57 casos de A no se re-verificaron con `pytest --collect-only` en esta orden. Se anotan los dos |
| 7 | Cantidad de pruebas de HU-88 | 13 casos | 12 funciones | Mismo caso que el 6: 12 funciones y 1 `parametrize` en `a693a27`. Compatible con 13 casos, pero no se ejecutó la recolección |
| 8 | HU de RNF-03 | HU-90 | HU-90.T2 (SAPI-137) | Se conserva B, que coincide con `docs/requerimientos.md` de #45 |
| 9 | Evidencia de RNF-07 | Corridas en `C:\SAPI-S3-D05-HARDEN-20261103` | `RankingDatabaseUnavailableIT` no existe en `main` | Se conservan los dos datos. Las corridas locales no son evidencia verificable del repositorio. Verificado el 23-11-2026: la clase no aparece en `main` ni en los heads de #46–#52; solo se cita como texto en `docs/pruebas/matriz-fallas.md` de #51 |
| 10 | HU sin sprint | 0 (sprint 37 de Jira) | No tratado | Se conserva el dato de A atribuido a #45, sin re-verificar (Jira no consultado) |
| 11 | Must sin elemento del modelo | RF-11 y RNF-06 | No tratado | Se conserva A |

### 6.3. Estado de cada requisito

Valores permitidos: SIN EVIDENCIA, NO EJECUTADO, PASS, FAIL, BLOQUEADO. Regla usada: **PASS** solo si todas las pruebas planificadas para el requisito tienen una ejecución verde citada (CI de `main` o del head de la PR). Si alguna prueba o criterio de aceptación planificado no se ejecutó, el estado es **NO EJECUTADO**. **PASS no es «Aprobado»**: ninguno de los 17 Must tiene la `.V` del Sprint 3 ni está en el tag `hito3`, así que ninguno está aprobado. Ninguna prueba citada aparece en FAIL en el SHA head; las roturas de D-48 son casos negativos provocados a propósito.

| Requisito | Prioridad | Estado | Base del estado | Por qué no está aprobado |
|---|---|---|---|---|
| RF-01 | Must | PASS | Gate 6/6 en `main` (run 41932911572); CI de #48 `f8c5218` | Merge de #48; `.V`; tag; KPI-01 NO APROBADA |
| RF-02 | Must | PASS | Gate 6/6 en `main` (run 41932911572) | `.V` del S3; tag |
| RF-03 | Must | PASS | Jobs Flyway y SQL del gate de `main` | `.V` del S3; tag; KPI-01 NO APROBADA |
| RF-04 | Must | NO EJECUTADO | Unitarias verdes en #48; HU-80 CA3 y CA4 y el E2E sobre SHA commiteado sin ejecutar | Faltan CA3, CA4, E2E, merge y `.V` |
| RF-05 | Must | PASS | Gate de `main` (pruebas de SAPI-71, no re-verificadas aquí) | `.V` del S3; tag |
| RF-06 | Must | PASS | CI verde en #47 `cc711e7` | CA6 pendiente; merge; `.V`; KPI-05 NO APROBADA |
| RF-07 | Must | BLOQUEADO | Sin implementación; gate de César (SAPI-165) | Bloqueado |
| RF-08 | Must | BLOQUEADO | Depende de RF-07 (SAPI-165) | Bloqueado |
| RF-09 | Could | BLOQUEADO | HU-93, SAPI-165 | Bloqueado |
| RF-10 | Should | SIN EVIDENCIA | No existe `tools/science_trace/` en `main` | Sin implementación |
| RF-10, HU-76 CA5 | Should | BLOQUEADO | Archivo E2 no localizado (#45) | Bloqueado |
| RF-11 | Must | NO EJECUTADO | Unitarias verdes en #46 `a693a27`; CA3 (en vivo), CA4 (La Cruz) y CA5 (defensa) sin ejecutar | Faltan CA3–CA5, merge y `.V` |
| RNF-01 | Must | PASS | Replay e IT-05 del H2 (Informe H2, Tabla 53); histórico, no ligado a un run de CI citado aquí | `.V` del S3; tag; KPI-02 NO APROBADA |
| RNF-02 | Must | PASS | `test_openapi_contracts.py` en el gate de `main` | Merge de #51; `.V`; tag |
| RNF-03 | Must | NO EJECUTADO | Arnés en #48 (`scripts/measure_browser_e2e_d21.py`); sin corrida con n declarado. Frente a la meta: NO EVALUADO | Corrida pendiente; KPI-03 NO APROBADA |
| RNF-04 | Must | NO EJECUTADO | Gate 6/6 en `main` `9e70867`, pero aún no existe el SHA de entrega (tag `hito3`); IT-13 solo en Windows local | Tag; T1/T4/T6/T7; M-1 de D-50; KPI-04 NO APROBADA |
| RNF-05 | Must | NO EJECUTADO | `test_sapi86_*` verdes en #48; validación de comprensión con La Cruz sin ejecutar | KPI-06 NO APROBADA; merges; `.V` |
| RNF-06 | Must | NO EJECUTADO | CI y Seguridad verdes en #49 `cf5f4cc`; Trivy de imágenes (DT-02) sin ejecutar | M-1 de D-49; Trivy; job obligatorio; `.V` |
| RNF-07 | Must | SIN EVIDENCIA | `RankingDatabaseUnavailableIT` no existe | Implementación incompleta |
| RNF-08 | Must | NO EJECUTADO | `test_compose_v2.py` verde en #52 `a87264b`; preflight en Docker NO_EVALUADO | M-1 de D-52; corrida en Docker; ADR-011; `.V` |

Resumen de los 17 Must: 7 PASS (RF-01, RF-02, RF-03, RF-05, RF-06, RNF-01, RNF-02; ninguno aprobado), 7 NO EJECUTADO (RF-04, RF-11, RNF-03, RNF-04, RNF-05, RNF-06, RNF-08), 2 BLOQUEADO (RF-07, RF-08) y 1 SIN EVIDENCIA (RNF-07). Ninguno está aprobado: los 13 Must que no están entre los 4 sin prueba tampoco. Las KPI-01..06 siguen **NO APROBADAS**.

### 6.4. Clasificación de los 4 Must sin prueba ejecutada

Clases: A enlazar, B ejecutar, C falta la prueba, D implementación incompleta, E bloqueo externo.

| Requisito | HU | Clase | Acción | Responsable | Evidencia esperada | Dependencia |
|---|---|---|---|---|---|---|
| RF-07 | HU-64 (SAPI-64); prueba planificada HU-64.T3 (SAPI-101) | E: gate de César (SAPI-165) | Ninguna hasta la respuesta escrita | Gobernanza (consulta en `docs/sprint3/gobernanza/05_consultas/cesar_SAPI-165_red_temporal_directiva2.md`, rama local `docs/s3-gobernanza` `8e2a6a2`) | Respuesta escrita de César | SAPI-165 |
| RF-08 | HU-65 (SAPI-65); prueba planificada HU-65.T4 (SAPI-108) | E: depende de RF-07 | Ninguna | — | — | RF-07 |
| RNF-03 | HU-90.T2 (SAPI-137) | B + E parcial: el arnés existe en #48 (`scripts/measure_browser_e2e_d21.py`, verificado en `f8c5218`) y falta la corrida con n declarado; sin meta de KPI-03, el resultado frente a la meta queda NO EVALUADO | Ejecutar la medición p95 por escenario | SAPI-UX | Log, JSON, SHA y entorno | Meta de KPI-03 (Daniel), solo para dar PASS/FAIL |
| RNF-07 | HU-75 (SAPI-75) | D: `RankingDatabaseUnavailableIT` no existe en `main` | Implementar el fallo rápido con la base caída y su IT, con caso negativo de saturación del pool | SAPI-Plataforma | Log de la IT, SHA y CI | Ninguna |

Las claves Jira de las HU y subtareas salen del borrador de gobernanza y de B; no se verificaron contra Jira en esta orden.

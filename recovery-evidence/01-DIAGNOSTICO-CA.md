# 01 — Diagnóstico de criterios de aceptación: SAPI-66 y SAPI-43

**Fecha de trabajo:** 2026-10-24  
**Workspace:** `C:\SAPI-S2-RECOVERY-CODE-20261024`  
**HEAD:** `51ec3c06b67959d3daad6349c962a1be643906b4`  
**Tree:** `68da56fcf0e0dc3bbe9048a9faac4cfceec49ef0`  
**Fuente normativa de los CA:** `docs/hito2/requerimientos-sprint2.md`, líneas 232–264 (texto literal de Jira).  
**Fuente del veredicto Gate B:** `C:\SAPI-S2-CIERRE-20261023\OPENCODE-CIERRE-FINAL\01-MATRIZ-GATE-B-V5.md` (NO GO: 3 PASS, 2 CONDICIONADO, 3 PARCIAL, 4 NO EJECUTADO).

## 1. Reglas de lectura

Este documento es un **diagnóstico de evidencia**, no una certificación de cierre.

- **ACREDITADO**: existe evidencia verificable en este HEAD o en el mismo SHA; no implica que se haya ejecutado un E2E nuevo.
- **ACREDITADO (W3/W4)**: la evidencia proviene de las corridas W3/W4 sobre `51ec3c06`, documentadas fuera de este workspace; se citan, no se re-ejecutan aquí.
- **PARCIAL**: una parte del criterio está probada y falta un tramo material.
- **NO ACREDITADO**: falta el artefacto o la ejecución que el criterio exige.
- **CONDICIONADO**: depende de una autorización, credencial, dato o infraestructura que no está disponible en esta sesión.

No se usa “PASS” como sinónimo de cierre de un CA. Los estados de Gate B se conservan con su vocabulario propio y **no se promueve ningún control**.

> **Nota de nomenclatura:** `docs/hito2/TRAZABILIDAD_HU_CA_EVIDENCIAS.md` usa una numeración más antigua para SAPI-66 (CA1 “orquestación”, CA4 “rendimiento”). Este diagnóstico usa el texto literal de `requerimientos-sprint2.md`, que es la fuente de los CA de Jira. La diferencia se registra para evitar dobles conteos.

## 2. Resumen ejecutivo

| HU | CA | Criterio (resumen literal) | Evidencia disponible | Estado de evidencia | Brecha principal |
|---|---|---|---|---|---|
| SAPI-66 | CA1 | Test E2E reproducible que recorre la cadena completa | W3 tiene E2E manual/scriptado fuera del repo; `tests/e2e/test_vertical_slice.py` y `scripts/e2e_slice.py` **no existen** | **NO ACREDITADO** | Falta el test reproducible planificado |
| SAPI-66 | CA2 | Errores y contratos verificados en cada salto | `test_openapi_contracts.py` 14 PASS; `test_ml_api.py` 23 PASS; `RankingResultValidatorTests` 60 PASS; W3 happy path | **PARCIAL** | No hay reporte E2E de errores por salto |
| SAPI-66 | CA3 | Resultado persiste en PostgreSQL y es consultable | W4 oráculos O1/O3; 50 filas; psql; Java 13 PASS; migraciones estáticas 12 PASS | **ACREDITADO (W4)** | No re-ejecutado aquí; no sustituye CA1 |
| SAPI-66 | CA4 | Tiempo total de respuesta documentado | `timings_browser.csv` de closeout, d26 y W3; latencias frío/update/caché | **PARCIAL / CONDICIONADO** | Capturas cached=update; falta desglose por salto y recaptura discriminante |
| SAPI-66 | CA5 | Ejecutable con `docker-compose up` sin configuración adicional | Ruta de secreto y tests estáticos 34 PASS; W3 usó profile + overrides; validador con 3 sustituciones | **NO ACREDITADO (NO LITERAL)** | `web-v2` no está en la ruta por defecto; falta ejecución literal |
| SAPI-43 | CA1 | Stores FIRMS/DMC versionados producidos por refresh de SAPI-71; `firms_origin=current` | W3/W4: CURRENT, fingerprint reconstruido, `firms_origin=current` | **CONDICIONADO / PARCIAL** | SAPI-71 Attempt 2 está `NOT STARTED`; no se prueba la procedencia exigida |
| SAPI-43 | CA2 | Score con Modelo D vía servicio ML SAPI-55 | W3 E2E-2 Spring→FastAPI→PostGIS; `test_ml_api.py` 23 PASS; contratos 14 PASS | **ACREDITADO (W3)** | Sin re-ejecución local |
| SAPI-43 | CA3 | 50 filas, `model_version` y fingerprint persistidos | W4 O1/O3; Java 13 PASS; migraciones estáticas 12 PASS | **ACREDITADO (W4)** | Sin re-ejecución local |
| SAPI-43 | CA4 | psql devuelve 50 filas ordenadas por ranking | W4 O2: `rank 1..50`; oráculos run1/run2/run3 | **ACREDITADO (W4)** | Sin re-ejecución local |
| SAPI-43 | CA5 | Evidencia de no usar `demo_seed` ni `run_daily_pipeline` legacy | `test_architecture.py` 8 PASS; W3/W4 sin evidencia de pipeline legacy | **ACREDITADO (ESTÁTICO)** | Falta log runtime dedicado que lo enumere |
| SAPI-43 | CA6 | Repetir con los mismos insumos es idempotente | W4 O4: 1 ejecución, 50 filas, `dup_cell_id=0`, `dup_K=0`; run1/run2 byte-identical | **ACREDITADO (W4)** | Sin re-ejecución local |
| SAPI-43 | CA7 | `scientific_model_validation=false`; score relativo | W3/W4 metadata; `test_db_migrations_v2.py` 12 PASS; `test_ml_api.py` 23 PASS | **ACREDITADO** | Sin cambio |
| SAPI-43 | CA8 | Nunca persistir `firms_origin` ausente o distinto de `current`; overlay fija `current` | Java 85 PASS (política y binding); overlay estático PASS; W3/W4 current | **PARCIAL / CONDICIONADO** | `RankingHttpToPostgresIT` real no re-ejecutado; GB-11 sigue CONDICIONADO |

**Lectura correcta del resumen:** hay evidencia técnica favorable y reutilizable, pero **no hay cierre literal de SAPI-66** y **no hay corrida operacional nueva de SAPI-43**. El veredicto Gate B no cambia.

## 3. SAPI-66 — Prueba E2E del vertical slice

### 3.1 CA1 — Test E2E reproducible

**Texto literal:** “Test E2E reproducible que recorre la cadena completa”.  
**Verificación planificada:** `tests/e2e/test_vertical_slice.py`.  
**Evidencia planificada:** `artifacts/hito2/e2e/<ts>/`.

**Comprobación realizada:**

```powershell
Test-Path tests\e2e\test_vertical_slice.py   # False
Test-Path scripts\e2e_slice.py               # False
```

Ambos artefactos planificados están ausentes. W3 sí ejecutó un E2E real (health, ranking y navegador Edge) y dejó evidencia en `C:\SAPI-OCC-S2-A2-INTEG-20261022\EV-W3\e2e\` y `e2e-http\`, pero:

- no es el test reproducible versionado que pide el CA;
- no está en `tests/e2e/`;
- no produce el directorio `artifacts/hito2/e2e/<ts>/` del plan;
- se ejecutó con overrides y una lista explícita de servicios, no con el flujo literal del CA5.

**Conclusión:** **NO ACREDITADO**. La cadena funciona en evidencia histórica, pero el criterio pide un test reproducible y ese artefacto no existe en este HEAD.

### 3.2 CA2 — Errores y contratos en cada salto

**Texto literal:** “Errores y contratos verificados en cada salto”.  
**Verificación planificada:** validación contra los YAML en cada salto; reporte E2E.

**Evidencia disponible:**

- `tests/test_openapi_contracts.py`: **14 passed**. Valida los contratos OpenAPI versionados.
- `tests/test_ml_api.py`: **23 passed**. Cubre contrato, errores 422/500/503 y ausencia de campos prohibidos.
- `RankingResultValidatorTests`: **60 tests, 0 fallos**. Cubre rechazo de resultados inválidos en el backend.
- W3 `e2e-http\30-health.txt`: ml, backend y web responden 200; `32-ranking-summary.txt`: 50 celdas, `firms_origin=current`, `relative_rank`, `scientific_model_validation=False`.
- W3 no contiene un reporte E2E que induzca y documente errores en **cada salto** de la cadena.

**Conclusión:** **PARCIAL**. Los contratos y errores están cubiertos por pruebas unitarias/estáticas y por el happy path E2E; falta el reporte E2E de errores por salto que el criterio pide.

### 3.3 CA3 — Persistencia y consulta en PostgreSQL/PostGIS

**Texto literal:** “Resultado persiste en PostgreSQL y es consultable”.  
**Verificación planificada:** filas en la base == respuesta; reporte E2E.

**Evidencia disponible (W4, mismo SHA `51ec3c06`):**

- `EV-W4\oracles-run1.txt`, `oracles-run2.txt`, `oracles-run3-after-restart.txt`:
  - `O1_50_filas|t|50`
  - `O2_rank_1_50|t|1..50`
  - `O3_current_y_metadatos|t|current|prototype_model_d_v1`
- `EV-W4\ranking-run2.json` (5.611 bytes) y `B11b-o4-compare.txt` (`O4 byte-identical: True`).
- `RankingPersistenceServiceTests`: **13 tests, 0 fallos** (persistencia de 50 filas, idempotencia y gate current-only).
- `tests/test_db_migrations_v2.py`: **12 passed** (V001–V004, constraints, PostGIS, seed de 50 celdas).

**Conclusión:** **ACREDITADO (W4)**. La persistencia y la consulta están probadas sobre base real en el mismo SHA; no se re-ejecutó aquí y no sustituye el test E2E de CA1.

### 3.4 CA4 — Tiempo total de respuesta documentado

**Texto literal:** “Tiempo total de respuesta documentado”.  
**Verificación planificada:** tiempos por salto (frío y caliente); `timings.csv`.

**Evidencia disponible:**

- `artifacts/hito2/closeout_e2e/timings_browser.csv` (commit `8982e58`): RUN-01 897,39 ms; RUN-02 1.952,52 ms; RUN-03 563,88 ms; RUN-04 582,61 ms.
- `artifacts/hito2/d26/timings_browser.csv` (commit `bb5efe2`): 3.691,87 / 1.526,44 / 604,65 / 563,68 ms.
- W3 `EV-W3\e2e\timings_browser.csv` (commit `51ec3c06`): 7.644,9 / 3.640,53 / 1.033,04 / 702,06 ms.
- W3 `e2e-http\30-health.txt` incluye tiempos por servicio: ml 0,005580 s; backend 0,007498 s; web 0,015073 s.

**Problema material:** las capturas de RUN-02 (update) y RUN-03 (cached) son byte-idénticas en closeout, d26 y W3. El detalle está en la sección 5. Esto no invalida los tiempos del CSV, pero **sí invalida usar las dos capturas como dos pruebas visuales independientes**.

**Conclusión:** **PARCIAL / CONDICIONADO**. Hay tiempos totales documentados y latencias por escenario; falta un `timings.csv` consolidado por salto (frío/caliente) y una recaptura que discrimine update de cached. Gate B GB-07 sigue CONDICIONADO y no admite cached/update como dos pruebas.

### 3.5 CA5 — `docker-compose up` sin configuración adicional

**Texto literal:** “Prueba ejecutable con `docker-compose up` sin configuración adicional”.  
**Verificación planificada:** `scripts/e2e_slice.py` sobre el compose por defecto; reporte E2E.

**Hechos verificados:**

- `docker-compose.yml` define `web-v2` con `profiles: ["presentation"]` (línea 161). La ruta por defecto solo levanta `db-v2`, `ml-api` y `backend`.
- `scripts/e2e_slice.py` no existe (ver CA1).
- W3 ejecutó CA5 **18/18** con una lista explícita de servicios, `COMPOSE_PROFILES=presentation` y overrides de subnet/montaje de datos autorizados condicionalmente por el PO.
- El validador usado en W3 (`validate_ca5.W3.diff`, SHA-256 `EFA6764DB82A51267FE3E401CE910F16080E6A8273E7E4E5CE10690A3D559814`) tiene exactamente **3 líneas sustituidas** (`15c15`, `73c73`, `78c78` en un diff no unificado): ruta del repo, puertos backend/ML y URL del ranking. No es el validador literal ni el compose por defecto.
- `tests/test_compose_v2.py`: **34 passed**. Cubre la ruta por defecto, el profile `presentation`, el volumen `sapi_v2_secrets`, el entrypoint fail-closed y los checks de contraseña. Es evidencia estática favorable, no una ejecución literal.
- Existe una **aceptación alternativa** del PO: `bootstrap_compose_v2.py` (Jira `#10156`), registrada en `docs/hito2/TRAZABILIDAD_HU_CA_EVIDENCIAS.md:32`. Esa aceptación no convierte el CA5 literal en PASS.

**Conclusión:** **NO ACREDITADO (NO LITERAL)**. La ruta de secreto y el fail-closed están implementados y testeados; la ejecución literal “sin configuración adicional” no está acreditada. Gate B GB-06 sigue **PARCIAL (no literal)** y EX-06 pendiente.

## 4. SAPI-43 — Ejecución del pipeline diario con datos reales

### 4.1 CA1 — Stores versionados producidos por SAPI-71; `firms_origin=current`

**Texto literal:** “Usa los stores FIRMS y DMC versionados (`CURRENT.json`) producidos por el refresh de SAPI-71”.  
**Verificación planificada:** `firms_origin=current` en la respuesta.

**Evidencia favorable:**

- W3 `41-inputs-manifest.json`: fingerprint reconstruido = respuesta (`551a54b3…`); FIRMS `fe22229a…` current; DMC versionado; `repro=false`.
- W3 `32-ranking-summary.txt`: `firms_origin = current`.
- W4 mantiene el mismo fingerprint y `CURRENT origin PASS`.

**Brecha:** `docs/ops/FIRST-CONTROLLED-REFRESH.md:5` declara **“Attempt 2 is NOT STARTED”**. Por tanto, no se puede demostrar que los stores CURRENT usados hayan sido producidos por el refresh de SAPI-71 Attempt 2 que el CA exige. Se probó el uso de CURRENT y la procedencia `current`, no la producción por SAPI-71.

**Conclusión:** **CONDICIONADO / PARCIAL**. La dependencia humana de SAPI-71 Attempt 2 sigue abierta. Gate B GB-11 sigue CONDICIONADO.

### 4.2 CA2 — Score con Modelo D vía servicio ML

**Texto literal:** “El score se calcula con el Modelo D a través del servicio ML de SAPI-55”.  
**Verificación planificada:** log del backend y del ML.

**Evidencia favorable:**

- W3 `e2e-http\30-health.txt`: ml, backend y web 200.
- W3 `e2e-http\32-ranking-summary.txt`: `model_version = prototype_model_d_v1`; 50 celdas; `relative_rank`; `scientific_model_validation = False`.
- W3 `40-ml-api.log` y `61-browser.log` documentan la corrida.
- `tests/test_ml_api.py`: **23 passed**; `tests/test_openapi_contracts.py`: **14 passed**; `RankingResultValidatorTests`: **60 passed**.

**Conclusión:** **ACREDITADO (W3)**. La cadena Spring→FastAPI→Modelo D está evidenciada en el mismo SHA; no se re-ejecutó localmente.

### 4.3 CA3 — 50 filas, `model_version` y fingerprint

**Texto literal:** “La corrida se persiste en las tablas de SAPI-58/59: 50 filas, `model_version` y fingerprint de entradas”.  
**Verificación planificada:** psql.

**Evidencia favorable:**

- W4 `oracles-run1.txt` / `oracles-run2.txt` / `oracles-run3-after-restart.txt`:
  - 50 filas;
  - `current`;
  - `model_version=prototype_model_d_v1`;
  - `fp=551a54b328e42f10df0d9fca4e8c1304d0162301b20bb659a0878b732d9a212c`.
- `RankingPersistenceServiceTests`: **13 passed**.
- `tests/test_db_migrations_v2.py`: **12 passed** (V002/V003/V004 y constraints).

**Conclusión:** **ACREDITADO (W4)**. Evidencia real sobre base PostGIS en el mismo SHA; no re-ejecutada aquí.

### 4.4 CA4 — psql devuelve 50 filas ordenadas

**Texto literal:** “Consulta en psql devuelve las 50 filas ordenadas por ranking”.  
**Verificación planificada:** psql.

**Evidencia favorable:** W4 `oracles-run1.txt` O2: `rank 1..50`; `oracles-run2.txt` idéntico; `oracles-run3-after-restart.txt` idéntico. La consulta se ejecutó dentro del contenedor y el SQL tiene hash de manifiesto (`00-sql-in-container.sha256`, `01380933…`).

**Conclusión:** **ACREDITADO (W4)**. No re-ejecutado aquí.

### 4.5 CA5 — Sin `demo_seed` ni `run_daily_pipeline` legacy

**Texto literal:** “Evidencia de que no se usó `demo_seed` ni `run_daily_pipeline` legacy”.  
**Verificación planificada:** logs y test de arquitectura.

**Evidencia favorable:**

- `tests/test_architecture.py`: **8 passed**. Incluye `test_temporal_pipeline_has_no_transitive_legacy_dependency`, `test_sapi61_flow_has_no_transitive_local_scoring`, `test_frontend_data_contract_compliance`.
- W3/W4 documentan una corrida con stores versionados y backend Spring; no aparece `demo_seed` ni el pipeline legacy en los artefactos revisados.

**Reserva:** no hay un log runtime dedicado que enumere explícitamente “no se ejecutó `demo_seed`”. La evidencia es estática y de ausencia; es razonable para el criterio, pero se declara como tal.

**Conclusión:** **ACREDITADO (ESTÁTICO)** con reserva de log runtime.

### 4.6 CA6 — Idempotencia con los mismos insumos

**Texto literal:** “Repetir la corrida con los mismos insumos es idempotente (no duplica)”.  
**Verificación planificada:** segunda corrida: 0 ejecuciones nuevas.

**Evidencia favorable:**

- W4 `oracles-run1.txt` y `oracles-run2.txt` idénticos: `id=1`, `ejecuciones_con_K=1`, `ejecuciones_total=1`, `filas=50`, `dup_cell_id=0`, `dup_K=0`.
- W4 `B11b-o4-compare.txt`: `O4 byte-identical: True`; `GET K equal: ft=True mv=True fp=True cells=50 origin=current`.
- W4 `C5-restart.txt`: tras `down` sin `-v` y `up`, run3 == run2 (`id=1`).
- `RankingPersistenceServiceTests`: 13 passed, incluye idempotencia.

**Conclusión:** **ACREDITADO (W4)**. No re-ejecutado aquí.

### 4.7 CA7 — `scientific_model_validation=false` y score relativo

**Texto literal:** “Se mantiene `scientific_model_validation=false` (score = ranking relativo, no probabilidad calibrada)”.  
**Verificación planificada:** CHECK en V002 y contrato.

**Evidencia favorable:**

- W3 `32-ranking-summary.txt`: `score_semantics = relative_rank`; `scientific_model_validation = False`.
- W4 O3: `current|prototype_model_d_v1`, con `validation=false`.
- `tests/test_db_migrations_v2.py`: **12 passed**, incluye `test_no_probability_wording_in_migrations` y constraints de V002.
- `tests/test_ml_api.py`: **23 passed**, incluye contrato y ausencia de campos de probabilidad.

**Conclusión:** **ACREDITADO**. No se observa regresión.

### 4.8 CA8 — `firms_origin` solo `current` y overlay operacional

**Texto literal:** “La corrida operacional nunca persiste con `firms_origin` ausente o distinto de `current`; el overlay operacional fija `sapi.persistence.allowed-firms-origins=current`”.  
**Verificación planificada:** `RankingHttpToPostgresIT` (B1) + `test_f1_operational_overlay_pins_the_persistence_policy_to_current_only` + E2E real con `docker-compose.operational.yml`.

**Evidencia favorable:**

- Java dirigido: **85 tests, 0 fallos**:
  - `FirmsOriginPolicyTests` 5;
  - `FirmsOriginPolicyBindingTests` 7;
  - `RankingPersistenceServiceTests` 13;
  - `RankingResultValidatorTests` 60.
- `tests/test_compose_v2.py`: **34 passed**, incluye `test_f1_operational_overlay_pins_the_persistence_policy_to_current_only` y `test_ca5_operational_overlay_keeps_the_database_secret_mount`.
- W3/W4: `firms_origin=current` en la respuesta y en la base.

**Brecha:** `RankingHttpToPostgresIT` requiere Testcontainers/DB real y **no se re-ejecutó** en esta sesión. La prueba negativa real (rechazo de `baseline`/`reproducibility`/ausente con política `current`) queda pendiente de ejecución. Gate B GB-11 sigue CONDICIONADO.

**Conclusión:** **PARCIAL / CONDICIONADO**. La política está cubierta por unitarias, binding y estáticos; falta el IT real que el CA nombra.

## 5. Hallazgo CA4: por qué `update` y `cached` tienen el mismo PNG

### 5.1 Hecho reproducible

| Conjunto | Commit | RUN-02 post | RUN-03 pre/post | Minuto visible | SHA-256 update | SHA-256 cached | ¿Capturas distintas? |
|---|---|---|---|---|---|---|---|
| `closeout_e2e` | `8982e58f…` | `2026-10-16 02:36:37 UTC` | `2026-10-16 02:36:37 UTC` | `02:36` | `49B4E7965AAA77BE0ED1A460E9631999CFA720AB207D0CAA8B668541C7B3AB53` | `49B4E7965AAA77BE0ED1A460E9631999CFA720AB207D0CAA8B668541C7B3AB53` | **No** |
| `d26` | `bb5efe26…` | `2026-10-15 15:53:20 UTC` | `2026-10-15 15:53:20 UTC` | `15:53` | `A7E8B5831BF5A8000A52C2F7749A9E1F21C00B1272E92BCB4357B8D61BC8FB9A` | `A7E8B5831BF5A8000A52C2F7749A9E1F21C00B1272E92BCB4357B8D61BC8FB9A` | **No** |
| W3 | `51ec3c06…` | `2026-10-22 05:49:27 UTC` | `2026-10-22 05:49:27 UTC` | `05:49` | `539A4BD57BE75C37D3068FF4B26100287DA1BFF2889C4117F7A8275C5743AC11` | `539A4BD57BE75C37D3068FF4B26100287DA1BFF2889C4117F7A8275C5743AC11` | **No** |
| `d21` / `d24` | `b3bc6820…` | CSV antiguo sin columnas de timestamp | CSV antiguo sin columnas de timestamp | n/d | `8F6E6A0FDD15B502E560041953AA2D48BB481A58677327C60904CD8B1482BEBC` | `33D432F67A8303A0B4C3D77353C9803041894FAE8A8E4F45F857FEE6F4724E46` | Sí, pero no atribuible |

En `d26`, la captura `cold` también es byte-idéntica a `update` y `cached` (`A7E8B583…`), porque las tres ocurrieron dentro del minuto `15:53`. En `closeout`, `cold` sí difiere (`0952EA80…`, 330.402 bytes) porque ocurrió en `02:33`, mientras update/cached ocurrieron en `02:36`.

### 5.2 Causa raíz

- El header visible renderiza `Obtenido del backend: {_human_hm(view.fetched_at)} UTC` en `app/components/ranking_backend_view.py:505`.
- `_human_hm` usa `strftime("%H:%M")` (`ranking_backend_view.py:137-138`): **precisión de minuto, sin segundos**.
- Los segundos sí existen en el detalle del expander: `(obtenido {_iso_utc(view.fetched_at)}; …)` (`ranking_backend_view.py:849`), pero el expander está colapsado en las capturas RUN-02/03.
- El arnés lee `document.body.textContent`, que incluye el texto del detalle aunque esté colapsado; por eso puede confirmar `05:49:18 → 05:49:27` en el DOM, aunque el píxel solo muestre `05:49`.

### 5.3 Implicación correcta

La coincidencia de PNG es una **limitación de diseño de la evidencia**, no una fabricación ni una prueba de que no hubo actualización. Pero también significa que:

- las capturas `cached` y `update` **no son dos pruebas visuales independientes**;
- el CSV y el DOM con segundos son la evidencia discriminante;
- Gate B GB-07 tiene razón al no admitir `cached=update` como dos pruebas y al mantener el control **CONDICIONADO**;
- la recaptura futura debe incluir un discriminador visible (por ejemplo, detalle con segundos o hash de contenido) y registrar el SHA-256 de cada PNG. El arnés fue endurecido en ese sentido (ver `02-CAMBIOS-Y-PRUEBAS.md`), sin alterar las imágenes históricas.

## 6. Hallazgo CA5: por qué no es literal

| Servicio | Profile | ¿Arranca con `docker compose up` por defecto? |
|---|---|---|
| `db-v2` | — | Sí |
| `ml-api` | — | Sí |
| `backend` | — | Sí |
| `web-v2` | `presentation` | **No** |
| `db-postgis` | `legacy` | No |
| `analytics-backend` | `legacy` | No |
| `web-presentation` | `legacy` | No |
| `n8n-bridge` | `ops` | No |

El CA5 pide una prueba ejecutable con `docker-compose up` “sin configuración adicional” y un `scripts/e2e_slice.py` sobre el compose por defecto. En este HEAD:

- el compose por defecto no incluye Streamlit (`web-v2` es opt-in por profile);
- `scripts/e2e_slice.py` no existe;
- W3 usó `COMPOSE_PROFILES=presentation`, lista explícita de servicios y overrides;
- el validador W3 difiere del literal en 3 sustituciones (ruta/ports), con SHA-256 `EFA6764DB82A51267FE3E401CE910F16080E6A8273E7E4E5CE10690A3D559814`.

La ruta de secreto sí está bien diseñada y testeada: `POSTGRES_PASSWORD_FILE`, volumen `sapi_v2_secrets`, backend con `SPRING_CONFIG_IMPORT=configtree:/run/sapi-secrets/`, entrypoint fail-closed y tests estáticos 34 PASS. Eso acredita el **mecanismo**, no la literalidad del CA5.

## 7. Qué no se puede afirmar

- No se puede afirmar que SAPI-66 esté cerrado: CA1 y CA5 no están acreditados; CA2 y CA4 son parciales.
- No se puede afirmar que SAPI-43 haya tenido una corrida operacional nueva: W3/W4 son evidencia histórica del mismo SHA, no una ejecución de esta sesión.
- No se puede afirmar que CA5 sea literal: el compose por defecto no levanta la UI y W3 usó overrides.
- No se puede afirmar que las capturas CA4 sean dos pruebas independientes: son byte-idénticas por precisión de minuto.
- No se puede afirmar que Gate B haya cambiado: sigue **NO GO**, con GB-06/07/11 en sus estados vigentes.

## 8. Referencias

- `docs/hito2/requerimientos-sprint2.md:232-264` — CA literales.
- `docs/hito2/TRAZABILIDAD_HU_CA_EVIDENCIAS.md:24-40` — mapeo histórico y aceptación alternativa CA5.
- `docs/ops/FIRST-CONTROLLED-REFRESH.md:5` — SAPI-71 Attempt 2 `NOT STARTED`.
- `C:\SAPI-OCC-S2-A2-INTEG-20261022\EV-W3\W3-RESULT.md` — E2E y CA5 18/18; reserva de PNG idénticos.
- `C:\SAPI-OCC-S2-A2-INTEG-20261022\EV-W4\W4-RESULT.md` — O1–O5, idempotencia y restart.
- `C:\SAPI-S2-CIERRE-20261023\OPENCODE-CIERRE-FINAL\01-MATRIZ-GATE-B-V5.md` — estados Gate B v5.
- `app/components/ranking_backend_view.py:137-138,505,849` — precisión de minuto vs segundos.
- `artifacts/hito2/closeout_e2e/timings_browser.csv`, `artifacts/hito2/d26/timings_browser.csv`, `artifacts/hito2/d21/timings_browser.csv`, `artifacts/hito2/d24/timings_browser.csv` — timings y hashes.

# Trazabilidad canónica — Sprint 1 / Hito 1

**Estado:** documento CANÓNICO de trazabilidad para el Hito 1. No
reemplaza `docs/matriz-trazabilidad-hu-test.md` (se conserva como
histórico) — lo audita, señala dónde quedó desactualizado, y lo
incorpora como fuente. Arquitectura (`docs/arquitectura-hito1.md`) y
Testing (`docs/testing-evidencia-hito1.md`) permanecen CONGELADOS y no se
reabren en esta fase. Fecha de esta fase: **07-09-2026**.

**Principio de no fabricación:** ninguna HU, CA, DoD, Sprint Goal, fecha,
story point, velocidad, estado Jira o Review se inventa. Donde no hay
evidencia verificable, este documento dice explícitamente `NO VERIFICADO`,
`NO ENCONTRADO`, `BRECHA HISTÓRICA` o `PENDIENTE`. No se confía en
recuerdos de conversaciones previas de este proyecto — solo en archivos
verificables en el repositorio en este momento.

---

## 1. Propósito y alcance

Construir la matriz de trazabilidad canónica del Sprint 1/Hito 1:
requerimiento → HU/issue → prioridad → estado → CA → prueba → resultado
→ evidencia, y (cuando sea verificable) → atributo de calidad →
riesgo/hallazgo → decisión/cambio. Satisface simultáneamente la rúbrica
de Hito 1, la de Sprint 1, la planificación Semana a Semana S1-S6 y el
syllabus INSW421 (IL 1.1–1.4), sin modificar Jira, código, tests, datos
ni la arquitectura/testing ya congelados.

## 2. Fuentes de evidencia

Auditadas en esta fase, en orden de lectura:

| Fuente | Fecha de la fuente | Rol en esta fase |
|---|---|---|
| `docs/matriz-trazabilidad-hu-test.md` | 05-09-2026 (última actualización) | Matriz histórica de HU↔test — auditada, NO modificada, señalada como parcialmente desactualizada (sección 4) |
| `docs/informe-1-seminario-licenciatura.md` | 02-09-2026 | Fuente independiente que confirma 10 tickets Jira contra un estado "confirmado contra Jira" en esa fecha |
| `docs/matriz-riesgo.md` | 05-09-2026 | Riesgos reales con decisiones de gestión — fuente para la columna riesgo/hallazgo |
| `docs/arquitectura-hito1.md` | 07-09-2026 (CONGELADA) | Componentes reales del pipeline temporal — fuente para requerimientos sin HU |
| `docs/testing-evidencia-hito1.md` + `artifacts/hito1/testing/*` | 07-09-2026 (CONGELADA) | Evidencia técnica fresca (470/470 PASS, 91.72% cobertura, AC-T01..T10, defectos) |
| `docs/acta-pruebas-aceptacion-usuario.md` | 01/05-09-2026 | Única evidencia real de una sesión de verificación con usuario (autoevaluación, alcance distinto) |
| `git log`, `git tag` | continuo desde 20-06-2026 | Fechas y mensajes reales de commits, tags de versión |
| `README.md` | — | Referencia al tablero Jira público (no accedido en vivo en esta fase) |

**No se encontró ningún export de Jira como archivo local** (buscado por
nombre, por contenido `SAPI-2[6-9]|SAPI-3[0-9]|SAPI-4[0-9]` en
`.json`/`.csv`/`.xml`, y por convención de nombre `*jira*`) — cero
resultados fuera de menciones en texto dentro de los `.md` ya listados.
**Por lo tanto, la única fuente Jira verificable son los IDs y estados
citados dentro de esos documentos `.md` del repositorio — no un
recuerdo de conversación ni un export externo.** Esto limita
explícitamente el inventario de HU de la sección 4 a los 10 tickets que
aparecen, de forma consistente, en al menos uno de esos dos documentos
independientes.

## 3. Sprint Goal / alcance verificable

Búsqueda exhaustiva de "Sprint Goal" en todo el repositorio: sin
resultados.

**HISTORICAL_SPRINT_GOAL: NOT_FOUND.**

**RECONSTRUCCIÓN RETROSPECTIVA DEL ALCANCE — 07/09/2026** (no es un
Sprint Goal histórico, es un resumen del alcance realmente cubierto,
formulado hoy a partir de la evidencia reunida):

> Sprint 1 cerró con: (a) ingesta real de NASA FIRMS (5 años, 12.477
> registros) y DMC (estación 330007), (b) un primer puente real
> ignición↔meteo↔celda sobre un evento histórico real (2024-02-03), (c)
> separación explícita demo/real en el dashboard, (d) un gate de
> cobertura de tests ≥80% alcanzado y superado, y (e), ya fuera del
> período que la matriz histórica documenta, un pipeline temporal nuevo
> completo (meteorología regional, episodios, target causal, Modelo D,
> servicio de inferencia) con su propia arquitectura congelada y su
> propia evidencia de testing — este último sin HU/Jira vinculada
> todavía (ver sección 12).

## 4. Inventario de HU/issues

### 4.1 Auditoría de `docs/matriz-trazabilidad-hu-test.md` (histórico vs. estado actual)

| Comparación | Resultado |
|---|---|
| Documento histórico vs. repo actual | La fila **SAPI-30** dice "Sin DEM ni `rasterio`; `_add_topography()` sintético" — **desactualizado**: `src/procesamiento/dem_features.py`, `dem_terrain.py` y sus tests (`test_dem_features.py`, `test_dem_terrain.py`) existen y están integrados al prototipo real (ver `docs/arquitectura-hito1.md`). |
| Documento histórico vs. testing actual | El documento cita "**Total pytest (05-09-2026):** ~325 tests" y "Corrida Docker 06-09-2026: 327 PASS, cobertura 87.18%". La ejecución fresca de esta fase (`pytest-full.txt`, 07-09-2026) da **470 passed, 0 failed**, cobertura **91.72%** — consistente con crecimiento real (nuevo pipeline temporal), no una contradicción, pero el documento histórico no refleja los ~143 tests nuevos ni los módulos nuevos (`regional_meteo`, `episodes`, `causality_validator`, `target_builder`, `temporal_features`, `experiment_abcd_contract`, `prototype_service`, `prototype_freshness`, `nan_journey_real_data`, `temporal_dataset_integration`, `grid_consistency`, `app_integration`). |
| Documento histórico vs. Jira verificable | No se accedió a Jira en vivo en esta fase (fuera de alcance). No se puede confirmar si los estados Jira reales de SAPI-26/28/30/32 siguen siendo "En curso" (según `informe-1-seminario-licenciatura.md`, 02-09-2026) o cambiaron después. |

**Discrepancia adicional detectada (no en el encargo de auditar la
matriz, pero relevante para esta fase):** los tres primeros commits del
repositorio (20-06-2026) usan una numeración **`#HU-01`..`#HU-08`,
`#TS-02`** — distinta de la numeración Jira `SAPI-*` usada desde
31-08-2026 en adelante. No existe en el repositorio un mapeo verificable
`HU-0X ↔ SAPI-XX`. Se documentan ambas numeraciones por separado en la
sección 5/6, sin asumir una correspondencia.

### 4.2 HU/issues Jira verificables (10, consistentes entre 2 documentos independientes)

| ID | Tipo | Resumen | Prioridad | Estado Jira **histórico** (`informe-1-seminario-licenciatura.md`, 02-09-2026) | Estado Jira **actual** (export `Jira (4).doc`, externo, ver §11) | Estado técnico (evidencia real) | Sprint | Story points (export `Jira (4).doc`) | Dependencia |
|---|---|---|---|---|---|---|---|---|---|
| SAPI-26 | HU | Histórico incendios NASA FIRMS | NO VERIFICADO (sin campo de prioridad en el repo) | En curso | En curso | Cerrado (lado NASA); CONAF sin fuente real | Sprint 1 | 8 SP — En curso (no finalizado) | R-CONAF-01 |
| SAPI-28 | HU | Telemetría DMC ↔ igniciones | NO VERIFICADO | En curso | **Finalizado (resuelta 07-09-2026)** | Parcial (join real feb-2025, 164/164 matched) | Sprint 1 | 8 SP — Finalizado | R-DMC-01 |
| SAPI-30 | HU | Topografía DEM por celda | NO VERIFICADO | En curso | **Finalizado (resuelta 07-09-2026)** | Avanzado — DEM real implementado y probado (`dem_features.py`/`dem_terrain.py`), más allá de lo que la matriz histórica registra | Sprint 1 | 5 SP — Finalizado | — |
| SAPI-32 | HU | Limpieza/normalización + integración | NO VERIFICADO | En curso | Por hacer | Parcial (sub-tarea limpieza cerrada; integración a producción pendiente, R-INTEGRACION-01) | Sprint 1 | 5 SP — Por hacer (no finalizado) | R-INTEGRACION-01 |
| SAPI-33 | Tarea de gestión | Gestión/documentación (sin evidencia de código asociada) | NO VERIFICADO | Finalizado | Finalizado | Manual (no verificable vía test/código) | Sprint 1 | NO ENCONTRADO (sin SP propio en el export) | — |
| SAPI-44 | HU | Separación demo vs. real (`SAPI_DATA_MODE`) | NO VERIFICADO | Finalizado | Finalizado | Cerrado (13/13 tests históricos; badge verificado en código) | Sprint 1 | 2 SP — Finalizado | — |
| SAPI-45 | Tarea técnica | Imports/tests estables, gate de cobertura ≥80% | NO VERIFICADO | Finalizado | Finalizado | Cerrado (80.34% histórico → 91.72% en esta fase) | Sprint 1 | 3 SP — Finalizado | — |
| SAPI-46 | Tarea de gestión | Gestión/documentación (sin evidencia de código asociada) | NO VERIFICADO | Finalizado | Finalizado | Manual (no verificable vía test/código) | Sprint 1 | NO ENCONTRADO (sin SP propio en el export) | — |
| SAPI-47 | Tarea de documentación | Matriz de riesgo | NO VERIFICADO | Finalizado | Finalizado | Cerrado (`docs/matriz-riesgo.md` real, 7 riesgos) | Sprint 1 | 1 SP — Finalizado | — |
| SAPI-48 | Tarea de documentación | Matriz de trazabilidad HU↔prueba | NO VERIFICADO | Finalizado | Finalizado | Cerrado (`docs/matriz-trazabilidad-hu-test.md`, ver auditoría 4.1) | Sprint 1 | 2 SP — Finalizado | — |

**Fechas académicas relevantes.** Fuente: export Jira `Jira (4).doc`,
externo al repositorio de código y correspondiente al estado disponible
del tablero al 07-09-2026, junto con el calendario académico del curso.
La fecha planificada de cierre de Sprint 1 fue **31-08-2026**. SAPI-28 y
SAPI-30 figuran **resueltas el 07-09-2026**, es decir, después de la
fecha planificada de cierre. En consecuencia, `CURRENT_FINALIZED_SP`
(21) no puede interpretarse automáticamente como la velocidad de Sprint 1
(ver sección 11).

**Sobre las dos columnas de estado Jira:** "Estado Jira histórico"
reproduce textualmente lo que `informe-1-seminario-licenciatura.md`
registró el 02-09-2026 — no se reescribe una fuente fechada. "Estado
Jira actual" reproduce el mismo export citado arriba. Para cualquier
análisis de estado vigente (incluida la sección 11 de story points) debe
usarse la columna "actual", nunca la histórica.

**Nota metodológica importante:** "Estado Jira" (histórico o actual) y
"Estado técnico" son columnas deliberadamente distintas (instrucción 7
de esta fase). Que SAPI-26 figure "En curso" tanto en el histórico como
en el actual, mientras su evidencia técnica muestra avance real y
verificable del lado NASA, **no es una contradicción** — es exactamente
la distinción que esta fase debe preservar, no colapsar. De igual modo,
que SAPI-28/30 hayan pasado de "En curso" (histórico) a "Finalizado"
(actual) en Jira no cambia por sí solo su estado técnico, documentado
por separado con su propia evidencia.

**Ningún estado se marcó "Done"/"Finalizado" por inferencia del
código** — los estados de ambas columnas Jira son los citados
textualmente en sus fuentes (`informe-1-seminario-licenciatura.md` y el
export `Jira (4).doc`, respectivamente), nunca una interpretación del
estado técnico.

### 4.3 Numeración legacy pre-Jira (no HU Jira, documentada por separado)

| ID | Commit | Resumen |
|---|---|---|
| HU-01..HU-04 | `6fcffa0` (20-06-2026) | "implementar pipeline ETL asíncrono y normalización geoespacial" |
| HU-05, TS-02 | `2d5afc8` (20-06-2026) | "Feature Engineering, balanceo por SMOTE y clasificador baseline RF" |
| HU-06..HU-08 | `30c8a26` (20-06-2026) | "optimizar motor predictivo XGBoost e implementar UI geográfica con caché bi-nivel" |

Sin mapeo verificable a SAPI-*. Se listan como evidencia de que existió
una numeración de requerimientos anterior, no como HU activas de
Sprint 1.

## 5. Requerimientos

Identificados a partir de evidencia real (HU Jira, componentes de
`docs/arquitectura-hito1.md`, decisiones de `docs/matriz-riesgo.md`) —
no se convierte una decisión interna de implementación en requerimiento
de usuario salvo que el propio requerimiento sea, en efecto, técnico o
metodológico.

| REQ | Tipo | Descripción | Fuente |
|---|---|---|---|
| REQ-01 | FUNCIONAL | Disponer de histórico de detecciones de incendio (NASA FIRMS) para entrenamiento/análisis | SAPI-26 |
| REQ-02 | FUNCIONAL | Vincular meteorología real (DMC) al instante de una detección | SAPI-28 |
| REQ-03 | FUNCIONAL | Disponer de topografía (elevación/pendiente/orientación) por celda | SAPI-30 |
| REQ-04 | FUNCIONAL | Limpiar/normalizar los datos crudos antes de usarlos | SAPI-32 |
| REQ-05 | NO FUNCIONAL | El dashboard debe distinguir explícitamente datos demo de datos reales | SAPI-44 |
| REQ-06 | NO FUNCIONAL | La suite de tests debe mantener un gate mínimo de cobertura (80%) | SAPI-45 |
| REQ-07 | TÉCNICO/ARQUITECTÓNICO | Mantener una matriz de riesgo activa y con evidencia | SAPI-47 |
| REQ-08 | TÉCNICO/ARQUITECTÓNICO | Mantener trazabilidad HU↔prueba | SAPI-48 |
| REQ-09 | FUNCIONAL (legacy) | Motor predictivo (baseline + XGBoost) con UI geográfica | HU-05..HU-08, TS-02 |
| REQ-10 | CIENTÍFICO/METODOLÓGICO | La meteorología DMC debe tratarse como regional, nunca reetiquetada por celda | `docs/arquitectura-hito1.md` (decisión arquitectónica); sin HU Jira |
| REQ-11 | CIENTÍFICO/METODOLÓGICO | Los features temporales deben cumplir causalidad estricta (`<= T`) | idem; sin HU Jira |
| REQ-12 | CIENTÍFICO/METODOLÓGICO | El target futuro debe definirse honestamente: ventana `(T,T+h]`, cooldown excluido (nunca 0) | idem; sin HU Jira |
| REQ-13 | TÉCNICO/ARQUITECTÓNICO | El prototipo debe aislarse completamente del pipeline legacy/demo | idem; sin HU Jira |
| REQ-14 | FUNCIONAL | Generar un ranking relativo de riesgo por celda a partir de información real | idem; sin HU Jira |
| REQ-15 | NO FUNCIONAL | Un dato topográfico faltante debe representarse como N/D, nunca como 0 | idem; sin HU Jira |
| REQ-16 | NO FUNCIONAL | El dashboard debe ensamblarse sin excepción fatal, con el modo Prototipo como default | idem; sin HU Jira |

## 6. Matriz requerimiento → HU

| REQ | HU/Issue vinculada |
|---|---|
| REQ-01 | SAPI-26 |
| REQ-02 | SAPI-28 |
| REQ-03 | SAPI-30 |
| REQ-04 | SAPI-32 |
| REQ-05 | SAPI-44 |
| REQ-06 | SAPI-45 |
| REQ-07 | SAPI-47 |
| REQ-08 | SAPI-48 |
| REQ-09 | HU-05, HU-06, HU-07, HU-08, TS-02 (legacy, numeración pre-Jira) |
| REQ-10 | **PENDIENTE DE VINCULAR EN FASE DE TRAZABILIDAD** (sección 12) |
| REQ-11 | **PENDIENTE DE VINCULAR EN FASE DE TRAZABILIDAD** |
| REQ-12 | **PENDIENTE DE VINCULAR EN FASE DE TRAZABILIDAD** |
| REQ-13 | **PENDIENTE DE VINCULAR EN FASE DE TRAZABILIDAD** |
| REQ-14 | **PENDIENTE DE VINCULAR EN FASE DE TRAZABILIDAD** |
| REQ-15 | **PENDIENTE DE VINCULAR EN FASE DE TRAZABILIDAD** |
| REQ-16 | **PENDIENTE DE VINCULAR EN FASE DE TRAZABILIDAD** |

## 7. Criterios de aceptación

| HU/Issue | CA | Estado del CA |
|---|---|---|
| SAPI-26 | "Backfill 5 años idempotente, dedup SP/NRT, manifest con conteos" (resumen de `docs/matriz-trazabilidad-hu-test.md`) | `CA_HISTORICO` |
| SAPI-28 | "Join T/HR/viento en instante de ignición; estación más cercana; ±15 min" | `CA_HISTORICO` |
| SAPI-30 | "Altitud, pendiente, orientación por celda 1 km²" | `CA_HISTORICO` — nota: la matriz que lo registra está desactualizada sobre el estado técnico (sección 4.1), pero el CA en sí (qué debía lograrse) sigue siendo el mismo texto histórico |
| SAPI-32 | "Z-Score outliers, imputación mediana solo en matched, dedup FIRMS, recorte físico meteo" | `CA_HISTORICO` |
| SAPI-44 | "UI y docs marcan fuente demo vs pipeline real" | `CA_HISTORICO` |
| SAPI-45 | "`app.utils.*` sin UnboundLocalError Cloud; suite verde; cobertura ≥80%" | `CA_HISTORICO` |
| SAPI-33, 46 | — | `CA_NO_ENCONTRADO` (tareas de gestión sin CA técnico documentado) |
| SAPI-47 | — (implícito: matriz de riesgo con evidencia) | `CA_PARCIAL` (criterio inferible del propio documento, no un CA redactado aparte) |
| SAPI-48 | — (implícito: HU conectada a test real verificable) | `CA_PARCIAL` |
| Pipeline temporal (REQ-10..16) | Sin CA histórico — solo **AC-T01..AC-T10, CRITERIOS TÉCNICOS DE VERIFICACIÓN DEL CIERRE — 07/09/2026** (`artifacts/hito1/testing/acceptance-checks.txt`) | `CA_NO_ENCONTRADO` como CA histórico; los AC-T aportan evidencia técnica real, nunca se presentan como CA de Sprint 1 |

## 8. Matriz HU → CA → prueba → resultado → evidencia

| HU/Issue | Prioridad | Estado Jira | Estado técnico | CA | Tipo de CA | Prueba | Tipo de prueba | Resultado | Evidencia | Cobertura | Brecha |
|---|---|---|---|---|---|---|---|---|---|---|---|
| SAPI-26 | NO VERIFICADO | En curso | Cerrado (NASA) | Backfill idempotente + manifest | CA_HISTORICO | `tests/test_nasa_firms_backfill.py`, `test_nasa_firms_backfill_client.py` | Integración | PASS (parte de 470/470) | `pytest-full.txt`; manifest real 12.477 registros | PARCIAL (CONAF sin fuente) | R-CONAF-01 |
| SAPI-28 | NO VERIFICADO | En curso | Parcial | Join ±15min, Haversine | CA_HISTORICO | `tests/test_meteo_fire_joiner.py` | Integración | PASS | `pytest-full.txt`; manifest feb-2025 164/164 matched | PARCIAL | `out_of_tolerance` no observado en datos reales |
| SAPI-30 | NO VERIFICADO | En curso | Avanzado (ver 4.1) | Altitud/pendiente/orientación por celda | CA_HISTORICO | `tests/test_dem_features.py`, `test_dem_terrain.py` | Unitaria/integración | PASS | `pytest-full.txt` | COMPLETA (técnicamente, no reflejada aún en la matriz histórica) | Matriz histórica desactualizada (sección 4.1) |
| SAPI-32 | NO VERIFICADO | En curso | Parcial | Limpieza Z-score/mediana | CA_HISTORICO | `tests/test_dataset_cleaner.py` | Unitaria | PASS | `pytest-full.txt`; parquet real feb-2025 | PARCIAL | Integración a producción pendiente (R-INTEGRACION-01) |
| SAPI-44 | NO VERIFICADO | Finalizado | Cerrado | UI marca fuente demo/real | CA_HISTORICO | `tests/test_app.py` | Contrato UI | PASS | `pytest-full.txt` | COMPLETA | — |
| SAPI-45 | NO VERIFICADO | Finalizado | Cerrado | Cobertura ≥80%, suite verde | CA_HISTORICO | Suite completa | Todas | PASS (470/470, 91.72%) | `pytest-full.txt`, `coverage-summary.txt` | COMPLETA | — |
| SAPI-47 | NO VERIFICADO | Finalizado | Cerrado | Matriz de riesgo con evidencia | CA_PARCIAL | Revisión manual | Manual | — | `docs/matriz-riesgo.md` | COMPLETA (documental) | No incorpora hallazgos nuevos de esta fase |
| SAPI-48 | NO VERIFICADO | Finalizado | Cerrado (con brecha, ver 4.1) | HU conectada a test real | CA_PARCIAL | Revisión manual | Manual | — | `docs/matriz-trazabilidad-hu-test.md` | PARCIAL | Desactualizada (SAPI-30, tamaño de suite) |
| SAPI-33, 46 | NO VERIFICADO | Finalizado | Manual | — | CA_NO_ENCONTRADO | — | — | — | — | SIN CA | Sin evidencia de código asociada (tareas de gestión) |
| **PENDIENTE DE VINCULAR** (REQ-10, meteo regional) | — | — | — | AC-T02 | Criterio técnico de cierre | `test_regional_meteo*.py` | Integración | PASS | `pytest-full.txt` | COMPLETA (técnica) | Sin HU Jira |
| **PENDIENTE DE VINCULAR** (REQ-11, causalidad) | — | — | — | AC-T03 | Criterio técnico de cierre | `test_causality_validator.py`, `test_temporal_features.py` | Unitaria | PASS | `pytest-full.txt` | COMPLETA (técnica) | Sin HU Jira |
| **PENDIENTE DE VINCULAR** (REQ-12, target) | — | — | — | AC-T04 | Criterio técnico de cierre | `test_target_builder.py` | Unitaria | PASS | `pytest-full.txt` | COMPLETA (técnica) | Sin HU Jira |
| **PENDIENTE DE VINCULAR** (REQ-13, aislamiento) | — | — | — | AC-T01/T10 | Criterio técnico de cierre | `test_prototype_service.py`, `test_architecture.py` | Contrato | PASS | `pytest-full.txt` | COMPLETA (técnica) | Sin HU Jira |
| **PENDIENTE DE VINCULAR** (REQ-14, ranking) | — | — | — | AC-T05/T06/T07 | Criterio técnico de cierre | `test_prototype_service.py` | Unitaria/integración | PASS | `pytest-full.txt` | COMPLETA (técnica) | Sin HU Jira |
| **PENDIENTE DE VINCULAR** (REQ-15, DEM N/D) | — | — | — | AC-T08 | Criterio técnico de cierre | `test_dem_features.py` | Integración | PASS (datos) / sin test (UI) | `pytest-full.txt` | PARCIAL | UI (`_fmt_nd`) sin test dedicado |
| **PENDIENTE DE VINCULAR** (REQ-16, app carga) | — | — | — | AC-T09 | Criterio técnico de cierre | `test_app_integration.py` | Integración (AppTest) | PASS | `streamlit-smoke.txt` | COMPLETA (técnica) | Sin HU Jira |

**HU_CA_TEST_RESULT_EVIDENCE: PARTIAL** — completa para las 8 HU/tarea
técnica con evidencia repo-verificable; sin CA histórico ni HU para los
7 requerimientos del pipeline temporal (evidencia técnica sí completa,
trazabilidad a HU no).

## 9. Cobertura del Sprint

Fuente fresca: `artifacts/hito1/testing/pytest-full.txt` +
`pytest-junit.xml` — **470 collected, 470 passed, 0 failed** (coincide
exactamente con lo guardado, no se re-ejecutó la suite para esta fase).
Cobertura de código: **91.72%** (coincide con
`artifacts/hito1/testing/coverage-summary.txt`).

Por tipo de ítem (sin mezclar HU con tareas de gestión ni con el
pipeline sin HU):

| Tipo | Total | Con CA verificable | Con prueba | Con resultado | Con evidencia | Completamente trazadas | Parcialmente trazadas |
|---|---|---|---|---|---|---|---|
| HU técnicas Jira (SAPI-26/28/30/32) | 4 | 4 | 4 | 4 | 4 | 1 (SAPI-30, técnicamente) | 3 |
| Tareas técnicas/documentales Jira (SAPI-44/45/47/48) | 4 | 4 (2 CA_HISTORICO + 2 CA_PARCIAL) | 4 | 4 | 4 | 2 (SAPI-44/45) | 2 (SAPI-47/48) |
| Tareas de gestión Jira (SAPI-33/46) | 2 | 0 | 0 | 0 | 0 | 0 | 0 (sin trazabilidad técnica posible) |
| Requerimientos del pipeline temporal (REQ-10..16, sin HU) | 7 | 0 (histórico) / 7 (criterio técnico de cierre) | 7 | 7 | 7 | 0 (falta HU) | 7 (evidencia técnica completa, trazabilidad a HU pendiente) |
| Legacy pre-Jira (HU-01..08, TS-02) | 8 | 0 | NO VERIFICADO (sin mapeo a tests actuales) | — | — | 0 | 0 |

**HU_COVERAGE (resumen verificable):** de 10 tickets Jira verificables,
8 tienen evidencia técnica completa (aunque 3 con brecha documentada de
integración/CONAF/out_of_tolerance) y 2 (tareas de gestión) no admiten
trazabilidad técnica. El incremento más reciente y metodológicamente
central del proyecto (7 requerimientos del pipeline temporal) tiene
evidencia técnica **completa** pero **cero** HU Jira vinculada.

## 10. DoD — evidencia disponible

Búsqueda exhaustiva (repetida de forma independiente en esta fase, sin
reutilizar el resultado de la fase de Testing sin verificar): sin
resultados en todo el repositorio.

**HISTORICAL_DOD_EVIDENCE: NOT_FOUND.**

No se vincula DoD→HU Done→evidencia porque no existe el DoD. Acción de
mejora (no evidencia retroactiva): **definir un DoD explícito antes de
iniciar Sprint 2**, con criterios mínimos verificables (p. ej. "código
con tests en verde", "cobertura no decrece", "sin imports prohibidos
por el Data Contract") que ya son, de hecho, invariantes reales que este
proyecto respeta en la práctica (ver `tests/test_architecture.py`,
gate de cobertura en `pytest.ini`) — formalizarlos como DoD sería
reconocer por escrito una disciplina que ya existe informalmente.

## 11. Story points y límite sobre velocidad

**Fuente de esta sección:** export Jira `Jira (4).doc`, externo al
repositorio de código y correspondiente al estado disponible del tablero
al 07-09-2026. Reemplaza la cifra "26/26 SP estimados" que esta sección
citaba antes a partir únicamente de
`docs/informe-1-seminario-licenciatura.md` (02-09-2026) — ese documento
solo cubría las 4 HU técnicas y no las 6 tareas de gestión/documentación,
que sí tienen SP propio en el export.

**Story points actualmente asociados a Sprint 1** (según el export,
estado actual — no un snapshot de inicio de Sprint):

| Ticket | SP | Estado (export) |
|---|---|---|
| SAPI-48 | 2 | Finalizado |
| SAPI-47 | 1 | Finalizado |
| SAPI-45 | 3 | Finalizado |
| SAPI-44 | 2 | Finalizado |
| SAPI-30 | 5 | Finalizado |
| SAPI-28 | 8 | Finalizado |
| **Subtotal Finalizado** | **21** | |
| SAPI-32 | 5 | Por hacer |
| SAPI-26 | 8 | En curso |
| **Subtotal No finalizado** | **13** | |
| **TOTAL actual asociado a Sprint 1** | **34** | |

Las subtareas sin Story Point propio (SAPI-33, SAPI-46 — tareas de
gestión sin evidencia de código, sección 4.2) **no se agregan** a este
total, tal como especifica el export.

- **CURRENT_SPRINT1_SP: 34**
- **CURRENT_FINALIZED_SP: 21**
- **CURRENT_NOT_FINALIZED_SP: 13**

**Dos brechas distintas — no una sola, y no intercambiables:**

1. **Compromiso inicial vs. entregado (`ORIGINAL_COMMITMENT_SNAPSHOT:
   NOT_FOUND`):** ningún archivo, interno o externo, documenta cuál era
   el total de SP comprometido el primer día de Sprint 1. Sin ese punto
   de partida no se puede comparar "lo prometido" contra "lo entregado".
   Esto por sí solo ya impediría afirmar un compromiso inicial de 34 SP.
2. **Velocidad del Sprint (`VELOCITY: NOT_RECONSTRUCTABLE`):** la
   velocidad de Scrum es la cantidad de trabajo (SP) que un equipo
   **completa y entrega dentro de los límites de un sprint** — no una
   división de SP completados entre duración calendario, y no algo que
   dependa únicamente de conocer el compromiso inicial. Aunque
   existiera un snapshot de compromiso inicial, la velocidad de Sprint 1
   seguiría sin ser reconstruible aquí por una razón **distinta y más
   directa**, ya expuesta en la sección 4.2 ("Fechas académicas
   relevantes"): el export citado es un snapshot del estado
   posterior/actual del tablero, no un snapshot verificado de qué
   issues estaban Done exactamente al cierre planificado de Sprint 1.
   `CURRENT_FINALIZED_SP = 21` mezcla trabajo que pudo cerrarse dentro
   de Sprint 1 con trabajo cerrado después de su fin planificado, y no
   puede leerse como "SP entregados durante Sprint 1".

**Formulación académica a usar (la única defendible con esta
evidencia):**

> 34 SP están actualmente asociados a Sprint 1 y 21 SP figuran
> actualmente como Finalizados según el export Jira disponible. Este
> snapshot no representa de forma verificable el estado exacto al cierre
> del Sprint 1 y contiene issues resueltos con posterioridad a la fecha
> académica planificada de cierre (31-08-2026). Por ello, la velocidad
> del Sprint 1 no puede reconstruirse de forma fiable a partir de la
> evidencia disponible.

**Enunciados explícitamente NO usados, porque ninguno es demostrable con
el snapshot disponible:** "velocidad = 21 SP", "compromiso inicial = 34
SP", "se completó 61,8% del compromiso original". Ninguno de los tres
aparece en este documento. Tampoco se afirma que la única causa de
`VELOCITY: NOT_RECONSTRUCTABLE` sea la ausencia de snapshot inicial — esa
es una brecha aparte (compromiso vs. entregado), no la razón principal
de por qué no se puede calcular la velocidad de Sprint 1 con este export.

## 12. Cambios derivados de hallazgos

Fuente: `artifacts/hito1/testing/defect-evidence.md` (6 hallazgos
D-01..D-06) + `docs/matriz-riesgo.md` (7 riesgos con decisión de
gestión). Cadena completa hasta donde la evidencia lo permite:

| Hallazgo | Análisis | Decisión | Cambio técnico/documental | Issue/backlog |
|---|---|---|---|---|
| D-01 (meteo asignada por posición) | `scripts/auditoria_integridad_datos.py`, 38/50 celdas mal asignadas | Construir módulo regional nuevo, nunca legacy `_load_meteo()` | `src/procesamiento/regional_meteo.py` + tests | **PARCIAL — SIN ISSUE VERIFICABLE** |
| D-02 (n_positive_rows sobrecontaba) | Test dedicado detectó el caso de dos eventos calificando | Contar por fila única, no por par evento-fila | `episode_evaluation.py` + test de regresión | **PARCIAL — SIN ISSUE VERIFICABLE** |
| D-03 (archivos de conflicto mezclados) | Glob ingenuo capturaría `_conflicto_*` | Exclusión explícita en el glob | `regional_meteo.py` + test | **PARCIAL — SIN ISSUE VERIFICABLE** |
| D-04 (HistGradientBoosting, clase minoritaria) | `ValueError` de sklearn poco explicable en fold 2021 | Guarda explícita con mensaje claro | `experiment_abcd.py::run_fold()` + test | **PARCIAL — SIN ISSUE VERIFICABLE** |
| D-05 (riesgo de desalineación cell_id↔score) | Riesgo preventivo identificado | Alineación por índice, nunca posición | Comentario + test de contrato | **PARCIAL — SIN ISSUE VERIFICABLE** |
| D-06 (DEM sin cobertura → NaN, no 0) | Decisión de diseño desde el origen | Usar `HistGradientBoostingClassifier` (NaN nativo) | `dem_features.py` + tests | **PARCIAL — SIN ISSUE VERIFICABLE**; relacionado con SAPI-30 (ver 4.1) |
| R-GRILLA-01 (grilla demo 17% de cobertura real) | Medición real contra evento 2024-02-03 | Reconstruir grilla única, fuente en `src/geo/grid.py` | `app/utils/grid.py`, `tests/test_grid.py`, `test_grid_consistency.py` | No verificado — `docs/matriz-riesgo.md` no cita un ticket Jira para este cambio específico |
| R-ETIQUETA-01 (regla 30-30-30 no correlaciona con incendios reales) | Exploratorio n=12, leave-one-out | Diferir a Sprint 2, no forzar entrenamiento | Ninguno todavía (investigación abierta) | No aplica (decisión de diferir, no de cambiar código) |

**DEFECT_TO_ACTION_TRACEABILITY: PARTIAL** — hallazgo→análisis→decisión→
cambio está completo y verificado en los 8 casos; el último eslabón
(issue/backlog Jira) no está verificado en ninguno.

## 13. Evidencia semanal

Tabla ya construida en la fase de Testing
(`artifacts/hito1/testing/rubric-testing-map.md`) — se reproduce aquí
como parte del documento canónico, sin backdatear ni añadir certeza que
no existe:

| Semana | Actividad esperada (planificación S1-S6, como expectativa) | Evidencia realmente encontrada | Fecha verificable | Desviación | Impacto |
|---|---|---|---|---|---|
| 3 | Plan de pruebas + primeras ejecuciones | Commits iniciales `#HU-01..#HU-08`/`#TS-02` (candidato cronológico, sin calendario para confirmar) | 20-06-2026 | No confirmable — falta calendario del curso | Bajo (no invalida el trabajo, solo impide certificar la semana exacta) |
| 4 | Resultados unitarios/integración | Expansión de suite a gate 80% (`b8bbeb5`); `reports/coverage_run.txt` | 31-08-2026 / 02-09-2026 | No confirmable contra calendario | Bajo |
| 5 | Aceptación con usuario | `docs/acta-pruebas-aceptacion-usuario.md` (autoevaluación, no usuario externo) | 01-09-2026 / cierre 05-09-2026 | Es autoevaluación, no aceptación externa — desviación real del tipo de evidencia esperado | Medio — la rúbrica probablemente espera un usuario externo, no el mismo desarrollador |

No se encontró en el repositorio un calendario de curso que confirme la
correspondencia fecha↔semana (ya señalado en
`docs/informe-1-seminario-licenciatura.md`). No se backdatea ninguna
fila para forzar el encaje.

## 14. Brechas de trazabilidad

1. **BRECHA: incremento técnico implementado sin HU histórica
   verificable asociada** (pipeline temporal completo — `regional_meteo`,
   `episodes`, `target_builder`, `causality_validator`, Modelo D,
   `prototype_service`). Ver sección 12 del encargo / sección 4.2 y 8 de
   este documento. **Funcionalidad que cubre:** estimación y priorización
   de riesgo relativo de nuevas detecciones FIRMS por celda, con
   causalidad temporal verificada. **Evidencia técnica:** 470/470 tests
   PASS, 10 criterios AC-T verificados, arquitectura congelada y
   auditada. **Requerimiento que satisface:** REQ-10 a REQ-16 (sección
   5). **Por qué falta el vínculo:** el pipeline se construyó como una
   auditoría/reconstrucción metodológica dentro de Sprint 1, después del
   corte de HU documentado en Jira al 02-09-2026 — no se creó (ni se
   crea ahora) una HU retroactiva para cubrirlo. **Acción recomendada
   para Sprint 2:** crear una HU real en Jira que describa el pipeline
   temporal como incremento, y vincular retroactivamente (desde ahora en
   adelante, no reescribiendo el pasado) los AC-T01..T10 como su
   evidencia de aceptación técnica.
2. `docs/matriz-trazabilidad-hu-test.md` desactualizada en la fila
   SAPI-30 y en el conteo total de tests (sección 4.1) — no se modifica
   en esta fase (fuera de alcance), pero queda señalado para su
   actualización formal.
3. Sin Sprint Goal, DoD ni Sprint Review históricos (secciones 3, 10; y
   confirmado también en la fase de Testing) — brechas históricas no
   recuperables retroactivamente.
4. Dos brechas distintas de story points/velocidad (sección 11): (a) sin
   snapshot de compromiso inicial de SP (impide comparar comprometido
   vs. entregado); (b) el export de SP actual (34/21/13) es un snapshot
   posterior al cierre planificado de Sprint 1 (31-08-2026) — SAPI-28 y
   SAPI-30 resueltas 07-09-2026 — por lo que la velocidad del Sprint no
   es reconstruible aunque (a) se resolviera.
5. Sin acceso a Jira en vivo en esta fase — el estado de "Sprint
   Backlog/Jira" y del tablero público no se verificó más allá de lo ya
   escrito en `.md` del repositorio.
6. 2 tickets de gestión (SAPI-33, 46) sin ninguna evidencia técnica
   asociable — no es una brecha de esta fase, es la naturaleza de una
   tarea de gestión, documentado así explícitamente (`CA_NO_ENCONTRADO`).
7. Numeración legacy `HU-01..HU-08`/`TS-02` sin mapeo verificable a
   `SAPI-*` (sección 4.1/4.3).

## 15. Acciones Sprint 2

1. Crear en Jira una HU real para el pipeline temporal (regional_meteo /
   episodes / target_builder / Modelo D / prototype_service) y vincular
   los AC-T01..T10 como su evidencia técnica de cierre — cierra la
   brecha #1 de la sección 14.
2. Actualizar `docs/matriz-trazabilidad-hu-test.md` (fuera de esta fase)
   para reflejar el estado real de SAPI-30 y el tamaño actual de la
   suite (470 tests).
3. Definir un DoD explícito antes de iniciar Sprint 2 (sección 10).
4. Definir y registrar un Sprint Goal explícito al inicio de Sprint 2,
   con fecha verificable desde el primer día.
5. Tomar un snapshot verificable del compromiso de SP al inicio de
   Sprint 2 (para poder calcular velocidad real al cierre).
6. Ejecutar una Sprint Review formal con PO/stakeholder real (usar
   `artifacts/hito1/testing/acceptance-protocol.md` como base del guion
   de demo, actualizado a lo que Sprint 2 entregue).
7. Vincular los 6 hallazgos de `defect-evidence.md` (y R-GRILLA-01) a
   issues Jira verificables, cerrando la trazabilidad de Gestión del
   cambio.
8. Resolver R-CONAF-01, R-DMC-01, R-INTEGRACION-01, R-ETIQUETA-01 según
   las decisiones de gestión ya documentadas en `docs/matriz-riesgo.md`.
9. Confirmar contra el calendario real del curso (syllabus INSW421) la
   correspondencia fecha↔semana, para poder cerrar la sección 13 de
   forma verificada en vez de aproximada.

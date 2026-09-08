# Matriz de riesgos e impedimentos — Sprint 1 / Hito 1

**Estado:** documento de trabajo. Arquitectura (`docs/arquitectura-hito1.md`),
Testing (`docs/testing-evidencia-hito1.md`), Trazabilidad
(`docs/trazabilidad-hito1.md`) y Atributos de Calidad
(`docs/atributos-calidad-hito1.md`) permanecen CONGELADOS — esta fase
los audita y reutiliza como fuente, no los reabre. Fecha de esta fase:
**07-09-2026**.

**Principio de honestidad temporal:** esta matriz se construye HOY,
07-09-2026. Donde existe un registro histórico real y fechado (commit,
manifest, `docs/matriz-riesgo.md`), se cita como tal
(`RIESGO_HISTORICO_VERIFICADO`). Donde el riesgo se identifica o
reformula recién en esta fase a partir de evidencia técnica ya
existente, se etiqueta explícitamente `RIESGO_RECONSTRUIDO_EN_CIERRE —
07-09-2026` — nunca se presenta como si hubiera sido registrado semanas
atrás. No se encontró evidencia de una revisión semanal de riesgos
durante Sprint 1 (búsqueda explícita, sin resultados):

**WEEKLY_RISK_UPDATE_EVIDENCE: NOT_FOUND.**

## 1. Objetivo

Construir la matriz de riesgos canónica de Hito 1 con riesgos, defectos,
impedimentos y decisiones realmente verificables — probabilidad,
impacto, prioridad, respuesta, responsable, acción, evidencia, estado y
seguimiento — sin fabricar movimientos históricos ni convertir una
corrección técnica en "riesgo cero".

## 2. Fuentes auditadas

`docs/matriz-riesgo.md` (05-09-2026, 7 riesgos históricos reales);
`docs/testing-evidencia-hito1.md` + `artifacts/hito1/testing/*`
(470/470, 91.72%, AC-T01..T10); `docs/trazabilidad-hito1.md` (HU/SP,
`TEMPORAL_PIPELINE_HU_LINK: GAP`); `docs/atributos-calidad-hito1.md`
(brechas de mantenibilidad/usabilidad/rendimiento/seguridad);
`artifacts/hito1/testing/defect-evidence.md` (D-01..D-06);
`docs/informe-1-seminario-licenciatura.md`; `reports/auditoria_integridad_datos.json`;
`reports/megaevento_2024-02-03_report.json`; `git log`/`git tag`. No se
encontró ningún export de Jira adicional al ya usado en Trazabilidad
(`Jira (4).doc`, externo al repositorio).

## 3. Escala de priorización

`docs/matriz-riesgo.md` usa una escala cualitativa (Alta/Media/Baja) solo
para probabilidad, sin una fórmula de exposición explícita. No existe en
el repositorio una escala numérica verificable anterior a esta fase.

**ESCALA DE PRIORIZACIÓN UTILIZADA EN EL CIERRE — 07-09-2026** (no
existía desde el inicio del Sprint; se define ahora para poder priorizar
de forma consistente):

- Probabilidad: 1 Baja / 2 Media / 3 Alta
- Impacto: 1 Bajo / 2 Medio / 3 Alto
- Exposición = Probabilidad × Impacto (1-9)
- Prioridad: 1-2 Baja · 3-4 Media · 6-9 Alta

Para los 7 riesgos de `docs/matriz-riesgo.md`, la probabilidad
cualitativa original ("Alta"/"Media"/"Baja") se traduce a esta escala
numérica como un mapeo hecho en esta fase (no una recalificación
retroactiva de lo que el documento decía) — el impacto (columna nueva,
no existía en el original) se asigna aquí por primera vez, según la
consecuencia real descrita en cada riesgo.

## 4. Categorías usadas

`RIESGO DE PROYECTO` (gestión, Sprint, Jira) · `RIESGO TÉCNICO`
(pipeline/código) · `RIESGO DE DATOS` (integridad/cobertura de fuentes)
· `RIESGO METODOLÓGICO` (proceso de trabajo) · `RIESGO CIENTÍFICO`
(validez/generalización del modelo). No se mezclan automáticamente.

## 5. Matriz principal — identificación y severidad

| ID | Categoría | Riesgo | Origen/fecha verificable | Tipo | Probabilidad | Impacto | Exposición | Prioridad | Estado actual |
|---|---|---|---|---|---|---|---|---|---|
| R-NASA-FIRMS-01 | Dato | API NASA FIRMS rechazaba solicitudes (querystring en vez de ruta posicional) | `docs/matriz-riesgo.md`; corregido 30-08-2026, commit `8d53ae8` | RIESGO_HISTORICO_VERIFICADO | 2 | 3 | 6 | Alta | MATERIALIZADO_Y_CORREGIDO |
| R-GRILLA-01 | Técnico | Grilla demo cubría solo 17% del evento real 2024-02-03 (8,4×4,0 km vs. corredor documentado) | `docs/matriz-riesgo.md`; cerrado 05/06-09-2026, commits `6477268`/`2ef14cd` | RIESGO_HISTORICO_VERIFICADO | 3 | 3 | 9 | Alta | MATERIALIZADO_Y_CORREGIDO |
| R-DMC-01 | Dato | Histórico DMC incompleto: solo 1 de 3 estaciones configuradas entrega datos reales (330007) | `docs/matriz-riesgo.md`, 05-09-2026 | RIESGO_HISTORICO_VERIFICADO | 3 | 2 | 6 | Alta | MITIGADO (parcial) |
| R-CONAF-01 | Dato | Sin fuente real de incendios CONAF integrada (stub sin datos) | `docs/matriz-riesgo.md`, investigado 30-08-2026 | RIESGO_HISTORICO_VERIFICADO | 3 | 2 | 6 | Alta | TRANSFERIDO_A_SPRINT_2 |
| R-COBERTURA-01 | Técnico | Cobertura de tests por debajo del umbral 80% en algún momento del sprint | `docs/matriz-riesgo.md`; cerrado 31-08-2026 (80.34%) | RIESGO_HISTORICO_VERIFICADO | 1 | 2 | 2 | Baja | MATERIALIZADO_Y_CORREGIDO (actualizado: 91.72% al 07-09-2026, ver nota 5.1) |
| R-INTEGRACION-01 | Técnico | Flujo de riesgo por celda y flujo de join ignición↔meteo no conectados en producción | `docs/matriz-riesgo.md`, documentado 30-08-2026 | RIESGO_HISTORICO_VERIFICADO | 3 | 3 | 9 | Alta | TRANSFERIDO_A_SPRINT_2 |
| R-ETIQUETA-01 | Científico | Etiqueta `ignicion` (regla 30-30-30) sin correlación confirmada con incendios reales | `docs/matriz-riesgo.md`, investigado 01/06-09-2026 | RIESGO_HISTORICO_VERIFICADO | 3 | 3 | 9 | Alta | ABIERTO (investigación exploratoria) |
| R-METEO-POSICIONAL-01 | Dato | Meteo DMC asignada por posición de fila a 50 celdas (38/50 geográficamente incorrectas) | `reports/auditoria_integridad_datos.json`; reemplazado en el pipeline temporal (commit `60f9fa7`, 07-09-2026) | RIESGO_RECONSTRUIDO_EN_CIERRE | 3 | 3 | 9 | Alta | MATERIALIZADO_Y_CORREGIDO |
| R-TARGET-OVERCOUNT-01 | Técnico | `n_positive_rows` sobrecontaba filas cuando dos eventos calificaban en la misma fila | `artifacts/hito1/testing/defect-evidence.md`, D-02 | RIESGO_RECONSTRUIDO_EN_CIERRE | 2 | 2 | 4 | Media | MATERIALIZADO_Y_CORREGIDO |
| R-BACKFILL-CONFLICTO-01 | Dato | Archivos `_conflicto_` del backfill DMC podían mezclarse con datos aceptados | `defect-evidence.md`, D-03 | RIESGO_RECONSTRUIDO_EN_CIERRE | 2 | 2 | 4 | Media | MATERIALIZADO_Y_CORREGIDO |
| R-MINCLASS-01 | Técnico | `HistGradientBoostingClassifier` fallaba con clase minoritaria insuficiente en un fold | `defect-evidence.md`, D-04 | RIESGO_RECONSTRUIDO_EN_CIERRE | 2 | 2 | 4 | Media | MATERIALIZADO_Y_CORREGIDO |
| R-ALIGN-CELLID-01 | Técnico | Riesgo preventivo de desalineación `cell_id`↔score tras reordenamiento | `defect-evidence.md`, D-05 (preventivo, sin incidente real observado) | RIESGO_RECONSTRUIDO_EN_CIERRE | 1 | 3 | 3 | Media | MITIGADO (preventivo) |
| R-DEM-NAN-01 | Dato | Riesgo de imputar 0 en DEM sin cobertura, fabricando un dato físico falso | `defect-evidence.md`, D-06 (decisión de diseño desde el origen) | RIESGO_RECONSTRUIDO_EN_CIERRE | 1 | 2 | 2 | Baja | MITIGADO (por diseño) |
| R-LEGACY-CONTAM-01 | Técnico | Contaminación del prototipo por imports del pipeline legacy/demo | `docs/arquitectura-hito1.md`; `tests/test_no_legacy_imports_in_prototype_modules` | RIESGO_RECONSTRUIDO_EN_CIERRE | 1 | 3 | 3 | Media | MITIGADO (verificado) |
| R-FRESCURA-01 | Dato | Dato meteorológico usado por el prototipo puede estar desactualizado sin que se note | `docs/arquitectura-hito1.md` sección 9; `tests/test_prototype_freshness.py` | RIESGO_RECONSTRUIDO_EN_CIERRE | 2 | 2 | 4 | Media | MITIGADO (banner) |
| R-HU-PIPELINE-01 | Metodológico | Pipeline temporal completo implementado sin HU/Jira histórica vinculada | `docs/trazabilidad-hito1.md`, sección 14 (`TEMPORAL_PIPELINE_HU_LINK: GAP`) | RIESGO_RECONSTRUIDO_EN_CIERRE | 3 | 2 | 6 | Alta | TRANSFERIDO_A_SPRINT_2 |
| R-ACEPT-EXT-01 | Metodológico | Sin aceptación externa formal (PO/stakeholder) del incremento del pipeline temporal | `docs/testing-evidencia-hito1.md`, sección 14; `docs/atributos-calidad-hito1.md`, sección 11 | RIESGO_RECONSTRUIDO_EN_CIERRE | 3 | 2 | 6 | Alta | ABIERTO |
| R-SPRINT-MGMT-01 | Metodológico | Sin Sprint Goal, DoD ni Sprint Review históricos; sin snapshot inicial de SP | `docs/trazabilidad-hito1.md`, secciones 3, 10, 11 | RIESGO_RECONSTRUIDO_EN_CIERRE | 3 | 2 | 6 | Alta | NO_RESUELTO (no recuperable retroactivamente) |
| R-MANTEN-01 | Técnico | Sin configuración de lint/type-checking ni métrica de complejidad ciclomática | `docs/atributos-calidad-hito1.md`, sección 7 (QA-03) | RIESGO_RECONSTRUIDO_EN_CIERRE | 2 | 1 | 2 | Baja | ABIERTO |
| R-PERF-SEC-01 | Técnico | Rendimiento y seguridad sin ninguna medición/verificación | `docs/atributos-calidad-hito1.md`, sección 12 (QA-08, QA-09) | RIESGO_RECONSTRUIDO_EN_CIERRE | 2 | 2 | 4 | Media | NO_RESUELTO |
| R-CIENT-POSITIVOS-01 | Científico | Escasez de positivos históricos produce empates masivos de score (41/50 celdas) | `docs/arquitectura-hito1.md` sección 6/9; `sapi-scientific-claims.md` | RIESGO_HISTORICO_VERIFICADO (auditoría 06-09-2026) | 3 | 2 | 6 | Alta | ACEPTADO (limitación, no defecto) |
| R-CIENT-MEGAEVENTO-01 | Científico | Un solo evento histórico (2024-02-03) concentra 355/n detecciones y domina el dataset de positivos de ese día (26 raw episodes, 14 celdas) | `reports/megaevento_2024-02-03_report.json` | RIESGO_HISTORICO_VERIFICADO | 2 | 2 | 4 | Media | ACEPTADO (documentado) |
| R-CIENT-GENERALIZACION-01 | Científico | Capacidad predictiva generalizable no demostrada; folds walk-forward limitados a pocos años; FIRMS ≠ incendio confirmado | `docs/arquitectura-hito1.md`, sección 9; `docs/testing-evidencia-hito1.md`, sección 19 | RIESGO_HISTORICO_VERIFICADO | 3 | 3 | 9 | Alta | ACEPTADO (límite explícito del alcance) |

### 5.1 Nota de actualización — R-COBERTURA-01

`docs/matriz-riesgo.md` registra el cierre en 80.34% (31-08-2026, 188
tests). La ejecución fresca de la fase de Testing (07-09-2026) da
**91.72%** sobre 470 tests (`artifacts/hito1/testing/coverage-summary.txt`).
No se modifica `docs/matriz-riesgo.md` (congelado fuera del alcance de
edición en esta fase) — se documenta aquí la cifra vigente sin
sobrescribir el registro histórico.

## 6. Matriz principal — gestión y evidencia

| ID | Respuesta | Responsable | Acción | Estado de mitigación | Evidencia | Riesgo residual | Próxima acción | Seguimiento semanal |
|---|---|---|---|---|---|---|---|---|
| R-NASA-FIRMS-01 | Corregir | Equipo S.A.P.I. | Contrato de URL a formato posicional | VERIFICADA | Manifest 12.477 registros, SHA256 | Rate limit 429 en backfills masivos (mitigado con backoff) | Ninguna | Ver tabla §7 |
| R-GRILLA-01 | Corregir | Equipo S.A.P.I. | Fuente única de geometría (`src/geo/grid.py`) | VERIFICADA | `test_grid_covers_the_real_2024_fire` (74,7%); `test_grid_consistency.py` | Grilla PostGIS de producción aún angosta (deuda documentada) | Regenerar features de producción sobre grilla nueva | Ver tabla §7 |
| R-DMC-01 | Mitigar | Equipo S.A.P.I. | Diferir backfill multi-estación; join con 1 estación + tests | IMPLEMENTADA | `meteo_fire_joiner.py`; `test_meteo_fire_joiner.py` | Solo 1/3 estaciones con datos reales — cobertura espacial meteorológica limitada | Backfill multi-mes/estación | Ver tabla §7 |
| R-CONAF-01 | Diferir | Equipo S.A.P.I. | Decisión explícita de posponer integración real | PROPUESTA (para Sprint 2) | `docs/matriz-riesgo.md` (investigación 30-08-2026) | Dataset de entrenamiento depende 100% de NASA FIRMS | Spike de fuente oficial CONAF/SNIF | Ver tabla §7 |
| R-COBERTURA-01 | Corregir | Equipo S.A.P.I. | Ampliar suite hasta superar el gate | VERIFICADA | `coverage-summary.txt` (91.72%, gate 80%) | Módulos legacy en 0-60% (`persister.py`, `inference_engine.py`) | Ninguna sobre el gate global | Ver tabla §7 |
| R-INTEGRACION-01 | Diferir | Equipo S.A.P.I. | Puente mínimo de prueba (SAPI-32) sin integrar a producción | PROPUESTA (Sprint 2) | `matriz_features_real_sapi32_preview.parquet` | Mapa de riesgo de producción no usa igniciones reales todavía | Conectar puente a `matriz_features` real | Ver tabla §7 |
| R-ETIQUETA-01 | Investigar | Equipo S.A.P.I. | Exploración n=12, leave-one-out, sin decisión de reemplazo | PROPUESTA (Sprint 2) | `reports/exploratorio_r_etiqueta_01_resultados.csv` | Etiqueta de entrenamiento del modelo legacy sigue siendo la regla sintética | Definir `ignicion=1` desde detecciones reales confirmadas | Ver tabla §7 |
| R-METEO-POSICIONAL-01 | Corregir | Equipo S.A.P.I. | Módulo `regional_meteo.py` sin `cell_id` por diseño | VERIFICADA | `test_regional_meteo*.py` PASS | Una sola estación real sigue siendo la única fuente regional (ver R-DMC-01) | Ninguna sobre este defecto puntual | Ver tabla §7 |
| R-TARGET-OVERCOUNT-01 | Corregir | Equipo S.A.P.I. | Contar por `(cell_id, forecast_time)` único | VERIFICADA | `test_n_positive_rows_counts_rows_not_row_event_pairs_when_two_events_qualify` PASS | Ninguno conocido | Ninguna | Ver tabla §7 |
| R-BACKFILL-CONFLICTO-01 | Corregir | Equipo S.A.P.I. | Exclusión explícita de archivos `_conflicto_` | VERIFICADA | `test_ignores_conflict_files_left_by_the_backfill_script` PASS | Conflictos siguen requiriendo revisión manual (por diseño) | Ninguna | Ver tabla §7 |
| R-MINCLASS-01 | Corregir | Equipo S.A.P.I. | Guarda explícita en `run_fold()` | VERIFICADA | `test_run_fold_handles_a_train_set_with_only_one_positive_without_crashing` PASS | Folds con pocos positivos siguen teniendo soporte estadístico débil (riesgo científico, no técnico) | Ninguna sobre el guard | Ver tabla §7 |
| R-ALIGN-CELLID-01 | Prevenir | Equipo S.A.P.I. | Alineación por índice `cell_id`, nunca por posición | VERIFICADA | `test_reordering_features_df_does_not_desync_cell_id_and_score` PASS | Ninguno mientras el contrato de índice se mantenga | Ninguna | Ver tabla §7 |
| R-DEM-NAN-01 | Prevenir | Equipo S.A.P.I. | `HistGradientBoostingClassifier` (NaN nativo) en vez de imputación | VERIFICADA | `test_sample_grid_topography_returns_nan_for_cell_outside_raster_coverage` PASS | UI (`_fmt_nd`) sin test dedicado (ver `docs/atributos-calidad-hito1.md` QA-04) | Test unitario de `_fmt_nd()` (Sprint 2) | Ver tabla §7 |
| R-LEGACY-CONTAM-01 | Prevenir | Equipo S.A.P.I. | Módulos separados, sin imports cruzados | VERIFICADA | `test_no_legacy_imports_in_prototype_modules` PASS | Ninguno mientras el test de contrato se mantenga | Ninguna | Ver tabla §7 |
| R-FRESCURA-01 | Mitigar | Equipo S.A.P.I. | Clasificación de frescura + banner explícito | VERIFICADA | `test_prototype_freshness.py` (8 tests) PASS | Dato sigue limitado a 1 estación (ver R-DMC-01) | Ninguna sobre el banner | Ver tabla §7 |
| R-HU-PIPELINE-01 | Transferir | Equipo S.A.P.I. | Ninguna acción de código; documentado como brecha | PROPUESTA (Sprint 2) | `docs/trazabilidad-hito1.md`, sección 15, acción 1 | Evidencia técnica sin respaldo de gestión (Jira) | Crear HU real y vincular AC-T01..T10 | Ver tabla §7 |
| R-ACEPT-EXT-01 | Transferir | Equipo S.A.P.I. | Protocolo de aceptación listo, sin ejecutar | PROPUESTA | `artifacts/hito1/testing/acceptance-protocol.md` (campos vacíos) | Sin validación de un evaluador distinto al desarrollador | Ejecutar la sesión real de aceptación | Ver tabla §7 |
| R-SPRINT-MGMT-01 | Aceptar | Equipo S.A.P.I. | Ninguna retroactiva posible | NO_APLICA (histórico irrecuperable) | `docs/trazabilidad-hito1.md`, secciones 3/10/11 | Rúbrica de Sprint 1 sin estos elementos | Definir DoD/Sprint Goal/snapshot antes de Sprint 2 | Ver tabla §7 |
| R-MANTEN-01 | Diferir | Equipo S.A.P.I. | Ninguna en esta fase (fuera de alcance tocar el repo) | PROPUESTA | `docs/atributos-calidad-hito1.md`, sección 7 | Código sin métrica de calidad estática | Configurar `ruff` (Sprint 2) | Ver tabla §7 |
| R-PERF-SEC-01 | Diferir | Equipo S.A.P.I. | Ninguna en esta fase | PROPUESTA | `docs/atributos-calidad-hito1.md`, sección 12 | Sin visibilidad de rendimiento/seguridad | Ejecutar `locustfile.py`; definir tests de seguridad mínimos | Ver tabla §7 |
| R-CIENT-POSITIVOS-01 | Aceptar | Equipo S.A.P.I. | Documentar honestamente en vez de ocultar | N/A (limitación, no defecto) | `sapi-scientific-claims.md` | 41/50 celdas indistinguibles en el score actual | Ampliar histórico/positivos antes de recalibrar | Ver tabla §7 |
| R-CIENT-MEGAEVENTO-01 | Aceptar | Equipo S.A.P.I. | Documentar como salvedad explícita en el artefacto | N/A | `megaevento_2024-02-03_report.json` (salvedad explícita en el manifest) | Riesgo de sobre-representar un evento catastrófico atípico | Incorporar más eventos históricos | Ver tabla §7 |
| R-CIENT-GENERALIZACION-01 | Aceptar | Equipo S.A.P.I. | Mantener el lenguaje de "ranking exploratorio", nunca "predicción" | N/A | `docs/arquitectura-hito1.md` (formulación central del sistema) | Capacidad predictiva generalizable sigue sin demostrarse | Criterio de éxito explícito para nivel 3 (ver `testing-evidencia-hito1.md` sección 19) | Ver tabla §7 |

**Nota sobre "mitigaciones VERIFICADA":** cada una cita un test PASS
concreto (parte de los 470/470 congelados) — nunca se marca VERIFICADA
sin un test, commit, reporte o comportamiento observable nombrado.

## 7. Seguimiento semanal

Usando la planificación S1-S6 como **expectativa**, no como prueba de
que ocurrió (mismo principio ya aplicado en `docs/trazabilidad-hito1.md`,
sección 13):

| Semana | Riesgo que debía revisarse | Evidencia realmente encontrada | Cambio verificable | Estado |
|---|---|---|---|---|
| 1-2 | Riesgos de ingesta inicial (NASA FIRMS, DMC) | Commits de corrección de endpoints (`8d53ae8` 30-08, DMC previo) | Corrección real de contrato de API | NOT_FOUND como revisión de riesgo formal — solo como commit de código |
| 3 | Riesgos de cobertura/testing inicial | Línea base de cobertura citada en `docs/matriz-riesgo.md` (63.21%, 86 tests) | Cifra existe, sin acta de revisión semanal | NOT_FOUND (revisión formal) / PARTIAL (evidencia técnica) |
| 4 | Riesgo de grilla/cobertura geográfica | Hallazgo R-GRILLA-01 documentado 05-09-2026 | Grilla reconstruida, tests de consistencia agregados | PARTIAL — hallazgo real, pero fuera de la ventana "semana 4" sin calendario que lo confirme |
| 5 | Riesgo de aceptación/usabilidad | `docs/acta-pruebas-aceptacion-usuario.md` (01-09-2026) | Hallazgo de usabilidad móvil confirmado y cerrado (05-09-2026) | PARTIAL — real, autoevaluación, no revisión de riesgo formal |
| 6 | Riesgo de integridad del pipeline temporal | Auditoría 06/07-09-2026 (regional_meteo, episodes, causality) | 6 defectos encontrados y corregidos (D-01..D-06) | PARTIAL — real y verificable, pero es una auditoría técnica puntual, no una revisión semanal programada |

No se fabricó ningún movimiento para las semanas sin evidencia — donde
no hay registro de una revisión de riesgo dedicada, se marca
explícitamente en vez de inferir que ocurrió porque hubo actividad de
código esa semana.

## 8. Relación con Testing y Atributos de Calidad

| Riesgo | Test/contrato relacionado | Atributo de calidad relacionado |
|---|---|---|
| R-METEO-POSICIONAL-01 | `test_regional_meteo*.py` | Integridad de datos (QA-02) |
| R-TARGET-OVERCOUNT-01 | `test_episode_evaluation.py` | Integridad de datos (QA-02) |
| R-MINCLASS-01 | `test_experiment_abcd_contract.py` | Fiabilidad (QA-01) |
| R-ALIGN-CELLID-01 | `test_prototype_service.py` | Fiabilidad (QA-01) |
| R-DEM-NAN-01 | `test_dem_features.py` | Robustez a datos faltantes (QA-04) |
| R-LEGACY-CONTAM-01 | `test_no_legacy_imports_in_prototype_modules`, `test_architecture.py` | Mantenibilidad (QA-03) |
| R-FRESCURA-01 | `test_prototype_freshness.py` | Usabilidad (QA-07) |
| R-HU-PIPELINE-01 | — | Auditabilidad/trazabilidad (QA-06) |
| R-MANTEN-01 | — | Mantenibilidad (QA-03) |
| R-PERF-SEC-01 | — | Rendimiento (QA-08), Seguridad (QA-09) |
| R-ACEPT-EXT-01 | — | Usabilidad (QA-07) |

No se modificaron `docs/testing-evidencia-hito1.md` ni
`docs/atributos-calidad-hito1.md` para construir esta tabla.

## 9. Alcance científico — riesgos preservados, no ocultos

Estos riesgos **no se consideran mitigados por la suite de tests** — los
470/470 verifican corrección técnica del código, no capacidad predictiva
ni validez científica (`docs/testing-evidencia-hito1.md`, sección 19):

- **Escasez de positivos / empates masivos:** 41/50 celdas comparten
  exactamente el mismo score en la corrida más reciente del prototipo.
- **Folds limitados:** el walk-forward de `experiment_abcd.py` cubre
  pocos años de histórico real con meteorología DMC.
- **Megaevento 2024-02-03:** un solo evento histórico concentra una
  fracción desproporcionada de las detecciones positivas del dataset.
- **FIRMS ≠ incendio confirmado:** una detección satelital es una
  detección satelital, no una confirmación en terreno.
- **Score no calibrado:** es un ranking relativo exploratorio, nunca una
  probabilidad de incendio.
- **No es una alerta oficial:** el prototipo no reemplaza a CONAF/SENAPRED.
- **Generalización no demostrada:** ningún experimento a la fecha
  cumple el criterio de "evidencia de capacidad predictiva" (nivel 3 de
  `docs/testing-evidencia-hito1.md`, sección 19).

## 10. Brechas de esta fase

1. Sin evidencia de revisión semanal de riesgos durante Sprint 1
   (`WEEKLY_RISK_UPDATE_EVIDENCE: NOT_FOUND`).
2. La escala de priorización numérica es una reconstrucción de cierre —
   no existía antes de esta fase.
3. `R-SPRINT-MGMT-01` no es recuperable retroactivamente (Sprint Goal,
   DoD, Sprint Review, snapshot inicial de SP).
4. `R-HU-PIPELINE-01` y `R-ACEPT-EXT-01` requieren acción de gestión real
   (Jira, sesión con evaluador externo) — no se resuelven documentando.
5. Los 4 riesgos científicos (sección 9) son limitaciones aceptadas del
   alcance actual, no defectos a corregir dentro de este Hito.

## 11. Tabla de control contable por estado actual

Extraída directamente de la columna "Estado actual" de la sección 5
(no del resumen narrativo de fases anteriores) — el estado del riesgo se
mantiene aquí distinto del estado de su mitigación (`PROPUESTA` /
`IMPLEMENTADA` / `VERIFICADA`, columna propia de la sección 6): un
riesgo puede estar en estado `MITIGADO` con una mitigación `VERIFICADA`,
pero "VERIFICADA" no es un estado del riesgo y no se cuenta como tal.

| Estado actual | Cantidad | IDs |
|---|---|---|
| MATERIALIZADO_Y_CORREGIDO | 7 | R-NASA-FIRMS-01, R-GRILLA-01, R-COBERTURA-01, R-METEO-POSICIONAL-01, R-TARGET-OVERCOUNT-01, R-BACKFILL-CONFLICTO-01, R-MINCLASS-01 |
| MITIGADO | 5 | R-DMC-01, R-ALIGN-CELLID-01, R-DEM-NAN-01, R-LEGACY-CONTAM-01, R-FRESCURA-01 |
| TRANSFERIDO_A_SPRINT_2 | 3 | R-CONAF-01, R-INTEGRACION-01, R-HU-PIPELINE-01 |
| ABIERTO | 3 | R-ETIQUETA-01, R-ACEPT-EXT-01, R-MANTEN-01 |
| NO_RESUELTO | 2 | R-SPRINT-MGMT-01, R-PERF-SEC-01 |
| ACEPTADO | 3 | R-CIENT-POSITIVOS-01, R-CIENT-MEGAEVENTO-01, R-CIENT-GENERALIZACION-01 |
| **TOTAL** | **23** | — |

**Verificación:** `UNIQUE_RISK_IDS = 23`, `DUPLICATE_RISK_IDS = 0`
(los 23 ID de la sección 5 son todos distintos, confirmado por
recuento directo), `UNCLASSIFIED_RISKS = 0` (las 23 filas tienen un
estado actual asignado), `TOTAL_BY_STATUS = 7+5+3+3+2+3 = 23`.

**Corrección respecto al resumen entregado en la fase anterior:** ese
resumen agrupó erróneamente `ABIERTO` y `NO_RESUELTO` bajo una única
etiqueta `OPEN = 3` y reportó `MITIGATED = 2` en vez de 5 — ambos
errores de conteo del resumen narrativo, no del contenido de las 23
filas (que no cambió). Esta tabla de control corrige el conteo, no el
contenido.

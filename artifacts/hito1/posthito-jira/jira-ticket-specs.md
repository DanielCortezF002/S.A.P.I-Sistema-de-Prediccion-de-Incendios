# Especificación de tickets Jira — vinculación posterior al Hito 1

**Fecha de creación de este documento:** 09-09-2026. **Estado de los tickets
descritos aquí: NO CREADOS EN JIRA TODAVÍA** — este entorno no tiene acceso
ni credenciales a ninguna instancia Jira (se verificó explícitamente: no
existe herramienta/MCP/CLI de Jira disponible en esta sesión). Este archivo
y el CSV que lo acompaña (`jira-import-pipeline-temporal.csv`) son el
**paquete listo para creación manual o import**, no un registro de tickets
reales existentes.

## Regla histórica — léase antes de crear nada en Jira

Al crear estos tickets en Jira, respetar exactamente:

- **Fecha de creación:** la fecha real en que se creen (09-09-2026 o
  posterior) — **nunca** una fecha de Sprint 1 (03-08 a 31-08-2026).
- **Sprint/Backlog destino:** Product Backlog actual o Sprint 2 — **nunca**
  Sprint 1.
- **Estado inicial:** `TO DO` / `POR HACER` (o el estado equivalente de
  entrada del backlog actual) — **no** `Done`/`Finalizado`, aunque la
  funcionalidad técnica ya exista y esté verificada. El estado de un ticket
  Jira refleja el proceso de aceptación formal (revisión de producto,
  Definition of Ready/Done aplicada), no si el código ya corre.
- **Descripción:** debe incluir la nota "implementation evidence already
  exists" (ver plantilla abajo) — nunca debe leerse como si el ticket
  hubiera guiado el desarrollo ya hecho.
- Esto **no repara** la ausencia histórica de Sprint Goal, DoD ni Sprint
  Review de Sprint 1 (`docs/cierre-sprint1-hito1.md`,
  `HISTORICAL_DOD: NOT_FOUND`) — son brechas de gestión de ese sprint que
  no se resuelven creando tickets ahora, y así se documenta explícitamente
  en el informe de esta acción.

---

## Auditoría de REQ-10..16 (previa al diseño de HU)

| REQ | Necesidad funcional/técnica | Usuario beneficiado | Módulos | AC-T existentes | Tests | Escenarios 4+1 | ¿HU Jira real? |
|---|---|---|---|---|---|---|---|
| REQ-10 | Meteorología DMC tratada como regional, nunca reetiquetada por celda | Analista (confía en el origen del dato) | `regional_meteo.py` | AC-T02 | `test_regional_meteo.py`, `test_regional_meteo_loading.py` | S5 | NO |
| REQ-11 | Features temporales con causalidad estricta (`<= T`) | Analista (confía en que no hay fuga de información futura) | `causality_validator.py`, `temporal_features.py` | AC-T03 | `test_causality_validator.py`, `test_temporal_features.py` | S5, S7 | NO |
| REQ-12 | Target futuro honesto: ventana `(T,T+h]`, cooldown excluido (nunca 0) | Analista / científico de datos | `target_builder.py` | AC-T04 | `test_target_builder.py` | S5 | NO |
| REQ-13 | Prototipo aislado del pipeline legacy/demo | Analista (confía en que el ranking no mezcla datos sintéticos) | `prototype_service.py`, `pipeline_validators.py`, `shared_thresholds.py` | AC-T01/T10 | `test_no_legacy_imports_in_prototype_modules`, `test_frontend_data_contract_compliance`, `test_temporal_pipeline_has_no_transitive_legacy_dependency` | (transversal) | NO |
| REQ-14 | Ranking relativo de riesgo por celda a partir de información real | Analista | `prototype_service.py` | AC-T05/T06/T07 | `test_prototype_service.py` (inferencia/ranking) | S1, S6 | NO |
| REQ-15 | Dato topográfico faltante representado como N/D, nunca 0 | Analista | `dem_features.py`, `prototype_view.py::_fmt_nd` | AC-T08 | `test_dem_features.py` (datos); **sin test de UI (`_fmt_nd`)** | S8 | NO |
| REQ-16 | Dashboard ensambla sin excepción fatal, modo Prototipo por defecto | Analista | `app/app.py` | AC-T09 | `test_app_integration.py` | S3 | NO |

**Todos sin HU Jira real** — consistente con `docs/trazabilidad-hito1.md`
(congelado), que ya marcaba REQ-10..16 como "PENDIENTE DE VINCULAR EN FASE
DE TRAZABILIDAD".

---

## Diseño de agrupación (por qué 3 HU, no 7)

Se descartó "una HU por REQ" porque varios REQ no son necesidades de
usuario independientes sino **restricciones técnicas que habilitan una
misma capacidad observable**. La agrupación sigue el acoplamiento real del
código, no una decisión arbitraria:

- **REQ-10, REQ-11, REQ-12** se resuelven en un único artefacto
  (`scripts/build_temporal_dataset.py`) y ninguno tiene sentido de
  producto por separado — "meteorología regional" sin "causalidad ≤T" ni
  "target honesto" no es una entrega útil aislada; las tres constituyen,
  juntas, la integridad del dataset que hace confiable el entrenamiento.
- **REQ-13 y REQ-14** son ambas propiedades de `score_current_grid()`
  observables por el analista como una sola cosa: "un ranking en el que
  puedo confiar". El aislamiento (REQ-13) no es visible al usuario por sí
  mismo — solo importa porque es la condición que hace verdadero el REQ-14.
- **REQ-15 y REQ-16** son ambas propiedades de robustez/honestidad de la
  capa de presentación (`app/`, `prototype_view.py`): que la app cargue sin
  romperse y que nunca disfrace un dato faltante como un valor real.

Se evaluó la hipótesis de 3 HU (A/B/C) planteada como punto de partida y
se confirmó independientemente contra el código real — no se adoptó sin
verificar el acoplamiento.

---

## HU-A — Integridad causal del dataset temporal

- **Tipo Jira recomendado:** Historia (Story) — técnica/científica.
- **Historia:**
  > Como **desarrollador/científico de datos del pipeline temporal**,
  > quiero que el dataset de entrenamiento use únicamente meteorología
  > regional real, features con causalidad estricta (`<= T`) y una
  > definición honesta del target futuro (ventana `(T, T+h]`, cooldown
  > excluido), para poder entrenar y confiar en un modelo sin fugas de
  > información ni datos inventados.
- **Valor:** sin esto, cualquier métrica de desempeño del modelo sería
  metodológicamente inválida (leakage) o engañosa (meteorología
  disfrazada de multi-estación). Es la base de confianza científica de
  todo lo que el analista ve después.
- **REQ cubiertos:** REQ-10, REQ-11, REQ-12.
- **Escenarios 4+1:** S5 (construir dataset temporal), S7 (detectar
  violación de causalidad).
- **Dependencias:** ninguna (es la base del pipeline; otras HU dependen de
  esta).
- **Restricciones:** no debe alterar `models/prototype_model_d.pkl` ya
  publicado ni la metodología congelada (Modelo D fijo, no auto-tuning).
- **Supuestos:** la fuente DMC 330007 sigue siendo la única estación
  meteorológica disponible para el corredor (documentado, no se espera
  que cambie a corto plazo).
- **Riesgos:** si se agregan nuevas estaciones DMC en el futuro, esta HU
  debería revisarse (hoy asume 1 sola estación por diseño, ver ADR-01 en
  `docs/architecture-4plus1-hito1.md`).
- **Definition of Ready actual:** descripción y CA listos (este
  documento); estimación PENDIENTE; sin refinamiento formal en equipo
  todavía → **DoR: PARCIAL**.
- **Prioridad:** Media — funcionalidad ya implementada y verificada, el
  valor de este ticket es formalizar la trazabilidad, no nuevo desarrollo.
- **Estimación:** **ESTIMACIÓN PENDIENTE DE REFINAMIENTO** (no existe una
  sesión real de planning poker para trabajo ya construido; asignar SP
  ahora sería inventar una cifra sin proceso real detrás).
- **Sprint objetivo:** Product Backlog actual / Sprint 2.
- **Labels:** `post-hito1`, `traceability`, `temporal-pipeline`, `sprint2`.
- **Tests/evidencia existente:** `tests/test_causality_validator.py`,
  `tests/test_target_builder.py`, `tests/test_regional_meteo.py`,
  `tests/test_regional_meteo_loading.py`, `tests/test_temporal_features.py`
  — todos PASS (suite completa 479 passed, 09-09-2026).

### Criterios de aceptación actuales (HU-A)

- **CA-A1 (Given/When/Then):** Dado un dataset temporal construido con
  `build_temporal_dataset.py`, cuando se ejecuta
  `validate_temporal_causality()`, entonces ningún feature usa un
  `timestamp` posterior a `T`. *Evidencia:* `test_causality_validator.py`
  (PASS).
- **CA-A2:** Dado el target de una fila con instante `T`, cuando se
  construye con `build_targets()`, entonces la ventana es `(T, T+6h]`
  excluyendo el cooldown — nunca incluye `T` mismo. *Evidencia:*
  `test_target_builder.py` (PASS).
- **CA-A3:** Dada la serie meteorológica de la estación 330007, cuando se
  aplica a las 50 celdas para un mismo instante, entonces se usa la MISMA
  observación regional para todas — nunca se reetiqueta como 50 mediciones
  distintas. *Evidencia:*
  `test_regional_meteo.py::test_regla_30_30_30_uses_the_same_observation`
  (PASS).

**Distinción explícita:** estos CA son criterios **actuales** (redactados
09-09-2026). Los `AC-T02`, `AC-T03`, `AC-T04` de
`artifacts/hito1/testing/acceptance-checks.txt` son **evidencia técnica de
verificación de cierre** (07-09-2026) — se reutilizan aquí como evidencia,
no se renombran como si hubieran sido el CA original de una HU histórica
(que no existió).

**Trazabilidad:** HU-A → CA-A1/A2/A3 → REQ-10/11/12 → 4 módulos → 5
archivos de test → PASS → evidencia citada arriba → escenarios S5, S7.
**Estado: COMPLETE** (los 3 CA tienen test real que pasa).

---

## HU-B — Ranking de riesgo confiable y aislado de datos sintéticos

- **Tipo Jira recomendado:** Historia (Story) — funcional.
- **Historia:**
  > Como **analista que usa el prototipo para priorizar celdas**, quiero
  > recibir un ranking de riesgo de las 50 celdas construido
  > exclusivamente con datos reales y aislado de cualquier dato
  > sintético/demo o del pipeline legacy, para poder usar esa priorización
  > sin dudar de su origen.
- **Valor:** la utilidad central del prototipo — sin esta garantía, el
  analista no podría distinguir un ranking real de un artefacto de datos
  de demostración.
- **REQ cubiertos:** REQ-13, REQ-14.
- **Escenarios 4+1:** S1 (ejecutar inferencia y priorizar 50 celdas), S6
  (entrenar/verificar Modelo D).
- **Dependencias:** HU-A (el ranking depende de que el dataset de
  entrenamiento sea íntegro).
- **Restricciones:** no cambiar `random_state=42`, `max_depth=4`,
  `class_weight="balanced"` del Modelo D (congelados).
- **Supuestos:** el modo Demo (`app/utils/demo_seed.py`) sigue existiendo
  como ruta separada, seleccionable explícitamente, no como default.
- **Riesgos:** si en el futuro se agrega una nueva fuente de features al
  pipeline temporal, debe auditarse su árbol transitivo de imports (ver
  el hallazgo `regional_meteo → features` en
  `docs/architecture-4plus1-hito1.md` sección 8) para no reintroducir un
  acoplamiento legacy oculto.
- **Definition of Ready actual:** igual que HU-A → **DoR: PARCIAL**.
- **Prioridad:** Media.
- **Estimación:** **ESTIMACIÓN PENDIENTE DE REFINAMIENTO**.
- **Sprint objetivo:** Product Backlog actual / Sprint 2.
- **Labels:** `post-hito1`, `traceability`, `temporal-pipeline`, `sprint2`.
- **Tests/evidencia existente:**
  `tests/test_prototype_service.py::test_no_legacy_imports_in_prototype_modules`,
  `tests/test_architecture.py::test_frontend_data_contract_compliance`,
  `tests/test_architecture.py::test_temporal_pipeline_has_no_transitive_legacy_dependency`,
  `test_ties_share_display_rank_but_internal_rank_stays_unique`,
  `test_inference_returns_fifty_cells`, `test_ranks_are_one_to_n` — todos
  PASS.

### Criterios de aceptación actuales (HU-B)

- **CA-B1:** Dado que se ejecuta `score_current_grid()` en modo
  Prototipo, cuando se audita su árbol transitivo real de imports,
  entonces no aparece ningún módulo de `src.modelo`,
  `src.procesamiento.features` ni `imblearn`. *Evidencia:*
  `test_temporal_pipeline_has_no_transitive_legacy_dependency` (PASS,
  nuevo 09-09-2026).
- **CA-B2:** Dado un conjunto de scores con empates, cuando se construye
  el ranking, entonces se expone `rank`/`display_rank`/`tie_group_size` —
  nunca un número tipo "probabilidad calibrada". *Evidencia:*
  `test_ties_share_display_rank_but_internal_rank_stays_unique` (PASS).
- **CA-B3:** Dado el código de `app/`, cuando se analiza estáticamente,
  entonces ningún archivo importa `src.ingesta`/`procesamiento`/`modelo`/`pipeline`
  directamente. *Evidencia:* `test_frontend_data_contract_compliance`
  (PASS).

**Trazabilidad:** HU-B → CA-B1/B2/B3 → REQ-13/14 → 3 módulos → 6 archivos
de test → PASS → escenarios S1, S6. **Estado: COMPLETE**.

---

## HU-C — Presentación robusta y honesta de la información por celda

- **Tipo Jira recomendado:** Historia (Story) — funcional/no funcional.
- **Historia:**
  > Como **analista que consulta el dashboard**, quiero que la aplicación
  > cargue siempre sin errores fatales y que cualquier dato topográfico
  > faltante se muestre honestamente como "N/D" (nunca como un valor
  > inventado), para poder confiar en lo que veo incluso cuando hay datos
  > incompletos.
- **Valor:** confianza en la interfaz — un dato faltante disfrazado de
  cero podría llevar a una lectura errónea del riesgo real de una celda.
- **REQ cubiertos:** REQ-15, REQ-16.
- **Escenarios 4+1:** S3 (detectar meteorología desactualizada — mismo
  principio de honestidad de presentación), S8 (manejar DEM faltante como
  N/D).
- **Dependencias:** HU-B (solo tiene sentido presentar un ranking que ya
  es confiable).
- **Restricciones:** ninguna sobre Modelo D.
- **Supuestos:** la cobertura del raster DEM seguirá siendo parcial para
  algunas celdas (no se espera un DEM 100% completo a corto plazo).
- **Riesgos:** **gap real identificado** — `_fmt_nd()` (la función que
  renderiza "N/D" en la UI) no tiene test dedicado; solo el dato
  subyacente (`NaN` en vez de `0`) está testeado. Riesgo de regresión
  silenciosa en la capa de presentación.
- **Definition of Ready actual:** descripción y CA listos, pero con un CA
  explícitamente marcado PARTIAL (ver abajo) → **DoR: PARCIAL, con deuda
  técnica identificada**.
- **Prioridad:** **Alta relativa** dentro de este lote — es la única de
  las 3 HU con un gap de test real y conocido, no solo de formalización.
- **Estimación:** **ESTIMACIÓN PENDIENTE DE REFINAMIENTO** (la
  formalización no tiene SP; si se decide cerrar el gap de test de
  `_fmt_nd`, ESO sí sería trabajo nuevo estimable — pero sería una
  sub-tarea, a decidir en refinamiento).
- **Sprint objetivo:** Product Backlog actual / Sprint 2.
- **Labels:** `post-hito1`, `traceability`, `temporal-pipeline`, `sprint2`,
  `tech-debt` (por el gap de `_fmt_nd`).
- **Tests/evidencia existente:** `tests/test_app_integration.py`,
  `tests/test_dem_features.py`, `tests/test_prototype_freshness.py`.

### Criterios de aceptación actuales (HU-C)

- **CA-C1:** Dado que la app se inicia en modo Prototipo (default), cuando
  se ejecuta, entonces no lanza ninguna excepción fatal. *Evidencia:*
  `test_main_runs_without_exceptions`,
  `test_prototype_mode_is_the_default_and_runs_without_exceptions` (PASS).
- **CA-C2:** Dado que una celda no tiene cobertura del raster DEM, cuando
  se calcula su topografía, entonces el valor queda `NaN` — nunca `0`.
  *Evidencia:* `tests/test_dem_features.py` (PASS).
- **CA-C3 — PARTIAL:** Dado un valor topográfico `NaN`, cuando se
  renderiza en el panel de detalle (`prototype_view.py::_fmt_nd`),
  entonces debería mostrarse "N/D". **Sin test dedicado a esta ruta de
  UI** — brecha ya señalada en `docs/trazabilidad-hito1.md` y en
  `docs/architecture-4plus1-hito1.md` sección 5 (escenario S8). No se
  cierra en esta acción (fuera de alcance — es de gestión/trazabilidad, no
  de código).
- **CA-C4:** Dado que la última lectura DMC es >24h anterior a
  `forecast_time`, cuando se clasifica la frescura, entonces se muestra
  explícitamente como "HISTÓRICO" — nunca disfrazada de reciente.
  *Evidencia:* `tests/test_prototype_freshness.py` (PASS).

**Trazabilidad:** HU-C → CA-C1/C2/C3/C4 → REQ-15/16 → 3 módulos → 3
archivos de test → CA-C1/C2/C4 PASS, CA-C3 sin test → escenarios S3, S8.
**Estado: PARTIAL** (3/4 CA con test real; 1/4 con gap conocido).

---

## Resumen de trazabilidad (números exactos)

| | Cadena completa (HU→CA→REQ→módulo→test→evidencia→escenario) |
|---|---|
| HU-A | **COMPLETE** (3/3 CA con test PASS) |
| HU-B | **COMPLETE** (3/3 CA con test PASS) |
| HU-C | **PARTIAL** (3/4 CA con test PASS; 1/4 sin test dedicado — `_fmt_nd`) |

**Escenarios 4+1 vinculados a una HU real (post creación en Jira):**
S1, S3, S5, S6, S7, S8 = **6/8 escenarios**, más la fila transversal de
aislamiento legacy (REQ-13) = **7/9 filas** de la matriz de
`docs/architecture-4plus1-hito1.md` sección 6. **S2** (detalle/trazabilidad
de celda) y **S4** (reproducir offline) permanecen sin REQ ni HU — no
porque se hayan omitido aquí, sino porque nunca estuvieron vinculados a
REQ-10..16 en `docs/trazabilidad-hito1.md` (S2 no tiene REQ asignado; S4 es
un requisito de la auditoría de reproducibilidad, no del backlog de
producto).

---

## Instrucciones de creación manual (máximo 5 minutos)

1. Abrir el proyecto Jira **SAPI** (mismo proyecto de SAPI-26..48, ver
   `artifacts/hito1/versioning/git-jira-links.txt`).
2. Backlog → **Crear ticket** (tipo Historia) — repetir 3 veces (HU-A,
   HU-B, HU-C).
3. Copiar `Summary`, `Description`, `Priority`, `Labels` desde
   `jira-import-pipeline-temporal.csv` (o importar el CSV directamente vía
   Jira → Backlog → Import issues from CSV).
4. **NO** completar `Story Points` todavía — dejar vacío hasta
   refinamiento real en equipo.
5. **NO** mover a Sprint 1 — dejar en Product Backlog o asignar a Sprint 2
   si ya existe esa iteración.
6. Estado inicial: `TO DO` / `POR HACER`.
7. Volver aquí con las 3 keys reales (ej. `SAPI-52`, `SAPI-53`, `SAPI-54`)
   para que se actualice `docs/architecture-4plus1-hito1.md` (sección 6) y
   se cree `docs/trazabilidad-current.md` con los links reales.

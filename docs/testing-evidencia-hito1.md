# Testing, aceptación y evidencia trazable — Sprint 1 / Hito 1

**Estado:** documento de trabajo, fase exclusivamente de auditoría/
ejecución/recolección — no incluye riesgos, atributos de calidad,
versionamiento ni retrospectiva (fases separadas). Arquitectura de
referencia: `docs/arquitectura-hito1.md` (CONGELADA, no modificada en
esta fase). Fecha de esta fase: **07-09-2026**.

**Principio de honestidad temporal:** toda evidencia reconstruida en esta
fase (protocolos, checklists, tablas) que no proviene de un registro
fechado real se marca explícitamente **RECONSTRUCCIÓN RETROSPECTIVA DE
CIERRE — 07/09/2026** o **CRITERIO TÉCNICO DE VERIFICACIÓN DEL CIERRE —
07/09/2026**. Ningún timestamp de ejecución, commit o archivo se alteró
para esta fase.

---

## 1. Objetivo y alcance

Auditar, ejecutar, recolectar, clasificar, trazar y documentar la
evidencia de testing/aceptación disponible para el Hito 1, sin modificar
`src/`, `app/`, `tests/`, `data/`, `docs/arquitectura-hito1.md` ni Jira,
sin crear tests nuevos y sin corregir bugs. El objetivo no es reportar
"470 tests passed" como conclusión — es mostrar **qué** se probó, **por
qué**, **contra qué criterio** y **con qué resultado**, distinguiendo
siempre cobertura de código de cobertura de HU/CA.

## 2. Relación con las rúbricas y syllabus

El syllabus (INSW421, ver `docs/informe-1-seminario-licenciatura.md`)
ubica el Hito 1 en **AE1 / IL 1.1–1.4**. Las rúbricas específicas de
Hito 1 y Sprint 1 exigen adicionalmente evidencia técnica de testing,
aceptación, trazabilidad y gestión del Sprint — ver el mapeo completo en
`artifacts/hito1/testing/rubric-testing-map.md`. Esta fase **no** afirma
estar evaluando formalmente AE3.

**Nota sobre pruebas de carga (AE3):** el repositorio contiene un script
real de prueba de carga (`locustfile.py`, "Prueba de carga CP-01" sobre
el dashboard Streamlit), pero no se encontró evidencia de una ejecución
capturada (sin reporte/CSV de Locust en `reports/`). No se fabricó una
prueba de carga nueva para esta fase ni se ejecutó el script existente
— queda documentado como lo que es (un artefacto real sin evidencia de
ejecución) y fuera del alcance de esta fase, que es AE1/IL1.1–1.4.

## 3. Estrategia de pruebas

La estrategia real observada en el repositorio combina:

- **Pruebas unitarias** deterministas sobre funciones puras del pipeline
  temporal (causalidad, target, lags, grilla).
- **Pruebas de integración** sobre I/O real (filesystem, rasters, APIs
  mockeadas) y sobre el ensamblado de la app Streamlit (`AppTest`).
- **Contratos/regresión** que blindan invariantes arquitectónicos (p. ej.
  que `app/` no importe módulos analíticos, que los feature-sets A/B/C/D
  no se mezclen).
- **Integridad de datos** y **causalidad/anti-leakage**, categoría propia
  dado que es el riesgo metodológico central del pipeline temporal (ver
  `docs/arquitectura-hito1.md`, decisión "Joins temporales causales/as-of-T").
- Ausencia de una **suite de aceptación automatizada formal** distinta de
  los tests técnicos — ver sección 12.

No existe, hoy, un documento de "plan de pruebas" único y separado del
propio código de test — la estrategia se infiere de la organización real
de `tests/` (ver inventario completo en
`artifacts/hito1/testing/test-inventory.txt`).

## 4. Entorno y versión evaluada

Ver `artifacts/hito1/testing/environment.txt` y
`artifacts/hito1/testing/git-state.txt` (íntegros, sin editar).

| Campo | Valor |
|---|---|
| Python | 3.14.6 |
| pytest | 9.1.1 (pytest-cov 7.1.0, coverage 7.16.0 ya instalados — no se instaló nada nuevo) |
| Commit evaluado (`git rev-parse HEAD`) | `9f076172adca3dbce0285f5d942d2803ac6f68a4` |
| Rama | `main` |
| `git status --short` al iniciar | `?? .claude/`, `?? artifacts/`, `?? docs/arquitectura-hito1.md`, `?? tools/` (trabajo de fases previas de este Hito, no commiteado — no se exige un repo limpio, ver instrucción de esta fase) |
| `git diff -- src app tests data` ANTES de esta fase | vacío |
| `git diff -- src app tests data` DESPUÉS de esta fase | vacío (ver `git-state.txt`, sección final) |

**TEST_CODE_MODIFIED: NO · APPLICATION_CODE_MODIFIED: NO · DATA_MODIFIED: NO**
— verificado por `git diff`, no solo afirmado.

## 5. Inventario de pruebas

58 archivos en `tests/` + `conftest.py` (sin tests propios), más 4
scripts `test_*.py` en la raíz que **no** se ejecutan en la suite
estándar (fuera de `testpaths = tests` en `pytest.ini`; son scripts
manuales que requieren PostGIS/API reales, sin `assert`). Inventario
completo, archivo por archivo, con propósito/componente/categoría/tipo
de evidencia: **`artifacts/hito1/testing/test-inventory.txt`** (no se
repite aquí para no inflar este documento).

Categorías principales usadas (no exhaustivas ni mutuamente excluyentes
al 100%, pero sí la clasificación primaria de cada archivo):
CAUSALIDAD/ANTI-LEAKAGE · INTEGRIDAD DE DATOS · INTEGRACIÓN ·
CONTRATOS/REGRESIÓN · PROTOTIPO/INFERENCIA · UI/STREAMLIT · MODELO ML
(legacy) · UNITARIA/CONFIGURACIÓN.

## 6. Ejecución de la suite

Comando ejecutado (una sola corrida completa, sin coverage para no mezclar
el fallo de un gate de cobertura con el resultado funcional):

```
python -m pytest -q --no-cov -rs --junitxml=artifacts/hito1/testing/pytest-junit.xml
```

Salida completa: `artifacts/hito1/testing/pytest-full.txt`. JUnit:
`artifacts/hito1/testing/pytest-junit.xml`.

| Métrica | Valor (ejecución fresca, 07-09-2026) |
|---|---|
| collected | 470 |
| passed | 470 |
| failed | 0 |
| skipped | 0 |
| xfailed | 0 |
| xpassed | 0 |
| errors | 0 |
| duración | 297.97 s (0:04:57) |

No se asumió que seguían siendo 470 — es el resultado real de esta
corrida (coincide con el número reportado en fases previas de este
mismo Hito, pero se verificó de nuevo, no se copió). La suite no falló
— no aplica el punto "si falla, no corregir y registrar el fallo".

Cobertura de código (pytest-cov ya estaba instalado, se corrió una
medición fresca aparte, ver `artifacts/hito1/testing/coverage-summary.txt`):
**TOTAL 91.72%** sobre `app`+`src` (gate configurado en `pytest.ini`:
80%, superado). Módulos con cobertura baja notable, todos del pipeline
**legacy**: `src/procesamiento/persister.py` (0%, PostGIS sin usar en el
prototipo), `src/modelo/inference_engine.py` (48%), `src/procesamiento/row_explainer.py`
(42%), `src/procesamiento/spatial_joiner.py` (61%).

**Advertencia metodológica explícita (no me pertenece silenciar esto):**
el 91.72% es cobertura de **líneas de código**, no de HU/CA — ver
sección 17.

## 7. Pruebas unitarias

Ejemplos representativos leídos directamente (no solo contados por
nombre): `tests/test_causality_validator.py` (10 tests sobre
`validate_temporal_causality` — el "test de no futuro"),
`tests/test_target_builder.py` (12 tests sobre la definición exacta de
`target(cell,T,h)`), `tests/test_temporal_features.py` (5 tests sobre
lags reales vs. filas más cercanas), `tests/test_grid_assign_cell.py`
(4 tests de geometría pura). Todas deterministas, sin I/O externo real,
todas PASS. Detalle completo por archivo en `test-inventory.txt`.

## 8. Pruebas de integración

Incluyen I/O real: `tests/test_backfill_dmc_historico.py` (filesystem +
API mockeada, idempotencia y detección de conflicto),
`tests/test_dem_features.py`/`test_dem_terrain.py` (rasters reales vía
`rasterio` sobre `tmp_path`), `tests/test_temporal_dataset_integration.py`
(condicional a que exista el artefacto real `temporal_dataset_h6.parquet`
— 9 tests sobre unicidad de clave, exclusión honesta, no-imputación,
walk-forward sin fuga de episodios), `tests/test_app_integration.py`
(`AppTest` real de Streamlit, sin mocks del pipeline — es también el
smoke test, ver sección 10). Todas PASS en esta corrida.

## 9. Contratos, regresión, integridad y causalidad

- **Contrato de arquitectura:** `tests/test_architecture.py` (AST
  estático: `app/` no puede importar `src.ingesta`/`procesamiento`/
  `modelo`/`pipeline` directamente) — PASS.
- **Contrato de no-fuga entre A/B/C/D:** `tests/test_experiment_abcd_contract.py`
  (13 tests) — incluye `test_no_model_contains_cell_id_or_synthetic_features`
  (confirma que `cell_id` nunca es predictor, ver `docs/arquitectura-hito1.md`
  sección "Modelo lógico de datos") y `test_run_fold_handles_a_train_set_with_only_one_positive_without_crashing`
  (guarda de regresión de D-04, ver `defect-evidence.md`) — todos PASS.
- **Integridad de datos:** `tests/test_pipeline_validators.py` (20
  tests), `tests/test_nan_journey_real_data.py` (traza NaN real contra
  el dataset real, no sintético) — PASS.
- **Causalidad/anti-leakage:** ver sección 7 — es la categoría con más
  tests dedicados específicamente a un solo riesgo metodológico
  (`feature_timestamp <= T`), consistente con que es el riesgo que
  `docs/arquitectura-hito1.md` marca como decisión arquitectónica
  explícita.

## 10. Prototipo y Streamlit

`tests/test_prototype_service.py` (14 tests) y
`tests/test_prototype_freshness.py` (8 tests) cubren directamente
`score_current_grid()`: 50 celdas únicas, ranking con empates honestos,
alineación `cell_id`↔score robusta a reordenamiento, ausencia de
timestamps futuros, fallo explícito ante `forecast_time` futuro,
clasificación de frescura. Todos PASS.

**Smoke/integración del incremento desplegado (instrucción 10):** el
mecanismo real ya existente es `tests/test_app_integration.py` —
usa `streamlit.testing.v1.AppTest` para ensamblar `app/app.py::main()`
de punta a punta, sin mocks del pipeline. Se ejecutó de forma aislada y
fresca (comando y salida completa en
`artifacts/hito1/testing/streamlit-smoke.txt`):

```
5 passed, 1029 warnings in 14.18s
```

Verifica exactamente lo pedido: `app/app.py` se ensambla, no hay
excepción fatal, el modo Prototipo es el default y corre, y
`prototype_service` participa de la ruta real (no un mock).

**Diferenciación explícita (instrucción 10):**

- **Test automatizado:** `tests/test_app_integration.py` (lo anterior).
- **Smoke técnico manual:** no se ejecutó `streamlit run app/app.py`
  manualmente en esta fase — el `AppTest` ya cubre el mismo camino de
  ensamblado sin necesitar un servidor real corriendo.
- **Validación humana:** ninguna en esta fase — ver sección 14 para la
  diferencia con aceptación real de usuario.

**STREAMLIT_SMOKE: PASS.**

## 11. HU → CA → prueba → resultado → evidencia

### 11.1 HUs históricas (Jira SAPI-*, pipeline legacy/demo)

Ya existe una matriz real y fechada para estas HU:
`docs/matriz-trazabilidad-hu-test.md` (última actualización 05-09-2026,
**no modificada en esta fase** — solo referenciada). Resumen sin
duplicar el detalle completo:

| HU / Issue | Estado (según la matriz existente) | Brecha registrada allí |
|---|---|---|
| SAPI-26 (histórico FIRMS) | Cerrado (lado NASA) | CONAF sin fuente real |
| SAPI-28 (telemetría DMC + ignición) | Parcial | `out_of_tolerance` no observado en corrida real |
| SAPI-30 (topografía DEM) | Post-hito (**desactualizado** — ver nota abajo) | Sin DEM ni rasterio al momento de esa matriz |
| SAPI-32 (limpieza/normalización) | Parcial | Integración join→riesgo pendiente (R-INTEGRACION-01) |
| SAPI-44 (separación demo/real) | Cerrado | Badge declara fuente, no pipeline ETL completo |
| SAPI-45 (imports/tests estables) | Cerrado | Gate 80% alcanzado (80.34% al 31-08-2026; 91.72% en esta fase) |
| SAPI-47 (matriz de riesgo) | Cerrado | — |
| SAPI-48 (esta misma matriz) | Cerrado | — |

**Nota de actualización honesta:** la fila SAPI-30 de la matriz existente
dice "Sin DEM ni `rasterio`" porque fue escrita el 05-09-2026, ANTES de
que `src/procesamiento/dem_features.py`/`dem_terrain.py` y sus tests
existieran (ver `git log`: esos módulos ya estaban antes, pero la
integración real con el prototipo es del 06/07-09-2026). Esta fase NO
edita esa matriz (fuera de alcance) — deja constancia aquí de que está
desactualizada respecto al estado real de DEM, y que su actualización
formal corresponde a la fase de Trazabilidad.

### 11.2 Componentes del pipeline temporal (sin HU/Jira identificado)

Estos componentes (`regional_meteo`, `episodes`, `target_builder`,
`causality_validator`, `temporal_features`, `experiment_abcd`, Modelo D,
`prototype_service`) no tienen un ticket SAPI-* verificado en la
reconciliación de Jira disponible para este proyecto. Se documentan con
**HU/Issue = PENDIENTE DE VINCULAR EN FASE DE TRAZABILIDAD** — nunca con
un ID inventado.

| HU/Issue | CA | Tipo de CA | Prueba | Tipo de prueba | Resultado | Evidencia | Estado metodológico | Brecha |
|---|---|---|---|---|---|---|---|---|
| PENDIENTE DE VINCULAR | AC-T02 — DMC regional, nunca por celda | Criterio técnico de cierre | `test_regional_meteo*.py` | Integración | PASS | `pytest-full.txt` | CUBIERTA | Sin HU Jira vinculada |
| PENDIENTE DE VINCULAR | AC-T03 — features `<= T` | Criterio técnico de cierre | `test_causality_validator.py`, `test_temporal_features.py` | Unitaria | PASS | `pytest-full.txt` | CUBIERTA | Sin HU Jira vinculada |
| PENDIENTE DE VINCULAR | AC-T04 — target `(T,T+6h]`, cooldown | Criterio técnico de cierre | `test_target_builder.py` | Unitaria | PASS | `pytest-full.txt` | CUBIERTA | Sin HU Jira vinculada |
| PENDIENTE DE VINCULAR | AC-T01/T10 — aislamiento legacy/demo | Criterio técnico de cierre | `test_prototype_service.py::test_no_legacy_imports_in_prototype_modules`, `test_architecture.py` | Contrato/regresión | PASS | `pytest-full.txt` | CUBIERTA | Sin HU Jira vinculada |
| PENDIENTE DE VINCULAR | AC-T05/T06/T07 — 50 celdas, empates, alineación | Criterio técnico de cierre | `test_prototype_service.py` (varios) | Unitaria/integración | PASS | `pytest-full.txt` | CUBIERTA | Sin HU Jira vinculada |
| PENDIENTE DE VINCULAR | AC-T08 — DEM NaN, nunca 0 | Criterio técnico de cierre | `test_dem_features.py` | Integración | PASS (capa datos) / sin test dedicado (capa UI) | `pytest-full.txt` | PARCIAL | UI (`_fmt_nd`) sin test dedicado |
| PENDIENTE DE VINCULAR | AC-T09 — app carga sin excepción fatal | Criterio técnico de cierre | `test_app_integration.py` | Integración (AppTest) | PASS | `streamlit-smoke.txt` | CUBIERTA | Sin HU Jira vinculada |

Detalle completo de cada AC-T en `artifacts/hito1/testing/acceptance-checks.txt`.

## 12. Criterios de aceptación del incremento

Ver `artifacts/hito1/testing/acceptance-checks.txt` (los 10 candidatos
AC-T01..AC-T10, verificados uno por uno contra test/código real — no
asumidos). 9/10 en PASS completo, 1/10 (AC-T08) PASS en la capa de
datos con una brecha menor documentada en la capa de UI.

Diferenciación exigida por la instrucción de esta fase:

- **A. Aceptación automatizada existente:** los tests técnicos citados
  arriba — no hay una suite de "aceptación" formalmente separada y
  etiquetada como tal en `tests/`.
- **B. Verificación técnica del incremento:** exactamente lo que este
  documento y `acceptance-checks.txt` hacen.
- **C. Aceptación real de PO/usuario/stakeholder:** ver sección 14 —
  `ACCEPTANCE_ACT_EXISTING: NO` para este incremento específico.

## 13. Definition of Done — evidencia histórica disponible

Se buscó explícitamente "Definition of Done", "DoD" y "Sprint Goal" en
todo el repositorio (`docs/*.md`, `README.md`, resto del árbol) — sin
resultados.

**HISTORICAL_DOD_EVIDENCE: NOT_FOUND.**

No se reconstruye un DoD y se presenta como el usado en Sprint 1. Un DoD
mejor para Sprint 2 sería una acción de mejora futura, explícitamente
fuera de esta fase.

## 14. Evidencia de aceptación / Sprint Review

- **Acta de aceptación existente:** `docs/acta-pruebas-aceptacion-usuario.md`
  (real, fechada 01-09-2026 y cierre 05-09-2026). Cubre un hallazgo de
  usabilidad móvil sobre el dashboard demo, ejecutado como
  **auto-evaluación del propio desarrollador** — el documento mismo lo
  aclara explícitamente ("no un usuario externo neutral"). **No cubre**
  el incremento del pipeline temporal/prototipo evaluado en este
  documento.
- **ACCEPTANCE_ACT_EXISTING (para el incremento de este Hito): NO.**
- **Sprint Review formal:** búsqueda exhaustiva sin resultados — ningún
  acta, registro, captura o comentario de PO/stakeholder encontrado.
  **FORMAL_SPRINT_REVIEW_EVIDENCE: NOT_FOUND.**
- Se generó `artifacts/hito1/testing/acceptance-protocol.md`, un
  protocolo LISTO para ejecutar una sesión real de aceptación del
  incremento actual — con todos los campos de fecha/evaluador/resultado
  vacíos hasta que una persona real lo ejecute. **No se presenta como
  evidencia de que ya ocurrió.**

**ACCEPTANCE_PROTOCOL_READY: YES.**

## 15. Defectos y acciones derivadas de pruebas

Ver `artifacts/hito1/testing/defect-evidence.md` — 6 hallazgos reales
(D-01 a D-06), cada uno con hallazgo/evidencia/impacto/decisión/
corrección/test de regresión verificado, más 2 hallazgos investigados y
descartados explícitamente (no eran defectos reales). Los 6 hallazgos
tienen evidencia completa de **hallazgo → análisis → decisión → cambio**;
ninguno tiene, hoy, un issue Jira verificado que cierre el ciclo hasta
"elemento de backlog" — ese último eslabón queda **PENDIENTE FASE DE
TRAZABILIDAD**, no inventado.

## 16. Evidencia semana a semana

No se encontró en el repositorio un calendario del curso que mapee
"Semana 3/4/5" a fechas calendario reales — `docs/informe-1-seminario-licenciatura.md`
ya señala esta misma brecha para el cronograma de Sprint 2-5. Ver tabla
completa con la evidencia dated real más cercana (sin forzar su
correspondencia a una semana específica) en
`artifacts/hito1/testing/rubric-testing-map.md`.

| Semana | Evidencia esperada | Evidencia real encontrada | Fuente verificable | Estado |
|---|---|---|---|---|
| 3 | Plan de pruebas + primeras ejecuciones | Commits iniciales con tags `#HU-01..#HU-08` (20-06-2026) — candidato cronológico, no confirmado contra calendario | `git log` | NO ENCONTRADA (sin calendario para confirmar) |
| 4 | Resultados unitarios/integración | Expansión de suite a gate 80% (commit `b8bbeb5`, 31-08-2026); `reports/coverage_run.txt` (02-09-2026) | `git log`, `reports/coverage_run.txt` | PARCIAL |
| 5 | Aceptación con usuario | `docs/acta-pruebas-aceptacion-usuario.md` (01/05-09-2026) — real, pero auto-evaluación, no usuario externo | `docs/acta-pruebas-aceptacion-usuario.md` | PARCIAL |

## 17. Cobertura de HU

No se fabrica un porcentaje. La matriz histórica (`matriz-trazabilidad-hu-test.md`)
cubre 8 HU/Jira identificadas del pipeline legacy con distintos grados
(Cerrado/Parcial/Post-hito). El pipeline temporal (7 AC-T técnicos
verificados) no tiene HU/Jira propia vinculada todavía.

**HU_COVERAGE: PENDING_TRACEABILITY.**

Se distingue explícitamente de la cobertura de código (91.72%, sección
6) — ver también sección 19.

## 18. Brechas y limitaciones

- Ningún DoD histórico verificable (sección 13).
- Ninguna Sprint Review formal verificable (sección 14).
- El pipeline temporal nuevo no tiene HU/Jira vinculada (secciones 11.2, 17).
- `docs/matriz-trazabilidad-hu-test.md` está desactualizada respecto al
  estado real de DEM/topografía (nota en 11.1) — su actualización queda
  fuera de esta fase (no se modificó).
- AC-T08 tiene una brecha de test en la capa de UI (`_fmt_nd` sin test
  dedicado) aunque la capa de datos está cubierta.
- No existe evidencia dated que permita confirmar Semana 3/4/5 contra un
  calendario real del curso (sección 16).
- Los scripts `test_persistence_postgis.py`, `test_prediction_query_real.py`,
  `test_spatial_join.py` (raíz) y el `test_raw_parser.py` de la raíz
  permanecen fuera de la suite automatizada (ya documentado como gap en
  la matriz histórica, no es un hallazgo nuevo).
- No se ejecutó `locustfile.py` (fuera de alcance AE1, sección 2).

## 19. Qué demuestra y qué NO demuestra la evidencia

**SÍ puede respaldar**, con la evidencia reunida en esta fase:

- Contratos de software (feature-sets A/B/C/D, data contract app/, no
  legacy en el prototipo).
- Regresión (los 6 hallazgos D-01..D-06 tienen guardas de test).
- Integridad del pipeline (unicidad de clave, no-imputación a 0/cero,
  exclusión honesta por cooldown).
- Comportamiento causal implementado (`feature_timestamp <= T`,
  ventana `(T,T+h]` exacta).
- Separación legacy/prototipo (verificada por AST y por test dedicado).
- Tratamiento de NaN (DEM, meteorología, HistGradientBoosting nativo).
- Ensamblado de la UI (Streamlit carga y corre en modo Prototipo).
- Reproducibilidad técnica (misma suite, mismo commit, mismo resultado).

**NO demuestra automáticamente**, aunque la suite completa pase:

- Capacidad predictiva generalizable del modelo.
- Calibración probabilística del score.
- Independencia de incendios físicos reales (FIRMS ≠ incendio confirmado).
- Utilidad operacional del prototipo.
- Vigilancia en tiempo real.
- Una alerta oficial.
- Validez científica del sistema solo porque `pytest` pasa — 470/470
  demuestra corrección técnica del código, no capacidad predictiva
  demostrada (ver `docs/arquitectura-hito1.md`/reglas científicas del
  proyecto, no modificadas en esta fase).

## 20. Evidencia reproducible

Todo lo citado en este documento es reproducible desde el mismo commit
(`9f076172adca3dbce0285f5d942d2803ac6f68a4`, rama `main`):

```
python -m pytest -q --no-cov -rs --junitxml=artifacts/hito1/testing/pytest-junit.xml
python -m pytest -q               # coverage vía pytest.ini (--cov=app --cov=src)
python -m pytest tests/test_app_integration.py -v --no-cov -rs   # smoke Streamlit
```

Artefactos completos, sin editar tras generarse:
`artifacts/hito1/testing/{environment.txt, git-state.txt, pytest-full.txt,
pytest-junit.xml, coverage-summary.txt, test-inventory.txt,
streamlit-smoke.txt, acceptance-checks.txt, rubric-testing-map.md,
defect-evidence.md, acceptance-protocol.md}`.

# Atributos de calidad — Sprint 1 / Hito 1

**Estado:** documento de trabajo. Arquitectura (`docs/arquitectura-hito1.md`),
Testing (`docs/testing-evidencia-hito1.md`) y Trazabilidad
(`docs/trazabilidad-hito1.md`) permanecen CONGELADOS — esta fase los
audita y reutiliza como fuente, no los reabre. Fecha de esta fase:
**07-09-2026**.

## 1. Propósito y alcance

Documentar los atributos de calidad del incremento del Hito 1 en el
único formato que la rúbrica reconoce como defendible: **atributo de
calidad → requerimiento relacionado → criterio medible → método de
verificación → evidencia → resultado observado**. No es una lista
genérica de ISO/IEC 25010 con adjetivos ("usabilidad: alta",
"seguridad: buena") — cada fila de la matriz principal cita un test, un
archivo o una cifra real ya verificada contra los artefactos congelados,
nunca una apreciación.

## 2. Método de selección

Se evaluaron 10 atributos candidatos (fiabilidad, mantenibilidad,
integridad de datos, robustez a datos faltantes, reproducibilidad,
auditabilidad/trazabilidad, usabilidad, rendimiento, seguridad,
disponibilidad) contra tres preguntas: ¿existe un requerimiento real en
`docs/trazabilidad-hito1.md`? ¿existe un criterio medible? ¿existe
evidencia verificable? Rendimiento y seguridad no superan la segunda
pregunta (no hay medición ni test de seguridad en el repositorio) — se
documentan como `NOT_MEASURED`/`NOT_PERFORMED`, nunca como "aceptables".
Disponibilidad no tiene requerimiento asociado: el prototipo es local,
on-demand, sin despliegue ni monitorización (`docs/arquitectura-hito1.md`,
sección 9) — no se confunde "la aplicación carga localmente" con "alta
disponibilidad".

**Cifras reutilizadas en este documento, confirmadas contra los
artefactos congelados antes de usarlas (no asumidas):**

| Cifra | Fuente verificada en esta fase |
|---|---|
| 470 collected / 470 passed / 0 failed / 0 skipped | `artifacts/hito1/testing/pytest-full.txt` (línea "470 passed... in 297.97s"); `pytest-junit.xml` (`tests="470" errors="0" failures="0" skipped="0"`) |
| Cobertura app+src = 91.72% | `artifacts/hito1/testing/coverage-summary.txt` (línea "Required test coverage of 80% reached. Total coverage: 91.72%") |
| Gate de cobertura ≥80% | `pytest.ini` (`--cov-fail-under=80`) |
| Smoke Streamlit: 5 passed | `artifacts/hito1/testing/streamlit-smoke.txt` ("5 passed... in 14.18s") |
| AC-T01..AC-T10 | `artifacts/hito1/testing/acceptance-checks.txt` (los 10 encabezados verificados uno por uno) |

## 3. Relación requerimiento → atributo

A partir de `docs/trazabilidad-hito1.md` (sección 5, REQ-01..REQ-16) —
no se inventan requerimientos nuevos. Ver la matriz completa en la
sección 15; resumen aquí:

| REQ | Descripción (resumen) | Atributo(s) asociado(s) |
|---|---|---|
| REQ-05 | Dashboard distingue demo vs. real | Fiabilidad, Usabilidad |
| REQ-06 | Gate de cobertura de tests ≥80% | Fiabilidad, Mantenibilidad |
| REQ-10 | DMC regional, nunca por celda | Integridad de datos |
| REQ-11 | Features `<= T` (causalidad) | Integridad de datos |
| REQ-12 | Target honesto `(T,T+h]`, cooldown | Integridad de datos |
| REQ-13 | Aislamiento legacy/demo del prototipo | Fiabilidad, Mantenibilidad |
| REQ-14 | Ranking relativo por celda | Fiabilidad |
| REQ-15 | DEM faltante → N/D, nunca 0 | Robustez a datos faltantes |
| REQ-16 | App carga sin excepción, modo Prototipo default | Fiabilidad, Usabilidad |
| REQ-07, REQ-08 | Matriz de riesgo / trazabilidad HU↔prueba | Auditabilidad/trazabilidad |

REQ-01, REQ-02, REQ-03, REQ-04, REQ-09 (contenido de ingesta/modelo
legacy) no tienen un atributo de calidad de software medible asociable
de forma directa — se marcan `SIN CRITERIO DE CALIDAD VERIFICABLE` en la
sección 15 en vez de forzar una relación artificial.

## 4. Matriz principal

| ID | Atributo | Requerimiento relacionado | Criterio medible | Método de verificación | Evidencia | Resultado observado | Estado | Brecha |
|---|---|---|---|---|---|---|---|---|
| QA-01 | Fiabilidad | REQ-06, REQ-13, REQ-14, REQ-16 | La suite automatizada completa debe finalizar sin fallos; la app debe ensamblarse sin excepción fatal; el ranking debe mantener la alineación `cell_id`↔score bajo reordenamiento; los empates deben compartir `display_rank` (method="min") | Ejecución de la suite (ya congelada) + tests de contrato dedicados | `pytest-full.txt`/`pytest-junit.xml`; `streamlit-smoke.txt`; `tests/test_prototype_service.py::test_reordering_features_df_does_not_desync_cell_id_and_score`; `test_ties_share_display_rank_but_internal_rank_stays_unique` | 470 passed / 0 failed; 5 passed (smoke); alineación y empates verificados por test dedicado, PASS | VERIFICADO | 470/0 no equivale a "100% fiable en producción" — ver sección 5 |
| QA-02 | Integridad de datos | REQ-10, REQ-11, REQ-12 | Meteorología regional nunca reetiquetada por celda; features `<= T`; target=1 solo en `(T,T+h]`; cooldown excluye (nunca 0); `cell_id` nunca es feature del modelo | Tests unitarios/integración por invariante | `test_regional_meteo*.py`; `test_causality_validator.py`; `test_target_builder.py`; `test_experiment_abcd_contract.py::test_no_model_contains_cell_id_or_synthetic_features` | Todos PASS (parte de 470/470); `reports/auditoria_integridad_datos.json` documenta el defecto histórico reemplazado | VERIFICADO | Integridad técnica — no implica validez predictiva científica (sección 6) |
| QA-03 | Mantenibilidad | REQ-06, REQ-13 | `app/` no debe importar módulos analíticos directamente; `prototype_service.py` debe ser la única frontera de inferencia; cobertura de código ≥80% | Análisis estático (AST) + estructura real + cobertura | `test_architecture.py`; `docs/arquitectura-hito1.md` (tabla de componentes); `coverage-summary.txt` (91.72%) | Contrato de arquitectura PASS; cobertura 91.72% (gate 80% superado) | PARCIALMENTE_VERIFICADO | Sin lint/type-checking/complejidad ciclomática — cero archivos de configuración (`ruff.toml`, `.flake8`, `mypy.ini`, secciones en `pyproject.toml`/`setup.cfg`) en el repositorio, verificado en esta fase |
| QA-04 | Robustez a datos faltantes | REQ-15 | DEM sin cobertura debe permanecer `NaN` (nunca 0); el modelo debe aceptar NaN nativamente; la UI debe mostrar "N/D" para datos faltantes | Tests dedicados (capa de datos) + lectura de código (capa de UI) | `test_dem_features.py::test_sample_grid_topography_returns_nan_for_cell_outside_raster_coverage`, `test_load_grid_topography_falls_back_to_nan_without_a_dem_directory`; `test_histgradientboosting_accepts_nan_end_to_end`; `app/components/prototype_view.py::_fmt_nd()` | Capa de datos: PASS. Capa de UI: implementada, verificada por lectura de código, sin test dedicado | PARCIALMENTE_VERIFICADO | UI: verificación manual, no automatizada — mismo hallazgo que AC-T08 |
| QA-05 | Reproducibilidad | (transversal) | Entorno, commit, artefacto de modelo y dataset deben ser identificables | Metadata real del artefacto + registro de entorno/commit | `models/prototype_model_d_metadata.json` (`dataset_hash`, `trained_at`, `random_state=42`, `n_training_rows=362883`); `environment.txt` (Python 3.14.6, pytest 9.1.1); `git-state.txt` (commit `9f076172...`); manifests con SHA256 | Pipeline completo identificado por hash/commit/semilla | VERIFICADO | Ninguna |
| QA-06 | Auditabilidad / trazabilidad | REQ-07, REQ-08, REQ-10..REQ-16 | Debe poder seguirse requerimiento→HU→CA→prueba→resultado→evidencia | Matriz de trazabilidad canónica | `docs/trazabilidad-hito1.md`, secciones 6 y 8 | Cadena completa para 8 HU/tarea Jira; evidencia técnica completa pero sin HU Jira para REQ-10..REQ-16 | PARCIALMENTE_VERIFICADO | `TEMPORAL_PIPELINE_HU_LINK: GAP` (heredado, no resuelto aquí) — no se afirma trazabilidad completa |
| QA-07 | Usabilidad | REQ-05, REQ-16 | Badge de modo visible; banner de datos históricos se activa correctamente; empates visibles (no ocultos); la app se ensambla sin excepción | Tests de UI + smoke Streamlit + una sesión con una persona real | `test_prototype_freshness.py` (8 tests, banner stale); `test_app_integration.py` (5 passed, smoke); `docs/acta-pruebas-aceptacion-usuario.md` | Banner y smoke PASS. La única sesión con una persona real es, según su propio documento, autoevaluación del desarrollador sobre un alcance distinto (usabilidad móvil del dashboard demo) | PARCIALMENTE_VERIFICADO | Smoke técnico ≠ prueba de usabilidad; no hay validación de usuario externo independiente para el pipeline temporal — no se reetiqueta la autoevaluación como tal |
| QA-08 | Rendimiento | — | Sin criterio medible definido ni medición realizada | — | `locustfile.py` existe (script real, "CP-01") sin evidencia de ejecución en `reports/` | Sin medición de tiempo de carga/inferencia/memoria | NO_VERIFICADO | `PERFORMANCE: NOT_MEASURED` |
| QA-09 | Seguridad | — | Sin test de seguridad definido | — | Búsqueda explícita en `tests/*.py`: cero resultados de seguridad/auth/inyección | Sin verificación de seguridad realizada | NO_VERIFICADO | `SECURITY: NOT_PERFORMED` — pendiente recomendado para Sprint 2 |
| QA-10 | Disponibilidad | — | No existe requisito de disponibilidad ni despliegue/monitorización/SLA en este incremento local | — | `docs/arquitectura-hito1.md`, sección 9 ("prototipo local") | — | NO_APLICA | `AVAILABILITY: NOT_VERIFIED (NO_APLICA_AL_INCREMENTO)` — no es un atributo fallido, es un atributo sin requisito asociado |

## 5. Fiabilidad

**Requerimientos:** REQ-06, REQ-13, REQ-14, REQ-16.

**Criterio medible:** (a) la suite automatizada completa debe finalizar
sin fallos; (b) la app debe ensamblarse sin excepción fatal; (c) el
ranking debe mantener la alineación `cell_id`↔score aunque cambie el
orden interno de las filas; (d) los empates de score deben compartir el
mismo `display_rank` (method="min").

**Resultado observado:** 470 collected, 470 passed, 0 failed, 0 skipped
(`pytest-full.txt`/`pytest-junit.xml`); 5 passed en el smoke Streamlit
aislado (`streamlit-smoke.txt`);
`test_reordering_features_df_does_not_desync_cell_id_and_score` y
`test_ties_share_display_rank_but_internal_rank_stays_unique` PASS.

**Lo que esto NO significa:** "470 passed / 0 failed" no se traduce a
"100% fiable" ni a "sistema confiable en producción". Es evidencia de
que, bajo las condiciones que la suite ejercita, el comportamiento
esperado se cumple de forma reproducible.

## 6. Integridad de datos

**Requerimientos:** REQ-10, REQ-11, REQ-12. Cuatro invariantes
verificadas independientemente: meteorología DMC tratada como regional
(nunca asignada por posición a una celda — el defecto histórico real que
esto reemplaza está en `reports/auditoria_integridad_datos.json`, 38/50
celdas mal asignadas bajo el mecanismo anterior); joins temporales
causales (`feature_timestamp <= T`, `test_causality_validator.py`, 10
tests); target honesto (ventana `(T,T+h]` exacta, cooldown excluye en
vez de etiquetar 0, `test_target_builder.py`, 12 tests); `cell_id`
excluido como predictor
(`test_no_model_contains_cell_id_or_synthetic_features`). DEM faltante
preservado como NaN (`test_dem_features.py`) — ver también sección 8.
`demo_seed` fuera del prototipo real, verificado por
`test_no_legacy_imports_in_prototype_modules`.

**Diferenciación obligatoria:** esto es integridad **técnica** de los
datos y del pipeline — no es lo mismo que **validez predictiva
científica** del modelo. No se usa PR-AUC, ROC-AUC, calibración ni
capacidad predictiva como evidencia de este atributo (ver sección 12).
El score sigue siendo un **ranking relativo exploratorio**, no una
probabilidad calibrada ni una alerta oficial.

## 7. Mantenibilidad

**Requerimientos:** REQ-06, REQ-13. Evidencia estructural real:
`tests/test_architecture.py` bloquea por AST cualquier import directo de
`app/` hacia `src.ingesta`/`procesamiento`/`modelo`/`pipeline`;
`src/inference/prototype_service.py` es la única interfaz pública del
prototipo (frontera de inferencia); la UI (`app/`) está separada de la
lógica de negocio (`src/`); ausencia de imports legacy verificada por
test dedicado; nomenclatura y responsabilidades separadas por módulo
(`docs/arquitectura-hito1.md`, tabla de componentes); cobertura de
código 91.72% sobre el gate del 80%.

**Lo que no se encontró (y no se inventa):** no existe ningún archivo de
configuración de linting o type-checking (`ruff.toml`, `.flake8`,
`mypy.ini`, o sección equivalente en `pyproject.toml`/`setup.cfg` — se
buscaron los cinco explícitamente, ninguno existe), ni una medición de
complejidad ciclomática. Estado: `PARCIALMENTE_VERIFICADO`.

## 8. Robustez a datos faltantes

**Requerimiento:** REQ-15. Capa de datos: `HistGradientBoostingClassifier`
acepta NaN nativamente
(`test_histgradientboosting_accepts_nan_end_to_end`); una celda DEM sin
cobertura de raster queda `NaN`, nunca `0`
(`test_sample_grid_topography_returns_nan_for_cell_outside_raster_coverage`,
`test_load_grid_topography_falls_back_to_nan_without_a_dem_directory`).
Capa de UI: `app/components/prototype_view.py::_fmt_nd()` formatea
NaN/None a "N/D" explícitamente (verificado leyendo el código, líneas
84-90) — sin test unitario dedicado a esta función. Estado:
`PARCIALMENTE_VERIFICADO` — capa de datos automatizada, capa de UI
manual, tal como exige registrarse (no se llama "automatizado" a lo que
no lo es).

## 9. Reproducibilidad

Es el atributo con la evidencia más completa. `models/prototype_model_d_metadata.json`
fija `dataset_hash`, `trained_at`, `random_state=42`,
`n_training_rows=362883`, `n_positive_rows=107` y la lista exacta de
`feature_columns`. `artifacts/hito1/testing/environment.txt` fija Python
3.14.6 y pytest 9.1.1. `artifacts/hito1/testing/git-state.txt` fija el
commit evaluado (`9f076172adca3dbce0285f5d942d2803ac6f68a4`). Los
manifests de ingesta (`nasa_firms_..._manifest.json`) incluyen SHA256
del CSV consolidado. `pytest-junit.xml` y `coverage-summary.txt` son
artefactos de ejecución con rutas verificables, no afirmaciones sueltas.
Estado: `VERIFICADO`.

## 10. Auditabilidad / trazabilidad

**Requerimientos:** REQ-07, REQ-08, REQ-10..REQ-16. `docs/trazabilidad-hito1.md`
(secciones 6 y 8) permite seguir la cadena
requerimiento→HU→CA→prueba→resultado→evidencia de forma completa para 8
HU/tarea Jira verificables (SAPI-26/28/30/32/44/45/47/48). Para los
requerimientos del pipeline temporal (REQ-10..REQ-16) la evidencia
técnica (prueba→resultado→evidencia) es completa, pero
**`TEMPORAL_PIPELINE_HU_LINK: GAP`** — no existe HU/Jira vinculada. **No
se afirma trazabilidad completa** del incremento; se afirma trazabilidad
completa de la evidencia técnica y trazabilidad parcial a nivel de HU
Jira. Estado: `PARCIALMENTE_VERIFICADO`.

## 11. Usabilidad

**Requerimientos:** REQ-05, REQ-16. Evidencia real: el banner de datos
históricos/desactualizados se activa según la antigüedad real de la
lectura meteorológica (`test_prototype_freshness.py`, 8 tests); la app
se ensambla y corre en modo Prototipo por defecto sin excepción
(`test_app_integration.py`, 5 passed — esto es un **smoke técnico de
integración**, no una prueba de usabilidad, y se etiqueta como tal). La
única evidencia de una persona real interactuando con el dashboard es
`docs/acta-pruebas-aceptacion-usuario.md`: ese documento etiqueta la
sesión explícitamente como **autoevaluación del desarrollador** (Daniel
Cortez Fierro, el mismo responsable del proyecto), **no** una validación
independiente de usuario, y sobre un alcance distinto (usabilidad móvil
del dashboard demo, no el pipeline temporal de este Hito). No se
reetiqueta esa sesión como algo que no fue. Estado:
`PARCIALMENTE_VERIFICADO`.

## 12. Atributos no verificados

**No evaluados por falta de evidencia** (candidatos válidos, sin
medición ni verificación — distinto de "no aplica"):

- **Rendimiento:** `PERFORMANCE: NOT_MEASURED`. Existe un script de
  prueba de carga real (`locustfile.py`, "CP-01") pero sin evidencia de
  ejecución capturada — no se ejecuta en esta fase ni se inventan
  cifras como "<2 segundos" o "respuesta rápida".
- **Seguridad:** `SECURITY: NOT_PERFORMED`. No existe ningún test de
  seguridad en el repositorio. No se afirma "sistema seguro" ni
  "seguridad validada". Puede documentarse como pendiente para Sprint 2.

**No aplicable al incremento** (distinto de un atributo fallido — no
existe requisito ni despliegue/monitorización/SLA que evaluar):

- **Disponibilidad:** `AVAILABILITY: NOT_VERIFIED (NO_APLICA_AL_INCREMENTO)`.
  El prototipo es local, ejecutado on-demand, sin despliegue ni
  monitorización — no existe un requisito de disponibilidad en este
  incremento contra el cual verificar nada. "La aplicación carga
  localmente" no se confunde con "alta disponibilidad", pero tampoco se
  cuenta como una brecha del incremento (ver sección 13).

**Fuera del alcance de la calidad de software** (mencionado aquí solo
para no mezclarlo con la matriz):

- **Calidad científica (PR-AUC, ROC-AUC, Brier, calibración,
  generalización, capacidad predictiva):** explícitamente **no** son
  atributos de calidad de software y no se mezclan con esta matriz —
  son limitaciones científicas documentadas en
  `docs/arquitectura-hito1.md`/`sapi-scientific-claims.md`. El sistema
  produce un **score relativo exploratorio**, no una probabilidad
  calibrada, y no es una alerta oficial.

## 13. Brechas

1. Mantenibilidad sin evidencia de linting/type-checking/complejidad
   ciclomática (sección 7).
2. Robustez a datos faltantes: capa de UI verificada solo manualmente
   (sección 8, mismo hallazgo que AC-T08).
3. Auditabilidad/trazabilidad: `TEMPORAL_PIPELINE_HU_LINK: GAP` heredado
   de la fase de Trazabilidad, no resuelto aquí (sección 10).
4. Usabilidad: sin validación de usuario externo independiente para el
   incremento del pipeline temporal (sección 11).
5. Rendimiento y seguridad: sin medición/verificación realizada en
   absoluto — no son atributos débiles, son atributos **no evaluados**.

**Nota (no es una brecha):** Disponibilidad queda `NO_APLICA` porque el
incremento no tiene un requisito de disponibilidad ni un
despliegue/SLA que evaluar — no se cuenta junto con las brechas
anteriores porque no representa una verificación pendiente ni fallida.

## 14. Evidencia reproducible

Todo lo citado proviene de artefactos ya congelados — no se re-ejecutó
la suite completa en esta fase (se reutilizaron `pytest-full.txt`/
`pytest-junit.xml`/`coverage-summary.txt`/`streamlit-smoke.txt`/
`acceptance-checks.txt`); se leyó directamente
`models/prototype_model_d_metadata.json`, `.env.example`, `pytest.ini`,
y se realizaron búsquedas puntuales de configuración de linting (cero
resultados) y de tests de seguridad (cero resultados) contra el árbol
real del repositorio en el commit
`9f076172adca3dbce0285f5d942d2803ac6f68a4`.

## 15. Matriz requerimiento → atributo

| Requerimiento | Atributo asociado | Criterio medible | Evidencia | Estado |
|---|---|---|---|---|
| REQ-01 (histórico FIRMS) | — | — | — | SIN CRITERIO DE CALIDAD VERIFICABLE |
| REQ-02 (join DMC↔ignición) | — | — | — | SIN CRITERIO DE CALIDAD VERIFICABLE |
| REQ-03 (topografía DEM por celda) | — | — | — | SIN CRITERIO DE CALIDAD VERIFICABLE |
| REQ-04 (limpieza/normalización) | — | — | — | SIN CRITERIO DE CALIDAD VERIFICABLE |
| REQ-05 (dashboard distingue demo/real) | Usabilidad | Badge de modo visible | `app/app.py::_resolve_dashboard_mode()`, `test_app.py` | PARCIALMENTE_VERIFICADO |
| REQ-06 (gate cobertura ≥80%) | Fiabilidad, Mantenibilidad | Cobertura app+src ≥80% | `coverage-summary.txt` (91.72%) | VERIFICADO |
| REQ-07 (matriz de riesgo) | Auditabilidad/trazabilidad | Documento con evidencia por riesgo | `docs/matriz-riesgo.md` | PARCIALMENTE_VERIFICADO |
| REQ-08 (trazabilidad HU↔prueba) | Auditabilidad/trazabilidad | Cadena HU→CA→prueba→evidencia | `docs/trazabilidad-hito1.md` | PARCIALMENTE_VERIFICADO |
| REQ-09 (motor predictivo legacy) | — | — | — | SIN CRITERIO DE CALIDAD VERIFICABLE |
| REQ-10 (DMC regional) | Integridad de datos | Serie sin `cell_id` propio | `test_regional_meteo*.py` | VERIFICADO |
| REQ-11 (causalidad `<=T`) | Integridad de datos | `feature_timestamp <= T` en el 100% de los casos probados | `test_causality_validator.py` | VERIFICADO |
| REQ-12 (target honesto) | Integridad de datos | `target=1` solo en `(T,T+h]`; cooldown excluye | `test_target_builder.py` | VERIFICADO |
| REQ-13 (aislamiento legacy) | Fiabilidad, Mantenibilidad | Cero imports legacy/demo en el prototipo | `test_no_legacy_imports_in_prototype_modules` | VERIFICADO |
| REQ-14 (ranking por celda) | Fiabilidad | 50 celdas únicas; alineación cell_id↔score robusta | `test_inference_returns_fifty_cells`, `test_reordering_features_df_does_not_desync_cell_id_and_score` | VERIFICADO |
| REQ-15 (DEM N/D, nunca 0) | Robustez a datos faltantes | DEM sin cobertura queda NaN | `test_dem_features.py` (datos); `_fmt_nd()` (UI, manual) | PARCIALMENTE_VERIFICADO |
| REQ-16 (app carga sin excepción) | Fiabilidad, Usabilidad | App se ensambla sin excepción; modo Prototipo default | `test_app_integration.py` (5 passed) | VERIFICADO |

**Nota sobre "50 celdas" y "horizonte 6h":** aparecen como criterio
medible únicamente en la fila REQ-14 (ranking) y en la definición de
REQ-12 (target), porque ahí sí están ligados a un requerimiento real y
verificable — no se usan sueltos como si fueran, por sí mismos, una
métrica de calidad de software.

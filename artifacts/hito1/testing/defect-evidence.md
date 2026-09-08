# Defectos y hallazgos — evidencia verificable

Solo defectos con evidencia real verificada (commit, test de regresión,
reporte/manifest en disco, o docstring del propio código citando la
auditoría que lo originó). Ninguno se etiqueta "bug del Sprint 1" sin
verificar fecha y contexto real.

---

## D-01 — Meteorología DMC asignada por posición de fila a 50 celdas

- **Origen:** `DataProcessor._load_meteo()` (pipeline legacy/demo).
- **Hallazgo:** la función asignaba `df["cell_id"] = grid["cell_id"].values[:len(df)]`
  — asignación por **posición de fila**, no por criterio geográfico. Una
  observación real de la estación 330007 (Rodelillo) terminaba etiquetada
  como si fuera la medición propia de hasta 50 celdas distintas.
- **Evidencia:** `reports/auditoria_integridad_datos.json` (script
  `scripts/auditoria_integridad_datos.py`) — `"n_celdas_con_asignacion_geograficamente_correcta": 12`,
  `"n_celdas_con_asignacion_geograficamente_incorrecta": 38`,
  `"delta_temporal_tipico_entre_celdas_consecutivas_minutos": 1.0`
  (indicando lecturas horarias consecutivas de una sola estación, no 50
  ubicaciones). Citado también en el docstring de
  `src/procesamiento/regional_meteo.py`.
- **Impacto:** cualquier feature meteorológico "por celda" del pipeline
  legacy no representaba variación espacial real.
- **Decisión tomada:** no parchear `_load_meteo()`; construir un módulo
  nuevo (`regional_meteo.py`) que nunca asigna `cell_id` a una lectura
  meteorológica — la serie queda explícitamente regional.
- **Corrección existente:** `src/procesamiento/regional_meteo.py::load_regional_meteo_series()`.
- **Test de regresión:** `tests/test_regional_meteo.py`,
  `tests/test_regional_meteo_loading.py` (PASS en la ejecución fresca).
- **Issue Jira asociado:** no verificado — el pipeline temporal
  (`regional_meteo.py`) no tiene un ticket SAPI-* identificado en la
  reconciliación de Jira disponible. **PENDIENTE FASE DE TRAZABILIDAD.**
- **Estado:** Cerrado (técnicamente, en el pipeline temporal). El
  `_load_meteo()` legacy original permanece en el código del pipeline
  demo/legacy, sin modificarse — el prototipo simplemente no lo usa
  (ver `docs/arquitectura-hito1.md`, sección 9).

---

## D-02 — `n_positive_rows` contaba pares (event_id, cell_id) en vez de filas

- **Origen:** `src/procesamiento/episode_evaluation.py`.
- **Hallazgo:** cuando dos eventos distintos calificaban como positivos
  para la misma fila `(cell_id, forecast_time)`, la función sobrecontaba
  esa fila una vez por cada evento en vez de una vez por fila.
- **Evidencia:** `tests/test_episode_evaluation.py::test_n_positive_rows_counts_rows_not_row_event_pairs_when_two_events_qualify`
  — test específico y nombrado exactamente para este caso, PASS en la
  ejecución fresca.
- **Impacto:** cualquier métrica derivada de "cuántas filas positivas
  hay" podía inflarse en escenarios reales con eventos próximos en
  tiempo y espacio.
- **Decisión tomada:** contar por `(cell_id, forecast_time)` único, no
  por combinación con `event_id`.
- **Corrección existente:** `src/procesamiento/episode_evaluation.py`.
- **Test de regresión:** el mismo test citado arriba (PASS).
- **Issue Jira asociado:** no verificado. **PENDIENTE FASE DE TRAZABILIDAD.**
- **Estado:** Cerrado.

---

## D-03 — Archivos de conflicto del backfill DMC podían mezclarse con los reales

- **Origen:** `src/procesamiento/regional_meteo.py` (glob de archivos).
- **Hallazgo:** un glob ingenuo sobre `dmc_historico_{station}_*.json`
  también capturaría los archivos `*_conflicto_*.json` que
  `scripts/backfill_dmc_historico.py` genera cuando una re-descarga no
  coincide con lo ya guardado — mezclando datos en disputa con datos
  aceptados en la misma serie.
- **Evidencia:** `tests/test_regional_meteo_loading.py::test_ignores_conflict_files_left_by_the_backfill_script`
  (PASS); comentario explícito en el docstring de `load_regional_meteo_series()`.
- **Impacto:** de no excluirse, la serie meteorológica regional podría
  promediar/duplicar en silencio observaciones marcadas para revisión
  manual.
- **Decisión tomada:** excluir explícitamente cualquier archivo con
  `_conflicto_` en el nombre; los conflictos quedan para revisión manual,
  nunca para consumo automático.
- **Corrección existente:** `src/procesamiento/regional_meteo.py`
  (exclusión explícita en el glob).
- **Test de regresión:** el citado arriba (PASS).
- **Issue Jira asociado:** no verificado. **PENDIENTE FASE DE TRAZABILIDAD.**
- **Estado:** Cerrado.

---

## D-04 — `HistGradientBoostingClassifier` fallaba con clase minoritaria insuficiente

- **Origen:** `scripts/experiment_abcd.py::run_fold()`.
- **Hallazgo:** con el fold `train=2021`, el conjunto de entrenamiento
  tenía un único positivo — insuficiente para el split interno
  estratificado de early-stopping de `HistGradientBoostingClassifier`,
  que lanzaba un `ValueError` de sklearn poco explicable en ese contexto.
- **Evidencia:** `tests/test_experiment_abcd_contract.py::test_run_fold_handles_a_train_set_with_only_one_positive_without_crashing`
  y `test_run_fold_trains_normally_when_train_has_at_least_two_positives`
  (ambos PASS).
- **Impacto:** el experimento walk-forward podía abortar por completo en
  el primer fold en vez de reportar explícitamente "soporte insuficiente"
  para ese fold.
- **Decisión tomada:** agregar una guarda explícita con un mensaje claro
  en vez de dejar propagar el `ValueError` de sklearn.
- **Corrección existente:** `scripts/experiment_abcd.py::run_fold()`.
- **Test de regresión:** los citados arriba (PASS).
- **Issue Jira asociado:** no verificado. **PENDIENTE FASE DE TRAZABILIDAD.**
- **Estado:** Cerrado.

---

## D-05 — Riesgo de desalineación `cell_id` ↔ `score` tras un reordenamiento

- **Origen:** `src/inference/prototype_service.py::score_current_grid()`.
- **Hallazgo (preventivo, no un bug observado en producción):** cualquier
  `.sort_values()` posterior sobre `features_df` por una columna de
  feature podría, en una implementación ingenua, desalinear qué score
  corresponde a qué `cell_id` si se realineara por posición entera en vez
  de por índice.
- **Evidencia:** `tests/test_prototype_service.py::test_reordering_features_df_does_not_desync_cell_id_and_score`
  (PASS) — test de contrato que fija el comportamiento correcto
  (alineación siempre por índice `cell_id`, nunca por posición).
- **Impacto potencial si se rompiera:** el mapa/ranking mostraría el
  score de una celda como si fuera el de otra — el hallazgo más grave
  posible en un sistema de priorización espacial.
- **Decisión tomada:** documentar y testear explícitamente el contrato
  "alineación por índice `cell_id`, nunca por posición" directamente en
  `build_feature_matrix()`/`score_current_grid()` (comentario en el
  código + test dedicado).
- **Corrección existente:** no aplica una corrección de un bug real —
  es una guarda de regresión preventiva sobre un riesgo identificado.
- **Test de regresión:** el citado arriba (PASS).
- **Issue Jira asociado:** no verificado. **PENDIENTE FASE DE TRAZABILIDAD.**
- **Estado:** Cerrado (mitigado preventivamente).

---

## D-06 — DEM sin cobertura podía convertirse en 0 si se imputaba genéricamente

- **Origen:** riesgo de diseño en `src/procesamiento/dem_features.py`
  (no un bug observado — una decisión que se blindó explícitamente).
- **Hallazgo:** una celda fuera de la cobertura del raster DEM, o sin
  directorio DEM disponible, no tiene un valor físico real de
  elevación/pendiente/orientación — imputar 0 sería fabricar un dato.
- **Evidencia:** `tests/test_dem_features.py::test_sample_grid_topography_returns_nan_for_cell_outside_raster_coverage`,
  `test_load_grid_topography_falls_back_to_nan_without_a_dem_directory`
  (ambos PASS) — confirman que el valor queda `NaN`, nunca `0`.
- **Impacto potencial si se hubiera imputado 0:** el modelo aprendería
  "elevación 0" como si fuera nivel del mar real para celdas sin dato,
  sesgando la topografía sistemáticamente.
- **Decisión tomada:** usar `HistGradientBoostingClassifier` (soporte
  nativo de NaN) en vez de imputación genérica, y blindar el
  comportamiento con tests dedicados.
- **Corrección existente:** no aplica — decisión de diseño desde el
  origen del módulo, blindada con tests.
- **Issue Jira asociado:** relacionado con SAPI-30 (topografía DEM),
  que la matriz de trazabilidad existente (`docs/matriz-trazabilidad-hu-test.md`,
  fila SAPI-30) marca como **"Post-hito"** — esa matriz es anterior a la
  existencia de `dem_features.py`/`dem_terrain.py` reales (última
  actualización 05-09-2026), por lo que **no refleja este avance**. Se
  registra aquí como **hallazgo nuevo de esta fase**, con el enlace
  Jira **PENDIENTE FASE DE TRAZABILIDAD**.
- **Estado:** Cerrado (mitigado por diseño).

---

## Hallazgos investigados y descartados como defecto de esta fase

- **Regla 30-30-30 "agregada entre distintas observaciones":** se
  verificó `src/procesamiento/features.py::_encode_rule_30_30_30` —
  opera fila por fila sobre una única lectura meteorológica
  (`RULE_30_30_30_TEMP_THRESHOLD`/`HUMIDITY`/`WIND`), no agrega entre
  observaciones distintas. No se encontró evidencia de que este defecto
  exista en el código actual — no se reporta como hallazgo real.
- **Scripts legacy `test_persistence_postgis.py` / `test_spatial_join.py`
  (raíz):** no son defectos — son scripts de verificación manual
  documentados como tales, fuera de `pytest.ini` `testpaths`, ya
  señalados como brecha ("Gap — no en pytest") en
  `docs/matriz-trazabilidad-hu-test.md` (fila "Persistencia PostGIS" /
  "Join espacial grilla") desde el 05-09-2026 — no es un hallazgo nuevo.

---

## Nota sobre gestión del cambio (alimenta la fase de Gestión del cambio)

Los seis hallazgos D-01 a D-06 tienen, en esta fase, evidencia completa
de **hallazgo → análisis → decisión → cambio** (todos verificables por
commit/código/test). Ninguno tiene, hoy, un **elemento de backlog Jira**
verificado que los vincule — el eslabón final de la cadena que exige la
rúbrica de Gestión del cambio queda **PENDIENTE FASE DE TRAZABILIDAD**,
no inventado aquí.

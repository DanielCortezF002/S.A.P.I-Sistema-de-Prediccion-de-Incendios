# Auditoría de consistencia código ↔ parquet ↔ informe (2026-09-06/07)

Continuación de la auditoría del pipeline temporal nuevo. Alcance: verificar,
contra el repositorio y los artefactos REALES (no contra reportes previos),
que el código, el `temporal_dataset_h6.parquet` generado y el manifest que lo
describe cuentan exactamente la misma historia — y corregir cualquier
discrepancia con una prueba de regresión permanente.

Marco de referencia que se mantiene en todo el documento:
- `event_id` es una construcción algorítmica de `assign_episodes()` (radio
  2km / gap máx. 6h, **congelados**, nunca reoptimizados). Nunca "incendio
  independiente" ni "independent_fire_id".
- "S.A.P.I. construye un ranking exploratorio de riesgo relativo para nuevas
  detecciones FIRMS futuras, condicionado a la información disponible en T."
  — no "predice".
- Todo resultado numérico de este documento es EXPLORATORIO, nunca evidencia
  de capacidad predictiva validada.

## A. Bugs de consistencia encontrados

1. **`event_id` no era columna del parquet.** El dataset no era
   auto-auditable: para saber por qué una fila tenía `target=1` había que
   recalcular `assign_episodes()` por fuera y cruzarlo a mano.
2. **Filas con más de un evento calificando en la misma ventana.**
   Verificado contra datos reales (2026-09-06): 8 celdas (VP-002, VP-003,
   VP-013, VP-021, VP-023, VP-027, VP-028, VP-033) tienen dos `event_id`
   distintos arribando a menos de 6h uno del otro. Una comprobación cruzada
   ingenua por igualdad de conjuntos (`positive_event_ids == cross_check_ids`)
   habría lanzado un falso positivo de "inconsistencia" en 6 filas reales.
3. **`EpisodeEvaluationReport.n_positive_rows` sobrecontaba** en el mismo
   escenario: contaba `(event_id, cell_id, forecast_time)` en vez de
   `(cell_id, forecast_time)`, así que una fila con dos eventos calificando
   se contaba dos veces como "fila positiva".
4. **`_prep_xy` no fallaba con un mensaje explicable** si recibía filas
   `excluded=True`: el `.astype(int)` sobre un `target=NaN` habría lanzado un
   `ValueError` genérico de pandas sin decir por qué esa fila no debía estar
   ahí.
5. **El manifest no se autoverificaba** contra el parquet que describe — no
   existía ningún chequeo automático de que sus cifras fueran reproducibles.
6. **Comentario desactualizado** en `experiment_abcd.py` seguía citando
   "n=17-31" de una iteración anterior de este mismo análisis.
7. **`ZeroDivisionError` real** en `scripts/megaevento_report.py` (bug
   introducido y atrapado por su propio test de regresión antes de llegar a
   producción) al pedir el reporte de una fecha sin ninguna fila positiva.

## B. Correcciones aplicadas

- `target_builder.build_targets()`: agrega `target_event_id` y
  `target_timestamp` a cada fila (el evento de arribo más temprano cuando
  hay empate, documentado explícitamente como tal).
- `build_temporal_dataset.py`: cross-check **por fila** (no por conjunto
  global) de que `target_event_id` está contenido en los eventos que un
  join independiente contra `arrivals` encuentra calificando para esa
  misma fila — falla con `RuntimeError` si no.
- Nuevo `validate_manifest_matches_dataset()` en `pipeline_validators.py`:
  recalcula 10 cifras del manifest directamente sobre el parquet reescrito
  en disco y FALLA (nunca WARN) ante cualquier discrepancia. Wireado dentro
  de `build_temporal_dataset.py::main()` — corre en cada generación del
  dataset, no solo en tests.
- `episode_evaluation.py::evaluate_by_episode`: `n_positive_rows` ahora
  cuenta `(cell_id, forecast_time)` únicos.
- `_prep_xy()`: falla explícitamente (`ValueError` con mensaje específico)
  si recibe `excluded=True`, `eligible_for_training=False`, o un `target`
  NaN sin columna `excluded` que lo explique.
- Verificación de reproducibilidad del hash: escribir → leer bytes →
  recalcular SHA-256 → comparar, dentro de `main()` — falla si no coincide.
- Manifest ahora reporta **dos** cifras de episodios positivos, ninguna
  oculta a la otra:
  - `n_positive_raw_episodes` (26): un disparador por fila
    (`target_event_id`).
  - `n_positive_raw_episodes_any_qualifying` (31): unión de todo evento que
    calificaría, incluidos los que pierden el desempate.

## C. Tests nuevos (permanentes, no exploratorios)

| Archivo | Qué ancla |
|---|---|
| `tests/test_target_builder.py` (+4) | `target_event_id`/`target_timestamp`: earliest-wins, `None` en negativos/excluidos |
| `tests/test_pipeline_validators.py` (+5) | `validate_manifest_matches_dataset`: PASS en fixture consistente, FAIL en 3 tipos de mentira, PASS contra el parquet+manifest reales |
| `tests/test_experiment_abcd_contract.py` (+4) | `_prep_xy` falla explícito en excluded/ineligible/NaN-sin-excluded; sigue funcionando limpio en el caso normal |
| `tests/test_temporal_dataset_integration.py` (+3) | dtype float de `target` (nunca int), `target_event_id`/`target_timestamp` NaN⟺no-positivo tras roundtrip a disco, `forecast_time` reproducible solo desde meteo (sin tocar FIRMS) |
| `tests/test_episode_evaluation.py` (+1) | dos eventos calificando en una fila cuentan 2 episodios pero 1 fila |
| `tests/test_row_explainer.py` (nuevo, 5) | herramienta de reconstrucción de fila, incluida una demostración contra una fila real del megaevento |
| `tests/test_megaevento_report.py` (nuevo, 2) | concentración del 2024-02-03 se mantiene medible y > 30 % del dataset; caso sin actividad bien definido |
| `tests/test_nan_journey_real_data.py` (nuevo, 1) | NaN antes/después de `_prep_xy` y en `predict_proba` idénticos, verificado contra `run_fold` real |

## D. Estado de `excluded` / `eligible_for_training`

Verificado contra el parquet real (23,650 filas, h=6): `n_excluded=55`,
`n_eligible=23,595`, `n_excluded + n_eligible == n_rows` exacto. El código de
`build_temporal_dataset.py` **nunca** filtra `dataset` por `excluded` — solo
la variable separada `eligible` se filtra; `dataset` conserva las 23,650
filas completas. Los 55 casos `excluded=True` tienen `target=None`
(`float('nan')`, dtype `float64` — no se puede representar como entero sin
forzar 0/1) en el 100 % de los casos, verificado con
`test_excluded_rows_are_never_negative_never_positive` y el nuevo
`test_target_column_dtype_allows_real_nan_not_a_forced_int_cast`.

## E. Estado de `positive_event_ids` / trazabilidad

`dataset[dataset.target==1]["target_event_id"].nunique()` = **26**, idéntico
al `n_positive_raw_episodes` del manifest — verificado directamente contra
el parquet (no solo en memoria durante la generación). El join independiente
contra `arrivals` confirma que cada `target_event_id` registrado es un
evento real que calificaba para esa fila exacta (chequeo por fila, sección A.2).

## F. Número de raw episodes — dos cifras, ninguna "independiente"

- **26** — `n_positive_raw_episodes`: un `event_id` por fila (el de arribo
  más temprano en caso de empate).
- **31** — `n_positive_raw_episodes_any_qualifying`: unión de todo `event_id`
  que calificaría para alguna fila positiva.
- Ninguna de las dos es "incendios independientes". Tabla completa de
  trazabilidad: `reports/event_traceability_h6.csv` (generada por
  `scripts/build_event_traceability_table.py`).

## G. Definición exacta de la unidad de evaluación (`evaluate_by_episode`)

Ver docstring extendido de `src/procesamiento/episode_evaluation.py`
(sección "Formato exacto"). Resumen:
1. Cada fila positiva se vincula a TODOS los `event_id` que calificarían
   para ella (join contra `arrivals`, no solo `target_event_id`).
2. `rank` = posición por score descendente entre todas las filas del mismo
   `forecast_time` (empates: `method="min"`).
3. Un episodio que aparece en varias filas usa su MEJOR rank.
4. `hit_at_k` = fracción de episodios (no de filas) con mejor rank `<= k`.

Reconciliación explícita: `n_raw_episodes_evaluated` de este módulo puede
ser **mayor** que `n_positive_raw_episodes` del manifest (31 "any
qualifying" vs 26 "un disparador por fila") — son dos preguntas distintas,
documentadas por separado, nunca mezcladas en un solo número.

## H. Estado del megaevento 2024-02-03

`scripts/megaevento_report.py` (`reports/megaevento_2024-02-03_report.json`):

- 355 detecciones FIRMS crudas, agrupadas por `assign_episodes()` en **26
  raw episodes** distintos, entre las 05:56 y las 18:19 UTC de un solo día.
- 14 celdas afectadas.
- **23 de las 46** filas positivas de TODO el dataset (**50.0 %**) y **23 de
  las 29** filas positivas del fold `test=2024-02` (**79.3 %**) provienen de
  este único día calendario.
- Ningún `event_id` individual supera el umbral de concentración de
  `validate_event_independence` (el mayor, event_id=3072, es 8/29=27.6% del
  fold) — la concentración real está a nivel de DÍA CALENDARIO, repartida en
  26 episodios distintos que el clustering separa correctamente por celda,
  no a nivel de un solo evento.
- Conclusión obligatoria: cualquier métrica del fold 2024-02 se lee como
  "rendimiento mayormente explicado por un evento regional de un día", nunca
  como evidencia de generalización a fuegos dispersos en el tiempo.

## I. Estado de missingness real (no solo fixture)

`tests/test_nan_journey_real_data.py`, corrida real de `run_fold` sobre
train=2022-01/test=2022-12: `_prep_xy` no altera el conteo de NaN
(`n_nan_before_prep_xy == n_nan_after_prep_xy` exacto, en train y test), y lo
que recibe `predict_proba` tiene el mismo conteo de NaN que antes de
llamarlo. Cifras reales para el modelo D en ese fold: `meteo_actual_*` con
150/6197 (train) y 50/5582 (test) NaN; el bloque de topografía
(`elevacion`/`pendiente`/`orientacion`) con **2479/6197 (40 %)** en train y
**2230/5582 (40 %)** en test — cobertura DEM real más baja que la
meteorológica, dato a tener presente al interpretar el modelo D, no un bug.

## J. Origen de `forecast_time` — independencia de FIRMS verificada

`test_forecast_times_are_reproducible_from_meteo_alone_without_touching_firms`:
recalcula el conjunto completo de `forecast_time` ÚNICAMENTE desde
`load_regional_meteo_series()` + `resample(6h).first().dropna()` — sin
importar `episodes`, `arrivals` ni leer el CSV de FIRMS en absoluto — y
confirma igualdad exacta con los `forecast_time` del parquet. Evidencia
estructural adicional: en `build_temporal_dataset.py`, `forecast_times` se
calcula en la línea 96, antes de que `fires`/`episodes`/`arrivals` se carguen
siquiera (línea 99-101) — no hay forma de que dependa de ellos.

## K. Definición de "nueva detección" vs. cooldown

`target(cell,T,h)=1 ⟺ ∃ evento con first_arrival(evento,cell) ∈ (T,T+h]`,
excepto si `(cell,T)` cae en cooldown de un arribo previo — ahí la fila es
`excluded=True`, `target=None` (nunca 0). Ventana abierta en T (un arribo
exactamente en T no cuenta como "futuro": activa cooldown, no un target
negativo). Frozen: radio 2km, gap 6h — ninguna búsqueda de "mejor" parámetro
se realizó ni se realizará en esta fase.

## L. Reproducibilidad del hash

`build_temporal_dataset.py::main()` ahora hace: escribir parquet → leer sus
bytes → SHA-256 → releer los mismos bytes → recalcular SHA-256 → comparar.
Corrida real: `hash_dataset =
c66f625141f530c0cc83ce401ced149d34b80dbebacaa674a8e6a3186d19f168`,
reproducible exacto en la misma corrida.

## M. Suite de tests

**433 passed, 0 failed, 0 skipped** (`python -m pytest -q --no-cov -rs`,
2026-09-07, ~132s). Incluye los tests de integración contra el dataset real
(antes condicionalmente saltados si el parquet no existía — hoy existe y
corren).

## N. Limitaciones que siguen abiertas (no resueltas por esta auditoría)

- Solo 4 meses de datos DMC reales (2022-01, 2022-12, 2024-02, 2025-02), una
  sola estación (330007, Rodelillo) — sigue sin backfill ampliado.
- `n_positive_evaluation_cases` sigue `null`: no existe una unidad de
  evaluación más fina que "raw episode" defendible sin una fuente externa.
- Ningún fold alcanza `event_support_status=ADEQUATE`. Fold 2025-02 tiene 0
  episodios (`INSUFFICIENT`).
- ~50 % de la señal positiva total del dataset depende de un solo evento
  regional de un día (sección H) — cualquier lectura de "el modelo
  funciona" que ignore esto sobrestima la generalización real.
- Cobertura DEM real ~60 % en las filas evaluadas (sección I).
- Esto sigue siendo (1) técnicamente limpio y (2) exploratoriamente medido;
  NO constituye (3) evidencia de capacidad predictiva validada.

## Fase 3 — Backfill DMC (2026-09-07)

Aprobado y ejecutado el mismo día. Resumen ejecutivo (detalle completo: `reports/backfill_dmc_330007_manifest.json`, `reports/temporal_dataset_h6_manifest.json`, `reports/experiment_abcd_h6_results.json`).

**Hallazgo que motivó la fase:** la baja cobertura histórica NO era una limitación de la fuente DMC — era que solo se habían descargado 4 meses de muestra. El endpoint mensual (`getDatosRecientesEma/{estación}/{año}/{mes}`, ya documentado en `src/config.py`) tiene datos reales para la estación 330007 desde al menos 2015, continuos hasta hoy.

**Período de backfill:** 2021-08-30 → 2026-08-29 (intersección DMC×FIRMS, elegida sin mirar dónde hay incendios). 61 meses calendario descargados (57 nuevos + 4 re-verificados idénticos a los ya existentes), 0 conflictos, 0 fallos, 0 duplicados. `scripts/backfill_dmc_historico.py` es idempotente (7 tests de regresión con red simulada).

| Métrica | Antes | Después |
|---|---:|---:|
| Meses DMC reales | 4 | 61 |
| Días con ≥1 lectura (período de solapamiento) | ~122 | 1,818 / 1,826 (99.6%) |
| forecast_times | 473 | 7,260 |
| Filas totales del dataset | 23,650 | 363,000 |
| Filas elegibles | 23,595 | 362,883 |
| Filas positivas | 46 | 107 |
| Raw episodes (un disparador/fila) | 26 | 79 |
| Raw episodes (unión, any-qualifying) | 31 | 84 |
| % filas con `meteo_actual` faltante | 1.5% (350) | 0.45% (1,650 de 363,000) |
| Folds temporalmente evaluables | 3 (uno de ellos INSUFFICIENT, 0 positivos) | **5** (1 ADEQUATE, 3 LIMITED, 1 no entrenable por clase minoritaria insuficiente) |
| Concentración del megaevento 2024-02-03 sobre el dataset completo | 50.0% (23/46) | 21.5% (23/107) — la cifra absoluta no cambió, bajó por dilución real |

**Bug real encontrado y corregido durante la Fase 3** (no parte del plan original, expuesto por los datos nuevos):
1. `load_regional_meteo_series` incluía en su glob los archivos `*_conflicto_*.json` que puede dejar el backfill — corregido para excluirlos explícitamente (3 tests nuevos).
2. Los forecast_time candidatos no estaban acotados al período de solapamiento exacto — el backfill descarga MESES CALENDARIO completos, así que sin este corte se habrían colado días de agosto de 2021/2026 fuera del rango aprobado. Corregido en `build_temporal_dataset.py` (el resample para lags sigue usando la serie completa; solo los candidatos de `forecast_time` se recortan).
3. `HistGradientBoostingClassifier` (early_stopping="auto") revienta con un `ValueError` genérico si la clase minoritaria del train tiene menos de 2 ejemplos — expuesto porque el fold `train=2021` tiene exactamente 1 positivo. Corregido: `run_fold` ahora reporta un error explicable por modelo en vez de abortar el script completo (2 tests nuevos).

**Folds temporalmente evaluables (walk-forward por año calendario — granularidad derivada de los datos, no elegida buscando mejor score):**

| Fold | Train | Test | n_test | positivos test | raw episodes | soporte |
|---|---|---|---:|---:|---:|---|
| 1 | 2021 | 2022 | 71,871 | 24 | — | no entrenable (train=2021 tiene 1 solo positivo) |
| 2 | 2021-2022 | 2023 | 72,981 | 19 | 16 | LIMITED |
| 3 | 2021-2023 | 2024 | 73,149 | 46 | 34 | **ADEQUATE** (primera vez en el proyecto) |
| 4 | 2021-2024 | 2025 | 72,143 | 7 | 6 | LIMITED |
| 5 | 2021-2025 | 2026 (parcial) | 48,190 | 10 | 8 | LIMITED |

**Suite de tests:** 445 passed, 0 failed, 0 skipped (incluye 12 tests nuevos de la Fase 3: 7 de `backfill_dmc_historico`, 3 de exclusión de archivos de conflicto, 2 del guard de clase minoritaria).

**No se tocó:** horizonte (6h), radio/gap de clustering (2km/6h), features A/B/C/D, modelo, cooldown, definición de target. La granularidad de fold (mes→año) fue el único ajuste estructural, requerido para que el walk-forward tuviera sentido con 5 años de datos en vez de 4 meses sueltos — no es una búsqueda de mejor score.

**Limitaciones que persisten:** el Fold 1 no es entrenable con los datos que trae 2021 solo; el Fold 3 (2024) es el único con soporte ADEQUATE y coincide con el año del megaevento de 2024-02-03; A/B/C/D siguen siendo resultados EXPLORATORIOS, no evidencia de capacidad predictiva validada — esta fase no cambió esa conclusión, solo la base de evidencia sobre la que se sostiene.

## Veredicto

**🟡 TÉCNICAMENTE LIMPIO, SOPORTE EMPÍRICO LIMITADO.**

La consistencia código↔parquet↔manifest está verificada de punta a punta con
pruebas permanentes contra datos reales (no solo fixtures), incluyendo
autoverificación del manifest en cada generación del dataset y
reproducibilidad del hash. Los bugs de trazabilidad y de conteo encontrados
en esta auditoría fueron corregidos y anclados con regresión. El volumen y
la concentración temporal de los datos disponibles (sección H, N) siguen
sin alcanzar el criterio de éxito acordado (≥2 particiones con mejora
consistente, soporte ADEQUATE) — no hay base aún para afirmar capacidad
predictiva, solo para seguir iterando el diseño del experimento con
confianza en que el propio pipeline no está mintiendo sobre lo que mide.

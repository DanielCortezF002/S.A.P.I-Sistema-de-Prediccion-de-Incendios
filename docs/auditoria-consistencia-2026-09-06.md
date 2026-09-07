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

## Veredicto

**🟡 TÉCNICAMENTE LIMPIO, SOPORTE LIMITADO.**

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

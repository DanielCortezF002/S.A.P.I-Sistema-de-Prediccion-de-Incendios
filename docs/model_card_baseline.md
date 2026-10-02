# Model Card — Modelo D (baseline experimental)

> **Estado científico: `scientific_model_validation = false`.** El Modelo D es el
> baseline experimental de S.A.P.I. Su score es un **ranking relativo** entre las 50
> celdas de una misma evaluación: **no es una probabilidad calibrada de incendio** y
> **no existe un umbral operacional científicamente validado**. Las métricas de esta
> tarjeta son exploratorias (el propio reporte de evaluación se declara "PRELIMINAR").

| Campo | Valor |
|---|---|
| Nombre | Modelo D (`prototype_model_d_v1`) |
| Artefacto | `models/prototype_model_d.pkl`, sha256 `ac017bef1f42a30ac74ba3e3787368c4418798b2d562adcfba01c923cff2173f` |
| Estado declarado en metadata | `PROTOTYPE / EXPLORATORY` |
| Algoritmo | `sklearn.ensemble.HistGradientBoostingClassifier` |
| Entrenado | 2026-09-09T16:25:16Z (`trained_at` embebido en el artefacto y en `models/prototype_model_d_metadata.json`) |
| Issue | SAPI-62 (Sprint 2). Base del repositorio: `4b0e2c8` |

## 1. Propósito y alcance

Ordenar las **50 celdas** de la grilla de estudio (VP-001…VP-050, corredor
Viña del Mar–Quilpué–precordillera, Región de Valparaíso) según su riesgo **relativo**
de recibir una nueva detección FIRMS en las próximas 6 horas `(T, T+6h]`, usando solo
información disponible hasta `T`. Cada celda es una caja de 0,0411° × 0,035°
(≈3,8 × 3,9 km, ≈15 km²) definida en `src/geo/grid.py`.

Pregunta que responde (`scripts/experiment_abcd.py`): *"dada la información disponible
antes de T, ¿podemos ordenar las celdas por riesgo relativo de recibir una nueva
detección FIRMS durante (T, T+h]?"*

## 2. Salida

- Un score por celda en [0, 1] que **solo sirve para ordenar** dentro de una evaluación.
- `rank` (posición única 1..50), `display_rank` (empates comparten la mejor posición,
  método min) y `tie_group_size`.
- En la corrida reproducible congelada (`forecast_time` 2026-09-01T00:00Z) los grupos de
  empate son de **41, 7 y 2 celdas**: el ranking tiene poca resolución y el sistema
  muestra el empate en vez de inventar un orden.

## 3. Algoritmo e hiperparámetros

- `HistGradientBoostingClassifier` con `max_depth=4`, `class_weight="balanced"`,
  `random_state=42`; el resto, valores por defecto de scikit-learn 1.9.0 (verificados en
  el artefacto: `learning_rate=0.1`, `max_iter=100`, `max_leaf_nodes=31`,
  `min_samples_leaf=20`, `l2_regularization=0.0`, `early_stopping="auto"`).
- Sin SMOTE ni remuestreo; sin XGBoost (el `.pkl` de XGBoost del repo es del pipeline
  legacy); **`cell_id` no es feature**.
- Se eligió porque maneja NaN de forma nativa, **no por desempeño**: `_prep_xy` no
  imputa nada (test `test_prep_xy_never_imputes_nan`).
- `class_weight="balanced"` distorsiona a propósito la escala de salida: por eso el
  score no se interpreta como probabilidad y no hay calibración.
- Script de entrenamiento: `scripts/build_prototype_model.py` (no se re-ejecutó para
  esta tarjeta).

## 4. Datos

| Elemento | Valor | Fuente |
|---|---|---|
| Dataset | `data/processed/temporal_dataset_h6.parquet`, sha256 `14b36ad8db680cf57f6e0c655cb0a1940ed4b4c63e810d59e470055babc530fe` (no versionado en git) | metadata del artefacto; `reports/temporal_dataset_h6_manifest.json` |
| Estructura | 50 celdas × 7 260 instantes (cada 6 h) = 363 000 filas; **362 883 elegibles** (117 excluidas por cooldown) | metadata `n_training_rows`; manifest del dataset |
| Positivos | **107 filas** | metadata `n_positive_rows` |
| Positivos por año | 2021 = 1, 2022 = 24, 2023 = 19, 2024 = 46, 2025 = 7, 2026 = 10 | folds de `reports/experiment_abcd_h6_results.json` |
| Periodo de entrenamiento | 2021-08-30 → 2026-08-29 18:00 UTC | metadata `training_start`/`training_end` |
| Detecciones | NASA FIRMS VIIRS, línea base congelada 2021-08-30 → 2026-08-30, sha256 `a9a85db4431b3e54f936b724e4de5a7fbb0cc19f5721f5e1a344a192bf9bb271` (copia versionada en `artifacts/hito1/reproducibility/firms/`) | `artifacts/hito1/reproducibility/manifest.json` |
| Meteorología | DMC, **una sola estación regional (330007)** aplicada a las 50 celdas | `docs/trazabilidad-current.md` |
| Topografía | elevación, pendiente y orientación por celda (DEM Copernicus GLO-30 vía OpenTopography) | `docs/arquitectura-hito1.md` |

**Desbalance de clases.** Con los conteos anteriores:

| Definición | Cálculo | Razón |
|---|---|---|
| Positivos sobre filas totales (cifra usada en Jira) | 363 000 / 107 | **≈ 1:3393** |
| Positivos sobre filas elegibles | 362 883 / 107 | ≈ 1:3391 |
| Positivos frente a negativos elegibles | 362 776 / 107 | ≈ 1:3390 |

**Concentración.** El año 2024 aporta 46 de los 107 positivos, y 23 de ellos ocurren en
un solo día (megaevento del 2024-02-03, `reports/megaevento_2024-02-03_report.json`):
el 21,5 % de todos los positivos del dataset.

## 5. Target y causalidad temporal

- **Target:** detección FIRMS válida en la celda dentro de `(T, T+6h]`. Las filas en
  cooldown quedan **excluidas** (nunca se etiquetan como negativo falso).
- **FIRMS son anomalías térmicas satelitales**, no incendios confirmados en terreno.
- **Causalidad:** toda feature usa solo información con `timestamp <= T`
  (`src/procesamiento/causality_validator.py`, `tests/test_causality_validator.py`).

## 6. Features (25, `FEATURES_D`)

| Grupo | Features |
|---|---|
| Historial FIRMS (2) | `historial_firms_count`, `dias_desde_ultimo_evento` (NaN = nunca hubo arribo antes de T) |
| Meteorología actual (4) | `meteo_actual_temp`, `meteo_actual_hr`, `meteo_actual_viento`, `meteo_actual_regla_30_30_30` |
| Lags meteorológicos (16) | `meteo_lag_{6,12,24,48}h_{temp,hr,viento,regla_30_30_30}` |
| Topografía (3) | `elevacion`, `pendiente`, `orientacion` |

## 7. Protocolo de evaluación (walk-forward)

`scripts/experiment_abcd.py` entrena por **bloques de año calendario**: cada fold
entrena con todos los años anteriores y evalúa en el año siguiente (sin
`train_test_split` aleatorio). Son 5 folds (test 2022–2026; 2026 parcial). Junto al
Modelo D se evalúan tres baselines ingenuos: azar, prevalencia e historial crudo sin
entrenar.

Importante: las métricas vienen de **re-entrenamientos walk-forward** del script
experimental, no del artefacto desplegado. El artefacto se entrenó con **todas** las
filas elegibles 2021–2026 y **no tiene un periodo de test retenido**.

## 8. Métricas por fold (Modelo D)

Fuente: `reports/experiment_abcd_h6_results.json`, reproducido exactamente el
2026-10-02 (sección 11). Valores redondeados a 4 cifras significativas; los exactos
están en el archivo.

| Fold (test) | Positivos train / test | Prevalencia test | PR-AUC | ROC-AUC | precision@3 | precision@5 | recall@3 | recall@5 | Soporte de episodios |
|---|---|---|---|---|---|---|---|---|---|
| 1 (2022) | 1 / 24 | 0,000334 | no entrenable (1 positivo en train) | — | — | — | — | — | — |
| 2 (2023) | 25 / 19 | 0,000260 | 0,0008561 | 0,6231 | 0,02381 | 0,01429 | 0,07143 | 0,07143 | LIMITED (16 episodios) |
| 3 (2024) | 44 / 46 | 0,000629 | 0,01069 | 0,8512 | 0,03175 | 0,04762 | 0,09524 | 0,1631 | ADEQUATE (34 episodios) |
| 4 (2025) | 90 / 7 | 0,0000970 | 0,0009183 | 0,6431 | 0,1111 | 0,1333 | 0,1667 | 0,5000 | LIMITED (6 episodios) |
| 5 (2026, parcial) | 97 / 10 | 0,000208 | 0,001026 | 0,8136 | 0,08333 | 0,05000 | 0,1250 | 0,1250 | LIMITED (8 episodios) |

Baselines ingenuos del mismo archivo, como referencia:

| Fold (test) | Mejor PR-AUC de un baseline | Mejor ROC-AUC de un baseline |
|---|---|---|
| 1 (2022) | 0,000524 (historial crudo) | 0,5933 (historial crudo) |
| 2 (2023) | 0,000325 (historial crudo) | 0,5772 (historial crudo) |
| 3 (2024) | 0,000874 (azar) | 0,5000 (prevalencia) |
| 4 (2025) | 0,000501 (historial crudo) | **0,7766 (historial crudo), mayor que el Modelo D (0,6431)** |
| 5 (2026) | 0,000589 (historial crudo) | 0,6231 (historial crudo) |

**Cómo leer estas métricas**
- **PR-AUC** se compara con la prevalencia del fold (lo que obtendría un score sin
  información): por ejemplo, 0,0107 frente a 0,000629 en 2024.
- **precision@K y recall@K son métricas de ranking, no de clasificación.** Para cada
  `forecast_time` del año de test con al menos una fila positiva, se toman las K celdas
  con mayor score: precision@K = aciertos / K y recall@K = aciertos / positivos de ese
  instante. Luego se promedian sobre esos instantes (14, 21, 6 y 8 instantes en los
  folds 2–5). **No equivalen a precision/recall de clasificación por umbral**: no se
  fabricó ningún umbral para producirlas.
- El **Brier score** del reporte se calcula sobre el score reescalado min-max y no es
  interpretable como calibración.
- **Criterio de éxito del proyecto no cumplido:** el reporte exige ≥2 particiones con
  mejora consistente y soporte ADEQUATE; solo el fold 2024 (el del megaevento) tiene
  soporte ADEQUATE.
- No hay intervalos de incertidumbre.

## 9. Limitaciones

- **Generalización no demostrada.** Ningún fold cumple el criterio de éxito del propio
  proyecto; el único con soporte adecuado es 2024 y está dominado por un solo día.
- **Desbalance severo:** 107 positivos (≈ 1:3393 sobre filas totales).
- **En 2025 un baseline sin entrenar supera al Modelo D en ROC-AUC** (0,777 frente a
  0,643).
- **Empates:** en el ranking congelado, 41 de 50 celdas comparten score. Con empates, la
  selección top-K dentro de un grupo empatado depende del orden de las filas; la
  evaluación es determinista (se reproduce idéntica), pero precision@K no refleja una
  preferencia real del modelo dentro del grupo.
- **Una sola estación meteorológica** para toda la grilla: la meteorología es contexto
  regional, no una medición por celda.
- **Dependencia espacial no modelada en la evaluación:** las métricas tratan cada fila
  (celda, T) como independiente, aunque celdas vecinas comparten meteorología y pueden
  compartir un mismo episodio FIRMS. Las cifras por fila pueden sobrestimar la cantidad
  de evidencia independiente.
- **Target:** anomalías térmicas FIRMS, no incendios confirmados; los "episodios" son un
  producto de clustering (radio 2 km, separación 6 h).
- **Sin periodo de test retenido** para el artefacto desplegado.
- **Reproducibilidad de software no es validación predictiva** (sección 11).

## 10. Uso permitido y no permitido

**Permitido:** apoyo exploratorio y académico para mostrar qué celdas tienen
**relativamente** más señal de riesgo según historial, meteorología y topografía,
siempre junto con la frescura de los datos y el aviso de que el score no es una
probabilidad.

**No permitido:**
- despachar recursos, emitir alertas públicas o cualquier uso de emergencia;
- presentar el score como probabilidad de incendio o fijarle un umbral de decisión;
- comparar riesgo con regiones fuera de la grilla;
- usarlo con datos atrasados sin mostrar el desfase;
- citar las métricas del fold 2024 como desempeño esperado en un año sin megaevento.

## 11. Reproducibilidad

| Nivel | Estado | Evidencia |
|---|---|---|
| Ranking de inferencia | **Idéntico bit a bit.** Fingerprint `33c2eacc49bd0cc130928b5bd182ec523e63614f0e3dd97a129a8d4657f231ff` (sha256 de `cell_id,score!r,rank` de las 50 celdas, modo `SAPI_REPRODUCIBILITY_MODE=1`, `forecast_time` 2026-09-01T00:00Z) | `tests/test_scoring_inputs.py`; sentinela RC-SCI-RANKING de la Release Gate |
| Evaluación walk-forward | **Reproducida exactamente el 2026-10-02.** `scripts/experiment_abcd.py` sin modificaciones, con el parquet `14b36ad8…` y el FIRMS `a9a85db4…` verificados por hash, terminó con exit 0 y produjo un `reports/experiment_abcd_h6_results.json` con el **mismo blob de git** que el versionado (`a7f6e9d97aad4e231d3d7b09e63a449ddd18b421`) y **0 diferencias numéricas** | Evidencia de SAPI-62 (`REPRODUCTION.md`) |
| Reentrenamiento desde un clon limpio | **No verificado** (R4 `NOT_VERIFIED_FROM_CLEAN_CLONE`): el parquet no está en git | `artifacts/hito1/reproducibility/manifest.json` |

Cómo reproducir la evaluación (sin tocar artefactos versionados):

1. Worktree limpio del repositorio, con el entorno de `requirements-dev.txt`
   (Python 3.14, scikit-learn 1.9.0).
2. Copiar a `data/processed/` el parquet `temporal_dataset_h6.parquet` y el CSV
   `nasa_firms_2021-08-30_2026-08-30.csv`, y verificar sus sha256 contra los de la
   sección 4.
3. Ejecutar `python scripts/experiment_abcd.py` (reescribe
   `reports/experiment_abcd_h6_results.json`) y confirmar con `git status` que el archivo
   quedó idéntico.

**Qué demuestra la reproducibilidad:** con los mismos datos, el mismo código y el mismo
artefacto se obtienen exactamente los mismos números. **Qué no demuestra:** que el
ranking sea correcto, útil o mejor que un baseline. Un modelo inútil también puede ser
perfectamente reproducible.

**Nota de trazabilidad:** `artifacts/hito1/reproducibility/manifest.json` menciona como
"fecha de entrenamiento original" el 2026-09-07; el artefacto versionado (sha256
`ac017bef…`) declara `trained_at` 2026-09-09T16:25Z tanto en su metadata embebida como en
el JSON. Esta tarjeta usa la fecha del propio artefacto.

## 12. Validación pendiente

`scientific_model_validation = false` se mantiene hasta que exista, como mínimo: una
evaluación walk-forward formal ligada por hash al dataset, métricas de ranking que traten
los empates, intervalos de incertidumbre, el reporte de 2024 con y sin el megaevento, y
una auditoría de fuga de información por fold.

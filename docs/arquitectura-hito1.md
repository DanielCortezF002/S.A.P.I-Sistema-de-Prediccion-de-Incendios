# Arquitectura S.A.P.I. — Hito 1 (pipeline temporal / prototipo real)

**Estado:** documento de trabajo. Describe la arquitectura del prototipo
tal como está implementada actualmente en el repositorio, construida
sobre artefactos derivados de fuentes reales (NASA FIRMS, DMC 330007,
Copernicus DEM) — no arquitectura aspiracional, no roadmap. La ejecución
demostrativa del prototipo puede operar sobre información histórica o
desactualizada y no constituye monitoreo operacional en tiempo real (ver
sección 9, frescura de datos). Fecha de auditoría: 2026-09-07.

## Índice

1. [Propósito](#1-propósito)
2. [Vista arquitectónica general](#2-vista-arquitectónica-general)
3. [Componentes](#3-componentes) (incluye Modelo lógico de datos)
4. [Flujo de datos](#4-flujo-de-datos)
5. [Entrenamiento vs. inferencia](#5-entrenamiento-vs-inferencia)
6. [Decisiones arquitectónicas](#6-decisiones-arquitectónicas)
7. [Flujo causal en T (Figura 2)](#7-flujo-causal-en-t-figura-2)
8. [Trazabilidad técnica](#8-trazabilidad-técnica)
9. [Límites y estado actual](#9-límites-y-estado-actual)

---

## 1. Propósito

Documentar la arquitectura **real, implementada y verificada en el
repositorio** del pipeline temporal de S.A.P.I. — la ruta que hoy alimenta
el modo "Prototipo (datos reales)" del dashboard. No cubre el pipeline
legacy (XGBoost/PostGIS) salvo para señalar dónde sigue existiendo y por
qué queda fuera del flujo principal (sección 9 y 12 del encargo).

**Formulación central del sistema** (usar esta, no una reformulación más
ambiciosa):

> S.A.P.I. estima y prioriza el riesgo relativo de nuevas detecciones de
> fuego en una grilla espacial, utilizando información disponible antes de
> la ventana futura.

No es una predicción de incendios, no es una probabilidad calibrada, no es
un sistema de alerta oficial. Una detección FIRMS es una detección
satelital — no un incendio confirmado en terreno.

## 2. Vista arquitectónica general

**Figura 1 — Arquitectura general**

```
┌─────────────────────────────┐
│           FUENTES            │
│                               │
│  NASA FIRMS (focos térmicos)  │
│  DMC estación 330007 Rodelillo│
│  (meteorología REGIONAL, una  │
│   sola estación — no 50)      │
│  Copernicus DEM GLO-30        │
│  (topografía estática)        │
└───────────────┬───────────────┘
                │
                ▼
┌───────────────────────────────┐
│   PROCESAMIENTO CAUSAL/ESPACIAL │
│                                 │
│  regional_meteo (serie única,   │
│    sin cell_id)                 │
│  episodes.assign_episodes       │
│    (radio 2 km / gap 6 h)       │
│  dem_features (topografía por   │
│    celda, join espacial)        │
│  temporal_features (lags,       │
│    historial FIRMS por celda,   │
│    todo con timestamp <= T)     │
└───────────────┬─────────────────┘
                │
                ▼
┌───────────────────────────────┐
│   DATASET TEMPORAL Y ESPACIAL   │
│                                 │
│  temporal_dataset_h6.parquet    │
│  unidad = (cell_id, forecast_   │
│  time), target = arribo FIRMS   │
│  nuevo en (T, T+6h]             │
└───────────────┬─────────────────┘
                │
                ▼
┌───────────────────────────────┐
│           MODELO D               │
│  HistGradientBoostingClassifier │
│  historial + meteo regional +   │
│  lags + topografía               │
│  (models/prototype_model_d.pkl) │
└───────────────┬─────────────────┘
                │
                ▼
┌───────────────────────────────┐
│  SCORE RELATIVO POR 50 CELDAS   │
│  score_current_grid(T)          │
└───────────────┬─────────────────┘
                │
                ▼
┌───────────────────────────────┐
│   RANKING / GRUPOS DE EMPATE     │
│  rank único (contrato interno)  │
│  display_rank + tie_group_size  │
│  (method="min", empates reales) │
└───────────────┬─────────────────┘
                │
                ▼
┌───────────────────────────────┐
│    DASHBOARD STREAMLIT           │
│  app/components/prototype_view  │
│  mapa + panel de detalle         │
└───────────────────────────────┘
```

La meteorología DMC entra **una sola vez por instante T** y se aplica
igual a las 50 celdas (línea horizontal conceptual, no 50 flechas
paralelas desde 50 estaciones inexistentes) — ver sección 6, primera
decisión.

## 3. Componentes

| Componente | Responsabilidad | Entrada | Salida | Implementación real |
|---|---|---|---|---|
| Ingesta FIRMS | Descarga y consolida focos térmicos NASA FIRMS (SP+NRT, idempotente) | Ventanas de fecha (máx. 5 días/llamada API) | CSV de focos + manifest | `src/ingesta/nasa_firms_backfill.py`; datos en `data/processed/nasa_firms_2021-08-30_2026-08-30.csv` |
| Ingesta DMC | Descarga histórico meteorológico de la estación 330007 (Rodelillo) | Rango mensual, endpoint `getDatosRecientesEma` | JSON crudo por mes | `scripts/backfill_dmc_historico.py`; datos en `data/raw/dmc_historico_330007_*.json` |
| Ingesta DEM | Descarga y cachea el modelo de elevación Copernicus GLO-30 (OpenTopography) | bbox acotado (`VALPARAISO_DEM_BBOX`) | GeoTIFF cacheado | `src/ingesta/dem_ingester.py` |
| Meteorología regional | Construye UNA serie temporal por estación, sin `cell_id` — nunca reetiqueta una lectura como propia de una celda | JSON crudo DMC | Serie `(station_id, momento, variables)` | `src/procesamiento/regional_meteo.py` → `load_regional_meteo_series()` |
| Clustering de episodios | Agrupa detecciones FIRMS en "raw episodes" por proximidad espacial/temporal | CSV de focos | Episodios con `event_id`, primer arribo por celda | `src/procesamiento/episodes.py` → `assign_episodes()`, `first_arrival_by_cell()` (radio 2 km, gap 6 h) |
| Topografía por celda | Extrae elevación/pendiente/orientación por celda desde el DEM | GeoTIFF + grilla | `elevacion`, `pendiente`, `orientacion` por `cell_id` | `src/procesamiento/dem_features.py` → `load_grid_topography()` |
| Features temporales | Calcula lags meteorológicos (0/6/12/24/48h) e historial FIRMS por celda, todo con `timestamp <= T` | Serie regional + episodios | Matriz de features "as of T" | `src/procesamiento/temporal_features.py` → `build_regional_meteo_features()`, `historial_firms_features()` |
| Definición del target | Define `target(cell,T,h)` como arribo FIRMS nuevo en `(T,T+h]`; excluye filas en cooldown (nunca las etiqueta 0) | Primeros arribos por celda | Filas `(cell_id, forecast_time, target, excluded)` | `src/procesamiento/target_builder.py` → `build_targets()` |
| Validación de causalidad | Verifica que ningún feature use información posterior a T | Dataset construido | Reporte pass/fail | `src/procesamiento/causality_validator.py` → `validate_temporal_causality()` |
| Constructor del dataset | Orquesta todo lo anterior en un dataset único, congelado al período 2021-08-30→2026-08-29 | Todas las fuentes | `temporal_dataset_h6.parquet` + manifest | `scripts/build_temporal_dataset.py` |
| Experimento A/B/C/D | Evalúa 4 conjuntos de features acumulativos con validación temporal walk-forward | Dataset temporal | Métricas por fold, definición de `FEATURES_D` | `scripts/experiment_abcd.py` |
| Entrenamiento del artefacto | Entrena el modelo final (Modelo D, sin tuning) sobre filas `eligible_for_training` | Dataset temporal | `models/prototype_model_d.pkl` + metadata | `scripts/build_prototype_model.py` |
| Servicio de inferencia | Única interfaz pública del prototipo: puntúa las 50 celdas para un `forecast_time` | Modelo + meteorología reciente + historial + topografía | `GridScoreResult` (scores, ranks, empates, frescura) | `src/inference/prototype_service.py` → `score_current_grid()` |
| Grilla espacial | Define las 50 celdas del corredor (geometría, centro, bordes) | — | Lista de celdas con bbox EPSG:4326 | `src/geo/grid.py` → `all_cells()` |
| Dashboard (modo Prototipo) | Renderiza mapa + panel de detalle a partir de `score_current_grid()` | `GridScoreResult` | UI Streamlit | `app/components/prototype_view.py` → `render_prototype_dashboard()` |
| Selector de modo | Decide entre modo Prototipo (datos reales, default) y modo Demo (seed sintético legacy) | `SAPI_DATA_MODE` / selección UI | Vista renderizada | `app/app.py` → `_resolve_dashboard_mode()` |

### Modelo lógico de datos

No es un modelo entidad-relación de base de datos (el prototipo no
persiste estas entidades en un motor relacional/PostGIS — ver sección 9).
Es el modelo lógico real de las entidades y artefactos que el pipeline
temporal produce y consume, con su clave/granularidad y su implementación
real:

| Entidad / artefacto | Clave o granularidad | Contenido principal | Relación | Implementación real |
|---|---|---|---|---|
| Grilla espacial | `cell_id` | Geometría (bbox EPSG:4326), centro y bordes de cada una de las 50 celdas del corredor | Unidad espacial base — el resto de las entidades se relacionan a través de `cell_id` | `src/geo/grid.py` → `all_cells()` |
| Serie meteorológica regional | `station_id` + `momento` | `temperatura`, `humedad_relativa`, `velocidad_viento_kmh` de la estación 330007 | Se aplica igual a las 50 celdas para un mismo `momento` — no tiene `cell_id` propio | `src/procesamiento/regional_meteo.py` → `load_regional_meteo_series()` |
| Detecciones / episodios FIRMS | `event_id` (agrupación algorítmica) + `cell_id` + `ignition_ts` | `latitude`, `longitude`, `ignition_ts`, `cell_id` asignado, `event_id` | Cada detección pertenece a un `event_id` (agrupación por proximidad espacial/temporal) y a una `cell_id` | `src/procesamiento/episodes.py` → `assign_episodes()`, `first_arrival_by_cell()` |
| Topografía | `cell_id` | `elevacion`, `pendiente`, `orientacion` (media zonal desde el DEM) | Una fila por `cell_id`, estática en el tiempo | `src/procesamiento/dem_features.py` → `load_grid_topography()` |
| Dataset temporal | `(cell_id, forecast_time)` | Features "as of T" (historial FIRMS, meteorología regional + lags, topografía) + target | Une grilla + meteorología regional + episodios + topografía en una fila por combinación | `scripts/build_temporal_dataset.py` → `build_dataset()` |
| Target | `(cell_id, forecast_time)` → `target` | `target=1` si existe un arribo FIRMS nuevo en la celda durante `T < t <= T+6h`; `excluded=True`/`target=None` (nunca 0) si la celda está en cooldown tras un arribo anterior | Depende de `first_arrival_by_cell()` y del `forecast_time` evaluado | `src/procesamiento/target_builder.py` → `build_targets()` |
| Artefacto Modelo D | `model_version` | Modelo entrenado (`HistGradientBoostingClassifier`) + `feature_columns` + `horizon_hours` + `status` | Entrenado sobre las filas `eligible_for_training` del dataset temporal, con la configuración fija Modelo D | `models/prototype_model_d.pkl` / `models/prototype_model_d_metadata.json` |
| Resultado de inferencia | `(cell_id, forecast_time)` | `score` relativo, `rank`, `display_rank`, `tie_group_size`, geometría, elevación, pendiente, historial | Una fila por `cell_id` para un `forecast_time` T, generada a partir del artefacto Modelo D | `src/inference/prototype_service.py` → `score_current_grid()`, dataclass `CellScore` |

Dos aclaraciones necesarias sobre este modelo, ya establecidas como reglas
no negociables del proyecto:

- **`cell_id` identifica la unidad espacial pero NO es un predictor
  directo.** El modelo no aprende "esta celda es peligrosa por su
  identidad"; aprende de las features reales (historial FIRMS,
  meteorología regional, topografía) que sí varían por celda.
- **`event_id` es una agrupación algorítmica de detecciones**
  (`assign_episodes()`, radio 2 km / gap 6 h, parámetros congelados), no
  la identidad de un incendio independiente confirmado en terreno.

## 4. Flujo de datos

**A. Pipeline de datos**

```
NASA FIRMS + DMC 330007 + Copernicus DEM
        ↓  (ingesta idempotente, cada fuente en su propio módulo)
data/raw/*.json (DMC) · data/processed/nasa_firms_*.csv (FIRMS) · GeoTIFF cacheado (DEM)
        ↓  (validación/procesamiento)
regional_meteo.load_regional_meteo_series() · episodes.assign_episodes() · dem_features.load_grid_topography()
        ↓  (características temporales y espaciales, timestamp <= T)
temporal_features.build_regional_meteo_features() + historial_firms_features()
```

Este tramo es compartido literalmente por el entrenamiento
(`scripts/build_temporal_dataset.py`) y por la inferencia
(`src/inference/prototype_service.py`) — ambos importan las mismas
funciones de `temporal_features.py`, no una reimplementación paralela. Es
la garantía real (no solo documental) de que "cómo se calcula un feature a
partir de T" tiene una única fuente de verdad.

## 5. Entrenamiento vs. inferencia

Son tres momentos distintos del pipeline, con artefactos y disparadores
distintos, que no deben confundirse entre sí. **El dashboard no entrena el
modelo, no lo selecciona ni lo recalibra.**

**Evaluación experimental** (`scripts/experiment_abcd.py`):

```
dataset temporal
       ↓
particiones temporales / walk-forward (train = bloques/años anteriores,
       test = bloque/año siguiente)
       ↓
evaluación de 4 configuraciones acumulativas de features (A/B/C/D)
```

Esta evaluación mide cómo se comportó cada configuración de features en
el pasado, sobre particiones temporales sucesivas. Es un experimento
aparte y congelado — **no calibra ni selecciona automáticamente** el
modelo que termina cargando el prototipo.

**Construcción del artefacto del prototipo** (`scripts/build_prototype_model.py`):

```
filas eligible_for_training del dataset temporal
       ↓
configuración fija "Modelo D": historial temporal + meteorología regional
       + lags causales + características topográficas por celda
       ↓
artefacto exploratorio (HistGradientBoostingClassifier, sin selección de
       modelos ni tuning de hiperparámetros)
       ↓
score_current_grid()
```

Modelo D es, en términos concretos, el conjunto de features del
experimento anterior más avanzado (identificador interno `FEATURES_D` en
`scripts/experiment_abcd.py`, ver trazabilidad técnica) — pero la
configuración se fija directamente, no se deriva de "qué ganó" en la
evaluación walk-forward. El resultado es un artefacto **exploratorio**
(`models/prototype_model_d.pkl`, `status="PROTOTYPE / EXPLORATORY"`), no
un modelo de producción.

**Inferencia del prototipo** (`src/inference/prototype_service.py::score_current_grid()`):
carga ese artefacto ya entrenado y lo usa para puntuar las 50 celdas en un
`forecast_time`. No hay entrenamiento, selección de modelo ni
recalibración en esta ruta — solo carga del artefacto y cálculo de
features nuevas para T.

| | Evaluación experimental | Construcción del artefacto | Inferencia del prototipo |
|---|---|---|---|
| Disparador | Manual: `python scripts/experiment_abcd.py` | Manual: `python scripts/build_temporal_dataset.py` → `python scripts/build_prototype_model.py` | Cada vez que el dashboard llama `score_current_grid()` (o se re-ejecuta manualmente) |
| Entrada | Dataset temporal completo (2021-08-30→2026-08-29) | Filas `eligible_for_training` del dataset temporal | Última meteorología regional real disponible (o un `forecast_time` explícito ≤ última lectura) |
| Qué produce | Métricas por fold para 4 configuraciones (A/B/C/D) — no un artefacto que el dashboard cargue | `models/prototype_model_d.pkl` + `prototype_model_d_metadata.json` | `GridScoreResult` en memoria (scores, ranks, frescura) — no se persiste como artefacto |
| Frecuencia real hoy | Ad hoc, cuando cambia la metodología del experimento | Ad hoc, cuando se regenera el dataset o se re-entrena tras un cambio | Cada carga del dashboard en modo Prototipo (sin caché entre sesiones más allá de `st.cache_data` de Streamlit) |

## 6. Decisiones arquitectónicas

| Decisión | Motivo | Alternativa descartada | Consecuencia |
|---|---|---|---|
| DMC regional (una serie, sin `cell_id`) vs. espacialización artificial | La versión anterior (`DataProcessor._load_meteo()`) asignaba una lectura de Rodelillo a 50 celdas por **posición de fila**, disfrazando ~50 minutos de una estación como 50 ubicaciones distintas (hallazgo real, `scripts/auditoria_integridad_datos.py`) | Interpolar/simular meteorología por celda a partir de una sola estación | El sistema es honesto sobre su soporte meteorológico real (1 estación), a costa de no capturar variación espacial fina del clima |
| Joins temporales causales/as-of-T | Cualquier feature con información posterior a T invalida la evaluación de un sistema que pretende puntuar "riesgo futuro" | Joins que miren hacia adelante (más simples de implementar, más fáciles de que "funcionen mejor" en retrospectiva) | Verificable explícitamente vía `causality_validator.validate_temporal_causality()`, a costa de descartar/excluir filas cuando no hay dato causal disponible |
| Manejo nativo de NaN (`HistGradientBoostingClassifier`) vs. imputación generalizada | Imputar (media/mediana/cero) inventa información que no existe — especialmente grave para DEM faltante o meteorología ausente | Imputación estándar (`SimpleImputer`) para poder usar cualquier clasificador | El modelo aprende directamente de la ausencia de dato (flags `{block}_missing`), a costa de limitarse a modelos con soporte nativo de NaN |
| Separación Demo / Prototipo (módulos distintos, sin imports cruzados) | Evitar que datos sintéticos de demo se mezclen, aunque sea accidentalmente, con el ranking real — verificado con un test dedicado (`test_no_legacy_imports_in_prototype_modules`) | Un único módulo de vista con una bandera `is_demo` | Duplica algo de código de presentación entre `app/components/prototype_view.py` y la ruta demo, a cambio de aislamiento verificable |
| Ranking relativo vs. probabilidad operacional | Con muy pocos positivos históricos, el modelo produce empates masivos de score (41/50 celdas en la corrida más reciente) — presentar eso como probabilidad calibrada sería engañoso | Calibrar el score (Platt/isotonic) y presentarlo como probabilidad de incendio | El dashboard muestra `rank`/`display_rank`/`tie_group_size` (ranking honesto con empates visibles), nunca un número tipo "72% de probabilidad" |

## 7. Flujo causal en T (Figura 2)

**Figura 2 — Flujo causal de una predicción en T**

```
forecast_time T
       │
       ▼
información disponible <= T
  (regional_meteo hasta T, historial FIRMS hasta T, topografía estática)
       │
       ▼
construcción de features para 50 celdas
  (build_feature_matrix: misma meteorología regional para las 50 celdas,
   historial FIRMS y topografía SÍ varían por celda)
       │
       ▼
Modelo D
  (HistGradientBoostingClassifier, predict_proba)
       │
       ▼
scores relativos por celda
  (score_by_cell, sin calibración de probabilidad)
       │
       ▼
ranking + grupos de empate
  (rank único / display_rank method="min" / tie_group_size)
       │
       ▼
mapa (dashboard Streamlit)
```

Nota de honestidad temporal: si `forecast_time` no se especifica,
`score_current_grid()` usa el último bucket real con lectura DMC — nunca
inventa meteorología futura. Si se pide un T posterior a la última lectura
real, el servicio falla explícitamente (`PrototypeUnavailableError`) en vez
de extrapolar.

## 8. Trazabilidad técnica

| Pieza conceptual | Archivo real | Función/símbolo |
|---|---|---|
| Meteorología regional | `src/procesamiento/regional_meteo.py` | `load_regional_meteo_series()` |
| Clustering de episodios | `src/procesamiento/episodes.py` | `assign_episodes()`, `first_arrival_by_cell()` |
| Topografía por celda | `src/procesamiento/dem_features.py` | `load_grid_topography()` |
| Features temporales (lags, historial) | `src/procesamiento/temporal_features.py` | `build_regional_meteo_features()`, `historial_firms_features()`, `LAG_HOURS = (0, 6, 12, 24, 48)` |
| Definición del target | `src/procesamiento/target_builder.py` | `build_targets()`, `TargetRow` |
| Validación de causalidad | `src/procesamiento/causality_validator.py` | `validate_temporal_causality()` |
| Construcción del dataset de entrenamiento | `scripts/build_temporal_dataset.py` | `build_dataset()`; `PERIOD_START`/`PERIOD_END` = 2021-08-30 / 2026-08-29 |
| Definición de Modelo D | `scripts/experiment_abcd.py` | `FEATURES_D` (= `FEATURES_C` + `elevacion`,`pendiente`,`orientacion`), `run_fold()` |
| Entrenamiento del artefacto | `scripts/build_prototype_model.py` | genera `models/prototype_model_d.pkl` / `models/prototype_model_d_metadata.json` |
| Grilla espacial | `src/geo/grid.py` | `all_cells()` |
| Servicio de inferencia (única interfaz pública) | `src/inference/prototype_service.py` | `score_current_grid()`, `build_feature_matrix()`, `classify_freshness()`, dataclasses `CellScore`/`GridScoreResult` |
| Vista del dashboard (modo Prototipo) | `app/components/prototype_view.py` | `render_prototype_dashboard()` |
| Selector de modo | `app/app.py` | `_resolve_dashboard_mode()`, `_MODE_PROTOTIPO` |
| Configuración de modo | `src/config.py` | `SAPI_DATA_MODE` (default `"prototype"`) |
| Catálogo de estaciones DMC | `src/procesamiento/station_catalog.py` | estación `330007` = "Rodelillo, Ad." |
| Test de aislamiento demo/prototipo | `tests/test_prototype_service.py` | `test_no_legacy_imports_in_prototype_modules()` |

## 9. Límites y estado actual

- **Una sola estación meteorológica (DMC 330007, Rodelillo).** Toda
  meteorología en el sistema es regional, aplicada igual a las 50 celdas
  para un mismo instante — no hay, ni se simula, variación meteorológica
  espacial fina entre celdas.
- **Los datos mostrados pueden ser históricos/desactualizados.** El
  dashboard clasifica la frescura de la lectura meteorológica usada
  (`classify_freshness()`: RECIENTE ≤12h, CON RETRASO ≤24h, HISTÓRICO
  >24h) y lo muestra explícitamente — no asume que el ranking corresponde
  al momento en que alguien abre la aplicación.
- **Es un prototipo local**, ejecutado on-demand (`streamlit run
  app/app.py`), no un servicio desplegado ni con SLA.
- **No existe un pipeline diario automatizado para esta ruta.** El único
  orquestador diario del repositorio, `src/pipeline/run_daily.py`,
  ejecuta el pipeline **legacy** (`DataProcessor`, `BaselineModel`,
  `XGBoostOptimizer`) — no está conectado a `regional_meteo` / `episodes`
  / Modelo D. Hoy, el dataset temporal y el artefacto del prototipo se
  regeneran manualmente.
- **Integración con CONAF: pendiente.** No existe ningún componente en
  este repositorio que consuma o publique hacia sistemas de CONAF/
  SENAPRED.
- **PostGIS no es parte de la ruta operacional del prototipo.** El
  servicio de inferencia (`src/inference/prototype_service.py`) lee
  directamente de `data/raw/` y `data/processed/` (JSON/CSV/parquet) — no
  importa `src.db` ni ningún módulo de persistencia PostGIS. Las
  referencias a PostGIS en el repositorio (`src/db.py`,
  `src/procesamiento/persister.py`, `src/query/*`, `src/modelo/*`,
  `docker-compose.yml`, `docker/initdb/01_extensions.sql`) pertenecen
  exclusivamente al pipeline legacy y no deben presentarse como parte del
  flujo del prototipo.
- **El score no es una probabilidad calibrada de incendio.** Es un
  ranking relativo exploratorio (`predict_proba` de un modelo sin
  calibración ni tuning), con empates masivos reales en las corridas
  actuales por la escasez de positivos históricos — el dashboard expone
  esto vía `display_rank`/`tie_group_size`, nunca como un ranking más
  granular de lo que el modelo realmente produce.
- **La evidencia experimental es limitada y exploratoria.** Las métricas
  de `scripts/experiment_abcd.py` (fuera de alcance de este documento,
  ver instrucción #15) describen un experimento con validación temporal
  walk-forward sobre un único horizonte (6 h) y un único corredor
  geográfico — no constituyen, por sí solas, evidencia de capacidad
  predictiva generalizable.
- **Las características topográficas pueden contener valores faltantes.**
  Cuando una celda no tiene cobertura válida del raster DEM (o la celda
  cae fuera de su extensión), `dem_features` conserva ese valor como
  `NaN` — nunca lo convierte artificialmente en cero (`_zonal_mean()` /
  `_zonal_circular_mean_deg()` en `src/procesamiento/dem_features.py`).
  El modelo, al usar `HistGradientBoostingClassifier`, maneja estos `NaN`
  de forma nativa sin necesidad de imputación (ver sección 6).
- **`demo_seed` y la ruta legacy quedan fuera del flujo principal.** El
  modo Demo (`app/utils/demo_seed.py`, seleccionable en
  `app/app.py::_resolve_dashboard_mode()`) usa datos sintéticos
  explícitamente etiquetados (`data_source=demo_seed`, "Nota: seed zonal
  demo (no alerta oficial CONAF/SENAPRED)") y nunca se mezcla con el
  pipeline temporal — verificado por un test dedicado (sección 8). El
  modelo `models/xgboost_optimized.pkl` y los módulos bajo `src/modelo/`
  pertenecen igualmente al pipeline legacy, no al prototipo aquí
  documentado.

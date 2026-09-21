# S.A.P.I. — Architecture & Stack Freeze — Sprint 2

Fecha: 2026-09-20

Este documento congela la arquitectura tecnológica base de S.A.P.I. para
Sprint 2, a partir de la auditoría técnica del repositorio ya cerrada
(código, datasets y ruta PostGIS verificados directamente contra el
código real, no contra documentación previa). Es la referencia formal
antes de crear tickets en Jira o de iniciar implementación de Sprint 2.

Marco de referencia que se mantiene en todo el documento:
- "Target positivo" = detección/arribo FIRMS válido en la ventana
  `T < t <= T+6h`. **Nunca** "ignición confirmada" ni "ignición real":
  FIRMS es un detector satelital de anomalías térmicas, no una
  confirmación de incendio en terreno.
- Todo número de rendimiento de Modelo D es exploratorio. Este
  documento no evalúa desempeño; solo congela stack y baseline.

---

## 1. Baseline verificado

### Modelo D (baseline actual)
- Algoritmo: `HistGradientBoostingClassifier` (`sklearn.ensemble`).
- Hiperparámetros relevantes: `max_depth=4`, `class_weight="balanced"`.
- SMOTE: **NO** usado (no hay `imblearn` ni resampling en el pipeline de
  entrenamiento; el desbalance de clases se maneja únicamente vía
  `class_weight="balanced"`).
- XGBoost: **NO** usado por Modelo D (el `.pkl` de XGBoost que existe en
  `models/xgboost_optimized.pkl` pertenece al pipeline legacy, no al
  prototipo activo).
- Fuente: `scripts/build_prototype_model.py`.

### Entrenamiento (training)
- Fuente de datos: `data/processed/temporal_dataset_h6.parquet`.
- PostgreSQL/PostGIS: **NO** — `build_prototype_model.py` no importa
  `src.db` ni `PredictionQuery`; lee exclusivamente el parquet.

### Inferencia (serving del prototipo)
- Fuentes de datos: CSV de FIRMS (histórico de detecciones), JSON de
  meteorología DMC (series por estación), TIF de DEM (elevación,
  pendiente, orientación), artefacto `.pkl` del modelo entrenado.
- PostgreSQL/PostGIS: **NO** — `src/inference/prototype_service.py::
  score_current_grid()` no abre ninguna conexión a base de datos; su
  propio docstring declara explícitamente que nunca importa el pipeline
  legacy ni `matriz_features`.

### PostGIS actual
- Implementación real existente: extensión `postgis` habilitada,
  tablas `matriz_features` y `predicciones_riesgo` con columnas
  `GEOMETRY(...,4326)` e índices GiST (`docker/initdb/`), y código
  funcional de escritura (`persist_features_to_postgis()` en
  `src/procesamiento/persister.py`) y lectura (`PredictionQuery` en
  `src/query/prediction_query.py`).
- Utilizada únicamente por la ruta legacy: `src/modelo/baseline.py`,
  `optimizer.py`, `inference_engine.py`, `src/ingesta/parallel_ingester.py`,
  y un script de prueba suelto (`test_persistence_postgis.py`). Ninguno
  de estos módulos es parte de la ruta activa de Modelo D
  (`build_prototype_model.py` → `score_current_grid()`).
- **Clasificación: `LEGACY_ONLY`.** El esquema y el código PostGIS
  existen y funcionan, pero hoy no forman parte del pipeline de
  entrenamiento ni de inferencia que produce el ranking que ve el
  dashboard en modo Prototipo.

### Dataset (`temporal_dataset_h6.parquet`)
- 50 celdas (`VP-001`…`VP-050`) × 7.260 timestamps cada una, frecuencia
  6h, sin huecos — grilla regular celda×tiempo.
- 363.000 filas totales; 362.883 elegibles para entrenamiento
  (`eligible_for_training=True`); 117 filas excluidas.
- 107 filas con target positivo (detección FIRMS válida en
  `T < t <= T+6h`). **Nunca** llamarlo "ignición confirmada".
- Distribución por año: 2021=1, 2022=24, 2023=19, 2024=46, 2025=7,
  2026=10.
- Concentración espacial: 39 de 50 celdas tienen al menos un positivo
  (11 celdas en cero); top 5 celdas (VP-038, VP-028, VP-033, VP-035,
  VP-040) concentran 31/107 = 29,0% de los positivos.
- **Contexto obligatorio sobre 2024:** de los 46 positivos de 2024, 23
  (el 50%) provienen de un único día calendario, 2024-02-03 (un
  megaevento de 26 episodios crudos distintos que afectó 14 celdas
  simultáneamente — ver `reports/megaevento_2024-02-03_report.json`).
  Esas 23 filas representan además el 21,5% de TODO el dataset. Ningún
  fold de validación temporal que incluya ese día debe leerse como
  "rendimiento típico": concentra una fracción desproporcionada de toda
  la señal positiva disponible.

### 2025
- 72.150 filas.
- 7 target positivos.

---

## 2. Stack congelado para Sprint 2

| Componente | Elección | Estado |
|---|---|---|
| Frontend | Streamlit | `KEEP` |
| Backend de aplicación | Spring Boot + Java | `ADOPT` |
| Servicio ML | FastAPI + Python | `ADOPT` |
| Modelo baseline | HistGradientBoostingClassifier / Modelo D | `KEEP_BASELINE` |
| Persistencia | PostgreSQL + PostGIS | `ADOPT_FOR_NEW_PIPELINE` |
| Metadata flexible | PostgreSQL JSONB | `ADOPT_WHEN_JUSTIFIED` |
| Infraestructura local | Docker + Docker Compose | `ADOPT` |
| Comunicación | REST + OpenAPI | `ADOPT` |
| Cloud | (sin definir) | `REQUIRED_BUT_PROVIDER_OPEN` |
| Flutter | — | `DEFERRED` |
| MongoDB | — | `NOT_ADOPTED` |

**Motivo `NOT_ADOPTED` para MongoDB:** no existe todavía necesidad
técnica que justifique una segunda base de datos. Todo lo que hoy se
consideraría "documento flexible" (metadata de corridas, configuración
de experimentos) cabe en `JSONB` sobre la misma instancia PostgreSQL
que ya provee PostGIS, sin el costo operacional de un segundo motor de
persistencia.

---

## 3. Arquitectura objetivo

```
Streamlit  →  Spring Boot (backend)  →  FastAPI (servicio ML)  →  Modelo D / experimentos temporales
                     ↓                          ↓
              PostgreSQL/PostGIS  ←──────────────
```

### Responsabilidades y límites por componente

- **Streamlit** — capa de presentación exclusivamente. Renderiza mapas,
  rankings y controles. No contiene lógica de negocio ni acceso directo
  a PostgreSQL: consume la API pública expuesta por Spring Boot. Rol
  actual (`KEEP`) se mantiene tal cual, migrando sus llamadas internas
  (`score_current_grid()` importado en proceso) a llamadas HTTP contra
  el backend.

- **Spring Boot (backend de aplicación)** — **quién expone la API
  pública.** Punto único de entrada externo (REST/OpenAPI). Orquesta
  solicitudes de Streamlit hacia el servicio ML, aplica autenticación/
  autorización, valida contratos de entrada/salida, y es responsable de
  **registrar ejecuciones/resultados** (auditoría de cada request de
  scoring: cuándo, qué `forecast_time`, qué versión de modelo, qué
  resultado). No ejecuta inferencia ni contiene lógica de ML.

- **FastAPI (servicio ML)** — **quién ejecuta inferencia.** Encapsula
  `score_current_grid()` y el ciclo de vida del artefacto `.pkl` de
  Modelo D (carga, versión, metadata). Expone un endpoint interno
  (no público) que Spring Boot consume. No conoce a Streamlit ni
  gestiona autenticación de usuarios finales — su único cliente es el
  backend de aplicación.

- **Modelo D / experimentos temporales** — la lógica de scoring en sí
  (hoy `HistGradientBoostingClassifier`; candidatos temporales en
  evaluación, ver sección 5). Vive dentro del proceso FastAPI, no como
  componente separado.

- **PostgreSQL/PostGIS** — **quién accede/escribe persistencia** y
  **quién maneja datos geoespaciales.** Fuente de verdad operacional
  para el pipeline nuevo: features geoespaciales por celda (`geom
  GEOMETRY(POLYGON,4326)`), predicciones persistidas, y (vía JSONB)
  metadata de corridas cuando se justifique. Tanto Spring Boot como
  FastAPI pueden leer/escribir, pero solo Spring Boot es responsable de
  las escrituras de auditoría/registro; FastAPI solo persiste
  resultados de inferencia cuando el backend se lo solicita.

### Evitar duplicación de lógica

- Una sola fuente de verdad para "cómo se calcula una feature a partir
  de T": las funciones ya existentes en `src/procesamiento/` (usadas
  hoy tanto por entrenamiento como por inferencia) se reutilizan sin
  reescribir dentro del servicio FastAPI — no se reimplementa feature
  engineering en Java.
- Spring Boot no reimplementa reglas de negoción de features ni
  formatea scores de riesgo: consume la respuesta de FastAPI y la
  reexpone tal cual (más metadata de auditoría) a Streamlit.
- El esquema de base de datos (`matriz_features`, `predicciones_riesgo`)
  se define una sola vez (SQL en `docker/initdb/`) y ambos servicios lo
  comparten vía el mismo motor PostgreSQL — no hay una copia de esquema
  por servicio.

---

## 4. Vertical slice para próxima revisión

Mínimo demostrable profesional, no confundir con el alcance completo
de Sprint 2:

```
Streamlit → Spring Boot → FastAPI → Modelo D → respuesta real → persistencia PostgreSQL/PostGIS
```

Criterios de aceptación del slice:
- Un único `forecast_time` real (dato existente, no sintético)
  atraviesa las cuatro capas y produce un ranking de las 50 celdas.
- Spring Boot registra la ejecución (timestamp, forecast_time, versión
  de modelo) en PostgreSQL.
- El resultado de scoring se persiste en `predicciones_riesgo` (o
  tabla equivalente del pipeline nuevo) vía PostGIS.
- Todo el slice se levanta con **Docker Compose** (Streamlit + Spring
  Boot + FastAPI + PostgreSQL/PostGIS en contenedores, una sola
  invocación).
- No requiere: autenticación real, UI pulida, cobertura de los otros
  84 experimentos/modelos — solo demostrar que el camino de extremo a
  extremo funciona con datos reales.

---

## 5. Modelamiento Sprint 2

- **Modelo D permanece baseline.** No se reemplaza ni se compite
  todavía contra un candidato ganador declarado.
- Se mantiene la **validación temporal walk-forward causal** ya usada
  en `scripts/experiment_abcd.py` — ningún fold de evaluación puede
  usar información posterior a la fecha que evalúa.
- **RNN/LSTM: `EXPERIMENTAL_CANDIDATE`.** La estructura temporal ya
  está disponible en el dataset (grilla regular celda×tiempo, sin
  necesidad de reshaping estructural), pero 107 target positivos
  repartidos en 39 celdas (30 de ellas con ≤2 eventos) implican
  evidencia escasa para entrenar y validar una arquitectura secuencial
  con confianza. No se afirma que LSTM vaya a rendir mejor ni peor que
  Modelo D — queda pendiente de evaluación comparativa.
- La evaluación comparativa posterior debe usar métricas adecuadas
  para clase fuertemente desbalanceada (p. ej. PR-AUC, recall a
  precisión fija, calibración), no accuracy ni ROC-AUC como criterio
  único.
- **2024 requiere contextualización adicional en cualquier evaluación**
  por el megaevento del 2024-02-03 (23 de 46 positivos del año, y 21,5%
  de todo el dataset, en un solo día). Un fold walk-forward que
  atraviese esa fecha debe reportarse por separado de folds "típicos",
  y ningún resultado de ese fold debe generalizarse como desempeño
  esperado en un año sin megaeventos.
- Ninguna evaluación de años anteriores puede usar información futura
  (esto ya es una invariante del pipeline actual — `feature_timestamp
  <= T` por construcción — y se mantiene como requisito no negociable
  para cualquier modelo nuevo que se pruebe).

---

## 6. ADRs a crear

### ADR-001 — Spring Boot como backend de aplicación
- **Contexto:** el prototipo actual no tiene una capa de backend
  separada; Streamlit importa y ejecuta la lógica de inferencia en el
  mismo proceso. Sprint 2 requiere una API pública auditable y
  desacoplada de la capa de presentación.
- **Decisión:** adoptar Spring Boot (Java) como backend de aplicación,
  responsable de exponer la API pública y registrar ejecuciones.
- **Alternativas consideradas:** extender FastAPI para exponer también
  la API pública (descartado: mezclaría responsabilidades de ML y de
  aplicación); Node/Express (descartado por falta de precedente en el
  proyecto/equipo).
- **Consecuencias:** dos lenguajes en el stack (Java + Python);
  necesidad de contrato REST/OpenAPI explícito entre capas.
- **Riesgos:** curva de aprendizaje si el equipo no tiene experiencia
  previa en Spring Boot; sobrecarga de mantener dos runtimes.
- **Estado:** propuesto.

### ADR-002 — FastAPI como servicio ML
- **Contexto:** la inferencia de Modelo D hoy vive embebida en
  `src/inference/prototype_service.py`, importada directamente por la
  app Streamlit. Se necesita aislar el servicio ML para que pueda
  evolucionar (nuevos modelos, incluyendo candidatos temporales) sin
  tocar la capa de presentación ni el backend de aplicación.
- **Decisión:** adoptar FastAPI como servicio ML dedicado, consumido
  únicamente por el backend Spring Boot.
- **Alternativas consideradas:** Flask (descartado: sin validación de
  tipos nativa ni generación de OpenAPI); mantener la inferencia
  embebida en Streamlit (descartado: no escalable ni auditable).
- **Consecuencias:** un servicio Python adicional a desplegar y
  versionar independientemente del backend.
- **Riesgos:** latencia de red entre Spring Boot y FastAPI si no se
  colocan en la misma red/infra; necesidad de versionar el contrato de
  features esperado por el modelo.
- **Estado:** propuesto.

### ADR-003 — PostgreSQL/PostGIS como persistencia operacional
- **Contexto:** el esquema PostGIS ya existe y funciona
  (`docker/initdb/`), pero está clasificado `LEGACY_ONLY` — no forma
  parte del pipeline activo de Modelo D.
- **Decisión:** adoptar PostgreSQL/PostGIS como persistencia
  operacional del pipeline nuevo (features geoespaciales,
  predicciones, metadata JSONB), en vez de descartarlo o introducir un
  motor distinto.
- **Alternativas consideradas:** seguir 100% en Parquet/CSV como hoy
  (descartado para Sprint 2: sin capacidad de escritura concurrente
  desde múltiples servicios ni de índice espacial en consultas del
  backend); MongoDB para metadata flexible (descartado, ver sección 2).
- **Consecuencias:** reactivar y adaptar el código legacy de
  persistencia (`persister.py`) en vez de reescribirlo desde cero.
- **Riesgos:** el esquema actual (`UNIQUE(cell_id, fecha)`) fue
  diseñado para el pipeline legacy diario, no para el pipeline temporal
  de 6h de Modelo D — puede requerir ajuste de granularidad temporal
  antes de reutilizarse tal cual.
- **Estado:** propuesto.

### ADR-004 — Docker Compose para entorno reproducible
- **Contexto:** hoy existen `Dockerfile.analytics`, `Dockerfile.web` y
  un `docker-compose.yml`, pero no cubren el vertical slice de 4 capas
  (Streamlit + Spring Boot + FastAPI + PostgreSQL/PostGIS).
- **Decisión:** extender Docker Compose para levantar las cuatro capas
  del vertical slice con una sola invocación.
- **Alternativas consideradas:** Kubernetes local (descartado por
  sobre-ingeniería para el alcance de Sprint 2).
- **Consecuencias:** un `docker-compose.yml` con más servicios y
  dependencias de arranque (`depends_on`, healthchecks) que coordinar.
- **Riesgos:** tiempos de build más largos con dos runtimes (JVM +
  Python) en el mismo compose.
- **Estado:** propuesto.

### ADR-005 — REST/OpenAPI como contratos entre servicios
- **Contexto:** se necesita un contrato explícito y versionable entre
  Streamlit↔Spring Boot y Spring Boot↔FastAPI.
- **Decisión:** usar REST con especificación OpenAPI para ambos
  contratos.
- **Alternativas consideradas:** gRPC (descartado: mayor complejidad
  de tooling para el tamaño actual del equipo/proyecto).
- **Consecuencias:** documentación de API generable automáticamente
  desde ambos frameworks (Spring Boot y FastAPI la soportan
  nativamente).
- **Riesgos:** ninguno significativo identificado más allá del
  overhead normal de mantener specs sincronizadas.
- **Estado:** propuesto.

### ADR-006 — Modelo D como baseline y modelos temporales como experimento
- **Contexto:** existe evidencia verificada (sección 1) de qué modelo
  corre hoy en producción/prototipo y con qué datos. Hay interés en
  evaluar arquitecturas secuenciales (RNN/LSTM) dado que el dataset ya
  tiene estructura temporal por celda.
- **Decisión:** Modelo D (`HistGradientBoostingClassifier`) queda
  formalmente congelado como baseline de Sprint 2. Cualquier modelo
  temporal es un experimento paralelo, no un reemplazo, hasta pasar por
  evaluación comparativa con métricas para clase desbalanceada y
  validación walk-forward causal.
- **Alternativas consideradas:** promover directamente un modelo
  temporal a baseline sin comparación (descartado: 107 positivos son
  evidencia insuficiente para esa afirmación sin evaluación formal).
- **Consecuencias:** el vertical slice (sección 4) y el servicio
  FastAPI se construyen alrededor de la interfaz de Modelo D; un
  modelo temporal futuro debe respetar la misma interfaz de entrada/
  salida para poder sustituirlo sin rediseñar las capas superiores.
- **Riesgos:** si el experimento temporal nunca alcanza evidencia
  suficiente, el baseline podría quedar congelado más tiempo del
  previsto — aceptable dado el estado actual de los datos.
- **Estado:** propuesto.

*(Ningún ADR selecciona todavía proveedor cloud — ver sección 7.)*

---

## 7. Decisiones abiertas

Se mantienen explícitamente abiertas, sin resolver en este freeze:

- Proveedor cloud.
- Modelo ML final (Modelo D vs. candidatos temporales).
- Diseño físico exacto de tablas para Sprint 2 (más allá del esquema
  legacy heredado — granularidad temporal, índices, particionamiento).
- Alcance académico completo de Sprint 2, hasta recibir pauta.
- Eventual frontend Flutter.

---

## 8. Veredicto

```
ARCHITECTURE_FREEZE: READY
SPRINT2_STACK: FROZEN
MODEL_D_BASELINE: FROZEN
TEMPORAL_MODEL_SELECTION: OPEN
CLOUD_PROVIDER: OPEN
JIRA_READY: YES
```

---

## 9. Baseline reproducible de tests — Sprint 2

**Entorno canónico: Docker.** La verificación reproducible del baseline de
tests de Sprint 2 se hace ejecutando `pytest` dentro de un contenedor
construido desde `Dockerfile.analytics` (`docker build --no-cache`, sin
volúmenes montados, usando exclusivamente lo que `COPY . .` trae del build
context filtrado por `.dockerignore`). Cualquier pipeline de CI futuro debe
reproducir exactamente este flujo — o invocarlo directamente — para que sus
resultados puedan compararse contra este baseline.

La ejecución en el `.venv` del host (entorno de desarrollo local) es
auxiliar, no canónica: puede mostrar un número distinto de tests
ejecutados/saltados porque el disco local de un desarrollador puede tener
artefactos generados en sesiones previas (`data/raw/*`, `data/processed/*`)
que están en `.gitignore` y por lo tanto nunca están presentes en un clon
limpio, en Docker, ni en CI. Un resultado "más verde" en el host (p. ej.
487 passed / 0 skipped) no es más confiable que el de Docker — es menos
reproducible, porque depende de archivos que no viven en git.

**Commit verificado:** `e573adc54a0d234507457af99e2deca27a874905`

**Resultados canónicos (Docker, commit de arriba):**

```
TESTS_COLLECTED: 487
TESTS_PASSED: 464
TESTS_FAILED: 0
TESTS_SKIPPED: 23
EXPECTED_SKIPS: 23
UNEXPECTED_SKIPS: 0
COVERAGE: 88.19%
COVERAGE_GATE: PASS (80% requerido)

DOCKER_REBUILD: PASS
MANIFEST_VISIBLE: YES
MANIFEST_HASH_VALIDATION: PASS
MODEL_D_LOAD: OK
MODEL: HistGradientBoostingClassifier
ARTIFACT: prototype_model_d_v1
```

**Alcance temporal — no confundir con Hito 1 / Sprint 1.** Estas cifras
corresponden exclusivamente al baseline de Sprint 2 (commit de arriba). El
baseline histórico de Hito 1 (470 collected / 470 passed / 0 failed,
commit `9f076172`, 2026-09-07 — ver
`artifacts/hito1/testing/pytest-full.txt`) es un snapshot distinto, de una
fase anterior, con menos tests recolectados y sin las condiciones de
verificación Docker descritas aquí. No se debe citar uno como si fuera el
otro.

### Aclaración de alcance — `test_locally_present_artifacts_match_manifest_hash`

`tests/test_reproducibility_manifest.py::test_locally_present_artifacts_match_manifest_hash`
valida el hash SHA-256 de los artefactos de `CHECKED_ARTIFACTS`
(`scripts/verify_reproducibility.py`) que estén **presentes localmente**
contra lo declarado en `artifacts/hito1/reproducibility/manifest.json`. La
ausencia local de un artefacto no produce fallo — es un comportamiento por
diseño (ver el docstring del propio test). Esto **no** debe interpretarse
como una verificación de existencia completa de todos los artefactos
declarados en el manifest: es una prueba de "si existe, su hash coincide
con lo publicado", no de "todo lo declarado existe". (La prueba que sí
exige existencia incondicional de los artefactos mínimos versionados es
`test_the_four_minimum_r3_artifacts_are_always_present`, en el mismo
archivo.)

### Deuda técnica registrada (no bloqueante para Sprint 2)

El pin de versiones del sistema operativo/GDAL/GEOS/PROJ en
`Dockerfile.analytics` y `Dockerfile.web` (`FROM python:3.14-slim` sin
digest fijo, `apt-get install` sin versiones exactas) queda registrado
como mejora futura de reproducibilidad de la capa de sistema operativo.
No es un requisito retroactivo del baseline de Sprint 2 ni bloquea el
veredicto de la sección 8 — se anota aquí únicamente para trazabilidad.

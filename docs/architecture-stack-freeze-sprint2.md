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
  Esas 23 filas representan además 23/107 = 21,5% de los positivos de
  TODO el dataset — no 21,5% de las filas del dataset completo (363.000),
  que sería 0,006%. Ningún
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
  de los positivos de todo el dataset — no de las filas totales —, en un
  solo día). Un fold walk-forward que
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
  DMC_RELATED (data/raw/dmc_historico_330007_*.json ausente,
    marcador _needs_recent_meteo en tests/test_prototype_service.py): 9
  PARQUET_RELATED (data/processed/temporal_dataset_h6.parquet ausente,
    tests/test_megaevento_report.py [2] + test_nan_journey_real_data.py [1]
    + test_temporal_dataset_integration.py [9] + test_pipeline_validators.py [1]
    + test_row_explainer.py [1]): 14
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

### Corrección del build context (SAPI-70) — nota fechada 22-09-2026

**La línea base de arriba no se ejecutó sobre un clon limpio en sentido
estricto.** El `.dockerignore` de ese commit no excluía `.env`, `.env.*`,
`.mcp.json` ni `.venv-demo/`, y sus reglas `__pycache__/` y `*.py[cod]` solo
aplicaban a la raíz del contexto. `COPY . .` copiaba el `.env` local del
desarrollador (credenciales NASA FIRMS, DMC y OpenTopography) dentro de la
imagen, y `src/config.py` (`load_dotenv()`) lo cargaba en cada contenedor.
Verificado en todas las imágenes locales construidas desde entonces. No hay
evidencia de que alguna imagen se haya publicado en un registry.

SAPI-70 corrige `.dockerignore` (reglas al final del archivo, después de toda
excepción `!`), quita `env_file` de `web-presentation` en
`docker-compose.yml` y agrega `tests/test_docker_build_hygiene.py`. No cambia
Dockerfiles, `src/`, `app/`, `models/` ni Model D.

**Resultados reales (Docker, `build --no-cache` de `Dockerfile.analytics`,
sin volúmenes, `main` `a4838bb` + cambios de SAPI-70):**

```
BUILD_CONTEXT: 240 archivos / 13.7 MB (antes: 17.695 / 779 MB)
IMAGE_ENV_FILES: 0 (.env, .env.*, .mcp.json ausentes)
IMAGE_VENV_DIRS: 0
IMAGE_PYCACHE_DIRS: 0
IMAGE_PYC_FILES: 0
SECRET_VALUES_IN_IMAGE_FS: NOT_FOUND (4/4 claves, 52.236 archivos)
SECRET_VALUES_IN_HISTORY_AND_CONFIG: NOT_FOUND
RUNTIME_CREDENTIALS_WITHOUT_INJECTION: vacías (4/4)
TESTS_COLLECTED: 527
TESTS_PASSED: 502
TESTS_FAILED: 0
TESTS_SKIPPED: 25 (los 23 de arriba + 2 de tests/test_data_loader_golden.py
  que requieren data/ local, agregados en SAPI-69)
COVERAGE: 88.30%
COVERAGE_GATE: PASS (80% requerido)
MODEL_D: prototype_model_d_v1, pkl sha256 ac017bef…2173f, ranking
  idéntico (hash de las 50 celdas e84b2323…1170)
```

La cobertura baja de 88.49% a 88.30% por sacar `.env` de la imagen, no por
cambios de código: medido sobre el mismo árbol (`a4838bb`), con y sin
`/app/.env`, ambas corridas dan 497 passed / 25 skipped / 0 failed; algunas
ramas solo se ejecutaban con credenciales cargadas. Los 5 tests adicionales
(502 − 497) son los de `test_docker_build_hygiene.py`, que dentro de la
imagen se ejecutan completos. Este es el baseline de referencia desde
SAPI-70; las cifras anteriores quedan como registro histórico.

### Fingerprint del ranking Model D y n8n-bridge (SAPI-71 Fase A) — nota fechada 23-09-2026

El hash `e84b2323…1170` citado arriba no es reproducible: no quedó
registrado cómo se calculó y ninguna de ~3.800 serializaciones candidatas
(campos, separadores, formatos de float, sha256/md5/sha1/blake2b, modo
normal y reproducible) lo reproduce sobre el mismo ranking. Queda como
registro histórico. Desde SAPI-71 el fingerprint de referencia es este:

- Entrada: `score_current_grid()` sin argumentos (último `forecast_time` real).
- Campos por celda: `cell_id`, `score`, `rank`, en ese orden.
- Orden de filas: el de `GridScoreResult.cells` (rank 1..50), sin reordenar.
- Serialización: una línea por celda `f"{cell_id},{score!r},{rank}"`
  (`repr` del float: precisión completa, sin redondeo), líneas unidas con
  `"\n"`, sin salto final, codificadas en UTF-8.
- Algoritmo: SHA-256, hexdigest.

```bash
PYTHONPATH=. python -c "
import hashlib
from src.inference.prototype_service import score_current_grid
cells = score_current_grid().cells
payload = '\n'.join(f'{c.cell_id},{c.score!r},{c.rank}' for c in cells)
print(len(cells), cells[0].cell_id, round(cells[0].score, 12))
print(hashlib.sha256(payload.encode('utf-8')).hexdigest())"
```

Valor esperado (`prototype_model_d_v1`, pkl sha256 `ac017bef…2173f`,
`forecast_time` 2026-09-01T00:00:00Z, 50 celdas, VP-001 primera con
0.131293368748), idéntico en modo normal y con
`SAPI_REPRODUCIBILITY_MODE=1`:

```
33c2eacc49bd0cc130928b5bd182ec523e63614f0e3dd97a129a8d4657f231ff
```

El valor depende de los datos: si llega meteorología DMC más reciente,
cambia el `forecast_time` y con él el fingerprint, sin que Model D haya
cambiado. Compararlo siempre contra el mismo `forecast_time`.

**Resultados reales SAPI-71 Fase A** (n8n-bridge, `main` `1bd32f2` + bridge
adaptado; `src/`, `app/`, `models/` y `scripts/` sin cambios):

```
HOST: 551 passed, 2 skipped, 0 failed; cobertura 91.97%
DOCKER (Dockerfile.analytics --no-cache, sin volúmenes):
  528 passed, 25 skipped, 0 failed; cobertura 88.30%
  (502 del baseline SAPI-70 + 26 de tests/test_n8n_bridge.py)
N8N_BRIDGE_IMAGE: sin .env/.env.*/.mcp.json/.venv*, 0 .pyc;
  valores del .env NOT_FOUND en filesystem, history y config
N8N_BRIDGE_RUNTIME: 127.0.0.1:8600->8600, data/ y models/ RW=false,
  sin env_file, sin docker.sock, sin DOCKER_HOST
/health y /score: HTTP 200 desde host y desde contenedor
  (host.docker.internal:8600); /score = 50 celdas, mismo ranking que
  score_current_grid() en host (fingerprint 33c2eacc…31ff)
```

### Refresco FIRMS versionado y gate de desfase (SAPI-71 Fase B) — nota fechada 23-09-2026

Decisiones (23-09-2026): desfase FIRMS con aviso sobre 3 días y bloqueo
sobre 7; puntero `CURRENT.json` en esquema 2 (el esquema 1 nunca se
escribió y ya no se acepta); primero FIRMS + gate, después DMC; el loop
legacy queda apagado (ver abajo).

- **Guard de la línea base.** `ensure_writable_firms_path()`
  (`src/procesamiento/firms_source.py`) rechaza cualquier escritura sobre
  `FIRMS_BASELINE_CSV`, su manifest o el snapshot del Hito 1 (rutas
  canónicas, symlinks y hardlinks), antes de la red. Antes de este guard,
  `NasaFirmsBackfill.run()` con el período 2021-08-30..2026-08-30 la
  sobrescribía.
- **Refresco manual** (`python -m src.refresh.firms_refresh refresh | status
  | rollback --to <versión|baseline> | cleanup [--apply]`). Cada versión en
  `data/processed/firms/versions/` son los bytes exactos de la vigente
  (la línea base la primera vez, verificada contra `FIRMS_BASELINE_SHA256`)
  más detecciones con `acq_date` estrictamente posterior a su
  `coverage_end` y hasta ayer (UTC). Como `assign_episodes` recorre en orden
  temporal, las features FIRMS de todo T ya cubierto quedan idénticas
  (test con la línea base real). Versión inmutable → sidecar → puntero
  atómico → `pointer_history.jsonl`; un fallo nunca reemplaza la versión
  vigente. Lock de escritor único (`O_EXCL`, sin espera). Sin credencial,
  sale con 78 sin tocar red; caída de red 69; respuesta inválida o vacía
  (0 bytes, HTML, MAP_KEY inválida) 65; una respuesta con solo la cabecera
  es "sin detecciones" y sí extiende la cobertura.
- **Gate de desfase** (`classify_firms_lag`, `prototype_service.py`): lag =
  fecha(T) − `coverage_end`. ≤3 días "FIRMS AL DÍA"; 4–7 "FIRMS
  DESACTUALIZADO" (se puntúa y `GridScoreResult.firms_status` lo informa);
  >7 `PrototypeUnavailableError` (503 en n8n-bridge). Motivo: el historial
  FIRMS por celda contaría como "sin incendios" los días no consultados.
  Estado al 23-09-2026: línea base, lag 2 días, sin cambio de ranking.
- **Loop legacy apagado.** `analytics-backend` (`scripts/run_daily_loop.sh`
  → `src.pipeline.run_daily`) escribe `nasa_firms_*.csv`/`dmc_meteo_*.json`
  sin lock, usa la degradación `staging_meteo` y reentrena modelos legacy.
  No debe correr mientras se usen los refrescos de Fase B; no se modifica
  su código (se retirará en un issue aparte).

**Resultados reales** (rama `feat/SAPI-71-firms-refresh-v2`, sobre el guard `f0b1a12`; sin
refresco real ejecutado: `data/processed/firms/` no existe):

```
HOST: 613 passed, 3 skipped, 0 failed; cobertura 91.79%
LINUX (contenedor sin red, tests de refresco/guard/gate/firms_source):
  81 passed, 1 skipped (caso Windows-only)
MODEL_D: fingerprint 33c2eacc…31ff sin cambios (modo normal y reproducible);
  firms_origin=baseline, firms_lag_days=2
BASELINE FIRMS: sha256 a9a85db4…bb271 sin cambios
```

### Refresco DMC versionado por mes (SAPI-71 Fase B) — nota fechada 23-09-2026

**Contrato verificado con UNA llamada real** (23-09-2026 15:25 UTC,
`getDatosRecientesEma/330007/2026/9`, credenciales solo en runtime; se
registró únicamente metadata): HTTP 200, `application/json`, raíz objeto
sin envoltorio de estación (`datosEstaciones`, `fechaCreacion`, `organismo`,
`pais`, `producto`, `registros`, `status`, `timezone`), `timezone: "UTC"`,
2.169 lecturas = `registros`, de 2026-09-01 00:00 a 2026-09-23 15:00
(desfase 0,42 h: el mes EN CURSO viene parcial y casi al día), orden
ascendente, sin `momento` repetidos, paso de 15 min (un hueco de 75 min),
26 campos uniformes (7 siempre nulos). Envuelta como `{estacion: respuesta}`
la lee `parse_dmc_json` sin descartar filas. El campo `producto` sigue
diciendo "últimas 12 horas" aunque la respuesta sea mensual.

- **Refresco manual** (`python -m src.refresh.dmc_refresh refresh | status |
  rollback --to <manifest_sha12>`): consulta desde el mes de la última
  lectura publicada (el mes anterior en la primera corrida) hasta el mes en
  curso y fusiona por mes con lo ya publicado, clave (estación, `momento`
  UTC); un `momento` ya publicado con otro contenido conserva el valor
  publicado (append-only) y se informa como conflicto. JSON canónico
  (claves ordenadas, lecturas ascendentes, sin `fechaCreacion`): la misma
  entrada produce los mismos bytes y una corrida sin datos nuevos no publica.
  Cada documento se relee con `parse_dmc_json` antes de publicarse.
- **Almacenamiento** en `data/processed/dmc/330007/` (versiones mensuales
  inmutables, `pointers/`, `CURRENT.json`, `pointer_history.jsonl`), fuera
  de `data/raw/`: `load_regional_meteo_series` sigue sin leerlo. Cuando se
  escribió esta nota el scoring tampoco lo usaba; desde la nota de
  `ScoringInputs` de más abajo sí lo consume, por otra puerta
  (`scoring_inputs.pin_dmc`: bloque legacy completo y, del almacén, solo
  lecturas posteriores a la última legacy). Los archivos legacy
  `dmc_historico_*`/`dmc_meteo_*` nunca se escriben.
- **Fallos**: sin credenciales, 78 antes de cualquier escritura o request;
  red caída o 5xx, 3 intentos acotados y luego 69; HTTP 4xx, 69 sin
  reintento; JSON inválido, `timezone` distinto de UTC, `registros` que no
  calza, lecturas de otro mes o sin `momento`, o respuesta vacía, 65 (el
  mes en curso vacío solo se tolera en sus primeras 6 h). En todos los casos
  `CURRENT.json` queda intacto. Lock de escritor único compartido con el
  patrón FIRMS: un segundo escritor sale con 75 sin llamar a la API.
- No usa `ParallelIngester`, `staging_meteo` ni `run_daily`; el loop legacy
  sigue apagado (no existe contenedor `sapi-analytics`).

**Resultados reales** (rama `feat/SAPI-71-dmc-refresh`, sobre `5d28a94`; sin
refresco real ejecutado: `data/processed/dmc/` no existe):

```
HOST: 649 passed, 3 skipped, 0 failed; cobertura 91.87% (dmc_refresh 93%)
LINUX (contenedor sin red): 70 passed (refresco DMC, FIRMS y primitivas)
MUTACIONES: perder lo publicado, no ordenar, pisar lo publicado y quitar el
  lock hacen fallar al menos un test cada una
MODEL_D: fingerprint 33c2eacc…31ff sin cambios
```

### ScoringInputs: entradas fijadas por corrida (SAPI-71 Fase B) — nota fechada 23-09-2026

Antes, una corrida de `score_current_grid()` tocaba disco en cuatro
momentos distintos: `exists()` + `joblib.load(path)` del modelo; listado
y lectura de ~64 JSON DMC; y, dentro de `build_feature_matrix`, un
`resolve_firms_source()` (que hashea el CSV) seguido de un
`pd.read_csv(path)` que volvía a abrir el archivo por ruta. Un refresco
publicado entre esos pasos podía mezclar versiones.

`capture_scoring_inputs()` (`src/inference/prototype_service.py`, tipos en
`src/inference/scoring_inputs.py`) fija todo al inicio: el modo
reproducible se lee una vez; cada archivo (modelo, DMC, FIRMS y la tabla
topográfica congelada) se lee UNA vez, se hashea y se parsea desde esos
bytes; FIRMS se verifica contra el sha256 del puntero o de la línea base
(`FIRMS_BASELINE_SHA256`) y, si no coincide, la captura aborta
(`PrototypeUnavailableError`). `score_current_grid(inputs=...)` usa solo
esa copia en memoria: un test bloquea `open`, `read_bytes`, `glob`,
`read_csv`, `joblib.load` y `resolve_firms_source` durante el scoring y el
ranking sale idéntico. `GridScoreResult` expone `inputs_fingerprint` y
`scoring_inputs` (manifest sin `captured_at`); la antigüedad se mide en el
instante de captura.

- **DMC legacy + versionado** (`pin_dmc`): el bloque legacy
  (`data/raw/`, ordenado por nombre) se usa completo; del almacén de
  `dmc_refresh` solo entran lecturas con `momento` posterior a la última
  legacy. Un mismo (estación, momento) nunca se cuenta dos veces y, ante
  valores distintos, gana legacy. El loader también concatena ahora por
  nombre (antes, orden del filesystem; sin efecto con los datos actuales:
  132 `momento` repetidos, 0 con valores distintos).
- **Modo reproducible**: solo snapshots Hito 1; no consulta ningún
  `CURRENT.json` (DMC ni FIRMS).
- **Sin cambios científicos**: mismas funciones de features, target,
  modelo y ranking; los tests que parcheaban internals (`_load_model`,
  `load_regional_meteo_series`, `build_feature_matrix` con FIRMS parcheado)
  pasan a `capture_scoring_inputs` en modo reproducible.

**Resultados reales** (rama `feat/SAPI-71-scoring-inputs`, sobre `53bd673`;
sin refresco real, sin `CURRENT.json` bajo `data/`):

```
HOST: 667 passed, 3 skipped, 0 failed; cobertura 92.11%
  (scoring_inputs 99%, prototype_service 96%)
LINUX sin data/ (como CI): 150 passed, 10 skipped (dependen de data/ local)
MUTACIONES: releer FIRMS en el scoring, no filtrar el solapamiento DMC,
  omitir la verificación de sha256 y leer el almacén en modo reproducible
  hacen fallar su test
MODEL_D: fingerprint 33c2eacc…31ff sin cambios (normal y reproducible)
LATENCIA score_current_grid: ~14,1 s (antes ~15,5 s, misma máquina)
```

### Cierre de SAPI-71 Fase B: estado integrado — nota fechada 23-09-2026

Las notas anteriores siguen siendo válidas para el commit en que se midió
cada una; esta las reconcilia sobre el árbol que las combina: `origin/main`
(`7a5ff61`), la corrección del refresco DMC, el endurecimiento previo al
primer refresco (F8/F4/F5), la semántica definitiva de `record_count` y
cobertura, `ScoringInputs` (`30a296c`), el endurecimiento de la
clasificación de errores de acceso y la reproducibilidad de fin de línea
(`.gitattributes`).

- **Corrección DMC**: `registros` presente que no es entero da 65 (ausente
  se tolera: el documento canónico no lo lleva). El docstring ya no afirma
  que un conflicto llegue al historial en una corrida `unchanged`.
- **Calidad de filas** (política inicial conservadora, no una propiedad
  científica): por mes, hasta 1 % de filas con `null` explícito se publica;
  más de 1 % da 65 y no se publica nada; un valor presente no numérico
  (texto, `""`, bool, NaN/inf) o un campo ausente da 65 siempre. `total_rows`,
  `null_rows`, `discard_rate` y `threshold` son metadata operacional: salen
  en la CLI y en la línea `publish` del historial, nunca en el puntero. Si
  la API usa `""` para "sin dato", cada corrida daría 65: se valida con el
  primer payload real.
- **Semántica del puntero** (`schema_version` 1, ver la nota de hardening):
  `record_count` = lecturas válidas publicadas; `coverage_start`/
  `coverage_end` = primer/último `momento` válido publicado.
- **Rollback**: el puntero de destino pasa por la misma verificación que
  `read_current`; cualquier falla es 65 sin tocar `CURRENT.json` ni el
  historial.
- **Credenciales**: un error de red se reporta solo por su tipo; `redact`
  cubre el valor crudo y sus variantes URL-encoded. No ejecutar el refresco
  con logging DEBUG (no probado con urllib3 real).
- **Acceso a entradas fijadas**: un `OSError` al leer una entrada fijada
  sale como `PinnedInputError` → 503 `prototype_unavailable` (antes, 500
  `internal_error`). `CURRENT.json` ausente degrada a solo-legacy (mantiene
  estable el fingerprint mientras no haya refresco publicado); ilegible
  aborta la captura en vez de descartar en silencio lecturas publicadas.
- **Reproducibilidad CRLF/LF**: tres artefactos congelados de
  `artifacts/hito1/reproducibility/` (FIRMS, `dmc_historico_330007_2026-08.json`,
  `dem/grid_topography.csv`) tienen su sha256 publicado sobre los bytes
  originales, con CRLF, pero se versionaron normalizados a LF. Un checkout
  Windows reponía los CR y el hash coincidía; uno LF (Linux, macOS, CI) no.
  `ScoringInputs` verifica ese hash al puntuar, así que en LF el modo
  reproducible abortaba. Corrección: `.gitattributes` marca **solo esas tres
  rutas** `-text` y sus blobs vuelven a ser los bytes originales. El
  contenido es idéntico salvo por los CR; ningún dato cambia, ningún hash
  congelado se recalcula y `manifest.json` no se toca. **`.gitattributes`
  es parte del contrato de reproducibilidad**: quitar esas líneas, o
  normalizar esas rutas, vuelve a romper la verificación en LF.
- **Refresco real: NO ejecutado.** No existe `data/processed/dmc/` ni
  `data/processed/firms/`, ni ningún `CURRENT.json`.

```
HOST (checkout Windows, core.autocrlf=true, datos locales):
  736 passed, 4 skipped, 0 failed; cobertura 92.26%
  (dmc_refresh.py 96%, scoring_inputs.py 99%)
DOCKER (Dockerfile.analytics --no-cache, checkout LF, sin volúmenes,
  --network none, Python 3.14.7): 713 passed, 27 skipped, 0 failed;
  cobertura 89.53%; los tres hashes congelados verificados dentro del
  contenedor. Los 27 skips son tests que requieren data/ local, que la
  imagen excluye.
LF ANTES/DESPUÉS de .gitattributes: origin/main 3 failed -> 3 passed;
  estado integrado 9 failed -> 9 passed (3 preexistentes + 6 de ScoringInputs)
DIRIGIDOS (checkout LF, sin datos locales): reproducibilidad 39 passed /
  11 skipped; ScoringInputs + n8n-bridge 48 / 1; DMC + primitivas +
  contrato de almacén 110 / 1
CONTRATO writer<->reader DMC: 6 passed (incluye 100 lecturas por mes con
  exactamente 1 % de nulos: record_count y cobertura del puntero = lo que
  pin_dmc fija)
PROPERTY-BASED DMC (Hypothesis, 300 ejemplos/propiedad): 11 passed
MODEL_D: fingerprint 33c2eacc…31ff idéntico en modo reproducible (checkout
  LF y Windows) y operacional (data/raw real, sin punteros publicados)
PYRIGHT: 0 en dmc_refresh.py, redact.py, scoring_inputs.py y
  test_dmc_store_contract.py; prototype_service.py 16 (antes 17); quedan
  12 solo-test preexistentes (3 en test_dmc_refresh.py, 9 en
  test_scoring_inputs.py)
```

### Reconciliación con `manifest.json` (R2/R3) — nota fechada 21-09-2026

`artifacts/hito1/reproducibility/manifest.json` es un snapshot histórico
fechado (ver sus propios campos `_meta.principio_de_honestidad_temporal`
y `_meta.principio_de_no_fabricacion`) y **no se reescribe
retroactivamente**. Esta nota solo reconcilia lo ya publicado ahí con el
baseline de Sprint 2 de arriba, sin alterar una sola palabra del manifest:

- `reproducibilidad_por_dimension.R2_build_test_reproducibility` (manifest,
  campo fechado 09-09-2026) registra 454 passed / 23 skipped / 0 failed
  (clon limpio) y 477 passed / 0 skipped (repo con datos locales). Ambas
  cifras eran correctas para esa fecha. Entre el commit que generó el
  manifest (`5e721f2`, 2026-09-09) y el baseline de Sprint 2 de arriba
  (`e573adc`) se agregaron 10 tests nuevos que nunca dependen de datos
  locales (no se saltan): 2 en `tests/test_architecture.py` (commit
  `07c8306`, 2026-09-09) y 8 en `tests/test_prototype_view.py` (commit
  `b66aaf3`, 2026-09-09). 454+10=464 y 477+10=487 — coincide exactamente
  con las cifras de Sprint 2. No hay regresión ni discrepancia real:
  son dos snapshots de fechas distintas, ambos correctos en su momento.
- Ese mismo campo del manifest atribuye los 23 skips únicamente al
  marcador `_needs_recent_meteo` — esto es impreciso incluso en su propia
  fecha: `_needs_recent_meteo` (ausencia de DMC) explica 9 de los 23; los
  otros 14 dependen de la ausencia de `temporal_dataset_h6.parquet`, vía
  guards de skip independientes (ver desglose completo arriba en esta
  sección). No se corrige el texto del manifest — se deja constancia aquí
  para no repetir la imprecisión en evidencia futura.
- `cadena_de_proveniencia.2_dmc_330007.snapshot_reproducibilidad_R3.limitacion_conocida`
  en el manifest es una nota de una ronda de verificación anterior a que
  se agregaran los snapshots FIRMS/DEM; el propio manifest la supera más
  abajo en `reproducibilidad_por_dimension.R3_inference_reproducibility`
  ("actualizado 09-09-2026, tercera ronda"), que sí confirma los 4
  artefactos mínimos versionados. Ambas afirmaciones son del mismo
  documento y no se contradicen en sustancia — la nota de la ronda
  anterior simplemente quedó sin una marca explícita de supersesión
  dentro del propio manifest. Corregir eso directamente en
  `manifest.json` queda fuera del alcance de este PR.

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

### Hardening previo al primer refresco DMC (SAPI-71 Fase B) — nota fechada 23-09-2026

Esta nota **no reescribe** la de "Refresco DMC versionado por mes" de más
arriba: la complementa con el comportamiento que el código tiene desde el
endurecimiento posterior a la corrección de `registros`. Sigue sin haberse
ejecutado ningún refresco real (`data/processed/dmc/` no existe) y **no se
autoriza ninguno** hasta completar el runbook del primer refresco controlado.

- **`registros`**: si viene, debe ser un entero que calce con `len(datos)`;
  `registros: null` explícito, texto o float dan 65. Solo se acepta ausente
  (el documento canónico no lo lleva). Decisión consciente: no se flexibiliza
  para el mes en curso vacío hasta observar un payload real que lo justifique;
  mientras tanto, un 65 en las primeras 6 h de un mes es posible y no publica
  nada.
- **Calidad de filas** (`temperatura`, `humedadRelativa`, las columnas que
  `parse_dmc_json` exige). Política inicial **conservadora, no una propiedad
  científica**, ajustable solo con evidencia real:
  - valor presente del que el parser no extrae un número finito (texto sin
    número, `""`, bool, NaN/inf, objeto) o campo ausente: **65 siempre**, sin
    convertir nada;
  - `null` explícito: la fila cuenta como nula; si
    `null_rows / total_rows > 0,01` (comparación exacta con `Fraction`),
    **65 y no se publica ninguna versión** del mes; con `<= 0,01` se publica y
    el parser descarta esas filas al leer;
  - se evalúa sobre el payload mensual recibido y otra vez sobre la versión
    fusionada antes de publicarla, y la relectura exige que `parse_dmc_json`
    conserve exactamente `total_rows - null_rows` filas;
  - metadata observable por mes: `total_rows`, `null_rows`, `discard_rate`,
    `threshold`, en la salida de la CLI (`row_quality`) y en la línea
    `publish` de `pointer_history.jsonl`. No entra al puntero ni a los bytes
    canónicos.
- **Semántica del puntero, fijada antes de la primera publicación real**
  (`schema_version` sigue en 1: no existe almacén publicado ni un v1 anterior
  que preservar, y la estructura no cambia):
  - `record_count` (por mes y total) = lecturas **válidas** publicadas, las
    que `parse_dmc_json` conserva. No es el total recibido de la API; ese
    total vive solo en `row_quality.total_rows` (CLI e historial).
  - `first_momento`/`last_momento` por mes, y con ellos `coverage_start`/
    `coverage_end`, son el primer y el último `momento` **válido** publicado.
    Una fila nula en el borde no mueve la cobertura.
  - La versión mensual sigue guardando todas las lecturas recibidas, nulas
    incluidas: los bytes canónicos no se filtran.
  - Contrato con el lector: `len(serie fijada por ScoringInputs) ==
    pointer["record_count"]`, anclado por
    `test_pointer_counts_and_coverage_describe_only_valid_published_readings`
    (writer) y por el test contractual con 1 % de nulos (writer↔lector).
- **Credenciales (F8)**: van en el querystring; un error de red se reporta
  solo por su tipo (`ConnectionError`, `Timeout`...), nunca con `str(exc)`,
  que traía la URL con usuario y token URL-encoded. `redact` cubre además el
  valor crudo y sus variantes URL-encoded. **No ejecutar el refresco con
  logging DEBUG** hasta verificar que urllib3 no registra la URL con
  credenciales (no probado con urllib3 real).
- **Rollback (F4a/F4b)**: el puntero de destino pasa por la misma
  verificación que `read_current` antes de publicarse: claves requeridas,
  `schema_version`, `station_id`, `manifest_sha256`, ruta confinada en
  `versions/` (sin separadores, `..`, unidad ni symlink que salga),
  existencia y sha256 de cada versión, y que `manifest_sha256` empiece por el
  identificador pedido. Cualquier rollback inválido sale con **65**, mensaje
  JSON en stderr, sin traceback, sin tocar `CURRENT.json` ni el historial.
  `read_current` es ahora igual de estricto (antes aceptaba punteros sin
  `station_id` o con `months` vacío).
- **Riesgos conocidos, no bloqueantes, a validar con el primer payload real**:
  - el parser acepta texto que contenga un número: `"N/A 5"` se lee como `5`.
    Clasificado como **deuda / contrato a validar con payload real**; no se
    relaja ni se endurece ahora;
  - `""` da 65: si la API usara cadena vacía como dato faltante, cada corrida
    fallaría;
  - versiones huérfanas (F3, deuda): si falla un mes posterior, la versión ya
    escrita de un mes anterior queda en `versions/` sin puntero que la
    referencie; no se publica.

Cifras medidas sobre el commit del hardening, antes de fijar la semántica
de `record_count`/cobertura; las del estado integrado están en la nota de
cierre de SAPI-71 Fase B.

```
HOST (Windows, worktree sin data/ local): 681 passed, 29 skipped, 0 failed;
  cobertura 89.13% (dmc_refresh 97%, redact 100%)
DOCKER (Dockerfile.analytics, --network none verificado): 684 passed,
  26 skipped, 0 failed; cobertura 89.22%; Python 3.14.7
PROPERTY-BASED DMC (Hypothesis): 11 passed
PYRIGHT: dmc_refresh.py y redact.py en 0; tests con los 3 preexistentes
TESTS NUEVOS: 52 casos; 47 fallan sobre el código previo al endurecimiento
```

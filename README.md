# S.A.P.I. — Sistema de Alerta y Predicción de Incendios Forestales

<div align="center">

![Python](https://img.shields.io/badge/Python-3.14-3776AB?style=flat-square&logo=python&logoColor=white)
![Modelo D](https://img.shields.io/badge/Modelo_D-HistGradientBoosting_(baseline)-FF6600?style=flat-square)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL_15-PostGIS-336791?style=flat-square&logo=postgresql&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.63-FF4B4B?style=flat-square&logo=streamlit&logoColor=white)

**Prototipo de software geoespacial basado en Machine Learning que ordena 50 celdas del corredor Viña del Mar – Quilpué (Región de Valparaíso, Chile) según su riesgo *relativo* de recibir una nueva detección satelital de anomalía térmica (NASA FIRMS) en las próximas 6 horas.**

> El score del Modelo D es un **ranking relativo** entre las celdas de una misma evaluación: **no es una probabilidad calibrada de incendio** y el modelo no tiene validación científica (`scientific_model_validation = false`). Una detección FIRMS es una anomalía térmica observada por satélite, **no** un incendio confirmado en terreno. Ver [`docs/model_card_baseline.md`](docs/model_card_baseline.md).

[Ver demo](#-demo) · [Instalación rápida](#️-instalación) · [Documentación técnica](#-documentación) · [Resultados](#-resultados-obtenidos)

</div>

---

## ¿Qué es S.A.P.I.?

Chile enfrenta cada verano una crisis de incendios forestales cuyo paradigma de respuesta sigue siendo **100% reactivo**: las alertas se activan cuando el fuego ya existe y es visible. En Valparaíso, la latencia entre el inicio real del foco y el despliegue de brigadas es de entre 20 y 60 minutos — tiempo más que suficiente para que un foco incipiente escale a megaincendio en su compleja red de quebradas.

**S.A.P.I. busca desplazar ese eje.** En lugar de esperar a que el fuego sea visible, el prototipo ordena las celdas de la zona de estudio según su riesgo relativo de recibir una nueva detección satelital en las próximas horas (horizonte actual: 6 h), para apoyar la priorización preventiva. Es un prototipo académico exploratorio: no reemplaza los sistemas oficiales de alerta ni debe usarse para decisiones operacionales.

```
Paradigma actual:  Ignición → Detección visual → Confirmación → Despliegue (≥20 min tarde)
S.A.P.I. (visión): Ranking relativo de riesgo → Priorización → Despliegue preventivo
```

---

## Arquitectura del Sistema

La arquitectura objetivo de Sprint 2 está congelada en
[`docs/architecture-stack-freeze-sprint2.md`](docs/architecture-stack-freeze-sprint2.md):

```
Streamlit (presentación) → Spring Boot (API pública, registro de ejecuciones)
                         → FastAPI (servicio ML interno, Modelo D)
                         → PostgreSQL/PostGIS (persistencia operacional v2)
```

**Estado real al checkpoint de Sprint 2 (`cd6b58e`)** — se distingue lo
implementado de lo planificado:

| Componente | Estado | Evidencia |
|---|---|---|
| Servicio ML FastAPI (`GET /health`, `POST /predict`) | Implementado (SAPI-55) | `services/ml_api/`, `tests/test_ml_api.py` |
| Backend Spring Boot | `GET /health` (SAPI-54) y `GET /api/v1/ranking`, que consulta al servicio ML (SAPI-57, en revisión); registro de ejecuciones pendiente (SAPI-59) | `services/backend/` |
| Contratos OpenAPI v0 | Definidos (SAPI-56) | `contracts/openapi/` |
| Esquema PostgreSQL/PostGIS v2 | Migraciones V001–V003 definidas (SAPI-58); persistencia de resultados pendiente (SAPI-59) | `db/migration/`, `db/README.md` |
| Streamlit | Implementado; hoy puntúa en el mismo proceso con `score_current_grid()`; consumo del backend pendiente (SAPI-61) | `app/` |
| Docker Compose de la arquitectura v2 | Pendiente al checkpoint (SAPI-60); ver la nota bajo la tabla | `docker-compose.yml` |
| Ruta legacy (RF/XGBoost, `src/modelo/`, `src/pipeline/`) | Conservada solo como histórico; no es la ruta activa del Modelo D | `docs/architecture-stack-freeze-sprint2.md` §1 |

Desde SAPI-60, `docker compose up --build` levanta la arquitectura v2
(Spring Boot, FastAPI y PostgreSQL/PostGIS v2); ver
[Instalación](#opción-a--docker-compose-arquitectura-v2-sapi-60). Los
servicios de Hito 1 quedan detrás de profiles de Compose.

### Stack tecnológico

| Capa | Tecnología (versiones fijadas) |
|------|-----------|
| Lenguaje / runtime ML | `Python 3.14.6`, `pandas 3.0.5`, `scikit-learn 1.9.0` |
| Modelo | Modelo D: `HistGradientBoostingClassifier`, `class_weight="balanced"`, sin SMOTE |
| Procesamiento espacial | `GeoPandas 1.1.4`, `rasterio 1.4.4` |
| Servicio ML | `FastAPI 0.141.1` + `uvicorn 0.53.0` |
| Backend | `Spring Boot 4.1.1` + `Java 21` |
| Persistencia | `PostgreSQL 15` + `PostGIS 3.4` (imagen `postgis/postgis:15-3.4`) |
| Visualización | `Streamlit 1.63.0` + `Folium 0.20.0` |
| Contenerización | `Docker` + `Docker Compose` |
| Calidad | `pytest` (gate de cobertura 80 %), `black`, `flake8` |

---

## Fuentes de Datos

El sistema usa únicamente fuentes públicas y de acceso abierto:

| Fuente | Datos usados por el Modelo D | Estado |
|--------|----------------|------------|
| **NASA FIRMS** (VIIRS) | Detecciones satelitales de anomalías térmicas (no confirman incendio en terreno); definen el target y el historial por celda | Integrada |
| **Dirección Meteorológica de Chile (DMC)** | Temperatura, humedad relativa y viento de la estación regional 330007 (serie regional, no por celda) | Integrada |
| **Copernicus DEM** (GLO-30 vía OpenTopography) | Elevación, pendiente y orientación por celda | Integrada |
| **CONAF** | Historial de igniciones | **No integrada** (spike SAPI-49, fuera del alcance de Sprint 2) |

---

## Resultados Obtenidos

### Motor predictivo (Modelo D, baseline experimental)

El modelo activo es el **Modelo D** (`HistGradientBoostingClassifier`,
`prototype_model_d_v1`), documentado en
[`docs/model_card_baseline.md`](docs/model_card_baseline.md) con validación
temporal walk-forward causal. Sus métricas son **exploratorias**: se reportan
por fold como métricas de ranking (PR-AUC, precision@k, recall@k) y no existe
un umbral operacional validado. El clasificador XGBoost y el baseline Random
Forest del pipeline de Hito 1 (`src/modelo/`) son legacy y no producen el
ranking que muestra el prototipo.

> ⚠️ **Nota histórica (2026-09-01):** los valores 71% / 78% / 0.83 que este README citó en el pasado eran valores de mock de `tests/test_pipeline.py` (commit `30c8a26`), sin una corrida real detrás. No deben citarse como resultados.

### Rendimiento

La latencia del sistema **todavía no está medida formalmente** (atributo de
calidad QA-08 en `docs/atributos-calidad-hito1.md`: `NOT_MEASURED`). La única
medición registrada es informal: `score_current_grid()` tarda ~14 s por
evaluación completa en la máquina de desarrollo
(`docs/architecture-stack-freeze-sprint2.md`, nota `ScoringInputs`). La
medición formal de latencia por servicio está planificada para Sprint 2.

### Suite de testing

```
pip install -r requirements-dev.txt
pytest            # gate de cobertura: 80 % sobre app/ y src/ (pytest.ini)
```

Los conteos de tests y la cobertura de cada corte se registran como evidencia
versionada (Hito 1: `artifacts/hito1/testing/`; Sprint 2: `artifacts/hito2/`),
no en este README, para que no queden desactualizados.

---

## Estructura del Repositorio

```
S.A.P.I-Sistema-de-Prediccion-de-Incendios/
├── app/                 # Streamlit (presentación); vista Prototipo y Centro de Control
├── services/
│   ├── ml_api/          # Servicio ML FastAPI (SAPI-55): /health, /predict
│   └── backend/         # Backend Spring Boot (SAPI-54, SAPI-57): /health, /api/v1/ranking
├── contracts/openapi/   # Contratos OpenAPI v0 (SAPI-56)
├── db/migration/        # Esquema PostgreSQL/PostGIS v2 (SAPI-58)
├── src/
│   ├── inference/       # Ruta activa del Modelo D (score_current_grid)
│   ├── procesamiento/   # Features (FIRMS, DMC regional, DEM)
│   ├── refresh/         # Refresco versionado FIRMS/DMC (SAPI-71)
│   ├── geo/             # Grilla de 50 celdas (VP-001..VP-050)
│   └── modelo/, pipeline/, query/   # Ruta legacy de Hito 1 (no activa)
├── models/              # Artefacto congelado del Modelo D (.pkl + metadata)
├── artifacts/           # Evidencia versionada (hito1/, hito2/)
├── docs/                # Documentación técnica, freeze de arquitectura, model card
├── scripts/             # Entrenamiento, verificación y utilidades
├── tests/               # Suite pytest
├── tools/, ops/         # Tooling de operación (puente n8n, refresco controlado)
├── docker/initdb/       # Esquema legacy de Hito 1 (LEGACY_ONLY)
├── docker-compose.yml
└── Dockerfile.*         # analytics (legacy), web, ml-api, n8n-bridge
```

---

## Instalación

### Requisitos previos

- Opción A: solo Docker y Docker Compose v2 (`docker compose`). Las imágenes se
  construyen dentro de Docker; no hace falta Python, Java ni Maven en el equipo.
- Opción B: Python 3.14 y, para el backend, Java 21 (el wrapper `mvnw`
  descarga Maven).

### Opción A — Docker Compose: arquitectura v2 (SAPI-60)

Levanta Spring Boot, el servicio ML FastAPI (Modelo D) y PostgreSQL/PostGIS v2
con un solo comando:

```bash
git clone https://github.com/DanielCortezF002/S.A.P.I-Sistema-de-Prediccion-de-Incendios.git
cd S.A.P.I-Sistema-de-Prediccion-de-Incendios
cp .env.example .env            # Windows (PowerShell): Copy-Item .env.example .env
docker compose up --build       # con -d --wait queda en segundo plano y espera a que todo esté healthy
```

`.env` nunca se versiona. `SAPI_DB_PASSWORD` no tiene valor por defecto en
`docker-compose.yml` (sin `.env`, Compose no arranca); el valor de
`.env.example` es solo para desarrollo local y conviene cambiarlo antes del
primer arranque, porque después queda fijado en el volumen. **Si ya existe un
`.env` de Hito 1** (por ejemplo con credenciales reales de NASA FIRMS u
OpenTopography), no lo reemplaces: agrega el bloque SAPI-60 de `.env.example`.
Compose interpola todo el archivo, así que desde SAPI-60 también los comandos
de los servicios de Hito 1 necesitan `SAPI_DB_PASSWORD`.

| Servicio | Dirección en el equipo | Health check |
|---|---|---|
| Backend Spring Boot | `http://localhost:8080` | `GET /health` → 200 `{"status":"UP"}` |
| Servicio ML (FastAPI, Modelo D) | `http://localhost:8000` | `GET /health` → 200 `{"status":"ok", "model_version": ...}` |
| PostgreSQL/PostGIS v2 | `localhost:5432` (base `sapi_v2`, usuario `sapi`) | `pg_isready` por TCP dentro del contenedor |

`docker compose ps` muestra cada servicio como `healthy`. Los puertos se
publican solo en `127.0.0.1`; si alguno está ocupado, cambiar
`SAPI_BACKEND_PORT`, `SAPI_ML_PORT` o `SAPI_DB_PORT` en `.env`.

```bash
curl http://localhost:8080/health
curl http://localhost:8000/health
curl http://localhost:8080/api/v1/ranking
```

`GET /api/v1/ranking` pide el ranking al servicio ML, lo valida y lo guarda en
PostgreSQL (una fila en `ejecuciones` y 50 en `predicciones_celda`) antes de
responder 200; repetir la misma evaluación no la duplica. El esquema lo crea
Flyway al arrancar el backend, desde `db/migration` (V001–V003).

**Modo de datos: reproducible (ADR-009).** El servicio ML puntúa con el
Modelo D versionado y el snapshot real congelado de Hito 1
(`artifacts/hito1/reproducibility`, incluido en la imagen). Por eso el
ranking corresponde siempre a `forecast_time` 2026-09-01T00:00Z y es idéntico
en cualquier equipo: no es una corrida diaria operacional. El score es un
ranking relativo entre las 50 celdas (`score_semantics=relative_rank`,
`scientific_model_validation=false`), no una probabilidad calibrada de
incendio ni una alerta oficial.

Último ranking persistido, con la consulta versionada
`db/queries/latest_ranking.sql`:

```bash
docker compose exec -T db-v2 sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < db/queries/latest_ranking.sql
# Windows (PowerShell):
# Get-Content db/queries/latest_ranking.sql | docker compose exec -T db-v2 sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

Detener y reiniciar:

```bash
docker compose down             # detiene y elimina todos los contenedores del proyecto (también los de Hito 1); los volúmenes quedan
docker compose up -d --wait     # vuelve a levantar con los mismos datos
```

Para borrar **solo** la base v2 (se pierde la persistencia local de
ejecuciones):

```bash
docker compose down
docker volume ls --filter name=sapi_v2_pgdata   # nombre real: <proyecto>_sapi_v2_pgdata
docker volume rm <proyecto>_sapi_v2_pgdata
```

`docker compose down -v` es un reset total: borra **todos** los volúmenes de
`docker-compose.yml`, incluida la base legacy de Hito 1 (`sapi_pgdata`),
aunque su profile no esté activo. Usarlo solo si también se quiere perder esa
base.

**Servicios de Hito 1.** Quedan fuera de la arquitectura v2 con profiles de
Compose y no se levantan por defecto: `legacy` (`db-postgis`,
`analytics-backend`, `web-presentation`) y `ops` (`n8n-bridge`). Nombrar un
servicio lo levanta junto con sus dependencias, por ejemplo
`docker compose up --build web-presentation` para el dashboard Streamlit de
Hito 1 en `http://localhost:8501`. Ese dashboard todavía no consume el
backend (SAPI-61), y sin datos locales en `data/` su modo Prototipo no puede
puntuar; para una corrida sin datos locales, usar la Opción B con
`SAPI_REPRODUCIBILITY_MODE=1`. `db-postgis` también publica el puerto 5432: para usar la
base legacy y la v2 a la vez, cambiar `SAPI_DB_PORT`.

### Opción B — Entorno local

```bash
git clone https://github.com/DanielCortezF002/S.A.P.I-Sistema-de-Prediccion-de-Incendios.git
cd S.A.P.I-Sistema-de-Prediccion-de-Incendios

python3.14 -m venv .venv
source .venv/bin/activate        # Linux / macOS
# .venv\Scripts\activate         # Windows

pip install --upgrade pip
pip install -r requirements-dev.txt   # incluye requirements.txt + herramientas de test

pytest                                # gate de cobertura 80 % (pytest.ini)
SAPI_REPRODUCIBILITY_MODE=1 streamlit run app/app.py
```

Servicios v2 por separado:

```bash
SAPI_REPRODUCIBILITY_MODE=1 uvicorn services.ml_api.main:app --port 8000   # servicio ML
cd services/backend && ./mvnw verify                                        # backend: tests
cd services/backend && ./mvnw spring-boot:run                               # backend en :8080
curl http://localhost:8080/api/v1/ranking                                   # ranking vía backend
```

El backend se configura por variables de entorno (sin secretos):

| Variable | Default | Uso |
|---|---|---|
| `SERVER_PORT` | `8080` | Puerto del backend |
| `SAPI_ML_BASE_URL` | `http://localhost:8000` | URL del servicio ML |
| `SAPI_ML_CONNECT_TIMEOUT` | `2s` | Timeout de conexión al servicio ML |
| `SAPI_ML_READ_TIMEOUT` | `60s` | Plazo total para recibir la respuesta del servicio ML; debe superar la duración del scoring |

Un timeout sin unidad se lee en segundos (`60` = 60 s).

`GET /api/v1/ranking`:
- acepta `forecast_time` en RFC 3339 con zona horaria; un `+` del offset va
  codificado como `%2B`;
- devuelve el ranking del servicio ML sin reordenarlo;
- sus errores siguen `contracts/openapi/backend.v0.yaml` (422, 500, 502, 503,
  504), y cada respuesta lleva `X-Request-Id`.

Para logs en JSON, usar `LOGGING_STRUCTURED_FORMAT_CONSOLE=logstash`.

---

## Demo

En la versión objetivo, el sistema muestra un mapa de la zona de estudio
donde cada celda se colorea según su posición en el **ranking relativo** de
riesgo de la evaluación actual:

- 🟢 **Verde** — Riesgo relativo bajo
- 🟠 **Ámbar** — Riesgo relativo medio
- 🔴 **Rojo** — Riesgo relativo alto

La demo de esta entrega no cubre la región completa: son 50 celdas de
0,0411° × 0,035° (≈3,8 × 3,9 km, ≈15 km² cada una) sobre el corredor
Viña del Mar – Quilpué – Villa Alemana, definidas en `src/geo/grid.py`. Los
documentos de Hito 1 que citan "~11,5 km²" se refieren a los círculos de
visualización legacy, no a las celdas reales. Ver
[`docs/alcance-prototipo.md`](docs/alcance-prototipo.md).

El nivel medio era amarillo hasta la centralización de tokens de diseño. Se
cambió a ámbar porque el amarillo daba 1,66:1 de contraste sobre el mapa base,
por debajo del mínimo de 3:1 que WCAG 2.1 pide para un elemento gráfico: el
relleno de una celda de riesgo medio era prácticamente invisible. La paleta
completa vive en `app/theme/tokens.py` y sus umbrales los verifica
`tests/test_theme.py`.

Al seleccionar una celda, el analista ve su posición en el ranking, su score
relativo (comparable solo con las demás celdas de la misma evaluación) y el
contexto disponible: meteorología regional, topografía e historial de
detecciones FIRMS. Las celdas empatadas comparten posición y el empate se
muestra explícitamente.

---

## Integración Continua

El workflow `.github/workflows/ci.yml` define un job que ejecuta `black
--check`, `flake8` y `pytest` (gate de cobertura 80 %) sobre `push` y
`pull_request` hacia `main` y `develop`. **A la fecha (2026-10-08) GitHub
Actions no registra ninguna ejecución de este workflow**, y no existe despliegue
automático. Su actualización y primera ejecución verificable es parte del
Quality Gate W0 de Sprint 2 (`artifacts/hito2/`).

### Estrategia de ramas

| Rama | Propósito |
|------|-----------|
| `main` | Código integrado |
| `develop` | Rama de integración histórica |
| `feat/SAPI-XX-…`, `docs/…`, `chore/…` | Una rama por issue de Jira, integrada vía pull request |

---

## Metodología

El proyecto aplica de forma combinada:

- **Scrum** para la gestión del proyecto, con seguimiento en Jira (proyecto `SAPI`)
- **CRISP-DM** para el ciclo de vida del dato

---

## Contexto Académico

| Campo | Detalle |
|-------|---------|
| Institución | Universidad Andrés Bello — Facultad de Ingeniería |
| Escuela | Ingeniería en Computación e Informática |
| Asignatura | Portafolio de Proyectos (2026) |
| Autor | Daniel Gonzalo Cortez Fierro |
| Profesor Guía | Giannina Costa Lizama |

---

## Licencia

Pendiente de definición: el repositorio todavía no incluye un archivo
`LICENSE`.

---

<div align="center">
<sub>Construido para desplazar el paradigma de la gestión reactiva de incendios hacia la prevención inteligente.</sub>
</div>

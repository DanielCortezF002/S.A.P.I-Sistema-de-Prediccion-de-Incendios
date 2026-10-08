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
| Backend Spring Boot | Solo `GET /health` (SAPI-54); integración con el servicio ML pendiente (SAPI-57) | `services/backend/` |
| Contratos OpenAPI v0 | Definidos (SAPI-56) | `contracts/openapi/` |
| Esquema PostgreSQL/PostGIS v2 | Migraciones V001–V003 definidas (SAPI-58); persistencia de resultados pendiente (SAPI-59) | `db/migration/`, `db/README.md` |
| Streamlit | Implementado; hoy puntúa en el mismo proceso con `score_current_grid()`; consumo del backend pendiente (SAPI-61) | `app/` |
| Docker Compose de la arquitectura v2 | Pendiente (SAPI-60). El `docker-compose.yml` actual levanta los servicios de Hito 1 | `docker-compose.yml` |
| Ruta legacy (RF/XGBoost, `src/modelo/`, `src/pipeline/`) | Conservada solo como histórico; no es la ruta activa del Modelo D | `docs/architecture-stack-freeze-sprint2.md` §1 |

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
│   └── backend/         # Backend Spring Boot (SAPI-54): /health
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

- Python 3.14
- Docker y Docker Compose
- Java 21 (solo para el backend Spring Boot; el wrapper `mvnw` descarga Maven)

### Opción A — Docker Compose (estado actual)

> El `docker-compose.yml` actual levanta los servicios de Hito 1 (PostGIS
> legacy, loop analytics legacy, Streamlit y puente n8n). La composición de la
> arquitectura v2 (Spring Boot + FastAPI + PostGIS v2) es el entregable SAPI-60
> y todavía no está implementada.

```bash
git clone https://github.com/DanielCortezF002/S.A.P.I-Sistema-de-Prediccion-de-Incendios.git
cd S.A.P.I-Sistema-de-Prediccion-de-Incendios
cp .env.example .env            # completar valores locales; nunca versionar .env
docker compose up --build
```

La interfaz Streamlit queda en `http://localhost:8501`. Sin datos locales en
`data/`, el modo Prototipo del contenedor no puede puntuar (no hay
meteorología ni FIRMS recientes); para una corrida sin datos locales usar la
Opción B con `SAPI_REPRODUCIBILITY_MODE=1` (snapshot versionado de Hito 1,
`forecast_time` 2026-09-01T00:00Z).

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
cd services/backend && ./mvnw verify                                        # backend
```

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

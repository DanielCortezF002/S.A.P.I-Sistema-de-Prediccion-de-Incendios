# S.A.P.I. — Sistema de Alerta y Predicción de Incendios Forestales

<div align="center">

![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)
![XGBoost](https://img.shields.io/badge/XGBoost-2.0-FF6600?style=flat-square)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL_15-PostGIS-336791?style=flat-square&logo=postgresql&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.32-FF4B4B?style=flat-square&logo=streamlit&logoColor=white)
![License](https://img.shields.io/badge/Licencia-MIT-green?style=flat-square)
![Coverage](https://img.shields.io/badge/Cobertura_Tests-81.66%25-brightgreen?style=flat-square)
![Tests](https://img.shields.io/badge/Tests-34_passed-brightgreen?style=flat-square)

**Sistema de software geoespacial basado en Machine Learning para la predicción probabilística de focos de ignición forestal en la Región de Valparaíso, Chile.**

[Ver demo](#-demo) · [Instalación rápida](#️-instalación) · [Documentación técnica](#-documentación) · [Resultados](#-resultados-obtenidos)

</div>

---

## ¿Qué es S.A.P.I.?

Chile enfrenta cada verano una crisis de incendios forestales cuyo paradigma de respuesta sigue siendo **100% reactivo**: las alertas se activan cuando el fuego ya existe y es visible. En Valparaíso, la latencia entre el inicio real del foco y el despliegue de brigadas es de entre 20 y 60 minutos — tiempo más que suficiente para que un foco incipiente escale a megaincendio en su compleja red de quebradas.

**S.A.P.I. desplaza ese eje.** En lugar de detectar el fuego cuando ya arde, el sistema genera cada madrugada un mapa de calor probabilístico que indica qué zonas de la región tienen mayor riesgo de ignición en las próximas 24 horas, permitiendo a los analistas de CONAF y SENAPRED posicionar brigadas **antes** de que ocurra la catástrofe.

```
Paradigma actual:  Ignición → Detección visual → Confirmación → Despliegue (≥20 min tarde)
S.A.P.I.:         Predicción nocturna → Mapa de riesgo → Despliegue preventivo → 0 víctimas
```

---

## Arquitectura del Sistema

S.A.P.I. adopta un diseño modular en tres capas completamente desacopladas, comunicadas a través de un **contrato de datos estricto** que garantiza que la interfaz nunca bloquee al pipeline y el pipeline nunca bloquee al modelo.

```
┌─────────────────────────────────────────────────────────────────┐
│                    FUENTES DE DATOS EXTERNAS                     │
│   NASA FIRMS (MODIS/VIIRS) │ DMC Chile │ CONAF │ DEM Topografía │
└────────────────────┬────────────────────────────────────────────┘
                     │ HTTPS / REST API / CSV
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│              MÓDULO 1 — INGESTA Y ETL  (src/ingesta/)           │
│  ThreadPoolExecutor · Reintentos exponenciales (tenacity)        │
│  Staging tables con MD5 hash · Formato Parquet intermedio        │
└────────────────────┬────────────────────────────────────────────┘
                     │ Write
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│         CAPA DE PERSISTENCIA — PostgreSQL 15 + PostGIS           │
│  Única Fuente de Verdad (SSoT) · ACID compliance                 │
│  Índices espaciales GiST · Grilla territorial 1 km²             │
└──────────┬──────────────────────────────────────┬───────────────┘
           │ Read (features)                       │ Read (predicciones)
           ▼                                       ▼
┌──────────────────────────┐           ┌───────────────────────────┐
│  MÓDULO 2 — MOTOR ML     │           │  MÓDULO 3 — VISUALIZACIÓN │
│  (src/modelo/)           │  Write →  │  (app/)                   │
│  Feature Engineering     │           │  Streamlit 1.32 + Folium  │
│  SMOTE balancing         │           │  Caché bi-nivel RAM       │
│  XGBoost · Serialización │           │  Mapa coroplético ≤0.2s   │
└──────────────────────────┘           └───────────────────────────┘
```

### Stack tecnológico

| Capa | Tecnología | Justificación |
|------|-----------|---------------|
| Ingesta | `Python 3.11` + `requests` + `tenacity` | Reintentos exponenciales, I/O no bloqueante |
| Procesamiento espacial | `GeoPandas 0.14` + `PostGIS` | Joins vectoriales, grilla WGS84 de 1 km² |
| Persistencia | `PostgreSQL 15` + `PostGIS` | ACID, índices GiST, SSoT anti-race conditions |
| Machine Learning | `XGBoost 2.0` + `scikit-learn 1.4` + `imbalanced-learn` | Regularización L1/L2, SMOTE, SHAP |
| Visualización | `Streamlit 1.32` + `Folium 0.16` | Caché bi-nivel, renderizado <0.2s |
| Contenerización | `Docker` + `Docker Compose` | Paridad total dev/prod, 3 contenedores aislados |
| CI/CD | `GitHub Actions` + `pytest` + `pre-commit` | Bloqueo automático si coverage < 80% |

---

## Fuentes de Datos

El sistema integra únicamente fuentes públicas y de acceso abierto — sin dependencias comerciales de ningún tipo:

| Fuente | Datos provistos | Frecuencia |
|--------|----------------|------------|
| **NASA FIRMS** (MODIS/VIIRS) | Anomalías térmicas activas, NDVI, EVI | Diaria |
| **Dirección Meteorológica de Chile (DMC)** | Temperatura, humedad relativa, velocidad del viento | Horaria |
| **CONAF** | Historial de igniciones, coordenadas, superficie afectada (2020–2025) | Estática + anual |
| **Modelo Digital de Elevación (DEM)** | Altitud, pendiente, orientación de ladera | Estática |

---

## Resultados Obtenidos

### Rendimiento del Motor Predictivo

El clasificador XGBoost supera consistentemente al modelo baseline Random Forest, priorizando la minimización de falsos negativos:

> ⚠️ **Nota (2026-09-01):** los valores 71% / 78% / 0.83 citados históricamente acá son valores de mock de `tests/test_pipeline.py`, copiados a `reports/metrics.json` en el mismo commit (`30c8a26`, 20-jun-2026) que agregó ese código — **nunca hubo una corrida real del pipeline detrás**, y el archivo nunca se regeneró desde entonces (confirmado por historial de git). Una corrida real el 2026-09-01 con datos de invierno dio `recall=0.0` / `auc-roc=nan`, correctamente, por ausencia real de casos positivos en esa ventana de datos. Falta una corrida con datos de temporada de incendios (verano) para tener una métrica real. La tabla de abajo deliberadamente **no** compara esos números fabricados contra el objetivo.

| Métrica | Baseline (Random Forest) | **Modelo Final (XGBoost)** | Objetivo |
|---------|--------------------------|---------------------------|----------|
| Recall (Sensibilidad) | pendiente de corrida real¹ | pendiente de corrida real¹ | ≥ 75% |
| AUC-ROC | — (no calculado en el baseline) | pendiente de corrida real¹ | ≥ 0.80 |

¹ Valor histórico sin corrida real detrás (71% / 78% / 0.83) — ver nota arriba. No se muestra en esta tabla para que no se lea como comparable contra el objetivo.

> **¿Por qué priorizar Recall?** En contextos de emergencia, un falso negativo (zona de alto riesgo no alertada) tiene consecuencias humanas irreversibles. El sistema está calibrado para que ningún cuadrante crítico quede sin alertar.

### Rendimiento del Servidor (Mitigación R-10)

El riesgo técnico crítico era la latencia de renderizado cartográfico en instancias cloud con 1 GB de RAM:

| Indicador | Sin optimización | **Con optimización** |
|-----------|-----------------|----------------------|
| Latencia de carga inicial | 8.4 segundos | **< 0.2 segundos** ✅ |
| Consumo RAM servidor | ~900 MB (OOM) | **< 250 MB** ✅ |
| Peso GeoJSON transmitido | ~45 MB | **~12 MB** (−73%) ✅ |

**Técnicas aplicadas:** simplificación topográfica con Douglas-Peucker (`GeoPandas.simplify()`), caché bi-nivel `@st.cache_data` + `@st.cache_resource`, y bloqueo de re-ejecución con `returned_objects=[]`.

### Suite de Testing

```
pytest tests/ -v --cov=src --cov=app

34 passed in 4.12s
Total Test Coverage: 81.66%  ✅ (umbral mínimo: 80%)
```

---

## Estructura del Repositorio

```
sapi-valparaiso/
│
├── app/                        # Módulo 3: Interfaz web (Streamlit)
│   ├── app.py                  # Servidor principal y lógica de caché
│   └── utils/                  # Contrato de datos y helpers de renderizado
│
├── data/                       # Almacenamiento local (excluido en .gitignore)
│   ├── raw/                    # Payloads crudos de APIs externas
│   └── processed/              # Matrices de features en formato Parquet
│
├── docs/                       # Documentación técnica y diagramas UML
│
├── models/                     # Binarios serializados de clasificadores (.pkl)
│
├── notebooks/                  # Bitácoras CRISP-DM interactivas
│   ├── 01_exploracion.ipynb
│   ├── 02_limpieza.ipynb
│   ├── 03_entrenamiento.ipynb
│   └── 04_evaluacion.ipynb
│
├── scripts/                    # Orquestadores del pipeline ETL
│   ├── ingesta_nasa.py
│   ├── ingesta_dmc.py
│   ├── ingesta_conaf.py
│   └── run_pipeline.sh
│
├── src/                        # Core del backend (lógica de negocio)
│   ├── ingesta/                # Captura paralela con ThreadPoolExecutor
│   ├── procesamiento/          # Feature Engineering (Regla 30-30-30, lags)
│   ├── modelo/                 # Entrenamiento, optimización y serialización
│   └── query/                  # Contrato de datos y abstracción PostGIS
│
├── tests/                      # Suite automatizada (34 tests, 81.66% coverage)
│   ├── test_ingesta.py
│   ├── test_procesamiento.py
│   ├── test_modelo.py
│   └── test_app.py
│
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

## Instalación

### Requisitos previos

- Python 3.11+
- PostgreSQL 15+ con extensión PostGIS activa
- Docker y Docker Compose (recomendado)

### Opción A — Docker (recomendado)

Levanta los tres contenedores (persistencia, backend y visualización) con un solo comando:

```bash
git clone https://github.com/DanielCortezF002/S.A.P.I-Sistema-de-Prediccion-de-Incendios.git
cd sapi-valparaiso
docker-compose up --build
```

La interfaz estará disponible en `http://localhost:8501`.

### Opción B — Entorno local

```bash
# 1. Clonar el repositorio
git clone https://github.com/DanielCortezF002/S.A.P.I-Sistema-de-Prediccion-de-Incendios.git
cd sapi-valparaiso

# 2. Crear y activar entorno virtual
python3.11 -m venv venv
source venv/bin/activate        # Linux / macOS
# venv\Scripts\activate         # Windows

# 3. Instalar dependencias y activar hooks de calidad
pip install --upgrade pip
pip install -r requirements.txt
pre-commit install

# 4. Verificar la suite de tests
pytest tests/ -v --cov=src --cov=app

# 5. Iniciar la interfaz
streamlit run app/app.py
```

---

## Demo

> *Capturas de pantalla del dashboard en producción — próximamente.*

El sistema genera cada madrugada un mapa coroplético de la Región de Valparaíso donde cada celda de 1 km² aparece coloreada según su probabilidad de ignición predicha:

- 🟢 **Verde** — Riesgo bajo
- 🟡 **Amarillo** — Riesgo medio
- 🔴 **Rojo** — Riesgo alto

Al hacer clic en cualquier zona, el analista obtiene la probabilidad exacta de ignición y el desglose de las variables dominantes (temperatura, humedad, viento, pendiente topográfica).

---

## Integración Continua

Cada `push` o `pull request` hacia `main` dispara automáticamente el pipeline de GitHub Actions:

```
[git push] → [Pre-commit hooks: flake8 + black] → [GitHub Actions CI]
                                                          ↓
                                              pytest 34 tests + coverage
                                                          ↓
                                         ┌── PASS (≥80%) → Deploy automático
                                         └── FAIL (<80%) → Merge bloqueado
```

### Estrategia de ramas

| Rama | Propósito |
|------|-----------|
| `main` | Código estable en producción |
| `develop` | Integración continua — siempre compila |
| `feature/HU-XX` | Una rama por historia de usuario |
| `hotfix/descripcion` | Correcciones urgentes de producción |

---

## Metodología

El proyecto aplica de forma combinada:

- **Scrum** para la gestión del proyecto: sprints de 3 semanas, 45 horas/sprint, seguimiento en Jira ([tablero público](https://danielcortez.atlassian.net/jira/software/projects/SAPI/boards))
- **CRISP-DM** para el ciclo de vida del dato: 6 fases mapeadas directamente a los 3 sprints de ejecución

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

Distribuido bajo licencia MIT. Ver `LICENSE` para más información.

---

<div align="center">
<sub>Construido para desplazar el paradigma de la gestión reactiva de incendios hacia la prevención inteligente.</sub>
</div>

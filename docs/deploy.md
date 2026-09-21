# Despliegue Prototipo S.A.P.I.

Este documento describe el despliegue del **prototipo funcional de demostración académica**.
No es una guía de infraestructura industrial en producción.

## CURRENT — Hito 1: entorno reproducible actual (verificado 09-09-2026)

**Esto es lo que el incremento evaluado en Hito 1 realmente usa.** El incremento
es un **prototipo local**, ejecutado bajo demanda (`streamlit run app/app.py`),
no un servicio desplegado con disponibilidad monitoreada (ver
`docs/informe-hito1-final.md`, `docs/arquitectura-hito1.md` sección 9). No se
afirma que este entorno haya estado definido/en uso durante Sprint 1 (03-08 a
31-08-2026) — es el estado reproducible verificado hoy, 09-09-2026, sobre el
mismo código y el mismo `models/prototype_model_d.pkl` ya publicado.

| Componente | Versión | Verificado |
|---|---|---|
| Python | **3.14.6** | `.github/workflows/ci.yml`, `Dockerfile.analytics`, `Dockerfile.web` |
| numpy | 2.5.2 | reproduce Modelo D bit a bit (`max\|Δpredict_proba\|=0.0`) |
| scikit-learn | 1.9.0 | ídem |
| pandas / pyarrow | 3.0.5 / 25.0.1 | suite completa 470/470 |
| Resto de versiones | ver `requirements.txt` / `requirements-dev.txt` | instalación limpia verificada en venv aislado y en Docker |

**Reproducir el entorno:**
```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements-dev.txt   # incluye requirements.txt
pytest                                                # 442 passed, 29 skipped desde un clon limpio
                                                       # (471 passed si ya tienes data/ y models/*.pkl generados localmente)
docker compose up --build                              # Dashboard: http://localhost:8501
```

**Mecanismo de despliegue real hoy:** Docker Compose local (`docker-compose.yml`)
— verificado con un contenedor real activo en esta máquina el 09-09-2026. No hay
evidencia de una instancia de Streamlit Cloud activa (sin URL pública, sin badge
"demo en vivo" en el repo) — ver sección OPTIONAL/FUTURE abajo.

### Reproducibilidad de datos y modelo — auditoría 09-09-2026

**Formalización posterior al cierre histórico de Sprint 1 (31-08-2026).** Lo
que sigue describe el estado del repositorio verificado **hoy**, no algo que
haya existido durante Sprint 1.

`data/` completo y la mayoría de `models/*.pkl` **NO** están versionados en git
(`.gitignore`). **Excepción quirúrgica desde 09-09-2026:**
`models/prototype_model_d.pkl` (el Modelo D oficial, 68 KB) **sí** está
versionado — verificado que coincide con el hash de su propio
`metadata.json` y con `dataset_hash`. El dataset temporal
(`temporal_dataset_h6.parquet`, 10,8 MB) **no** se versionó:
`LICENSE_NOT_CONFIRMED` — el repo no documenta los términos de redistribución
de datos derivados de NASA FIRMS/DMC/Copernicus, y no se asumió una condición
legal sin evidencia (ver `artifacts/hito1/reproducibility/manifest.json`,
sección `licencia_dataset`).

### Dos modos de score_current_grid()

**MODO NORMAL (por defecto, sin cambios de comportamiento):**
```bash
streamlit run app/app.py
```
Usa `data/raw/` operacional real (todo el histórico DMC disponible + lo más
reciente que exista), calcula `forecast_time`/frescura sobre el momento real.
Es lo que corre en producción/desarrollo normal — nada de esta sección lo
altera.

**MODO HITO 1 REPRODUCIBLE (opt-in explícito, 09-09-2026, cerrado en tercera
ronda):**
```bash
git clone <repo>
pip install -r requirements.txt      # basta con el runtime de producción
SAPI_REPRODUCIBILITY_MODE=1 python -c "from src.inference.prototype_service import score_current_grid; print(score_current_grid())"
```
Con `SAPI_REPRODUCIBILITY_MODE=1`, `score_current_grid()` lee **exclusivamente**
los 4 artefactos mínimos versionados bajo
`artifacts/hito1/reproducibility/` — DMC (2 archivos, ~4,3 MB), FIRMS
(`firms/nasa_firms_2021-08-30_2026-08-30.csv`, copia exacta del operacional,
1,3 MB) y DEM (`dem/grid_topography.csv`, tabla derivada de 1,6 KB generada
con la función real `load_grid_topography()`) — junto con el Modelo D
(`models/prototype_model_d.pkl`), sin ninguna llamada de red y **sin** leer
`data/raw/` ni `data/processed/`. **Verificado 09-09-2026 (tercera ronda):**
reproduce el resultado oficial exacto (`forecast_time=2026-09-01
00:00:00+00:00`, 50 celdas, 41/50 empatadas, celda top `VP-001`,
`score=0.13129336874795144`) — probado con la red bloqueada en dos entornos
independientes: (a) un venv de solo-producción (`requirements.txt`, sin
`requirements-dev.txt`) con `socket.socket.connect` parcheado para lanzar
excepción, y (b) un contenedor Docker (`Dockerfile.web`) corrido con
`docker run --network none`, construido desde un build context que respeta
`.dockerignore` (no ve `data/raw/` ni `data/processed/` locales). Test de
regresión: `tests/test_prototype_service.py::test_reproducibility_mode_works_fully_offline`.
El banner de frescura sigue funcionando honestamente: clasifica estos datos
como **"DATOS HISTÓRICOS / DESACTUALIZADOS"**, nunca como meteorología en
tiempo real.

**Limitación anterior, ya cerrada (09-09-2026, tercera ronda):** en la ronda
previa, el snapshot DMC resolvía solo la parte meteorológica y
`score_current_grid()` fallaba explícitamente (`PrototypeUnavailableError`) al
faltar FIRMS/DEM versionados. Se cerró versionando el mínimo necesario de
ambos (ver arriba) — decisión de seguridad/licencia documentada en
`artifacts/hito1/reproducibility/manifest.json` (`licencia_dataset` y
`cadena_de_proveniencia`).

**Segunda limitación anterior, ya cerrada (09-09-2026, tercera ronda):**
`requirements.txt` no incluía `joblib`, `scikit-learn`, `rasterio` ni
`imbalanced-learn`, pese a ser dependencias reales de runtime (no solo de
entrenamiento) para `score_current_grid()`: `joblib`/`scikit-learn` porque
`joblib.load()` deserializa un `HistGradientBoostingClassifier`;
`rasterio` porque `prototype_service.py` importa a nivel de módulo
`src.procesamiento.dem_features`, que importa `rasterio`
incondicionalmente aunque esa ruta no se ejecute en modo reproducibilidad;
`imbalanced-learn` porque `src.procesamiento.regional_meteo` importa
transitivamente el módulo legacy `src.procesamiento.features` (NDVI/SMOTE) —
un acoplamiento real del pipeline temporal nuevo al legacy que contradice la
afirmación de aislamiento total en `docs/arquitectura-hito1.md` y queda
señalado aquí como hallazgo, sin corregirse arquitectónicamente (fuera de
alcance de esta acción). Las 4 dependencias se descubrieron empíricamente
ejecutando el contenedor con `docker run --network none` y confirmando cada
`ModuleNotFoundError` uno a uno, más una auditoría sistemática de
`sys.modules` para descartar dependencias adicionales ocultas. Corregido
añadiendo las 4 a `requirements.txt` con las mismas versiones ya verificadas
reproduciendo el Modelo D bit a bit (`scikit-learn==1.9.0`, `joblib==1.5.3`,
`rasterio==1.4.4`, `imbalanced-learn==0.14.2`).

**RUTA B — reconstrucción desde fuentes externas (opcional, no bit-a-bit garantizada):**
```bash
python scripts/backfill_nasa_firms.py
python scripts/backfill_dmc_historico.py
python scripts/build_temporal_dataset.py
python scripts/build_prototype_model.py         # reentrena; comparar su hash contra manifest.json
```
Depende de que NASA FIRMS/DMC/Copernicus devuelvan datos históricos idénticos
a los originales — sin garantía documentada de que eso ocurra (ver
`apis_externas_garantizan_reconstruccion_bit_a_bit` en el manifest).

Verificado con un clon limpio simulado (371 archivos = `git ls-files` +
`git ls-files --others --exclude-standard`, sin archivos locales ignorados) y,
para R3, adicionalmente con Docker (`--network none`) y un venv de
solo-producción con la red bloqueada por código:

| Dimensión | Estado | Qué significa |
|---|---|---|
| **R1 — entorno** | `VERIFIED` | Un clon limpio instala el entorno declarado (`requirements*.txt`, incluidas las 4 dependencias de runtime corregidas 09-09-2026) y corre sin errores |
| **R2 — build/tests** | `VERIFIED` | Clon limpio (371 archivos) + `requirements-dev.txt`: 454 passed, 23 skipped explícitos, 0 fallos, cobertura 87,77% (gate 80% cumplido). Repo real (con datos locales adicionales): 477 passed, 0 skipped, cobertura 91,72% — 477 = 454 + 23, consistente |
| **R3 — inferencia con el Modelo D oficial** | `VERIFIED` (cerrado 09-09-2026, tercera ronda) | Modelo D + snapshots mínimos DMC/FIRMS/DEM versionados; `SAPI_REPRODUCIBILITY_MODE=1` reproduce el resultado oficial exacto sin red, verificado en venv de solo-producción y en Docker `--network none` — ver detalle arriba |
| **R4 — reentrenamiento científico desde las fuentes** | `NOT_VERIFIED_FROM_CLEAN_CLONE` (fuera de alcance de esta acción) | El dataset completo no se congeló en git (licencia no confirmada, y versionar todos los RAW históricos no está autorizado) — reentrenar desde un clon limpio sigue requiriendo Ruta B. Desacoplado de R3: la inferencia con el modelo ya entrenado no depende del reentrenamiento |

Detalle completo (hashes, endpoints, comandos de reconstrucción, cadena
fuente→modelo): `artifacts/hito1/reproducibility/manifest.json`. Verificar el
estado local contra ese manifest: `python scripts/verify_reproducibility.py`.

**Formulación defendible de "reproducibilidad" para este proyecto:**
*"Reproducibilidad verificada para entorno, pruebas de software e inferencia
(R1, R2 y R3): un clon limpio, sin datos locales y sin acceso a internet,
instala el entorno declarado, pasa la suite de pruebas y reproduce
exactamente la salida oficial de `score_current_grid()` (mismas 50 celdas,
mismo ranking, mismo empate de 41 celdas, mismo score de la celda top) usando
únicamente el Modelo D y los snapshots mínimos versionados de DMC, FIRMS y
DEM. El banner de frescura sigue reportando honestamente estos datos como
históricos. La reconstrucción científica completa desde las fuentes externas
(reentrenamiento desde cero, R4) se mantiene como ruta separada (Ruta B) y no
se asume bit a bit estable, porque el dataset de entrenamiento completo no
pudo congelarse en el repositorio (licencia de los datos derivados no
confirmada, y versionar todos los datos RAW históricos excede el alcance
autorizado)."*

## OPTIONAL/FUTURE — Streamlit Cloud + Supabase PostGIS (legacy, no evaluado en Hito 1)

**No forma parte del incremento evaluado en Hito 1.** Documentado aquí como
información histórica/una ruta posible, sin afirmar que esté operacional. Nació
el 20-06-2026 (misma era que el pipeline legacy, anterior al Modelo D actual) y
describe una arquitectura Streamlit Cloud + Supabase que el prototipo del pipeline
temporal (evaluado en Hito 1) no usa — `prototype_service.py` lee directo de
`data/`/`models/`, sin pasar por PostGIS.

### Arquitectura cloud (conexión híbrida)

| Capa | Puerto | Variable | Uso |
|------|--------|----------|-----|
| Streamlit Cloud | 6543 | `DATABASE_URL` | Connection Pooler (UI serverless) |
| Pipeline batch | 5432 | `DATABASE_URL_DIRECT` | Ingesta y escrituras PostGIS |
| Migraciones DDL | 5432 | manual | `psql` contra instancia directa |

## 1. Provisionar Supabase PostGIS

1. Crear proyecto en [supabase.com](https://supabase.com).
2. Habilitar extensión PostGIS en SQL Editor:

```sql
CREATE EXTENSION IF NOT EXISTS postgis;
```

3. Ejecutar scripts locales **desde tu máquina** contra el host directo (puerto 5432):

```bash
psql "postgresql://postgres.[PROJECT]:[PASSWORD]@db.[PROJECT].supabase.co:5432/postgres?sslmode=require" \
  -f docker/initdb/01_extensions.sql
psql ... -f docker/initdb/02_schema.sql
psql ... -f docker/initdb/03_gist_indexes.sql
psql ... -f docker/initdb/04_seed_valparaiso.sql
```

> **Importante:** No pegar SQL PostGIS en PowerShell. Usar `psql` o el SQL Editor de Supabase.
> En Windows sin `psql`, usar Docker contra el **pooler puerto 5432** (ver sección anterior del chat).

4. Si el seed ya estaba cargado (v1 cuadrados/aleatorio), **reemplazar** con seed v2:

```bash
psql ... -f docker/initdb/04_seed_valparaiso.sql
```

El seed v2 (`scripts/generate_seed.py`) usa microclimas costa/urbano/precordillera y celdas circulares ~11,5 km² sobre la grilla canónica de `src/geo/grid.py` (no series MeteoChile en vivo).

## 2. Streamlit Community Cloud — versión de Python

Streamlit Cloud **no usa** `runtime.txt`. Debes elegir la versión en el panel:

1. [share.streamlit.io](https://share.streamlit.io) → tu app → **Manage app**
2. **Settings** → sección **Python version** (o **Advanced settings** al crear la app)
3. **Save** → **Reboot app**

**Advertencia histórica (20-06-2026, ya no aplica al stack actual):** en esa
fecha, con `pandas==2.1.4` (versión antigua, sin wheels para Python 3.14),
crear la app con Python 3.14 producía fallos de compilación de `pandas` y
`psycopg2-binary`. El stack actual (`pandas==3.0.5`, versiones de
`requirements.txt`) instala y corre limpio en Python 3.14.6 **en Docker
local**, verificado 09-09-2026. **No verificado en Streamlit Cloud
específicamente** — Streamlit Cloud tiene su propio mecanismo de build, no
necesariamente idéntico a `docker build`. Si se reintenta este despliegue,
confirmar la versión de Python ahí antes de asumir compatibilidad.

Repo: `DanielCortezF002/S.A.P.I-Sistema-de-Prediccion-de-Incendios` · Main file: `app/app.py`

## 3. Variables en Streamlit Community Cloud

En [share.streamlit.io](https://share.streamlit.io), conectar el repositorio:

| Secreto | Valor |
|---------|-------|
| `DATABASE_URL` | `postgresql://...@aws-0-....pooler.supabase.com:6543/postgres?sslmode=require` |
| `NASA_FIRMS_API_KEY` | (opcional para demo con seed) |

Main file: `app/app.py`

## 4. Pipeline batch en cloud (opcional)

Ejecutar una vez con conexión directa:

```bash
DATABASE_URL_DIRECT="postgresql://...@db....supabase.co:5432/postgres?sslmode=require" \
  python -m src.pipeline.run_daily
```

## 5. Validación demo

- Mapa muestra **50 celdas** de riesgo en Valparaíso
- Popup incluye Regla 30-30-30
- `reports/metrics.json`: Recall XGBoost ≥ 0.75

## Desarrollo local

Ver sección **CURRENT** al inicio de este documento — es el entorno realmente
usado y verificado para el incremento de Hito 1.

```bash
copy .env.example .env
docker compose up --build
# Dashboard: http://localhost:8501
```

Todo el SQL y el bucle analítico corren **dentro de contenedores Linux**, no en PowerShell.

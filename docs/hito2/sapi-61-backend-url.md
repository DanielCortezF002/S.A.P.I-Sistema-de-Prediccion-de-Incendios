# SAPI-61 — Configuración `SAPI_BACKEND_BASE_URL` (Streamlit → backend REST)

Estado: **Etapa B** (rama `feat/SAPI-61-streamlit-backend-rest`, sin merge).
`main` ya incluye el Compose de SAPI-60. El dashboard v2 es el servicio
`web-v2` (profile `presentation`); el profile `legacy` no se activa.

## Qué cambia

El modo **Prototipo (datos reales)** del dashboard ya no ejecuta
`score_current_grid()` en el proceso de Streamlit. La vista nueva
`app/components/ranking_backend_view.py` consume únicamente
`GET {SAPI_BACKEND_BASE_URL}/api/v1/ranking` del backend Spring Boot
(`contracts/openapi/backend.v0.yaml`) a través de
`app/utils/backend_client.py`. El flujo por defecto ya no carga `src.inference`
ni el stack del Modelo D (regla en `tests/test_architecture.py`).

```
app/app.py ─► ranking_backend_view ─► BackendRankingClient ─HTTP GET─► Spring Boot /api/v1/ranking ─► FastAPI /predict ─► Modelo D
                     │
                     └─► src/geo/grid.py (geometría estática de las 50 celdas)
                     └─► artifacts/hito1/reproducibility/dem/grid_topography.csv (topografía de referencia, solo lectura)
```

La vista Hito 1 (`prototype_view.py`, congelada por `freeze_check`) sigue
disponible como "Prototipo local (legacy Hito 1)" solo con
`SAPI_UI_LEGACY_MODES=1` (decisión H7).

## Variables de entorno (`src/config.py`)

| Variable | Default | Uso |
|---|---|---|
| `SAPI_BACKEND_BASE_URL` | `http://localhost:8080` | URL base del backend (sin ruta). El cliente agrega `/api/v1/ranking`. |
| `SAPI_BACKEND_CONNECT_TIMEOUT` | `3` (s) | Timeout de conexión. |
| `SAPI_BACKEND_READ_TIMEOUT` | `90` (s) | Timeout de lectura: el backend espera al servicio ML (scoring de la grilla completa). |
| `SAPI_UI_LEGACY_MODES` | `0` | `1` muestra el modo legacy en el selector. Nunca es el default. |

Las tres primeras se leen en cada consulta (`get_backend_base_url()`,
`get_backend_timeouts()`), así que pueden inyectarse desde tests o cambiarse
sin reiniciar el proceso. Un timeout no numérico o ≤ 0 vuelve al default.

## Compose (profile `presentation`)

`docker compose up` sigue levantando solo `db-v2`, `ml-api` y `backend`.
Streamlit v2 es opt-in:

```bash
docker compose --profile presentation up --build web-v2
```

`web-v2` fija `SAPI_BACKEND_BASE_URL=http://backend:8080` por `environment:`
(sin `env_file`, misma higiene que `web-presentation`). No monta `data/` ni
depende de `db-postgis`. Publica `127.0.0.1:8501`.

Desde el host, contra el puerto publicado del backend, el default
`http://localhost:8080` alcanza el mismo `GET /api/v1/ranking`.

`README.md` y `.env.example` documentan `SAPI_BACKEND_BASE_URL`,
`SAPI_BACKEND_CONNECT_TIMEOUT`, `SAPI_BACKEND_READ_TIMEOUT` y
`SAPI_UI_LEGACY_MODES`. `scripts/merge_gate.py::V2_LINT_PATHS` incluye los
módulos de esta vista.

## Metadata opcional del contrato

`schema_version` sigue siendo `sapi-ranking-v0`. El `RankingResult` suma nueve
campos opcionales, emitidos por el servicio ML desde el resultado de la
evaluación (no los calcula Streamlit):

| Campo | Origen |
|---|---|
| `weather_timestamp` | observación DMC regional usada al puntuar |
| `age_hours` | instante de captura de la evaluación − `weather_timestamp` |
| `freshness` | clasificación de ese `age_hours` |
| `station_id`, `station_name` | estación DMC regional (no meteorología por celda) |
| `firms_origin`, `firms_coverage_end`, `firms_lag_days`, `firms_status` | archivo FIRMS usado (anomalías térmicas, no incendios confirmados) |

No se agregan `model_status`, `meteo_actual` ni `historical_count`.
`CellRanking` no cambia. Si un campo opcional no llega, la vista muestra
"no informado por el backend" y no asume que el ranking sea el riesgo actual.
`age_hours` puede cambiar entre dos evaluaciones con los mismos insumos,
porque el instante de captura es el reloj del servicio; la clave de
idempotencia persistida sigue siendo `(forecast_time, model_version,
inputs_fingerprint)`.

## Errores (CA4)

Conexión rechazada, timeout, HTTP 422/500/502/503/504, cuerpo vacío, JSON
inválido, cuerpo mayor a 2 MiB o ranking que no cumple el contrato terminan en
un `st.error` con mensaje genérico local (sin host, ruta ni stack trace). Del
cuerpo `Error` del contrato solo se muestra el `error_type` cuando pertenece
al enum conocido; el `message` remoto se trata como detalle operativo no
confiable y nunca se conserva ni se renderiza. La respuesta se lee en
streaming con el límite de tamaño aplicado durante la lectura, para cualquier
status. No se muestran datos cacheados como actuales: la cache (5 min) solo
guarda rankings validados y el instante de obtención se muestra en el
encabezado.

# SAPI-61 — Configuración `SAPI_BACKEND_BASE_URL` (Streamlit → backend REST)

Estado: **Etapa A** (rama `feat/SAPI-61-streamlit-backend-rest`, sin merge).
Este documento existe porque `README.md`, `.env.example` y `docker-compose*`
pertenecen a SAPI-60 (PR-4) y no se tocan en esta rama; la integración real en
Compose se hace en la Etapa B, después del merge de SAPI-60.

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

## Para la Etapa B (SAPI-60 / Compose)

- `tests/test_docker_build_hygiene.py` exige que `web-presentation` **no**
  reciba `env_file`; la variable debe ir por `environment:`:

  ```yaml
  web-presentation:
    environment:
      SAPI_BACKEND_BASE_URL: http://backend:8080
  ```

  (`backend` = nombre del servicio Spring Boot en el Compose de SAPI-60).
- Desde el host contra un backend en contenedor: `http://localhost:8080`
  (puerto publicado). Desde un contenedor hacia el host:
  `http://host.docker.internal:8080` (mismo patrón que `SAPI_SCORE_URL`).
- `README.md` y `.env.example` deben documentar las cuatro variables en el
  mismo PR que integre Compose.
- `scripts/merge_gate.py::V2_LINT_PATHS` debe incorporar
  `app/utils/backend_client.py`, `app/utils/reference_topography.py`,
  `app/components/ranking_backend_view.py`, `tests/test_backend_client.py`,
  `tests/test_ranking_backend_view.py` y `tests/test_sapi61_http_stub.py`
  (en Etapa A se verificaron a mano con `black --line-length 100` y
  `flake8 --max-line-length=100 --extend-ignore=E203,W503`).

## Comportamiento con el contrato v0 actual

El `RankingResult` v0 no transporta frescura (`weather_timestamp`,
`age_hours`, `freshness`), estación (`station_id`, `station_name`),
`model_status`, meteorología usada (`meteo_actual`) ni procedencia FIRMS
(`firms_*`). La vista los lee como opcionales: si llegan (extensión aditiva de
la Etapa B) se muestran tal cual; si no, muestra "no informado por el backend"
y una nota explícita de que no se asume que el ranking sea actual. Nunca se
derivan localmente. `historical_count` por celda no viaja (`CellRanking`
congelado, F4c) y se muestra como "no disponible en la respuesta del backend".

## Errores (CA4)

Conexión rechazada, timeout, HTTP 422/500/502/503/504, cuerpo vacío, JSON
inválido o ranking que no cumple el contrato terminan en un `st.error` con
mensaje genérico (sin host, ruta ni stack trace) más el `error_type` y el
`message` del cuerpo `Error` del contrato cuando existen. No se muestran datos
cacheados como actuales: la cache (5 min) solo guarda rankings validados y el
instante de obtención se muestra en el encabezado.

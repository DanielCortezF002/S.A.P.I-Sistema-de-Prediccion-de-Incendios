# SAPI-61 — Evidencia Etapa A: Streamlit → backend REST (PR-5, parcial)

| Campo | Valor |
|---|---|
| HU | SAPI-61 (S2-08) Adaptar Streamlit para consumir el backend REST |
| Rama | `feat/SAPI-61-streamlit-backend-rest` (base `main` @ `736e5b45c07e4104d3ba841d6a11c1a12c47d7fa`) |
| SHA de código | `6f62c1ab169a8995d917e72c66317d7d53c5c4ab` (Etapa A) → `4745b07` (delta correctivo Astra, ver sección al final) |
| Fecha | 2026-10-10 (UTC) |
| Entorno | Sandbox Linux (host `cursor`); Python 3.12.3; pytest 9.1.1; Streamlit 1.63.0; requests 2.34.2; folium 0.20.0. CI usa Python 3.14 (misma `requirements-dev.txt`) |
| Etapa | **A** (paralela a SAPI-60, sin tocar `contracts/`, `services/`, Compose, README, `.env.example`, `merge_gate.py`, `requerimientos-sprint2.md`). Etapa B = extensión aditiva del contrato + validación contra Spring/FastAPI reales |
| Freeze | `freeze_check_6f62c1a.txt/.json`: **FREEZE CHECK PASS** (27 PASS, modo B, con `ls-remote`) |

Etiquetas de evidencia usadas: **UNIT**, **COMPONENT**, **HTTP_STUB**,
**STREAMLIT_INTEGRATION**. **No hay FULL E2E** (Spring + FastAPI + Docker):
eso es SAPI-66 y la Etapa B.

## Criterios de aceptación

| CA | Verificación | Evidencia | Estado Etapa A |
|---|---|---|---|
| CA1. Streamlit deja de llamar `score_current_grid()` en el flujo principal | `app/app.py` enruta Prototipo a `ranking_backend_view`; `prototype_view.py` (congelado) solo con `SAPI_UI_LEGACY_MODES=1` e import perezoso. `tests/test_architecture.py`: `src.inference` prohibido en `app/` (excepción explícita `prototype_view.py`), sin identificador `score_current_grid`, import perezoso, árbol transitivo limpio en subproceso (`app.app`, vista, cliente: sin `src.inference`, `sklearn`, `joblib`) | `pytest_sapi61.xml` | **PASS** |
| CA2. Consume `GET /api/v1/ranking` | `BackendRankingClient` (`app/utils/backend_client.py`) con `SAPI_BACKEND_BASE_URL` (default `http://localhost:8080`), `Accept: application/json`, timeouts explícitos; stub HTTP real registra `GET /api/v1/ranking` y `forecast_time` | `http_stub_run.txt`, `pytest_sapi61.xml` | **PASS** (contra stub; Spring real en Etapa B) |
| CA3. Mapa, ranking, empates, frescura y trazabilidad se mantienen | Mapa: 50 `Rectangle` con geometría de `src/geo/grid.py`, click → `assign_cell`, selección, prioridad. Ranking/empates: `score`, `rank`, `display_rank`, `tie_group_size` y orden preservados byte a valor con la fixture real (empates 7/41/2). Trazabilidad: `model_version`, `forecast_time`, `inputs_fingerprint`, `horizon_hours`, `schema_version`, `score_semantics`. **Frescura/estación/`model_status`/meteo/FIRMS: el contrato v0 no los transporta** → estado explícito "no informado por el backend", sin banner inventado; el cliente/vista ya los renderizan si llegan (payload extendido probado) | `pytest_sapi61.xml`, `apptest_run.txt` | **PARCIAL — WAITING_FOR_ADDITIVE_CONTRACT** (mapa/ranking/empates/trazabilidad PASS; frescura pendiente de Etapa B) |
| CA4. Backend caído → mensaje visible y controlado | Conexión rechazada, timeout, 422/500/502/503/504, cuerpo vacío, JSON inválido, ranking inválido → `BackendError` tipado → `st.error` genérico (sin host/ruta/stack) + `error_type`/`message` del contrato. AppTest con puerto cerrado y con 503/504 | `apptest_run.txt`, `http_stub_run.txt` | **PASS** |
| CA5. No se rompe la funcionalidad del mapa | 50 geometrías, tooltips, selección por click y selectbox, grupo prioritario, panel de detalle (territorio de referencia, FIRMS "no disponible", meteo "no informada"), ranking completo. Regresión completa 1895 passed / 0 failed; cobertura 85,10 % (gate 80 %) | `regression_summary.txt`, `pytest_sapi61.xml` | **PASS** |

## Suites ejecutadas (`6f62c1a`)

| Suite | Etiqueta | Resultado |
|---|---|---|
| `tests/test_backend_client.py` | UNIT | 127 passed |
| `tests/test_ranking_backend_view.py` | COMPONENT | 41 passed |
| `tests/test_sapi61_http_stub.py` (cliente) | HTTP_STUB | 15 passed |
| `tests/test_sapi61_http_stub.py` (AppTest) + `tests/test_app_integration.py` | STREAMLIT_INTEGRATION | 10 + 5 passed |
| `tests/test_architecture.py` (incl. 3 reglas CA1 nuevas + 3 entrypoints) | UNIT | 8 passed |
| Total SAPI-61 (`pytest_sapi61.xml`) | — | **206 passed, 0 failed** |
| Regresión completa (`pytest -q`) | — | **1895 passed, 137 skipped, 0 failed; cobertura 85,10 %** |

Cobertura de los módulos nuevos: `backend_client.py` 99 %,
`ranking_backend_view.py` 96 %, `reference_topography.py` 94 %,
`src/config.py` 100 %, `app/app.py` 93 %.

## Matriz de brecha contractual (resumen; completa en el reporte de Etapa A)

| Campo | Uso UI | Fuente autoritativa | En backend v0 | Estático/Dinámico | Resoluble local | Viaja por REST | Decisión Etapa A |
|---|---|---|---|---|---|---|---|
| `cell_id`, `score`, `rank`, `display_rank`, `tie_group_size` | mapa, prioridad, panel, tabla | servicio ML | sí | dinámico | n/a | ya viaja | preservado exacto |
| `forecast_time`, `horizon_hours`, `model_version`, `inputs_fingerprint`, `score_semantics`, `scientific_model_validation`, `schema_version`, `disclaimer` | header, panel, tech | servicio ML | sí (`horizon_hours`/`disclaimer` opcionales) | dinámico | n/a | ya viaja | preservado/verificado; `inputs_fingerprint` sustituye a `dataset_hash` local |
| `geometry` (per-cell) | mapa, click | `src/geo/grid.py` (misma fuente del servicio) | no | estático | sí | no | local autoritativo |
| `elevation`, `slope` (per-cell) | tooltip, panel | `artifacts/hito1/reproducibility/dem/grid_topography.csv` (F5; lo que consume el servicio en modo H8) | no | estático | sí (solo lectura, etiqueta "referencia") | no (`CellRanking` congelado, F4c) | local autoritativo; N/D sin cobertura (20 celdas) |
| `weather_timestamp`, `age_hours`, `freshness` | banner, badge, tech | servicio ML (corrida) | **no** | dinámico | **no** (sería inventar frescura) | **sí, opcional** | Etapa B; hoy "no informado" |
| `station_id`, `station_name`, `model_status` | header, tech | servicio ML | **no** | dinámico (identidad de corrida) | no (acoplamiento oculto) | **sí, opcional** | Etapa B; hoy "no informado" |
| `meteo_actual{4}` | KPIs, panel | servicio ML (observación usada) | **no** | dinámico | no (`data/raw` local ≠ observación que puntuó) | **sí, opcional** (requiere superseder H6/ADR-010 §5/nota CA3) | Etapa B; hoy "no informado" |
| `firms_origin`, `firms_coverage_end`, `firms_lag_days`, `firms_status` | tech (nuevo) | servicio ML | **no** | dinámico | no | **sí, opcional** | Etapa B; hoy "no informado" |
| `historical_count` (per-cell) | tooltip, panel | feature interna de la corrida | no | dinámico | no | no (F4c + H6) | "no disponible en la respuesta del backend"; nunca 0 |
| `dataset_hash` (archivo local), `scoring_inputs`, `meteo_actual.momento_observacion` | tech / no leído | — | no | — | — | no | no requeridos (sustituidos o duplicados) |

## Archivos

| Archivo | Contenido |
|---|---|
| `pytest_sapi61.xml` | JUnit de las 5 suites SAPI-61 (206 tests) |
| `pytest_sapi61_console.txt` | Consola `-rA` de esa ejecución |
| `http_stub_run.txt` | HTTP_STUB: cliente contra `http.server` real |
| `apptest_run.txt` | STREAMLIT_INTEGRATION: AppTest de `app/app.py` |
| `regression_summary.txt` | Resumen de la regresión completa con cobertura |
| `lint_manual.txt` | `black`/`flake8` de los archivos nuevos (limpios) y deuda preexistente de los legacy tocados |
| `freeze_check_6f62c1a.txt`, `freeze_check_6f62c1a.json` | `python -B scripts/freeze_check.py` en `6f62c1a`: PASS |

Saneamiento: sin rutas personales, usuarios, tokens ni dominios; host = `cursor`.

## Delta correctivo Astra (STAGE_A_FIX_REQUIRED)

Base del delta `fb3dd05a685015a3b4bcefec54b639b5afa1d6cb`; código corregido en
`580bd5b` (producto) + `4745b07` (tests). Sin cambios en contratos, servicios,
Compose, README, `.env.example`, `prototype_view.py`, `score_contract.py`,
`merge_gate.py`, requerimientos, Flyway ni modelos.

| Hallazgo | Corrección | Tests discriminantes |
|---|---|---|
| MAJOR 1 — límite de cuerpo aplicado tarde | `fetch_ranking()` usa `stream=True`; `Content-Length > 2 MiB` falla antes de leer; sin/mal `Content-Length` se lee por chunks de 64 KiB (`iter_content`) y se aborta al cruzar el límite, para **todos** los status; nunca `response.content` ni `response.json()`; JSON desde los bytes acotados; `response.close()` en `finally`; `Timeout`→`timeout`, otras `RequestException` durante el stream→`connection`; en status de error, cuerpo grande/ilegible→`http_backend` sin `error_type` | UNIT: fake cuyo `.content`/`.json()` lanzan `AssertionError`; >2 MiB con/sin CL (200 y 500/503), cruce en `iter_content`, CL falso/inválido, fallo a mitad (4 excepciones), frontera exacta y +1, `close()` contado en 7 caminos. HTTP_STUB: CL real, sin CL (HTTP/1.0), chunked (200 y 503), CL pequeño/enorme que miente, transferencia incompleta, frontera exacta y +1, `raw.closed` y `_content_consumed is False` |
| MAJOR 2 — `message` remoto en la UI | `BackendError` ya no tiene `backend_message`; `error_type` solo si ∈ `KNOWN_ERROR_TYPES` (enum del contrato); `_render_backend_error` muestra solo texto local + ese `error_type` (re-filtrado) | 8 mensajes maliciosos (ruta Windows, ruta Unix, host interno, DSN con credencial, markdown, HTML/script, controles, traceback) × {objeto de error, `st.*` mockeado, AppTest real}; `error_type` fuera del contrato no se renderiza; no hashable no rompe |
| MINOR 1 — `window_end` desborda | `forecast_time + timedelta(hours=h)` con `except (OverflowError, ValueError) → None`; vista: "ventana no representable" (sin recorte) | 6 h normal; 10**18 (timedelta no construible); 10**8 y 70M h (datetime fuera de rango); 69M h aún representable; render de header/panel/tech sin excepción |
| MINOR 2 — `_env_float` acepta `inf` | `math.isfinite(value) and value > 0`, si no default | `nan`, `inf`, `+inf`, `-inf`, `Infinity`, `0`, `0.0`, negativos, texto, vacío → default; `0.5`, `7`, `12.25`, `1e2` aceptados |

Corrida discriminante (`discriminating_run_fb3dd05.txt`): los tests de
`4745b07` contra el producto de `fb3dd05` (con shim de dos constantes para
que importen) → **96 failed, 189 passed**. Con `580bd5b`: **298 passed**.

| Archivo | Contenido |
|---|---|
| `pytest_sapi61_delta.xml`, `pytest_sapi61_delta_console.txt` | 5 suites SAPI-61 tras el delta: 298 passed |
| `discriminating_run_fb3dd05.txt` | Prueba de que los tests nuevos fallan en fb3dd05 |
| `regression_summary_delta.txt` | Regresión completa: 1987 passed, 137 skipped, cobertura 85,12 % |
| `lint_delta.txt` | black/flake8 de los 6 archivos del delta |
| `freeze_check_4745b07.txt/.json` | FREEZE CHECK PASS |

Los nombres de parámetros en la consola (`/home/internal/service/key`,
`postgresql://user:password@db/internal`, …) son fixtures sintéticas de los
tests, no rutas ni credenciales reales.

## Reproducir

```bash
pip install -r requirements-dev.txt
python -m pytest tests/test_backend_client.py tests/test_ranking_backend_view.py \
  tests/test_sapi61_http_stub.py tests/test_architecture.py tests/test_app_integration.py \
  -p no:cacheprovider --no-cov -q
python -m pytest -q                      # regresión completa con gate de cobertura
python -B scripts/freeze_check.py        # F1–F9
SAPI_BACKEND_BASE_URL=http://localhost:8080 streamlit run app/app.py   # con Spring Boot levantado
```

La HU sigue abierta: faltan la Etapa B (contrato aditivo, Compose, backend
real), la revisión independiente (Codex), el merge y Jira (no integrado en
este entorno: JIRA_NOT_AVAILABLE). El score es un ranking relativo entre las
50 celdas, no una probabilidad calibrada.

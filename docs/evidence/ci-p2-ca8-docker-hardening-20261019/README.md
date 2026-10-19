# CI-P2 — Auditoría, Diagnóstico de Causa Raíz y Endurecimiento de Integración Docker CA8

**Fecha:** 2026-10-19
**Directiva:** OCC-003B / CI-P2-R3
**Rol:** Senior Integration Engineer — Reliability & QA
**Rama:** `test/ci-p2-current-only-diagnostics-r2-20261019`
**Base:** `origin/main` (`2ba8cebe895b3791241546e7303a8f771a93683b`)
**Worktree:** `C:\SAPI-CI-P2-R2-20261019`
**PR:** #35 (Draft)

---

## 1. Contexto e Incidente Verificable

Durante la ejecución de GitHub Actions en el Quality Gate Python para la PR #32:
- **Run URL:** https://github.com/DanielCortezF002/S.A.P.I-Sistema-de-Prediccion-de-Incendios/actions/runs/39184234562
- **Job ID:** `117843154524` (`python`)
- **Commit evaluado:** `f53cdde62f6d1f1e927809a036c288ad447a82f5` (merge de PR #32 sobre `origin/main`)
- **Runner:** `Linux-6.17.0-1022-azure-x86_64-with-glibc2.39` (Ubuntu runner)
- **Fallo reportado:**
  `tests/test_f1_ca8_operational_overlay_dynamic.py::test_f1_operational_overlay_real_stack_enforces_current_only_gate`
  `AssertionError: assert 503 == 200` en línea 222 (paso 6: replay idempotente).

En contraste:
- Una ejecución paralela previa sobre el push (`run/39184229530`) aprobó el job `python`.
- Una ejecución posterior (`run/39186658836` y `run/39186662212`) con instrumentación diagnóstica básica también aprobó el job `python`.
- La PR #33 (`run/39195782195` y `run/39195804721`), que no modificó el test, también pasó `python`.

Este patrón intermitente requirió una investigación forense profunda para determinar si correspondía a un defecto de infraestructura, a una condición de carrera o a una discrepancia protocolar entre el stub de prueba y el cliente HTTP de Spring Boot.

---

## 2. Investigación de Causa Raíz y Estado de la Hipótesis HTTP

### 2.1 Análisis del flujo de ejecución del test original

El test ejecuta secuencialmente:
1. **Paso 1:** Despliegue de Docker Compose (`db-v2`, `ml-api`, `backend`) con overlay operacional (`docker-compose.operational.yml`), esperando que el backend alcance estado `healthy`.
2. **Paso 2:** Verificación de variables efectivas en el contenedor (`SAPI_PERSISTENCE_ALLOWED_FIRMS_ORIGINS=current`).
3. **Paso 3:** Arranque de `probe_container` apuntando a `SAPI_ML_BASE_URL=http://host.docker.internal:{stub_port}`.
4. **Paso 4:** Verificación de rechazo de procedencias no autorizadas (`baseline` y `reproducibility`): ambas devuelven HTTP 500 con `error_type: "internal_error"` y 0 escrituras en PostGIS.
5. **Paso 5:** Solicitud con `firms_origin=current`. El backend consulta el stub, recibe 200, valida el payload, persiste 1 registro en `ejecuciones` y 50 en `predicciones_celda`, y responde HTTP 200.
6. **Paso 6:** **Replay idempotente:** Se realiza una segunda solicitud idéntica a `/api/v1/ranking`.

### 2.2 Localización exacta del fallo

En el log de `run/39184234562`:
```text
tests/test_f1_ca8_operational_overlay_dynamic.py:159:
stored_origin = _psql(db_container, "SELECT firms_origin FROM ejecuciones ORDER BY id DESC LIMIT 1;")
assert stored_origin == "current"  <-- PASÓ (Paso 5 exitoso)

# 6) Replay idempotente: misma identidad, misma respuesta, sin filas nuevas.
status2, body2 = _http(f"http://127.0.0.1:{probe_port}/api/v1/ranking")
results["replay_current"] = {"status": status2}
assert status2 == 200
E assert 503 == 200  <-- FALLÓ en el replay
```

El paso 5 (`accept_current`) fue completamente exitoso. El fallo ocurrió en el paso 6 (`replay_current`).

### 2.3 Mecánica del HTTP 503 en el backend Spring Boot

Revisando `RankingService.java` y `MlServiceClient.java`:
1. El backend usa `RestClient` con el cliente JDK `HttpClient` configurado en `HttpClient.Version.HTTP_1_1`.
2. JDK `HttpClient` implementa agrupación de conexiones (connection pool) por defecto para conexiones HTTP/1.1 persistentes (Keep-Alive).
3. En el test original, el stub Python se definía como `http.server.BaseHTTPRequestHandler` con `protocol_version = "HTTP/1.0"`.
4. Al procesar una solicitud bajo `HTTP/1.0`, `parse_request()` establece internamente `self.close_connection = True`.
5. En `send_response()`, el stub enviaba la cabecera `HTTP/1.0 200 OK` pero **NO** enviaba la cabecera `Connection: close`.
6. Al concluir `do_POST()`, el socket TCP era cerrado unilateralmente por el servidor en el host.
7. En el lado del cliente (Spring Boot dentro del contenedor):
   - Al no recibir `Connection: close`, JDK `HttpClient` retiene la conexión en su pool para reutilizarla.
   - Entre el paso 5 y el paso 6 transcurren entre 200 ms y 400 ms mientras el test ejecuta consultas `psql` para validar los conteos SQL.
   - En el paso 6, el backend despacha el segundo `POST /predict`. Si el backend intenta escribir en el socket antes de que el kernel del contenedor procese el paquete `FIN` o si el socket entra en estado de cierre asíncrono, el socket genera `TCP RST` / `SocketException: Connection reset by peer` o `IOException: Broken pipe`.
   - Dado que el método HTTP es `POST` (no idempotente según RFC 7230 / RFC 9110), el cliente HTTP del JDK **no realiza reintento automático**.
   - `MlServiceClient` captura `ResourceAccessException` y lanza `MlCallException(Kind.UNAVAILABLE)`.
   - `RankingService` traduce `MlCallException` no-timeout en:
     `RankingOutcome.error(RankingError.UPSTREAM_UNAVAILABLE)` -> **HTTP 503**.

### 2.4 Clasificación técnica y estado de la hipótesis (Directiva CI-P2-R3 §4)

- **Ausencia de logs directos de transporte:** En la corrida remota original `39184234562`, el arnés de prueba original no capturaba trazas de transporte (`Connection reset`, `Broken pipe`), no volcaba el cuerpo de error en `results["replay_current"]` ni extraía los logs de Tomcat del contenedor probe.
- **Estado epistemológico:** Conforme a los principios de Integridad Científica y Evidence-First de SAPI, esta explicación se califica formalmente como:
  **Hipótesis explicativa altamente probable y plenamente compatible con la evidencia técnica**, y **no** como una causa raíz empíricamente probada por trazas directas de red.
- **No es defecto de la política `current-only`:** Se constató fehacientemente que la política `current-only` funcionó según el contrato en el Paso 5 (+1 ejecución y +50 predicciones persistidas con `firms_origin=current`).
- **Validez de la medida preventiva:** La inclusión de `Connection: close` y `self.close_connection = True` sigue siendo una práctica rigurosa y necesaria bajo RFC 7230 §6.6 que elimina la posibilidad de reutilización de sockets cerrados en el stub de prueba.

---

## 3. Endurecimiento e Instrumentación Aplicada

En `tests/test_f1_ca8_operational_overlay_dynamic.py`:

1. **Cierre de conexión protocolar explícito (RFC 7230 §6.6):**
   ```python
   self.send_header("Connection", "close")
   self.end_headers()
   self.wfile.write(body)
   self.close_connection = True
   ```
   Indica explícitamente al cliente JDK que no reutilice la conexión en el pool, eliminando la condición de carrera del socket reseteado.

2. **Conteo atómico de solicitudes recibidas por el stub:**
   ```python
   requests: int = 0
   requests_lock = threading.Lock()
   ```
   En cada paso (`reject_baseline`, `reject_reproducibility`, `accept_current`, `replay_current`):
   ```python
   with _StubHandler.requests_lock:
       stub_posts = _StubHandler.requests - requests_before
   assert stub_posts > 0, ...
   ```
   Garantiza que el backend realmente alcanzó el stub y no falló prematuramente antes de consultar el servicio ML.

3. **Extracción segura de `error_type` para diagnóstico:**
   Función `_error_type(body: bytes) -> str` que parsea únicamente la clave contractual `error_type`, sin exponer cabeceras, rutas de filesystem, tokens o variables de entorno.

4. **Preservación de resultados parciales:**
   En bloque `finally`, `results.json` se escribe antes del desmontaje de los contenedores para garantizar trazabilidad forense ante cualquier fallo.

5. **Limpieza estricta y segura:**
   El desmontaje elimina únicamente el contenedor de sondeo (`docker rm -f probe_container`), apaga el stub HTTP local (`stub.shutdown()`) y ejecuta `compose("down")` sin `-v`, protegiendo los volúmenes del usuario y sin tocar servicios preexistentes (como n8n u otros contenedores SAPI).

---

## 4. Matriz de Verificaciones Funcionales

Se ejecutaron tres corridas diagnósticas independientes consecutivas con Docker local en el entorno aislado `C:\SAPI-CI-P2-R2-20261019`, más la verificación final post-modificación:

| Métrica / Escenario | Ejecución 1 (`run-263dc607`) | Ejecución 2 (`run-f2573bfe`) | Ejecución 3 (`run-bd0f1b1b`) | Verificación Final (`run-01bb0ef0`) |
|---|---|---|---|---|
| **Duración** | 27.57s | 28.63s | 27.49s | 28.65s |
| **Rechazo Baseline** | HTTP 500 (`internal_error`) | HTTP 500 (`internal_error`) | HTTP 500 (`internal_error`) | HTTP 500 (`internal_error`) |
| **Stub posts (Baseline)** | 1 | 1 | 1 | 1 |
| **Escrituras SQL (Baseline)** | 0 ejecuciones, 0 celdas | 0 ejecuciones, 0 celdas | 0 ejecuciones, 0 celdas | 0 ejecuciones, 0 celdas |
| **Rechazo Reproducibility** | HTTP 500 (`internal_error`) | HTTP 500 (`internal_error`) | HTTP 500 (`internal_error`) | HTTP 500 (`internal_error`) |
| **Stub posts (Reprod.)** | 1 | 1 | 1 | 1 |
| **Escrituras SQL (Reprod.)**| 0 ejecuciones, 0 celdas | 0 ejecuciones, 0 celdas | 0 ejecuciones, 0 celdas | 0 ejecuciones, 0 celdas |
| **Aceptación CURRENT** | HTTP 200 (`error_type: null`) | HTTP 200 (`error_type: null`) | HTTP 200 (`error_type: null`) | HTTP 200 (`error_type: null`) |
| **Stub posts (CURRENT)** | 1 | 1 | 1 | 1 |
| **Persistencia SQL** | +1 ejecución, +50 celdas | +1 ejecución, +50 celdas | +1 ejecución, +50 celdas | +1 ejecución, +50 celdas |
| **`firms_origin` en DB** | `"current"` | `"current"` | `"current"` | `"current"` |
| **Replay Idempotente** | HTTP 200 (`error_type: null`) | HTTP 200 (`error_type: null`) | HTTP 200 (`error_type: null`) | HTTP 200 (`error_type: null`) |
| **Stub posts (Replay)** | 1 | 1 | 1 | 1 |
| **Idempotencia SQL** | 0 filas adicionales | 0 filas adicionales | 0 filas adicionales | 0 filas adicionales |
| **Limpieza Docker** | 0 contenedores residuales | 0 contenedores residuales | 0 contenedores residuales | 0 contenedores residuales |

---

## 5. Verificaciones de Calidad de Código e Integridad Local

- **Sintaxis Python:** `python -m py_compile tests/test_f1_ca8_operational_overlay_dynamic.py` -> **PASS (0)**
- **Flake8 Compliance:** `python -m flake8 --max-line-length=100 --extend-ignore=E203,W503 tests/test_f1_ca8_operational_overlay_dynamic.py` -> **PASS (0 infracciones)**
- **Black Check:** `python -m black --check tests/test_f1_ca8_operational_overlay_dynamic.py` -> **PASS (0 diferencias)**
- **Git Diff Hygiene:** `git diff --check` -> **PASS (limpio, sin trailing whitespace)**
- **Pruebas unitarias de integración relacionadas:** 248 pruebas aprobadas (`test_sapi61_http_stub.py`, `test_ml_api.py`, `test_backend_client.py`).
- **Integridad de Modelo D:** SHA-256 de `prototype_model_d.pkl` es `ac017bef1f42a30ac74ba3e3787368c4418798b2d562adcfba01c923cff2173f` (**intacto**).
- **Rutas congeladas F4:** No se modificó ningún archivo bajo `src/inference`, `src/procesamiento`, `models`, `db/migration` ni scripts congelados.
- **Aislamiento:** La rama de trabajo y worktree operaron de forma 100% aislada sin interferir con otros agentes.

---

## 6. Auditoría Forense del Fallo en CI Remoto (Run 39250758520)

### 6.1 Identidad del commit ejecutado en GitHub Actions
- **Rama HEAD SHA:** `7277ec80cdef87ba2e95811e153b110f90961fb9`
- **Merge temporal evaluado por GitHub Actions:** `69f93893cfc0508d6617a03c4edebaf612968b96` (`refs/pull/35/merge`)
- **Artefacto inspeccionado:** `gate-python-69f93893cfc0508d6617a03c4edebaf612968b96`

### 6.2 Desglose de comandos del Job `python`
De acuerdo con `gate_summary.json` y `python.txt`:
1. **Black Check (`exit=1`):**
   - Fallo en 2 archivos: `app/components/ranking_backend_view.py` y `tests/test_ranking_backend_view.py`.
   - Cero diferencias en archivos del PR #35.
2. **Flake8 Compliance (`exit=1`):**
   - 16 infracciones (11 `E501 line too long` y 5 `W293 blank line contains whitespace`), todas localizadas en `app/components/ranking_backend_view.py`.
   - Cero infracciones en archivos del PR #35.
3. **Pytest (`exit=2`):**
   - Fallo durante la fase de importación/colección:
     ```text
     ERROR collecting tests/test_measure_browser_e2e_d21.py
     ImportError while importing test module 'tests/test_measure_browser_e2e_d21.py'
       from scripts.measure_browser_e2e_d21 import create_driver
       from selenium import webdriver
     ModuleNotFoundError: No module named 'selenium'
     ```
   - Interrupción inmediata: `1 error during collection in 6.02s`.
   - Tests ejecutados: **0** (ningún test corrió).
   - Cobertura obtenida: **0.00 %** (no evaluada por aborto en colección).
   - **¿Llegó a ejecutarse CA8?: NO.** La prueba CA8 no fue ejecutada en la corrida remota debido a la detención previa en la colección de Pytest.

### 6.3 Conclusión sobre la causa del fallo remoto
El fallo del job `python` en el CI remoto es **100 % independiente del test CA8 y de las modificaciones de CI-P2**.
Se debe exclusivamente a defectos preexistentes en `origin/main` (`2ba8ceb`), correspondientes a las correcciones que actualmente se encuentran aisladas en la PR #33 (`fix/sapi-ci-python-r3-20261019`).
Dado que la directiva prohíbe taxativamente modificar `ranking_backend_view.py`, `scripts/measure_browser_e2e_d21.py`, `requirements-dev.txt` o integrar cambios de otros agentes, el fallo del CI remoto constituye una **dependencia no satisfecha de la rama base `origin/main`**.

---

## 7. Auditoría de Limpieza de Recursos (Directiva CI-P2-R3 §5)

### 7.1 Reconstrucción de la carpeta `artifacts/hito2/f1`
- **En `origin/main` (`2ba8ceb`):** El directorio `artifacts/hito2/f1` **no existe** y no contiene ningún archivo rastreado en el árbol git.
- **Origen en el worktree:** El directorio fue creado en tiempo de ejecución por `tests/test_f1_ca8_operational_overlay_dynamic.py` (línea 30: `EVIDENCE_DIR = REPO_ROOT / "artifacts/hito2/f1/ca8-dynamic-overlay"`).
- **Contenido previo al borrado:** Contenía exclusivamente subcarpetas de corridas generadas durante las pruebas locales de esta sesión (`run-582d21a3`, `run-e0e945e3`, `run-263dc607`, `run-f2573bfe`, `run-bd0f1b1b`).
- **Impacto evaluado:** Cero afectación a archivos rastreados, cero pérdida de evidencias de otros frentes y cero alteración de volúmenes persistentes de Docker.
- **Compromiso de gobernanza:** Conforme a la Directiva CI-P2-R3 §5, **se prohíben nuevas limpiezas recursivas globales** sobre `artifacts/hito2/f1`. Toda limpieza queda restringida a recursos unívocamente identificados como creados por esta directiva.

---

## 8. Dictamen Técnico y Recomendación de Integración

- **Estado de CA8:** **COMPLETO Y VERIFICADO FUNCIONALMENTE.**
- **Integridad:** Modelo D, archivos F4 y gobernanza del repositorio preservados sin alteraciones.
- **Dictamen:** **GO CONDICIONADO**.
  - Aprobado técnicamente para su integración.
  - Bloqueado en CI remoto por la ausencia de la corrección del gate Python de la PR #33 en `origin/main`.
  - Se recomienda que el SAPI Command Center apruebe y fusione primero la PR #33 en `origin/main`, tras lo cual la PR #35 podrá rebasar limpiamente sobre `origin/main` y obtener un Quality Gate Python en verde en GitHub Actions.

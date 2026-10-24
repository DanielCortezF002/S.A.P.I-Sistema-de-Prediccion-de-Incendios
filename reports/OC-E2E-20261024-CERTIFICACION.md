# Certificación E2E física del Sprint 2 — S.A.P.I. v2

**Fecha:** 2026-10-24 (UTC)  
**Rama:** `test/oc-fullstack-e2e-20261024`  
**Worktree:** `C:\SAPI-OC-E2E-20261024`  
**HEAD evaluado:** `2a71c7e1160ab87ef7c0ec5e2dfaf3b06c1b4876`  
**Tree:** `655ad33db79b5ba98e06df770595ed916d660036`  
**Candidato protegido:** `51ec3c06b67959d3daad6349c962a1be643906b4` — **no modificado**.  
**Evidencia:** `artifacts/oc-e2e-20261024/` (índice y SHA-256 en `SHA256SUMS.txt`).

> **Veredicto de esta corrida:** el camino físico completo
> `Edge → Streamlit → Spring Boot → FastAPI/Modelo D → PostgreSQL/PostGIS →
> ranking de 50 celdas` quedó **VALIDADO E2E** en modo reproducible.
> **No** se declara GO, **no** se cierra SAPI-66 ni SAPI-43, **no** se promueve
> Gate B y **no** se recalcula nota académica. CA5 literal y la corrida
> operacional `firms_origin=current` siguen **BLOQUEADOS**.

---

## 1. Resumen ejecutivo

| Clasificación | Alcance | Resultado |
|---|---|---|
| **IMPLEMENTADO** | Stack v2 aislado de cuatro servicios, overlay de red, suites E2E nuevas y captura de evidencia | Completo en esta rama; sin cambios en aplicación, contratos, modelo ni reglas de Gate B |
| **PROBADO** | Maven backend, suite vertical preexistente, suite full-stack nueva, matriz negativa | 163 tests Java (0 fallos, 5 skipped); 5 tests vertical slice; 8 tests full-stack; 5 tests negativos |
| **VALIDADO E2E** | Navegador real, contrato HTTP, PostGIS 1:1, idempotencia, OpenAPI, CA4, fallos por salto, persistencia tras `down`/`up` | **Sí**, con las limitaciones de §9 |
| **BLOQUEADO** | CA5 literal sin profile/overrides; corrida operacional SAPI-43 `current`; CA8 real `current`; caso ML degradado | **No ejecutado**; requiere decisión/autorización o cambio de alcance |

**Conteo de pruebas de esta corrida:**

| Suite | Resultado | Tiempo | Log autoritativo |
|---|---:|---:|---|
| `tests/e2e/test_vertical_slice.py` (preexistente, sin cambios) | **5 passed** | 17,23 s | `logs/08-vertical-slice-tests.log` |
| `tests/e2e/test_full_stack_timings.py` + `test_full_stack_browser.py` | **8 passed** | 48,76 s | `logs/35-final-suite.log` |
| `tests/e2e/test_full_stack_negative.py` | **5 passed** | 101,29 s | `logs/36-final-negative.log` |
| Backend Maven (`mvnw.cmd -B test`) | **163 tests, 0 failures, 0 errors, 5 skipped** | BUILD SUCCESS | `logs/09-backend-surefire.log` |

Los tests nuevos se omiten por defecto. La suite full-stack exige
`SAPI_E2E_FULL_STACK=1`; la matriz negativa exige además
`SAPI_E2E_FAULT_INJECTION=1`. No se alteraron los cinco tests de
`test_vertical_slice.py`.

---

## 2. Alcance y no alcance

### 2.1 Lo que sí se ejecutó

- Levantamiento real con Docker Compose del stack v2 aislado.
- Navegador Microsoft Edge real (no HTML simulado) contra Streamlit.
- Recorrido HTTP real por los cuatro saltos, incluido el log de FastAPI.
- Verificación PostGIS de migraciones, geometrías, ejecución y 50 predicciones.
- Comparación 1:1 entre la respuesta HTTP y las filas persistidas.
- Repetición idempotente y ciclo completo `down`/`up` sin `-v`.
- Inyección real de fallos: payload inválido, ML caído, base caída, backend caído.
- Medición CA4 de UI fría, actualización con invalidación de caché y rerun cacheado.
- Validación del payload contra los contratos OpenAPI congelados.

### 2.2 Lo que no se ejecutó y no se puede afirmar

- `docker compose up` **literal** sin `--profile presentation` ni overlay.
- SAPI-71 Attempt 2 ni una corrida operacional nueva de SAPI-43.
- Una corrida con `firms_origin=current`.
- `RankingHttpToPostgresIT` real con rechazo de `baseline`/`reproducibility`.
- El caso de salud ML degradada por artefacto faltante (se preservó la
  inmutabilidad del Modelo D).
- Push, PR, merge, comentarios Jira, cierre de issues o cambio de Gate B.

**Regla científica respetada:** el score se mantiene como
`score_semantics=relative_rank`, `scientific_model_validation=false`; no se
presenta como probabilidad calibrada ni como predicción validada de incendios.

---

## 3. Entorno y aislamiento

| Elemento | Valor observado |
|---|---|
| Sistema | Windows NT 10.0.26200.0 |
| Docker client/server | 29.8.1 / 29.8.1 |
| Docker Compose | v5.5.1 |
| Python / pytest | 3.14.7 / 9.1.1 |
| Playwright | 1.64.1 |
| Navegador | Microsoft Edge 156.0.4314.42 (`channel="msedge"`, headless) |
| Proyecto Compose | `sapi-oc-e2e-20261024` |
| Red | `sapi-oc-e2e-20261024_sapi-v2-net`, subred explícita `10.99.99.0/24` |
| Puertos host | DB `55432`, ML `58000`, backend `58080`, web `58501` |
| Volúmenes | `sapi-oc-e2e-20261024_sapi_v2_pgdata`, `..._sapi_v2_secrets` |

Se usó el overlay `tests/e2e/docker-compose.e2e-oc.yml` porque el daemon tenía
agotados los pools de direcciones por defecto (≈30 redes preexistentes de otros
entornos). El overlay **solo** fija la subred de la red de este proyecto; no se
tocó ninguna red, volumen o contenedor ajeno. Los dos contenedores n8n que
estaban activos en 5678/5680 se dejaron intactos.

### 3.1 Comando exacto de levantamiento

```powershell
$env:SAPI_DB_PORT='55432'
$env:SAPI_ML_PORT='58000'
$env:SAPI_BACKEND_PORT='58080'
$env:SAPI_WEB_PORT='58501'
docker compose -f docker-compose.yml `
  -f tests/e2e/docker-compose.e2e-oc.yml `
  -p sapi-oc-e2e-20261024 --profile presentation up -d
```

La configuración resuelta se conserva en `logs/38-compose-config-final.log`:
cuatro servicios, `web-v2` con profile `presentation`, la subred
`10.99.99.0/24` y los puertos aislados.

**Hallazgo de reproducibilidad:** los puertos host se inyectan por variables de
entorno. Un shell nuevo que no las define vuelve silenciosamente a
`5432/8000/8080/8501`. Durante el ciclo de reinicio se observó ese fallback y se
corrigió volviendo a levantar con las variables explícitas. El comando de §3.1
es el que debe reproducirse; no basta `docker compose up`.

---

## 4. Resultado por criterio de SAPI-66

| CA | Qué se verificó | Resultado | Evidencia principal |
|---|---|---|---|
| **CA1** | Test E2E versionado y reproducible sobre stack real, con navegador | **PASS E2E** | `logs/35-final-suite.log`, `e2e/*.json`, `timings/ca4-*` |
| **CA2** | Errores y contratos por salto, con códigos observados y cero escrituras | **PASS E2E** | `logs/36-final-negative.log`, `negative/*.json` |
| **CA3** | Filas PostGIS == respuesta HTTP, comparación 1:1 en la misma corrida | **PASS E2E** | `e2e/postgis-verification.json`, `postgis-snapshot.txt` |
| **CA4** | Tiempos de UI fría, actualización y cached; hash de captura y discriminador | **PASS E2E con salvedad** | `timings/ca4-timings.csv`, `timings/ca4-timings.json` |
| **CA5** | `docker compose up` literal, sin `.env` ni overrides | **BLOQUEADO** | `docs/architecture-stack-freeze-sprint2.md`; `web-v2` profile `presentation` |

**Lectura correcta de SAPI-66:** el núcleo E2E (CA1–CA4) quedó acreditado con
evidencia ejecutada. **SAPI-66 no se cierra** porque CA5 sigue sin cumplimiento
literal: `web-v2` está detrás de `profiles: ["presentation"]` y esta corrida usó
`--profile presentation` más un overlay de red. Cambiar la ruta por defecto es
una decisión de arquitectura que no fue autorizada en este trabajo.

### 4.1 Mapa SAPI-43 (para evitar cierres indebidos)

| CA SAPI-43 | Estado en esta corrida | Motivo |
|---|---|---|
| CA1 | **BLOQUEADO** | No se ejecutó SAPI-71 Attempt 2; no hay stores `current` nuevos |
| CA2–CA7 | **NO ACREDITADO para SAPI-43** | La mecánica se ejercitó con `firms_origin=reproducibility`; no es una corrida operacional |
| CA8 | **BLOQUEADO** | No se ejecutó el IT real de rechazo con política `current` |

La evidencia demuestra que el pipeline persiste y responde, pero **no** que los
datos provengan de un refresh operacional autorizado. No debe usarse para
cerrar SAPI-43.

---

## 5. Contrato del ranking observado

Respuesta `GET /api/v1/ranking` (200) en `e2e/ranking-http.json`:

| Campo | Valor observado |
|---|---|
| `schema_version` | `sapi-ranking-v0` |
| `model_version` | `prototype_model_d_v1` |
| `forecast_time` | `2026-09-01T00:00:00Z` |
| `horizon_hours` | `6` |
| `score_semantics` | `relative_rank` |
| `scientific_model_validation` | `false` |
| `firms_origin` | `reproducibility` |
| `inputs_fingerprint` | `09482d6b3a8b4ab210c32cdddaec352c8eca8be25bbf76592799c1702096c5a3` |
| Celdas | 50 (`VP-001` … `VP-050`) |
| `rank` | 1..50, sin huecos |
| Distribución | 7 celdas con `0.13129336874795144` (display #1), 41 con `0.10508928467283135` (display #8), 2 con `0.10210320770655851` (display #49) |
| Tamaños de empate | 7, 41 y 2 |

La UI muestra los empates como `×7`, `×41`, `×2` y declara explícitamente que
el score es un ranking relativo, no una probabilidad. La validación formal
contra `contracts/openapi/ml-service.v0.yaml#/components/schemas/RankingResult`
y contra la respuesta 200 de `contracts/openapi/backend.v0.yaml` fue **válida**
(`e2e/openapi-conformance.json`, 50 celdas).

---

## 6. PostGIS, persistencia e idempotencia

### 6.1 Migraciones y geometría

| Verificación | Resultado |
|---|---|
| Flyway V001–V004 | `success` en las cuatro |
| PostgreSQL / PostGIS | 15.8 / 3.4 |
| `celdas_geom` | 50 filas |
| Geometrías válidas SRID 4326 | 50/50, tipo `POLYGON` |
| Extensión | `(-71.58,-33.14)` a `(-71.169,-32.965)` |
| `ejecuciones` | 1 |
| `predicciones_celda` | 50 |
| Duplicados `cell_id` / `rank` | 0 / 0 |
| Celdas sin predicción | 0 |

La comparación `cell_id, score, rank, display_rank, tie_group_size` entre la
respuesta HTTP y las 50 filas persistidas fue **1:1 exacta**
(`e2e/postgis-verification.json`, `postgis-snapshot.txt`).

### 6.2 Idempotencia

Una segunda llamada al mismo endpoint devolvió 200, las mismas 50 celdas y el
mismo fingerprint; `ejecuciones` se mantuvo en 1 y `predicciones_celda` en 50
(`e2e/idempotency.json`).

`age_hours` cambió de `1294.2902932577776` a `1294.2910862836113` entre las dos
respuestas. **No es una falla de idempotencia**: ese campo se calcula contra el
reloj de evaluación y no forma parte de la clave natural persistida. La clave
natural (`forecast_time`, `model_version`, `inputs_fingerprint`,
`score_semantics`) permaneció idéntica.

### 6.3 Persistencia tras `down`/`up`

Se ejecutó `docker compose ... down` **sin `-v`** y luego `up -d` con los puertos
aislados. Los volúmenes se conservaron y, tras el arranque:

- los cuatro servicios respondieron 200 (los tres con healthcheck, `healthy`);
- `ejecuciones=1` y `predicciones_celda=50`;
- `created_at` siguió siendo `2026-10-24T21:30:04.003667+00:00`;
- el fingerprint no cambió;
- Flyway reportó el esquema al día (sin nueva migración).

Evidencia: `logs/18-compose-down-isolated.log`,
`logs/19-compose-up-isolated.log`, `logs/20-restart-health-isolated.log`,
`logs/21-restart-persistence.log`, `restart-persistence.json`.

---

## 7. Navegador real y representación territorial

El test `test_full_stack_browser_consumes_backend` abrió Edge real contra
`http://127.0.0.1:58501` y verificó:

- cabecera `S.A.P.I.`, badge `BACKEND REST`, `PROTOTIPO EXPLORATORIO`;
- KPI `50 CELDAS EVALUADAS`;
- `GRUPO PRIORITARIO` y `#1` con 7 celdas empatadas;
- ausencia de la palabra `Probabilidad` en el cuerpo;
- fingerprint del backend visible en “Información técnica y fuentes”;
- `relative_rank` y `scientific_model_validation` visibles;
- **exactamente 50 rectángulos Leaflet** en el iframe de Folium;
- 0 errores de consola.

`e2e/browser-verification.json` registra `load_ms=7246.58` (incluye una espera
de 5 s para que monte el mapa; no debe citarse como tiempo puro de carga),
`leaflet_rectangles=50`, `console_errors=[]` y el SHA-256 de la captura.
La captura `e2e/streamlit-ranking.png` muestra la tabla, el fingerprint y los
50 grupos; el mapa se verificó por conteo de rectángulos en el iframe.

---

## 8. CA4 — tiempos de UI fría, actualización y cached

La evidencia autoritativa es `timings/ca4-timings.csv` y
`timings/ca4-timings.json`. El discriminador **no** es el PNG: el header solo
muestra `HH:MM`. El discriminador es el delta de líneas
`ml_predict request_id=` en el log del backend antes/después de cada acción.

| Acción | Tiempo medido | Hasta cabecera | Hasta backend | `ml_predict` delta | Latencia ML | `fetched_at` |
|---|---:|---:|---:|---:|---:|---|
| `cold_ui` (navegador y caché Streamlit fríos) | **6.065,26 ms** hasta mapa | 5.500,46 ms | — | **1** | 1.987 ms | 22:17 UTC |
| `update` (botón “Actualizar ranking”, invalida caché) | **2.649,82 ms** | — | 2.552,69 ms | **1** | 2.267 ms | 22:17 UTC |
| `cached` (cambio de orden, rerun sin backend) | **893,25 ms** | — | — | **0** | — | 22:17 UTC |

- `cold_ui` se midió tras reiniciar únicamente `web-v2`, con la caché de
  Streamlit vacía; por eso produjo una predicción ML real.
- `update` ejecutó `st.cache_data.clear()` y recorrió
  Streamlit → Spring → FastAPI → PostGIS.
- `cached` cambió el orden de la tabla a “Identificador de celda”; el rerun
  tardó 0,89 s y **no** produjo ninguna llamada ML, lo que demuestra el uso de
  la caché de 5 minutos.

Capturas y SHA-256:

| Acción | Archivo | SHA-256 |
|---|---|---|
| cold | `timings/ca4-cold-ui.png` | `2b8bf4291ea99b1f25283903b01a52e4c695a06f2e0ebccb1d90ce846a7c4e6d` |
| update | `timings/ca4-update.png` | `5f0ea03ce1e8c3efbf49b08b2e3e3d6ef8f2f4360558b8b1aafd70844dbb3f60` |
| cached | `timings/ca4-cached.png` | `32076760ebacbaa856587ceca22043be3049e1775f90d27885c50fb3412fedf2` |

**Salvedad CA4:** la captura `cached` muestra la tabla ordenada por
identificador y la selección del filtro; las capturas `cold`/`update` muestran
cabecera y KPIs. Como el header solo tiene resolución de minuto, dos capturas
del mismo minuto podrían ser idénticas. Por eso el CSV y el log ML son la
prueba principal; el PNG es soporte visual.

---

## 9. Matriz negativa y comportamiento fail-closed

| Caso inducido | Resultado observado | Escrituras | Recuperación |
|---|---|---|---|
| `forecast_time` inválido | `422 invalid_request` | 0 (1/50 antes y después) | inmediata |
| Payload inválido a FastAPI (3 variantes) | `422 invalid_request` en las tres | n/a | inmediata |
| `ml-api` detenido | `503 upstream_unavailable` en 4.015,48 ms | 0 | 200 en 4.531,23 ms |
| `db-v2` detenida | `500 internal_error` en 32.734,50 ms | 0 | 200 en 5.058,09 ms |
| `backend` detenido + UI recargada | error controlado “No se pudo conectar con el backend”, sin traceback ni host interno | n/a | 50 celdas visibles al volver |

Evidencia: `logs/36-final-negative.log` y `negative/*.json` /
`negative/*.png`.

**Hallazgo real:** al reiniciar `ml-api`, el backend puede seguir devolviendo
`503 upstream_unavailable` durante unos segundos por conexión/DNS en caché,
antes de recuperar. El test reintenta hasta 120 s y documenta el tiempo real; no
se ocultó el comportamiento. La caída de base tarda ≈33 s porque Hikari agota su
timeout de conexión; la respuesta es un 500 controlado y **no** deja escrituras
parciales.

---

## 10. Hallazgos operativos y correcciones de alcance

1. **Puertos por variables de entorno.** El fallback silencioso a
   `5432/8000/8080/8501` en un shell nuevo se detectó durante el reinicio. La
   corrida final usa los puertos aislados y el comando de §3.1 los declara.
2. **Pools de direcciones Docker agotados.** Se resolvió con el overlay de
   subred explícita, sin tocar redes ajenas.
3. **Dropdown de Streamlit.** El desplegable de grupo podía quedar fuera del
   viewport tras abrir el expander; se corrigió el test nuevo con
   `scroll_into_view_if_needed()` y espera explícita. Fue un ajuste del arnés,
   no un cambio de producto.
4. **Estabilización de capturas.** Streamlit necesita varios segundos para
   asentar CSS/fuentes después de un rerun; las capturas CA4 esperan 5 s
   **después** de registrar el tiempo, para no contaminar la medición.
5. **Encoding.** Algunos mensajes con acentos se ven como `�` en consolas
   Windows; los bytes UTF-8 de los JSON y respuestas HTTP son correctos. No se
   alteró el contenido.

---

## 11. Impacto legítimo en las rúbricas

No se recalcula puntaje ni se declara una subida de nota. Lo que esta corrida
aporta, por criterio:

| Criterio | Impacto | Lectura |
|---|---|---|
| **César 3 — Arquitectura (IL2.3)** | Confirma físicamente los cuatro servicios, la ruta v2 y el aislamiento de fallos | Ya estaba en “Excelente”; **no cambia el nivel**, pero la evidencia es más fuerte |
| **César 4 — Datos/plataformas (IL2.4)** | Confirma Flyway, PostGIS, 50 geometrías y persistencia 1:1 | Ya estaba en “Excelente”; **no cambia el nivel** |
| **César 5 — Gestión del Sprint 2, pruebas y riesgos** | Aporta una corrida E2E real, matriz negativa y paquete reproducible | **Mejora la base de evidencia**; el descriptor “Excelente” sigue limitado por el Sprint Backlog incompleto (SAPI-43/66 abiertas). No se declara subida |
| **Matías 6 — Validación y pruebas** | Agrega una validación ejecutada, no solo histórica | Ya estaba en “Excelente”; **refuerza la defensa**, sin cambiar el nivel |
| **Matías 7 — Integración y atributos de calidad** | Prueba real de fallos por salto, recuperación y persistencia tras reinicio | Ya estaba en “Excelente”; **refuerza la defensa**, sin cambiar el nivel |
| **Matías 1 — Incremento funcional** | La tubería queda certificada, pero SAPI-43/66 siguen abiertas | **No se declara incremento íntegro** |
| **Matías 5 — Implementación y calidad** | Los defectos históricos no se borran por repetir pruebas | **Sin cambio de nivel** |

En síntesis: la evidencia **mejora César 5, Matías 6 y Matías 7**; confirma
César 3/4 sin subirlos; no alcanza para Matías 1 mientras SAPI-43/66 no cierren.

---

## 12. Limitaciones y bloqueos

| Bloqueo | Estado | Qué haría falta |
|---|---|---|
| SAPI-66 CA5 literal | **BLOQUEADO** | Decisión sobre `web-v2` en la ruta por defecto, o reformulación aprobada del CA |
| SAPI-43 corrida operacional | **BLOQUEADO** | SAPI-71 Attempt 2 autorizado, credenciales y stores `current` |
| SAPI-43 CA8 | **BLOQUEADO** | `RankingHttpToPostgresIT` real con política `current` |
| ML degradado (artefacto faltante) | **NO EJECUTADO** | Prueba con una copia/artefacto alternativo, preservando Modelo D |
| CA4 resolución de header | **SALVEDAD** | El CSV/log ML discriminan; el PNG solo muestra `HH:MM` |
| Docker local/Windows | **LIMITACIÓN** | No sustituye CI remoto ni un despliegue operacional |

No se modificaron las reglas de Gate B. El veredicto sigue siendo **NO GO**.

---

## 13. Reproducción

### 13.1 Levantar

```powershell
$env:SAPI_DB_PORT='55432'
$env:SAPI_ML_PORT='58000'
$env:SAPI_BACKEND_PORT='58080'
$env:SAPI_WEB_PORT='58501'
docker compose -f docker-compose.yml `
  -f tests/e2e/docker-compose.e2e-oc.yml `
  -p sapi-oc-e2e-20261024 --profile presentation up -d
```

Esperar healthchecks:

```powershell
Invoke-WebRequest http://127.0.0.1:58000/health
Invoke-WebRequest http://127.0.0.1:58080/health
Invoke-WebRequest http://127.0.0.1:58501/_stcore/health
```

### 13.2 Ejecutar las suites

```powershell
# Suite vertical preexistente
python -m pytest tests/e2e/test_vertical_slice.py -v --no-cov

# Full-stack + CA4 (navegador real)
$env:SAPI_E2E_FULL_STACK='1'
python -m pytest tests/e2e/test_full_stack_timings.py `
  tests/e2e/test_full_stack_browser.py -v --no-cov

# Matriz negativa (detiene/levanta servicios de este proyecto)
$env:SAPI_E2E_FAULT_INJECTION='1'
python -m pytest tests/e2e/test_full_stack_negative.py -v --no-cov
```

`--no-cov` es necesario porque `pytest.ini` exige 80 % de cobertura global; una
corrida dirigida de otro modo termina con código 1 aunque los tests pasen.

### 13.3 Cerrar sin borrar volúmenes

```powershell
docker compose -f docker-compose.yml `
  -f tests/e2e/docker-compose.e2e-oc.yml `
  -p sapi-oc-e2e-20261024 --profile presentation down
```

Este `down` no usa `-v`: elimina contenedores y red del proyecto, pero conserva
`..._sapi_v2_pgdata` y `..._sapi_v2_secrets`. No ejecutar `down -v` sobre otros
proyectos.

---

## 14. Índice de evidencia

| Archivo | Contenido |
|---|---|
| `logs/35-final-suite.log` | 8 tests full-stack + CA4, salida final |
| `logs/36-final-negative.log` | 5 tests de fallos, salida final |
| `logs/08-vertical-slice-tests.log` | 5 tests vertical slice preexistentes |
| `logs/09-backend-surefire.log` | Maven: 163 tests, 0 fallos |
| `e2e/ranking-http.json` | Respuesta HTTP, hash y request id |
| `e2e/postgis-verification.json` | Flyway, ejecución, 50 filas, comparación 1:1 |
| `e2e/idempotency.json` | Segunda llamada, celdas iguales, 1 ejecución |
| `e2e/openapi-conformance.json` | Validación contra contratos congelados |
| `e2e/browser-verification.json` | Edge, 50 rectángulos, fingerprint, consola |
| `timings/ca4-timings.csv` / `.json` | Tiempos y deltas ML de cold/update/cached |
| `negative/*.json` | Códigos, tiempos y conteos de la matriz negativa |
| `postgis-snapshot.txt` | Snapshot SQL final (Flyway, ranking, geometría, integridad) |
| `restart-persistence.json` | Persistencia tras `down`/`up` sin `-v` |
| `final-state.json` | Salud, ranking, base, contenedores y volúmenes al cierre |
| `environment.txt` | Versiones del entorno |
| `git-state.txt` | HEAD, tree y estado del worktree |
| `SHA256SUMS.txt` | SHA-256 del paquete de evidencia (bytes exactos, sin conversión EOL) |

El manifiesto contiene 79 entradas y cubre todos los archivos de
`artifacts/oc-e2e-20261024/` salvo `SHA256SUMS.txt`; se verifica con
`Get-FileHash` o `sha256sum -c`. El
`.gitattributes` local del paquete fija `-text` para que los hashes no dependan
del sistema operativo ni de `core.autocrlf`.

---

## 15. Conclusión

La tubería física del Sprint 2 funciona de extremo a extremo en el entorno
aislado y reproducible: el navegador consume el backend, el backend orquesta
FastAPI/Modelo D, PostGIS persiste 50 celdas y la UI muestra exactamente 50
rectángulos con el fingerprint correcto. Los fallos por salto fallan de forma
controlada y sin escrituras parciales; la repetición es idempotente; el ciclo
`down`/`up` conserva la ejecución y el fingerprint.

Eso permite afirmar **VALIDADO E2E** para el núcleo CA1–CA4 de SAPI-66. No
permite afirmar GO, cierre de SAPI-66/43, aprobación de CA5 literal, corrida
operacional `current` ni validación científica del modelo. Cualquier cierre de
Jira, PR, merge o cambio de Gate B requiere una decisión humana posterior.

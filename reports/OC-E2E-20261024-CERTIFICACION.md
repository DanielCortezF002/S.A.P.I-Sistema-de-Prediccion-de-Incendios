# Certificación E2E física del Sprint 2 — S.A.P.I. v2

**Versión:** R2 — remediación de hallazgos P1 (2026-10-24, UTC)  
**Rama de evidencia:** `test/oc-fullstack-e2e-r2-20261024`  
**Worktree:** `C:\SAPI-OC-E2E-R2-20261024`  
**Base:** `origin/recovery/s2-academic-20261024` @ `eb1b37030d206462878a785a8f4a67edba7b2c98`  
**Código de aplicación evaluado:** `2a71c7e1160ab87ef7c0ec5e2dfaf3b06c1b4876` — árboles `services`, `app`, `contracts` y `db` idénticos en R1 y R2.  
**Arnés CA4 R2:** `tests/e2e/test_full_stack_timings.py` — blob `22828600e01e27bade5b430fc2174eebeaa26b36`, SHA-256 `e7169f4e178dc9208c5c9d9bb83c884806f9f3065d106b7a6bea5abd8fd20015`.  
**Arnés contratos R2:** `tests/e2e/test_full_stack_contracts.py` — blob `635212c73e01af86bcc657d2542f0ac6c485db45`, SHA-256 `f8796b6ad0e15add4962b16cf27103460d54d05e2b99aaa75f832184d360b613`.  
**Commit de evidencia R2:** el commit que introduce este informe; su SHA se registra en el segundo commit y en el PR de sustitución.  
**R1 (histórico):** rama `test/oc-fullstack-e2e-20261024`, commit `426605f86a98939cd5124ef0e9cea5aa0fc271d1`, PR #41 (draft). Sus mediciones CA4 están **superadas** y no se reutilizan.  
**Candidato protegido:** `51ec3c06b67959d3daad6349c962a1be643906b4` — **no modificado**.  
**Evidencia:** `artifacts/oc-e2e-20261024/` (índice y SHA-256 en `SHA256SUMS.txt`; procedencia en `PROVENANCE.md`; redacción en `REDACTION-NOTICE.md`).

> **Veredicto de esta corrida:** el camino físico completo
> `Edge → Streamlit → Spring Boot → FastAPI/Modelo D → PostgreSQL/PostGIS →
> ranking de 50 celdas` quedó **VALIDADO E2E** para **CA1, CA3 y CA4** en modo
> reproducible. **CA2 queda PARCIAL**: se validaron los contratos de respuesta y
> error en cada servicio, pero no se observó el cuerpo exacto de las peticiones
> entre saltos. **No** se declara GO, **no** se cierra SAPI-66 ni SAPI-43, **no**
> se promueve Gate B y **no** se recalcula nota académica. CA5 literal y la
> corrida operacional `firms_origin=current` siguen **BLOQUEADOS**.

---

## 1. Resumen ejecutivo

| Clasificación | Alcance | Resultado |
|---|---|---|
| **IMPLEMENTADO** | Stack v2 aislado de cuatro servicios, overlay de red, suites E2E y captura de evidencia | Completo en esta rama; sin cambios en aplicación, contratos, modelo ni reglas de Gate B |
| **PROBADO** | Maven backend, suite vertical preexistente, suite full-stack, matriz negativa, contratos por servicio | 163 tests Java (0 fallos, 5 skipped); 5 vertical slice; 8 full-stack R1; 5 negativos R1; 1 contratos R2; 1 CA4 R2 |
| **VALIDADO E2E** | Navegador real, contrato HTTP, PostGIS 1:1, idempotencia, CA4 con gates duros, fallos por salto, persistencia tras `down`/`up` | **CA1, CA3 y CA4 sí** (R1/R2, con limitaciones de §9 y §12). **CA2 PARCIAL** |
| **BLOQUEADO** | CA5 literal sin profile/overrides; corrida operacional SAPI-43 `current`; CA8 real `current`; caso ML degradado | **No ejecutado**; requiere decisión/autorización o cambio de alcance |

**Conteo de pruebas:**

| Suite | Corrida | Resultado | Tiempo | Log autoritativo |
|---|---|---:|---:|---|
| `tests/e2e/test_vertical_slice.py` (preexistente, sin cambios) | R1 | **5 passed** | 17,23 s | `logs/08-vertical-slice-tests.log` |
| `tests/e2e/test_full_stack_timings.py` + `test_full_stack_browser.py` | R1 | **8 passed** | 48,76 s | `logs/35-final-suite.log` |
| `tests/e2e/test_full_stack_negative.py` | R1 | **5 passed** | 101,29 s | `logs/36-final-negative.log` |
| Backend Maven (`mvnw.cmd -B test`) | R1 | **163 tests, 0 failures, 0 errors, 5 skipped** | BUILD SUCCESS | `logs/09-backend-surefire.log` |
| `tests/e2e/test_full_stack_contracts.py` | **R2** | **1 passed** | 10,77 s | `logs/41-r2-contracts.log` |
| `tests/e2e/test_full_stack_timings.py` (gates duros) | **R2** | **1 passed** | 37,16 s | `logs/42-r2-ca4.log` |

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
- Medición CA4 R2 con reinicio de `web-v2` dentro del test, gates duros y
  correlación de `request_id`; logs crudos archivados.
- Validación R2 de contratos de respuesta/error 200 y 422 directamente contra
  FastAPI y Spring Boot.
- Redacción de datos identificatorios y regeneración del manifiesto de hashes.

### 2.2 Lo que no se ejecutó y no se puede afirmar

- `docker compose up` **literal** sin `--profile presentation` ni overlay.
- SAPI-71 Attempt 2 ni una corrida operacional nueva de SAPI-43.
- Una corrida con `firms_origin=current`.
- `RankingHttpToPostgresIT` real con rechazo de `baseline`/`reproducibility`.
- El caso de salud ML degradada por artefacto faltante (se preservó la
  inmutabilidad del Modelo D).
- Captura del cuerpo exacto de las peticiones **entre** servicios (sin
  proxy/tap): por eso CA2 es PARCIAL.
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
| Captura R2 | `2026-10-24T23:41:23Z` (`environment.txt`) |

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

La configuración resuelta se conserva en `logs/43-r2-compose-config.log`:
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
| **CA1** | Test E2E versionado y reproducible sobre stack real, con navegador | **PASS E2E** (R1) | `logs/35-final-suite.log`, `e2e/*.json`, `timings/ca4-*` |
| **CA2** | Errores y contratos por salto, con códigos observados y cero escrituras | **PARCIAL** | `logs/41-r2-contracts.log`, `e2e/contracts-r2.json`, `logs/36-final-negative.log`, `negative/*.json` |
| **CA3** | Filas PostGIS == respuesta HTTP, comparación 1:1 en la misma corrida | **PASS E2E** (R1) | `e2e/postgis-verification.json`, `postgis-snapshot.txt` |
| **CA4** | Tiempos de UI fría, actualización y cached; hash de captura y discriminador | **PASS E2E (R2) con gates duros** | `timings/ca4-timings.csv/.json`, `timings/ca4-raw-*.log`, `timings/ca4-request-correlation.json`, `logs/42-r2-ca4.log` |
| **CA5** | `docker compose up` literal, sin `.env` ni overrides | **BLOQUEADO** | `docs/architecture-stack-freeze-sprint2.md`; `web-v2` profile `presentation` |

**CA2 — por qué PARCIAL.** El test R2 valida, con llamadas HTTP reales, el
`200`/`422` de FastAPI contra `ml-service.v0.yaml` y el `200`/`422` del backend
contra `backend.v0.yaml`; también exige el mismo `inputs_fingerprint` en ambos
saltos. Lo que **no** se observa es el cuerpo exacto que Spring Boot envía a
FastAPI ni el que Streamlit envía al backend: sin un proxy/tap no hay captura de
ese tramo. La clasificación honesta es **PARCIAL**, no PASS total.

**Lectura correcta de SAPI-66:** CA1, CA3 y CA4 quedaron acreditados con
evidencia ejecutada; CA2 es PARCIAL; **SAPI-66 no se cierra** porque CA5 sigue
sin cumplimiento literal: `web-v2` está detrás de `profiles: ["presentation"]` y
esta corrida usó `--profile presentation` más un overlay de red. Cambiar la ruta
por defecto es una decisión de arquitectura que no fue autorizada en este
trabajo.

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
el score es un ranking relativo, no una probabilidad.

**Validación R2 por servicio** (`e2e/contracts-r2.json`):

- FastAPI `GET /health` → 200 contra `MlHealth`.
- FastAPI `POST /predict` → 200 con 50 celdas contra `RankingResult`.
- FastAPI `POST /predict` con campo no admitido → 422 contra `Error`.
- Spring Boot `GET /health` → 200 contra `BackendHealth`.
- Spring Boot `GET /api/v1/ranking` → 200 con 50 celdas contra `RankingResult`.
- Spring Boot `GET /api/v1/ranking?forecast_time=not-a-date` → 422 contra `Error`.
- Mismo `inputs_fingerprint` en FastAPI y backend para la misma `T`.

La cobertura declarada en el JSON mantiene explícitamente
`per_hop_contract_validation: PARCIAL` y los dos tramos no observados.

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

**Comprobación R2 al cierre:** `r2-final-state.json` registra 1 ejecución, 50
predicciones, 50 geometrías (50 válidas), fingerprint sin cambios y los tres
servicios en 200. CA4 (cold, update y cached) no alteró el estado persistido.

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

**Alcance R2:** la suite de navegador no se modificó ni se volvió a ejecutar en
R2; esta evidencia es R1 y su arnés es el mismo blob (`a71286d7`) que en R2. No
se presenta como una corrida nueva.

---

## 8. CA4 — tiempos de UI fría, actualización y cached

La evidencia autoritativa R2 es `timings/ca4-timings.csv` y
`timings/ca4-timings.json`. El test **impone** las condiciones y falla si no se
cumplen:

1. reinicia **solo** `web-v2` dentro del test y espera salud (caché de Streamlit
   vacía, `cache_establishment.ready_ms = 4.115,89 ms`);
2. exige **≥1** `ml_predict` real y **≥1** `POST /predict 200` en frío;
3. exige en la actualización un `request_id` nuevo, `ml_responded=true`,
   `ml_http_status=200`, `outcome=ok` y el mismo `inputs_fingerprint`;
4. exige **cero** `ml_predict` y **cero** `POST /predict` en el rerun cacheado.

| Acción | Tiempo medido (R2) | Hasta cabecera | Hasta backend | `ml_predict` Δ | ML Δ | Latencia ML | `fetched_at` |
|---|---:|---:|---:|---:|---:|---:|---|
| `cold_ui` (web-v2 reiniciado, navegador nuevo) | **6.867,90 ms** hasta mapa | 5.791,92 ms | — | **1** | **1** | 2.820 ms | 23:49 UTC |
| `update` (“Actualizar ranking”, invalida caché) | **3.723,47 ms** | — | 3.576,28 ms | **1** | **1** | 3.338 ms | 23:50 UTC |
| `cached` (cambio de orden, rerun sin backend) | **424,06 ms** | — | — | **0** | **0** | — | 23:50 UTC |

Gates verificados: `cold_backend_predicts=1`, `cold_ml_predicts_200=1`,
`update_backend_predicts=1`, `update_ml_predicts_200=1`,
`update_fingerprint_unchanged=true`, `cached_backend_predicts=0`,
`cached_ml_predicts_200=0`, `console_errors=0`.

Request IDs correlacionados:

- cold: `fa05e014-4228-4ed9-92b6-53a2a9c6fc1e`
- update: `b197bbe3-0646-4876-be9e-f55d30fa0892` (nuevo, distinto de cold)
- cached: ninguno

Capturas y SHA-256 (R2):

| Acción | Archivo | SHA-256 |
|---|---|---|
| cold | `timings/ca4-cold-ui.png` | `db471446fc824ca9ae83beef720a1e68a6c935c321f2506403072482b59e44a5` |
| update | `timings/ca4-update.png` | `49b67479d56888ea1740a185c1fcb6c2af87317db7376d0fb9aebf417a9e8ebe` |
| cached | `timings/ca4-cached.png` | `bfa8799a956158122c54b17498bcb9e5b7d15637a4d4515010b33f772cd9cf20` |

Logs crudos y correlación:

- `timings/ca4-raw-backend.log`: log completo del backend durante R2, con
  timestamps de Docker.
- `timings/ca4-raw-ml.log`: log completo de FastAPI durante R2, con timestamps.
- `timings/ca4-request-correlation.json`: por acción, ventana temporal, líneas
  `ml_predict` nuevas, líneas `POST /predict 200` nuevas, deltas y procedencia.
- `logs/42-r2-ca4.log`: salida pytest de la corrida (1 passed, 37,16 s).

**Salvedades CA4:**

- El tiempo cold incluye el arranque en frío de Streamlit tras el reinicio; no es
  un tiempo puro de red ni un SLA.
- La cabecera solo muestra `HH:MM`; el discriminador real es la correlación de
  `request_id` y los deltas de logs, no el PNG.
- R2 se midió en el mismo equipo local; no sustituye CI remoto ni producción.
- Las mediciones R1 (`6.065,26 / 2.649,82 / 893,25 ms`) se conservan como
  registro histórico en el commit `426605f`, pero **están superadas**: su arnés
  no imponía caché fría. No se reutilizan en este informe como si fueran R2.

---

## 9. Matriz negativa y comportamiento fail-closed

| Caso inducido | Resultado observado | Escrituras | Recuperación |
|---|---|---|---|
| `forecast_time` inválido | `422 invalid_request` | 0 (1/50 antes y después) | inmediata |
| Payload inválido a FastAPI (3 variantes) | `422 invalid_request` en las tres | n/a | inmediata |
| `ml-api` detenido | `503 upstream_unavailable` en 4.015,48 ms | 0 | 200 en 4.531,23 ms |
| `db-v2` detenida | `500 internal_error` en 32.734,50 ms | 0 | 200 en 5.058,09 ms |
| `backend` detenido + UI recargada | error controlado “No se pudo conectar con el backend”, sin traceback ni host interno | n/a | 50 celdas visibles al volver |

Evidencia: `logs/36-final-negative.log` y `negative/*.json` / `negative/*.png`
(R1, arnés sin cambios en R2). El test R2 de contratos revalida además el
`422 invalid_request` real de ambos servicios (`logs/41-r2-contracts.log`).

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
6. **CA4 R1 no imponía la condición de caché fría (P1 corregido en R2).** El
   arnés R1 medía, pero la caché se vaciaba a mano fuera del test. R2 reinicia
   `web-v2`, exige llamadas reales y falla en caso contrario.
7. **CA2 estaba sobredeclarado (P1 corregido en R2).** Se validaba el payload
   final contra el esquema, no cada salto. R2 agrega contratos reales por
   servicio y declara PARCIAL el tramo no observado.
8. **Privacidad de los artefactos (P1 corregido en R2).** R1 publicó un IPv4
   globalmente enrutable y el nombre del perfil local en logs. R2 los redactó y
   regeneró hashes; la historia de `426605f` sigue expuesta y requiere decisión
   del Product Owner (`REDACTION-NOTICE.md` §4).
9. **Procedencia ambigua (P1 corregido en R2).** R1 mezclaba el commit de
   aplicación (`2a71c7e`), el del arnés (`426605f`) y el de evidencia. R2
   registra autohash del arnés, árboles de aplicación y hashes por artefacto
   (`PROVENANCE.md`).

---

## 11. Impacto legítimo en las rúbricas

No se recalcula puntaje ni se declara una subida de nota. Lo que esta corrida
aporta, por criterio:

| Criterio | Impacto | Lectura |
|---|---|---|
| **César 3 — Arquitectura (IL2.3)** | Confirma físicamente los cuatro servicios, la ruta v2 y el aislamiento de fallos | Ya estaba en “Excelente”; **no cambia el nivel**, pero la evidencia es más fuerte |
| **César 4 — Datos/plataformas (IL2.4)** | Confirma Flyway, PostGIS, 50 geometrías y persistencia 1:1 | Ya estaba en “Excelente”; **no cambia el nivel** |
| **César 5 — Gestión del Sprint 2, pruebas y riesgos** | Aporta una corrida E2E real, matriz negativa y paquete reproducible | **Mejora la base de evidencia**; el descriptor “Excelente” sigue limitado por el Sprint Backlog incompleto (SAPI-43/66 abiertas). No se declara subida |
| **Matías 6 — Validación y pruebas** | Agrega una validación ejecutada, no solo histórica; CA2 se declara PARCIAL | Ya estaba en “Excelente”; **refuerza la defensa**, sin cambiar el nivel |
| **Matías 7 — Integración y atributos de calidad** | Prueba real de fallos por salto, recuperación y persistencia tras reinicio | Ya estaba en “Excelente”; **refuerza la defensa**, sin cambiar el nivel |
| **Matías 1 — Incremento funcional** | La tubería queda certificada, pero SAPI-43/66 siguen abiertas y CA2 es PARCIAL | **No se declara incremento íntegro** |
| **Matías 5 — Implementación y calidad** | Los defectos históricos no se borran por repetir pruebas | **Sin cambio de nivel** |

En síntesis: la evidencia **mejora César 5, Matías 6 y Matías 7**; confirma
César 3/4 sin subirlos; no alcanza para Matías 1 mientras SAPI-43/66 no cierren y
CA2 no sea total.

---

## 12. Limitaciones y bloqueos

| Bloqueo | Estado | Qué haría falta |
|---|---|---|
| SAPI-66 CA5 literal | **BLOQUEADO** | Decisión sobre `web-v2` en la ruta por defecto, o reformulación aprobada del CA |
| SAPI-66 CA2 por salto | **PARCIAL** | Proxy/tap que capture las peticiones backend→ML y Streamlit→backend, o instrumentación equivalente |
| SAPI-43 corrida operacional | **BLOQUEADO** | SAPI-71 Attempt 2 autorizado, credenciales y stores `current` |
| SAPI-43 CA8 | **BLOQUEADO** | `RankingHttpToPostgresIT` real con política `current` |
| ML degradado (artefacto faltante) | **NO EJECUTADO** | Prueba con una copia/artefacto alternativo, preservando Modelo D |
| Exposición histórica de datos R1 | **ABIERTA** | Cerrar/abandonar PR #41, reescribir historia o purga de GitHub; decisión del PO |
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

$env:SAPI_E2E_FULL_STACK='1'

# Contratos por servicio (R2)
python -m pytest tests/e2e/test_full_stack_contracts.py -v --no-cov

# CA4 con gates duros (R2). Reinicia solo web-v2 al comenzar.
python -m pytest tests/e2e/test_full_stack_timings.py -v --no-cov

# Navegador real (R1, sin cambios)
python -m pytest tests/e2e/test_full_stack_browser.py -v --no-cov

# Matriz negativa (detiene/levanta servicios de este proyecto)
$env:SAPI_E2E_FAULT_INJECTION='1'
python -m pytest tests/e2e/test_full_stack_negative.py -v --no-cov
```

`--no-cov` es necesario porque `pytest.ini` exige 80 % de cobertura global; una
corrida dirigida de otro modo termina con código 1 aunque los tests pasen.
`test_full_stack_timings.py` debe ejecutarse **antes** que
`test_full_stack_browser.py` porque reinicia `web-v2`.

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

| Archivo | Contenido | Corrida |
|---|---|---|
| `logs/42-r2-ca4.log` | CA4 R2 con gates duros (1 passed) | R2 |
| `logs/41-r2-contracts.log` | Contratos por servicio (1 passed) | R2 |
| `logs/40-r2-compose-up.log` / `logs/43-r2-compose-config.log` | Levantamiento y configuración resuelta | R2 |
| `timings/ca4-timings.csv` / `.json` | Tiempos, deltas, request IDs, gates y procedencia | R2 |
| `timings/ca4-request-correlation.json` | Correlación por acción y líneas crudas | R2 |
| `timings/ca4-raw-backend.log` / `ca4-raw-ml.log` | Logs crudos con timestamps | R2 |
| `e2e/contracts-r2.json` | 200/422 reales por servicio + cobertura PARCIAL | R2 |
| `r2-final-state.json` | Salud, ranking, base y contenedores al cierre R2 | R2 |
| `r2-git-state.txt` | HEAD, tree y estado del worktree R2 | R2 |
| `environment.txt` | Versiones del entorno (R2) | R2 |
| `logs/35-final-suite.log` | 8 tests full-stack + CA4 de R1 | R1 |
| `logs/36-final-negative.log` | 5 tests de fallos, salida final | R1 |
| `logs/08-vertical-slice-tests.log` | 5 tests vertical slice preexistentes | R1 |
| `logs/09-backend-surefire.log` | Maven: 163 tests, 0 fallos | R1 |
| `e2e/ranking-http.json` | Respuesta HTTP, hash y request id | R1 |
| `e2e/postgis-verification.json` | Flyway, ejecución, 50 filas, comparación 1:1 | R1 |
| `e2e/idempotency.json` | Segunda llamada, celdas iguales, 1 ejecución | R1 |
| `e2e/openapi-conformance.json` | Validación contra contratos congelados | R1 |
| `e2e/browser-verification.json` | Edge, 50 rectángulos, fingerprint, consola | R1 |
| `negative/*.json` | Códigos, tiempos y conteos de la matriz negativa | R1 |
| `postgis-snapshot.txt` | Snapshot SQL final (Flyway, ranking, geometría, integridad) | R1 |
| `restart-persistence.json` | Persistencia tras `down`/`up` sin `-v` | R1 |
| `r1-final-state.json` | Salud, ranking, base, contenedores y volúmenes al cierre R1 | R1 |
| `r1-git-state.txt` | HEAD, tree y estado del worktree R1 | R1 |
| `PROVENANCE.md` | Qué arnés/commit produjo cada grupo | R1 + R2 |
| `REDACTION-NOTICE.md` | Redacción, conteos y exposición histórica | R1 + R2 |
| `SHA256SUMS.txt` | SHA-256 del paquete (91 entradas) | R1 + R2 |

El manifiesto cubre los 91 archivos de `artifacts/oc-e2e-20261024/` salvo
`SHA256SUMS.txt`; se verifica con `Get-FileHash` o `sha256sum -c`. El
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

Eso permite afirmar **VALIDADO E2E** para CA1, CA3 y CA4, y **PARCIAL** para CA2.
No permite afirmar GO, cierre de SAPI-66/43, aprobación de CA5 literal, corrida
operacional `current`, validación científica del modelo ni validación total de
contratos por salto. Cualquier cierre de Jira, PR, merge o cambio de Gate B
requiere una decisión humana posterior.

---

## 16. Procedencia, R1 y notas de supersesión

| Rol | R1 | R2 |
|---|---|---|
| Aplicación probada | `2a71c7e` | Mismos árboles en `eb1b370` |
| Arnés CA4 | blob `3b750d8b` / SHA-256 `26877fbf` | blob `22828600` / SHA-256 `e7169f4e` |
| Arnés contratos | no existía | blob `635212c7` / SHA-256 `f8796b6a` |
| Commit de evidencia | `426605f` (PR #41) | commit de evidencia R2 + commit de registro |

- **R1 no registró autohash del arnés.** Su vínculo es documental: el log de la
  corrida y el commit `426605f`, cuyo blob de CA4 es `3b750d8b`.
- **R2 registra autohash** en `timings/ca4-timings.json` y
  `e2e/contracts-r2.json`; el blob publicado debe coincidir con
  `git hash-object` en el commit de evidencia.
- **R1 CA4 está superado** por R2. Los números R1 se conservan solo como
  registro histórico; no se usan como medición vigente.
- **La aplicación no cambió** entre `2a71c7e` y `eb1b370` (`git diff` vacío para
  `services`, `app`, `contracts`, `db`).
- Las contradicciones documentales con `SAPI_SPRINT2_CLOSEOUT_REPORT.md`,
  `docs/hito2/INFORME_HITO2_FINAL.md` y `recovery-evidence/` se tratan en
  `reports/OC-E2E-R2-SUPERSESSION-NOTES.md`, sin sobrescribir esos registros.

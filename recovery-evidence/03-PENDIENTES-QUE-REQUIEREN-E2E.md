# 03 — Pendientes que requieren E2E, datos reales o infraestructura

**Fecha:** 2026-10-24  
**HEAD:** `51ec3c06b67959d3daad6349c962a1be643906b4`  
**Regla:** este documento enumera lo que **no** puede cerrarse con pruebas unitarias/estáticas ni con evidencia histórica. No autoriza ejecutar nada por sí solo.

## 1. Resumen de pendientes

| HU / CA | Pendiente | Tipo | Evidencia mínima para cerrar | Prerrequisito | Control Gate B |
|---|---|---|---|---|---|
| SAPI-66 CA1 | Crear y ejecutar `tests/e2e/test_vertical_slice.py` | E2E | Test reproducible + reporte en `artifacts/hito2/e2e/<ts>/` | Stack completo arriba; Docker/Edge | GB-07 |
| SAPI-66 CA2 | Reporte de errores y contratos **por salto** | E2E | Fallos inducidos en UI→Spring→FastAPI→Modelo→PostGIS, con códigos y contratos | CA1 + capacidad de inyectar fallos | GB-07 |
| SAPI-66 CA3 | Igualdad filas en base == respuesta, en corrida E2E | E2E | Consulta psql + respuesta HTTP + conteos | CA1 + PostGIS | GB-07 |
| SAPI-66 CA4 | Recaptura discriminante de update/cached y timings por salto | E2E | PNG con detalle de segundos o hash de contenido; `screenshot_sha256`; `navigation_type`; `timings.csv` frío/caliente | CA1 + Edge + ventana horaria | GB-07 |
| SAPI-66 CA5 | `docker compose up` literal, sin `.env` ni overrides | E2E / decisión | `scripts/e2e_slice.py` sobre compose por defecto; 18/18 o equivalente | Decisión sobre `web-v2` en la ruta por defecto | GB-06 |
| SAPI-43 CA1 | Ejecutar SAPI-71 Attempt 2 y usar sus stores CURRENT | Datos reales | Evidencia de refresh autorizado + `firms_origin=current` + fingerprint | Autorización humana, credenciales, host Windows | GB-11 |
| SAPI-43 CA2 | Corrida operacional con logs backend/ML | Datos reales | Logs de la corrida + respuesta con `model_version` | CA1 | GB-11 / GB-07 |
| SAPI-43 CA3 | Persistencia real de 50 filas con metadata | Datos reales | psql: 50 filas, `model_version`, fingerprint | CA1 | GB-11 |
| SAPI-43 CA4 | Consulta psql ordenada por ranking | Datos reales | `rank 1..50` en la misma corrida | CA1 | GB-11 |
| SAPI-43 CA5 | Evidencia runtime de no usar `demo_seed`/legacy | Datos reales | Log de entrypoint + test de arquitectura | CA1 | GB-11 |
| SAPI-43 CA6 | Repetición idempotente sobre la corrida real | Datos reales | Segunda corrida: 0 ejecuciones nuevas, 50 filas, `dup=0` | CA1 | GB-11 |
| SAPI-43 CA7 | Metadatos científicos en la corrida real | Datos reales | `scientific_model_validation=false`, `relative_rank` | CA1 | GB-11 |
| SAPI-43 CA8 | `RankingHttpToPostgresIT` real + rechazo operacional | Infraestructura | IT con Testcontainers; rechazo de `baseline`/`reproducibility`/ausente con política `current` | Docker/Testcontainers + autorización | GB-11 |

## 2. SAPI-66: qué falta exactamente

### 2.1 CA1 — Test E2E reproducible

No basta con que W3 haya ejecutado un E2E manual. El CA pide un **test versionado y reproducible**. Mínimo:

1. Crear `tests/e2e/test_vertical_slice.py` con un test que arranque desde la UI o desde HTTP y recorra Streamlit → Spring → FastAPI → Modelo D → PostgreSQL/PostGIS.
2. Crear `scripts/e2e_slice.py` si se mantiene la vía script (el CA5 lo nombra).
3. Guardar en `artifacts/hito2/e2e/<timestamp>/`: comando, salida, códigos HTTP, payload, filas de base, timings y hashes.
4. Ejecutarlo sobre un stack limpio y sobre el SHA congelado.

**No ejecutado aquí:** Docker está prohibido y el daemon no está disponible. No se creó el test porque el alcance de esta recuperación es documentar y probar lo existente, no inventar un E2E no ejecutado.

### 2.2 CA2 — Errores y contratos por salto

El happy path W3 no demuestra errores por salto. Mínimo:

- UI/Streamlit con backend caído: mensaje controlado, sin stack trace.
- Spring con ML caído: 503/504, sin 200 con resultado inválido.
- FastAPI con payload inválido: 422; con resultado inválido: 500.
- Backend con resultado inválido: 500, cero escrituras.
- PostGIS caído: fallo fail-closed, no persistencia parcial.
- Cada caso con contrato YAML y código observado.

Las pruebas unitarias P-04/P-06 y Java J-01 cubren varias de estas ramas, pero no la cadena E2E completa.

### 2.3 CA3 — Persistencia y consulta

W4 ya probó persistencia/consulta real sobre el mismo SHA. Para **cerrar CA3 dentro de SAPI-66** hace falta que esa verificación forme parte de la corrida E2E reproducible: respuesta HTTP, filas en base, comparación 1:1 y consulta psql en el mismo reporte.

### 2.4 CA4 — Tiempos y recaptura

El CA4 literal pide “tiempo total de respuesta documentado”; la verificación planificada pide “tiempos por salto (frío y caliente)” y un `timings.csv`.

Pendiente:

1. Un `timings.csv` consolidado con, al menos: cold UI, update, cached, health ML, health backend, health web, consulta PostGIS.
2. Recaptura de update y cached con un discriminador **visible**: abrir el detalle con segundos antes de la captura, o incluir un hash de contenido en la vista.
3. Registrar `screenshot_sha256`, `browser_navigation_type` y `action` (el arnés ya los produce).
4. Evitar que update y cached caigan en el mismo minuto, o aceptar que el PNG no discrimina y usar el DOM/CSV como evidencia principal.

**No ejecutado aquí:** requiere Edge + stack + ventana de medición. Las capturas históricas no se alteraron.

### 2.5 CA5 — `docker compose up` literal

El obstáculo no es solo Docker: es de **diseño de la ruta por defecto**.

- `web-v2` tiene `profiles: ["presentation"]`; `docker compose up` no lo arranca.
- `scripts/e2e_slice.py` no existe.
- W3 usó `COMPOSE_PROFILES=presentation`, lista explícita y overrides; el validador tiene 3 sustituciones (ruta, puertos backend/ML, URL).

Opciones (ninguna ejecutada aquí):

| Opción | Qué implica | Efecto en CA5 |
|---|---|---|
| A. Incluir `web-v2` en la ruta por defecto | Cambio de compose y de arquitectura de arranque; requiere aprobación | Podría habilitar la ejecución literal |
| B. Mantener el profile y aceptar la alternativa `bootstrap_compose_v2.py` | Ya aprobada por el PO (Jira `#10156`) | **No convierte el CA5 literal en PASS**; EX-06 sigue pendiente |
| C. Reformular el CA5 con el PO | Cambio documental/Jira | No ejecutado; no se inventa |

Gate B v5: **GB-06 PARCIAL (no literal)**, EX-06 pendiente/diferida. No se promueve.

## 3. SAPI-43: qué falta exactamente

### 3.1 Dependencia dura: SAPI-71 Attempt 2

`docs/ops/FIRST-CONTROLLED-REFRESH.md:5` declara:

> “Attempt 2 is **NOT STARTED**.”

El CA1 exige stores FIRMS/DMC versionados **producidos por el refresh de SAPI-71**. W3/W4 prueban que se usaron stores CURRENT y que `firms_origin=current`, pero no que esos stores provengan de Attempt 2. Por tanto:

- no se puede cerrar CA1;
- no se puede presentar la corrida W3/W4 como “corrida operacional nueva”;
- no se puede rotular el snapshot de Hito 1 como corrida diaria real.

Requisitos para Attempt 2 (según el runbook): nuevo SHA main, directorio de evidencia, preflight, autorización humana explícita y datos del equipo Windows de Daniel. **No ejecutado aquí.**

### 3.2 Cadena operacional posterior

Una vez exista Attempt 2, la corrida SAPI-43 debe producir:

| CA | Evidencia mínima |
|---|---|
| CA2 | Log backend + log ML + respuesta con `model_version=prototype_model_d_v1` |
| CA3 | psql: 50 filas, `model_version`, `inputs_fingerprint`, `firms_origin=current` |
| CA4 | psql: `rank 1..50` y orden estable |
| CA5 | Log de entrypoint que no invoque `demo_seed` ni `run_daily_pipeline`; test de arquitectura |
| CA6 | Repetición con los mismos insumos: 1 ejecución, 50 filas, `dup_cell_id=0`, `dup_K=0` |
| CA7 | `scientific_model_validation=false`, `score_semantics=relative_rank` |
| CA8 | Rechazo real de `baseline`/`reproducibility`/ausente con política `current`; 0 escrituras |

### 3.3 CA8 — IT real pendiente

`RankingHttpToPostgresIT` (B1) requiere Testcontainers/DB real. La corrida Java J-01 cubre política, binding y persistencia unitaria, pero **no** el rechazo HTTP→PostgreSQL real. Para cerrar CA8 hacen falta:

- `RankingHttpToPostgresIT` con política `current` y casos `baseline`, `reproducibility`, ausente;
- control sintético `current` → 1 ejecución + 50 predicciones;
- E2E operacional con `docker-compose.operational.yml` que demuestre rechazo (500, cero escrituras) de una respuesta real en `reproducibility`.

**No ejecutado aquí:** Docker/Testcontainers prohibidos. Gate B GB-11 sigue CONDICIONADO.

## 4. Protocolo E2E mínimo (para cuando esté autorizado)

Este protocolo **no se ejecutó**; se deja para que la próxima sesión no improvise.

1. **Congelar**: registrar `git rev-parse HEAD`, tree, `git status --porcelain --ignored`, ausencia de `.env`.
2. **Arrancar**: `docker compose config` y `docker compose up -d` (o la ruta que el PO apruebe para CA5). Registrar servicios y healthchecks.
3. **Salud**: `GET /health` de ML/backend/web; códigos y latencias.
4. **Ranking**: `GET /api/v1/ranking`; validar 50 celdas, `rank 1..50`, `firms_origin=current`, `relative_rank`, `scientific_model_validation=false`, `model_version`, fingerprint.
5. **Base**: psql; 50 filas, `rank`, `cell_id`, `model_version`, fingerprint; comparar 1:1 con la respuesta.
6. **Navegador**: Edge; cold, click “Actualizar ranking”, refresh; capturar timings, timestamp DOM con segundos, `screenshot_sha256` y `browser_navigation_type`.
7. **Errores**: inducir ML caído, backend caído, payload inválido, resultado inválido; verificar 503/504/422/500 y cero escrituras.
8. **Idempotencia**: repetir el mismo GET; verificar 1 ejecución, 50 filas, `dup=0`.
9. **Reinicio**: `docker compose down` sin `-v`; `up`; verificar volumen y misma ejecución.
10. **Cierre**: `down` sin `-v`; preservar volúmenes/evidencia; registrar comando, exit code, archivo y SHA.

## 5. Qué no se puede afirmar hasta ejecutar lo anterior

- “SAPI-66 cerrado” o “CA1/CA5 PASS”.
- “CA4 tiene dos pruebas independientes de update y cached”.
- “SAPI-43 tuvo una corrida operacional nueva”.
- “`firms_origin=current` proviene de SAPI-71 Attempt 2”.
- “CA8 está cerrado con IT real”.
- “Gate B cambió a GO”.

## 6. Impacto en Gate B

| Control | Estado v5 | Qué falta | ¿Este documento lo cambia? |
|---|---|---|---|
| GB-06 | **PARCIAL (no literal)** | L2 CA5 literal sin `.env` + negativos, o EX-06 | No |
| GB-07 | **CONDICIONADO** | L3/L4 literal sobre el SHA, o EX-07 + overrides; CA4 recapturado | No |
| GB-11 | **CONDICIONADO** | `firms_origin=current` sobre el SHA, o EX-11 + overrides | No |

**No se promueve ningún control.** Gate B sigue **NO GO**.

## 7. Responsables y autorizaciones

| Pendiente | Responsable / autorización |
|---|---|
| Docker/E2E, Testcontainers, D08/G1/L1 | PO / responsable de infraestructura; no autorizado en esta sesión |
| SAPI-71 Attempt 2 y datos reales | Daniel / PO; credenciales y host Windows |
| Cambio de ruta por defecto para CA5 | PO + arquitectura; no decidido aquí |
| Cierre Jira / comentarios / merge | PO / responsable de Jira; **no ejecutado** |

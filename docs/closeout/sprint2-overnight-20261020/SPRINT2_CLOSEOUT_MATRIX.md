# Matriz de cierre Sprint 2 — estado verificable

Base: `0ac6c05ebd1df66c029fc25f6dbfd66899e8bce4` (SHA coincide con el esperado). Criterios tomados de
`docs/hito2/requerimientos-sprint2.md` y de Jira (lectura) para SAPI-67. Nada aquí cambia Jira.

**Leyenda de evidencia:** `[N]` ejecutado en esta sesión (nube Linux, sin Docker daemon) ·
`[R]` artefacto versionado en el repo, producido en otro entorno/commit, **no reproducido aquí** ·
`[—]` sin evidencia. Un `[R]` no se promueve a "comprobado" sin repetirlo sobre la candidata definitiva.

## 1. HU / CA clave

| HU/CA | Comportamiento esperado | Implementación | Prueba existente | Evidencia | Brecha | Prio |
|---|---|---|---|---|---|---|
| SAPI-55 `/predict`, `/health` | Contrato `ml-service.v0`, 50 celdas, `scientific_model_validation=false` | `services/ml_api/main.py` | `test_ml_api.py`, `test_openapi_contracts.py`; nuevas `test_overnight_s2_chain_integrity.py` | `[N]` suite 2154 ok / 0 fallos | Dockerfile.ml-api no construible en nube (apt bloqueado) → CA8 de SAPI-55 solo en host | M |
| SAPI-57.CA4 Spring↔FastAPI real | Mismos bytes que `POST /predict` | `MlServiceClient`, `RankingService` | `RankingRealMlServiceTests` (se omite sin `SAPI_IT_ML_BASE_URL`) | `[N]` contra uvicorn real: **3/4 FALLAN** en el candidato por `age_hours` (reloj); con el parche propuesto 4/4 | **Defecto de prueba latente**, ver `E2E_VERIFICATION_REPORT.md` §3 | **A** |
| SAPI-60.CA1–CA5 | Compose v2, health, `.env.example`, volumen, README | `docker-compose.yml`, `tests/test_compose_v2.py` | tests estáticos de compose `[N]` pasan | `[R]` `artifacts/hito2/testing/sapi-60/` (con imagen ML *sustituta*) | Reproducción real solo en host | A |
| SAPI-60.CA6 entorno limpio | Funciona desde clon limpio sin deps locales | `Dockerfile.*`, `scripts/compose_v2_preflight.py` | — | `[R]` parcial (sandbox, imagen sustituta) | **Falta build de `Dockerfile.ml-api` + preflight en Omen; el plan pide además un no-autor y Windows** | **A** |
| SAPI-61.CA1–CA5 | Streamlit consume REST, errores visibles | `app/utils/backend_client.py`, `ranking_backend_view.py` | `test_backend_client.py`, `test_sapi61_http_stub.py`, `test_ranking_backend_view.py`; nuevas E2E-stub | `[N]` | Sin backend Spring real en la prueba | M |
| SAPI-66.CA1 cadena completa | E2E reproducible Streamlit→Spring→FastAPI→PostGIS | `scripts/bootstrap_compose_v2.py`, `scripts/measure_browser_e2e_d21.py` | `test_convergence_*`, `test_measure_browser_e2e_d21.py` | `[R]` `artifacts/hito2/closeout_e2e/` generado sobre commit `8982e58`, **que no existe en el historial de esta rama** | Repetir sobre la candidata definitiva (Docker + navegador) | **A** |
| SAPI-66.CA2 contratos por salto | Validación contra YAML | `test_openapi_contracts.py`, `BackendContract` (Java) | `[N]` Python y Maven (162 ok) | `[N]` | Salto Streamlit→backend solo con stub | M |
| SAPI-66.CA3 persistencia == respuesta | Filas en BD == respuesta | `RankingPersistenceIT`, `RankingHttpToPostgresIT` (Testcontainers) | ITs **no ejecutados** (`mvn verify` requiere Docker) | `[R]` | Sin Docker en la nube | A |
| SAPI-66.CA4 tiempos | frío/caliente documentados | `measure_browser_e2e_d21.py` | — | `[R]` 897,4 / 1952,5 ms (informe raíz) vs 1709,5 ms (TRAZABILIDAD): **cifras distintas entre documentos** | Unificar fuente y SHA | M |
| SAPI-66.CA5 literal | `docker-compose up` sin configuración | — | — | TRAZABILIDAD: "FALLA tal como escrito"; alternativa aprobada (Jira #10156) | Requiere `.env`/`SAPI_DB_PASSWORD` (`:?`). Cierre honesto = criterio reformulado, no PASS literal | M |
| SAPI-43.CA8 política `current` | Origen ≠ `current` → 500, 0 escrituras | `FirmsOriginPolicy`, `RankingService` | Java `RankingHttpToPostgresIT` (Docker); Py `test_f1_ca8_operational_overlay_dynamic` | `[N]` omitido aquí (sin Docker); `[R]` CI verde con Docker | Ver `CI_AND_SKIPS_AUDIT.md` §3 (regresión experimental 503/500) | A |
| SAPI-43 datos reales / SAPI-71 | Refresh real FIRMS/DMC | `src/refresh/` | suites adversariales `[N]` | `[R]` Autorización B (rutas `C:\Users\...` del Omen, no versionadas) | Hashes del informe raíz no verificables aquí | M |
| SAPI-67 | Ver §2 | `docs/adr/ADR-011-cloud-provider.md` | — | Jira: PENDIENTE A VALIDACION | ADR sin firma; decisión de presupuesto lo desplaza | M |

## 2. SAPI-67 (criterios literales de Jira, leídos hoy)

1. Comparar ≥3 opciones (Railway, Render, AWS Free Tier/Fly.io) → **cumple** (ADR-011 compara 4: Railway, Render, Fly.io, AWS).
2. Criterios: costo, Docker, PostgreSQL managed, HTTPS, CI/CD → **cumple** (matriz de 9 criterios).
3. **ADR firmado con decisión final → NO cumple.** ADR-011 está en estado *Propuesto*; recomendaba AWS Lightsail.
4. No desplegar nada hasta ADR aprobado → **cumple** (ADR dice "No desplegado").

Hecho nuevo en Jira (16-10): el responsable fijó gasto incremental **$0 CLP**, descartando Lightsail y Railway Hobby,
y el ticket dice expresamente que esa restricción *no completa* el criterio 3. **Consecuencia:** el ADR vigente
recomienda una opción ya prohibida. Cierre honesto (decisión humana, no mía): (a) enmendar ADR-011 a
`LOCAL-FIRST / SIN CLOUD DE PAGO` con registro documental y aprobación explícita, y reformular el criterio 3; o
(b) replanificar como *Could* fuera del Sprint 2. No declarar Finalizado sin una de las dos.

## 3. Discrepancias entre fuentes (a resolver antes de la defensa)

| Tema | Fuente A | Fuente B |
|---|---|---|
| Estado SAPI-66/60 | Jira: Finalizado; `SAPI_SPRINT2_CLOSEOUT_REPORT.md`: PASS | TRAZABILIDAD: CA5 literal falla; CA6 de SAPI-60 PARCIAL |
| Historias abiertas | Informe raíz: todas PASS | `MATRIZ_RUBRICA_CESAR_FINAL.md`: 5/14 abiertas |
| Latencia cold | 897,4 ms (commit `8982e58`) | 1709,5 ms (TRAZABILIDAD) |
| Jira SAPI-43/SAPI-71 | Finalizado | `requerimientos`: SAPI-71 Attempt 2 "NOT STARTED" (documento anterior al 16-10; puede estar desfasado) |

## 4. Veredicto

**CONDITIONAL.** Lo automatizable sin humano está verde (Python 2154/0 fallos; Maven 162/0 fallos). No es READY porque:
SAPI-60.CA6 y SAPI-66 dependen de Docker/Omen y su evidencia es de otro commit; SAPI-67.CA3 requiere decisión humana;
y existe un defecto real de prueba (SAPI-57.CA4 contra ML real) que hoy está oculto porque la prueba se omite.

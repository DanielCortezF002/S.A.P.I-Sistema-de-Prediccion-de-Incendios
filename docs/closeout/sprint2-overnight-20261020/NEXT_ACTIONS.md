# Acciones priorizadas para cerrar el Sprint 2

| # | Acción | Quién | Requiere aprobación | Cierra |
|---|---|---|---|---|
| 1 | En el Omen, sobre la candidata definitiva: `docker compose` build **incl. `Dockerfile.ml-api`** + `scripts/compose_v2_preflight.py`; guardar salida en `artifacts/hito2/testing/sapi-60/host/` con SHA | Daniel (delegable el análisis de logs) | No | SAPI-60.CA6 |
| 2 | Repetir E2E de navegador + persistencia (`measure_browser_e2e_d21.py`) sobre la candidata (la evidencia actual es del commit `8982e58`, ausente de esta rama); unificar cifra de latencia 897,4 vs 1709,5 ms | Daniel | No | SAPI-66.CA1/3/4 |
| 3 | Decidir SAPI-67: enmendar ADR-011 a `LOCAL-FIRST / SIN CLOUD DE PAGO` y reformular el criterio "firmado", **o** replanificar fuera del Sprint 2. Luego firmar | Daniel (decisión humana) | **Sí** | SAPI-67.CA3 |
| 4 | Revisar y aplicar `evidence/proposed-fix-RankingRealMlServiceTests.patch` (PR aparte, tras el endurecimiento F7); ejecutar con `SAPI_IT_ML_BASE_URL` en CI/Omen | Delegable | Sí (toca prueba del candidato) | SAPI-57.CA4 real |
| 5 | Ejecutar el test CA8 dinámico en Linux con Docker y capturar logs del backend (`ml_responded`, `outcome`) para confirmar/descartar la hipótesis 503 | Delegable | No | SAPI-43.CA8 |
| 6 | Reconciliar Jira (SAPI-60/66 "Finalizado") con TRAZABILIDAD (CA6 parcial, CA5 literal) — decidir reformular CA o reabrir; **no cambiar estados sin ese registro** | Daniel | **Sí** | coherencia |
| 7 | Añadir `playwright` a `requirements-dev.txt` o aceptar explícitamente las 12 omisiones; ejecutar las 65 omisiones de manifiesto en el Omen con plano de datos real | Delegable | Parcial | omisiones |
| 8 | Actualizar matriz de riesgos y matrices de rúbrica contra la candidata final; ensayar defensa de 20 min; confirmar fecha efectiva de entrega con el docente | Daniel | No | rúbricas |

Orden de impacto: 1, 2, 3, 6, 4. Nada de esto debe mezclarse con el endurecimiento F7 del worktree local del Omen.

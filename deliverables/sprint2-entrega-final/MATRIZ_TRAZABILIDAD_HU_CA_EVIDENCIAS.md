# Trazabilidad HU → CA → Código → Prueba → Evidencia — Sprint 2 / Hito 2

Candidato consolidado: `8010e4421cf91b80e6dc66d732ef6e98dfd1e4d8` (Base F7: `51ec3c06b67959d3daad6349c962a1be643906b4`) (Directiva 34; el commit que incorpora esta versión del documento es necesariamente posterior y se reporta en el entregable ejecutivo de esa directiva, no puede autorreferenciarse). Cubre las 14 historias
comprometidas (58 SP). Para las 9 DONE se muestra el amarre código↔prueba
representativo (no se reabrió investigación); para las 5 abiertas se detalla
el estado exacto por CA.

## Historias DONE (37 SP) — sin cambios de investigación respecto a Directiva 30/31

| HU | SP | CA clave | Código | Prueba | Resultado |
|---|---:|---|---|---|---|
| SAPI-55 | 5 | Freeze científico F1-F9 | `scripts/freeze_check.py` | Ejecución directa | PASS salvo excepciones explicadas (ver §gate) |
| SAPI-56 | 5 | Harness CI/CD unificado | `scripts/merge_gate.py` | `--job all` × 3 esta sesión | Evidencia en `/c/sapi-gate/d11428a6165d/` |
| SAPI-57 | 5 | `/predict` síncrono, 50 celdas, fingerprint | `services/ml_api/main.py` | `container-smoke-ml` | PASS, fingerprint exacto `33c2eacc...` |
| SAPI-58 | 5 | Migraciones V001-V003 | `db/migration/` | `sql-migration-validation`, `flyway-integration` | PASS real con Postgres/Flyway reales |
| SAPI-59 | 5 | Persistencia write-through, idempotencia | `services/backend/.../RankingPersistenceServiceTests.java` | Maven surefire | PASS, 162 tests |
| SAPI-60 | 3 | Orquestación Docker Compose v2 | `docker-compose.yml` | `container-smoke` | PASS |
| SAPI-61 | 3 | Streamlit consume REST | `app/components/ranking_backend_view.py` | `tests/test_ranking_backend_view.py` | PASS (job `python`) |
| SAPI-62 | 3 | Visualización espacial Folium/Pydeck | `app/utils/reference_topography.py` | Incluido en job `python` | PASS |
| SAPI-64 | 3 | Marco de testing E2E | `services/backend/src/test/` | Surefire + Testcontainers | PASS |

## Historias abiertas (21 SP) — estado exacto por CA

### SAPI-66 — Vertical slice E2E (5 SP)

| CA | Código/artefacto | Prueba | Estado |
|---|---|---|---|
| CA1 Orquestación v2 | `docker-compose.yml` | `container-smoke` | **PASS** |
| CA2 Integración Spring+FastAPI | `services/backend/.../RankingServiceTests.java` | Surefire | **PASS** |
| CA3 Persistencia PostGIS correlacionada | `bootstrap_compose_v2.py::verify_database_persistence_correlated` | 6 casos RED/GREEN | **PASS** |
| CA4 Rendimiento navegador real | `scripts/measure_browser_e2e_d21.py` | Selenium/Edge real + prueba negativa | **PASS**, 1709.5 ms |
| CA5 (literal) `docker-compose up` sin config | — | Ejecución directa | **FALLA tal como escrito**; alternativa (`bootstrap_compose_v2.py`) aprobada por el PO (Jira `#10156`) |
| Dependencia SAPI-43/71 (datos reales en vivo) | `src/refresh/` | 139 tests con fixtures sintéticas | **No ejecutado con datos reales** — pendiente de autorización humana |

### SAPI-43 — Pipeline diario (5 SP)

| CA | Código | Prueba | Estado |
|---|---|---|---|
| Atomicidad/locks/redacción | `src/refresh/atomic.py`, `lock.py`, `redact.py` | `test_refresh_primitives.py`, `test_refresh_adversarial.py` | **PASS real**, 139/140 (1 skipped) |
| Refresco con datos DMC/FIRMS reales | `src/refresh/dmc_refresh.py`, `firms_refresh.py` | Runbook `docs/ops/FIRST-CONTROLLED-REFRESH.md` | **No ejecutado** — requiere autorización + credenciales (Jira `#10160`) |

### SAPI-49 — Spike CONAF (3 SP)

| CA | Artefacto | Verificación | Estado |
|---|---|---|---|
| Fuentes, cobertura, acceso, limitaciones, recomendación | `docs/spikes/SAPI-49-CONAF-historical-source.md` | Lectura verificada línea por línea | **Cumple el estándar**, recomendado DONE (Jira `#10159`) |

### SAPI-63 — Dataset de secuencias temporales (5 SP)

| CA | Artefacto | Verificación | Estado |
|---|---|---|---|
| Ventanas causales, walk-forward sin leakage, shape, distribución, conclusión | `experiments/sapi63/temporal_sequences.py`, `notebooks/sapi63_lstm_viability.py` | **Reproducido de forma independiente** contra el dataset real externo | **Cumple**, recomendado DONE científico (Jira `#10158`) |

### SAPI-67 — ADR Cloud Provider (3 SP)

| CA | Artefacto | Verificación | Estado |
|---|---|---|---|
| Comparación ≥3 proveedores con criterios | `docs/adr/ADR-011-cloud-provider.md` | Lectura verificada, 9 criterios, fuentes citadas | **Cumple** |
| ADR firmado con decisión final | `docs/adr/ADR-011-cloud-provider.md` §Estado | — | **No cumple** — Propuesto, sin firma (Jira `#10157`) |

## Resumen cuantitativo

- 37/58 SP (63.8%) formalmente DONE con trazabilidad código↔prueba completa.
- 21/58 SP (36.2%) en 5 historias, con 8 de 11 CA individuales cumplidos y
  evidencia real; los 3 CA no cumplidos (CA5 literal de SAPI-66, refresco
  real de SAPI-43, firma de SAPI-67) están identificados sin maquillaje.

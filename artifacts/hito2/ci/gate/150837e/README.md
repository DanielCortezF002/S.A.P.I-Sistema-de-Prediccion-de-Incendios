# Merge gate en la nube (fallback) — SHA `150837e` (SAPI-60, PR-4)

| Campo | Valor |
|---|---|
| Comando | `python scripts/merge_gate.py --job freeze --job python --job backend-unit --job sql-migration-validation --job flyway-integration --fresh-clone` sobre un clon limpio de `150837ed2b98b1bcd1e87492def1bc5c614337b4` (rama `feat/SAPI-60-docker-compose-v2`) |
| Entorno | Sandbox Linux, Python 3.14.6, OpenJDK 21, **Docker 29.8.2 disponible**, PowerShell 7.4.6 en el PATH; sin `SAPI_IT_ML_BASE_URL` |
| Fecha | 2026-10-10, 15:48–15:53 UTC |
| Veredicto | **GATE PASS** |

| Job | Resultado | Detalle |
|---|---|---|
| `freeze` | PASS | F1–F9 en modo gate, sin SKIP; fingerprint del Modelo D `33c2eacc…` |
| `python` | PASS | Lint v2 limpio (incluye `scripts/compose_v2_preflight.py` y `tests/test_compose_v2.py`); pytest 1744 passed, 114 skipped, cobertura 84,54 % |
| `backend-unit` | PASS | `mvnw -B verify -DskipITs`: 127 tests, 0 fallas, 4 omitidos (los opt-in contra el ML real) |
| `sql-migration-validation` | PASS | psql sobre PostGIS desechable (`scripts/w0_host_checks.ps1`), ejecutado de verdad en el sandbox |
| `flyway-integration` | PASS | Flyway CLI 12.4.0 contra PostGIS limpio, ejecutado de verdad en el sandbox. La imagen `flyway/flyway:12.4.0` se bajó desde `mirror.gcr.io` (mismo digest) por el límite de pulls de Docker Hub |
| `container-smoke` | No ejecutado | Construye `Dockerfile.ml-api`, que el sandbox no puede construir (egress bloquea los mirrors de Debian). Su evidencia de host (`7618cce`) está CADUCA (`docker_evidence_validity.txt`). **Pendiente en el host** |

Los ITs de failsafe (`RankingPersistenceIT`, 11/11 con Testcontainers) y el
preflight del Compose (27/27) no son jobs del gate. Su evidencia está en
`artifacts/hito2/testing/sapi-60/`.

## Saneamiento

Mismo criterio que la evidencia de W1:
- rutas reemplazadas por marcadores (`[gate-out]`, `[scratch]`, `[repo]`, `[home]`, `[venv]`);
- sin las líneas de opciones de la JVM;
- sin bloques `<properties>` de surefire;
- el `hostname`, `host` y `machine` del sandbox se reemplazan por `[host]`.

Como `machine` cambió, los `manifest.sha256` de `flyway-integration/` y de
`sql-migration-validation/` se recalcularon sobre los archivos saneados.

Es un commit solo de evidencia: hereda el gate de `150837e`.

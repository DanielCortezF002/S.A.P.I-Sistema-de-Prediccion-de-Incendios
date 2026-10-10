# Merge gate en la nube (fallback) — SHA `569c898` (SAPI-57, PR-2)

| Campo | Valor |
|---|---|
| Comando | `python scripts/merge_gate.py --job all --fresh-clone` sobre un clon limpio de `569c8988ed648d7185a98d70fc123715f2eab5fd`, rama `feat/SAPI-57-ranking-ml-client` |
| Entorno | Sandbox Linux, Python 3.14.6, OpenJDK 21.0.12.1, sin Docker. Se pasó la ruta de PowerShell 7.4.6 para los tests del harness; sin `SAPI_IT_ML_BASE_URL` |
| Fecha | 2026-10-10, 01:22–01:27 UTC |

| Job | Resultado | Detalle |
|---|---|---|
| `freeze` | PASS | F1–F9 en modo gate, sin SKIP; fingerprint del Modelo D `33c2eacc…` |
| `python` | PASS | Lint v2 limpio; pytest 1720 passed, 114 skipped, cobertura 84,56 % |
| `backend-unit` | PASS | `mvnw -B verify -DskipITs`: 118 tests, 0 fallas, 4 omitidos (los opt-in contra el ML real; ver `../../../testing/sapi-57/`) |
| jobs con Docker | NOT_VERIFIABLE_IN_THIS_ENVIRONMENT | Ver la tabla de validez |

Dentro de `python`, ningún test omitido en `test_w0_host_checks_evidence` (7), `test_w0_host_checks` (20), `test_merge_gate` (26), `test_openapi_contracts` (13) ni `test_architecture` (3).

**Validez de la evidencia Docker** (`docker_evidence_validity.txt`)

| Job | Evidencia de host | Estado |
|---|---|---|
| `flyway-integration` | `artifacts/hito2/w0/host/7618cce/` | VIGENTE |
| `sql-migration-validation` | `artifacts/hito2/w0/host/43c17fd/` | VIGENTE |
| `container-smoke` | `artifacts/hito2/w0/host/7618cce/` | CADUCA: cambió `services/` |

Que `container-smoke` caduque no bloquea este PR: la Revisión 3 §3.1 exige para PR-2 solo `freeze`, `python` y `backend-unit`. Queda pendiente una nueva corrida en el host antes de los PR que lo exigen (PR-1 y PR-4).

**Saneamiento.** Este es el criterio de evidencia nueva vigente desde W1:
- las rutas locales se reemplazan por marcadores entre corchetes (`[fresh-clone]`, `[gate-out]`, `[venv]`, `[m2]`, `[home]`);
- se quitan las líneas que imprimen las opciones de la JVM del sandbox (proxy);
- se elimina el bloque `<properties>` de los XML de surefire (usuario, home y proxy);
- el `hostname` de junit se reemplaza por `[host]`.

Es un commit solo de evidencia: hereda el gate de `569c898`.

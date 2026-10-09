# Merge gate en la nube (fallback) — SHA `ec65008` (registro de las decisiones G9)

Corrida de `python scripts/merge_gate.py --job all --fresh-clone` sobre un clon
limpio de `ec65008ad71ee3fd82bedb1f2e70620e19dc2b75`, HEAD de
`chore/hito2-w0-gate`. Sandbox: Linux, Python 3.14.6, OpenJDK 21, sin Docker;
`SAPI_PWSH=[pwsh-7.4.6]` para ejecutar los tests que usan PowerShell.
2026-10-09, 14:46–14:51 UTC.

**Por qué se re-ejecuta.** Respecto de `7618cce`, este commit solo cambia
`docs/hito2/decisiones-w0.md`. Antes de CODE FREEZE, `docs/hito2/` no hereda el
gate: `merge_gate.py --inherit 7618cce` da `INHERIT FAIL`
(`inherit_from_7618cce.txt`). Por eso se corre el gate completo sobre este SHA.

| Job | Resultado | Detalle |
|---|---|---|
| `freeze` | PASS | F1–F9 en modo gate, sin SKIP; fingerprint del Modelo D `33c2eacc…` |
| `python` | PASS | lint v2 limpio; pytest 1720 passed, 114 skipped, cobertura 84,56 %. `test_w0_host_checks_evidence` 7/7, `test_w0_host_checks` 20/20, `test_merge_gate` 26/26 y `test_openapi_contracts` 13/13, ninguno skipped |
| `backend-unit` | PASS | `mvnw -B verify -DskipITs`: 3 tests, BUILD SUCCESS |
| jobs con Docker | NOT_VERIFIABLE_IN_THIS_ENVIRONMENT | Cubiertos por la evidencia de host vigente (abajo) |

**Validez de la evidencia Docker para `ec65008`** (`docker_evidence_validity.txt`):

| Job | Evidencia | Resultado |
|---|---|---|
| `container-smoke` | `../../host/7618cce/` | VIGENTE |
| `flyway-integration` | `../../host/7618cce/` | VIGENTE |
| `sql-migration-validation` | `../../host/43c17fd/` | VIGENTE |

El veredicto agregado de `gate_summary.json` es
`NOT_VERIFIABLE_IN_THIS_ENVIRONMENT` (exit 2) solo porque los 3 jobs con Docker
no corren en la nube.

Las rutas locales se reemplazaron por marcadores entre corchetes (`[gate-out]`,
`[fresh-clone]`, `[venv]`, `[scratch]`, `[pwsh-7.4.6]`). Es un commit solo de
evidencia: hereda el gate de `ec65008`.

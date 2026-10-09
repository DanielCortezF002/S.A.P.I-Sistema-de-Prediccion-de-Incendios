# Merge gate en la nube (fallback) — SHA `df29550` (fix del checker de Flyway)

Corrida de `python scripts/merge_gate.py --job all --fresh-clone` sobre un clon
limpio de `df295500ad9fe6f431aa3f7f5d6b05a64d43b4e1` (`chore/hito2-w0-gate`).
Sandbox: Linux, Python 3.14.6, OpenJDK 21, sin Docker. Se usó
`SAPI_PWSH=<pwsh-7.4.6>` (PowerShell 7.4.6 local, no en PATH) para que los tests
de comportamiento del checker se ejecutaran dentro de `pytest`. 2026-10-09,
00:31–00:35 UTC.

| Job | Resultado | Detalle |
|---|---|---|
| `freeze` | PASS | F1–F9 en modo gate (sin SKIP), con fingerprint del Modelo D `33c2eacc…` |
| `python` | PASS | lint v2 limpio; pytest 1712 passed, 114 skipped, cobertura 84,56 %. Incluye los 19 tests de `tests/test_w0_host_checks.py` ejecutados (0 skipped) |
| `backend-unit` | PASS | `mvnw -B verify -DskipITs`: 3 tests, BUILD SUCCESS |
| `sql-migration-validation`, `flyway-integration`, `container-smoke` | NOT_VERIFIABLE_IN_THIS_ENVIRONMENT | Requieren Docker → re-run en Windows/Omen sobre este mismo SHA |

Rutas locales reemplazadas por marcadores. Commit solo de evidencia: hereda el
gate de `df29550`.

# Merge gate en la nube (fallback) — SHA `6f0fde6` (SHA final de W0.9)

Corrida de `python scripts/merge_gate.py --job all --fresh-clone` sobre un clon
limpio de `6f0fde6b2a38e707c1c41ab6f39dcf7b1472923e` (rama
`chore/hito2-w0-gate`), en el sandbox de Claude Code: Linux, Python 3.14.6 y
OpenJDK 21, **sin Docker ni PowerShell**. GitHub Actions no estaba disponible,
así que este es el FALLBACK GATE (Revisión 3 §3.1). 2026-10-08, 23:11–23:16 UTC.

| Job | Resultado | Detalle |
|---|---|---|
| `freeze` | PASS | F1–F9 en modo gate (sin SKIP), con fingerprint del Modelo D `33c2eacc…` |
| `python` | PASS | lint v2 limpio; pytest 1693 passed, 114 skipped, cobertura 84,56 %; deuda legacy de flake8 = 231 (informativa) |
| `backend-unit` | PASS | `mvnw -B verify -DskipITs`: 3 tests, BUILD SUCCESS |
| `sql-migration-validation` | NOT_VERIFIABLE_IN_THIS_ENVIRONMENT | Requiere Docker → bloque Windows/Omen |
| `flyway-integration` | NOT_VERIFIABLE_IN_THIS_ENVIRONMENT | Requiere Docker → bloque Windows/Omen |
| `container-smoke` | NOT_VERIFIABLE_IN_THIS_ENVIRONMENT | Requiere Docker → bloque Windows/Omen |

Esto cubre G1/G2 del W1 ENTRY GATE para este SHA. Los jobs Docker (G3–G6) se
cierran con la evidencia del host, que se versiona en `artifacts/hito2/w0/host/`.
Las rutas locales se reemplazaron por los marcadores `<gate-out>`,
`<fresh-clone>`, `<venv>` y `<scratch>`. Este commit solo toca `artifacts/hito2/**`
y hereda el gate de `6f0fde6`.

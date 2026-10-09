# Merge gate en la nube (fallback) — SHA `7618cce` (fix de la escritura de evidencia)

Corrida de `python scripts/merge_gate.py --job all --fresh-clone` sobre un clon
limpio de `7618cce00123ac0b3f0c18e2ba8ec6778f19059a` (commit de la rama
`chore/hito2-w0-gate`; el resumen dice `branch: HEAD` porque se lanzó con ese SHA
en modo detached). Sandbox: Linux, Python 3.14.6, OpenJDK 21, sin Docker;
`SAPI_PWSH=[pwsh-7.4.6]` para ejecutar los tests que usan PowerShell.
2026-10-09, 04:38–04:42 UTC.

| Job | Resultado | Detalle |
|---|---|---|
| `freeze` | PASS | F1–F9 en modo gate (sin SKIP), con fingerprint del Modelo D `33c2eacc…` |
| `python` | PASS | lint v2 limpio; pytest 1720 passed, 114 skipped, cobertura 84,56 %. Incluye `test_w0_host_checks_evidence` 7/7, `test_w0_host_checks` 20/20 y `test_merge_gate` 26/26, ninguno skipped |
| `backend-unit` | PASS | `mvnw -B verify -DskipITs`: 3 tests, BUILD SUCCESS |
| jobs con Docker | NOT_VERIFIABLE_IN_THIS_ENVIRONMENT | Se cubren con el re-run en Windows/Omen sobre este mismo SHA |

Rutas locales reemplazadas por marcadores. Commit solo de evidencia: hereda el
gate de `7618cce`.

**Corrección de saneamiento (2026-10-09):** la primera versión de esta carpeta reemplazó las rutas
locales por marcadores con `<...>`, lo que dejaba los XML (junit/surefire) mal formados. Se regeneraron
todos los archivos desde las salidas originales del gate con marcadores entre corchetes (`[gate-out]`,
`[fresh-clone]`, `[venv]`, `[scratch]`, `[pwsh-7.4.6]`); el contenido no cambió.

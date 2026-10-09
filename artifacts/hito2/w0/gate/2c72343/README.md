# Merge gate en la nube (fallback) — SHA `2c72343`

Corrida de `python scripts/merge_gate.py --job all --fresh-clone` sobre un clon
limpio del SHA `2c72343184f28cd614e7b60d6c1275b9f8c8971b` (rama
`chore/hito2-w0-gate`), en el sandbox de Claude Code: Linux, Python 3.14.6 y
OpenJDK 21, **sin Docker ni PowerShell**. GitHub Actions no estaba disponible
(0 runs), por lo que este es el FALLBACK GATE de la Revisión 3 §3.1.
2026-10-08, 23:04–23:09 UTC.

| Job | Resultado | Detalle |
|---|---|---|
| `freeze` | PASS | F1–F9 en modo gate (ningún SKIP), con fingerprint del Modelo D `33c2eacc…` |
| `python` | PASS | lint v2 limpio; pytest 1692 passed, 114 skipped, cobertura 84,56 % (≥ 80 %); deuda legacy de flake8 = 231 (informativa) |
| `backend-unit` | PASS | `mvnw -B verify -DskipITs`: 3 tests, BUILD SUCCESS |
| `sql-migration-validation` | NOT_VERIFIABLE_IN_THIS_ENVIRONMENT | Requiere Docker → Windows/Omen (o Actions) |
| `flyway-integration` | NOT_VERIFIABLE_IN_THIS_ENVIRONMENT | Requiere Docker → Windows/Omen (o Actions) |
| `container-smoke` | NOT_VERIFIABLE_IN_THIS_ENVIRONMENT | Requiere Docker → Windows/Omen (o Actions) |

Veredicto del runner: `NOT_VERIFIABLE_IN_THIS_ENVIRONMENT` (exit 2): ningún
FAIL; los jobs Docker se cierran con la evidencia del host
(`artifacts/hito2/w0/host/`). En el clon el `branch` figura como `HEAD`
porque el gate hace checkout del SHA exacto (detached).

Las rutas locales del sandbox se reemplazaron por `[gate-out]`,
`[fresh-clone]`, `[venv]` y `[scratch]`; ningún otro contenido fue editado.
Este commit solo toca `artifacts/hito2/**`, así que hereda el gate de
`2c72343` (`merge_gate.py --inherit 2c72343`).

**Nota (commit posterior):** el `.gitignore` del repo ignora `*.log`, por lo que
los 6 logs por job no entraron en el primer commit de evidencia. Se agregaron
renombrados `<job>.log` → `<job>.log.txt`, con el contenido sin cambios (salvo
el reemplazo de rutas descrito arriba). Desde el SHA siguiente, `merge_gate.py`
y `w0_host_checks.ps1` escriben los logs directamente como `.txt`.

**Corrección de saneamiento (2026-10-09):** la primera versión de esta carpeta reemplazó las rutas
locales por marcadores con `<...>`, lo que dejaba los XML (junit/surefire) mal formados. Se regeneraron
todos los archivos desde las salidas originales del gate con marcadores entre corchetes (`[gate-out]`,
`[fresh-clone]`, `[venv]`, `[scratch]`, `[pwsh-7.4.6]`); el contenido no cambió.

# S.A.P.I. — Estado del Sprint 2

Corte: **2026-10-08** (Quality Gate W0 en curso). Fuente: Jira (lectura) y el
repositorio en la rama `chore/hito2-w0-gate`. Este documento se actualiza al
cierre de cada ola; no reemplaza a Jira.

## Story points

| Grupo | SP comprometidos | SP terminados | Avance |
|---|---|---|---|
| Core | 47 | 17 | 36 % |
| Stretch (congelado) | 11 | 0 | — |

## Estado por HU

| HU | SP | Jira | Estado real en el repo | Criterios sin evidencia | Siguiente paso |
|---|---|---|---|---|---|
| SAPI-54 | 3 | Finalizado | `/health` y tests verdes (W0.3) | CA5 (Dockerfile) | W0.3 parte Docker (host) |
| SAPI-55 | 5 | Finalizado | `/health` y `/predict` con el modelo real; fingerprint `33c2…31ff` reproducido | CA8 (Dockerfile nunca construido) | W0.2 (host) |
| SAPI-56 | 3 | Finalizado | Contratos v0 versionados | Validación automática pendiente | W0.8 |
| SAPI-58 | 3 | Finalizado | V001–V003 y MER | CA3/CA5 sin log versionado | W0.4 (host) |
| SAPI-62 | 3 | Finalizado | Model card | CA4 parcial (reentrenamiento desde clon limpio no verificado) | — (limitación declarada) |
| SAPI-57 | 5 | Por hacer | No iniciado | Todos | W1, PR-2 |
| SAPI-59 | 5 | Por hacer | No iniciado | Todos | W1, PR-3 |
| SAPI-60 | 5 | Por hacer | No iniciado | Todos | W1, PR-4 |
| SAPI-61 | 5 | Por hacer | No iniciado | Todos | W1, PR-5 |
| SAPI-66 | 5 | Por hacer | No iniciado | Todos | W2, PR-6 |
| SAPI-43 | 5 | Por hacer | No iniciado; bloqueado para la corrida operacional por SAPI-71 | Todos | W2, PR-7 + decisión H9 |

## Quality Gate W0

Ver `artifacts/hito2/w0/` y el reporte de ejecución de W0. W1 no comienza sin
la autorización explícita de Daniel.

# Mapa a rúbrica — Matriz de riesgos e impedimentos (Hito 1 / Sprint 1)

Generado 07-09-2026. Niveles: `EXCELENTE_DEFENDIBLE` ·
`BUENO_DEFENDIBLE` · `SUFICIENTE_DEFENDIBLE` · `INSUFICIENTE_RISK`. No se
predice nota del profesor.

## Checklist de nivel máximo

| Comprobación | Resultado |
|---|---|
| Matriz completa | 23 riesgos identificados: 7 `RIESGO_HISTORICO_VERIFICADO` reutilizados de `docs/matriz-riesgo.md` (sin reescribirlos) + 13 `RIESGO_RECONSTRUIDO_EN_CIERRE` (técnicos/metodológicos, con fuente real citada) + 3 científicos históricos (auditoría 06-09-2026) |
| Priorización | Escala P×I definida y aplicada a los 23 riesgos (sección 3/5 de `docs/riesgos-hito1.md`) — etiquetada explícitamente como reconstrucción de cierre, no histórica |
| Probabilidad/impacto | Presente en las 23 filas de la matriz principal; para los 7 históricos, mapeo explícito desde la escala cualitativa original |
| Respuesta | Presente en las 23 filas (Corregir/Mitigar/Prevenir/Diferir/Transferir/Aceptar) |
| Responsable/acción | Presente en las 23 filas ("Equipo S.A.P.I.", único responsable verificable — no hay evidencia de roles diferenciados por riesgo en el repositorio) |
| Mitigaciones aplicadas | 12 de 23 con mitigación IMPLEMENTADA/VERIFICADA citando un test PASS concreto |
| Mitigaciones verificadas | Igual que arriba — ninguna se marcó VERIFICADA sin nombrar el test/commit/reporte exacto |
| Seguimiento | Tabla semanal (sección 7) construida contra S1-S6 como expectativa, con `NOT_FOUND`/`PARTIAL` donde no hay evidencia — no se fabricó ningún movimiento |
| Actualización semanal real | `WEEKLY_RISK_UPDATE_EVIDENCE: NOT_FOUND` — declarado explícitamente, no disimulado |

- **Nivel defendible hoy:** `BUENO_DEFENDIBLE`. No es
  `EXCELENTE_DEFENDIBLE` porque: (a) no existe evidencia de revisión
  semanal de riesgos real durante Sprint 1 (la rúbrica de Sprint 1 pide
  seguimiento hasta cierre/transferencia, y aquí el seguimiento se
  reconstruye al cierre, no se demuestra semana a semana); (b) 3 riesgos
  metodológicos (`R-HU-PIPELINE-01`, `R-ACEPT-EXT-01`,
  `R-SPRINT-MGMT-01`) no tienen mitigación verificable, solo un plan
  para Sprint 2; (c) el "Responsable" es uniformemente "Equipo S.A.P.I."
  sin evidencia de asignación individual por riesgo (esperable en un
  proyecto de una sola persona, pero la rúbrica pide el campo
  explícitamente).
- **Brecha:** las 3 anteriores, más la ausencia de una escala de
  priorización histórica (se define recién ahora).
- **Recuperable antes de presentación:** parcialmente. La escala y el
  seguimiento semanal formal solo pueden implementarse hacia adelante
  (Sprint 2), no retroactivamente para Sprint 1. `R-MANTEN-01` y
  `R-PERF-SEC-01` son recuperables con esfuerzo técnico bajo si se
  autoriza una fase de implementación. `R-HU-PIPELINE-01` y
  `R-ACEPT-EXT-01` requieren gestión real (Jira, sesión con evaluador),
  no solo documentación.
- **Fase que lo cerrará:** esta fase deja la matriz lista para revisión;
  el seguimiento semanal real y el cierre de los riesgos metodológicos
  dependen de Sprint 2 en adelante.

## Resumen sin puntaje inventado

| Categoría | Riesgos | Estado dominante |
|---|---|---|
| RIESGO_HISTORICO_VERIFICADO (de `matriz-riesgo.md`) | 7 | 3 MATERIALIZADO_Y_CORREGIDO, 1 MITIGADO (parcial), 2 TRANSFERIDO_A_SPRINT_2, 1 ABIERTO |
| RIESGO_RECONSTRUIDO_EN_CIERRE — técnico/dato | 10 (D-01..D-06 + legacy + frescura + mantenibilidad + rendimiento/seguridad) | 8 MATERIALIZADO_Y_CORREGIDO/MITIGADO (VERIFICADA), 2 ABIERTO/NO_RESUELTO |
| RIESGO_RECONSTRUIDO_EN_CIERRE — metodológico | 3 (HU pipeline, aceptación externa, gestión de Sprint) | 1 TRANSFERIDO_A_SPRINT_2, 1 ABIERTO, 1 NO_RESUELTO |
| Científico (histórico, auditoría 06-09-2026) | 3 (agrupando 4 hallazgos científicos en 3 filas) | ACEPTADO (limitación explícita, no defecto) |

**Total de riesgos identificados en la matriz principal: 23** (7 + 8 + 3
+ 3, con R-CIENT-* representando 3 filas para 4 limitaciones científicas
distintas — FIRMS≠confirmado se documenta dentro de
R-CIENT-GENERALIZACION-01, no como fila propia, para no inflar el
conteo con una reformulación del mismo límite de alcance).

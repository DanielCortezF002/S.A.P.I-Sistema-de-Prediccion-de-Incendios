# Cierre metodológico de Sprint 1 — Hito 1

**Estado:** documento CANÓNICO de cierre. Consolida, sin reabrir,
`docs/arquitectura-hito1.md`, `docs/testing-evidencia-hito1.md`,
`docs/trazabilidad-hito1.md`, `docs/atributos-calidad-hito1.md`,
`docs/riesgos-hito1.md`, `docs/versionamiento-hito1.md` y
`docs/calidad-codigo-hito1.md`. Fecha de esta fase: **07-09-2026**.

**Convención de etiquetado usada en todo el documento:**
`EVIDENCIA_HISTORICA_VERIFICADA` (registro real, fechado, anterior a
esta fase) · `EVIDENCIA_ACTUAL_DE_CIERRE` (verificación técnica hecha
hoy, 07-09-2026, sobre el estado actual) · `RECONSTRUCCION_RETROSPECTIVA`
(interpretación/síntesis hecha hoy sobre hechos pasados, nunca
presentada como si hubiera existido antes) · `NOT_FOUND` (buscado
explícitamente, sin resultado). Ninguna reconstrucción del 07-09-2026 se
presenta como evidencia histórica del 31-08-2026.

## 1. Propósito

Cerrar metodológicamente Sprint 1 de forma honesta y defendible frente a
la rúbrica de Hito 1 y de Sprint 1, consolidando lo ya auditado en las
siete fases previas — sin inventar Sprint Goal, DoD, actas, reuniones,
aceptación externa, snapshot inicial ni velocidad.

## 2. Alcance y fechas

| Fecha | Evento | Tipo |
|---|---|---|
| `PLANNED_CLOSE_DATE` = 31-08-2026 | Cierre planificado de Sprint 1 (fecha académica) | Referencia de calendario |
| 31-08-2026 | Tag anotado `v1.0.0-sprint1-verified`, tagger date propio | `EVIDENCIA_HISTORICA_VERIFICADA` (`docs/versionamiento-hito1.md`, sección 6.1) |
| 01-09 a 05-09-2026 | Avance de SAPI-30/32, hallazgo y cierre de R-GRILLA-01, sesión de usabilidad móvil (autoevaluación) | `EVIDENCIA_HISTORICA_VERIFICADA` |
| 06-09 a 07-09-2026 | Construcción y congelamiento del pipeline temporal nuevo; 7 fases de auditoría de Hito 1 (arquitectura→cierre) | `EVIDENCIA_ACTUAL_DE_CIERRE` |
| `HITO_REVIEW_DATE` = 07-09-2026 | Fecha de este documento y del Hito 1 | — |

El tag `v1.0.0-sprint1-verified` es evidencia real de **versionamiento**
al 31-08-2026 — no se interpreta como prueba de que todas las
ceremonias Scrum (Sprint Goal, Review, retrospectiva) ocurrieron esa
fecha; esas ceremonias se auditan por separado en las secciones 3, 11 y
13.

## 3. Sprint Goal

Búsqueda exhaustiva repetida en esta fase (sin resultados, consistente
con las fases de Testing y Trazabilidad):

**HISTORICAL_SPRINT_GOAL: NOT_FOUND.**

**RECONSTRUCCION_RETROSPECTIVA_DEL_OBJETIVO — 07/09/2026** (no es un
Sprint Goal acordado; es una síntesis de lo que el trabajo verificable
del Sprint efectivamente persiguió, formulada hoy):

> Consolidar la ingesta real de datos (NASA FIRMS, DMC), un primer
> puente verificable entre ignición, meteorología y celda sobre un
> evento histórico real, la separación explícita entre demostración y
> datos reales en el dashboard, y un gate de calidad de tests ≥80% —
> como base para, posteriormente, auditar y reconstruir un pipeline
> temporal metodológicamente honesto.

## 4. Backlog y estado de HU

Fuente de story points y estado actual: export externo `Jira (4).doc`
(citado en `docs/trazabilidad-hito1.md`, sección 11) —
**EVIDENCIA_ACTUAL_DE_CIERRE**, no un snapshot del 31-08-2026.

| ID | Resumen | SP | Estado actual (Jira) | Fecha de resolución | Estado técnico | Observación de Sprint |
|---|---|---|---|---|---|---|
| SAPI-26 | Histórico NASA FIRMS | 8 | En curso | — (no finalizado) | Cerrado lado NASA; CONAF sin fuente real | **No finalizado — CONAF pendiente** |
| SAPI-28 | Telemetría DMC↔ignición | 8 | Finalizado | **07-09-2026** | Parcial (join real feb-2025) | Resuelta **después** del cierre planificado (31-08) |
| SAPI-30 | Topografía DEM | 5 | Finalizado | **07-09-2026** | Avanzado, integrado al prototipo real | Resuelta **después** del cierre planificado |
| SAPI-32 | Limpieza/integración | 5 | Por hacer | — (no finalizado) | Sub-tarea limpieza cerrada; integración a producción pendiente | **No finalizado — integración pendiente (R-INTEGRACION-01)** |
| SAPI-33 | Gestión/documentación | — | Finalizado | No documentada | Manual, sin evidencia de código | — |
| SAPI-44 | Separación demo/real | 2 | Finalizado | 31-08-2026 (histórico) | Cerrado, 13/13 tests | Dentro de ventana planificada |
| SAPI-45 | Gate cobertura ≥80% | 3 | Finalizado | 31-08-2026 (histórico) | Cerrado, 80.34%→91.72% | Dentro de ventana planificada |
| SAPI-46 | Gestión/documentación | — | Finalizado | No documentada | Manual, sin evidencia de código | — |
| SAPI-47 | Matriz de riesgo | 1 | Finalizado | No documentada | `docs/matriz-riesgo.md` real | — |
| SAPI-48 | Trazabilidad HU↔prueba | 2 | Finalizado | No documentada | `docs/matriz-trazabilidad-hu-test.md` real | — |

**No se infiere el estado al 31-08-2026 para SAPI-28/30 porque no
existe un snapshot tomado esa fecha** — solo se sabe que se resolvieron
después, el 07-09-2026 (posterior al cierre planificado).

## 5. Criterios de aceptación

**HISTORICAL_CA: PARTIAL.** CA históricos reales, resumidos en
`docs/matriz-trazabilidad-hu-test.md`, existen para SAPI-26/28/30/32/44/45
(`CA_HISTORICO`); SAPI-33/46 sin CA documentado (`CA_NO_ENCONTRADO`);
SAPI-47/48 con CA implícito (`CA_PARCIAL`).

**CURRENT_TECHNICAL_AC: VERIFIED.** Los 10 criterios técnicos
`AC-T01..AC-T10` (`artifacts/hito1/testing/acceptance-checks.txt`) son
**criterios técnicos de verificación del cierre — 07/09/2026**,
construidos y verificados hoy contra el pipeline temporal — **nunca se
presentan como los CA pactados al inicio de Sprint 1**, porque ese
pipeline no existía como HU de Sprint 1.

## 6. Definition of Done

**HISTORICAL_DOD: NOT_FOUND** (búsqueda exhaustiva repetida, sin
resultados en el repositorio).

**DOD_PROPUESTO_PARA_SPRINT_2** (completamente separado de la evidencia
de Sprint 1 — es una propuesta hacia adelante, no una reconstrucción):

- Código con la suite de tests en verde antes de mergear a `main`.
- Cobertura de código no decrece respecto al commit anterior.
- Ningún import prohibido por el Data Contract (`test_architecture.py`
  en verde).
- CA definido y documentado en Jira **antes** de empezar a implementar
  la HU.
- Commit(s) de la HU referencian su ticket Jira explícitamente.
- Evidencia técnica (test/reporte/artefacto) citada en el ticket al
  moverlo a Done.

## 7. Seguimiento semanal

Comparando la planificación S1-S6 (recibida como expectativa, no como
prueba de que ocurrió) contra la evidencia real:

| Semana | Actividad esperada | Evidencia encontrada | Estado |
|---|---|---|---|
| 1-2 | Arranque, ingesta inicial | Commits 20-06-2026 (pipeline legacy, tags v1.0.0-data..v3.2.0-demo-professional) | PARTIAL (evidencia técnica sí, reunión formal no) |
| 3 | Plan de pruebas + primeras ejecuciones | Sin commits verificables en julio (brecha de 53 días, `docs/versionamiento-hito1.md` sección 3.1) | NOT_FOUND |
| 4 | Resultados unitarios/integración | Corrección de endpoints reales + expansión de suite a gate 80% (28-31/08) | PARTIAL |
| 5 | Aceptación con usuario | `docs/acta-pruebas-aceptacion-usuario.md` (01/05-09) — autoevaluación, no usuario externo | PARTIAL |
| 6 | Cierre e integridad del pipeline | Auditoría del pipeline temporal (06/07-09-2026) | PARTIAL — real, pero fuera de la ventana "semana 6" sin calendario que lo confirme |

**WEEKLY_MEETING_EVIDENCE: NOT_FOUND.** No existe ningún registro de
reunión (acta, calendario, minuta) en el repositorio para ninguna
semana. No se fabrica ninguna.

## 8. Incremento técnico

Resumen (sin reabrir `docs/arquitectura-hito1.md`/`docs/testing-evidencia-hito1.md`):
pipeline temporal completo (meteorología regional, episodios, target
causal, Modelo D, `score_current_grid()`), congelado y auditado; 470/470
tests PASS, cobertura 91.72%; separación legacy/prototipo verificada por
test; tag `v1.1.0-corredor-verified` (05-09-2026) documentando la
corrección de la grilla real.

## 9. Testing y aceptación

- **Automatizada:** 470/470 PASS, AC-T01..AC-T10 verificados
  (`docs/testing-evidencia-hito1.md`).
- **Autoevaluación histórica:** `docs/acta-pruebas-aceptacion-usuario.md`
  — el propio desarrollador, sobre usabilidad móvil del dashboard demo,
  explícitamente etiquetada como tal en su origen.
- **Protocolo preparado, no ejecutado:**
  `artifacts/hito1/testing/acceptance-protocol.md`, con campos vacíos
  hasta que se ejecute una sesión real.
- **Aceptación externa real:** **EXTERNAL_ACCEPTANCE: NOT_FOUND** — no
  existe un evaluador distinto al desarrollador que haya aceptado o
  rechazado el incremento. No se fabrica firma, acta ni aprobación.

## 10. Riesgos e impedimentos

23 riesgos identificados y clasificados en `docs/riesgos-hito1.md`
(7 `EVIDENCIA_HISTORICA_VERIFICADA` de `docs/matriz-riesgo.md`, 13
`RECONSTRUCCION_RETROSPECTIVA` técnica/metodológica, 3 científicos
históricos) — no se reabre ni se recalcula aquí. Los más relevantes para
el cierre de Sprint: `R-CONAF-01` y `R-INTEGRACION-01`
(`TRANSFERIDO_A_SPRINT_2`), `R-HU-PIPELINE-01` (pipeline temporal sin HU
Jira), `R-SPRINT-MGMT-01` (Sprint Goal/DoD/Review/snapshot ausentes,
`NO_RESUELTO`, no recuperable retroactivamente).

## 11. Sprint Review

Búsqueda exhaustiva repetida: acta, registro, captura, comentario de
PO/stakeholder — sin resultados.

**FORMAL_SPRINT_REVIEW: NOT_FOUND.**

`docs/acta-pruebas-aceptacion-usuario.md` **no se presenta como Review
formal** — es una autoevaluación del desarrollador sobre un alcance
distinto (usabilidad móvil), tal como el propio documento lo aclara.

**REVISION_RETROSPECTIVA_DE_CIERRE — 07/09/2026** (sustituye, para
efectos de este documento, a una Review que no ocurrió — nunca se
backdatea al 31-08):

> Revisando el incremento real hoy: el pipeline temporal cumple los 10
> criterios técnicos AC-T01..T10; las 4 HU técnicas de Sprint 1 muestran
> avance real pero desigual (2 finalizadas 07-09, 2 no finalizadas); no
> existe evidencia de que un stakeholder externo haya visto o aprobado
> el incremento hasta la fecha de este documento.

## 12. Gestión de cambios

Cadenas hallazgo→análisis→decisión→cambio→backlog
(`artifacts/hito1/testing/defect-evidence.md`,
`docs/riesgos-hito1.md`):

| Cadena | Hallazgo→análisis→decisión→cambio | Elemento de backlog (Jira) | Estado |
|---|---|---|---|
| Meteo DMC posicional → regional | Completo, verificado (`reports/auditoria_integridad_datos.json`, `regional_meteo.py`) | No verificado | PARTIAL |
| `n_positive_rows` sobrecontaba | Completo (D-02) | No verificado | PARTIAL |
| Conflictos de backfill DMC | Completo (D-03) | No verificado | PARTIAL |
| Modelo legacy → Modelo D | Completo (`experiment_abcd.py`, Modelo D congelado) | No verificado | PARTIAL |
| CONAF pendiente | Completo hasta decisión (diferir a Sprint 2, `docs/matriz-riesgo.md`) | No verificado (sin ticket de seguimiento confirmado) | PARTIAL |

**CHANGE_MANAGEMENT: PARTIAL** en las 5 cadenas — ninguna llega a
`COMPLETE` porque el eslabón final (issue/backlog Jira verificado)
falta en todas. No se crea ningún ticket ahora para completarlas
artificialmente.

## 13. Retrospectiva actual

**RETROSPECTIVA_DE_CIERRE_HITO1 — 07/09/2026** (retrospectiva actual,
no una ceremonia efectuada el 31-08).

### Producto

| Qué funcionó | Qué no funcionó | Causa | Aprendizaje | Acción Sprint 2 | Criterio de verificación |
|---|---|---|---|---|---|
| Pipeline temporal con causalidad e integridad de datos verificadas por test | Pipeline temporal sin HU/Jira propia | Se construyó como auditoría metodológica, no como HU planificada | Un incremento técnico grande debería nacer con su HU, aunque sea "de investigación" | Crear HU real y vincular AC-T01..T10 | HU visible en Jira con AC-T enlazados |
| Separación demo/prototipo verificada automáticamente | CONAF e integración SAPI-32 siguen sin resolver | Decisión explícita de diferir, no descuido | Diferir con decisión documentada es mejor que forzar una integración apresurada | Resolver R-CONAF-01/R-INTEGRACION-01 | Tests + manifest reales para ambos |

### Proceso

| Qué funcionó | Qué no funcionó | Causa | Aprendizaje | Acción Sprint 2 | Criterio de verificación |
|---|---|---|---|---|---|
| Mensajes de commit descriptivos (FUERTE); tag anotado real de cierre | Sin Sprint Goal, DoD ni Sprint Review históricos | No se definieron/ejecutaron al inicio del Sprint | Estas ceremonias deben existir **antes**, no reconstruirse al cierre | Definir Sprint Goal + DoD el día 1 de Sprint 2 | Documento fechado al inicio de Sprint 2, no al cierre |
| Gate de cobertura ≥80% respetado y superado (91.72%) | Sin snapshot de compromiso inicial de SP; sin revisión semanal de riesgos | No se instrumentó el seguimiento | Sin snapshot inicial, la velocidad nunca es reconstruible | Tomar snapshot de SP el día 1; registrar riesgos semanalmente | Snapshot fechado + bitácora semanal verificable |

## 14. Acciones Sprint 2

| # | Acción | Responsable | Momento | Evidencia esperada | Criterio de cierre |
|---|---|---|---|---|---|
| 1 | Definir Sprint Goal antes de iniciar Sprint 2 | Equipo S.A.P.I. | Día 1 de Sprint 2 | Documento/ticket fechado al inicio | Sprint Goal legible, con fecha ≤ día 1 |
| 2 | Definir DoD antes del desarrollo | Equipo S.A.P.I. | Día 1 de Sprint 2 | Documento DoD fechado | DoD aplicado a la primera HU marcada Done |
| 3 | Capturar snapshot inicial del Sprint Backlog | Equipo S.A.P.I. | Día 1 de Sprint 2 | Export Jira fechado al inicio | Snapshot con SP totales por HU |
| 4 | Registrar revisión semanal de riesgos | Equipo S.A.P.I. | Cada semana de Sprint 2 | Bitácora fechada semana a semana | ≥1 entrada real por semana |
| 5 | Vincular pipeline temporal a HU Jira | Equipo S.A.P.I. | Inicio de Sprint 2 | HU creada + AC-T01..T10 enlazados | HU visible con evidencia técnica citada |
| 6 | Ejecutar sesión real con evaluador/usuario externo | Equipo S.A.P.I. | Durante Sprint 2 | `acceptance-protocol.md` completado con evaluador real | Campos de aceptación/rechazo llenos, con nombre/rol distinto al desarrollador |
| 7 | Completar integración CONAF (SAPI-26) | Equipo S.A.P.I. | Sprint 2 | Fuente real + parser + tests | SAPI-26 Finalizado con evidencia CONAF |
| 8 | Completar integración SAPI-32 a producción | Equipo S.A.P.I. | Sprint 2 | Puente conectado a `matriz_features` real | R-INTEGRACION-01 cerrado con evidencia |
| 9 | Mejorar trazabilidad commit↔Jira | Equipo S.A.P.I. | Continuo en Sprint 2 | Commits con `SAPI-xx` explícito | Tasa >50% (vs. 10.3% actual) |
| 10 | Definir responsables individuales por riesgo/HU | Equipo S.A.P.I. (si el equipo crece) | Inicio de Sprint 2 | Campo "responsable" con nombre real, no genérico | Cada riesgo/HU con responsable nombrado |

**No se crea ningún ticket Jira en esta fase** — las 10 acciones quedan
documentadas aquí como plan, no como backlog creado.

## 15. Conclusión del Sprint

Sprint 1 entrega un incremento técnico real y verificado (pipeline
temporal + 4 HU técnicas con avance desigual), con evidencia de
versionamiento sólida (tag anotado de cierre) y calidad técnica alta
(470/470, 91.72%). La disciplina de **gestión** de Sprint (Sprint Goal,
DoD, Sprint Review, snapshot inicial, revisión semanal de riesgos,
aceptación externa) **no tiene evidencia histórica** — esta es la
brecha central del cierre, no recuperable retroactivamente, y se
convierte en las 10 acciones de la sección 14 para Sprint 2.

## 16. Brechas no recuperables

1. `HISTORICAL_SPRINT_GOAL: NOT_FOUND` — no recuperable.
2. `HISTORICAL_DOD: NOT_FOUND` — no recuperable.
3. `FORMAL_SPRINT_REVIEW: NOT_FOUND` — no recuperable.
4. `EXTERNAL_ACCEPTANCE: NOT_FOUND` — no recuperable para Sprint 1
   (recuperable hacia adelante en Sprint 2).
5. `ORIGINAL_COMMITMENT_SNAPSHOT: NOT_FOUND` → `VELOCITY:
   NOT_RECONSTRUCTABLE` — no recuperable.
6. `WEEKLY_MEETING_EVIDENCE: NOT_FOUND` — no recuperable.
7. Cadenas de gestión de cambio sin eslabón final Jira (5/5 `PARTIAL`)
   — recuperable solo hacia adelante.
8. Pipeline temporal sin HU Jira (`TEMPORAL_PIPELINE_HU_LINK: GAP`,
   heredado) — recuperable en Sprint 2 (acción 5).

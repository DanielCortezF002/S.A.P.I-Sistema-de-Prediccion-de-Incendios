# Mapa de ubicación de rúbrica — SAPI_Hito1_Informe_Final.pdf (21 páginas)

Generado 07-09-2026 contra el PDF final ya verificado visualmente
(`visual-qa.md`, iteración 4, `CRITICAL_VISUAL_ISSUES: 0`). Paginación
actualizada tras recalcular el campo TOC con Word real (20 → 21
páginas; ver `visual-qa.md`, iteración 4, y `docx-build-log.md`).
"Cubrir" un criterio significa que el informe lo documenta con evidencia
real en la página indicada — **no** significa afirmar que el criterio
está cumplido. Para las brechas históricas, la página indicada es la
que documenta honestamente el `NOT_FOUND` correspondiente.

## Hito 1

| Criterio | Sección del DOCX | Página PDF | Evidencia | Estado |
|---|---|---|---|---|
| Asistencia (10%) | No cubierto en el cuerpo — fuera del alcance de un repositorio de código | — | `artifacts/hito1/traceability/rubric-master-map.md` (fase previa) | PENDIENTE (fuera de alcance) |
| Incremento + tablero (20%) | §4 Alcance del incremento; §9 Prototipo funcional | 4, 8 | Prototipo real descrito; tablero Jira referenciado en README, no verificado en vivo | PARCIAL |
| Arquitectura (12%) | §6 Arquitectura de la solución + Figuras 1-2; Anexo A | 5-6, 14 | Diagramas + tabla de componentes + límites | CUBIERTO |
| Testing (12%) | §10 Estrategia de pruebas y resultados; Anexo C | 8, 16 | 470/470, 91,72%, smoke 5/5, AC-T01-10 | CUBIERTO |
| Versionamiento (8%) | §14 Versionamiento y calidad de código; Anexo F | 9, 20 | Tags, partición de commits, tag anotado `v1.0.0-sprint1-verified` | CUBIERTO |
| Trazabilidad (10%) | §11 Trazabilidad; Anexo B | 8, 15 | Matriz HU/REQ; `TEMPORAL_PIPELINE_HU_LINK: GAP` explícito | PARCIAL (GAP declarado) |
| Atributos de calidad (10%) | §12 Atributos de calidad; Anexo D | 9, 17 | 10 atributos, 3 verificados/4 parciales/2 no verificados/1 no aplica | CUBIERTO |
| Calidad de código (8%) | §14 Versionamiento y calidad de código; Anexo F | 9, 20 | Modularidad, nomenclatura, manejo de errores, sin lint/type-check | CUBIERTO |
| Matriz de riesgo (10%) | §13 Riesgos e impedimentos; Anexo E | 9, 18 | 23 riesgos, control contable por estado | CUBIERTO |

## Sprint 1 (12 criterios)

| # | Criterio | Sección del DOCX | Página PDF | Evidencia | Estado |
|---|---|---|---|---|---|
| 1 | Sprint Goal | §15 Cierre metodológico; §16 Limitaciones | 10 | "No existe registro de un Sprint Goal acordado" | **NOT_FOUND documentado** |
| 2 | HU y refinamiento | §5 Requerimientos y Sprint 1; Anexo B | 4, 15 | 10 tickets Jira, SP 34/21/13, tabla de estado actual | PARCIAL (pipeline temporal sin HU) |
| 3 | Criterios de aceptación | §5; §11 Trazabilidad; Anexo B | 4, 8, 15 | CA históricos parciales + AC-T01-10 técnicos de cierre | PARCIAL |
| 4 | Sprint Backlog / Jira | §5 Requerimientos y Sprint 1 | 4 | 34 SP actuales / 21 Finalizados / 13 no Finalizados; `VELOCITY: NOT_RECONSTRUCTABLE` | PARCIAL |
| 5 | Definition of Done | §16 Limitaciones | 10 | "Sin Definition of Done definida antes del desarrollo" | **NOT_FOUND documentado** |
| 6 | Diseño 4+1 / equivalente | §6 Arquitectura de la solución; Anexo A | 5-6, 14 | Diagramas + componentes (formato no 4+1 canónico) | PARCIAL |
| 7 | Seguimiento / reuniones | §15 Cierre metodológico; §16 Limitaciones | 10 | "Sin evidencia de seguimiento/revisión semanal... ni de reuniones registradas" | **NOT_FOUND documentado** |
| 8 | Riesgos / impedimentos | §13 Riesgos e impedimentos; Anexo E | 9, 18 | 23 riesgos clasificados con estado actual | CUBIERTO |
| 9 | Pruebas / resultados / trazabilidad | §10, §11; Anexo B, C | 8, 15-16 | 470/470, AC-T01-10, matriz HU→CA→prueba→evidencia | CUBIERTO |
| 10 | Sprint Review / validación | §15 Cierre metodológico; §16 Limitaciones | 10 | "ni de una Sprint Review formal con participación externa" | **NOT_FOUND documentado** |
| 11 | Gestión de cambios | §13 Riesgos e impedimentos; §8 Implementación | 7, 9 | 6 defectos con hallazgo→decisión→cambio, sin eslabón Jira final | PARCIAL |
| 12 | Retrospectiva / cierre / mejora | §15 Cierre metodológico; §17 Trabajo pendiente / Sprint 2; Anexo G | 10, 11, 21 | Retrospectiva fechada 07-09-2026 + 10 acciones Sprint 2 con criterio de cierre | CUBIERTO (como reconstrucción actual, no histórica) |

## Cobertura total

**100% de los 9 criterios de Hito 1** y **12/12 criterios de Sprint 1**
tienen una ubicación real en el documento — 5 de los 12 criterios de
Sprint 1 (#1, #5, #7, #10, y parcialmente #2/3/4/6/11) llevan a una
sección que documenta honestamente una brecha `NOT_FOUND` o `PARCIAL`,
no a una sección que afirma cumplimiento. Esto es intencional y
coherente con el principio de honestidad temporal seguido en todo el
Hito — "cubrir" un criterio en este mapa nunca significa "aprobar" ese
criterio.

## Nota de versión

Este mapa referencia la versión de 21 páginas (post-actualización del
campo TOC con Word real, iteración 4 de `visual-qa.md`). La versión
previa de 20 páginas (generada solo con el pipeline LibreOffice del
proyecto) queda superada por esta.

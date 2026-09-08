# Mapa a rúbrica — Cierre de Sprint 1 (12 criterios)

Generado 07-09-2026. Niveles: `EXCELENTE_DEFENDIBLE` ·
`BUENO_DEFENDIBLE` · `SUFICIENTE_DEFENDIBLE` · `INSUFICIENTE_RISK`. No
se calcula nota total inventada.

## 1. Sprint Goal

- **Evidencia:** ninguna histórica. `RECONSTRUCCION_RETROSPECTIVA_DEL_OBJETIVO`
  formulada hoy (sección 3 de `docs/cierre-sprint1-hito1.md`).
- **Estado:** `HISTORICAL_SPRINT_GOAL: NOT_FOUND`.
- **Brecha:** no recuperable retroactivamente.
- **Nivel defendible:** `INSUFICIENTE_RISK`.

## 2. HU / refinamiento

- **Evidencia:** 10 tickets Jira verificables, con estado actual y
  fechas de resolución donde existen (SAPI-28/30, 07-09-2026); 4 HU
  técnicas con avance desigual (2 finalizadas, 2 no finalizadas).
- **Estado:** `BUENO_DEFENDIBLE` para las HU legacy; `GAP` para el
  pipeline temporal (sin HU propia).
- **Brecha:** vínculo HU del pipeline temporal.
- **Nivel defendible:** `BUENO_DEFENDIBLE`.

## 3. Criterios de aceptación

- **Evidencia:** CA históricos parciales (`HISTORICAL_CA: PARTIAL`);
  10 criterios técnicos de cierre (`AC-T01..T10`) verificados,
  correctamente no presentados como CA históricos.
- **Estado:** `PARTIAL` (histórico) + `VERIFIED` (técnico de cierre).
- **Brecha:** sin CA histórico para el incremento más reciente.
- **Nivel defendible:** `SUFICIENTE_DEFENDIBLE`.

## 4. Sprint Backlog / Jira

- **Evidencia:** snapshot actual verificado externamente (34 SP totales,
  21 Finalizados, 13 no finalizados) — sin snapshot de compromiso
  inicial.
- **Estado:** `ORIGINAL_COMMITMENT_SNAPSHOT: NOT_FOUND`, `VELOCITY:
  NOT_RECONSTRUCTABLE`.
- **Brecha:** sin punto de partida para medir compromiso vs. entrega.
- **Nivel defendible:** `SUFICIENTE_DEFENDIBLE` (hay snapshot actual
  real, pero no permite el análisis que la rúbrica probablemente espera).

## 5. Definition of Done

- **Evidencia:** ninguna histórica. `DOD_PROPUESTO_PARA_SPRINT_2`
  documentado, explícitamente separado de Sprint 1.
- **Estado:** `HISTORICAL_DOD: NOT_FOUND`.
- **Brecha:** no recuperable retroactivamente — la rúbrica exige DoD
  definido *antes* del desarrollo.
- **Nivel defendible:** `INSUFICIENTE_RISK`.

## 6. Diseño 4+1 / equivalente

- **Evidencia:** `docs/arquitectura.md` (contenedores/Data Contract/
  tablas) y `docs/arquitectura-hito1.md` (pipeline temporal) — contenido
  real, formato no canónico 4+1.
- **Estado:** heredado de la fase de Atributos de Calidad, sin cambios.
- **Brecha:** formato no 4+1 explícito.
- **Nivel defendible:** `SUFICIENTE_DEFENDIBLE`.

## 7. Seguimiento / reuniones

- **Evidencia:** ninguna acta o registro de reunión en el repositorio
  para ninguna de las 6 semanas.
- **Estado:** `WEEKLY_MEETING_EVIDENCE: NOT_FOUND`.
- **Brecha:** sin registro de seguimiento verificable, salvo evidencia
  técnica indirecta (commits) que no sustituye una reunión.
- **Nivel defendible:** `INSUFICIENTE_RISK`.

## 8. Riesgos / impedimentos

- **Evidencia:** 23 riesgos clasificados con probabilidad/impacto/
  exposición/prioridad/respuesta/evidencia (`docs/riesgos-hito1.md`).
- **Estado:** matriz completa; `WEEKLY_RISK_UPDATE_EVIDENCE: NOT_FOUND`.
- **Brecha:** sin revisión semanal real, escala de priorización
  reconstruida al cierre.
- **Nivel defendible:** `BUENO_DEFENDIBLE`.

## 9. Pruebas / resultados / trazabilidad

- **Evidencia:** 470/470 PASS, 91.72% cobertura, AC-T01..T10, matriz
  HU→CA→prueba→resultado→evidencia completa para 8 HU/tarea Jira.
- **Estado:** técnicamente sólido; `TEMPORAL_PIPELINE_HU_LINK: GAP`
  para el pipeline temporal.
- **Brecha:** cobertura de HU pendiente de vínculo Jira para el
  incremento más reciente.
- **Nivel defendible:** `BUENO_DEFENDIBLE`.

## 10. Sprint Review / validación

- **Evidencia:** ninguna Review formal; autoevaluación del desarrollador
  de alcance distinto; `REVISION_RETROSPECTIVA_DE_CIERRE` documentada
  hoy como sustituto no equivalente.
- **Estado:** `FORMAL_SPRINT_REVIEW: NOT_FOUND`, `EXTERNAL_ACCEPTANCE:
  NOT_FOUND`.
- **Brecha:** sin evaluador externo real en ningún punto del Sprint.
- **Nivel defendible:** `INSUFICIENTE_RISK`.

## 11. Gestión de cambios

- **Evidencia:** 5 cadenas hallazgo→análisis→decisión→cambio completas
  hasta el cambio técnico; ninguna con eslabón de backlog Jira
  verificado.
- **Estado:** `CHANGE_MANAGEMENT: PARTIAL` (5/5).
- **Brecha:** eslabón final (issue/backlog) ausente en todas.
- **Nivel defendible:** `SUFICIENTE_DEFENDIBLE`.

## 12. Retrospectiva / cierre / mejora

- **Evidencia:** ninguna retrospectiva histórica; `RETROSPECTIVA_DE_CIERRE_HITO1`
  documentada hoy (producto + proceso, con causa/aprendizaje/acción/
  criterio de verificación por punto), y 10 acciones concretas para
  Sprint 2.
- **Estado:** `RETROSPECTIVE_CLOSE_07SEP: DOCUMENTED`.
- **Brecha:** no hubo retrospectiva real al cierre de Sprint 1 — esta es
  una reconstrucción, declarada como tal.
- **Nivel defendible:** `SUFICIENTE_DEFENDIBLE` (la reconstrucción es
  seria y accionable, pero no sustituye a la ceremonia real).

## Resumen sin nota inventada

| # | Criterio | Nivel defendible |
|---|---|---|
| 1 | Sprint Goal | INSUFICIENTE_RISK |
| 2 | HU/refinamiento | BUENO_DEFENDIBLE |
| 3 | Criterios de aceptación | SUFICIENTE_DEFENDIBLE |
| 4 | Sprint Backlog/Jira | SUFICIENTE_DEFENDIBLE |
| 5 | Definition of Done | INSUFICIENTE_RISK |
| 6 | Diseño 4+1/equivalente | SUFICIENTE_DEFENDIBLE |
| 7 | Seguimiento/reuniones | INSUFICIENTE_RISK |
| 8 | Riesgos/impedimentos | BUENO_DEFENDIBLE |
| 9 | Pruebas/resultados/trazabilidad | BUENO_DEFENDIBLE |
| 10 | Sprint Review/validación | INSUFICIENTE_RISK |
| 11 | Gestión de cambios | SUFICIENTE_DEFENDIBLE |
| 12 | Retrospectiva/cierre/mejora | SUFICIENTE_DEFENDIBLE |

**Patrón honesto observado:** los criterios de **evidencia técnica**
(HU, riesgos, testing/trazabilidad) están en `BUENO_DEFENDIBLE`; los
criterios de **ceremonia/gestión de Scrum** (Sprint Goal, DoD,
seguimiento, Review) están en `INSUFICIENTE_RISK` porque no tienen
evidencia histórica y no son recuperables retroactivamente — no se
disimula esta asimetría promediándola.

# Change Log — post-Hito 1

Registro de decisiones de gestión posteriores al cierre de Hito 1
(31-08-2026 planificado; evaluación 07-09-2026). Cada entrada es actual,
fechada en el momento real en que se tomó la decisión — ninguna reconstruye
ni presenta una decisión de Sprint 1 que no existió.

---

## CR-001 — Vinculación HU Jira de REQ-10..REQ-16 (pipeline temporal)

**Fecha:** 09-09-2026.

**Origen:** Auditoría de Hito 1 / brecha de trazabilidad REQ-10..16,
identificada en `docs/trazabilidad-hito1.md` (congelado, 07-09-2026:
"PENDIENTE DE VINCULAR EN FASE DE TRAZABILIDAD") y confirmada en
`docs/architecture-4plus1-hito1.md` (09-09-2026, sección 6: 9/9 vínculos
vista→escenario→REQ sin HU Jira real).

**Hallazgo:** el pipeline temporal (meteorología regional, causalidad
`<=T`, target honesto, aislamiento legacy, ranking, robustez de
presentación) está técnicamente implementado, testeado (479 tests, 0
fallos, cobertura 91,72%) y documentado en 4+1 — pero ninguno de sus 7
requerimientos (REQ-10 a REQ-16) tiene una historia de usuario Jira real
detrás. Los únicos REQ del proyecto con HU Jira real (REQ-01..08,
SAPI-26/28/30/32/44/45/47/48) pertenecen al pipeline de ingesta/legacy.

**Análisis:** no corresponde reconstruir Sprint 1. Ninguna HU nueva puede
presentarse como si hubiera existido durante el sprint histórico (03-08 a
31-08-2026) — hacerlo sería fabricar evidencia retroactiva, exactamente lo
que las reglas de esta auditoría prohíben. Tampoco corresponde inflar el
número de HU mecánicamente (una por REQ): se diseñaron 3 HU agrupadas por
acoplamiento real de código y valor de producto (ver
`artifacts/hito1/posthito-jira/jira-ticket-specs.md`), no 7.

**Decisión:** preparar 3 HU (HU-A integridad del dataset temporal, HU-B
ranking confiable/aislado, HU-C presentación robusta/honesta) para el
Product Backlog actual / Sprint 2, con criterios de aceptación actuales,
trazabilidad completa a REQ/módulo/test/evidencia/escenario 4+1, y
estimación explícitamente marcada `PENDIENTE DE REFINAMIENTO` (no se
inventaron story points para trabajo ya construido sin una sesión real de
estimación).

**Ejecución:** este entorno no tiene acceso a ninguna instancia Jira real
(verificado explícitamente, sin herramienta/MCP/CLI disponible) — se
generó en su lugar el paquete de importación
(`artifacts/hito1/posthito-jira/`) y las instrucciones de creación manual
(≤5 minutos). Los tickets **no existen todavía en Jira**;
`docs/architecture-4plus1-hito1.md` **no se modificó** (sigue mostrando
"Sin HU Jira real — pendiente de vincular" en los 9 vínculos, con
honestidad, hasta que existan keys reales).

**Impacto:**
- Trazabilidad actual: mejora de "0/9 vínculos con HU real" a "un paquete
  de 3 HU listo, con 7/9 vínculos potenciales una vez creadas" (S2 y S4
  seguirán sin REQ/HU, por diseño — nunca estuvieron vinculados).
- Arquitectura 4+1: sin cambio todavía (se actualizará solo con keys
  reales, ver Fase 10 de la acción autorizada).
- Aceptación futura: define un Definition of Ready parcial (descripción y
  CA listos, estimación pendiente) para 3 HU concretas de Sprint 2.

**Prioridad:** justificada por ser la única brecha del nivel "excelente"
de la rúbrica de César ("vincula las vistas con HU") que sigue
genuinamente incompleta tras el cierre del bloque de arquitectura 4+1
(informe de la acción anterior, sección 20).

**Lo que esta decisión NO hace — explícito:**
- No convierte `Sprint Goal = existente` (histórico:
  `HISTORICAL_DOD: NOT_FOUND`, sin Sprint Goal documentado — ver
  `docs/cierre-sprint1-hito1.md`).
- No convierte `DoD = existente` para Sprint 1 (el mismo documento ya
  propone un `DOD_PROPUESTO_PARA_SPRINT_2`, separado de esto).
- No convierte `Sprint Review = realizada` para Sprint 1.
- No implica que hubo refinamiento previo de estas HU durante Sprint 1.
- No convierte el Sprint Backlog histórico en completo — la tasa de
  trazabilidad Git↔Jira de Sprint 1 sigue siendo 7/68 = 10,3%
  (`artifacts/hito1/versioning/git-jira-links.txt`), sin cambios, porque
  esos son commits ya hechos en el pasado.

---

## Documentos afectados por CR-001

**Creados (09-09-2026, todos rotulados como posteriores a Hito 1):**
- `artifacts/hito1/posthito-jira/jira-ticket-specs.md`
- `artifacts/hito1/posthito-jira/jira-import-pipeline-temporal.csv`
- Este archivo (`docs/change-log-posthito1.md`)

**No modificados (documentos congelados de Hito 1, decisión deliberada):**
- `docs/trazabilidad-hito1.md`
- `docs/architecture-4plus1-hito1.md` (pendiente de actualizar SOLO cuando
  existan keys Jira reales)
- `docs/informe-hito1-final.md`, `docs/atributos-calidad-hito1.md`,
  `docs/cierre-sprint1-hito1.md`
- Ningún export Jira histórico (`artifacts/hito1/versioning/*`) fue tocado.

**No modificados (fuera de alcance de esta acción, es de
gestión/trazabilidad, no de código):**
- `src/`, `app/`, `tests/` — sin cambios en esta acción.

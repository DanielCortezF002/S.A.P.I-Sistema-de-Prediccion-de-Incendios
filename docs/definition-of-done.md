# S.A.P.I. — Definition of Done (Sprint 3 / Hito 3)

Subtarea HU-92.T9 (SAPI-176). Versión 0.1 del 22-11-2026. Parte de la DoD del Sprint 2 (`docs/hito2/definition-of-done.md`, formalizada el 08-10-2026) y le suma las exigencias del Hito 3: la rúbrica de Matías y la revisión del Hito 2 de César.
**Rige para las HU que se cierren desde la fecha de integración de este archivo.** No se aplica de forma retroactiva para dar por cumplidas HU anteriores.

Una HU del Sprint 3 está **terminada** solo cuando cumple las 12 condiciones. En el ticket, al pasar a «Finalizado», se registra la verificación punto a punto (HU-92 CA5).

| # | Condición | Cómo se verifica | Evidencia que se enlaza en el ticket |
|---|---|---|---|
| 1 | Cada criterio de aceptación (Dado/Cuando/Entonces) está cumplido, o el cambio de alcance quedó registrado y aprobado por Daniel | Revisión criterio por criterio | Enlace a la prueba o al reporte de cada CA |
| 2 | Hay al menos un caso negativo o de borde por HU Must, y falla cuando se rompe el requisito | Ejecutar el caso y romper a propósito | Salida de la prueba con fecha y SHA |
| 3 | La suite completa pasa: `pytest` con el gate de cobertura del 80 % y `./mvnw verify` si la HU toca el backend. Cada prueba nueva cita su requerimiento (`docs/requerimientos.md`) o el ID del CA | CI en la PR | Run de CI enlazado |
| 4 | El gate oficial está en verde (6/6 jobs) en el SHA de la PR | `scripts/merge_gate.py` / CI | Run de CI enlazado |
| 5 | Fronteras y congelamiento: `tests/test_architecture.py` pasa y `scripts/freeze_check.py` da `FREEZE CHECK PASS`. No cambian `models/`, el dataset `14b36ad8…` ni el código congelado | CI | Salida del freeze check |
| 6 | Integridad científica: ningún texto presenta el score como probabilidad; `scientific_model_validation=false` se mantiene | Revisión de la PR | Comentario del revisor |
| 7 | Trazabilidad: la rama (`feat/SAPI-NN-…`), los commits (`SAPI-NN: …`) y la PR citan la clave de Jira. La HU figura en `docs/trazabilidad.md` con su prueba y su evidencia | `git log`, plantilla de PR | Enlace a la PR |
| 8 | Las mediciones se hicieron después del sello de su meta (`docs/objetivos.md`) y del plan de pruebas (`docs/pruebas/plan-sprint3.md`) | Comparar las fechas de los commits | SHA del sello y SHA del reporte |
| 9 | Revisión independiente: el Auditor u otra persona distinta del autor revisó la PR; Daniel la integra. Ningún bot integra ni cambia estados en Jira | PR | Enlace a la revisión |
| 10 | Documentación: si cambia el comportamiento visible, el contrato o la ejecución, el README, el contrato o el ADR se actualizan en la misma PR, y el `CHANGELOG.md` registra el cambio | Revisión de la PR | Diff |
| 11 | **Aprobación de un stakeholder distinto del estudiante** (subtarea `.V`): nombre, rol y fecha en el ticket, con enlace al acta de HU-79. La autoaprobación no cuenta | Ticket | Enlace al acta |
| 12 | Jira: Daniel mueve el ticket a «Finalizado» y deja el enlace a la evidencia y esta tabla marcada | Ticket | — |

**Lo que la DoD no concede:** las pruebas de software no validan científicamente el Modelo D, y cumplir la DoD no autoriza publicar, desplegar ni presentar el score como apto para decisiones operacionales.

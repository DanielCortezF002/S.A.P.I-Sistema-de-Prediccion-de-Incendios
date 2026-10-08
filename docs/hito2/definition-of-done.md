# S.A.P.I. — Definition of Done (Sprint 2 / Hito 2)

Formalizada el **2026-10-08**, día 7 del Sprint 2, durante el Quality Gate W0.
No existía antes como artefacto del proyecto: el cierre de Sprint 1 registró
`HISTORICAL_DOD: NOT_FOUND` y propuso una DoD para Sprint 2
(`docs/cierre-sprint1-hito1.md` §6). Este documento adopta esa propuesta y la
amplía con las reglas del plan de Hito 2. Se aplica a toda HU que se cierre
desde esta fecha. Las HU cerradas antes (SAPI-54, 55, 56, 58, 62) se evalúan
retroactivamente en `requerimientos-sprint2.md`, criterio por criterio.

Una HU de Sprint 2 está **terminada** cuando se cumple todo lo siguiente:

1. **Criterios de aceptación.** Cada criterio `SAPI-<n>.CA<k>` está
   `CUMPLIDO` con evidencia reproducible, o el cambio de alcance quedó
   registrado y aprobado por Daniel. Un criterio sin evidencia no cuenta como
   cumplido aunque el código exista.
2. **Pruebas.** La suite completa pasa (`pytest`, gate de cobertura 80 %;
   `./mvnw verify` si la HU toca el backend). Cada test nuevo cita el ID del
   criterio que verifica.
3. **Fronteras de arquitectura.** `tests/test_architecture.py` pasa. No se
   agregan imports prohibidos por el contrato de datos.
4. **Congelamiento.** `python -B scripts/freeze_check.py` termina con
   `FREEZE CHECK PASS`: sin cambios en rutas congeladas, en los hashes de
   readiness, en V001–V003, en el modelo ni en `artifacts/hito1`; contratos
   solo aditivos.
5. **Integridad científica.** Ningún texto nuevo presenta el score como
   probabilidad ni una detección FIRMS como incendio confirmado;
   `scientific_model_validation=false` se mantiene.
6. **Trazabilidad.** La rama, los commits y el pull request citan la clave
   Jira de la HU. La evidencia queda versionada en `artifacts/hito2/` en
   formato `.txt`, `.json`, `.csv` o `.xml` (nunca `.log`, que git ignora), con
   SHA, fecha UTC, host, versión de herramienta, comando y resultado.
7. **Revisión.** Una revisión independiente (Codex u otro revisor) aprobó el
   PR y Daniel lo mergeó. Ningún agente mergea ni cambia estados en Jira.
8. **Documentación.** Si la HU cambia el comportamiento visible, el contrato o
   la forma de ejecutar el sistema, el README, el contrato o el ADR
   correspondiente se actualizan en el mismo PR.
9. **Jira.** Daniel mueve el ticket a Finalizado y deja en él el enlace a la
   evidencia.

Lo que la DoD **no** concede: los tests de software no validan
científicamente el Modelo D, y cumplir la DoD no autoriza publicar, desplegar
ni presentar el score como apto para decisiones operacionales.

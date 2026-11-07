---
name: sapi-checkpoint
description: Produce un checkpoint factual, auditado y conciso de la ejecución de SAPI con SHAs, pruebas, integridad y bloqueos.
---

Genera reporte de no más de 30 líneas con tabla `Ticket | SHA | PASS | FAIL | SKIP | evidencia | estado`. Incluye versiones de herramientas importantes, exit code, hash de manifests, freeze-check, cambios Git y recursos Docker previos/posteriores cuando se ejecutaron. Clasifica exactamente `VERIFIED_INDEPENDENTLY`, `REPORTED_ONLY`, `SANDBOX_SUBSTITUTE`, `NOT_EXECUTED`, `BLOCKED_BY_AUTHORIZATION` o `FAIL`. No declaras integración con main por un commit local, ni predicción real por stores sintéticos. Separa trabajo propio de ajeno, y acción siguiente de autorización pendiente.

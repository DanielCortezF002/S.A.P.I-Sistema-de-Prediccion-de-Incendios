---
name: sapi-freeze-audit
description: Audita solo lectura la integridad F1–F9 y cambios prohibidos en SAPI antes de aceptar un candidato.
---

Antes de auditar: verificar repositorio, SHA exacto, árbol limpio, base comparada. Ejecutar scripts existentes de `freeze_check` sin modificarlos y comparar rutas congeladas de la línea base aprobada; si el script no existe o falla, no suplirlo con una simulación. No imprimir secretos. Confirmar fingerprints y que `scientific_model_validation=false`. Clasificar F3 raíz, PERM-01 y F4-HTTP como sujetos a change-control. Rechazar candidatos cuyos diffs toquen artefactos congelados sin autorización. Emitir diferencias + comandos y exit codes.

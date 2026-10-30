# Expediente F4 2/4 — `src/procesamiento/firms_source.py`

**Estado:** PENDIENTE DE FIRMA. Este expediente no autoriza nada por sí mismo.

| Campo | Valor |
|---|---|
| Defecto(s) | B1 |
| Motivo declarado | Extracción de validate_pointer_dict para validación en memoria desacoplada del filesystem (prevención TOCTOU) |
| Alcance declarado | validate_pointer_dict (L166-195) |
| Commit autorizado | `7dcd0b666e05bb5efd64c1c98685902e8b4908bf` |
| Autoridad citada en el código | Directiva OCC-003A (orquestador), autor DanielCortezF002 |
| Baseline del freeze | `cd6b58eb9bd4b9a22b8937c4cda73be46322cddb` |
| Candidato evaluado | `61b1afbeb85d2dafda63dd880b55948b136fa94e` |
| Blob baseline → candidato | `32750d0a8efb3a05110b227c12f36e755c6c3471` → `211c0a8fa897d644cf8520a2789f083ba235ba62` |
| SHA-256 (LF) pin | `90daeff030f3561107ff084fce852c5761116ed010ec279e4eeea4c8d8ebfbef` |
| Cambio frente al baseline | +15 / −10 líneas (`02_firms_source.diff`) |
| Evidencia citada | docs/evidence/b1-b2-b3-estado-real-20261015/README.md |

## Comprobaciones automáticas

| Comprobación | Resultado |
|---|---|
| Blob en el commit autorizado = pin | PASS |
| Blob en el candidato (HEAD) = pin | PASS |
| SHA-256 (LF) en el candidato = pin | PASS |
| Sin cambios desde el commit autorizado | PASS |
| Evidencia citada existe | PASS |

## Pruebas que ejercitan esta ruta y el alcance declarado

- `tests/test_remediation_red_defects.py`
- `tests/test_freeze_f4_exceptions.py` (pruebas negativas y positivas del mecanismo)

Los resultados de estas pruebas sobre el candidato están en el informe F2.

## Revisión que debe hacer quien firma

1. Leer `02_firms_source.diff` y confirmar que el cambio se limita al alcance declarado.
2. Confirmar que el defecto citado existía y que la evidencia lo demuestra.
3. Confirmar que el cambio no altera features, target, modelo ni semántica del score.

## Decisión

- [ ] Autorizo esta excepción F4
- [ ] Rechazo esta excepción F4 (el archivo debe volver al contenido del baseline)

Firma: ______________________  Fecha: ____________

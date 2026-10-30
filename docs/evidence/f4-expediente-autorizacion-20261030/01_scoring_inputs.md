# Expediente F4 1/4 — `src/inference/scoring_inputs.py`

**Estado:** PENDIENTE DE FIRMA. Este expediente no autoriza nada por sí mismo.

| Campo | Valor |
|---|---|
| Defecto(s) | B2 |
| Motivo declarado | Manejo defensivo de excepciones en decodificación DMC (UnicodeDecodeError, JSONDecodeError -> PinnedInputError) |
| Alcance declarado | _read_versioned_months (L154-159) |
| Commit autorizado | `7dcd0b666e05bb5efd64c1c98685902e8b4908bf` |
| Autoridad citada en el código | Directiva OCC-003A (orquestador), autor DanielCortezF002 |
| Baseline del freeze | `cd6b58eb9bd4b9a22b8937c4cda73be46322cddb` |
| Candidato evaluado | `61b1afbeb85d2dafda63dd880b55948b136fa94e` |
| Blob baseline → candidato | `f3fb477e60a4f7882a40e2a90c9501655c12bd9c` → `2dcb470886f6d2ea1a1f300854e20d4e545cc041` |
| SHA-256 (LF) pin | `1aa419fdda5ccdd4834970ecf0e7d613abdba9efb951b028bb2dca1596a2c221` |
| Cambio frente al baseline | +6 / −1 líneas (`01_scoring_inputs.diff`) |
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

1. Leer `01_scoring_inputs.diff` y confirmar que el cambio se limita al alcance declarado.
2. Confirmar que el defecto citado existía y que la evidencia lo demuestra.
3. Confirmar que el cambio no altera features, target, modelo ni semántica del score.

## Decisión

- [ ] Autorizo esta excepción F4
- [ ] Rechazo esta excepción F4 (el archivo debe volver al contenido del baseline)

Firma: ______________________  Fecha: ____________

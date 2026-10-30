# Expediente F4 3/4 — `src/refresh/dmc_refresh.py`

**Estado:** PENDIENTE DE FIRMA. Este expediente no autoriza nada por sí mismo.

| Campo | Valor |
|---|---|
| Defecto(s) | ADV-05 |
| Motivo declarado | Invariante Write-Ahead Logging (WAL): registrar en historial antes de actualizar puntero atómico en _publish() |
| Alcance declarado | _publish (L586-589) |
| Commit autorizado | `7dcd0b666e05bb5efd64c1c98685902e8b4908bf` |
| Autoridad citada en el código | Directiva OCC-003A (orquestador), autor DanielCortezF002 |
| Baseline del freeze | `cd6b58eb9bd4b9a22b8937c4cda73be46322cddb` |
| Candidato evaluado | `61b1afbeb85d2dafda63dd880b55948b136fa94e` |
| Blob baseline → candidato | `1db368d1cd2027460a6640f7f6076b0696640c7e` → `3c67404247f67f13cad2533394f7e67cb1f03486` |
| SHA-256 (LF) pin | `6b3c51a71687651ba30ab4c1949b52c5f5499227b3c2b8cd021c0e53b445c84c` |
| Cambio frente al baseline | +1 / −1 líneas (`03_dmc_refresh.diff`) |
| Evidencia citada | docs/evidence/adv05-fix-validated-20261015/README.md |

## Comprobaciones automáticas

| Comprobación | Resultado |
|---|---|
| Blob en el commit autorizado = pin | PASS |
| Blob en el candidato (HEAD) = pin | PASS |
| SHA-256 (LF) en el candidato = pin | PASS |
| Sin cambios desde el commit autorizado | PASS |
| Evidencia citada existe | PASS |

## Pruebas que ejercitan esta ruta y el alcance declarado

- `tests/test_adv05_characterization.py`
- `tests/test_adv05_proposed_fix_oracle.py`
- `tests/test_dmc_refresh.py`
- `tests/test_dmc_store_contract.py`
- `tests/test_remediation_red_defects.py`
- `tests/test_scoring_inputs.py`
- `tests/test_freeze_f4_exceptions.py` (pruebas negativas y positivas del mecanismo)

Los resultados de estas pruebas sobre el candidato están en el informe F2.

## Revisión que debe hacer quien firma

1. Leer `03_dmc_refresh.diff` y confirmar que el cambio se limita al alcance declarado.
2. Confirmar que el defecto citado existía y que la evidencia lo demuestra.
3. Confirmar que el cambio no altera features, target, modelo ni semántica del score.

## Decisión

- [ ] Autorizo esta excepción F4
- [ ] Rechazo esta excepción F4 (el archivo debe volver al contenido del baseline)

Firma: ______________________  Fecha: ____________

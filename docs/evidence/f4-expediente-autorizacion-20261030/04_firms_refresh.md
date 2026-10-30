# Expediente F4 4/4 — `src/refresh/firms_refresh.py`

**Estado:** PENDIENTE DE FIRMA. Este expediente no autoriza nada por sí mismo.

| Campo | Valor |
|---|---|
| Defecto(s) | B1, B3, ADV-05 |
| Motivo declarado | Invariante WAL en _publish(), preservación de FirmsRefreshError en refresh(), y validación estricta de sidecar en rollback() |
| Alcance declarado | _publish (L273-277), refresh (L316-317), rollback (L400-417) |
| Commit autorizado | `7dcd0b666e05bb5efd64c1c98685902e8b4908bf` |
| Autoridad citada en el código | Directiva OCC-003A (orquestador), autor DanielCortezF002 |
| Baseline del freeze | `cd6b58eb9bd4b9a22b8937c4cda73be46322cddb` |
| Candidato evaluado | `61b1afbeb85d2dafda63dd880b55948b136fa94e` |
| Blob baseline → candidato | `6861d517e5d92d9a7f56b9cbd741e96f8e1127c2` → `ebc67c74fce44801bf373795672c56ca6198628c` |
| SHA-256 (LF) pin | `d6031497246a4461b108c521a7d9dde2da77580d06bff00da985556f7f90d654` |
| Cambio frente al baseline | +20 / −4 líneas (`04_firms_refresh.diff`) |
| Evidencia citada | docs/evidence/adv05-fix-validated-20261015/README.md y b1-b2-b3-estado-real-20261015/README.md |

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
- `tests/test_attempt2_operator_phase4.py`
- `tests/test_firms_refresh.py`
- `tests/test_ops_dashboard.py`
- `tests/test_refresh_adversarial.py`
- `tests/test_remediation_red_defects.py`
- `tests/test_scoring_inputs.py`
- `tests/test_freeze_f4_exceptions.py` (pruebas negativas y positivas del mecanismo)

Los resultados de estas pruebas sobre el candidato están en el informe F2.

## Revisión que debe hacer quien firma

1. Leer `04_firms_refresh.diff` y confirmar que el cambio se limita al alcance declarado.
2. Confirmar que el defecto citado existía y que la evidencia lo demuestra.
3. Confirmar que el cambio no altera features, target, modelo ni semántica del score.

## Decisión

- [ ] Autorizo esta excepción F4
- [ ] Rechazo esta excepción F4 (el archivo debe volver al contenido del baseline)

Firma: ______________________  Fecha: ____________

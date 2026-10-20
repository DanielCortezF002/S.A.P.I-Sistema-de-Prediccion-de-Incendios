# OVERNIGHT HANDOFF — OCC-NIGHTSHIFT-S2-20261020

**Veredicto honesto: CONDITIONAL.** No se declara el Sprint 2 cerrado al 100 %.

- Base verificada: `0ac6c05ebd1df66c029fc25f6dbfd66899e8bce4` (= SHA esperado), rama de trabajo `claude/overnight-sprint2-evidence-20261020`.
  No se tocó `main`, PR #36, `freeze_check.py`, `merge_gate.py`, las rutas F4 ni el endurecimiento F7 del Omen.
- Ejecutado: pytest completo **2154 ok / 138 omitidas / 0 fallos / cobertura 85,3 %** (2292 casos, igual al expediente previo);
  Maven **162 casos, 0 fallos, 4 omitidas**; node `policy.test.js` 45/45.
- Agregado: `tests/test_overnight_s2_chain_integrity.py` (12 pruebas, estáticas/integración/**E2E con stub**) + este expediente.
- **Hallazgo principal:** `RankingRealMlServiceTests` (SAPI-57.CA4, Spring↔FastAPI real) **falla 3/4** contra un ML vivo porque
  compara bytes y `age_hours` depende del reloj. Hoy pasa inadvertido porque la prueba se omite. Parche verificado (4/4) en
  `evidence/`, **no aplicado**.
- **Hallazgo 2:** la evidencia E2E de navegador/PostGIS está generada sobre `8982e58`, que no existe en esta rama; hay que repetirla.
- **Hallazgo 3:** ADR-011 recomienda AWS Lightsail, descartado por la restricción presupuestaria $0 de Jira (16-10). SAPI-67 sigue
  "PENDIENTE A VALIDACION"; su criterio "ADR firmado" no se cumple.
- **Hallazgo 4:** Jira marca SAPI-60 y SAPI-66 "Finalizado" mientras la trazabilidad del repo deja SAPI-60.CA6 parcial y SAPI-66.CA5
  literal fallido. Sin cambios de Jira por mi parte.
- No ejecutable aquí: Docker/Compose/Testcontainers, navegador, datos reales FIRMS/DMC, PostGIS, n8n vivo, PowerShell.

## Índice (cada archivo cumple una función)

| Archivo | Función |
|---|---|
| `SPRINT2_CLOSEOUT_MATRIX.md` | criterios, estado, evidencia, brechas, SAPI-67 |
| `E2E_VERIFICATION_REPORT.md` | rutas reales, pruebas ejecutadas, hallazgo `age_hours` |
| `CI_AND_SKIPS_AUDIT.md` | CI, reconciliación 2292/114, causa de cada omisión, CA8 |
| `ACADEMIC_RUBRIC_TRACEABILITY.md` | cobertura de rúbricas Matías / César (sin notas) |
| `NEXT_ACTIONS.md` | acciones ordenadas y quién decide |
| `evidence/` | JUnit, consola, parche propuesto, JSON de `age_hours`, logs Maven |

## Integridad científica

Las pruebas nuevas fijan: ranking relativo, `scientific_model_validation=false`, aviso "NO una probabilidad calibrada…
No usar para decisiones", y que Streamlit nunca muestra internals ni ranking cuando el ML falla. No se modificó modelo ni datos.

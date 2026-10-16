# Paquete de publicación — Sprint 2 / Hito 2 (Directiva 31)

Candidato: `9343321a7e630fbbfdfaecd889c0abd4662c4c1c` (rama
`release/sprint2-closeout-candidate`). Este documento prepara la publicación;
**no ejecuta** push, merge, despliegue ni transición de Jira.

## 1. Matriz HU → CA → Pruebas → Evidencia (5 historias reevaluadas)

| Historia | CA clave | Prueba | Evidencia |
|---|---|---|---|
| SAPI-66 | CA1-CA4 orquestación/integración/persistencia/rendimiento | `merge_gate.py --job all`, `measure_browser_e2e_d21.py`, `bootstrap_compose_v2.py::verify_database_persistence_correlated` | `/c/sapi-gate/609f615ceca7/`; `tests/test_bootstrap_compose_v2.py`; `tests/test_measure_browser_e2e_d21.py` |
| SAPI-66 | CA5 (literal: `docker-compose up` sin config) | Ejecución directa `docker compose up` sin `.env` | **FALLA probada** (exit 1, 0 contenedores) — aclarada en Jira (comentario `10156`) como PO-aprobado vía `bootstrap_compose_v2.py` |
| SAPI-63 | Ventanas causales, walk-forward sin leakage, shape, distribución positivos, conclusión viabilidad | `notebooks/sapi63_lstm_viability.py` reejecutado contra dataset real | `docs/evidence/sapi63-reproduction-20261015/README.md`; Jira SAPI-63 comentario `10158` |
| SAPI-49 | Fuentes oficiales, cobertura, acceso, limitaciones, recomendación | Lectura verificada línea por línea del spike | `docs/spikes/SAPI-49-CONAF-historical-source.md`; Jira SAPI-49 comentario `10159` |
| SAPI-67 | Comparación ≥3 proveedores, ADR firmado | Lectura verificada de `ADR-011-cloud-provider.md` | Comparación: cumple. Firma: **pendiente**, no fabricada. Jira SAPI-67 comentario `10157` |
| SAPI-43 | Atomicidad, locks, redacción, rollback | `pytest tests/test_dmc_refresh.py tests/test_firms_refresh.py tests/test_refresh_primitives.py tests/test_refresh_adversarial.py` | 139 passed, 1 skipped (ejecutado hoy); Jira SAPI-43 comentario `10160` |

## 2. Secuencia de integración Git propuesta (NO ejecutada)

```
1. git fetch origin                                   # sobre el remoto real cuando se autorice
2. git checkout sprint2/integration-candidate
3. git merge --no-ff release/sprint2-closeout-candidate@9343321 \
       -m "merge(sprint2): closeout candidate 9343321 (CA5 aprobado por PO, gate verde salvo F4/F6/F9 explicados)"
4. Re-ejecutar merge_gate.py --job all sobre el SHA de merge resultante
   (un merge commit es un SHA nuevo; la evidencia de 609f615/9343321 no se hereda automáticamente)
5. git tag hito2-sprint2-rc6 <sha-de-merge>             # o -final si se decide cierre definitivo
6. Recién entonces: push origin sprint2/integration-candidate (requiere autorización explícita)
```

## 3. PR propuesto (texto listo, no publicado)

**Título:** `Sprint 2 / Hito 2 — cierre candidato (CA5 aprobado, gate consolidado)`

**Cuerpo:**
```markdown
## Resumen
- Cierra la cadena SAPI-66 Directiva 26/28/30/31: CA4 (falso positivo de timestamp),
  CA5 persistencia correlacionada, sql-migration-validation, container-smoke-backend (D29).
- CA5 literal de SAPI-66 ("docker-compose up sin configuración adicional") se prueba
  que NO se cumple tal cual; el PO aprueba bootstrap_compose_v2.py como alternativa
  formal (Jira SAPI-66, comentario 10156).
- SAPI-63 reproducido de forma independiente contra el dataset real externo
  (docs/evidence/sapi63-reproduction-20261015/).
- SAPI-67: corregida la referencia documental (ADR-011, no adr-003 inexistente).

## Gate
PASS: python, backend-unit, sql-migration-validation, flyway-integration, container-smoke.
FAIL explicado: freeze (F1 origin/main sin remoto real; F6/F9 y F4 preexistentes,
idénticos al origen inmutable sin tocar; F4/SAPI-71 con cadena de autorización documentada).

## Test plan
- [x] merge_gate.py --job all sobre 609f615/9343321 (ver /c/sapi-gate/)
- [ ] Re-ejecutar sobre el SHA de merge resultante antes de cualquier release

## No incluido / no autorizado en este PR
- Push a remoto real, despliegue cloud, transición de estado Jira de SAPI-49/63/66/67/43.
```

## 4. Checklist de publicación

- [x] CA5 aclarado formalmente en Jira (no fabricado, decisión expresa del PO registrada)
- [x] Gate completo ejecutado y atribuido al SHA final
- [x] SAPI-63 con evidencia reproducida, no solo narrada
- [x] SAPI-67 con referencia documental corregida, sin ADR duplicado
- [x] SAPI-43/71 con runbook listo, sin credenciales inventadas, B1/B2/B3 mantenidos abiertos
- [x] Matriz de rúbricas con niveles sustentados (no auto-Excelente)
- [ ] **Autorización humana de merge/push/despliegue** (pendiente, fuera de este alcance)
- [ ] Firma formal de ADR-011 (pendiente de César/Matías o del PO)
- [ ] Decisión sobre la rama Codex `review/SAPI-66-hardening` (6fbcd74) antes de cerrar SAPI-66 por completo
- [ ] Transición de estado Jira de las 5 historias (pendiente de decisión del PO)

## 5. Documentos definitivos de Hito 2 (ubicación)

- Gate: `/c/sapi-gate/609f615ceca7/gate_summary.json`
- Rúbricas: `docs/evidence/rubricas-hito2-verificadas-20261015/README.md`
- SAPI-63: `docs/evidence/sapi63-reproduction-20261015/README.md`
- Este paquete: `docs/evidence/cierre-sprint2-publicacion-20261015/README.md`

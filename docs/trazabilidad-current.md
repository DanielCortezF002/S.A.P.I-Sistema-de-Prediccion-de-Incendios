# Trazabilidad actual — REQ-10..REQ-16 (pipeline temporal)

**Estado de este documento: ACTUAL / POST-HITO 1.** Creado 09-09-2026, tras
la creación real en Jira de SAPI-50, SAPI-51 y SAPI-52 (ver
`docs/change-log-posthito1.md`, CR-002). **No reemplaza ni reescribe**
`docs/trazabilidad-hito1.md` (congelado, entrega histórica de Sprint 1,
31-08-2026 planificado / 07-09-2026 evaluación) — ese documento sigue
mostrando, con honestidad, que REQ-10..16 estaban "PENDIENTE DE VINCULAR EN
FASE DE TRAZABILIDAD" durante el Hito 1. Este documento registra el estado
**de hoy**, después de que esa vinculación se formalizó.

**Principio de honestidad temporal:** SAPI-50/51/52 no existieron durante
Sprint 1 (03-08 a 31-08-2026). Se crearon el 09-09-2026 para formalizar
trazabilidad de funcionalidad ya implementada y verificada — no
representan trabajo planificado, estimado ni aceptado durante ese sprint.
Actualmente están en **Product Backlog**, estado **TO DO**, Sprint **vacío**,
Story Points **vacíos** — candidatas a refinamiento y a Sprint Planning 2,
no asignadas todavía a Sprint 2.

---

## Mapping HU real → REQ

| HU Jira | Título | REQ cubiertos |
|---|---|---|
| **SAPI-50** | Integridad causal del dataset temporal (DMC regional, causalidad ≤T, target honesto) | REQ-10, REQ-11, REQ-12 |
| **SAPI-51** | Ranking de riesgo confiable y aislado de datos sintéticos/legacy | REQ-13, REQ-14 |
| **SAPI-52** | Presentación robusta y honesta de información por celda (carga sin excepción, DEM N/D) | REQ-15, REQ-16 |

---

## Matriz completa — HU → CA actual → REQ → Módulo → Test → Resultado → Evidencia → Escenario 4+1 → Estado

| HU Jira | CA actual | REQ | Módulo | Test | Resultado | Evidencia | Escenario 4+1 | Estado |
|---|---|---|---|---|---|---|---|---|
| SAPI-50 | CA-A3 — misma observación regional 330007 para las 50 celdas, nunca reetiquetada por celda | REQ-10 | `regional_meteo.py` | `test_regional_meteo.py::test_regla_30_30_30_uses_the_same_observation` | PASS | `artifacts/hito1/posthito-jira/jira-ticket-specs.md` (HU-A) | S5 | COMPLETE |
| SAPI-50 | CA-A1 — ningún feature usa `timestamp > T` | REQ-11 | `causality_validator.py`, `temporal_features.py` | `test_causality_validator.py` | PASS | ídem | S5, S7 | COMPLETE |
| SAPI-50 | CA-A2 — target en ventana `(T, T+6h]`, cooldown excluido, nunca 0 falso | REQ-12 | `target_builder.py` | `test_target_builder.py` | PASS | ídem | S5 | COMPLETE |
| SAPI-51 | CA-B1 — árbol transitivo real de imports sin `src.modelo`/`features`/`imblearn` | REQ-13 | `prototype_service.py`, `shared_thresholds.py` | `test_architecture.py::test_temporal_pipeline_has_no_transitive_legacy_dependency` | PASS | `artifacts/hito1/posthito-jira/jira-ticket-specs.md` (HU-B) | (transversal) | COMPLETE |
| SAPI-51 | CA-B3 — `app/` no importa `src.ingesta`/`procesamiento`/`modelo`/`pipeline` directamente | REQ-13 | `app/` | `test_architecture.py::test_frontend_data_contract_compliance` | PASS | ídem | (transversal) | COMPLETE |
| SAPI-51 | CA-B2 — ranking expone `rank`/`display_rank`/`tie_group_size`, nunca probabilidad calibrada falsa | REQ-14 | `prototype_service.py` | `test_prototype_service.py::test_ties_share_display_rank_but_internal_rank_stays_unique`, `test_inference_returns_fifty_cells`, `test_ranks_are_one_to_n` | PASS | ídem | S1, S6 | COMPLETE |
| SAPI-52 | CA-C2 — celda sin cobertura DEM queda `NaN`, nunca `0` | REQ-15 | `dem_features.py` | `test_dem_features.py` | PASS | `artifacts/hito1/posthito-jira/jira-ticket-specs.md` (HU-C) | S8 | COMPLETE |
| SAPI-52 | CA-C3 — `NaN` topográfico se renderiza como "N/D" en el panel de detalle | REQ-15 | `prototype_view.py::_fmt_nd` | **sin test dedicado** | **PARTIAL — gap conocido** | ídem, sección "Riesgos" | S8 | **PARTIAL** |
| SAPI-52 | CA-C1 — la app arranca en modo Prototipo sin excepción fatal | REQ-16 | `app/app.py` | `test_main_runs_without_exceptions`, `test_prototype_mode_is_the_default_and_runs_without_exceptions` | PASS | ídem | S3 | COMPLETE |
| SAPI-52 | CA-C4 — lectura DMC >24h se muestra como "HISTÓRICO", nunca disfrazada de reciente | REQ-16 | `prototype_service.py::classify_freshness` | `test_prototype_freshness.py` | PASS | ídem | S3 | COMPLETE |

**Distinción explícita:** las CA de esta matriz son criterios **actuales**
(redactados 09-09-2026, ligados a SAPI-50/51/52). Los `AC-T01..AC-T10` de
`artifacts/hito1/testing/acceptance-checks.txt` son **evidencia técnica de
verificación de cierre del Hito 1** (07-09-2026) — se citan aquí como
evidencia de que la funcionalidad ya estaba verificada antes de crear estas
HU, no se renombran ni se presentan como si hubieran sido el CA original de
una historia de usuario que no existió durante Sprint 1.

---

## Resumen de trazabilidad (números exactos)

- REQ-10..16 con HU Jira real: **7/7**
- REQ-10..16 con CA actual definido: **7/7**
- REQ-10..16 con test que pasa para **todas** sus CA: **6/7** (todos salvo
  REQ-15, que tiene un gap conocido en CA-C3 — `_fmt_nd` sin test dedicado)
- REQ-10..16 con evidencia (al menos parcial): **7/7**
- REQ-10..16 con escenario 4+1 vinculado: **7/7**
- Cadenas completas actuales (HU→CA→REQ→módulo→test→evidencia→escenario,
  todas PASS): **6/7**

Escenarios 4+1 con HU Jira real: **7/9** (S1, S3, S5, S6, S7, S8 + fila
transversal de aislamiento legacy). S2 y S4 siguen sin HU Jira real, por
diseño: S2 nunca tuvo REQ asignado en `docs/trazabilidad-hito1.md`, y S4 es
un requisito de la auditoría de reproducibilidad, no del backlog de
producto — ver `docs/architecture-4plus1-hito1.md` sección 6.

---

## Lo que este documento NO hace

- No modifica `docs/trazabilidad-hito1.md`, `docs/informe-hito1-final.md`,
  `docs/atributos-calidad-hito1.md`, `docs/cierre-sprint1-hito1.md`, ni
  ningún export Jira histórico de Sprint 1.
- No implica que SAPI-50/51/52 formaron parte del Sprint Backlog, Sprint
  Goal o DoD histórico de Sprint 1 (`HISTORICAL_DOD: NOT_FOUND`, ver
  `docs/cierre-sprint1-hito1.md`).
- No asigna Story Points ni mueve las HU a Sprint 2 — quedan en Product
  Backlog, `TO DO`, pendientes de refinamiento y Sprint Planning 2.
- No cierra el gap real de CA-C3 (`_fmt_nd` sin test) — lo deja explícito
  para que se decida en refinamiento si se convierte en sub-tarea.

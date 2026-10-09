# W0 EXECUTION REPORT — Sprint 2 / Hito 2

| Campo | Valor |
|---|---|
| Rama | `chore/hito2-w0-gate`. Baseline `cd6b58e` = `origin/main`, sin tocar |
| SHA de código certificado | `7618cce00123ac0b3f0c18e2ba8ec6778f19059a` (con push) |
| Commits posteriores a `7618cce` | Solo de evidencia: `artifacts/hito2/**`. Heredan el gate (`merge_gate.py --inherit 7618cce` → PASS). Este reporte y los commits `1e08aa1` y `598af80` se publican en el mismo push que cierra W0 |
| Fecha | 2026-10-09 |
| Referencia | Revisión 3 (FINAL CONSENSUS DELTA): §3 W1 ENTRY GATE, §8 paquete de ejecución |
| Alcance | Solo W0. Sin W1, sin PR, sin merge, sin Jira, sin W0.12 |

## 1. Veredicto técnico

- **G1 a G8 están en PASS**, con evidencia reproducible y verificable por sha256.
- **G9 está pendiente** de las decisiones humanas del §4.
- **G10** es el GO W1 explícito de Daniel.
- No hubo fallas del producto. Las **cuatro** fallas de W0 fueron del instrumento de medición o del saneamiento de su evidencia (§3). Las de código se corrigieron con tests de regresión; la #4 se corrigió regenerando los archivos y verificando el diff de marcadores.
- Las cuatro quedan registradas como historia.

## 2. W1 ENTRY GATE (Revisión 3 §3.2)

| Gate | Condición | Resultado | Evidencia |
|---|---|---|---|
| **G1** | Rama con push; `cd6b58e` ancestro; `freeze` F1–F9 en PASS sobre el HEAD | **PASS** | `7618cce` está en `origin`. `gate/7618cce/freeze_check.json` (modo gate, sin SKIP) y `freeze_check_598af80.{txt,json}`: freeze del HEAD de evidencia `598af80`, modo B, F1–F9 PASS sin `--allow-dirty` |
| **G2** | `freeze`, `python` y `backend-unit` en verde sobre el SHA (Rev3 §3.2) | **PASS** (fallback en la nube; Actions tiene 0 runs) | `gate/7618cce/`: pytest 1720 passed, 114 skipped, cobertura 84,56 %; `mvnw verify` 3/3; lint v2 limpio. El veredicto agregado de `gate_summary.json` es `NOT_VERIFIABLE_IN_THIS_ENVIRONMENT` (exit 2) solo porque sus 3 jobs Docker no corren en la nube; esos jobs se cubren con G3–G6 |
| **G3** | `container-smoke` ML: 200, 50 celdas, fingerprint `33c2…31ff` | **PASS** | `host/7618cce/extracted/container-smoke-ml.json`: uid 10001, `relative_rank`, `scientific_model_validation=false` |
| **G4** | `container-smoke` backend: `/health` UP, usuario no root | **PASS** | `host/7618cce/extracted/container-smoke-backend.json` (uid 10001) |
| **G5** | REAL FLYWAY INTEGRATION | **PASS** | `host/7618cce/extracted/flyway-integration.json`: Flyway 12.4.0, migrate 3 → validate e info OK → segundo migrate 0 pendientes; historial `001..003` (derivado y semántico); 50 celdas; 0 geometrías inválidas |
| **G6** | SQL MIGRATION VALIDATION (independiente de G5) | **PASS** | `host/43c17fd/extracted/sql-migration-validation*`. Sigue vigente por regla: `db/` y `sapi58_migration_integration.ps1` no cambiaron hasta `7618cce` (`--evidence-valid` → VIGENTE) |
| **G7** | Datos del host | **PASS** | `host/7618cce/extracted/hostfacts.json`: Docker 29.8.1, Compose 5.5.1, puertos libres, `sapi_pgdata` ausente, `core.autocrlf=false`, JDK 21, Python 3.14.7, 418,9 GB libres |
| **G8** | Integridad sin regresión (grep W0.6 y OpenAPI) | **PASS** | `integrity_grep_final_w0.txt`: README.md, `contracts/openapi/README.md` y `docs/arquitectura.md` sin cambios desde W0.6; `requirements-dev.txt` solo suma los pins de W0.8. No hay afirmaciones de probabilidad ni de calibración: las raíces §11.6 aparecen en negaciones, referencias a decisiones, la tabla legacy E5 y un ítem de nombre conocido (§6). OpenAPI 13/13 dentro de G2 |
| **G9** | Decisiones registradas: D-N3 y D-N13 bloquean; también D-N11, H14 y H3 | **PENDIENTE (humano)** | §4 |
| G10 | GO W1 explícito | Humano | — |

**Origen de cada gate:**
- G1–G5 y G7 provienen del mismo SHA de código, `7618cce`: G1/G2 en la nube, G3–G5 y G7 en el Omen.
- G6 proviene de `43c17fd` y sigue vigente por la regla de validez de evidencia Docker de `merge_gate.py`.

## 3. Incidentes durante W0 (instrumento, no producto)

| # | Incidente | Clasificación | Corrección | Registro |
|---|---|---|---|---|
| 1 | pytest completo falló en `test_no_hardcoded_firms_baseline_path_outside_firms_source`: `freeze_check.py` (W0.0) repetía la ruta FIRMS en un literal | Regresión de W0 (del instrumento) | `67a2ee2`: la ruta se lee de `firms_source.py`; el test existente pasa | Commit + gate `2c72343` |
| 2 | Primera corrida en el Omen (`43c17fd`): flyway FAIL porque el checker esperaba `1:true…` y Flyway guarda `001:true…` | HARNESS_FALSE_NEGATIVE | `df29550`: versiones derivadas de `db/migration` + comparación semántica; 19 tests de regresión | `host/43c17fd/` |
| 3 | Segunda corrida (`df29550`): OutDir, en OneDrive, desapareció a mitad de la corrida. Las escrituras lanzaban excepciones y produjeron un "PASS" engañoso y "no-assertions"; no hubo ZIP | HARNESS_EVIDENCE_OUTPUT_FAILURE | `7618cce`: `Save-Evidence` nunca lanza, un check con escritura fallida es FAIL, summary y manifest siempre se escriben, exit 3, aviso si OutDir está en OneDrive; 7 tests de evidencia + 1 guard estático + reproducción. El bloque de ejecución pasó a usar `%LOCALAPPDATA%` | `host/df29550/` |
| 4 | El saneamiento de rutas de la evidencia del gate usó marcadores `<…>` y dejó los XML junit/surefire mal formados | Defecto de saneamiento de la evidencia | `1e08aa1`: regeneración desde las salidas originales con marcadores `[…]`; se verificó que los 40 archivos solo cambian en el estilo del marcador (sin test nuevo) | READMEs de `gate/*` |

Ninguna corrección tocó V001–V003, el Modelo D, los artefactos de Hito 1, los
archivos protegidos de readiness ni la lógica científica.

**Residual del incidente 3 (no verificado por la evidencia):** la corrida `df29550`
pudo dejar un contenedor `sapi-w0-backend-*` sin eliminar, porque el `docker rm` del
`finally` podía saltarse. El bloque de `7618cce` elimina al inicio los `sapi-w0-*`
sobrantes, pero eso no quedó registrado en el ZIP. Para confirmarlo, en el Omen
(solo lectura): `docker ps -a --filter name=sapi-w0-`.

## 4. Decisiones pendientes para G9

Ninguna se da por aprobada. Todas esperan a Daniel.

| ID | Decisión | Recomendación | Si no se decide |
|---|---|---|---|
| **D-N3** (bloquea) | Llevar W0 a `main` como **un solo PR** (PR-W0) desde `chore/hito2-w0-gate`, lo que autoriza **abrirlo** | **Aprobar.** Abrir PR-W0 con merge commit para conservar los commits de evidencia. Su gate (Rev3 §22: W1 GATE GO + MERGE GATE) es el fallback en la nube **re-ejecutado sobre el HEAD posterior a las decisiones** + la evidencia Docker vigente de `7618cce` (G3–G5, G7) y `43c17fd` (G6). Si Actions se habilita, el run del PR suma | PR-W0 no se abre y W1 no arranca |
| **D-N13** (bloquea) | Régimen de cortes de la Revisión 3: C/B/A acumulativos con disparadores fechados. Reemplaza `decisiones-w0` §1/§3.4/§3.6 | **Aprobar.** El régimen anterior define cortes con "CI verde" (léase GitHub Actions), lo que hoy contradice C1 (Actions no es dependencia dura). El nuevo elimina cortes disparados por Actions, por profesores o por aceptación externa, y fija disparadores verificables con fecha | Sigue el régimen anterior, en conflicto con C1 |
| **D-N11** | El Centro de Control queda fuera del producto de Sprint 2 y sin cambios: sus archivos están en `OUTPUT_SOURCES`, congelados por F3–F4 | **Aprobar.** Evita tocar archivos hasheados y no aporta al vertical slice | Los congelamientos impiden tocarlo igual |
| **H14** | Prefijo de tags: lista finita `hito2-sprint2-rc1…rc5` y `hito2-sprint2-final` | **Aprobar `hito2-sprint2`.** Nota de transparencia: `scripts/merge_gate.py` (`TAG_PREFIX`) **ya implementa esta recomendación** como lista permitida, antes de la decisión. No se creó ningún tag y la recomendación sigue sin aprobar. Si se elige otro prefijo, se cambia `TAG_PREFIX`; es un cambio en `scripts/` que exige re-ejecutar el gate en la nube, pero la evidencia Docker sigue vigente | No se crea ningún tag; DEMO FREEZE y ACCEPTANCE FREEZE no podrían marcarse |
| **H3** | Runner de migraciones | **Flyway dentro de Spring Boot**, viable gracias a G5: Flyway 12.4.0 y `spring-boot-starter-flyway` 4.1.1 vienen del BOM (`spring_bom_coordinates.txt`); `locations` en `filesystem:` hacia `db/migration`; `validate-on-migrate`; **nunca `baselineOnMigrate`**; ITs con Testcontainers 2.0.5 y `postgis/postgis:15-3.4` | PR-3 (SAPI-59) no arranca |

**Después de que Daniel decida:**
1. El agente registra las decisiones en `docs/hito2/decisiones-w0.md`.
2. Ese commit toca `docs/`, así que no hereda el gate: se re-ejecuta el fallback en la nube (freeze, python, backend-unit) sobre el nuevo HEAD.
3. La evidencia Docker sigue vigente, porque `docs/` no está en sus rutas de validez.

## 5. Estado de los ítems W0

| Ítem | Estado | Nota |
|---|---|---|
| W0.1 decisiones | PARTIAL | Falta registrar D-N3, D-N13, D-N11, H14 y H3 (G9) |
| W0.2 contenedor ML | PASS | G3 |
| W0.3 backend: Maven + Docker | PASS | `w0/spring_*` + G4 |
| W0.4 Flyway real | PASS | G5 |
| W0.5 host | PASS | G7 |
| W0.6 integridad | PASS | G8 |
| W0.7 requerimientos | PARTIAL | Borrador. Las tres capas de objetivos y el mapeo a IL se completan en el carril C (no bloquea W1) |
| W0.8 OpenAPI | PASS | 13/13 dentro de G2 |
| W0.9 CI veraz + merge gate | PASS | `merge_gate.py`, `w0_host_checks.ps1`, `ci.yml`; 53 tests del harness (26 + 20 + 7) |
| W0.10 ADR + erratum | PARTIAL | Faltan las filas E11/E12 del erratum y la aceptación de los ADR (carril C, no bloquea W1) |
| W0.11 screencast de respaldo | PENDIENTE | Se graba en DEMO FREEZE; no es gate de W1 |
| W0.12 Docker en la nube | NO EJECUTADO | Contingencia opcional; no se cumplió ningún disparador T1/T2 |

## 6. Observaciones para W1 (no bloqueantes)

- **GitHub Actions sigue sin runs.** Toda la certificación usó el gate de respaldo, como prevé la Revisión 3 (C1). Habilitarlo es recomendable, no obligatorio.
- **Nombre del sistema:** `README.md:1` y `docs/arquitectura.md:3` dicen "Sistema de Alerta y Predicción de Incendios". Es una inconsistencia conocida (RUBRIC_CONFLICT_2), con errata planificada en PR-8. No afirma calibración.
- **La evidencia del host debe quedar fuera de OneDrive** (lección del incidente 3).
- **La recomendación del agente se calcula sobre G1–G9.** G10 es la decisión humana.

## 7. Recomendación (Revisión 3 §3.3)

**NO-GO W1 — G9 pendiente: D-N3 y D-N13 sin registrar.** Los gates técnicos G1–G8
están en PASS. La regla de la Revisión 3 §3.3 asigna NO-GO cuando G9 no está en
PASS, y en este momento lo único que falta son las decisiones de Daniel.

**Para pasar a `GO W1 RECOMMENDED`:**
1. Daniel registra D-N3 y D-N13. Conviene decidir también D-N11, H14 y H3; H3 es necesario antes de PR-3.
2. El agente registra las decisiones en `docs/hito2/decisiones-w0.md` y re-ejecuta el gate de respaldo en la nube sobre ese HEAD.
3. Con eso, G9 pasa a PASS y la recomendación cambia a `GO W1 RECOMMENDED`.
4. Daniel emite el GO W1 (G10).
5. Como primer paso de W1, se abre y se mergea PR-W0 con su merge gate, según la Rev3 §22.

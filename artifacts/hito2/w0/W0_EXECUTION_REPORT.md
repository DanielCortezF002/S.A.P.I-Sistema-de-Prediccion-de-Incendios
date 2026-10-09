# W0 EXECUTION REPORT — Sprint 2 / Hito 2

| Campo | Valor |
|---|---|
| Rama | `chore/hito2-w0-gate`. Baseline `cd6b58e` = `origin/main`, sin tocar |
| SHA certificado por el gate | `ec65008ad71ee3fd82bedb1f2e70620e19dc2b75`: registro de las decisiones G9. Respecto de `7618cce` solo cambia `docs/hito2/decisiones-w0.md` |
| SHA de la evidencia Docker | `7618cce00123ac0b3f0c18e2ba8ec6778f19059a` (G3–G5, G7) y `43c17fd` (G6), vigentes para `ec65008` según la regla de `merge_gate.py` |
| Commits posteriores a `ec65008` | Solo de evidencia (`artifacts/hito2/**`). Heredan el gate: `merge_gate.py --inherit ec65008` → PASS |
| Fecha | 2026-10-09 |
| Referencia | Revisión 3 (FINAL CONSENSUS DELTA): §3 W1 ENTRY GATE, §7 decisiones, §8 paquete de ejecución |
| Alcance | Solo W0. Sin W1, sin PR, sin merge, sin Jira, sin tags, sin W0.12 |

## 1. Veredicto

- **G1 a G9 están en PASS**, con evidencia reproducible y verificable por sha256.
- **W0 queda cerrado en ingeniería (G1–G8) y en gobernanza (G9).** Daniel aprobó las decisiones de G9 el 2026-10-09; quedan registradas en `docs/hito2/decisiones-w0.md` §4.
- **G10** es el GO W1 explícito de Daniel. Sigue pendiente.
- No hubo fallas del producto. Las **cuatro** fallas de W0 fueron del instrumento de medición o del saneamiento de su evidencia (§3). Las de código se corrigieron con tests de regresión; la #4 se corrigió regenerando los archivos y verificando el diff de marcadores.
- Las cuatro quedan registradas como historia.

## 2. W1 ENTRY GATE (Revisión 3 §3.2)

| Gate | Condición | Resultado | Evidencia |
|---|---|---|---|
| **G1** | Rama con push; `cd6b58e` ancestro; `freeze` F1–F9 en PASS sobre el HEAD | **PASS** | `ec65008` está en `origin`. `gate/ec65008/freeze_check.json` (modo gate, sin SKIP) y `freeze_check_8f3edab.{txt,json}`: freeze del HEAD de evidencia `8f3edab`, F1–F9 PASS sin `--allow-dirty` |
| **G2** | `freeze`, `python` y `backend-unit` en verde sobre el SHA (Rev3 §3.2) | **PASS** (fallback en la nube; Actions tiene 0 runs) | `gate/ec65008/`: pytest 1720 passed, 114 skipped, cobertura 84,56 %; `mvnw verify` 3/3; lint v2 limpio. Se re-ejecutó porque `docs/hito2/` no hereda el gate antes de CODE FREEZE (`inherit_from_7618cce.txt`: INHERIT FAIL). El veredicto agregado de `gate_summary.json` es `NOT_VERIFIABLE_IN_THIS_ENVIRONMENT` (exit 2) solo porque sus 3 jobs Docker no corren en la nube; esos jobs se cubren con G3–G6 |
| **G3** | `container-smoke` ML: 200, 50 celdas, fingerprint `33c2…31ff` | **PASS** | `host/7618cce/extracted/container-smoke-ml.json`: uid 10001, `relative_rank`, `scientific_model_validation=false`. Vigente para `ec65008` (`gate/ec65008/docker_evidence_validity.txt`) |
| **G4** | `container-smoke` backend: `/health` UP, usuario no root | **PASS** | `host/7618cce/extracted/container-smoke-backend.json` (uid 10001). Vigente para `ec65008` |
| **G5** | REAL FLYWAY INTEGRATION | **PASS** | `host/7618cce/extracted/flyway-integration.json`: Flyway 12.4.0, migrate 3 → validate e info OK → segundo migrate 0 pendientes; historial `001..003` (derivado y semántico); 50 celdas; 0 geometrías inválidas. Vigente para `ec65008` |
| **G6** | SQL MIGRATION VALIDATION (independiente de G5) | **PASS** | `host/43c17fd/extracted/sql-migration-validation*`. Vigente para `ec65008`: ni `db/` ni `sapi58_migration_integration.ps1` cambiaron |
| **G7** | Datos del host | **PASS** | `host/7618cce/extracted/hostfacts.json`: Docker 29.8.1, Compose 5.5.1, puertos libres, `sapi_pgdata` ausente, `core.autocrlf=false`, JDK 21, Python 3.14.7, 418,9 GB libres |
| **G8** | Integridad sin regresión (grep W0.6 y OpenAPI) | **PASS** | `integrity_grep_final_w0.txt`: README.md, `contracts/openapi/README.md` y `docs/arquitectura.md` sin cambios desde W0.6; `requirements-dev.txt` solo suma los pins de W0.8. No hay afirmaciones de probabilidad ni de calibración: las raíces §11.6 aparecen en negaciones, referencias a decisiones, la tabla legacy E5 y un ítem de nombre conocido (§6). Re-verificado sobre `ec65008`: en `decisiones-w0.md` solo aparecen las líneas previas de H6 (negación) y H17 (decisión abierta). OpenAPI 13/13 dentro de G2 |
| **G9** | Decisiones registradas: D-N3 y D-N13 bloquean; también D-N11, H14 y H3 | **PASS** | `docs/hito2/decisiones-w0.md` §4 (commit `ec65008`). Detalle en §4 |
| G10 | GO W1 explícito | **Pendiente (humano)** | — |

**Origen de cada gate:**
- G1, G2 y G9 provienen de `ec65008`, en la nube.
- G3–G5 y G7 provienen de `7618cce`, en el Omen. G6 proviene de `43c17fd`.
- Los tres son vigentes para `ec65008` por la regla de validez de evidencia Docker de `merge_gate.py`, porque entre esos SHA no cambió ninguna de sus rutas.

## 3. Incidentes durante W0 (instrumento, no producto)

| # | Incidente | Clasificación | Corrección | Registro |
|---|---|---|---|---|
| 1 | pytest completo falló en `test_no_hardcoded_firms_baseline_path_outside_firms_source`: `freeze_check.py` (W0.0) repetía la ruta FIRMS en un literal | Regresión de W0 (del instrumento) | `67a2ee2`: la ruta se lee de `firms_source.py`; el test existente pasa | Commit + gate `2c72343` |
| 2 | Primera corrida en el Omen (`43c17fd`): flyway FAIL porque el checker esperaba `1:true…` y Flyway guarda `001:true…` | HARNESS_FALSE_NEGATIVE | `df29550`: versiones derivadas de `db/migration` + comparación semántica; 19 tests de regresión | `host/43c17fd/` |
| 3 | Segunda corrida (`df29550`): OutDir, en OneDrive, desapareció a mitad de la corrida. Las escrituras lanzaban excepciones y produjeron un "PASS" engañoso y "no-assertions"; no hubo ZIP | HARNESS_EVIDENCE_OUTPUT_FAILURE | `7618cce`: `Save-Evidence` nunca lanza, un check con escritura fallida es FAIL, summary y manifest siempre se escriben, exit 3, aviso si OutDir está en OneDrive; 7 tests de evidencia + 1 guard estático + reproducción. El bloque de ejecución pasó a usar `%LOCALAPPDATA%` | `host/df29550/` |
| 4 | El saneamiento de rutas de la evidencia del gate usó marcadores `<…>` y dejó los XML junit/surefire mal formados | Defecto de saneamiento de la evidencia | `1e08aa1`: regeneración desde las salidas originales con marcadores `[…]`; se verificó que los 40 archivos solo cambian en el estilo del marcador (sin test nuevo) | READMEs de `gate/*` |

Ninguna corrección tocó V001–V003, el Modelo D, los artefactos de Hito 1, los
archivos protegidos de readiness ni la lógica científica.

**Residual del incidente 3 (no verificado, no bloqueante):** la corrida `df29550`
pudo dejar un contenedor `sapi-w0-backend-*` sin eliminar, porque el `docker rm` del
`finally` podía saltarse. El bloque de `7618cce` elimina al inicio los `sapi-w0-*`
sobrantes, pero eso no quedó registrado en el ZIP. Daniel decidió el 2026-10-09
que este chequeo no es un gate ni bloquea G9 ni W1. Queda como verificación
opcional de solo lectura en el Omen: `docker ps -a --filter name=sapi-w0-`.

## 4. Decisiones de G9

Daniel las aprobó el 2026-10-09 (mensaje "G9 — DECISIONES HUMANAS APROBADAS").
Quedan registradas en `docs/hito2/decisiones-w0.md` §4 (commit `ec65008`).

| ID | Decisión aprobada | Registro |
|---|---|---|
| **D-N3** (bloqueaba) | W0 llega a `main` como **un único PR** (PR-W0) desde `chore/hito2-w0-gate`. No se abre hasta registrar las decisiones y re-ejecutar el gate (hecho: `ec65008`, `gate/ec65008/`), y Daniel indicó además esperar su GO W1. El método de merge lo decide Daniel al mergear; la recomendación del agente es merge commit | §4.1 |
| **D-N13** (bloqueaba) | Régimen de cortes de la Revisión 3, con la precisión de Daniel: GitHub Actions **no** es dependencia dura; "CI verde" = **MERGE GATE** (Actions si está disponible; si no, el fallback reproducible equivalente); ningún corte A/B/C se activa solo porque Actions esté deshabilitado o no tenga runs. Reemplaza `decisiones-w0` §1 (fallback y Ruta C) y §3.4/§3.6, que se conservan marcados como historia | §4.2 |
| **D-N11** | El Centro de Control queda fuera del producto de Sprint 2 y no se modifica | §4 (tabla) |
| **H14** | Prefijo `hito2-sprint2`; lista finita `rc1…rc5` y `final`. Coincide con `TAG_PREFIX`/`ALLOWED_TAGS` de `merge_gate.py`, presentes desde antes de la decisión; no hizo falta cambiar código. No se crea ningún tag hasta que el flujo lo pida | §4.3 |
| **H3** | Flyway dentro de Spring Boot sobre `db/migration`; `validate`/`migrate` reales; **nunca `baselineOnMigrate`**; PostgreSQL/PostGIS; ITs con Testcontainers; SQL migration validation separada de Flyway integration. Cierra la condición del 2026-10-08 (G5 PASS) | §4.4 |

**Cómo se re-validó después de registrar las decisiones:**
1. `ec65008` toca `docs/hito2/`, que antes de CODE FREEZE no hereda el gate: `--inherit 7618cce` → INHERIT FAIL.
2. Se re-ejecutó el fallback completo sobre un clon limpio de `ec65008`: `freeze`, `python` y `backend-unit` en PASS (`gate/ec65008/`).
3. `--evidence-valid`: `container-smoke` y `flyway-integration` (7618cce) y `sql-migration-validation` (43c17fd) → VIGENTE.
4. `8f3edab`, commit de evidencia del gate, hereda `ec65008` (`--inherit` → PASS). `freeze_check` sobre `8f3edab`: F1–F9 PASS (`freeze_check_8f3edab.*`).

## 5. Estado de los ítems W0

| Ítem | Estado | Nota |
|---|---|---|
| W0.1 decisiones | PASS | H0–H17 (2026-10-08) + G9: D-N3, D-N13, D-N11, H14 y H3 (2026-10-09) |
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

- **GitHub Actions sigue sin runs.** Toda la certificación usó el gate de respaldo, como prevén la Revisión 3 (C1) y D-N13. Habilitarlo es recomendable, no obligatorio.
- **Nombre del sistema:** `README.md:1` y `docs/arquitectura.md:3` dicen "Sistema de Alerta y Predicción de Incendios". Es una inconsistencia conocida (RUBRIC_CONFLICT_2), con errata planificada en PR-8. No afirma calibración.
- **La evidencia del host debe quedar fuera de OneDrive** (lección del incidente 3).
- **La recomendación del agente se calcula sobre G1–G9.** G10 es la decisión humana.
- **Plazos de la Revisión 3 §3.3 y del régimen D-N13:** el objetivo era dejar el gate listo el vie 09 a las 20:00 para mergear PR-W0 en la ventana de 21:00–22:00; el límite es el sáb 10 a las 10:00. El disparador A1 no aplica, porque exige Docker inviable en todos los entornos. A3 corre aparte: PR-2 debe mergearse a más tardar en la ventana del dom 11, 09:00–10:00.

## 7. Recomendación (Revisión 3 §3.3)

**GO W1 RECOMMENDED.** G1–G9 están en PASS: G1–G8 con evidencia técnica
reproducible y G9 con las cinco decisiones aprobadas por Daniel y registradas
en `ec65008`. El gate se re-ejecutó sobre ese commit.

Falta solo G10, el GO W1 explícito de Daniel. Hasta entonces no se inicia W1,
no se abre PR-W0 y no se modifica Jira.

**Después del GO W1** (Revisión 3 §22 y D-N3):
1. Se abre PR-W0 desde `chore/hito2-w0-gate`. Su gate es `gate/ec65008/` más la evidencia Docker vigente; si el HEAD trae commits nuevos que no sean de evidencia, se re-ejecuta.
2. Daniel lo mergea en una ventana y elige el método.
3. W1 arranca con PR-1 y PR-2, según el calendario de la Revisión 3.

**Historial de la recomendación:**

| Commit | Recomendación |
|---|---|
| `edb5097` | NO-GO W1 — G9 pendiente: D-N3 y D-N13 sin registrar (G1–G8 PASS) |
| este reporte | GO W1 RECOMMENDED — G1–G9 PASS tras registrar las decisiones G9 en `ec65008` y re-ejecutar el gate |

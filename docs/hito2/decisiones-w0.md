# S.A.P.I. — Decisiones del Quality Gate W0 (W0.1)

Registro de las decisiones H0–H17 del plan de Hito 2 tal como quedaron al
autorizarse W0 (mensaje "EXECUTION AUTHORIZATION: GO W0 ONLY" de Daniel,
2026-10-08). Este archivo es la evidencia de W0.1. No crea decisiones nuevas:
las aclaraciones de la sección 3 vienen de la revisión adversarial del plan y
corrigen inconsistencias internas, sin cambiar lo aprobado.

La sección 4 registra las decisiones que Daniel aprobó el 2026-10-09 para el
gate G9 de W1 (D-N3, D-N13, D-N11, H14 y H3). Las secciones 1–3 se conservan
como registro histórico; donde D-N13 las reemplaza, se indica en el lugar.

Clases: **A**, adoptada según el plan; **B**, requiere validación de Daniel
antes de W1; **C**, requiere información externa (profesor); **D**, diferible
(se indica plazo).

## 1. Ruta y alcance

> **Reemplazado en parte por D-N13 (2026-10-09, §4.2).** Ya no rigen las viñetas
> de fallback ("Ruta B"), de "Ruta C" ni la frase "se planifica para el CUT B y
> se conserva el CUT A como respaldo". El antiguo "Ruta B" corresponde al nuevo
> **CUT A**. El resto de esta sección no cambia con D-N13.

- **Ruta principal:** A, walking skeleton / vertical slice reproducible.
- **Fallback:** Ruta B (backend + persistencia + evidencia) si el calendario o
  un riesgo técnico impiden cerrar la Ruta A.
- **Ruta C:** solo si un spike demuestra que la Ruta A es técnicamente
  inviable.
- **Congelados hasta después de la presentación:** SAPI-49, 63, 64, 65, 67,
  68; el Orquestador de IAs; todo el stretch.
- **Fecha de presentación y entregables:** desconocidos. Se planifica para el
  CUT B y se conserva el CUT A como respaldo.

## 2. Decisiones

| ID | Decisión | Estado al 2026-10-08 | Clase |
|---|---|---|---|
| H0 | Materializar el checkpoint `cd6b58e` | Abierta. Se decide después de W0 (tag anotado y/o nota de checkpoint) | D |
| H1 | Fecha, entregables y feedback del Hito 1 | Abierta; consulta al profesor pendiente fuera del repo | C |
| H2 | Semántica de `GET /api/v1/ranking` | **Aprobada:** write-through según `backend.v0`, más `GET /api/v1/ranking/latest` aditivo desde la persistencia | B → aprobada |
| H3 | Runner de migraciones | **Aprobada con condición:** primero W0.4. Si W0.4 pasa, Flyway dentro de Spring sobre `db/migration`. Si falla por una incompatibilidad estructural, STOP y se presenta la evidencia antes de adoptar otra alternativa. Nunca `baselineOnMigrate` para ocultar un esquema incompatible | B → condicionada a W0.4 |
| H4 | Base v2 y servicios legacy en Compose | **Aprobada:** base v2 en un volumen nuevo y aislado; no se reutiliza `sapi_pgdata`; no se borra el legacy; se mantienen los bloques de Compose protegidos por tests; legacy y ops quedan fuera de la ruta v2 | B → aprobada |
| H5 | Auditoría por request (V004) | **Aprobada:** forma parte del diseño objetivo. Si el calendario obliga, es el primer candidato a simplificar; no se recorta en W0 | B → aprobada |
| H6 | Contrato v0.2 | **Aprobada para diseño y validación en W0:** aditivo, con campos de procedencia y frescura; el score no se convierte en probabilidad; no se exponen features internas por celda; no se rompe la compatibilidad v0. La implementación pertenece a W1 | B → aprobada |
| H7 | Vistas legacy de Streamlit | **Aprobada:** la vista v2 será la vista por defecto; los modos legacy quedan detrás de `SAPI_UI_LEGACY_MODES=1`; no se borran | B → aprobada |
| H8 | Modo de datos por defecto | Adoptada: reproducible | A |
| H9 | SAPI-43 / SAPI-71 | Abierta; plazo: antes de PR-7 (W2). Default: PARTIAL honesto | D |
| H10 | Política ante falla de persistencia | Adoptada: fail-closed | A |
| H11 | CI | **Aprobada:** lint bloqueante en rutas v2; deuda legacy cuantificada y no bloqueante; Maven verify; validación de migraciones; sin reformateo masivo; sin tocar `OUTPUT_SOURCES`. Pendiente que Daniel confirme si Actions está habilitado | B → aprobada |
| H12 | Acoplamiento `ml_api` → `tools.n8n_bridge.contract` | Adoptada: se mantiene con allowlist y ADR; refactor después del Hito 2 | A |
| H13 | Higiene de Jira | Abierta; plazo W3. Solo Daniel escribe en Jira | D |
| H14 | Nombre del tag | Abierta; plazo W3 | D |
| H15 | Máquina de demo | Abierta; plazo: antes del ensayo general | D |
| H16 | Higiene del repo (`.cursorrules`, PNG sin fuente) | Abierta; plazo W3 | D |
| H17 | Textos "Probabilidad" del modo Demo legacy | Abierta; plazo W3. Mientras tanto, oculto detrás de H7 | D |

Actualización 2026-10-09: H3 y H14 quedaron aprobadas en G9 (§4). La columna
de estado de esta tabla refleja el 2026-10-08 y no se reescribe.

## 3. Aclaraciones de la revisión adversarial del plan

La revisión independiente del plan aprobado encontró inconsistencias
internas. Se corrigen así, sin cambiar las decisiones de la sección 2.

1. **H3, alternativa según el modo de falla de W0.4.**
   - Falla solo la integración con Spring (ITs de PR-3): contenedor Flyway
     one-shot.
   - Falla por objetos de la imagen postgis en el esquema `public`: esquema
     propio (`flyway.schemas`) o imagen postgres con PostGIS habilitada por
     V001, documentado en un ADR.
   - Error SQL en V001–V003: STOP, porque están congeladas.

   En los tres casos se presenta la evidencia a Daniel antes de adoptar la
   alternativa, como exige su aprobación condicional.
2. **W0.2 frente al gate de W1.** Si W0.2 falla, el resultado es NO-GO W1: se
   corrige el Dockerfile dentro de W0, se re-ejecuta W0.2 y, si no se logra,
   se evalúa la Ruta B. La "continuación de SAPI-57 contra un ML mockeado" ya
   no es una opción automática.
3. **Alcance de PR-1 (W1).** `_ranking` construye `RankingResult`, cuyo
   modelo Pydantic ignora campos extra. Emitir los campos v0.2 exige agregar
   campos opcionales a la clase `RankingResult`. La verificación de freeze F4c
   (`scripts/freeze_check.py`) ya acepta campos nuevos en esa clase y falla si
   se altera o elimina un campo existente.
4. *(Reemplazada por D-N13, §4.2.)* **CUT C sin stretch.** El CUT C es el CUT B más endurecimiento (corrida
   operacional de SAPI-43 si SAPI-71 se ejecutó, CI verde, ensayos). El
   stretch sigue congelado hasta después de la presentación.
5. **Tags y freeze check.** F1 acepta los 6 tags fijados más los que Daniel
   autorice (`--allow-tag`). Un tag nuevo no autorizado es FAIL.
6. *(Reemplazada por D-N13, §4.2.)* **Disparador de la Ruta B** (default propuesto; Daniel lo confirma cuando
   se conozca H1): el gate de W1 no da GO a más tardar 6 días hábiles antes
   de la presentación, o PR-3 no está mergeado 4 días hábiles antes. En ese
   caso, la Ruta B es PR-2 + PR-3 (+ `/latest`) más evidencia, y SAPI-60, 61
   y 66 se declaran pendientes.
7. **SAPI-57.CA1.** El plan usa `RestClient`, sucesor síncrono de
   `RestTemplate` en Spring 6+/Boot 4. Daniel acepta esta lectura o ajusta la
   redacción en Jira (anotado en `requerimientos-sprint2.md`).
8. **Rutas congeladas adicionales.** `HealthController.java` y
   `app/components/prototype_view.py` quedan protegidos en F4. El historial de
   cambios de Hito 2 vive en `docs/hito2/`, no en
   `docs/change-log-posthito1.md`, que sigue congelado.

## 4. Decisiones del gate G9 de W1 (2026-10-09)

Fuente: mensaje "G9 — DECISIONES HUMANAS APROBADAS" de Daniel, 2026-10-09,
emitido después del W0 EXECUTION REPORT
(`artifacts/hito2/w0/W0_EXECUTION_REPORT.md`). Referencia: Revisión 3 (FINAL
CONSENSUS DELTA) §2.1, §3 y §7. Daniel aprobó las cinco; el agente solo las
registra. Ninguna autoriza por sí sola iniciar W1, abrir PR-W0, crear tags ni
modificar Jira.

| ID | Decisión | Estado |
|---|---|---|
| D-N3 | W0 llega a `main` como **un único PR** (PR-W0) desde `chore/hito2-w0-gate` | **Aprobada.** Condiciones de apertura en §4.1 |
| D-N13 | Régimen de cortes de la Revisión 3, con la precisión de Daniel sobre "CI verde" | **Aprobada con precisión.** Ver §4.2 |
| D-N11 | El Centro de Control queda fuera del producto de Sprint 2 y no se modifica | **Aprobada** |
| H14 | Prefijo de tags `hito2-sprint2`, lista finita | **Aprobada.** Ver §4.3 |
| H3 | Runner de migraciones: Flyway dentro de Spring Boot | **Aprobada** (cierra la condición del 2026-10-08: G5 en PASS). Ver §4.4 |

### 4.1 D-N3: PR-W0

- Un solo PR desde `chore/hito2-w0-gate` hacia `main`, con los commits
  granulares de W0.
- No se abre hasta que estas decisiones estén registradas y el gate final se
  haya re-ejecutado sobre el commit que las registra. Además, Daniel indicó no
  abrirlo hasta su GO W1 explícito.
- Su gate es el de la Revisión 3 §3.1 para PR-W0: `freeze`, `python` y
  `backend-unit` en verde sobre el SHA head (Actions o fallback reproducible),
  más G3–G6 con evidencia Docker vigente.
- El método de merge lo decide Daniel al mergear. La recomendación del agente
  es un merge commit, que conserva los commits de evidencia.

### 4.2 D-N13: régimen de cortes

Reemplaza el régimen de la sección 1 (fallback "Ruta B", "Ruta C") y las
aclaraciones 3.4 y 3.6. El antiguo "Ruta B" corresponde al nuevo **CUT A**.

**Regla obligatoria (precisión de Daniel):**
- GitHub Actions **no** es dependencia dura.
- Toda referencia a "CI verde" se interpreta como **MERGE GATE**: GitHub Actions
  cuando esté disponible; el fallback reproducible equivalente
  (`scripts/merge_gate.py` y `scripts/w0_host_checks.ps1`, con los mismos jobs y
  criterios) cuando no lo esté.
- Ningún corte A, B o C puede activarse únicamente porque GitHub Actions esté
  deshabilitado o no tenga runs.

**Reglas del régimen:**
- Los cortes son acumulativos: A ⊇ B ⊇ C.
- Se activa el más severo cuyo disparador se haya cumplido.
- Nunca se recorta de forma preventiva.
- Lo activa Daniel por escrito, en este registro y en Jira.
- Ningún corte se dispara porque Actions esté deshabilitado, porque los
  profesores no respondan o porque no haya aceptación externa.

| Corte | Disparador (hora de Chile) | Alcance |
|---|---|---|
| **C** | SAPI-71 Attempt 2 sin éxito al mar 13, 12:00; o corrida operacional sin evidencia al jue 15, 14:00 | FULL salvo la corrida operacional de SAPI-43, que queda PARTIAL con el mecanismo probado y el 503 auditado |
| **B** | B1: PR-3 no mergeado al lun 12, 23:59. B2: E2E no verde sobre el SHA candidato (head de PR-6 rebasado sobre `main`) al mié 14, 18:00 | C + persistencia sin V004 (auditoría por logs, brecha declarada en ADR-007) y/o E2E manual guionado en lugar del automatizado |
| **A** | A1: NO-GO W1 al sáb 10, 10:00 por Docker inviable en todos los entornos (T1 cumplido y W0.12 negado o fallido) | B + SAPI-57 y SAPI-61 demostrados en ejecución nativa sin contenedores (UI ↔ Spring ↔ ML), tests unitarios y de contrato, validación SQL estática y evidencia de diseño. Pendientes: SAPI-59 en ITs, SAPI-60, SAPI-66 y la corrida SAPI-43 |
| | A2: G5 (Flyway real) en FAIL sin alternativa H3 al sáb 10, 10:00 | B + SAPI-59 pendiente. Compose sin base v2 |
| | A3: PR-2 no mergeado en la ventana del dom 11, 09:00–10:00 | B + backend y persistencia con ITs (Actions o Windows/Omen) + corrida grabada. Pendientes: SAPI-60, 61 y 66 |

Regla adicional (Revisión 2 §27, sin cambios en la Revisión 3): si el
ACCEPTANCE FREEZE no se cumple al sáb 17, 12:00, se congela lo que esté DONE y
se activa el corte que corresponda.

Estado al registrar: el disparador A2 no se cumple, porque G5 está en PASS
(`artifacts/hito2/w0/host/7618cce/`).

### 4.3 H14: tags

- Prefijo `hito2-sprint2`. Lista finita: `hito2-sprint2-rc1`,
  `hito2-sprint2-rc2`, `hito2-sprint2-rc3`, `hito2-sprint2-rc4`,
  `hito2-sprint2-rc5` y `hito2-sprint2-final`.
- Un tag nunca se mueve: un fix crea el siguiente rc.
- Es la lista que el job `freeze` ya admite (`TAG_PREFIX` y `ALLOWED_TAGS` en
  `scripts/merge_gate.py`, presentes desde antes de esta decisión).
- No se crea ningún tag hasta que corresponda según el flujo: `rc1` en DEMO
  FREEZE y `final` en ACCEPTANCE FREEZE.

### 4.4 H3: Flyway dentro de Spring Boot

Base: G5 en PASS. Flyway 12.4.0 real aplicó V001–V003 sobre
`postgis/postgis:15-3.4`; `validate` OK; segundo `migrate` sin pendientes.

Condiciones aprobadas:
- Usar las migraciones versionadas de `db/migration`. V001–V003 siguen
  congeladas.
- `validate`/`migrate` reales.
- **Nunca `baselineOnMigrate`.**
- Integración con PostgreSQL/PostGIS.
- ITs con Testcontainers.
- SQL MIGRATION VALIDATION (`sql-migration-validation`) se mantiene separada de
  REAL FLYWAY INTEGRATION (`flyway-integration` y `backend-it`). Ninguna
  sustituye a la otra, y la validación SQL nunca cierra un CA de Flyway.

Referencia de implementación para PR-3 (recomendación del agente, se concreta
en ese PR):
- Flyway 12.4.0 y `spring-boot-starter-flyway` 4.1.1 desde el BOM de Spring
  Boot.
- `locations` en `filesystem:` hacia `db/migration`.
- `validate-on-migrate`.
- Testcontainers 2.0.5 con `postgis/postgis:15-3.4`.

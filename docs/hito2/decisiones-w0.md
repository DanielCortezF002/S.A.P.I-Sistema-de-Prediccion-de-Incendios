# S.A.P.I. — Decisiones del Quality Gate W0 (W0.1)

Registro de las decisiones H0–H17 del plan de Hito 2 tal como quedaron al
autorizarse W0 (mensaje "EXECUTION AUTHORIZATION: GO W0 ONLY" de Daniel,
2026-10-08). Este archivo es la evidencia de W0.1. No crea decisiones nuevas:
las aclaraciones de la sección 3 vienen de la revisión adversarial del plan y
corrigen inconsistencias internas, sin cambiar lo aprobado.

Clases: **A**, adoptada según el plan; **B**, requiere validación de Daniel
antes de W1; **C**, requiere información externa (profesor); **D**, diferible
(se indica plazo).

## 1. Ruta y alcance

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
4. **CUT C sin stretch.** El CUT C es el CUT B más endurecimiento (corrida
   operacional de SAPI-43 si SAPI-71 se ejecutó, CI verde, ensayos). El
   stretch sigue congelado hasta después de la presentación.
5. **Tags y freeze check.** F1 acepta los 6 tags fijados más los que Daniel
   autorice (`--allow-tag`). Un tag nuevo no autorizado es FAIL.
6. **Disparador de la Ruta B** (default propuesto; Daniel lo confirma cuando
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

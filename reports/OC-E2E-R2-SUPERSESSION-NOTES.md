# Notas de supersesión y reconciliación documental — E2E 2026-10-24 (R2)

**Fecha:** 2026-10-24 (UTC)  
**Alcance:** reconciliar las afirmaciones de cuatro cuerpos documentales sin
modificar los registros históricos.  
**Regla:** este documento **no** cambia Gate B, no cierra Jira, no reescribe
historia y no sustituye una decisión del Product Owner.

---

## 1. Corpus y coordenadas

| Documento | Fecha | Commit / workspace | Veredicto que declara |
|---|---|---|---|
| `SAPI_SPRINT2_CLOSEOUT_REPORT.md` | 16-oct-2026 | base `8982e58`; cierres `4ef54e7` (E2E) y `8bd7ba1` | “VERTICAL SLICE ACADÉMICO VALIDADO”; SAPI-43 PASS (`firms_origin=current`); SAPI-66 PASS (897,4 / 1.952,5 ms) |
| `docs/hito2/INFORME_HITO2_FINAL.md` | 15-oct-2026 | candidato `d11428a`, tree `e4b50cf` | No hay PASS global; SAPI-43 PARTIAL/BLOCKED_EXTERNAL; SAPI-66 CA1–CA4 verificados y CA5 “resuelto por decisión formal del PO” |
| `recovery-evidence/01-DIAGNOSTICO-CA.md` y anexos | 24-oct-2026 | HEAD `51ec3c06` | Gate B **NO GO** (3 PASS, 2 CONDICIONADO, 3 PARCIAL, 4 NO EJECUTADO); CA2 PARCIAL; CA4 PARCIAL/CONDICIONADO; CA5 NO ACREDITADO; SAPI-43 CONDICIONADO/PARCIAL |
| `reports/OC-E2E-20261024-CERTIFICACION.md` (R2) | 24-oct-2026 | base `eb1b370`; aplicación `2a71c7e` | CA1/CA3/CA4 PASS E2E; **CA2 PARCIAL**; CA5 BLOQUEADO; SAPI-43 no acreditado; Gate B NO GO sin cambios |

Las cuatro piezas no describen la misma corrida. El commit, el workspace y el
arnés cambian; por eso sus números y estados no son intercambiables.

---

## 2. Contradicciones y resolución

### 2.1 SAPI-43: PASS/`current` vs PARTIAL/BLOCKED vs CONDICIONADO

- **Closeout (16-oct):** PASS con `firms_origin=current`, 50 filas persistidas.
- **Informe Hito 2 (15-oct):** PARTIAL/BLOCKED_EXTERNAL; no hay refresh
  operacional nuevo ni credenciales.
- **Recovery (24-oct):** CONDICIONADO/PARCIAL; SAPI-71 Attempt 2 sigue
  `NOT STARTED`.
- **R2 (24-oct):** no acreditado para SAPI-43; la corrida usa
  `firms_origin=reproducibility`.

**Resolución:** el PASS del closeout corresponde a una corrida operacional
histórica sobre `8982e58`, con stores y evidencia de otra fecha. La corrida del
24-oct no re-ejecutó SAPI-71 ni produjo stores `current`; por tanto **no
re-acredita SAPI-43**. Su valor histórico se conserva, pero no se puede citar
como estado vigente ni para cerrar el issue. Gate B sigue NO GO.

### 2.2 SAPI-66: PASS global vs “no PASS global”

- **Closeout:** SAPI-66 PASS, benchmark 897,4 ms cold / 1.952,5 ms update.
- **Informe Hito 2:** “No se declara PASS global del gate”; el freeze falla por
  tres causas.
- **Recovery:** CA5 NO ACREDITADO (no literal); CA2 y CA4 PARCIALES.
- **R2:** CA1/CA3/CA4 acreditados; CA2 PARCIAL; CA5 BLOQUEADO; SAPI-66 abierto.

**Resolución:** no hay base para declarar SAPI-66 cerrado. El “PASS” del closeout
es un veredicto histórico de alcance académico que **precede** a la auditoría
estricta de CA2/CA4 y al hallazgo del arnés CA4 sin gate de caché fría. Se
conserva como registro, no como estado actual. Gate B no se promueve.

### 2.3 CA5 literal: “resuelto por el PO” vs NO ACREDITADO vs BLOQUEADO

- **Informe Hito 2:** afirma que CA5 literal se resolvió mediante una alternativa
  aprobada por el Product Owner (bootstrap seguro).
- **Recovery:** NO ACREDITADO (NO LITERAL): `web-v2` no está en la ruta por
  defecto y W3 usó profile + overrides.
- **R2:** BLOQUEADO; no se ejecutó `docker compose up` literal.

**Resolución:** la afirmación del Informe Hito 2 es una decisión de gobernanza,
no evidencia técnica. En este workspace no se adjunta el acta, comentario de
Jira ni resolución que la formalice. Hasta que exista y se incorpore a la matriz
de Gate B, **CA5 literal permanece pendiente/bloqueado**. No se usa el Informe
Hito 2 para declarar CA5 cumplido.

### 2.4 CA2: PASS E2E vs PARCIAL

- **R1 (informe anterior):** declaraba CA2 PASS E2E con la matriz negativa y la
  validación del payload final.
- **Recovery:** PARCIAL: falta el reporte E2E de errores en **cada** salto.
- **R2:** PARCIAL explícito; se agregan contratos reales 200/422 en FastAPI y
  backend, pero no se observa el cuerpo de las peticiones entre servicios.

**Resolución:** la lectura de Recovery era correcta. R2 corrige la
sobredeclaración: valida cada servicio en su frontera, no el “por salto” completo.
Para pasar a total haría falta un proxy/tap o instrumentación equivalente.

### 2.5 CA4: 897,4/1.952,5 ms vs PARCIAL vs R1 vs R2

- **Closeout (16-oct):** 897,4 ms cold / 1.952,5 ms update, con
  `scripts/measure_browser_e2e_d21.py` sobre `8982e58`.
- **Recovery:** PARCIAL/CONDICIONADO; faltaba un `timings.csv` consolidado por
  salto y una recaptura que discriminara update de cached.
- **R1 (24-oct, 22:17 UTC):** 6.065,26 / 2.649,82 / 893,25 ms con Playwright +
  Edge; caché fría preparada **a mano** fuera del test.
- **R2 (24-oct, 23:50 UTC):** 6.867,90 / 3.723,47 / 424,06 ms; `web-v2` se
  reinicia dentro del test y hay gates duros.

**Resolución:** son mediciones de arneses, fechas y alcances distintos; no se
comparan ni se promedian. Los 897,4/1.952,5 ms siguen siendo válidos solo para
`measure_browser_e2e_d21.py` en la corrida del closeout. R1 queda superado por
R2 porque su arnés no imponía la condición de caché fría. Ninguna de las cifras
es un SLA ni una medición de producción.

### 2.6 CA1: “NO ACREDITADO” en Recovery vs tests presentes en R2

- **Recovery (HEAD `51ec3c06`):** `tests/e2e/test_vertical_slice.py` y
  `scripts/e2e_slice.py` no existían en ese árbol.
- **R2 (base `eb1b370`):** `tests/e2e/test_vertical_slice.py` existe y pasa
  5/5; se agregan las suites full-stack.

**Resolución:** no hay contradicción real: son árboles distintos. Los tests
nuevos **no modifican** el candidato protegido `51ec3c06`; son evidencia
adicional en otra rama. Que CA1 esté acreditado en R2 no re-acredita el
candidato ni cambia su estado.

### 2.7 Pruebas históricas vs pruebas del 24-oct

| Bloque | Fecha | Qué es | Uso válido |
|---|---|---|---|
| Closeout (`4ef54e7`/`8bd7ba1`) | 16-oct | Benchmark y persistencia de la corrida de cierre | Registro histórico; no estado vigente |
| Informe Hito 2 (`d11428a`) | 15-oct | Redacción académica y matriz de riesgos | Registro histórico; no evidencia E2E nueva |
| Recovery (`51ec3c06`) | 24-oct | Diagnóstico de evidencia, sin re-ejecutar E2E | Fuente del veredicto Gate B NO GO |
| R1 (`426605f`) | 24-oct | E2E real con caché fría manual | Evidencia válida salvo CA4; reemplazada por R2 |
| R2 (`eb1b370` + commit R2) | 24-oct | E2E real con gates duros y contratos por servicio | Evidencia vigente de este paquete |

---

## 3. Qué sigue siendo autoritativo

1. **Gate B:** la matriz citada por Recovery (NO GO) sigue siendo la referencia;
   R2 no la modifica.
2. **Jira:** ningún issue se cierra, transiciona o comenta por este trabajo.
3. **Candidato protegido:** `51ec3c06` no se modifica; R2 no lo re-acredita.
4. **Modelo D / contratos:** sin cambios; `scientific_model_validation=false` y
   `score_semantics=relative_rank` se mantienen.
5. **Evidencia E2E del 24-oct:** para CA1/CA3/CA4 vale R2; para CA2 vale
   PARCIAL; para CA5 y SAPI-43 no hay evidencia nueva que permita cerrar.

---

## 4. Autorizaciones humanas pendientes

1. **Privacidad histórica:** decidir si se cierra/abandona PR #41 y la rama R1,
   si se reescribe historia con `force-push` o si se solicita purga a GitHub.
   Sin esa decisión, la exposición de `426605f` sigue abierta.
2. **Aceptación de R2:** revisar y fusionar (o rechazar) la PR de sustitución;
   PR #41 queda como histórica y no debe fusionarse.
3. **CA5 literal:** aportar el acto formal del PO o mantener el bloqueo; no se
   infiere de una narrativa.
4. **SAPI-43:** autorizar SAPI-71 Attempt 2 con credenciales y stores `current`
   si se quiere una corrida operacional.
5. **CA2 total:** autorizar un proxy/tap de captura entre saltos si se exige
   validación de contrato “por salto” completa.
6. **Gate B / Jira / nota:** cualquier promoción, cierre o recálculo requiere
   decisión humana y no forma parte de este paquete.

---

## 5. Nota de no modificación

`SAPI_SPRINT2_CLOSEOUT_REPORT.md`, `docs/hito2/INFORME_HITO2_FINAL.md` y
`recovery-evidence/` **no fueron editados**. Se conservan intactos como registros
históricos. Este documento solo explicita sus coordenadas, sus contradicciones y
cuál es la lectura vigente para la evidencia E2E del 24-oct-2026.

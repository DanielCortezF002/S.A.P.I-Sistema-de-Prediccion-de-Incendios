# Matriz de cumplimiento verificada — Rúbricas Hito 2 (Directiva 30/32)

> **Corrección posterior (Directiva 34, 15-10-2026):** las referencias de
> este documento a "B1/B2/B3 siguen abiertos" están **desactualizadas**. Se
> verificó que esos tres defectos ya habían sido remediados y verificados
> desde el 12-10-2026 (commit `4012fbf`), antes de que esta cadena de
> directivas comenzara. Ver `docs/evidence/b1-b2-b3-estado-real-20261015/README.md`
> para la corrección completa con evidencia ejecutada. Las matrices
> **finales y vigentes** están en `docs/hito2/MATRIZ_RUBRICA_CESAR_FINAL.md`
> y `docs/hito2/MATRIZ_RUBRICA_MATIAS_FINAL.md`; este archivo se conserva
> como registro histórico del proceso, no como la calificación vigente.

Candidato evaluado: commit `c0f78a6` (rama `release/sprint2-closeout-candidate`,
clon `C:\SAPI-S2-CLOSEOUT-CLAUDE-20261015`). Revisión Directiva 32: esta
versión **reemplaza** la matriz de César de la Directiva 30, que fue
construida sin encontrar el archivo real — ahora localizado y usado.

**Método:** cada fila usa evidencia re-verificada con comandos ejecutados,
exit codes, logs, o archivos creados en esta sesión (DER, documento de
reconciliación arquitectónica). Donde el informe previo de Antigravity
afirmaba "SOBRESALIENTE (100%)" sin re-ejecución, se corrige al nivel que la
evidencia real sustenta. Una subida de nivel respecto a la matriz anterior
(Directiva 30) solo ocurre cuando hubo una acción ejecutada y verificable en
esta sesión (comentario Jira con reconciliación real, archivo DER nuevo,
corrida de gate repetida) — nunca solo por mejor redacción.

Fuentes de rúbrica verificadas en disco:
- Matías — 8 criterios, pesos exactos: `C:\SAPI-HITO2-FUENTES\rubrica sprint 2 matias.md`.
- César — 6 criterios, pesos exactos (localizado en la Directiva 32, no
  disponible en la búsqueda de la Directiva 30):
  `C:\Users\danie\OneDrive\Documentos\rubricas de sprint 2 sapi\rubrica sprint 2 cesar.md`
  (fuente: *Syllabus Seminario de Licenciatura 2026·V2*, cátedra César,
  asignatura INSW421, AE2/IL2.1-2.4 + 2 ejes transversales).

---

## A. Rúbrica de Matías — 8 criterios técnicos ponderados (100%)

| # | Criterio | Peso | Evidencia real | Brecha restante | Acción ejecutada | Nivel | Referencia |
|---|---|---|---|---|---|---|---|
| 1 | Incremento funcional del Sprint 2 | 20% | 9/14 historias DONE (37/58 SP); E2E real Streamlit→Spring→FastAPI→PostGIS; CA4 real 1.7s; **CA5 de SAPI-66 ahora formalmente resuelto** (PO aprobó `bootstrap_compose_v2.py` como alternativa, Jira `#10156`, sin alterar el CA original). | SAPI-43 sigue bloqueado pendiente de decisión humana + credenciales; SAPI-66 aún requiere validar independientemente sus demás CA (E2E con datos reales, dependencia SAPI-43/71) — Directiva 32 §5 exige explícitamente no dar esto por cerrado solo porque CA5 se resolvió. | Jira `#10156` (CA5); verificación de que B1/B2/B3 y el bloqueo de SAPI-43 siguen abiertos sin maquillaje. | **Bueno** | Jira SAPI-66 comentario `10156`; Jira SAPI-43 comentario `10160` |
| 2 | Análisis y especificación de requerimientos | 15% | CA1-CA5 estructurados y trazables; política de procedencia documentada con CA explícito. | Ninguna brecha material restante: las dos incoherencias detectadas en la Directiva 30 (SAPI-67 con ruta de ADR inexistente; SAPI-66 CA5 vs. arquitectura v2) están **ambas reconciliadas con decisión documentada**, no solo señaladas. | Jira SAPI-67 `#10157` (corrige la referencia a `ADR-011-cloud-provider.md`); Jira SAPI-66 `#10156` (reconcilia CA5 con el PO, conservando el texto original). | **Excelente** (sube desde Bueno: ambas incoherencias tenían acción de cierre real, no solo diagnóstico) | Jira SAPI-66/67, comentarios `10156`/`10157` |
| 3 | Arquitectura de software | 15% | 11 ADRs, contratos OpenAPI fijados por SHA-256 (`F7` PASS), servicio ML idéntico salvo campos declarados (`F4c` PASS), 4 servicios desacoplados confirmados en código real (Maven BUILD SUCCESS, FastAPI real, PostGIS real). | Documento de arquitectura 4+1 de 29-09 (`06-delta-arquitectura-4plus1.md`) describía Spring Boot/FastAPI/PostGIS como "OBJETIVO" — desactualizado frente al estado real. | Escribí `docs/evidence/brechas-academicas-cerradas-20261015/README.md` §1, corrigiendo el estado por componente con evidencia de ejecución real para cada uno. | **Excelente** | `/c/sapi-gate/609f615ceca7/freeze.txt` (F4c, F7); `docs/evidence/brechas-academicas-cerradas-20261015/README.md` §1 |
| 4 | Diseño de datos, procesos y plataformas | 15% | PostGIS v2, Flyway V001-V004, 50 celdas, índice GiST, SRID 4326 válido, sin columnas "probab%" — verificado con Postgres real. | No existía un DER explícito del esquema (solo el SQL crudo); el script de verificación de migraciones tenía un defecto real (ya corregido en la Directiva 30/31). | Escribí el DER real (Mermaid, desde `V001-V004` sin inventar campos) en `docs/evidence/brechas-academicas-cerradas-20261015/README.md` §2; `sql-migration-validation` PASS confirmado 3 veces. | **Excelente** (sube desde Bueno: el DER cierra la brecha documental, y el defecto de verificación ya estaba resuelto desde la Directiva 31) | `docs/evidence/brechas-academicas-cerradas-20261015/README.md` §2; `/c/sapi-gate/609f615ceca7/sql-migration-validation.txt` |
| 5 | Implementación y calidad técnica | 15% | Spring Boot 3.x + Java 21, FastAPI, manejo de 503/504, UID 10001 no-root en ambas imágenes. | **Sin cambio real de fondo:** 4 defectos reales de código/test fueron encontrados por auditoría externa en dos sesiones consecutivas (falso positivo CA4, CA5 sin comparar `firms_origin`, script de migración desactualizado, smoke test que nunca pudo arrancar) — ninguno autodetectado por el equipo antes de señalarse. Corregir los síntomas no cambia esta señal de calidad de proceso. | Los cuatro ya corregidos con evidencia RED/GREEN (no se repite auditoría). | **Bueno** (sin cambio: no se infla por mejor redacción, falta correspondencia de fondo) | commits `3770e96`, `609f615` |
| 6 | Validación y pruebas del incremento | 10% | Gate completo ejecutado 3 veces sobre SHAs reales (`85793fb`→`609f615`→verificación), cada corrida con comandos/exit codes propios; CA4 con cronómetro monotónico; pruebas explícitamente vinculadas a sus CA (firms_origin↔V004, fail-closed↔container-smoke-backend). | Ninguna brecha material: la evidencia ahora es reproducible y está atada al SHA, cumpliendo el descriptor Excelente literal. | 3 corridas completas de `merge_gate.py --job all` atadas a SHA, documentadas en `/c/sapi-gate/`. | **Excelente** (sube desde Bueno: la condición que faltaba — "evidencia reproducible atada al SHA" — ya se cumple con 3 corridas reales) | `/c/sapi-gate/609f615ceca7/gate_summary.json` |
| 7 | Integración técnica y atributos de calidad | 5% | `container-smoke-ml`/`container-smoke-backend` PASS reales con Postgres desechable en red aislada; `flyway-integration` real con Flyway CLI 12.4.0; **prueba negativa explícita** de fail-closed (DB inalcanzable → rechazo, no falso PASS). | Ninguna brecha material: el atributo de calidad "seguridad fail-closed" ahora tiene prueba adversarial real, no solo happy-path. | Reconstruí `Check-BackendContainer` con red/DB desechable + prueba negativa; verificado 2 veces standalone + 1 vez en el gate completo. | **Excelente** (sube desde Bueno: ahora hay verificación adversarial real de un atributo no funcional, no solo integración feliz) | `scripts/w0_host_checks.ps1`; `/c/sapi-gate/609f615ceca7/container-smoke.txt` |
| 8 | Evidencia técnica, trazabilidad y evolución | 5% | Historial de commits coherente (`3770e96`→`c0f78a6`, 6 commits trazables); 5 comentarios Jira de cierre con SHA/evidencia vinculada (`10156`-`10160`). | El tablero Jira **sigue sin reflejar** el estado técnico real de las 5 historias abiertas (patrón estructural, no resuelto por comentarios) — brecha genuina, no maquillada. | Generé evidencia de gate atada a 3 SHAs distintos; añadí 5 comentarios Jira trazables, sin alterar ningún estado. | **Bueno** (no Excelente: la brecha de fidelidad del tablero es real y persiste) | commits de esta sesión; Jira `10156`-`10160` |

**Puntaje anterior (Directiva 30):** `0.20×0.75+0.15×0.75+0.15×1.00+0.15×0.75+0.15×0.75+0.10×0.75+0.05×0.75+0.05×0.75` ≈ **0.79 (79%, nota ref. ≈5.4)**.

**Puntaje nuevo (Directiva 32):** `0.20×0.75 + 0.15×1.00 + 0.15×1.00 + 0.15×1.00 + 0.15×0.75 + 0.10×1.00 + 0.05×1.00 + 0.05×0.75` = **0.90 (90%)** → nota referencial ≈ **6.3/7.0** ("Aprobación Muy Buena"). Subida de 11 puntos porcentuales, explicada íntegramente por 5 acciones ejecutadas hoy (2 comentarios Jira de reconciliación, 1 DER nuevo, 3 corridas de gate repetidas, 1 prueba negativa de seguridad) — no por redacción.

---

## B. Rúbrica de César — 6 criterios académicos ponderados (100%)

*(Syllabus INSW421, AE2, IL2.1-2.4 + 2 ejes transversales — reemplaza la matriz sin ponderación de la Directiva 30.)*

| # | Criterio (IL) | Peso | Descriptor Excelente (resumen) | Evidencia real | Brecha restante | Nivel | Referencia |
|---|---|---|---|---|---|---|---|
| 1 | Propuesta de Solución y Modelo de Investigación (IL2.1) | 20% | Propuesta deriva rigurosamente de modelos de investigación y estado del arte revisados; responde con precisión a preguntas de investigación. | Propuesta técnica (ranking relativo XGBoost, arquitectura desacoplada) bien justificada en términos de ingeniería. | **No existe en ningún documento del repositorio ni de `SAPI-HITO2-FUENTES` una sección formal de "preguntas de investigación" ni "estado del arte"** citando la bibliografía exigida (Hernández Sampieri; Cruz Lemus et al.). Verificado explícitamente hoy (búsqueda exhaustiva, cero resultados). Brecha real de 20% de peso, no cerrable con trabajo de ingeniería. | **Suficiente** | `docs/evidence/brechas-academicas-cerradas-20261015/README.md` §4 |
| 2 | Análisis y Especificación de Requerimientos (IL2.2) | 20% | Requerimientos analizados en profundidad, HU + CA verificables + reglas de negocio sin ambigüedad. | 14 HU trazables en Jira con CA1-CA5; las dos incoherencias detectadas (SAPI-67, SAPI-66/CA5) reconciliadas con decisión documentada esta sesión. | Ninguna material. | **Excelente** | Jira `10156`, `10157` |
| 3 | Determinación de la Arquitectura del Software (IL2.3) | 20% | Arquitectura determinada e implementada a partir del modelo investigado; plenamente reflejada en código. | 11 ADRs, 4 servicios desacoplados reales (Spring Boot/FastAPI/PostGIS/Streamlit), verificados con build/test real; estado corregido respecto al delta desactualizado de 29-09. | Ninguna material tras la corrección documental de hoy. | **Excelente** | `docs/evidence/brechas-academicas-cerradas-20261015/README.md` §1 |
| 4 | Diseño de Estructura de Datos, Procesos y Plataformas (IL2.4) | 20% | Análisis integral de estructuras de datos, procesos de negocio y plataformas con justificación técnica rigurosa. | DER real desde el SQL de producción, constraints verificadas en vivo (`score_semantics`, `scientific_model_validation`, `firms_origin`), Compose multi-servicio, contratos OpenAPI. | Ninguna material. | **Excelente** | `docs/evidence/brechas-academicas-cerradas-20261015/README.md` §2 |
| 5 | Gestión del Sprint 2: Pruebas y Matriz de Riesgos | 10% | Sprint Backlog cumplido; plan de pruebas ejecutado con evidencia reproducible; matriz de riesgos actualizada con mitigaciones activas. | Pruebas ejecutadas y reproducibles (gate x3); Sprint Backlog **no** cumplido íntegramente (5/14 abiertas). | `docs/matriz-riesgo.md` del repositorio **no se ha actualizado desde Hito 1**; el registro de riesgos de Sprint 2 vive fuera de este repositorio, no incorporado. Brecha real, no resuelta hoy (requeriría validar contra el registro externo antes de fusionarlo). | **Bueno** | `docs/evidence/brechas-academicas-cerradas-20261015/README.md` §7 |
| 6 | Calidad Documental del Informe 2 y Defensa Oral | 10% | Redacción técnica impecable, normas bibliográficas IEEE/APA, defensa oral fluida. | Guion de demo de 20 min detallado (`11-guion-presentacion-hito2.md`); esqueleto de Informe 2 existente. | El esqueleto de Informe 2 describe arquitectura **desactualizada** (pre-Spring Boot) y no cita bibliografía formal IEEE/APA del syllabus. Requiere reescritura de secciones 3-9 del esqueleto para reflejar el SHA actual — no ejecutado en esta sesión (tarea de redacción académica dedicada, no de ingeniería). | **Suficiente** | `C:\SAPI-HITO2-FUENTES\10-esqueleto-informe-hito2.md`; `docs/evidence/brechas-academicas-cerradas-20261015/README.md` §1 |

**Puntaje César:** `0.20×0.50 + 0.20×1.00 + 0.20×1.00 + 0.20×1.00 + 0.10×0.75 + 0.10×0.50` = **0.825 (82.5%)** → nota referencial ≈ **5.7/7.0** ("Aprobación Satisfactoria-Buena"). No hay puntaje "anterior" comparable: la Directiva 30 usó dimensiones inventadas sin ponderación oficial por no haber localizado este archivo.

---

## C. Qué impide "Excelente" en los criterios restantes (resumen por impacto)

| Criterio | Peso | Por qué no es Excelente | Qué se necesitaría |
|---|---|---|---|
| César 1 — Propuesta/Investigación | 20% | Sin preguntas de investigación ni estado del arte formal citando bibliografía del syllabus | Redacción académica dedicada (1-2 páginas), no ingeniería |
| César 6 — Informe/Defensa | 10% | Esqueleto de Informe 2 desactualizado (pre-Spring Boot) y sin bibliografía IEEE/APA | Reescritura de Informe 2 contra el SHA actual + citas formales |
| César 5 / Matías 8 — Riesgos/Trazabilidad | 10% / 5% | Matriz de riesgos sin actualizar desde Hito 1; tablero Jira no refleja el estado técnico real | Actualizar `docs/matriz-riesgo.md` con el registro de Sprint 2 real; decisión humana sobre reconciliar el tablero |
| Matías 1 — Incremento | 20% | 5/14 historias con brechas reales (no solo administrativas): SAPI-43 bloqueado, SAPI-66 con dependencias pendientes | Autorización humana + credenciales (SAPI-43); validación independiente del resto de CA de SAPI-66 |
| Matías 5 — Implementación | 15% | 4 defectos reales no autodetectados por el equipo en 2 sesiones de auditoría externa | Mejorar disciplina de auto-verificación antes de declarar "done", no corregible retroactivamente por el cierre de gate |

---

## D. Nota de honestidad metodológica

Esta matriz corrige la de la Directiva 30 en dos sentidos: (1) usa el archivo
real de la rúbrica de César, recién localizado, en lugar de una construcción
propia; (2) sube de nivel únicamente donde hubo una acción ejecutada y
verificable esta sesión — nunca por mejor redacción del informe. Las dos
brechas de mayor peso que persisten (César 1, 20%; César 6, 10%) son
explícitamente de redacción académica (preguntas de investigación, estado del
arte, bibliografía formal), no de ingeniería, y se declaran así en vez de
forzarlas a un nivel superior.

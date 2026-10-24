# 04 — Impacto en rúbricas y en Gate B

**Fecha:** 2026-10-24  
**HEAD de esta recuperación:** `51ec3c06b67959d3daad6349c962a1be643906b4`  
**Rúbricas de referencia:**
- `docs/hito2/MATRIZ_RUBRICA_CESAR_FINAL.md` — 6 criterios; total histórico 0.825 (5.7/7.0).
- `docs/hito2/MATRIZ_RUBRICA_MATIAS_FINAL.md` — 8 criterios; total histórico 0.900 (6.3/7.0).

> **Aclaración importante:** ambas matrices fueron calculadas sobre el candidato `f9654834cec0e026cd8fc84d5af7d81f75da25e2`, no sobre `51ec3c06`. Se usan aquí solo como marco de criterios y niveles. **No se recalcula el puntaje ni se declara una subida de nota.**

## 1. Principio de esta recuperación

La recuperación sigue la regla de las matrices: un nivel sube solo con una **acción ejecutada y verificable**, no por redacción ni por repetir una instrucción. Por eso:

- se ejecutaron pruebas dirigidas y se registraron comandos, exit codes, archivos y SHA;
- no se ejecutó un E2E nuevo, no se levantó Docker y no se corrió la batería completa;
- no se editó Jira, no se hizo push/merge y no se alteraron imágenes ni hashes;
- los estados “ACREDITADO” de `01` son estados de evidencia, no certificaciones de cierre.

## 2. Qué aporta y qué no aporta

### 2.1 Aporta

| Aporte | Evidencia | Criterio de rúbrica que toca |
|---|---|---|
| 134 pruebas Python PASS (1 skip) en 8 archivos dirigidos | `02-CAMBIOS-Y-PRUEBAS.md` §2 | Calidad técnica, validación |
| 85 pruebas Java PASS en 4 clases | §3 | Persistencia, política `current`, validador |
| Hash de capturas, tipo de navegación y verificación de grilla en el arnés CA4 | §1.1; 18 PASS | Trazabilidad, reproducibilidad futura |
| Diagnóstico explícito de CA4 (PNG idénticos por minuto) | `01` §5 | Integridad de evidencia |
| Diagnóstico explícito de CA5 (profile `presentation`, validador con 3 sustituciones) | `01` §6 | Precisión de requisitos |
| Cuatro documentos con comandos, exit codes, SHA y límites | este paquete | Trazabilidad documental |

### 2.2 No aporta

- No cierra SAPI-66 CA1, CA2, CA4 ni CA5.
- No cierra SAPI-43 CA1 ni CA8.
- No re-ejecuta W3/W4; solo cita evidencia del mismo SHA.
- No sustituye la batería completa, el gate de cobertura ni un E2E real.
- No convierte una aceptación alternativa del PO (CA5) en cumplimiento literal.
- No cambia el veredicto Gate B.

## 3. Rúbrica de César (6 criterios)

| # | Criterio | Peso | Nivel histórico | Impacto de esta recuperación | ¿Sube nivel ahora? |
|---|---|---:|---|---|---|
| 1 | Propuesta de Solución y Modelo de Investigación (IL 2.1) | 20% | Suficiente | Ninguno: faltan preguntas de investigación y estado del arte formal; es trabajo académico, no ingeniería | **No** |
| 2 | Análisis y Especificación de Requerimientos (IL 2.2) | 20% | Excelente | Refuerza la precisión: distingue CA5 literal de la aceptación alternativa ya aprobada; no hay nueva decisión Jira | **No** |
| 3 | Determinación de la Arquitectura del Software (IL 2.3) | 20% | Excelente | Confirma con tests estáticos la ruta v2, el profile `presentation` y el secreto; no hay ADR nuevo | **No** |
| 4 | Diseño de Estructura de Datos, Procesos y Plataformas (IL 2.4) | 20% | Excelente | Refuerza con migraciones V001–V004 y W3/W4; no hay corrida nueva | **No** |
| 5 | Gestión del Sprint 2: Pruebas y Matriz de Riesgos | 10% | Bueno | Mejora la **calidad de la evidencia** (comandos, exit codes, hashes, límites), pero el Sprint Backlog sigue incompleto (SAPI-43/66 abiertas) y no hay E2E nuevo | **No** |
| 6 | Calidad Documental del Informe 2 y Defensa Oral | 10% | Suficiente | Ninguno directo: estos documentos son evidencia interna, no el Informe 2 ni un ensayo de defensa | **No** |

**Lectura:** el criterio 5 es el más beneficiado, pero su descriptor de Excelente exige Sprint Backlog cumplido; no se cumple. El criterio 2 no cambia porque la reconciliación de CA5 ya estaba registrada; lo que se añade es la distinción explícita entre aceptación alternativa y literalidad.

## 4. Rúbrica de Matías (8 criterios)

| # | Criterio | Peso | Nivel histórico | Impacto de esta recuperación | ¿Sube nivel ahora? |
|---|---|---:|---|---|---|
| 1 | Incremento funcional del Sprint 2 | 20% | Bueno | Ninguno: SAPI-43 y SAPI-66 siguen abiertas; no se declara incremento íntegro | **No** |
| 2 | Análisis y especificación de requerimientos | 15% | Excelente | Refuerza la trazabilidad CA↔evidencia; no hay nueva decisión de Jira | **No** |
| 3 | Arquitectura de software | 15% | Excelente | Sin cambio material; los tests confirman lo ya documentado | **No** |
| 4 | Diseño de datos, procesos y plataformas | 15% | Excelente | Sin cambio material; W3/W4 y migraciones ya sostenían el nivel | **No** |
| 5 | Implementación y calidad técnica | 15% | Bueno | Las pruebas dirigidas pasan y el arnés mejora, pero no hay E2E nuevo; los defectos históricos no se borran por repetir tests | **No** |
| 6 | Validación y pruebas del incremento | 10% | Excelente | La evidencia sigue siendo consistente; no se ejecutó un gate completo nuevo, así que no se usa para “subir” nada | **No** |
| 7 | Integración técnica y atributos de calidad | 5% | Excelente | Sin cambio: no hay container-smoke ni prueba negativa real nueva | **No** |
| 8 | Evidencia técnica, trazabilidad y evolución | 5% | Bueno | Mejora la trazabilidad documental (comandos, hashes, límites), pero persisten las brechas de Jira/PR/gobernanza | **No** |

**Lectura:** el paquete mejora la defensa del criterio 8 y la calidad de la evidencia del criterio 6, pero no crea la acción ejecutada que exige una subida de nivel. El criterio 1 sigue limitado por SAPI-43/66.

## 5. Impacto en Gate B

| Control | Estado v5 | ¿Cambia con esta recuperación? | Motivo |
|---|---|---|---|
| GB-01 | PASS | No | Candidato inmutable; no se tocó |
| GB-02 | PASS con salvedad | No | CI remoto no reconsultado |
| GB-03 | PARCIAL | No | F4 abierta |
| GB-04 | NO EJECUTADO | No | Sin acta F1–F5 completa |
| GB-05 | NO EJECUTADO | No | L1 Windows no ejecutado |
| GB-06 | PARCIAL (no literal) | **No** | CA5 literal sin `.env` sigue sin ejecutarse; EX-06 pendiente |
| GB-07 | CONDICIONADO | **No** | CA4 cached=update; falta recaptura y L3/L4 literal |
| GB-08 | PARCIAL | No | L6/G0 sin procedimiento |
| GB-09 | NO EJECUTADO | No | D08 no ejecutado |
| GB-10 | NO EJECUTADO | No | G1 real no ejecutado |
| GB-11 | CONDICIONADO | **No** | `firms_origin=current` sobre el SHA/EX-11 sigue pendiente |
| GB-12 | PASS (declarativo) | No | Sin claims prohibidos; se refuerza la redacción, no el estado |

**Conteo vigente:** 3 PASS · 2 CONDICIONADO · 3 PARCIAL · 4 NO EJECUTADO · 0 FAIL. **Gate B técnico: NO GO.** Ningún control se promueve.

## 6. Qué haría falta para subir un nivel

| Acción | Criterio impactado | Requisito |
|---|---|---|
| Ejecutar `tests/e2e/test_vertical_slice.py` sobre stack limpio | Matías 1/6; César 5; GB-07 | Docker + Edge + autorización |
| Recapturar CA4 con detalle de segundos/hash y `timings.csv` por salto | Matías 6; GB-07 | E2E + ventana de medición |
| Ejecutar CA5 literal sin `.env` ni overrides | Matías 1/6; GB-06 | Decisión sobre `web-v2` en la ruta por defecto |
| Ejecutar SAPI-71 Attempt 2 y la corrida SAPI-43 | Matías 1; GB-11 | Autorización, credenciales, host Windows |
| Ejecutar `RankingHttpToPostgresIT` real | Matías 5/6; GB-11 | Testcontainers/DB |
| Cerrar Jira / documentar PRs | Matías 8; César 2 | Decisión humana; no ejecutado |
| Reescribir Informe 2 con bibliografía y ensayar defensa | César 1/6 | Trabajo académico |

Ninguna de estas acciones se ejecutó en esta recuperación. No se declara un nivel nuevo por “mejor documentación”.

## 7. Integridad científica y límites

- **No se inventaron** PASS, tiempos, filas, fingerprints ni datos operacionales.
- **No se presentó** el score como probabilidad calibrada; se mantiene `relative_rank` y `scientific_model_validation=false`.
- **No se alteraron** las capturas CA4 ni sus hashes; la coincidencia se explicó por la precisión de minuto del header.
- **No se ocultó** que W3/W4 son evidencia histórica del mismo SHA, no una re-ejecución.
- **No se ocultó** que CA5 tiene una aceptación alternativa del PO; se distinguió de la literalidad.
- **No se usó** la matriz histórica como si fuera un veredicto del HEAD actual.

## 8. Conclusión

Esta recuperación **aumenta la verificabilidad y la trazabilidad** de lo ya construido: comandos exactos, exit codes, 134 PASS Python, 85 PASS Java, hashes de capturas y diagnóstico de las brechas CA4/CA5. También endurece el arnés para que una futura recaptura no vuelva a producir evidencia ambigua.

Pero **no cierra SAPI-43 ni SAPI-66**, no sustituye un E2E real y no cambia Gate B. El veredicto sigue siendo **NO GO**; los controles GB-06, GB-07 y GB-11 siguen en **PARCIAL/CONDICIONADO**, y cualquier subida de rúbrica requiere las acciones humanas y de infraestructura listadas en `03-PENDIENTES-QUE-REQUIEREN-E2E.md`.

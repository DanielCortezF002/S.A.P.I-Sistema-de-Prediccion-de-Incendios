# Matriz final — Rúbrica de Matías (8 criterios, 100%)

**Fuente:** `rubrica sprint 2 matias.md` / `Rubrica_Hito_2_Proyecto_de_Titulo.md`.
**Candidato evaluado:** commit `f9654834cec0e026cd8fc84d5af7d81f75da25e2` (Directiva 34).
**Proceso de calificación:** ver `docs/evidence/rubricas-hito2-verificadas-20261015/README.md` para el detalle de evidencia y brechas por criterio.

| # | Criterio | Ponderación | Nivel asignado | Puntaje | Evidencia / Referencia |
|---|---|---:|:---:|---:|---|
| 1 | Incremento funcional del Sprint 2 | 20% | **Bueno** | 0.150 | 9/14 historias DONE (37/58 SP); 5 historias con brechas reales (SAPI-43 bloqueado, SAPI-66 con dependencias pendientes) — **no se declara incremento íntegro ni 58/58**, conforme a instrucción expresa de la Directiva 34 |
| 2 | Análisis y especificación de requerimientos | 15% | **Excelente** | 0.150 | Jira `#10156`/`#10157`: ambas incoherencias reconciliadas con decisión trazable |
| 3 | Arquitectura de software | 15% | **Excelente** | 0.150 | 11 ADRs; `F4c`/`F7` PASS; 4 servicios reales verificados |
| 4 | Diseño de datos, procesos y plataformas | 15% | **Excelente** | 0.150 | DER real; `sql-migration-validation`/`flyway-integration` PASS |
| 5 | Implementación y calidad técnica | 15% | **Bueno** | 0.1125 | 2043 pruebas Python + 162 JUnit reales y reproducibles (cobertura 83.91%); **reconsiderado en Directiva 34 y mantenido**, ver nota debajo |
| 6 | Validación y pruebas del incremento | 10% | **Excelente** | 0.100 | 3 corridas reales de `merge_gate.py --job all` atadas a SHA en Directiva 32, más regresión adicional de 176 pruebas en Directiva 34 (módulos SAPI-71), todas vinculadas a su CA |
| 7 | Integración técnica y atributos de calidad | 5% | **Excelente** | 0.050 | `container-smoke-ml`/`backend` PASS real; prueba negativa fail-closed real (DB inalcanzable → rechazo) |
| 8 | Evidencia técnica, trazabilidad y evolución | 5% | **Bueno** | 0.0375 | Historial de commits coherente + 6 comentarios Jira trazables (`10156`-`10161`); **matriz de riesgos de Sprint 2 ahora incorporada** (`MATRIZ_RIESGOS_SPRINT2.md`, 19 riesgos) — cierra parte del descriptor de Excelente; persiste como brecha real: no hay pull requests documentados ni ramas por feature (gobernanza de este proyecto es de commits locales únicamente, por diseño, no por descuido) |
| **TOTAL** | | **100%** | — | **0.900** | |

## Cálculo de nota

Puntaje = 0.900 (90%) ≥ 0.60 →
Nota = 4.0 + 3.0 × ((0.900 − 0.60) / 0.40) = 4.0 + 2.25 = **6.25 ≈ 6.3 / 7.0**
("Aprobación Muy Buena").

## Nota sobre el criterio 5 (reconsiderado explícitamente en Directiva 34)

La Directiva 34 pidió explícitamente reconsiderar este criterio con la misma
evidencia de calidad (2043 pruebas, 83.91% de cobertura, validación
independiente, corrección de falsos positivos, trazabilidad de gate). Se
reconsideró y **se mantiene en Bueno**, no Excelente: esa evidencia no es
nueva desde la Directiva 33, y la razón original sigue vigente sin refutar —
el descriptor de Excelente exige que el código demuestre "correcta separación
de responsabilidades, manejo de errores, validaciones" de forma consistente,
y **seis** defectos reales en total (los 4 ya conocidos más los hallazgos de
B1/B2/B3 — aunque estos últimos resultaron ya remediados antes de esta
cadena de directivas, su sola existencia histórica documentada en
`docs/evidence/sapi71-f4-prep/` es la misma clase de señal) pasaron sin
detectarse por el propio equipo hasta ser señalados por auditoría externa.
Subir el nivel solo porque se repitió la instrucción, sin evidencia nueva,
sería precisamente el tipo de inflación que la Directiva 34 prohíbe.

## Brechas que impiden Excelente en el criterio 1 (mayor peso, 20%)

SAPI-43 permanece bloqueado pendiente de decisión humana y credenciales;
SAPI-66 tiene su CA5 resuelto pero el resto de sus criterios (E2E con datos
operacionales reales, dependiente de SAPI-43/71) no están satisfechos. **No
se declara el incremento como íntegro** mientras estas 2 historias (10 SP)
no cierren con evidencia real, conforme a instrucción expresa de la
Directiva 33 §4.

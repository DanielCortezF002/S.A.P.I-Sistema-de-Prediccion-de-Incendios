# Matriz final — Rúbrica de César (6 criterios, 100%)

**Fuente:** `rubrica sprint 2 cesar.md` (Syllabus Seminario de Licenciatura, INSW421, cátedra César, AE2/IL2.1–2.4 + 2 ejes transversales).
**Candidato evaluado:** commit `f9654834cec0e026cd8fc84d5af7d81f75da25e2` (Directiva 34).
**Proceso de calificación:** ver `docs/evidence/rubricas-hito2-verificadas-20261015/README.md` para el detalle de evidencia y brechas por criterio; este documento presenta la matriz final lista para la planilla de registro del docente.

| # | Criterio (Indicador de Logro) | Ponderación | Nivel asignado | Puntaje | Evidencia / Referencia |
|---|---|---:|:---:|---:|---|
| 1 | Propuesta de Solución y Modelo de Investigación (IL 2.1) | 20% | **Suficiente** | 0.100 | `INFORME_HITO2_FINAL.md` §2–4 (redactado en Directiva 33); brecha: primera versión, sin revisión docente/par |
| 2 | Análisis y Especificación de Requerimientos (IL 2.2) | 20% | **Excelente** | 0.200 | Jira SAPI-66 `#10156`, SAPI-67 `#10157` (reconciliación documentada de las dos únicas incoherencias detectadas) |
| 3 | Determinación de la Arquitectura del Software (IL 2.3) | 20% | **Excelente** | 0.200 | `INFORME_HITO2_FINAL.md` §7; freeze checks `F4c`/`F7` PASS; 11 ADRs |
| 4 | Diseño de Estructura de Datos, Procesos y Plataformas (IL 2.4) | 20% | **Excelente** | 0.200 | `INFORME_HITO2_FINAL.md` §8 (DER real); `sql-migration-validation`/`flyway-integration` PASS |
| 5 | Gestión del Sprint 2: Pruebas y Matriz de Riesgos | 10% | **Bueno** | 0.075 | Gate ejecutado 3× con evidencia reproducible; **matriz de riesgos de Sprint 2 ahora incorporada** (`MATRIZ_RIESGOS_SPRINT2.md`, 19 riesgos, Directiva 34) — cierra la brecha original; se mantiene en Bueno (no Excelente) porque el Sprint Backlog no está íntegramente cumplido (5/14 historias abiertas), condición explícita del descriptor de Excelente |
| 6 | Calidad Documental del Informe 2 y Defensa Oral | 10% | **Suficiente** | 0.050 | `INFORME_HITO2_FINAL.md` ahora incluye matriz de riesgos integrada; brecha sin cambio: primera versión formal, sin ensayo de defensa aún realizado |
| **TOTAL** | | **100%** | — | **0.825** | |

## Cálculo de nota

Puntaje = 0.825 (82.5%) ≥ 0.60 →
Nota = 4.0 + 3.0 × ((0.825 − 0.60) / 0.40) = 4.0 + 1.6875 = **5.69 ≈ 5.7 / 7.0**
("Aprobación Satisfactoria-Buena", escala institucional 60%=4.0, 100%=7.0).

## Brechas que impiden Excelente (ordenadas por impacto)

1. **Criterio 1 (20%):** sin preguntas de investigación ni estado del arte
   formal previos a este informe — ahora redactados (§2–4 de
   `INFORME_HITO2_FINAL.md`), pero es la primera versión, no revisada por
   pares ni iterada; se mantiene Suficiente hasta una segunda revisión.
2. **Criterio 6 (10%):** el Informe 2 es nuevo en su forma actual; falta
   ensayo de la defensa oral y verificación de tiempos reales de exposición.
3. **Criterio 5 (10%):** la matriz de riesgos ya se incorporó (Directiva 34);
   la brecha restante es el Sprint Backlog incompleto (5/14 historias
   abiertas), no corregible documentalmente.

## Acciones humanas necesarias para subir de nivel

- Revisión docente/par del Informe 2 (criterio 1 y 6 dependen de iteración,
  no solo de redacción inicial).
- Ensayar la defensa oral contra el guion de 20 minutos (criterio 6).
- Cerrar las 5 historias abiertas (SAPI-43/49/63/66/67) con decisión humana
  (criterio 5, Sprint Backlog).

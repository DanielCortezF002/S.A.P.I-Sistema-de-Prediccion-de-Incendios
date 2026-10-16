# Checklist de entrega — Hito 2 / Sprint 2

Candidato base (Directiva 34): `f9654834cec0e026cd8fc84d5af7d81f75da25e2`.
El commit que incorpora esta versión del checklist es necesariamente
posterior (no puede autorreferenciarse) y se reporta en el entregable
ejecutivo de la Directiva 34.

## Documentos producidos

**Directiva 33:**
- [x] `docs/hito2/INFORME_HITO2_FINAL.md` — Informe 2 completo, secciones A-K
- [x] `docs/hito2/MATRIZ_RUBRICA_CESAR_FINAL.md` — 6/6 criterios, puntaje 82.5%
- [x] `docs/hito2/MATRIZ_RUBRICA_MATIAS_FINAL.md` — 8/8 criterios, puntaje 90%
- [x] `docs/hito2/TRAZABILIDAD_HU_CA_EVIDENCIAS.md` — 14 historias, HU→CA→código→prueba
- [x] `docs/hito2/PRESENTACION_HITO2_GUION_20MIN.md` — guion 5+5+7+3 min + contingencias
- [x] `docs/hito2/PREGUNTAS_COMISION_Y_RESPUESTAS.md` — preguntas anticipadas con evidencia
- [x] `docs/hito2/CHECKLIST_ENTREGA_HITO2.md` — este documento

**Directiva 34 (añadidos/actualizados):**
- [x] `docs/evidence/b1-b2-b3-estado-real-20261015/README.md` — corrección: B1/B2/B3 ya remediados (commit `4012fbf`), 9/9 + 176 pruebas reales verificadas hoy
- [x] `docs/hito2/MATRIZ_RIESGOS_SPRINT2.md` — 19 riesgos reales, integrado en el Informe y ambas matrices
- [x] `INFORME_HITO2_FINAL.md` §9/11/12 corregidos (B1/B2/B3→ADV-05, riesgos integrados)
- [x] `MATRIZ_RUBRICA_MATIAS_FINAL.md` criterios 5/8 reconsiderados explícitamente (sin cambio de nivel, con justificación transparente)
- [x] `MATRIZ_RUBRICA_CESAR_FINAL.md` criterio 5 actualizado (riesgos cerrados; Sprint Backlog sigue bloqueando Excelente)
- [x] `PRESENTACION_HITO2_GUION_20MIN.md` corregido (ADV-05 en vez de B1/B2/B3 como ejemplo de defecto abierto)

## Revisión editorial (Directiva 33 §6 + Directiva 34 §6)

- [x] Placeholders eliminados (`[GATE_VERDICT]`, `[ATTEMPT2_RESULT]`, `[JIRA_STATUS]`, `[RUBRICA_HITO2]`, `[PR1_STATUS]`)
- [x] Cifras confirmadas: 107 positivos/1:3390/26 de 49 folds (SAPI-63); 1709.5 ms CA4; 37/58 SP; 5/6 subgates PASS; 9/9 + 176 pruebas B1/B2/B3-adyacentes
- [x] Citas verificadas: Hernández Sampieri y Cruz Lemus et al.; NASA FIRMS con DOI oficial; 4 artículos con URL/DOI verificado por búsqueda real
- [x] Diagramas (arquitectura, DER) generados desde el código/SQL real
- [x] Referencias de SHA actualizadas al candidato base de Directiva 34 (`f9654834`)
- [x] Contradicciones Informe↔Jira↔matrices revisadas y corregidas: **se detectó y corrigió una contradicción real** (B1/B2/B3 reportados como abiertos en 3 directivas consecutivas y en Jira `#10160`, cuando ya estaban remediados) — corrección publicada en Jira `#10161`

## Lo que NO se hizo (alcance respetado)

- [x] No se modificó código productivo ni scripts de gate (solo documentación en `docs/`)
- [x] No se tocó la rama Codex SAPI-66
- [x] No se reentrenó el Modelo D
- [x] No se ejecutó push, PR, merge, despliegue ni transición Jira (solo comentarios)
- [x] No se declaró F4/freeze PASS global; no se redujeron umbrales ni se deshabilitaron verificaciones
- [x] No se ejecutó el refresco real de SAPI-43/71 ni se tocó CURRENT canónico
- [x] No se imprimieron ni introdujeron credenciales

## Brechas pendientes (no resueltas, declaradas explícitamente)

| Brecha | Peso en rúbrica | Acción necesaria |
|---|---|---|
| Preguntas de investigación/estado del arte, primera versión sin revisión de pares | César 1 (20%) | Revisión docente/par |
| Informe 2 nuevo, sin ensayo de defensa oral | César 6 (10%) | Ensayar contra el guion de 20 min |
| Sprint Backlog incompleto (5/14 historias abiertas) | César 5 (10%) | Cerrar historias con decisión humana |
| 4+ defectos reales (CA4/CA5/migración/smoke) no autodetectados por el equipo | Matías 5 (15%) | Mejorar disciplina de auto-verificación, no retroactivo |
| SAPI-43 sin refresco real, SAPI-66 sin E2E con datos reales | Matías 1 (20%) | Autorización humana + credenciales |
| Sin pull requests/ramas por feature (gobernanza local-only por diseño) | Matías 8 (5%) | No aplica mientras el proyecto opere solo con commits locales |
| ADR-011 sin firma | — | Decisión del PO/comisión |
| ADV-05 (atomicidad de publicación bajo fallo de IO) | — | Decisión de change-control (compensación vs. reconciliación durable) |

## Acciones humanas estrictamente necesarias antes de cerrar Sprint 2

1. Revisión docente del Informe 2 (César 1, 6).
2. Decisión y firma de ADR-011 (SAPI-67).
3. Autorización del runbook de refresco real + credenciales (SAPI-43).
4. Decisión de change-control para ADV-05.
5. Decisión sobre la rama Codex SAPI-66 (excluida hasta entonces).
6. Autorización de merge/push/despliegue y transiciones Jira.

**Estado final: candidato documental completo, consolidado sobre `f9654834` + el commit de esta Directiva, listo para revisión humana. Ninguna publicación ejecutada.**

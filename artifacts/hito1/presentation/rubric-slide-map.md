# Mapa de rúbrica → slides — presentación Hito 1

Generado 07-09-2026 contra `docs/presentacion-hito1.md` (11 slides).
"Cubrir" un criterio significa que la slide lo comunica con la evidencia
real que ya documentan las fuentes congeladas — **no** significa afirmar
que el criterio está cumplido. Para las brechas, la slide indicada es la
que comunica honestamente el `NOT_FOUND`/`PARCIAL` correspondiente. Base:
`artifacts/hito1/final-report/final-rubric-location-map.md` (misma
lógica de mapeo, remapeada de páginas del DOCX a slides).

## Hito 1

| Criterio | Slide(s) | Evidencia comunicada | Estado |
|---|---|---|---|
| Asistencia (10%) | — | Fuera del alcance de una presentación de proyecto | PENDIENTE (fuera de alcance) |
| Incremento + tablero (20%) | 3, 7 | Pipeline + prototipo real; tablero Jira mencionado en slide 9, no verificado en vivo durante la exposición | PARCIAL |
| Arquitectura (12%) | 4 | Diagrama de 3 fuentes → procesamiento → dataset → Modelo D → ranking → dashboard | CUBIERTO |
| Testing (12%) | 8 | 470/470, 91,72%, smoke 5/5 | CUBIERTO |
| Versionamiento (8%) | 9 | 68 commits, tag `v1.0.0-sprint1-verified` | CUBIERTO |
| Trazabilidad (10%) | 9 | 10 tickets auditados, CA 6/10, 7 REQ sin HU Jira declarado explícitamente | PARCIAL (GAP declarado) |
| Atributos de calidad (10%) | 9 | 3 verificados / 4 parciales / 2 no verificados / 1 no aplica | CUBIERTO |
| Calidad de código (8%) | 9 | Mencionado dentro del bloque GIT/calidad (detalle completo queda en el informe, no en la slide) | PARCIAL (mención breve, no detalle) |
| Matriz de riesgo (10%) | 9 | 23 riesgos identificados | CUBIERTO |

## Sprint 1 (12 criterios)

| # | Criterio | Slide(s) | Evidencia comunicada | Estado |
|---|---|---|---|---|
| 1 | Sprint Goal | 10 | "Sprint Goal histórico" listado como brecha de gestión | **NOT_FOUND documentado** |
| 2 | HU y refinamiento | 3, 9 | 10 tickets Jira auditados; 7 REQ del pipeline temporal sin HU | PARCIAL |
| 3 | Criterios de aceptación | 9 | "CA históricos completos: 6/10" | PARCIAL |
| 4 | Sprint Backlog / Jira | 9 | Bloque GIT (commits/tag); SP 34/21/13 no incluido en slide, sí en informe/Anexo B | PARCIAL (detalle SP no está en el deck, solo en el informe) |
| 5 | Definition of Done | 10 | "Definition of Done histórica" listada como brecha | **NOT_FOUND documentado** |
| 6 | Diseño 4+1 / equivalente | 4 | Diagrama de arquitectura (formato no 4+1 canónico, igual que en el informe) | PARCIAL |
| 7 | Seguimiento / reuniones | 10 | "seguimiento semanal" listado como brecha | **NOT_FOUND documentado** |
| 8 | Riesgos / impedimentos | 9 | "23 identificados" | CUBIERTO (cifra; detalle por riesgo queda en el informe/Anexo E) |
| 9 | Pruebas / resultados / trazabilidad | 8, 9 | 470/470 + bloque de trazabilidad | CUBIERTO |
| 10 | Sprint Review / validación | 10 | "aceptación externa" listada como brecha | **NOT_FOUND documentado** |
| 11 | Gestión de cambios | 9 | Mencionado solo indirectamente vía bloque de riesgos; sin detalle de hallazgo→decisión→cambio en el deck | PARCIAL (detalle solo en el informe, no en la slide) |
| 12 | Retrospectiva / cierre / mejora | 10, 11 | "No se reconstruyó evidencia retroactivamente" + mensaje de conclusión orientado a Sprint 2 | CUBIERTO (como reconstrucción actual, no histórica) |

## Cobertura total

**8/9 criterios de Hito 1** tienen mención directa en el deck (Asistencia
queda fuera por naturaleza de una presentación de proyecto). **12/12
criterios de Sprint 1** tienen una referencia en el deck, pero el deck es
deliberadamente menos detallado que el informe escrito: una presentación
de 13:35 minutos no puede portar el mismo nivel de detalle que un
documento de 21 páginas. Donde el deck resume o generaliza (SP exactos,
detalle riesgo por riesgo, gestión de cambios hallazgo por hallazgo), se
marca aquí explícitamente como "detalle solo en el informe" en vez de
presentarlo como si la slide lo cubriera con el mismo nivel de evidencia
que `docs/informe-hito1-final.md`.

Igual que en el mapa del informe final: **"cubrir" en este documento
nunca significa "aprobar"** ese criterio. Las brechas de gestión de
Sprint 1 (#1, #5, #7, #10) se comunican en la slide 10 exactamente como
brechas, no como logros.

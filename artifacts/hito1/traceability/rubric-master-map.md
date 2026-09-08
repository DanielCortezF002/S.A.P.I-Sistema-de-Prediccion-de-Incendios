# Mapa maestro de rúbricas — Hito 1 / Sprint 1

Generado 07-09-2026. No sustituye el criterio del profesor — es una
autoevaluación defendible basada en evidencia verificable del
repositorio, para saber honestamente en qué posición se llega a la
presentación. **No se inventa un puntaje final.**

Niveles usados: `EXCELENTE_DEFENDIBLE` · `BUENO_DEFENDIBLE` ·
`SUFICIENTE_DEFENDIBLE` · `INSUFICIENTE_RISK` · `PENDIENTE`

---

## Rúbrica Hito 1

### 1. Asistencia — 10%

- **Evidencia encontrada:** ninguna verificable desde este repositorio —
  la asistencia es un registro externo (plataforma del curso/profesor),
  no algo que un repositorio de código pueda evidenciar por sí mismo.
- **Nivel defendible hoy:** `PENDIENTE`
- **Brecha:** estructural — este criterio no se puede cerrar con
  evidencia de repositorio.
- **Recuperable antes de presentación:** no vía este proyecto; depende
  del registro de asistencia real del curso.
- **Fase que lo cerrará:** ninguna de las fases de este repositorio.

### 2. Incremento + tablero — 20%

- **Evidencia encontrada:** incremento real y funcional (prototipo
  congelado, `docs/arquitectura-hito1.md`, 470/470 tests,
  `docs/testing-evidencia-hito1.md`). Tablero: `README.md` referencia un
  tablero Jira público (línea 283), pero esta fase **no accedió a Jira
  en vivo** (fuera de alcance explícito — "no reabrir Jira todavía").
- **Nivel defendible hoy:** `BUENO_DEFENDIBLE` en el incremento;
  `PENDIENTE` en la verificación en vivo del tablero.
- **Brecha:** el estado actual del tablero Jira no está verificado desde
  esta fase, solo referenciado.
- **Recuperable:** sí.
- **Fase que lo cerrará:** próxima fase de Jira/trazabilidad con acceso
  al tablero real.

### 3. Arquitectura — 12%

- **Evidencia encontrada:** `docs/arquitectura-hito1.md` (CONGELADA),
  auditada dos veces en fases previas, con modelo lógico de datos,
  decisiones arquitectónicas y trazabilidad técnica verificadas contra
  código real (`src/inference/prototype_service.py`,
  `src/procesamiento/regional_meteo.py`, etc.).
- **Nivel defendible hoy:** `EXCELENTE_DEFENDIBLE`
- **Brecha:** ninguna crítica encontrada en las auditorías previas.
- **Recuperable:** N/A (ya cerrada).
- **Fase que lo cerrará:** CERRADA (fase Arquitectura, 07-09-2026).

### 4. Testing — 12%

- **Evidencia encontrada:** `docs/testing-evidencia-hito1.md` +
  `artifacts/hito1/testing/` — ejecución fresca 470/470 PASS, cobertura
  91.72%, 10 criterios técnicos AC-T01..T10 verificados, 6 hallazgos con
  evidencia real (`defect-evidence.md`), smoke Streamlit real.
- **Nivel defendible hoy:** `BUENO_DEFENDIBLE` en la parte técnica.
  La pieza más débil es la cobertura de HU/CA (ver criterio Sprint 1 #9)
  y la ausencia de aceptación externa formal.
- **Brecha:** `HU_COVERAGE: PENDING_TRACEABILITY`; sin aceptación de
  usuario externo para el incremento actual.
- **Recuperable:** parcialmente en esta misma fase de Trazabilidad;
  completamente solo con una sesión de aceptación real futura.
- **Fase que lo cerrará:** esta fase de Trazabilidad (parcial) + una
  sesión de aceptación real (pendiente de programar).

### 5. Versionamiento — 8%

- **Evidencia encontrada:** `git log` con commits descriptivos y
  consistentes desde 2026-06-20; 6 tags semánticos reales
  (`v1.0.0-data`, `v1.0.0-sprint1-verified`, `v1.1.0-corredor-verified`,
  `v2.0.0-baseline`, `v3.0.0-final-release`, `v3.2.0-demo-professional`);
  branches de trabajo reales (`feature/dmc-live-card`,
  `experiment/real-cells-map-preview`, `design/direccion-b-institucional`).
- **Nivel defendible hoy:** `BUENO_DEFENDIBLE`
- **Brecha:** no se verificó en esta fase una convención documentada de
  branching/tagging (p. ej. si sigue Gitflow formalmente o es ad hoc) —
  eso es evaluación de la fase de Versionamiento, no de esta.
- **Recuperable:** sí, en su fase dedicada.
- **Fase que lo cerrará:** fase de Versionamiento (no ejecutada aún).

### 6. Trazabilidad — 10%

- **Evidencia encontrada:** esta misma fase construye
  `docs/trazabilidad-hito1.md`, con la matriz canónica
  requerimiento→HU→CA→prueba→resultado→evidencia, auditando y
  señalando explícitamente dónde `docs/matriz-trazabilidad-hu-test.md`
  (pre-existente) quedó desactualizada.
- **Nivel defendible hoy:** `BUENO_DEFENDIBLE` para lo que SÍ tiene HU
  Jira verificada; `SUFICIENTE_DEFENDIBLE` en conjunto porque el
  pipeline temporal completo queda con el vínculo HU pendiente (ver
  sección 12 del documento principal).
- **Brecha:** vínculo HU-Jira del pipeline temporal nuevo.
- **Recuperable:** sí, vinculando o creando la HU correspondiente en
  Jira (acción para Sprint 2, no en esta fase).
- **Fase que lo cerrará:** próxima fase de gestión de Jira.

### 7. Atributos de calidad — 10%

- **Evidencia encontrada:** ninguna matriz de atributos de calidad
  existe todavía — explícitamente fuera de alcance de las fases
  Arquitectura/Testing/Trazabilidad (instrucción 17 de esta fase: "NO
  crear todavía las matrices finales").
- **Nivel defendible hoy:** `PENDIENTE`
- **Brecha:** matriz de atributos de calidad no construida.
- **Recuperable:** sí.
- **Fase que lo cerrará:** fase de Atributos de calidad (futura,
  explícitamente separada).

### 8. Calidad de código — 8%

- **Evidencia encontrada:** 470/470 tests PASS, cobertura 91.72%
  (`artifacts/hito1/testing/coverage-summary.txt`); ningún linter/type
  checker (`ruff`, `flake8`, `mypy`) se ejecutó ni se verificó en esta
  fase ni en la de Testing.
- **Nivel defendible hoy:** `SUFICIENTE_DEFENDIBLE` (evidencia de
  corrección funcional vía tests, sin evidencia de estilo/complejidad).
- **Brecha:** sin verificación de linting/type-checking/complejidad
  ciclomática.
- **Recuperable:** sí.
- **Fase que lo cerrará:** fase de Calidad de código (futura).

### 9. Matriz de riesgo — 10%

- **Evidencia encontrada:** `docs/matriz-riesgo.md` (real, fechada
  05-09-2026), 7 riesgos (R-NASA-FIRMS-01, R-GRILLA-01, R-DMC-01,
  R-CONAF-01, R-COBERTURA-01, R-INTEGRACION-01, R-ETIQUETA-01), varios
  cerrados con evidencia verificable, decisiones de gestión explícitas.
- **Nivel defendible hoy:** `BUENO_DEFENDIBLE`
- **Brecha:** no incorpora todavía los 6 hallazgos del pipeline temporal
  nuevo (`defect-evidence.md`, D-01..D-06) — son hallazgos técnicos, no
  necesariamente riesgos de proyecto, pero al menos D-01 (meteorología
  regional) tiene relación directa con R-DMC-01.
- **Recuperable:** sí.
- **Fase que lo cerrará:** fase de Matriz de riesgo (futura,
  explícitamente separada de esta).

---

## Rúbrica Sprint 1

### 1. Sprint Goal

- **Evidencia encontrada:** ninguna — búsqueda exhaustiva sin resultados.
- **HISTORICAL_SPRINT_GOAL: NOT_FOUND**
- **Nivel:** `INSUFICIENTE_RISK` si la rúbrica exige un Sprint Goal
  explícito documentado desde el inicio.
- **Recuperable:** NO retroactivamente. Se puede ofrecer una
  **RECONSTRUCCIÓN RETROSPECTIVA DEL ALCANCE** (objetivo realmente
  alcanzado, formulado hoy) — nunca presentada como Sprint Goal
  histórico.
- **Fase que lo cerrará:** ninguna puede "recuperar" un Sprint Goal que
  no se escribió; Sprint 2 puede definirlo correctamente desde el inicio.

### 2. HU y refinamiento

- **Evidencia encontrada:** 10 tickets Jira verificables en 2 documentos
  independientes del repo (`docs/informe-1-seminario-licenciatura.md`,
  `docs/matriz-trazabilidad-hu-test.md`): SAPI-26, 28, 30, 32, 33, 44,
  45, 46, 47, 48. Decisiones de refinamiento reales documentadas (p. ej.
  diferir CONAF a Sprint 2, opción B para DMC).
- **Nivel:** `BUENO_DEFENDIBLE` para las HU legacy documentadas;
  **GAP** para el pipeline temporal nuevo (sin HU vinculada, ver
  sección 12 del documento principal).
- **Recuperable:** sí, vinculando/creando HU para el pipeline temporal.
- **Fase que lo cerrará:** próxima gestión de Jira (Sprint 2).

### 3. Criterios de aceptación

- **Evidencia encontrada:** CA históricos resumidos para 8 HU en
  `docs/matriz-trazabilidad-hu-test.md`. El pipeline temporal no tiene
  CA histórico — solo los AC-T01..T10 de cierre (07-09-2026),
  explícitamente NO presentados como CA históricos.
- **Nivel:** `SUFICIENTE_DEFENDIBLE`
- **Brecha:** CA histórico ausente para el incremento más reciente y
  metodológicamente más relevante del proyecto.
- **Recuperable:** parcialmente (formular CA reales para Sprint 2 antes
  de implementar, no retroactivamente para Sprint 1).
- **Fase que lo cerrará:** Sprint 2 (proceso, no esta fase).

### 4. Sprint Backlog / Jira

- **Evidencia encontrada:** ninguna verificada en vivo (en Jira) en esta
  fase. Fuente: export Jira `Jira (4).doc`, externo al repositorio de
  código y correspondiente al estado disponible del tablero al
  07-09-2026, con story points actuales por ticket: 34 SP totales
  asociados a Sprint 1 (21 Finalizados, 13 no finalizados) — ver
  `docs/trazabilidad-hito1.md`, sección 11.
- **Nivel:** `SUFICIENTE_DEFENDIBLE` (mejora desde `PENDIENTE`: ya existe
  un desglose de SP verificado, aunque de fuente externa al repositorio).
- **Brecha (dos brechas distintas, no una sola):** (1) sin sesión en
  vivo sobre el tablero Jira desde esta auditoría; sin snapshot del
  compromiso inicial de Sprint 1 (`ORIGINAL_COMMITMENT_SNAPSHOT:
  NOT_FOUND`) — impide comparar comprometido vs. entregado. (2)
  `VELOCITY: NOT_RECONSTRUCTABLE` **no** se debe a la falta de ese
  snapshot inicial: el export `Jira (4).doc` es un snapshot del estado
  posterior/actual del tablero, no un snapshot verificable de qué
  issues estaban Done exactamente al cierre de Sprint 1 — de hecho
  incluye issues (SAPI-28, SAPI-30) resueltos el 07-09-2026, después de
  la fecha académica planificada de cierre de Sprint 1 (31-08-2026). Por
  eso los 21 SP "Finalizados" actuales no pueden leerse como la
  velocidad de Sprint 1, aunque existiera el snapshot inicial.
- **Recuperable:** sí, en la próxima fase con acceso a Jira en vivo y con
  un snapshot verificado tomado exactamente en la fecha de cierre de
  cada sprint futuro.
- **Fase que lo cerrará:** próxima fase de gestión de Jira.

### 5. Definition of Done

- **HISTORICAL_DOD_EVIDENCE: NOT_FOUND** (ya verificado en la fase de
  Testing y confirmado de nuevo en esta).
- **Nivel:** `INSUFICIENTE_RISK`
- **Recuperable:** NO retroactivamente. Acción recomendada: definir un
  DoD explícito antes de iniciar Sprint 2.
- **Fase que lo cerrará:** ninguna retroactiva; Sprint 2 en adelante.

### 6. Diseño 4+1 o equivalente

- **Evidencia encontrada:** `docs/arquitectura.md` (contenedores Docker,
  Data Contract, tablas PostGIS, resiliencia, ML) y
  `docs/arquitectura-hito1.md` (pipeline temporal) — cubren contenido
  real de despliegue/datos/comportamiento, pero ninguno está organizado
  explícitamente como vistas 4+1 (lógica/proceso/desarrollo/física/
  escenarios).
- **Nivel:** `SUFICIENTE_DEFENDIBLE` — contenido real y verificable,
  formato no canónico.
- **Recuperable:** sí, reorganizando el contenido existente en vistas
  explícitas si la rúbrica lo exige literalmente.
- **Fase que lo cerrará:** no asignada todavía.

### 7. Meetings

- **Evidencia encontrada:** ninguna acta de reunión en el repositorio.
- **Nivel:** `PENDIENTE`
- **Recuperable:** solo si existen registros externos (calendario,
  grabaciones) no incluidos en este repositorio.
- **Fase que lo cerrará:** no asignada.

### 8. Riesgos/impedimentos

- **Evidencia encontrada:** `docs/matriz-riesgo.md` — 7 riesgos con
  evidencia, varios cerrados.
- **Nivel:** `BUENO_DEFENDIBLE`
- **Fase que lo cerrará:** ya sustancialmente cubierto; refinamiento en
  la fase dedicada de Matriz de riesgo.

### 9. Testing / resultados / trazabilidad

- **Evidencia encontrada:** fases Testing + esta fase de Trazabilidad.
- **Nivel:** `BUENO_DEFENDIBLE`
- **Brecha:** igual que Hito1 #4/#6 — HU coverage pendiente.
- **Fase que lo cerrará:** en curso (esta fase la avanza).

### 10. Sprint Review

- **FORMAL_SPRINT_REVIEW_EVIDENCE: NOT_FOUND** (confirmado de nuevo).
- **Nivel:** `INSUFICIENTE_RISK`
- **Recuperable:** NO retroactivamente para Sprint 1.
  `acceptance-protocol.md` queda listo para una sesión real futura.
- **Fase que lo cerrará:** ninguna retroactiva.

### 11. Gestión del cambio

- **Evidencia encontrada:** `artifacts/hito1/testing/defect-evidence.md`
  — 6 hallazgos con hallazgo→análisis→decisión→cambio verificado.
- **Nivel:** `SUFICIENTE_DEFENDIBLE`
- **Brecha:** ningún hallazgo tiene issue Jira vinculado y verificado
  (**PARCIAL — SIN ISSUE VERIFICABLE** para los 6).
- **Recuperable:** sí, vinculando issues en Jira.
- **Fase que lo cerrará:** próxima gestión de Jira.

### 12. Retrospectiva / cierre

- **Evidencia encontrada:** ninguna — no se buscó ni existe un registro
  de retrospectiva de Sprint 1 en el repositorio.
- **Nivel:** `PENDIENTE`
- **Recuperable:** sí, si se ejecuta una retrospectiva real antes de la
  presentación (fase explícitamente separada, no parte de este trabajo).
- **Fase que lo cerrará:** fase de Retrospectiva (futura, no iniciada).

---

## Resumen (sin puntaje inventado)

| Área | Mejor nivel defendible hoy | Motivo principal de no ser EXCELENTE |
|---|---|---|
| Arquitectura | EXCELENTE_DEFENDIBLE | — |
| Riesgos/impedimentos | BUENO_DEFENDIBLE | Sin vincular hallazgos de esta fase |
| Testing / Testing-resultados | BUENO_DEFENDIBLE | HU coverage pendiente, sin aceptación externa |
| HU y refinamiento | BUENO_DEFENDIBLE (legacy) / GAP (pipeline nuevo) | Pipeline temporal sin HU |
| Versionamiento | BUENO_DEFENDIBLE | Convención no verificada formalmente |
| Matriz de riesgo | BUENO_DEFENDIBLE | No incorpora hallazgos nuevos |
| Trazabilidad | SUFICIENTE_DEFENDIBLE | Vínculo HU-pipeline temporal pendiente |
| Criterios de aceptación | SUFICIENTE_DEFENDIBLE | Sin CA histórico para el incremento más nuevo |
| Diseño 4+1 | SUFICIENTE_DEFENDIBLE | Formato no canónico |
| Calidad de código | SUFICIENTE_DEFENDIBLE | Sin linting/type-check verificado |
| Gestión del cambio | SUFICIENTE_DEFENDIBLE | Sin vínculo a issue Jira |
| Atributos de calidad | PENDIENTE | Fase no iniciada (por diseño) |
| Incremento + tablero | BUENO_DEFENDIBLE (incremento) / PENDIENTE (tablero) | Tablero no verificado en vivo |
| Sprint Backlog/Jira | SUFICIENTE_DEFENDIBLE | SP verificados por export externo (34 total/21 finalizados), sin sesión Jira en vivo ni snapshot inicial |
| Meetings | PENDIENTE | Sin evidencia en repo |
| Asistencia | PENDIENTE | Fuera del alcance de un repo de código |
| Sprint Goal | INSUFICIENTE_RISK | No existe evidencia histórica |
| Definition of Done | INSUFICIENTE_RISK | No existe evidencia histórica |
| Sprint Review | INSUFICIENTE_RISK | No existe evidencia histórica |
| Retrospectiva/cierre | PENDIENTE | No ejecutada |

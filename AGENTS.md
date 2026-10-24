# AGENTS.md — S.A.P.I. / directiva permanente para agentes

Este workspace se usa EXCLUSIVAMENTE para S.A.P.I. (Sistema de Alerta y Predicción de Incendios). Antes de cualquier intervención, leer `docs/ai/SAPI_CONTEXT.md` y consultar `docs/architecture-stack-freeze-sprint2.md`.

Respetar el alcance pedido. La preparacion de herramientas no autoriza iniciar sprints, cerrar issues, publicar comentarios, fusionar ni desplegar.

## Estado Real de la Arquitectura (Distinción Obligatoria)
Los agentes deben distinguir taxativamente el nivel de madurez técnica de cada componente:
1. **Arquitectura Implementada y Operativa (Línea Base Verificada):**
   - Frontend Streamlit + Folium: dashboard de ranking territorial de 50 celdas (Valparaíso), panel de detalle y navegación tabla↔mapa (en validación bajo PR #30).
   - Ingesta y Versionado de Datos: pipelines de NASA FIRMS y DMC con almacenamiento inmutable (`CURRENT.json`, `pointer_history.json`), refresh atómico e idempotente (SAPI-71).
   - Topografía: modelo de elevación Copernicus DEM GLO-30 (cobertura parcial; celdas sin datos catalogadas como `N/D`).
   - Microservicio ML FastAPI: encapsula el Modelo D (`HistGradientBoostingClassifier`, `POST /predict`), operando bajo ranking relativo y F4 FAIL.
   - Orquestación Local: Docker Compose v2 levantando contenedores con aislamiento de red.
2. **Arquitectura Parcialmente Integrada (Vertical Slice / Transición v2):**
   - Backend Spring Boot: endpoints REST (`GET /api/v1/ranking`) para orquestación de inferencia con timeouts y degradación controlada (SAPI-57).
   - Persistencia Operacional: persistencia write-through vía Spring JDBC en PostgreSQL 15 / PostGIS 3.4 (tablas `ejecuciones` y `predicciones_celda` para 50 celdas, SAPI-43/59).
   - Contratos OpenAPI: especificación OpenAPI v0 establecida; desacoplamiento total en curso.
3. **Funcionalidades Planificadas (Backlog Futuro / No Integradas en Sprint 2):**
   - Infraestructura Cloud: Spike y ADR de proveedor cloud (ADR-011 / SAPI-67 permanece en estado PROPUESTO, sin firma); despliegue cloud (SAPI-68) para Hito 3.
   - Modelos Temporales y Avanzados: Secuencias temporales causales 3D, Walk-Forward y redes LSTM (SAPI-64/65); dictaminadas técnicamente como INVIABLES con los datos actuales.
   - Orquestación n8n: contenedor configurado pero desacoplado operativamente; disparadores y alertas automáticas a terceros estrictamente congelados/no implementados.
   - Validación Científica: probabilidades calibradas de incendio, ground truth externo CONAF/SENAPRED y validación experimental externa (F4).

## Autoridad y orden de evidencia
1. Código fuente, artefactos y pruebas reproducibles de la revisión Git actual, Docker Compose y contratos efectivos.
2. GitHub y Jira vivos (con fecha, issue/PR/SHA); documentos docentes, matrices de rúbricas y syllabus originales.
3. Documentación interna del repositorio.
4. Resúmenes históricos, prompts e informes previos (no constituyen prueba de estado actual).
Si hay discrepancia, NO reconciliar silenciosamente: documentar la contradicción, fecha, fuente y bloqueo.

## Invariantes científicos NO negociables
- El Modelo D entrega un **ranking relativo exploratorio**; NO es probabilidad calibrada de incendio, alerta oficial, sistema operacional validado ni garantía predictiva.
- F4 = FAIL y `scientific_model_validation=false` hasta que evidencia reproducible y revisión humana formal autoricen modificar estas declaraciones.
- Distinguir rigurosamente tests de software, E2E y reproducibilidad de validación externa con datos históricos etiquetados, métricas científicas y/o comisiones docentes.
- Nunca inventar scores, accuracy/F1, timestamps, datos FIRMS/DMC, cobertura DEM, aprobación CONAF/SENAPRED, ni resultados docentes.
- Preservar datos científicos congelados, linaje inmutable de DMC/FIRMS CURRENT/versiones, contratos API, idempotencia, rollback y DEM N/D donde no hay cobertura satelital.

## Skills del proyecto (Antigravity e IDEs)
Las skills operan a demanda mediante progressive disclosure en `.agents/skills/`:
- `.agents/skills/sapi-academic-defense/SKILL.md`: Doble rúbrica César/Matías, Informe 2 y defensa académica.
- `.agents/skills/sapi-scientific-integrity/SKILL.md`: Modelo D, score relativo, F4 FAIL y claims científicos.
- `.agents/skills/sapi-sprint-close/SKILL.md`: Cierre técnico de Sprint 2 y matriz de gates G0-G7.
- `.agents/skills/sapi-e2e-quality/SKILL.md`: Pruebas de integración, ranking API y QA de interfaz Streamlit/Folium.
- `.agents/skills/sapi-release-engineering/SKILL.md`: Auditoría de PR #30, checks de release y squash merge seguro.
- `.agents/skills/sapi-jira-traceability/SKILL.md`: Trazabilidad HU/CA/Jira sin escrituras rutinarias.
- `.agents/skills/sapi-mcp-governance/SKILL.md`: Seguridad y menor privilegio en conectores MCP.
- `.agents/skills/sapi-roadmap-strategy/SKILL.md`: Planificación post-Hito 2 (CONAF, LSTM, Cloud ADR).

## Skills y configuración Claude Code / Desktop (Preservadas)
Se conservan las herramientas preexistentes en `.claude/skills/`:
- .claude/skills/sapi-scientific-integrity/SKILL.md: modelo, features, targets, evaluacion y claims.
- .claude/skills/sapi-jira-workflow/SKILL.md: trabajo vinculado a issues SAPI.
- .claude/skills/sapi-definition-of-done/SKILL.md: revision de cumplimiento antes de declarar terminado.
- .claude/skills/sapi-evidence-first/SKILL.md: evidencias reproducibles de cambios y experimentos.
- .claude/skills/sapi-professional-word: Conservar para redacción y maquetación de documentos académicos en Word.

## Diseño
Usar Impeccable para propuestas y revision visual del dashboard respetando Streamlit. Taste (design-taste-frontend) esta disponible para landing pages o portafolio: su version instalada excluye dashboards y tablas de datos. No forzarla sobre el panel operativo.
Ninguna skill de diseno autoriza migrar a React, inventar series o presentar scores como probabilidades calibradas. Reutilizar componentes y tokens existentes. Verificar cambios de UI en navegador cuando corresponda.

## Colaboración y Gobernanza MCP
Codex plugin esta disponible para revisiones y delegaciones solicitadas. Preferir revision de solo lectura como primera prueba. Evitar dos agentes escribiendo simultaneamente en los mismos archivos. Una revision de IA no sustituye pruebas ni validacion cientifica.
No activar MCP desconocidos. No imprimir ni versionar tokens, claves, credenciales, `.env`, datos privados ni configuraciones personales. Conectores GitHub y Jira en solo lectura; PostgreSQL restringido a SELECT; n8n desacoplado sin disparadores de alertas reales.

## Protocolo corto por tarea
1. Identificar HU/CA/rúbrica/sprint; revisar Jira y GitHub actual.
2. Clasificar: (A) documental, (B) científica, (C) software, (D) infraestructura, (E) liberación.
3. Seleccionar Skill específica. Ejecutar el mínimo de validación suficiente y preservar evidencia reproducible.
4. Reportar: hechos verificados / reportados / pendientes; resultados con rutas, SHA, timestamp y comandos.
5. Mantener notas durables en `docs/ai/` sin convertirlas en verdad histórica si están desactualizadas.

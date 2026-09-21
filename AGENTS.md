# S.A.P.I. — contexto para agentes

Consultar docs/architecture-stack-freeze-sprint2.md antes de proponer cambios de arquitectura. Distinguir lo implementado de lo planificado: Streamlit se conserva; Spring Boot, FastAPI y PostGIS son la arquitectura objetivo del nuevo pipeline, no evidencia de integracion actual.

Respetar el alcance pedido. La preparacion de herramientas no autoriza iniciar sprints, cerrar issues, publicar comentarios, fusionar ni desplegar.

## Skills del proyecto
- .claude/skills/sapi-scientific-integrity/SKILL.md: modelo, features, targets, evaluacion y claims.
- .claude/skills/sapi-jira-workflow/SKILL.md: trabajo vinculado a issues SAPI.
- .claude/skills/sapi-definition-of-done/SKILL.md: revision de cumplimiento antes de declarar terminado.
- .claude/skills/sapi-evidence-first/SKILL.md: evidencias reproducibles de cambios y experimentos.
- Conservar sapi-professional-word para documentos academicos.

## Diseno
Usar Impeccable para propuestas y revision visual del dashboard respetando Streamlit. Taste (design-taste-frontend) esta disponible para landing pages o portafolio: su version instalada excluye dashboards y tablas de datos. No forzarla sobre el panel operativo.
Ninguna skill de diseno autoriza migrar a React, inventar series o presentar scores como probabilidades calibradas. Reutilizar componentes y tokens existentes. Verificar cambios de UI en navegador cuando corresponda.

## Colaboracion
Codex plugin esta disponible para revisiones y delegaciones solicitadas. Preferir revision de solo lectura como primera prueba. Evitar dos agentes escribiendo simultaneamente en los mismos archivos. Una revision de IA no sustituye pruebas ni validacion cientifica.

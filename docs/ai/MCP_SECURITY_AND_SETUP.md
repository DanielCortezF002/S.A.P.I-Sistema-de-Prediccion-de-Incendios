# MCP para S.A.P.I. — catálogo y política de instalación

**NO se incluyen MCP activos ni tokens en este kit.** Cada conector requiere instalación/autenticación voluntaria y prueba de mínima capacidad. Consultar primero herramientas ya conectadas: no duplicar integraciones.

| Orden | Conector | Necesidad y capacidad inicial | Restricción |
|---|---|---|---|
| 1 | GitHub MCP | PR, ramas, commits, checks, cambios | Empezar READ, push/merge sólo con autorización específica |
| 2 | Jira / Atlassian MCP | Sprint, issues, CA, estados, trazabilidad | Empezar READ; transición/comentarios bajo aprobación |
| 3 | Playwright / browser MCP | Pruebas reales Streamlit/Folium, screenshots | Solo localhost/staging autorizado; no datos personales |
| 4 | PostgreSQL MCP | Esquemas, consultas, verificación PostGIS | Credenciales **RO**, permisos SELECT restringidos; prohibido DROP/UPDATE/INSERT |
| 5 | Filesystem MCP (si hace falta) | Leer documentación/rúbricas fuera de repo | Acotar a carpetas SAPI; nunca perfil completo ni `.env` |
| 6 | n8n MCP (opcional) | Inspección de orquestación y workflows | RO por defecto; NO activar ejecuciones, disparadores o envíos |

**Antes de instalar:** verificar la procedencia oficial, repo, permisos y binarios; prueba de confianza, versión y alcance; no ejecutar `npx` remoto sin revisión ni copiar comandos con tokens visibles.

**Antigravity IDE:** panel agente → `…` → `MCP Servers` → `Install` para servidores disponibles; para custom `Manage MCP Servers` → `View raw config`. Documentación: https://antigravity.google/docs/mcp. Archivo global: `~/.gemini/config/mcp_config.json`; workspace `.agents/mcp_config.json` donde esté soportado. Mantener secretos fuera de Git.

**Claude Desktop:** Settings → Extensions → Browse extensions para MCP locales `.mcpb`; conectores SaaS bajo Customize → Connectors/Settings → Connectors según interfaz disponible. No suponer que chat, Cowork y Claude Code pueden usar los mismos MCP locales. Ver https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop

**Prueba de funcionamiento:** consultar en GitHub PR #30 RO, consultar Jira SAPI-71 RO, consultar tabla PostGIS RO si conectado, capturar screenshot localhost sólo si autorizado. Registrar herramienta real y si falta conector informar 'NO CONECTADO'.

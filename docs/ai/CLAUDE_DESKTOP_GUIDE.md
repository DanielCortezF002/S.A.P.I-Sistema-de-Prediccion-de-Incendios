# Claude Desktop y Claude Code — Skill S.A.P.I.

- **Claude Desktop chat:** importar el archivo individual `claude-desktop-sapi-academic.zip` (y opcionalmente los otros ZIP) desde Customize → Skills → + → Create skill → Upload a skill. Cada ZIP tiene **una carpeta raíz de Skill** con `SKILL.md`. Activar el interruptor. Fuente: https://support.claude.com/en/articles/12512180-use-skills-in-claude
- **Claude Desktop MCP:** Settings → Extensions para MCP local, Customize → Connectors para proveedores remotos. No asumas acceso al filesystem del PC desde chat; solicita conectar la carpeta/adjuntar rúbrica cuando corresponda.
- **Claude Code:** inspeccionar la versión local y usar Skills bajo `.claude/skills/<name>/SKILL.md` o la ruta soportada por la versión en uso. Se puede copiar el contenido de `.agents/skills/*` sin secretos para esta instancia. Antes de cambiar `CLAUDE.md` existente, inspeccionar y fusionar manualmente.
- **Skills de Claude listas en el kit:** académico (informes/rúbricas), científico (validez F4) y cierre del sprint (Jira/Git/QA). La skill no conecta las herramientas por sí sola.
- **Uso recomendado:** Antigravity ejecuta código y captura evidencia; Claude Desktop prepara documentos y revisa material real, separando hechos comprobados de reportes. Claude no debe ejecutar cambios sin autorización.

---
name: sapi-mcp-governance
description: "Revisar, elegir y configurar Skills y servidores MCP para S.A.P.I., manteniendo permisos mínimos, procedencia comprobable y sin publicar secretos."
---

# S.A.P.I. / Gobierno de Skills y MCP
Revisar primero `docs/ai/MCP_SECURITY_AND_SETUP.md`. Inventariar MCP/skills instalados en Antigravity y Claude; no duplicar ni instalar servicios solo porque existan.
Fase 1: GitHub y Atlassian en solo lectura. Fase 2: Playwright/browser y PostgreSQL con usuario SELECT-only. Fase 3: n8n si es imprescindible y sin ejecuciones automáticas.
Para cada MCP verificar procedencia, permisos, dependencia local, binding de credenciales, actualizaciones, conflictos de nombres y superficie (chat/Cowork/Code).
No copiar tokens en prompts, `.agents/`, logs, git, respuestas o scripts. Archivos de config locales secretos fuera del control de versiones.
Solicitar consentimiento antes de instalar, autenticar, modificar configuración o cambiar permisos. Registrar versión/capacidades comprobadas.
Salida: inventario ACTIVO/PROPUESTO/RECHAZADO y plan en orden de menor riesgo.

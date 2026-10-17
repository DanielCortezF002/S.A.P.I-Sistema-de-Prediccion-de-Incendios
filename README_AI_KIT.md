# Paquete S.A.P.I. Agent Suite — Antigravity + Claude Desktop

**Contenido:** `SAPI_AI_KIT/` (los archivos de esta carpeta son propuesta de instalación en el repo), `install_sapi_ai.ps1` y tres ZIP individuales para Claude Desktop.

### Instalación segura (PowerShell en tu PC)
1. Descomprime este ZIP en una carpeta temporal.
2. Abre Antigravity apuntando a `C:\SAPI-PUBLICACION-SEGURA-20261016` solo si `git rev-parse --show-toplevel` confirma que es el checkout autorizado.
3. Lee el `AGENTS.md` propuesto antes de incorporarlo. Si ya existe `AGENTS.md`, fusionar manualmente.
4. Desde PowerShell en la carpeta descomprimida ejecuta primero:
   `powershell -ExecutionPolicy Bypass -File .\install_sapi_ai.ps1 -RepoPath "C:\SAPI-PUBLICACION-SEGURA-20261016"`
   Es **modo verificación** y NO copia nada.
5. Para copiar archivos sin sobreescribir ninguno, si apruebas cambios:
   `powershell -ExecutionPolicy Bypass -File .\install_sapi_ai.ps1 -RepoPath "C:\SAPI-PUBLICACION-SEGURA-20261016" -Apply`
6. Revisa `git status` y el diff; crea rama separada para la instalación de skills. No subir datos o configuración con secretos.
7. En Antigravity IDE revisa panel agente → Customizations/Skills; invoca `/sapi-sprint-close` o `/sapi-academic-defense`.
8. Para Claude Desktop, sube uno de los ZIP individuales en Customize → Skills → + → Upload a skill. No cargues el paquete completo como una sola skill.

**Advertencias:** Los Skills NO instalan MCP; los conectores requieren consentir e instalar en cada aplicación. No se modifica Git, Docker, DB, GitHub ni Jira desde este paquete. El informe de cierre requiere datos actuales, no solo snapshot.

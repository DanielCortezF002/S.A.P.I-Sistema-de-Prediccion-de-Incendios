---
name: sapi-release-engineering
description: "Revisar releases, PRs, Docker, CI y squash merge seguro para S.A.P.I.; activar antes de branch, cambios en main o publicación de demo."
---

# S.A.P.I. / Release engineering
1. Inspeccionar `git status`, rama, `origin/main`, remotes, SHA, diff y cambios ajenos ANTES de editar.
2. Determinar objetivo limitado + CA, asegurar rama aislada y plan de rollback.
3. Verificar suite específica + contratos + E2E según cambio. Distinguir 411 pruebas seleccionadas de total repo y CI remoto (si 0 checks, no declarar PASS).
4. Para Docker: preservar db y volúmenes, NO `down -v`, no sobrescribir stores ni datos científicos; validar imagen reproducible, no solo docker cp.
5. Comparar cambios con F4, DEM, OpenAPI y reproducibilidad; registrar screenshots y logs con SHA.
6. Push/PR y squash merge son acciones distintas; solicitar consentimiento explícito para cada tramo destructivo o público cuando aplique. PR #30 abierto en snapshot.
7. Verificar rama/main después del merge y documentar release note/rollback.
Salida: checklist GO/NO-GO + riesgo residual + SHA + comandos/evidencias + autorización faltante.

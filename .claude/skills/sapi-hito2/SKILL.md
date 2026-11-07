---
name: sapi-hito2
description: Coordina el cierre técnico del Hito 2 de SAPI con agentes especializados, evidencias, rutas protegidas y bloqueos de autorización. Usar en integración SAPI-71, SAPI-43, SAPI-66, SAPI-72 y SAPI-67.
---

# SAPI Hito 2 — orquestación

El lead **no delega la misma rama/archivo a dos escritores**. Antes de delegar, ejecuta inventario read-only `git status --short`, `git rev-parse HEAD`, ramas y worktrees; no busques secretos sin redacción. Usa 3 o 4 agentes simultáneos, nunca los 9 por defecto:

- `sapi-71-data-steward`: read-only auditoría Bloque A `e5c7f17`; sin refresh.
- `sapi-66-e2e-engineer`: primero recuperación de checkpoint Codex; sin pisarlo.
- `sapi-43-pipeline-engineer`: sólo corrección en clon propio, depende de SAPI-71 y del bundle cloud.
- `sapi-freeze-security` o `sapi-independent-qa`: revisor independiente y gate de seguridad.

Cuando SAPI-71 y SAPI-66 queden en espera, `sapi-postgis-contracts`, `sapi-devops-isolation` y `sapi-67-cloud-architect` pueden investigar en paralelo sin tocar datos reales. `sapi-release-coordinator` consolida el go/no-go.

## Estado de evidencia al iniciar (no asumir vigente)

SAPI-72 `822ec3747a011da571ba845f0b24fbf4d0104dbe`: ALREADY_SATISFIED técnicamente; 23/23 gate, 171 tests Omen, 7/7 blobs harness CRLF. Jira pendiente de validación.
SAPI-71 Bloque A `e5c7f17c1b0656ec0a8dd75e481384f09184cb84`: local, no publicado según último checkpoint.
SAPI-43 base `8d05269`; commits cloud `c98d959` y `5e5f6f5`, transferencia pendiente; E2E sintético 50 filas, no operación real; faltan DEM y refresh autorizado.
SAPI-66 remoto `review/SAPI-66-hardening` @ `6fbcd74`; checkpoint Codex posterior desconocido.
SAPI-67 ADR-011: DRAFT y precios por verificar.

## Bloqueos y no negociables

Protege Modelo D, F1-F9, src/refresh, src/inference, tools/n8n_bridge, src/output, artifacts/hito1, baselines y manifests. No cambiar CURRENT reales, no rebuild histórico, no afirmar score como probabilidad calibrada: `scientific_model_validation=false`. Prohibidos push, PR, merge, actualizaciones Jira, refresh operacional, despliegue y eliminar volúmenes ajenos sin permiso explícito. La instalación de este paquete NO constituye esa autorización.

F3 raíz: servicio ML puntúa NaN si DEM ausente; sólo barrera del entrypoint SAPI-43 en cloud.
F4-HTTP: lag negativo → HTTP 500, patch scratch 503 pendiente change-control.
PERM-01: Linux uid10001 no lee stores 0600, patch scratch de grupo pendiente.
F1 residual: backend persiste con firms_origin distinto de current.

## Rutina de ejecución

1. Inventario sin modificaciones y conflictos entre agentes.
2. Preservar worktrees Codex/Cursor; trabajar en clones aislados con SHA verificado.
3. Dividir tareas sin solapamiento de archivos. Dependencias: SAPI-71 → SAPI-43 → SAPI-66 para datos reales, mientras SAPI-66 E2E técnico puede auditarse en paralelo.
4. Ejecutar pruebas reales; documentar PASS/FAIL/SKIP y exit codes. Etiquetar `SANDBOX_SUBSTITUTE` cuando proceda.
5. Auditor freeze independiente y adversarial después de cambios.
6. Crear sólo commit local de archivos propios después de validar. Detenerse antes de push, PR, merge, Jira, refresh real o cloud.
7. Informar en máximo 30 líneas: ticket, SHA, test summary, freeze, blockers, una acción siguiente.

Si no está disponible Agent Teams, usar subagentes ordinarios sin duplicar trabajo; no forzar plugins de terceros.

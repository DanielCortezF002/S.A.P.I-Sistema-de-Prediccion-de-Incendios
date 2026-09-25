# Workspace operacional canónico

`src/ops/operational_workspace.py` crea un directorio operacional **nuevo** que cumple `workspace_safety` en modo `OPERATIONAL_REAL_DATA` (ver [WORKSPACE-SAFETY-GUARD.md](WORKSPACE-SAFETY-GUARD.md)). Resuelve CRR-OPS-02 sin tocar el WIP ni los stores de origen.

## Por qué un workspace nuevo
Hoy el código integrado y los stores reales viven en checkouts distintos, y el checkout operacional llegaba a los stores mediante **junctions**. Ninguna topología existente pasa la guarda.

Se descartan dos alternativas:
- hacer checkout de `main` dentro del WIP, que contiene estado histórico sin commit y debe quedar intacto;
- flexibilizar la guarda.

El workspace nuevo contiene código de un SHA exacto más **copias físicas** de `data/raw`, `data/processed` y `models`.

## Flujo
```
plan (solo lectura) → revisión humana → materialize --confirm-real-copy <PLAN_ID>
   → staging (<destino>.staging-<run_id>)
      1. código: git fetch --depth 1 <repo> <SHA> + checkout --detach
         (core.autocrlf=false: bytes del commit; sin remotos; 1 commit)
      2. CODE-IDENTITY.json (sha, tree, repo de origen, materialized_at)
      3. copia byte a byte de cada store (archivos nuevos exclusivos; nunca
         move, rename, hardlink, symlink ni junction; conserva mtime)
      4. re-inventario y re-hash de la fuente → debe ser idéntica (si no: FAIL)
      5. verificación destino: mismo conjunto, tamaños, sha256; inodo propio
      6. escaneo: sin enlaces/reparse points; escaneo de secretos (solo rutas)
      7. workspace_safety OPERATIONAL_REAL_DATA sobre el staging → debe ser PASS
      8. OPERATIONAL-WORKSPACE-MANIFEST.json (VALIDATED)
   → renombre atómico staging → destino (se rechaza si el destino existe)
   → workspace_safety sobre el destino → PROMOTED
```
Si falla cualquier paso, el staging queda con `MATERIALIZATION-FAILED.json` y el manifiesto marca `FAILED`. **No se promueve y no se borra nada.** La limpieza es una decisión humana: el staging contiene solo copias.

**Detalles:**
- El plan exige los tres stores. Un store que sobrescribiría un archivo commiteado con otro contenido (p. ej. `models/prototype_model_d.pkl`) es FAIL; si el contenido es idéntico, queda verificado como `identical_to_committed`.
- `.git/info/exclude` del workspace (local, no commiteado) excluye los metadatos y las rutas de store: el código se verifica con Git y los stores con el manifiesto.
- CURRENT, history y los raw del Attempt 1 se copian **tal cual**. No se crea ni se altera ningún CURRENT.
- El workspace **no** es un build context de Docker: usar `git archive` y comprobar con `workspace_safety --mode docker-build`.

## CLI
```powershell
python -m src.ops.operational_workspace plan `
  --repo-root "D:\portafolio y seminario\S.A.P.I-Sistema-de-Prediccion-de-Incendios-main" `
  --code-sha <40 hex> `
  --source-store raw="...\data\raw" --source-store processed="...\data\processed" --source-store models="...\models" `
  --destination "D:\portafolio y seminario\SAPI-operational-canonical"

python -m src.ops.operational_workspace materialize <mismos argumentos> --dry-run
python -m src.ops.operational_workspace materialize <mismos argumentos> --confirm-real-copy <PLAN_ID>   # GATE HUMANO
python -m src.ops.operational_workspace verify --workspace <destino>
python -m src.ops.operational_workspace status --destination <destino>
```
Opciones: `--stage-only` valida sin promover; `--margin-bytes N` fija el margen (por defecto max(256 MiB, 10 %)); `--json`; `--json-out` (nunca dentro de un store).

| Exit | Significado |
|---|---|
| 0 | PASS |
| 1 | FAIL |
| 2 | Uso inválido |
| 3 | INCOMPLETE |
| 4 | BLOCKED: falta `--confirm-real-copy`, o el `PLAN_ID` no coincide con el plan actual |

`PLAN_ID` es un hash de las entradas, del tree, del destino y del **listado completo** de cada store (ruta, tamaño, mtime) más los archivos críticos. Si algo cambia entre el plan revisado y la copia, la copia queda BLOCKED.

## Hallazgos
| ID | Código | Nota |
|---|---|---|
| MW-001 | INVALID_OR_UNKNOWN_SHA | SHA de 40 hex que exista como commit |
| MW-002 | SOURCE_STORE_MISSING | |
| MW-003 | SOURCE_STORE_ROOT_REPARSE | **WARN**: se lee desde la ruta física resuelta |
| MW-004 | SOURCE_STORE_INTERNAL_REPARSE | Enlaces dentro de un store: FAIL (no se siguen) |
| MW-005 | DESTINATION_EXISTS | Nunca se sobrescribe |
| MW-006 | DESTINATION_REPARSE | |
| MW-007 | DESTINATION_OVERLAP | Con el repo o con un store |
| MW-008 | INSUFFICIENT_SPACE | Antes de escribir |
| MW-009 | TRACKED_FILE_CONFLICT | |
| MW-010 | SOURCE_UNREADABLE | Desconocido ⇒ FAIL |
| MW-011 | SECRET_DETECTED | En el commit (nombres y URL con MAP_KEY vía `git grep`) o en el staging. Se registran solo rutas |
| MW-012 | COPY_VERIFICATION_MISMATCH | |
| MW-013 | SOURCE_CHANGED_DURING_COPY | |
| MW-014 | DESTINATION_NOT_PHYSICAL | Enlace o hardlink hacia la fuente |
| MW-015 | WORKSPACE_SAFETY_NOT_PASS | |
| MW-016 | STAGING_CONFLICT | |
| MW-017 | DESTINATION_PARENT_MISSING | |
| MW-018 | REQUIRED_STORE_NOT_DECLARED | |
| MW-019 | GIT_EXTRACTION_FAILED | |
| MW-020 | UNKNOWN_STORE_NAME | |

## Integración con el operador del Attempt 2
```python
from src.ops.operational_workspace import run
req = {"repo_root": ..., "code_sha": ..., "destination": ...,
       "source_stores": {"raw": ..., "processed": ..., "models": ...}, "margin_bytes": None}
p = run("plan", req)                                   # 1. solo lectura
# 2. GATE HUMANO: mostrar p, obtener confirmación explícita de p["plan_id"]
r = run("materialize", {**req, "confirm_plan_id": p["plan_id"]})   # 3.
v = run("verify", {"workspace": req["destination"]})   # 4. solo lectura
# 5. preflight del Attempt 2 con code_root = destino (workspace_safety PASS de nuevo)
```

**Resultados:**
- `plan`: `plan_id`, `code{sha,tree,commit_exists,blob_bytes,secret_scan}`, `source_stores[]{logical_name,requested_path,resolved_path,file_count,total_bytes,listing_digest,critical_files}`, `destination`, `space`, `findings[]`, `overall_status`.
- `materialize`: `overall_status` (`PASS`|`FAIL`|`BLOCKED`), `promotion_status` (`DRY_RUN`|`VALIDATED`|`PROMOTED`|`PROMOTED_POSTCHECK_FAILED`|`FAILED`|`NOT_STARTED`), `staging`, `destination`, `manifest`, `findings[]`, `exit_code`.
- `verify`: `drifted_files[]`, `workspace_safety`, `overall_status`.

Después de un refresh real, los stores cambian legítimamente: `verify` reportará drift respecto del manifiesto de materialización. Es esperable, y lo relevante es la guarda.

El operador procede solo con `promotion_status == "PROMOTED"` y una nueva evaluación de `workspace_safety` en PASS inmediatamente antes de cada escritura protegida.

## Límites
- La detección de cambios en la fuente combina listado (tamaño y mtime) con re-hash completo después de la copia. Un cambio que se revierta exactamente durante la copia no es detectable.
- El escaneo de secretos es por patrones: puede dar falsos positivos (bloquean) y no encuentra todo.
- El renombre atómico requiere que el staging y el destino estén en el mismo volumen (se crean como hermanos).

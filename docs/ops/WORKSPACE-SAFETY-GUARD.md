# Workspace Safety Guard (CRR-OPS-02)

`src/ops/workspace_safety.py` comprueba, **solo observando**, que el checkout de código y los stores reales tengan la topología que exige un modo de operación. Nunca crea ni borra enlaces, no hace checkout, reset ni stash, no monta, no arranca Docker, no ejecuta refresh y no toca CURRENT. Git se consulta únicamente con comandos de lectura y `--no-optional-locks`.

Un **PASS** significa solo que la topología observada cumplió la política declarada en `observed_at`. **No autoriza** ninguna operación y no garantiza el estado futuro. **UNKNOWN nunca es PASS.**

## Por qué existe
- La autoridad de código es el checkout integrado, pero los stores reales viven históricamente en el checkout WIP.
- Un worktree post-merge con `data/` y `models/` enlazados a esos stores fue un casi-incidente: un refresh desde ahí habría escrito en los stores reales.
- Parte del código fija rutas relativas a la raíz del repo (`firms_source.FIRMS_CURRENT_DIR`, `prototype_service.MODEL_PATH`), mientras `src.config` acepta `DATA_RAW_DIR`, `DATA_PROCESSED_DIR`, `DATA_PREDICTIONS_DIR` y `MODELS_DIR`. Por eso el guard verifica el **binding efectivo**: dónde leerá y escribirá realmente el código en `code_root` (`data/raw`, `data/processed`, `data/predictions`, `models`). Si alguno de esos overrides está activo, lo reporta, porque dividiría las rutas.

## Modos
| Modo | Uso | Política |
|---|---|---|
| `READ_ONLY` | Inspección | Reporta todo; tolera topología (WARN); lo desconocido queda INCOMPLETE. **Un PASS aquí no sirve como autorización para los otros modos** |
| `TEST_ISOLATED` | Correr tests sobre una copia | FAIL si el checkout expone stores reales (datos dentro o enlaces hacia ellos) o si el SHA/tree no coincide |
| `OPERATIONAL_REAL_DATA` | Refresh o scoring sobre stores reales | FAIL si el SHA completo no coincide, si hay cambios sin commit, si la raíz o los stores tienen indirección, si hay un store ambiguo o en otro checkout, si el binding no coincide con los stores declarados, si hay overrides o si la identidad es desconocida |
| `DOCKER_BUILD` | Antes de `docker build` | FAIL si el contexto contiene datos locales no versionados en `data/*` o `models`, o cualquier enlace/reparse point. Recomienda `git archive <sha>`. Un contexto sin Git (p. ej. un archive) queda como máximo INCOMPLETE |

## CLI
```powershell
python -m src.ops.workspace_safety check `
  --mode operational-real-data `
  --code-root "D:\ruta\checkout" `
  --expected-code-sha <40 hex> [--expected-tree-sha <40 hex>] `
  --store raw="D:\ruta\checkout\data\raw" `
  --store processed="D:\ruta\checkout\data\processed" `
  --store models="D:\ruta\checkout\models" `
  [--expected-store raw=<ubicación física esperada>] [--allow-dirty | --require-clean] `
  [--json] [--json-out <archivo fuera de los stores>]
```

| Exit | Significado |
|---|---|
| 0 | PASS |
| 1 | FAIL |
| 2 | Uso inválido (argparse), o `--json-out` dentro de un store |
| 3 | INCOMPLETE (algo no se pudo determinar) |

## Hallazgos
| ID | Código | READ_ONLY | TEST_ISOLATED | OPERATIONAL | DOCKER |
|---|---|---|---|---|---|
| WS-001 | WRONG_CODE_SHA | WARN | FAIL | FAIL | FAIL |
| WS-002 | DIRTY_CODE | WARN | WARN | FAIL¹ | FAIL¹ |
| WS-003 | CODE_ROOT_REPARSE | WARN | WARN | FAIL | FAIL |
| WS-004 | STORE_PATH_MISMATCH | WARN | WARN | FAIL | WARN |
| WS-005 | STORE_REPARSE | WARN | WARN | FAIL | WARN |
| WS-006 | CODE_STORE_OVERLAP (incluye store dentro de otro checkout) | WARN | FAIL | FAIL | FAIL |
| WS-007 | DOCKER_REAL_STORE_EXPOSURE | WARN | WARN | WARN | FAIL |
| WS-008 | UNKNOWN_FILESYSTEM_IDENTITY | INCOMPLETE | INCOMPLETE | FAIL | FAIL |
| WS-009 | STORE_MISSING | INCOMPLETE | WARN | FAIL | INFO |
| WS-010 | STORE_ALIAS (mismo lugar físico o anidados) | WARN | WARN | FAIL | WARN |
| WS-011 | CODE_STORE_PATH_INDIRECTION (`data/*` o `models` enlazados) | WARN | FAIL | FAIL | FAIL² |
| WS-012 | CODE_STORE_BINDING_MISMATCH | WARN | INFO | FAIL | INFO |
| WS-013 | CODE_IDENTITY_UNAVAILABLE | INCOMPLETE | INCOMPLETE | FAIL | INCOMPLETE |
| WS-014 | WRONG_TREE_SHA | WARN | FAIL | FAIL | FAIL |
| WS-015 | EXPECTED_SHA_REQUIRED (SHA ausente o abreviado) | INFO | INFO | FAIL | WARN |
| WS-016 | STORE_ENV_OVERRIDE (solo nombres, nunca valores) | WARN | WARN | FAIL | WARN |
| WS-017 | CODE_ROOT_NOT_TOPLEVEL | WARN | WARN | FAIL | FAIL |
| WS-018 | STORES_NOT_DECLARED | INFO | INFO | FAIL | INFO |

¹ Pasa a WARN con `--allow-dirty` o `require_clean=False`.
² En DOCKER_BUILD se reporta como WS-007.

Windows: los enlaces se detectan con `os.lstat`, usando `st_file_attributes` (`FILE_ATTRIBUTE_REPARSE_POINT`) y `st_reparse_tag` (junction `0xA0000003`, symlink `0xA000000C`, otros tags → `reparse_other`), en **cada componente** de la ruta. `Path.is_symlink()` sola no ve las junctions.
Identidad física: `(st_dev, st_ino)`. Si `st_ino` es 0 o ilegible, la identidad queda desconocida (WS-008).

## ATTEMPT 2 OPERATOR INTEGRATION

**Llamable Python** (sin efectos secundarios):
```python
from src.ops.workspace_safety import run, check_workspace, GuardRequest, Mode
result = run({
    "mode": "OPERATIONAL_REAL_DATA",           # o "operational-real-data"
    "code_root": "D:/...",
    "expected_code_sha": "<40 hex>",            # obligatorio en OPERATIONAL
    "expected_tree_sha": "<40 hex>",            # opcional
    "stores": {"raw": "...", "processed": "...", "models": "..."},
    "expected_stores": {"raw": "..."},          # opcional: ubicación física esperada
    "require_clean": True                       # opcional; por defecto True en OPERATIONAL/DOCKER
})
```

**Esquema del resultado** (`schema_version: 1`):
- Campos: `guard`, `mode`, `observed_at` (UTC ISO), `policy`, `code`, `stores[]`, `topology`, `findings[]`, `warnings[]`, `failures[]`, `incomplete[]`, `overall_status` (`PASS`|`FAIL`|`INCOMPLETE`), `exit_code`, `disclaimer`.
- `code`: `requested_path`, `resolved_path`, `reparse_points[]`, `is_git`, `head_sha`, `tree_sha`, `branch`, `dirty`, `dirty_count`, `dirty_sample[]`, `is_linked_worktree`, `sha_match`, `tree_match`, `expected_code_sha`, `expected_tree_sha`.
- `stores[]`: `logical_name`, `requested_path`, `resolved_path`, `exists`, `kind`, `is_symlink`, `is_junction`, `is_reparse_point`, `reparse_points[]`, `filesystem_identity`, `identity_known`, `writable`, `expected_path`, `expected_path_match`, `git_checkout`.
- `topology`: `code_effective_store_paths[]` (con `binds_to_declared_store` y `reparse_inside_code_root[]`), `store_env_overrides[]`, `docker_context`.
- `findings[]`: `{id, code, severity, message, subject}`.

**Contrato para el operador:**
- Proceder **solo** si `overall_status == "PASS"` **y** `mode == "OPERATIONAL_REAL_DATA"`.
- Registrar el JSON completo como evidencia de la corrida.
- Reevaluar inmediatamente antes de cada escritura protegida: el resultado vale solo en `observed_at`.
- `FAIL` o `INCOMPLETE` → detenerse. No reintentar con otro modo y no relajar `require_clean` sin una decisión humana registrada.

Exit codes de la CLI: 0 PASS · 1 FAIL · 2 uso inválido · 3 INCOMPLETE.

## Límites conocidos
- No evalúa `.dockerignore`: en DOCKER_BUILD es conservador a propósito.
- No hashea el contenido de los stores; la integridad del contenido es tarea del inventario sha256 del pre-flight.
- No detecta otras formas de redirección: unidades mapeadas, `subst` ni montajes de volumen.
- Es un chequeo puntual (TOCTOU): la topología puede cambiar después de `observed_at`.

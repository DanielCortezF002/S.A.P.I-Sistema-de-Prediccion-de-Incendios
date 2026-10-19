# F4-R2: Implementación Controlada de Excepciones Criptográficas F4

**Directiva:** OCC-003A
**Rol:** Principal Software Engineer — Configuration Governance
**Fecha:** 19 de octubre de 2026
**Rama:** `governance/f4-allowlist-r2-20261019`
**Base:** `origin/main` (`2ba8cebe895b3791241546e7303a8f771a93683b`)

---

## 1. Justificación y Decisión Arquitectónica

El control de congelamiento F4 en `scripts/freeze_check.py` fue diseñado para garantizar que los componentes críticos del sistema no sufran modificaciones accidentales ni regresiones científicas respecto al baseline de referencia `cd6b58eb9bd4b9a22b8937c4cda73be46322cddb`.

La auditoría formal F4-R1 demostró que cuatro archivos bajo rutas congeladas cambiaron legítimamente en el commit consolidado `7dcd0b666e05bb5efd64c1c98685902e8b4908bf` para implementar remediaciones de defectos transaccionales y de concurrencia requeridas para la estabilidad de la ingesta meteorológica y satelital (B1, B2, B3 y ADV-05).

Conforme a la decisión del SAPI Command Center:
- **NO se altera el baseline histórico:** `BASELINE = "cd6b58eb9bd4b9a22b8937c4cda73be46322cddb"` permanece inmutable.
- **NO se modifican los `FILE_PINS` existentes:** Las migraciones V001-V003, el manifiesto de Hito 1 y el Modelo D (`prototype_model_d.pkl`) conservan sus hashes originales intactos.
- **Se implementa una política de excepción criptográfica de doble anclaje:** Cada archivo autorizado queda fijado simultáneamente por su **Git Blob SHA** canónico y por el **SHA-256** de su contenido normalizado (LF).

---

## 2. Matriz de Autorización Criptográfica F4

| Ruta del Archivo | Git Blob SHA Canónico | Content SHA-256 (LF) | Commit Autorizado | Defecto | Autor | Resumen del Cambio y Alcance |
| :--- | :--- | :--- | :---: | :---: | :---: | :--- |
| `src/inference/scoring_inputs.py` | `2dcb470886f6d2ea1a1f300854e20d4e545cc041` | `1aa419fdda5ccdd4834970ecf0e7d613abdba9efb951b028bb2dca1596a2c221` | `7dcd0b6` | B2 | DanielCortezF002 | Manejo de excepciones en decodificación DMC (`UnicodeDecodeError`, `JSONDecodeError` $\to$ `PinnedInputError`) en `_read_versioned_months`. |
| `src/procesamiento/firms_source.py` | `211c0a8fa897d644cf8520a2789f083ba235ba62` | `90daeff030f3561107ff084fce852c5761116ed010ec279e4eeea4c8d8ebfbef` | `7dcd0b6` | B1 | DanielCortezF002 | Extracción de `validate_pointer_dict` para validación en memoria desacoplada del filesystem (prevención TOCTOU). |
| `src/refresh/dmc_refresh.py` | `3c67404247f67f13cad2533394f7e67cb1f03486` | `6b3c51a71687651ba30ab4c1949b52c5f5499227b3c2b8cd021c0e53b445c84c` | `7dcd0b6` | ADV-05 | DanielCortezF002 | Invariante Write-Ahead Logging (WAL): registrar en historial antes de actualizar puntero atómico en `_publish()`. |
| `src/refresh/firms_refresh.py` | `ebc67c74fce44801bf373795672c56ca6198628c` | `d6031497246a4461b108c521a7d9dde2da77580d06bff00da985556f7f90d654` | `7dcd0b6` | B1, B3, ADV-05 | DanielCortezF002 | Invariante WAL en `_publish()`, preservación de `FirmsRefreshError` en `refresh()`, y validación estricta de sidecar en `rollback()`. |

---

## 3. Comportamiento y Salvaguardas Implementadas en `scripts/freeze_check.py`

1. **Detección de diferencias:** `check_frozen_paths` consulta `git diff --name-only BASELINE HEAD -- *paths`.
2. **Filtrado estricto:** Cualquier archivo que no figure en `F4_AUTHORIZED_EXCEPTIONS` se clasifica como `unauthorized` y causa **FAIL** inmediato.
3. **Verificación de doble hash:** Para cada archivo presente en `F4_AUTHORIZED_EXCEPTIONS`, se extrae el Git Blob SHA en `HEAD` y se calcula el SHA-256 de los bytes de Git. Si alguno difiere por tan solo 1 bit o 1 byte respecto al valor fijado, se marca como `drift` y causa **FAIL** inmediato.
4. **Protección de Worktree y Staging:** `git diff --name-only HEAD -- *paths` y `git diff --cached --name-only -- *paths` se evalúan independientemente. Cualquier modificación local no commiteada en rutas congeladas causa **FAIL** en `F4 congelados (worktree)`.
5. **Protección contra Archivos Nuevos:** `git ls-files --others -- *paths` se evalúa de forma continua. Cualquier archivo nuevo o ignorado no autorizado bajo rutas congeladas causa **FAIL** en `F4 congelados (archivos nuevos)`.

---

## 4. Pruebas Automatizadas de la Política (`tests/test_freeze_f4_exceptions.py`)

Se implementó una suite completa de pruebas unitarias cubriendo escenarios positivos y negativos:

### Casos Positivos (PASS):
- `test_baseline_remains_immutable`: Valida que `BASELINE == "cd6b58eb9bd4b9a22b8937c4cda73be46322cddb"`.
- `test_file_pins_remain_intact`: Valida los 6 hashes de `FILE_PINS` inalterados.
- `test_allowlist_contains_exactly_four_authorized_paths`: Valida la cardinalidad y unicidad del alcance.
- `test_allowlist_metadata_fields_are_complete`: Valida todos los campos de trazabilidad.
- `test_current_repo_blobs_match_allowlist_hashes_exactly`: Valida que el repositorio actual cumple al 100 % con los hashes canónicos.

### Casos Negativos (FAIL verificado):
- `test_single_byte_drift_in_authorized_file_triggers_fail`: Simula alteración de 1 byte en archivo autorizado $\to$ produce FAIL.
- `test_modification_in_unauthorized_frozen_path_triggers_fail`: Simula alteración en otra ruta congelada (`src/geo/grid.py`) $\to$ produce FAIL.
- `test_uncommitted_local_modification_triggers_worktree_fail`: Simula modificación local no confirmada $\to$ produce FAIL en worktree.
- `test_untracked_file_under_frozen_paths_triggers_new_files_fail`: Simula archivo nuevo bajo rutas congeladas $\to$ produce FAIL en archivos nuevos.
- `test_incorrect_content_sha256_triggers_fail`: Simula discrepancia de SHA-256 con blob SHA idéntico $\to$ produce FAIL.

**Resultado de ejecución:** 10/10 pruebas en estado **PASS**.

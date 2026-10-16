# B1/B2/B3 — Corrección de estado (Directiva 34 / Prioridad 1)

**Hallazgo crítico de esta sesión: B1, B2 y B3 NO están abiertos. Fueron
remediados y verificados el 12-10-2026, tres días antes de que esta cadena de
directivas (30-34) comenzara.** Las sesiones anteriores (Directivas 30-33, y
el informe de Antigravity) afirmaron repetidamente "B1/B2/B3 siguen abiertos
y sin remediar" basándose en la lectura de `docs/evidence/sapi71-f4-prep/README.md`,
que describe el estado **ANTES** de la autorización, sin verificar si una
corrección posterior ya los había cerrado. Esta sección corrige ese error.

## Qué se verificó hoy (comandos reales, no narrativa)

1. **Commit de remediación ya existente y autorizado:**
   `4012fbfc054a1640cc02518e625cfd92a12fe5f9` — "fix(SAPI-71): implementar
   remediación autorizada Bloque A (B1, B2, B3)", 12-10-2026, ancestro directo
   del candidato actual (confirmado: `git log --oneline 4012fbf..HEAD` lista
   commits intermedios reales, ancestría confirmada).

2. **Diff real del commit** (`git show 4012fbf`):
   - **B2** (`src/inference/scoring_inputs.py::_read_versioned_months`):
     envuelve `parse_dmc_bytes` en `try/except (UnicodeDecodeError,
     json.JSONDecodeError)`, relanzando como `PinnedInputError` — exactamente
     la corrección propuesta en el prep doc.
   - **B3** (`src/refresh/firms_refresh.py::refresh`): añade
     `except FirmsRefreshError: raise` **antes** del handler genérico de
     `RuntimeError`, preservando la clasificación DATA/USAGE en vez de
     degradarla a NETWORK — exactamente la corrección propuesta.
   - **B1** (`src/refresh/firms_refresh.py::rollback`): ahora invoca
     `_resolve_pointer(sidecar, paths.versions_dir)` (función ya existente en
     `src/procesamiento/firms_source.py`, sin necesidad de modificarla) para
     validar el sidecar completo, y verifica que `relative_path` coincida con
     la versión solicitada antes de publicar — exactamente la corrección
     propuesta.

3. **Regresión ejecutada hoy, en este repositorio, contra el candidato
   `b4e5440`:**
   ```
   pytest tests/test_remediation_red_defects.py -v --no-cov
   -> 9 passed in 4.13s (0 failed)

   pytest tests/test_remediation_red_defects.py tests/test_refresh_adversarial.py
          tests/test_scoring_inputs.py tests/test_firms_refresh.py
          tests/test_dmc_refresh.py tests/test_refresh_primitives.py
          tests/test_dmc_store_contract.py --no-cov
   -> 176 passed, 2 skipped, 0 failed in 28.42s
   ```

## RED histórico (antes de 4012fbf) vs. GREEN (hoy)

| Defecto | RED (según `sapi71-f4-prep/README.md`, 12-10-2026 antes de autorización) | GREEN (verificado hoy, 15-10-2026) |
|---|---|---|
| B1 — rollback no valida sidecar completo | "missing FirmsRefreshError" | `test_b1_firms_rollback_*` (4 casos) PASSED |
| B2 — errores de decodificación escapan | "UnicodeDecodeError/JSONDecodeError escape" (pin_dmc y capture_body) | `test_b2_dmc_version_*` (4 casos) PASSED |
| B3 — `FirmsRefreshError` reclasificado como NETWORK | "NETWORK 69 instead of DATA 65" | `test_b3_firms_coverage_gap_misclassified_as_exit_network` PASSED |

## Qué sigue abierto (no confundir con B1/B2/B3)

**ADV-05** (publicación/recuperación de historial bajo fallo de IO) sigue
**explícitamente sin resolver** — es un asunto arquitectónico distinto,
"bloqueado en arquitectura/change-control" según el propio prep doc, no
cerrado por el Bloque A. Las 5 pruebas de caracterización de ADV-05
(`tests/test_adv05_characterization.py`) **pasan hoy**, pero una prueba de
caracterización que pasa confirma que el comportamiento (el defecto) sigue
presente, tal como el propio documento advierte explícitamente: "Passing
characterization cases cannot authorize release or close ADV-05." **No se
declara ADV-05 cerrado.**

## Por qué F4 sigue en FAIL (correctamente, sin cambio)

`src/inference/scoring_inputs.py`, `src/procesamiento/firms_source.py` y
`src/refresh/firms_refresh.py` siguen apareciendo como divergentes del
baseline `cd6b58e` en el check de freeze — **esto es correcto y esperado**:
el baseline es anterior a TODO el trabajo de SAPI-71 (TOCTOU, Bloque A
incluido). La cadena de autorización completa es:
`docs/evidence/sapi71-f4-prep/README.md` (preparación, sin autorizar) →
`4012fbf` (implementación autorizada de Bloque A) → verificación de hoy
(regresión real). **No se sustituye F4 FAIL por PASS**; se documenta como
divergencia autorizada y verificada, consistente con los informes previos.

## Corrección de registros anteriores

Los comentarios Jira `#10160` (SAPI-43) y los informes de las Directivas
30-33 que afirman "B1/B2/B3 siguen abiertos y sin remediar" están
**desactualizados en ese punto específico** y deben leerse con esta
corrección. No se edita el historial de Jira (los comentarios ya publicados
se mantienen como registro); se dejará una aclaración nueva en Jira SAPI-43
en el marco de esta misma sesión.

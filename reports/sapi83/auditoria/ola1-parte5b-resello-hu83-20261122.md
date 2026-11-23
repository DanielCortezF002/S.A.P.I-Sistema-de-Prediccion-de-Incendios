# SAPI-Auditor · Ola 1 · Parte 5b — Re-sello del preregistro HU-83

Fecha: 2026-11-22 · Modo: solo lectura · Objeto: `7c8498b..71722ef4b16bc6b4ae6a372d8588fe8b79c94f4d` (rama `ml/sapi-83-preregistro`), revisado en mi clon y worktree propios.
Complementa a `ola1-parte5-preregistro-hu83-20261122.md` (f865f5bc…).

## Independencia
Los commits a01a0e8, b4bab54 y 71722ef tienen autor `DanielCortezF002` y coautor `Claude Opus 5.5` (SAPI-ML). Ninguno es mío. **Independiente.**

## Verificaciones
| # | Punto | Evidencia | Dictamen |
|---|---|---|---|
| 1 | El diff solo toca la sección 10 y el test | `git diff --stat 7c8498b 71722ef`: solo `docs/preregistro_sapi83.md` (+3, 0 líneas borradas) y `tests/test_sapi83_evaluacion_modelo_d.py` (+82). Las 3 líneas nuevas son la fila D9 y el párrafo del hash del CSV, al final de la tabla de la §10. Script, CSV y pip freeze no cambian. 71722ef es un commit vacío de sello. | GO |
| 2 | Condición 1: D9 y hash del CSV | La fila D9 recoge el conteo del auditor y no cambia ni el protocolo ni `S(d)`. Hash del blob LF recalculado: `4024917c5c8872e2f138d9e4f867fb29dd5171a770d14fd3fee06182dadeae15`, coincide. El hash CRLF `80119cc7…` coincide con mi informe anterior. | GO |
| 3 | Condición 2: integración de la regla de parada | `test_main_con_ca4_no_se_detiene_antes_de_matrices_y_figuras` arma artefactos 100 % sintéticos en `tmp_path` y fuerza CA4 = NO con una PR-AUC de referencia alterada. Comprueba tres cosas: que `matriz_zona`, `matriz_dia`, `umbral_p90`, `score_por_dia`, `curva_entrenamiento` y `_figuras` no se llamen; que solo se escriba el JSON de control; y que no exista `figuras_sapi83/`. No toca datos reales ni `models/`. | GO |
| 4 | Pruebas | Las ejecuté en mi worktree en 71722ef: **37 passed**. | GO |

Hashes en 71722ef: preregistro `ac0fd0545f50a9118a66adb0fc022860d948cbfe180c143ade2a14785647a7d0`; test `5819c45333713186d7ee3ef3bde745677c202f14b29ab8d4c5e8c950b936de8a`; script sin cambios `de492b8d…0b6`.

## Observación (informativa, no bloquea)
En la prueba nueva, `entrenar_fold_d` se sustituye por un stub, así que el guard del fold 2022 no se ejercita ahí. Ese guard ya tiene su propia prueba unitaria.

## Dictamen final parte 5: **GO para autorizar R2–R6** sobre `71722ef`.
Cualquier commit posterior al re-sello invalida este GO para lo que cambie y debe revisarse antes de ejecutar. Si CA4 da NO, se aplica la regla de parada tal como está escrita.

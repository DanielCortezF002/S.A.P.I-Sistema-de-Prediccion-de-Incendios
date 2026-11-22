# SAPI-Auditor · Orden 01 · HU-83: ejecución R2–R6

Fecha: 2026-11-22 · Objeto: commits `2175742`, `fc3deab` (§12) y `475668f` (log) sobre el código `71722ef` (rama `ml/sapi-83-preregistro`). Los traje a mi clon aislado.
`git diff --stat 71722ef 475668f`: 7 archivos, +2125 líneas, solo en `reports/` y en la §12 de `docs/preregistro_sapi83.md`.

## Independencia
Autor `DanielCortezF002`, coautor `Claude Opus 5.5` (SAPI-ML). Ninguno es mío. **Independiente.**

## Resultados por criterio

| # | Criterio | Evidencia (comando, fecha) | Resultado |
|---|---|---|---|
| 1 | El código ejecutado es 71722ef sin cambios | (a) El log registra `HEAD=71722ef…`. (b) `git diff --quiet 71722ef 475668f -- scripts tests docs/dias_prueba_seleccionados.csv models` da sin cambios. (c) **Reproducción independiente:** en mi worktree, limpio en 71722ef (`git status` vacío, script `de492b8d…`), ejecuté `python -B scripts/evaluacion_modelo_d.py --dataset C:/SAPI-DATOS-VERIFICADOS/20261122/temporal_dataset_h6.parquet --salida <scratch> --confirmo-autorizacion-ejecucion` (2026-11-22T06:04:53Z→06:05:15Z, exit 0). Los dos JSON salen **idénticos** a los commiteados, excepto `sello` (hora) y `figuras` (rutas). Los PNG difieren solo porque el título incluye la hora. | PASS |
| 2 | Dataset y `models/` sin cambios | Hoy, después de la corrida: dataset `14b36ad8…530fe` y `models/prototype_model_d.pkl` `ac017bef…`. Ningún commit toca `models/`. | PASS |
| 3 | CA4 reproducido desde los JSON | Las PR-AUC 2023–2026 del control (`0.0008561319756338858`, `0.010692228032479597`, `0.0009183479102241013`, `0.0010260189942317172`) son iguales a `reports/experiment_abcd_h6_results.json` (blob `4bbe4db0…`) con diferencia 0. El fold 2022 queda sin entrenar. Lo recalculé además con mi propia corrida (fila 1). | PASS |
| 4 | **Rotura deliberada de CA4 con datos reales** | Script propio (`break_ca4.py`, en mi scratch): copia de la referencia con la PR-AUC del fold 2025 alterada en +1e-6 y el hash esperado ajustado solo para llegar al control. Resultado: `EvaluacionDetenida: Control de reproducción CA4 = NO: fold 2025 … (tol 1e-09)`. La salida contiene **solo** `evaluacion_modelo_d_control_ca4_*.json`, sin matrices ni figuras. | PASS (la regla de parada funciona con datos reales) |
| 5 | Matriz por zona (CA2) | La §12 coincide con el JSON: VP 12, FP 26 643, FN 70, VN 239 738; VP/FN por año 1/18, 5/41, 4/3, 2/8; empates en el corte 1265/1460, 1303/1464, 1075/1443, 747/964; positivos en el grupo empatado 8, 6, 1, 2. | PASS |
| 6 | Matriz por día (CA3) | Primaria: VP 6, FP 3, FN 3, VN 6. τ = 0,3906 / 0,6410 / 0,7507 / 0,7683. Ningún día NO_EVALUABLE. La secundaria también coincide con la §12. | PASS |
| 7 | Casos negativos CA5 | 37 passed en el log commiteado. Yo los ejecuté en 71722ef con el mismo resultado (parte 5b). | PASS (ya auditado) |
| 8 | Curva de entrenamiento (CA1) | **E1 confirmado.** El pkl es `{"model","metadata"}`, y en el modelo hay `n_iter_=22` y 23 valores en `train_score_` y en `validation_score_` (lectura de solo lectura). El JSON dice «curva no disponible en el artefacto», lo cual es **falso**: la curva existe y el script no desenvolvió el dict. | **FAIL** (CA1 no cumplido) |
| 9 | Registro §12 | Solo añade texto; no reescribe las secciones 1–10. Declara E1, E2 y E3 y la observación de los empates. | PASS |

## Hallazgos
- **A-1 (Alto, ya declarado como E1):** CA1 no se cumple, y el texto que quedó en `reports/evaluacion_modelo_d_20261122.json` («curva no disponible en el artefacto») es falso. La corrección debe dejar ese JSON anotado o reemplazado, no solo agregar la figura.
- **M-1 (Medio, de proceso):** el log registra `HEAD` pero no el estado del árbol ni el hash del script en el momento de correr. La §12 dice «árbol limpio», pero no queda evidencia en el log. Hoy el worktree `vaquita` tiene cambios sin commit en el script y en el test (la corrección de E1, E2 y E3, de las 06:04Z, posterior a la corrida). En este caso mi reproducción independiente lo compensa. Para la re-ejecución de la curva: añadir `git status --porcelain` y `sha256sum scripts/evaluacion_modelo_d.py` al log, y ejecutar solo con el commit de corrección ya sellado.
- **M-2 (Medio, de interpretación):** en el 77–89 % de los forecast_times hay empate en el corte Top 5, y en 2023 8 de los 19 positivos caen en el grupo empatado. Las cifras por zona deben presentarse siempre junto a ese dato (D8). Ya está observado en la §12.
- **B-1 / B-2:** E2 (contraste) y E3 (rutas absolutas) confirmados; son cosméticos.

## Dictamen
- **Ejecución R2–R6 (CA2, CA3, CA4, CA5): GO.** Reproducida de forma independiente y con la regla de parada comprobada con datos reales.
- **CA1: NO GO** hasta el commit de corrección de E1. Pido revisarlo antes de re-ejecutar solo la curva, con las condiciones de M-1.

## Anexo: SAPI-167 (D-02), caso negativo pedido por el Director
Worktree propio en `9e70867` (detached). `tests/test_risk_colors.py::test_stylesheet_sets_touch_targets_without_dataframe_checkbox_hack`: **pasa** en limpio. Tres roturas deliberadas: agregar a `build_stylesheet()` el selector `input[type="checkbox"]`, luego `[role="checkbox"]` y luego `MutationObserver`. **Las 3 fallan** («1 failed»). Al restaurar con `git checkout`, vuelve a pasar. **PASS.**
El run `41932911572` corresponde a `push` sobre `main` con `headSha 9e70867…`, 6/6 jobs en `success` (`freeze`, `python`, `backend-unit`, `sql-migration-validation`, `flyway-integration`, `container-smoke`).
Pendiente: reproducir lint v2 en local (`black` y `flake8` no están instalados en el entorno disponible: NO_EVALUADO local, solo evidencia CI), certificar SAPI-141 y revisar la equivalencia de las PR #32, #33, #34, #35 y #41.

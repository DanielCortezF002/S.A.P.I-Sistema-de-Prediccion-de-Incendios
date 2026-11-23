# SAPI-Auditor · Ola 1 · Parte 5 — Preregistro HU-83 (SAPI-83)

Fecha: 2026-11-22 · Modo: solo lectura · No se ejecutó `scripts/evaluacion_modelo_d.py` ni `experiment_abcd.py`, y no se entrenó ni puntuó ningún modelo.
Objeto: rama `ml/sapi-83-preregistro`, punta `7c8498bf46edc761e2d3a41d1b618d0a89d37e53` (worktree `vaquita` sin cambios locales). La revisé desde un clon y un worktree propios (`work/wt-sapi83`), no desde el worktree de SAPI-ML.

## Independencia
- Los 4 commits (c15993c, 9f7b023, 3a8f45c, 7c8498b) tienen autor `DanielCortezF002` y coautor `Claude Opus 5.5`, producidos por la sesión de SAPI-ML. SAPI-Auditor no es autor de ninguno. **Independiente.**
- Limitación declarada: el autor y el auditor usan el mismo modelo base. Por eso todo lo importante se recalculó de forma independiente (abajo) en lugar de leerse.

## Hashes de los archivos revisados (en 7c8498b)
| Archivo | SHA-256 |
|---|---|
| docs/preregistro_sapi83.md | dc5cea31fa735ccbacdae585421a7d06a7da17d499a04ad5d17ca2b593d7de8f |
| docs/dias_prueba_seleccionados.csv | 80119cc7f3e9e4dc17d8ab9d06cb6349955d817fe0edf5dbc2787e638b9a59b6 |
| scripts/evaluacion_modelo_d.py | de492b8d52b86369a35992bfa2444bdfa105292396063aa0aa56c873b4c70558 |
| tests/test_sapi83_evaluacion_modelo_d.py | 3339abfb8dbc675fa797e98fa86860b81fa75400a2f0e130a3b5555b6ea6b843 |

## Verificaciones

| # | Punto | Evidencia | Dictamen |
|---|---|---|---|
| 1 | El criterio se commiteó antes que el CSV | Orden de commits: c15993c (01:16:29) → 9f7b023 (01:21:09) → 3a8f45c CSV (01:21:19) → 7c8498b sello (01:21:51, = 04:21:50Z). Entre c15993c y 7c8498b solo se **añadieron** líneas al preregistro (secciones 10–11); las secciones 1–9 no cambian. c15993c no contiene ninguna de las fechas elegidas. | GO |
| 2 | El criterio usa solo FIRMS y fechas, sin salidas del modelo | `seleccionar_dias()` y `estadisticas_diarias_firms()` leen solo `latitude`, `longitude` y `acq_date`, más `assign_cell`. **Recálculo independiente:** escribí mi propia implementación (con `csv` de la biblioteca estándar, sin importar el script de SAPI-ML) sobre el FIRMS congelado y obtuve el CSV **idéntico, fila por fila (18/18)**. El CSV es función determinista de FIRMS, así que ninguna salida del modelo pudo influir en él, sea cual sea el orden en que se generó. | GO |
| 3 | El umbral p90 usa solo años de entrenamiento | `main()`: `train = df[bloque < anio]`, scores del D del fold sobre `train`, y luego `umbral_p90(..., anio)`, que lanza `FugaDeUmbral` si entra un año ≥ al de prueba. Hay pruebas CA5-a para el mismo año y para un año posterior. | GO |
| 4 | El pkl desplegado no se usa para las matrices | En `main()` solo se verifica su hash y se hace `joblib.load` para `curva_entrenamiento`. Las matrices usan `modelos[b]`, re-entrenados por fold. | GO |
| 5 | Desviaciones D1–D8 | D1: Python 3.14.10 frente a 3.14.6, con numpy, scipy, sklearn y joblib idénticos a los pines. D2/D6: los paquetes nuevos coinciden con `requirements*.txt` (pandas 3.0.5, pyarrow 25.0.1); matplotlib 3.11.2 no está fijado pero solo afecta a las figuras. D3: comprobado, el blob LF de `reports/experiment_abcd_h6_results.json` en 9e70867 da `4bbe4db0…`. D8: el desempate no estable queda mitigado porque se reportan los empates en el corte. Todas están declaradas y la regla de parada CA4 cubre su riesgo. | GO |
| 6 | 36 pruebas sintéticas con negativos CA5 | Las ejecuté en mi worktree (`python -B -m pytest -p no:cacheprovider -o addopts=""`): **36 passed**. Las pruebas no leen el parquet ni el pkl (no hay rutas reales). Negativos presentes: CA5-a (umbral, 2 casos) y CA5-b (PR-AUC alterada, referencia alterada, mutaciones paramétricas, sin folds), además de hash distinto o faltante, ejecución sin autorización, hashes antes de leer, CSV alterado y fold con un solo positivo. | GO |
| 7 | Hashes de dataset, FIRMS, pkl y resultados | Los recalculé hoy: dataset `14b36ad8…` (parte 1), FIRMS `a9a85db4…`, pkl `ac017bef…` y blob de resultados `4bbe4db0…`. Coinciden con las constantes del script y con el preregistro. | GO |
| 8 | Regla de parada si CA4 no da SÍ | `control_reproduccion` exige los 4 folds con PR-AUC dentro de 1e-9, `n_test` y positivos iguales, y el fold 2022 sin entrenar. `exigir_reproduccion` lanza error **después** de escribir solo el JSON de control y **antes** de umbrales, matrices y figuras. | GO |

## Hallazgos
- **Medio — falta prueba de integración de la regla de parada.** `exigir_reproduccion` y `control_reproduccion` están probados por separado, pero ninguna prueba ejecuta `main()` con un dataset sintético cuyo CA4 dé NO para comprobar que no se escriben matrices ni figuras. Hoy se sostiene solo por lectura de código (líneas de `main()`). Recomendación: añadir esa prueba antes de R2, o aceptar el riesgo de forma explícita.
- **Bajo — el cooldown también afecta a la matriz por día (CA3) y no está declarado allí.** La sección 5 declara el cooldown solo para la matriz por zona. Conté filas elegibles (solo `forecast_time`, `eligible_for_training` y `target`, sin el modelo): 2024-02-03 tiene 185/200 filas elegibles, 2024-02-04 tiene 183/200 y 2023-12-09/10 tienen 196/200. `S(d)` se calcula sin las celdas que ya están ardiendo. El efecto es pequeño, pero hay que registrarlo como desviación D9 antes de ejecutar.
- **Bajo — el sello no registra el hash del CSV**, aunque la sección 2 dice «se registra en el commit de sello». Queda mitigado porque el commit 3a8f45c fija el contenido y `main()` recalcula y compara. Hash del auditor: `80119cc7…a9b6`.
- **Bajo — independencia de los días con incendio.** 2024-02-02, 02-03 y 02-04 son el mismo evento (el 02-04 entra por el cupo global) y 2023-12-09/10 son consecutivos, así que hay unos 5 eventos distintos en 9 días. El preregistro solo declara el par 02/03. Corresponde precisarlo en la redacción de resultados; no cambia el protocolo.
- **Informativo:** la referencia tiene pocos positivos por fold (19, 46, 7 y 10 filas). Las matrices por zona serán muy ralas, sobre todo en 2025. Ya está declarado que no habrá inferencia.

## Dictamen parte 5: **GO para autorizar R2–R6**, con dos condiciones previas a la ejecución, ninguna de las cuales cambia el protocolo:
1. Registrar D9 (cooldown en CA3) y el hash del CSV en la sección 10 del preregistro, como texto añadido sin reescribir lo anterior.
2. Añadir la prueba de integración de la regla de parada, o que el Director acepte por escrito el riesgo.

Si CA4 da NO al ejecutar, la regla de parada se aplica tal como está escrita y el dictamen de las fases posteriores queda NO EVALUADO.

# Preregistro SAPI-83 (HU-83): evaluación del Modelo D con datos reales

| Campo | Valor |
|---|---|
| Issue | SAPI-83 «HU-83 (S3-10) — Evaluación del Modelo D con datos reales» (Jira, leído en solo lectura el 22-11-2026) |
| Autorización | Preparación y preregistro autorizados por el dueño el 22-11-2026. **No autoriza ejecutar la evaluación.** |
| Rama | `ml/sapi-83-preregistro` (desde `main` @ `9e70867`) |
| Estado | PREREGISTRO. Nada de este documento es un resultado. No se ha ejecutado `scripts/experiment_abcd.py` ni `scripts/evaluacion_modelo_d.py` con datos reales. |

Este documento fija, **antes de ver cualquier salida del modelo sobre 2023–2026**, qué se evaluará, con qué datos, con qué reglas y qué cuenta como éxito o como parada. Cualquier cambio posterior se registra en la sección 10 («Desviaciones») con fecha y motivo; no se reescribe el texto original.

## 1. Pregunta

¿Cuántas veces el Modelo D, evaluado con el protocolo walk-forward del proyecto, puso en su Top 5 las zonas que de verdad recibieron una nueva detección FIRMS, y cuántas veces marcó como «de alerta» los días en que de verdad hubo detecciones FIRMS en la grilla, para los años 2023 a 2026?

El score del Modelo D es un **ranking relativo**, no una probabilidad calibrada de incendio. Ninguna métrica de este preregistro se presentará como probabilidad de incendio.

## 2. Artefactos y hashes esperados (SHA-256)

El script verifica estos hashes **antes de leer cualquier contenido**. Si uno no coincide, se detiene con error y no evalúa nada.

| Artefacto | Ruta | SHA-256 esperado | Nota |
|---|---|---|---|
| Dataset temporal h6 | `C:/SAPI-DATOS-VERIFICADOS/20261122/temporal_dataset_h6.parquet` (se pasa por argumento; no se copia al repo) | `14b36ad8db680cf57f6e0c655cb0a1940ed4b4c63e810d59e470055babc530fe` | Verificado por SAPI-ML el 22-11-2026. Este preregistro no abrió, copió ni movió el archivo. Coincide con `dataset_hash` de `models/prototype_model_d_metadata.json`. |
| FIRMS línea base | `artifacts/hito1/reproducibility/firms/nasa_firms_2021-08-30_2026-08-30.csv` | `a9a85db4431b3e54f936b724e4de5a7fbb0cc19f5721f5e1a344a192bf9bb271` | Versionado con `-text` (bytes exactos). Recalculado el 22-11-2026 en este worktree: coincide. |
| Modelo D desplegado | `models/prototype_model_d.pkl` | `ac017bef1f42a30ac74ba3e3787368c4418798b2d562adcfba01c923cff2173f` | Recalculado el 22-11-2026: coincide. Solo se lee; nunca se reescribe. |
| Resultados walk-forward de referencia | `reports/experiment_abcd_h6_results.json` | `4bbe4db0054c4c08c08c93cfc0253201475b2fab9562ec61ccd0acc8ae04f8cd` | Hash del **blob en git** (`git show 9e70867:reports/experiment_abcd_h6_results.json`, fin de línea LF). En un checkout Windows con `core.autocrlf=true` el archivo en disco tiene CRLF y su hash crudo es `20da64d2dda535610571d4359c3884acafb4bebe116c4685c2a71c7347f406e4`. El script normaliza `\r\n`→`\n` antes de hashear y compara contra el hash del blob. |
| Días de prueba | `docs/dias_prueba_seleccionados.csv` | se registra en el commit de sello | Generado después del commit que fija el criterio (sección 6). |

El script de evaluación usa como FIRMS la ruta congelada de reproducibilidad (mismo hash que `FIRMS_BASELINE_CSV` de `src/procesamiento/firms_source.py`); si se le pasa otra ruta, igual exige el hash `a9a85db4…`.

## 3. Protocolo walk-forward (de `scripts/experiment_abcd.py`, sin modificar)

Leído, no ejecutado. El script de HU-83 **importa** sus constantes y funciones (`MODELOS`, `RANDOM_STATE`, `_prep_xy`) en lugar de copiarlas, para que cualquier diferencia de protocolo sea imposible sin tocar ese archivo.

1. Se cargan solo las filas `eligible_for_training == True` del dataset (las filas en cooldown, `excluded=True`, nunca entran).
2. Bloque temporal = año calendario UTC de `forecast_time`. Bloques presentes en la referencia: 2021–2026.
3. Fold *i*: entrena con todos los años anteriores al año de prueba y prueba con ese año. La referencia tiene 5 folds (prueba 2022…2026); el fold 2022 quedó sin entrenar (1 positivo en 2021).
4. Modelo D = features `FEATURES_D` (historial FIRMS, meteo actual, lags 6/12/24/48 h, topografía). Sin `cell_id`. Sin imputación (`_prep_xy`).
5. Clasificador: `HistGradientBoostingClassifier(random_state=42, max_depth=4, class_weight="balanced")`, demás hiperparámetros por defecto. Guard: si la clase minoritaria del train tiene < 2 ejemplos, el fold no se entrena.
6. Score = `predict_proba(x_test)[:, 1]`, usado solo como ranking.

**Alcance de HU-83:** se evalúan los folds con año de prueba **2023, 2024, 2025 y 2026** (2026 cubre hasta el último `forecast_time` del dataset, 2026-08-29 18:00 UTC según la metadata del modelo).

**Qué modelo se evalúa:** el D **re-entrenado por fold** con este protocolo (modelo entrenado solo con años anteriores). El artefacto desplegado `models/prototype_model_d.pkl` fue entrenado con 2021-08-30 → 2026-08-29, es decir, **incluye los años de prueba**; usarlo para puntuar 2023–2026 sería evaluación dentro de la muestra. Por eso el desplegado se usa solo para (a) verificar su hash y (b) leer su curva de entrenamiento (sección 8). No se entrena ni se guarda ningún modelo nuevo en `models/`.

## 4. Control de reproducción (CA4) y regla de parada

Antes de cualquier matriz, para cada fold de la referencia en que `modelo_D` tiene PR-AUC (prueba 2023, 2024, 2025, 2026):

- se re-entrena el D del fold con el protocolo de la sección 3;
- se recalcula la PR-AUC por fila (`average_precision_score`) sobre el test del fold;
- se compara con `folds[k].resultados.fila.modelo_D.pr_auc` de la referencia.

**Criterio SÍ:** para los 4 folds, `|PR-AUC recalculada − PR-AUC referencia| ≤ 1e-9`, y además `n_test` y `n_positivos_test_filas` coinciden exactamente. El fold 2022 debe volver a quedar sin entrenar (mismo guard); si en la reproducción sí entrena, es NO.

**Regla de parada:** si el control no da SÍ (cualquier fold fuera de tolerancia, conteos distintos, fold faltante o hash de referencia distinto), la ejecución **se detiene con error, no calcula umbrales ni matrices y no escribe figuras**. Solo se escribe el informe del control con el motivo. No se ajusta la tolerancia ni se re-intenta con otras versiones para «hacerlo pasar» sin registrarlo como desviación.

Tolerancia 1e-9: el proceso es determinista (`random_state=42`) y las versiones de librerías son las del manifiesto; una diferencia mayor indica que algo del protocolo, de los datos o del entorno cambió.

## 5. Matriz por zona (regla Top 5 de la pantalla, CA2)

Regla tomada de `app/utils/score_contract.py` (y de `src/inference/prototype_service.py`, que produce el ranking que ese contrato valida):

- `TOP_N = 5`; el Top 5 de la pantalla son las celdas con `rank` 1..5 (`DashboardView.top = cells[:TOP_N]`, ordenadas por `rank`).
- `rank` es la posición 1..N **siempre única**; se obtiene como en `prototype_service.score_current_grid`: `pd.Series(scores, index=cell_id).sort_values(ascending=False)` y se numera en ese orden. La serie de entrada se ordena por `cell_id` ascendente (orden de la grilla, VP-001…VP-050, el mismo orden en que la inferencia construye las filas).
- **Empates:** `display_rank = 1 + nº de celdas con score estrictamente mayor` (método «min») y `tie_group_size = nº de celdas con exactamente el mismo score`, idéntico a la validación `tie_metadata_inconsistent` de `score_contract.validate`. El corte Top 5 **no** reparte los empates: entra quien tenga `rank ≤ 5`, aunque comparta score con celdas de `rank > 5`.

Construcción, por fold (año de prueba) y para cada `forecast_time` *T* del año de prueba:

1. Se rankean las filas elegibles de *T* con el score del D del fold.
2. Predicho positivo = `rank ≤ 5`. Real positivo = `target == 1` (nueva detección FIRMS en la celda en (T, T+6h], definición del dataset).
3. Se acumulan VP, FP, FN, VN por fold, por celda (zona) y agregados 2023–2026.

Se informa además, por fold:
- `n_T_empate_en_corte`: nº de *T* en que la celda de `rank 5` comparte score con alguna celda de `rank > 5`;
- `n_positivos_en_grupo_empatado_del_corte`: positivos reales dentro de esos grupos empatados (para dimensionar cuánto depende la matriz del orden de desempate);
- `n_T_con_menos_de_50_celdas`: *T* en que algunas celdas no son elegibles (cooldown). En esos *T* se rankean solo las celdas elegibles (igual que `_rank_metrics` de `experiment_abcd.py`); la pantalla rankea siempre las 50. Esta diferencia es una limitación declarada, no se corrige.

## 6. Criterio de selección de días (fijado antes de generar el CSV)

Base: **solo** el registro FIRMS congelado (`a9a85db4…`). Se usan únicamente las columnas `latitude`, `longitude` y `acq_date`. No se usa ninguna salida de ningún modelo, ni el dataset, ni la meteorología. Sin filtro de `confidence` (el pipeline del dataset tampoco filtra: `assign_episodes` usa todas las detecciones).

Definiciones:
- Día = `acq_date` de FIRMS (fecha UTC).
- Detección en la grilla = `src.geo.grid.assign_cell(lat, lon)` no nulo (contención estricta en las 50 celdas).
- `n_celdas(d)` = nº de celdas distintas con ≥ 1 detección en la grilla el día *d*; `n_det(d)` = nº de detecciones en la grilla el día *d*.
- **Día con incendio** = `n_celdas(d) ≥ 1`.
- Período elegible: 2023-01-01 a 2026-08-29 (último día con `forecast_time` en el dataset). Años de prueba: 2023, 2024, 2025, 2026.
- Orden de candidatos: `n_celdas` descendente, luego `n_det` descendente, luego fecha ascendente.

**9 días con incendio:**
1. Inclusión forzada de **2024-02-02 y 2024-02-03** (megaincendio de febrero de 2024; pedido explícito en el comentario de SAPI-83 del 20-11-2026). Si alguno no es día con incendio según la definición, se detiene y se reporta; no se sustituye.
2. Cuota de 2 días por año de prueba. La cuota de 2024 la llenan los dos días forzados. Para 2023, 2025 y 2026 se toman los 2 primeros candidatos del año según el orden.
3. El 9.º día es el mejor candidato restante de los cuatro años según el mismo orden.
4. Si un año tiene menos de 2 candidatos, se toman los que haya y el faltante pasa al cupo global (paso 3), registrándolo.

**9 días sin incendio (uno emparejado con cada día con incendio):** procesando los días con incendio en orden cronológico, para cada día *d* se elige el día *c* que cumpla:
- mismo año calendario que *d* y dentro del período elegible;
- **ninguna detección en la grilla en todo el intervalo [c−3, c+3]** (los 7 días dentro de la cobertura FIRMS 2021-08-30…2026-08-30);
- no elegido antes;
- `|c − d|` mínimo (misma época); empate → el más temprano; búsqueda limitada a `|c − d| ≤ 60` días.

Si para algún *d* no existe *c*, se detiene y se reporta; no se inventa ni se relaja el criterio sin registrar una desviación.

Salida: `docs/dias_prueba_seleccionados.csv` con columnas `fecha, clase (con_incendio|sin_incendio), anio, n_celdas, n_det, motivo, dia_emparejado`. El script de evaluación recalcula la selección desde FIRMS y **se detiene si no coincide con el CSV commiteado**.

Limitaciones conocidas del criterio: los días con incendio no son independientes (02 y 03-02-2024 son el mismo evento); 9 + 9 días no permiten inferencia estadística, solo descripción; «día con incendio» es detección satelital en la grilla, no un incendio confirmado en terreno.

## 7. Matriz por día con/sin incendio (CA3)

Para cada fold (año de prueba *Y*, modelo D del fold *M_Y*):

1. **Score del día** `S(d)` = máximo del score de *M_Y* sobre todas las filas elegibles (todas las celdas y los 4 `forecast_time`) cuya fecha UTC de `forecast_time` es *d*.
2. **Umbral** `τ_Y` = percentil 90 (`numpy.percentile`, `method="linear"`) de `S(d)` sobre **todos los días de los años de entrenamiento** (años < *Y*), puntuados con el mismo *M_Y*. **Ningún día del año de prueba ni posterior entra al umbral**; la función que lo calcula recibe el año de prueba y levanta error si algún día de entrada es de un año ≥ *Y* (caso negativo CA5-a).
3. Predicho «día de alerta» si `S(d) ≥ τ_Y`. Real = clase del CSV (con/sin incendio).
4. Matriz 2×2 (VP, FP, FN, VN) **primaria** sobre los 18 días del CSV, por fold y agregada.
5. Matriz **secundaria** (descriptiva) sobre todos los días de 2023–2026 con al menos una fila elegible, con la misma definición de día con incendio de la sección 6.

Limitación declarada: `τ_Y` se calcula con scores de *M_Y* sobre sus propios datos de entrenamiento (dentro de la muestra), por lo que tiende a ser más alto que un umbral fuera de la muestra. Se acepta porque CA3 exige usar solo años de entrenamiento; no se cambia después de ver resultados.

Un día del CSV sin filas elegibles en el dataset se reporta como `NO_EVALUABLE` y no se reemplaza.

## 8. Curva de entrenamiento del D desplegado (CA1)

Se lee `models/prototype_model_d.pkl` (tras verificar su hash) con `joblib` y se grafican, si existen, `train_score_` y `validation_score_` por iteración (`n_iter_`), que el propio `HistGradientBoostingClassifier` guardó durante su entrenamiento original. No se re-entrena. Si el artefacto no tiene esos atributos (sin early stopping), se reporta «curva no disponible en el artefacto» y no se reconstruye ni se inventa.

## 9. Métricas preespecificadas

| Bloque | Métrica | Unidad |
|---|---|---|
| CA4 | PR-AUC por fila del D re-entrenado vs referencia; `n_test`, `n_positivos_test_filas` | por fold 2023–2026 |
| Zona | VP, FP, FN, VN; precisión = VP/(VP+FP); sensibilidad = VP/(VP+FN); `n_T`, `n_T_empate_en_corte`, `n_positivos_en_grupo_empatado_del_corte`, `n_T_con_menos_de_50_celdas` | por fold, por celda y agregado |
| Día | `τ_Y`; VP, FP, FN, VN; sensibilidad; especificidad = VN/(VN+FP); precisión | 18 días del CSV (primaria) y todos los días 2023–2026 (secundaria) |
| Curva | `train_score_`, `validation_score_`, `n_iter_` del desplegado | iteración |

Cocientes con denominador 0 se informan como `null` («no evaluable»), nunca como 0 o 1. No se reportan intervalos de confianza ni pruebas de hipótesis: con 9 + 9 días no hay potencia y no se hará afirmación inferencial. No se agregan métricas después de ver resultados sin registrarlas como desviación.

Salidas previstas (al ejecutar, no ahora): `reports/evaluacion_modelo_d_<fecha>.json`, `reports/evaluacion_modelo_d_control_ca4_<fecha>.json`, figuras en `reports/figuras_sapi83/`, cada una con fecha y SHA del commit.

## 10. Desviaciones registradas

| # | Fecha | Desviación | Impacto esperado |
|---|---|---|---|
| D1 | 22-11-2026 | Python **3.14.10** en `.venv` del worktree; el manifiesto y la metadata del modelo declaran **3.14.6** (3.14.6 no instalado en el equipo). numpy 2.5.2, scipy 1.18.1, scikit-learn 1.9.0, joblib 1.5.3 sí coinciden. | Bajo (misma versión menor). Si CA4 no da SÍ, esta es la primera causa a revisar y el resultado no se fuerza. |
| D2 | 22-11-2026 | Paquetes adicionales instalados (pines de `requirements*.txt`): pandas 3.0.5, pyarrow 25.0.1, python-dotenv 1.2.3, geopandas 1.1.4, shapely 2.1.2, pyproj 3.7.2 (los exige la cadena de imports de `experiment_abcd.py`: `episodes` → `meteo_fire_joiner` → `config`/`raw_parser`), pytest 9.1.1. Lista completa en `docs/pip_freeze_sapi83.txt`. | Ninguno sobre el protocolo. |
| D3 | 22-11-2026 | El hash de `reports/experiment_abcd_h6_results.json` se fija sobre el blob de git (LF), no sobre el archivo en disco (CRLF por `core.autocrlf`). | Ninguno: el script normaliza fin de línea antes de comparar. |
| D4 | 22-11-2026 | El fold 2022 queda fuera del alcance de las matrices (no tiene D entrenado en la referencia). | Ninguno; ya era así en la referencia. |
| D5 | 22-11-2026 | Las pruebas de HU-83 se corren con `-o addopts=""` (sin el umbral global de cobertura 80 % de `pytest.ini`, que aplica a la suite completa). | Ninguno sobre la evaluación. |

# SAPI-63 — Reproducción independiente de las métricas de viabilidad LSTM

Verdict: **VERIFIED_INDEPENDENTLY**. Las cifras citadas como evidencia científica
de SAPI-63 (107 positivos, ratio 1:3390, 26/49 folds de prueba con cero
positivos, shape 3D `(360695, 4, 31)`) fueron regeneradas desde cero en esta
sesión, no solo leídas del informe previo.

## Por qué este directorio no contiene el dataset

El parquet real (`data/processed/temporal_dataset_h6.parquet`, ~10.3 MB) vive
en un checkout externo, **no versionado** en ningún repositorio (`git ls-files`
no lo lista), consistente con la política de no incorporar datasets grandes o
de procedencia incierta al repositorio del candidato de cierre. Este directorio
documenta su identidad (hash) y el procedimiento de reproducción en vez de
copiar el archivo.

## Identidad del dataset fuente

- Ruta de origen: `C:\SAPI-63-TEMPORAL-SEQUENCES\data\processed\temporal_dataset_h6.parquet`
- Tamaño: 10 838 028 bytes
- SHA-256: `14b36ad8db680cf57f6e0c655cb0a1940ed4b4c63e810d59e470055babc530fe`
- Repositorio origen: `C:\SAPI-63-TEMPORAL-SEQUENCES`, rama `feat/SAPI-63-temporal-sequences`,
  HEAD `583fe99d9dde59dd9af0e82ba3c0ebfc28d68050`, worktree limpio
  (`git status --short` sin salida) en el momento de esta verificación.
- El propio `reports/sapi63_lstm_viability_report.json` de ese repositorio está
  **trackeado por git** (`git ls-files` lo lista) y, tras la regeneración
  descrita abajo, `git status --short` sobre ese archivo no reportó cambios:
  el reporte existente es exactamente lo que el script determinístico produce
  hoy, byte a byte.
- SHA-256 de `reports/sapi63_lstm_viability_report.json` (post-regeneración):
  `4cfa0f414fc3edbc5f661b75722e55a60985c658d11d89758705b791964e9789`

## Procedimiento ejecutado (comandos reales, sesión 2026-10-15)

```text
cd C:\SAPI-63-TEMPORAL-SEQUENCES
C:\SAPI\.venv\Scripts\python.exe notebooks\sapi63_lstm_viability.py
```

El script es exploratorio y determinístico: carga el parquet, calcula
estadísticas y folds walk-forward, verifica causalidad, y escribe
`reports/sapi63_lstm_viability_report.json`. No entrena ningún modelo, no
genera números aleatorios.

## Resultado de la reproducción (salida real, no reescrita)

```
107 positivos en 362883 filas elegibles (0.0295%)
ratio_desbalance: 1:3390
shape_3d_secuencias: [360695, 4, 31]
n_folds_walk_forward: 49
folds_con_cero_positivos_test: 26
megaevento 2024-02-03: 21.5% de los positivos (23 de 107) en un solo día
Fold 0 -- PASS: Causalidad walk-forward verificada
```

Cada una de estas cifras coincide exactamente con las citadas en el informe de
cierre de Antigravity y en `reports/sapi63_lstm_viability_report.json`.

## Qué queda fuera de esta verificación

- No se auditó el script `scripts/build_temporal_dataset.py` que generó el
  parquet original a partir de los datos crudos DMC/FIRMS (fuera del alcance
  de esta tarea: verificar reproducción del *análisis*, no reconstruir el
  *dataset* desde cero).
- No se recalculó el fingerprint/hash contra una versión anterior del parquet
  para descartar que el archivo haya sido regenerado entre la fecha del
  informe de Antigravity y esta verificación; solo se confirma que, **con el
  archivo tal como existe hoy**, el análisis es reproducible y consistente
  consigo mismo (reporte trackeado sin diff).

## Conclusión

La conclusión científica "LSTM inviable con los datos actuales" (ADR-006,
SAPI-63) está sustentada por un experimento ejecutable, determinístico y
reproducido de forma independiente en esta sesión — no es una afirmación sin
evidencia. Se mantiene la recomendación original: Modelo D (XGBoost) como
baseline, LSTM como infraestructura disponible para cuando crezca el volumen
de datos.

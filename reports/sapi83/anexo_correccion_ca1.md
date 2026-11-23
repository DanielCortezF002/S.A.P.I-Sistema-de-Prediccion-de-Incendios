# Anexo — corrección de CA1 en la ejecución R2–R6 de HU-83 (SAPI-83)

Fecha: 2026-11-22 · Rama `ml/sapi-83-preregistro` · Origen: hallazgo A-1 del Auditor (`orden01-hu83-ejecucion-r2r6-20261122.md`, SHA-256 `c722649ff6537d0f9ed83dbabb979248b234c33ff9e0e61116f5fb382c86a884`).

## Qué se corrige

El archivo `reports/evaluacion_modelo_d_20261122.json` (commit `2175742`, código ejecutado `71722ef`) dice en `curva_entrenamiento_desplegado`:

> `{"disponible": false, "nota": "curva no disponible en el artefacto"}`

**Esa frase es errónea.** La curva sí existe en el artefacto. Por el defecto de implementación E1, el script pasó a `curva_entrenamiento()` el dict completo `{"model", "metadata"}` de `models/prototype_model_d.pkl`, en lugar del estimador `payload["model"]`.

Hechos verificados con lecturas de solo lectura del artefacto (SHA-256 `ac017bef1f42a30ac74ba3e3787368c4418798b2d562adcfba01c923cff2173f`), sin re-entrenar, por SAPI-ML y por el Auditor:
- el estimador es `HistGradientBoostingClassifier` con `early_stopping="auto"` activo;
- `n_iter_ = 22`;
- `train_score_` y `validation_score_` tienen 23 valores cada uno.

## Qué no se hace

- No se reescriben ni el commit `2175742` ni el JSON. Este anexo lo reemplaza **solo en lo que toca a la curva**. El resto del JSON (CA2, CA3 y la referencia de CA4) sigue vigente y quedó auditado (GO CA2–CA5).
- No se toca `models/`.

## Cómo se reemplaza el dato

Tras el GO del Auditor sobre el commit de corrección, el modo `--solo-curva-ca1` de `scripts/evaluacion_modelo_d.py` generará en un directorio **nuevo** `curva_ca1.json` y `curva_entrenamiento_modelo_d.png`, con rutas relativas, el hash del pkl verificado antes de cargarlo, el `git status --porcelain` y el SHA-256 del script (M-1). Ese `curva_ca1.json` es el dato de CA1 que vale; el campo `curva_entrenamiento_desplegado` del JSON de `2175742` queda **superado**.

Hasta entonces, CA1 (curva de entrenamiento) sigue **NO cumplido**.

## Dato que acompaña a la matriz por zona (M-2)

Las cifras de la matriz por zona (VP 12, FP 26 643, FN 70, VN 239 738) se presentan siempre junto a esto, calculado desde el mismo JSON:

> Empate en el corte Top 5 en 4390/5331 (82.3 %) forecast_times: 2023 1265/1460 (86.6 %); 2024 1303/1464 (89.0 %); 2025 1075/1443 (74.5 %); 2026 747/964 (77.5 %). Positivos dentro del grupo empatado del corte: 17. El orden entre celdas empatadas es arbitrario (D8).

Corrección: el rango «77–89 %» de la sección 12 del preregistro, que el informe del Auditor también repite, es inexacto. El rango real es **74.5–89.0 %**, porque 2025 da 74.5 %.

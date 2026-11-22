# El Modelo D en una página

*HU-88 · 22-11-2026 · Fuente de las cifras: `reports/hu88_explicacion_modelo_d/` (generado con `python scripts/explicar_modelo_d.py`).*

## Qué es

El Modelo D es el programa que S.A.P.I. usa para **ordenar las 50 celdas de la zona de Valparaíso de más a menos preocupante** para las próximas 6 horas. No dice "va a haber un incendio aquí". Dice "si hubiera que mirar primero algunas celdas, estas parecen más parecidas a las situaciones donde antes aparecieron focos de calor".

Por dentro es un conjunto de **22 árboles de decisión** pequeños (técnicamente, un `HistGradientBoostingClassifier`). Cada árbol hace hasta 4 preguntas seguidas del tipo "¿la temperatura supera tal valor?" y termina en una de sus 16 respuestas posibles. El puntaje final suma lo que aportan los 22 árboles.

**¿Por qué 22 árboles y no 100?** Por la **parada temprana**. Al entrenar se permitían hasta 100 árboles (`max_iter=100`), pero el modelo tenía activada la parada temprana (`early_stopping='auto'`, que se activó: `do_early_stopping_=True`). Con esa opción, scikit-learn aparta una parte de los datos para comprobar el aprendizaje (`validation_fraction=0.1`) y se detiene cuando pasan 10 árboles seguidos sin mejorar (`n_iter_no_change=10`). El mejor resultado se alcanzó con 12 árboles. Los 10 siguientes no lo mejoraron, así que el entrenamiento se detuvo en 22 (`n_iter_=22`). El modelo guarda los 22, no solo los 12 primeros. Todos estos valores se leyeron del propio archivo del modelo, después de comprobar su huella digital (sección "Por que hay este numero de arboles" de `reports/hu88_explicacion_modelo_d/modelo_d_explicacion.md`).

El archivo desplegado es `models/prototype_model_d.pkl`. Su huella digital (SHA-256) es `ac017bef…2173f`. El script de HU-88 la comprueba antes de abrir el archivo y no lo modifica.

## Qué información usa (25 variables)

| Grupo | Variables | En palabras simples |
|---|---|---|
| Historial de focos | `historial_firms_count`, `dias_desde_ultimo_evento` | Cuántos focos detectó antes el satélite (NASA FIRMS) en la celda y cuántos días pasaron desde el último. |
| Clima ahora | `meteo_actual_temp`, `_hr`, `_viento`, `_regla_30_30_30` | Temperatura, humedad relativa y viento de la estación Rodelillo (DMC), y si se cumple la "regla 30-30-30" (más de 30 °C, menos de 30 % de humedad y viento sobre 30 km/h). |
| Clima de antes | las mismas 4, con 6, 12, 24 y 48 horas de retraso | El tiempo que hizo en las horas y días previos. |
| Terreno | `elevacion`, `pendiente`, `orientacion` | Altura, inclinación y hacia dónde mira la ladera (modelo digital de elevación Copernicus). |

## Cómo leer sus importancias

La "importancia" mide **cuánto se apoyó el modelo en cada variable cuando aprendió**. Se calcula sumando cuánto mejoró el ajuste cada vez que un árbol usó esa variable para separar casos. Los porcentajes suman 100 %.

| # | Variable | Importancia | Lectura |
|---|---|---:|---|
| 1 | Temperatura actual | 42,1 % | Es la primera pregunta en 19 de los 22 árboles. |
| 2 | Días desde el último foco | 11,4 % | La usan los 22 árboles. |
| 3 | Temperatura hace 6 h | 11,0 % | La usan los 22 árboles. |
| 4 | Humedad hace 24 h | 5,5 % | |
| 5 | Humedad hace 6 h | 4,5 % | |

Las 15 variables restantes suman 25,5 %. Las cinco variables de la **regla 30-30-30 no se usaron en ningún árbol (0 %)**. El reporte no explica la causa: averiguarla requeriría revisar los datos, y este análisis no los usa.

Al leer estas cifras:

- **Importancia no es causa.** Que la temperatura pese 42 % no prueba que el calor provoque los focos. Solo indica que el modelo la encontró útil para separar casos.
- **No dice en qué dirección.** No indica si más temperatura sube o baja el puntaje en cada celda.
- **Viene del entrenamiento.** No mide si el modelo acierta con datos nuevos.
- **Favorece variables con muchos valores distintos.** Las mediciones continuas, como la temperatura, ofrecen más cortes posibles que una variable de sí o no.
- **No es una cifra oficial de la librería.** El modelo no trae una "importancia" incorporada (`HistGradientBoostingClassifier` no tiene `feature_importances_`). El script de HU-88 la calcula recorriendo partes internas y privadas de scikit-learn 1.9.0 (`_predictors`). Con otra versión de scikit-learn, el cálculo puede dejar de funcionar o cambiar.

## Limitaciones

- **El puntaje es un orden relativo, no una probabilidad.** Un 0,13 no significa "13 % de probabilidad de incendio" (`score_semantics = relative_rank`).
- **No está validado científicamente.** El sistema declara `scientific_model_validation = false`, y este documento no cambia esa condición.
- **El modelo desplegado se entrenó con todo el periodo 2021–2026** (30-08-2021 a 29-08-2026). No se reservó un periodo de prueba. Las métricas publicadas vienen de reentrenamientos por año (`docs/model_card_baseline.md`), no de este archivo.
- **Aprendió de muy pocos casos:** 107 situaciones positivas entre 362.883 filas.
- **Usa una sola estación meteorológica** (Rodelillo, 330007) para toda la zona, así que todas las celdas comparten el mismo clima en un mismo momento. Las diferencias entre celdas vienen del historial de focos y del terreno. En la práctica, muchas celdas quedan con el mismo puntaje (empates). En la evaluación de HU-83 (años 2023 a 2026), entre el 74,5 % y el 89,0 % de los momentos de pronóstico tenían celdas empatadas justo en el corte del Top 5. Cuando eso ocurre, el orden entre las celdas empatadas es arbitrario. Fuente: resultados de HU-83, commit `2175742` de la rama `ml/sapi-83-preregistro` (`reports/evaluacion_modelo_d_20261122.json`). El rango corregido está en la sección 12 de `docs/preregistro_sapi83.md`, commit `afb8725`.
- **No sirve para decisiones operacionales.** Es un prototipo exploratorio.

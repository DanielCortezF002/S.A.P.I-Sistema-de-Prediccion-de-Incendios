# El Modelo D en una página

*HU-88 · 22-11-2026 · Fuente de las cifras: `reports/hu88_explicacion_modelo_d/` (generado con `python scripts/explicar_modelo_d.py`).*

## Qué es

El Modelo D es el programa que S.A.P.I. usa para **ordenar las 50 celdas de la zona de Valparaíso de más a menos preocupante** para las próximas 6 horas. No dice "va a haber un incendio aquí". Dice "si hubiera que mirar primero algunas celdas, estas parecen más parecidas a las situaciones donde antes aparecieron focos de calor".

Por dentro es un conjunto de **22 árboles de decisión** pequeños (técnicamente, un `HistGradientBoostingClassifier`). Cada árbol hace hasta 4 preguntas seguidas del tipo "¿la temperatura supera tal valor?" y termina en una de sus 16 respuestas posibles. El puntaje final suma lo que aportan los 22 árboles.

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

## Limitaciones

- **El puntaje es un orden relativo, no una probabilidad.** Un 0,13 no significa "13 % de probabilidad de incendio" (`score_semantics = relative_rank`).
- **No está validado científicamente.** El sistema declara `scientific_model_validation = false`, y este documento no cambia esa condición.
- **El modelo desplegado se entrenó con todo el periodo 2021–2026** (30-08-2021 a 29-08-2026). No se reservó un periodo de prueba. Las métricas publicadas vienen de reentrenamientos por año (`docs/model_card_baseline.md`), no de este archivo.
- **Aprendió de muy pocos casos:** 107 situaciones positivas entre 362.883 filas.
- **Usa una sola estación meteorológica** (Rodelillo, 330007) para toda la zona, así que todas las celdas comparten el mismo clima en un mismo momento. Las diferencias entre celdas vienen del historial de focos y del terreno. En la práctica, muchas celdas quedan con el mismo puntaje (empates).
- **No sirve para decisiones operacionales.** Es un prototipo exploratorio.

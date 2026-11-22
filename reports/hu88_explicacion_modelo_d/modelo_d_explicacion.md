# HU-88 -- Explicacion estructural del Modelo D

- Generado: 2026-11-22T06:11:17+00:00
- Artefacto: `models/prototype_model_d.pkl`
- SHA-256 verificado (antes de cargar y despues): `ac017bef1f42a30ac74ba3e3787368c4418798b2d562adcfba01c923cff2173f`
- Tipo: HistGradientBoostingClassifier -- 22 arboles, 25 variables (verificado contra lo esperado: 22 / 25)
- Datos usados: ninguno (solo estructura del artefacto; el dataset no se lee)

## Por que hay este numero de arboles

Parametros leidos del artefacto: early_stopping='auto', n_iter_no_change=10, max_iter=100, tol=1e-07, validation_fraction=0.1, scoring='loss'; atributos: n_iter_=22, do_early_stopping_=True, validation_score_ con 23 valores. El entrenamiento se detuvo por parada temprana en la iteracion 22 de 100 posibles: la mejor puntuacion de validacion interna se alcanzo tras 12 arboles y las 10 iteraciones siguientes no la mejoraron. scikit-learn conserva todos los arboles construidos hasta detenerse; no descarta los posteriores a la mejor iteracion de validacion.

## Forma de los arboles

- Profundidad maxima por arbol: 4--4 (hiperparametro max_depth=4)
- Hojas por arbol: 16--16 (total 352)
- Particiones totales: 330
- Variables que ningun arbol usa: meteo_actual_regla_30_30_30, meteo_lag_6h_regla_30_30_30, meteo_lag_12h_regla_30_30_30, meteo_lag_24h_regla_30_30_30, meteo_lag_48h_regla_30_30_30

## Importancia de variables (ganancia de particion)

Importancia por ganancia: suma del campo 'gain' (reduccion de la perdida log-loss lograda por la particion, segun scikit-learn) de todos los nodos internos que usan cada variable, normalizada para sumar 1. Se calcula solo con la estructura del artefacto (sin datos). Es una medida interna del entrenamiento: no es causal, no es importancia por permutacion, y puede sobrevalorar variables continuas con muchos umbrales posibles.

Fuente del calculo: Calculada por este script recorriendo atributos PRIVADOS de scikit-learn 1.9.0 (HistGradientBoostingClassifier._predictors y TreePredictor.nodes). No es un atributo oficial del modelo (HistGradientBoostingClassifier no expone feature_importances_) y puede romperse o cambiar con otra version de scikit-learn.

| # | Variable | Importancia (ganancia) | Particiones | Arboles que la usan | Veces en raiz |
|---|---|---:|---:|---:|---:|
| 1 | `meteo_actual_temp` | 42.1 % | 47 | 22 | 19 |
| 2 | `dias_desde_ultimo_evento` | 11.4 % | 35 | 22 | 0 |
| 3 | `meteo_lag_6h_temp` | 11.0 % | 53 | 22 | 2 |
| 4 | `meteo_lag_24h_hr` | 5.5 % | 19 | 10 | 0 |
| 5 | `meteo_lag_6h_hr` | 4.5 % | 39 | 22 | 0 |
| 6 | `meteo_lag_24h_temp` | 3.5 % | 14 | 11 | 1 |
| 7 | `meteo_actual_hr` | 3.3 % | 12 | 8 | 0 |
| 8 | `meteo_lag_48h_viento` | 2.6 % | 17 | 13 | 0 |
| 9 | `meteo_lag_12h_temp` | 2.6 % | 10 | 10 | 0 |
| 10 | `meteo_lag_48h_hr` | 2.2 % | 11 | 10 | 0 |
| 11 | `meteo_actual_viento` | 2.0 % | 12 | 9 | 0 |
| 12 | `meteo_lag_12h_viento` | 1.6 % | 11 | 9 | 0 |
| 13 | `meteo_lag_24h_viento` | 1.4 % | 7 | 6 | 0 |
| 14 | `elevacion` | 1.3 % | 6 | 6 | 0 |
| 15 | `historial_firms_count` | 1.2 % | 7 | 7 | 0 |
| 16 | `meteo_lag_48h_temp` | 1.0 % | 7 | 5 | 0 |
| 17 | `meteo_lag_6h_viento` | 0.9 % | 6 | 5 | 0 |
| 18 | `orientacion` | 0.8 % | 8 | 8 | 0 |
| 19 | `meteo_lag_12h_hr` | 0.7 % | 6 | 6 | 0 |
| 20 | `pendiente` | 0.4 % | 3 | 3 | 0 |
| 21 | `meteo_actual_regla_30_30_30` | 0.0 % | 0 | 0 | 0 |
| 22 | `meteo_lag_6h_regla_30_30_30` | 0.0 % | 0 | 0 | 0 |
| 23 | `meteo_lag_12h_regla_30_30_30` | 0.0 % | 0 | 0 | 0 |
| 24 | `meteo_lag_24h_regla_30_30_30` | 0.0 % | 0 | 0 | 0 |
| 25 | `meteo_lag_48h_regla_30_30_30` | 0.0 % | 0 | 0 | 0 |

Figura: `modelo_d_importancias.svg` (misma informacion que la tabla).

## Detalle por arbol

| Arbol | Nodos | Hojas | Particiones | Profundidad | Variable raiz | Ganancia total |
|---:|---:|---:|---:|---:|---|---:|
| 1 | 31 | 16 | 15 | 4 | `meteo_actual_temp` | 216386.036 |
| 2 | 31 | 16 | 15 | 4 | `meteo_actual_temp` | 185835.422 |
| 3 | 31 | 16 | 15 | 4 | `meteo_actual_temp` | 159753.180 |
| 4 | 31 | 16 | 15 | 4 | `meteo_actual_temp` | 131999.960 |
| 5 | 31 | 16 | 15 | 4 | `meteo_actual_temp` | 122452.531 |
| 6 | 31 | 16 | 15 | 4 | `meteo_actual_temp` | 102472.674 |
| 7 | 31 | 16 | 15 | 4 | `meteo_actual_temp` | 92118.521 |
| 8 | 31 | 16 | 15 | 4 | `meteo_actual_temp` | 88387.425 |
| 9 | 31 | 16 | 15 | 4 | `meteo_actual_temp` | 59600.301 |
| 10 | 31 | 16 | 15 | 4 | `meteo_actual_temp` | 68953.453 |
| 11 | 31 | 16 | 15 | 4 | `meteo_actual_temp` | 58250.980 |
| 12 | 31 | 16 | 15 | 4 | `meteo_actual_temp` | 46961.497 |
| 13 | 31 | 16 | 15 | 4 | `meteo_actual_temp` | 55275.497 |
| 14 | 31 | 16 | 15 | 4 | `meteo_actual_temp` | 41570.452 |
| 15 | 31 | 16 | 15 | 4 | `meteo_actual_temp` | 42827.958 |
| 16 | 31 | 16 | 15 | 4 | `meteo_actual_temp` | 37266.254 |
| 17 | 31 | 16 | 15 | 4 | `meteo_actual_temp` | 36587.377 |
| 18 | 31 | 16 | 15 | 4 | `meteo_actual_temp` | 30657.796 |
| 19 | 31 | 16 | 15 | 4 | `meteo_lag_24h_temp` | 31104.463 |
| 20 | 31 | 16 | 15 | 4 | `meteo_actual_temp` | 19513.582 |
| 21 | 31 | 16 | 15 | 4 | `meteo_lag_6h_temp` | 32334.995 |
| 22 | 31 | 16 | 15 | 4 | `meteo_lag_6h_temp` | 32052.986 |

## Limitaciones

- El score del Modelo D es un ranking relativo, no una probabilidad calibrada.
- `scientific_model_validation=false`: este reporte no valida el modelo.
- La importancia por ganancia describe como el modelo se ajusto a sus datos de entrenamiento; no mide causalidad ni desempeno fuera de muestra.
- La importancia por ganancia y el detalle por arbol se calculan con atributos privados de scikit-learn 1.9.0 (`_predictors`); otra version puede no ser compatible.

Entorno: python 3.14.10, numpy 2.5.2, scipy 1.18.1, sklearn 1.9.0, joblib 1.5.3

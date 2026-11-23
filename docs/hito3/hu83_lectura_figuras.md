# HU-83 (CA6): curva de entrenamiento y matrices de confusión del Modelo D, explicadas

Este texto alimenta el informe del Hito 3. No recalcula nada: cada cifra sale de los archivos citados, que se verificaron el 22-11-2026.

> Aviso permanente: el score de S.A.P.I. es un **ranking relativo**, no una probabilidad calibrada (`scientific_model_validation=false`).

## Fuentes

| Figura | Archivo | SHA-256 | Dato de origen |
|---|---|---|---|
| Curva de entrenamiento | `reports/sapi83/curva_ca1_20261122T181645Z/curva_entrenamiento_modelo_d.png` | `792f3b61…2d812` | `curva_ca1.json`, modo `--solo-curva-ca1`, código `afb8725`, 2026-11-22T18:16:50Z |
| Matriz por zona (Top 5) | `reports/sapi83/figuras_regeneradas_20261122T181645Z/figuras_sapi83/matriz_zona_top5_2023_2026.png` | `45d94754…000aa` | `reports/evaluacion_modelo_d_20261122.json`, ejecución R2–R6, código `71722ef`, 2026-11-22T06:01:11Z |
| Matriz por día | `reports/sapi83/figuras_regeneradas_20261122T181645Z/figuras_sapi83/matriz_dia_con_sin_incendio.png` | `b882581d…adb4` | El mismo JSON |

Artefacto evaluado: `models/prototype_model_d.pkl` (SHA-256 `ac017bef…2173f`), que no se modificó. Dataset: `14b36ad8…`. Protocolo walk-forward: cada año se evalúa con un modelo entrenado solo con los años anteriores. Preregistro en `c15993c`, sello en `71722ef`.

Las versiones regeneradas reemplazan a las de `reports/figuras_sapi83/`, que fueron las primeras. Las regeneradas se generaron desde el mismo JSON, ya con el defecto E2 corregido. En el JSON, el campo `figuras` guarda rutas absolutas de Windows (`C:\Users\…`). Esa es una deuda menor: las rutas válidas son las de esta tabla. El campo `curva_entrenamiento_desplegado` del JSON quedó superado por `curva_ca1.json` (ver `reports/sapi83/anexo_correccion_ca1.md`).

## 1. Curva de entrenamiento

**Qué muestra.** Cómo cambia el error del Modelo D a medida que se agregan árboles. La línea azul es el error sobre los datos con que se entrenó; la naranja, sobre una parte reservada para validar. El eje es el log-loss negativo: más arriba es mejor. No es una medida de acierto.

**Qué se ve.**
- El error de entrenamiento mejora en todas las iteraciones, de −0,693 a −0,200.
- La validación mejora hasta la iteración 12, donde llega a su mejor valor (−0,508). Después empeora, hasta −0,559 en la iteración 22.

**Qué significa.** Desde la iteración 12 el modelo sigue aprendiendo detalles de los datos de entrenamiento que no se repiten en datos nuevos. Eso es sobreajuste. Por eso el entrenamiento se detuvo en 22 árboles: la detención temprana espera 10 iteraciones sin mejora (12 + 10 = 22). No llegó al tope de 100 (`max_iter`). Lo verifica `tests/test_hu88_explicar_modelo_d.py::test_artefacto_real_parada_temprana`.

**Limitación.** La validación interna la separa el propio estimador, no por año. Esta curva describe el entrenamiento, no el desempeño en años futuros; eso lo miden las matrices.

## 2. Matriz por zona: ¿la celda con incendio estaba en el Top 5?

**Regla.** Es la misma que usa la pantalla (`app/utils/score_contract.py`): las 5 celdas mejor rankeadas en cada pronóstico. «Hubo detección» quiere decir que NASA FIRMS registró un foco en esa celda dentro del horizonte.

| 2023–2026 | Top 5 | Fuera del Top 5 |
|---|---|---|
| Hubo detección | 12 | 70 |
| No hubo | 26 643 | 239 738 |

Por año, aciertos sobre el total de casos con detección (sensibilidad):

| Año | Acertadas / con detección | Sensibilidad |
|---|---|---|
| 2023 | 1/19 | 5,3 % |
| 2024 | 5/46 | 10,9 % |
| 2025 | 4/7 | 57,1 % |
| 2026 | 2/10 | 20,0 % |

**Qué significa.**
- De 82 casos con detección, el Top 5 incluyó 12, es decir el 14,6 %. El resto quedó fuera.
- Los focos son muy raros (82 en más de 266 000 combinaciones de celda y pronóstico). Por eso casi todo lo que aparece en el Top 5 es «falsa alarma» (26 643), y la precisión es cercana a 0 (0,05 %).
- La especificidad (90 %) parece buena solo por esa rareza. No hay que leerla como mérito del modelo.

**Límite fuerte.** En el 82,3 % de los pronósticos (4390 de 5331) hay empate justo en el corte del Top 5. Por año, va de 74,5 % (2025) a 89,0 % (2024). Entre celdas empatadas el orden es arbitrario (D8), y 17 positivos cayeron en ese grupo empatado. Esta matriz se presenta siempre junto a este dato.

**Por qué 2025 parece mejor.** Solo tuvo 7 casos con detección. Con tan pocos casos, 57 % no permite concluir nada. El único año con casos suficientes es 2024 (46), y ahí la sensibilidad fue 10,9 %.

## 3. Matriz por día: ¿el modelo distingue días con y sin incendio?

**Muestra.** 18 días fijados antes de ejecutar (`docs/dias_prueba_seleccionados.csv`): 9 con incendio y 9 sin incendio, emparejados por fecha cercana. Incluye el megaevento del 2 y 3 de febrero de 2024. Un día es «de alerta» si el score supera el percentil 90, calculado solo con años de entrenamiento.

| 18 días | Día de alerta | Día sin alerta |
|---|---|---|
| Hubo detección | 6 | 3 |
| No hubo | 3 | 6 |

**Qué significa.** El modelo marcó como alerta 6 de los 9 días con incendio, y también 3 de los 9 días sin incendio (sensibilidad y especificidad de 66,7 %). Separa mejor los días que las celdas. Con 18 días, una diferencia de un día mueve el resultado 11 puntos, así que esta matriz ilustra el comportamiento; no lo valida.

## 4. Conclusión para el informe

- El Modelo D sirve como **ordenamiento relativo**. No sirve como predictor confiable de en qué celda habrá un foco: con la regla Top 5 encontró 12 de 82 casos (14,6 %), y la mayoría de los pronósticos tiene empate en el corte.
- A nivel de día muestra alguna capacidad para separar días con y sin incendio. La muestra (18 días) es demasiado chica para afirmarlo.
- Estos resultados son coherentes con el Hito 2: el Modelo A, que solo usa el historial FIRMS, supera al D en PR-AUC en 3 de 4 años. La comparación formal es HU-65.
- La lectura en lenguaje simple para usuarios de bomberos la revisan Mauricio Herrera y Angelo Sepúlveda (HU-83.V). Su opinión queda como comprensión percibida, no como validación científica.

## Trazabilidad

| Elemento | Referencia |
|---|---|
| HU | SAPI-83 (PR #47) |
| Requisito y objetivo | OE5; el requisito sigue pendiente de definirse en el catálogo (HU-92.T6) |
| Casos negativos | `tests/test_sapi83_evaluacion_modelo_d.py`: 57 casos (fuga de umbral y reproducción alterada) |
| Control de reproducción | SÍ, en `2175742`, contra `reports/experiment_abcd_h6_results.json` |
| Revisión independiente | `reports/sapi83/auditoria/` (GO CA2–CA5 sobre `2175742`; GO CA1 sobre `8401649`) |

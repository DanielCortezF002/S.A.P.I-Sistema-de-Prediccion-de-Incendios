# S.A.P.I. scientific claims — reglas NO NEGOCIABLES

Estas reglas vienen directamente de la auditoría metodológica del
pipeline temporal de S.A.P.I. (Fases 1-4, documentadas en
`docs/auditoria-consistencia-2026-09-06.md` y en el historial de este
proyecto). No son estilo de redacción: son límites de lo que el
proyecto puede afirmar honestamente sobre sí mismo, dado lo que
realmente se ha construido y verificado. Cualquier documento producido
con este skill que hable de S.A.P.I. debe respetarlas exactamente,
incluso si eso hace el documento menos impresionante.

Si una sección de un documento contradice algo de este archivo, el
documento está mal -- no este archivo.

## Arquitectura conceptual (la única formulación correcta)

```
regional_meteo
  +
características espaciales/estáticas por celda (topografía)
  +
historia temporal FIRMS disponible hasta T
  ↓
score/ranking relativo futuro por celda
```

## Formulación defendible del sistema (usar esta, no una propia)

> "S.A.P.I. estima y prioriza el riesgo relativo de nuevas detecciones de
> fuego en una grilla espacial, utilizando información disponible antes
> de la ventana futura."

No reformular esto para sonar más ambicioso. Si un documento necesita una
frase de una sola línea que resuma qué hace S.A.P.I., es esta.

## Reglas NO NEGOCIABLES

- **La estación DMC 330007 (Rodelillo) aporta meteorología REGIONAL.**
  Nunca asignar artificialmente esa observación meteorológica como si
  fuera una medición independiente de cada celda de la grilla. Una
  medición de Rodelillo sigue siendo una medición de Rodelillo -- nunca
  se convierte en "la meteorología de la celda VP-038".
- **FIRMS detection ≠ incendio confirmado.** Una detección satelital es
  una detección satelital: un valor de brillo/confianza sobre un pixel,
  no una confirmación en terreno de un incendio.
- **`target = nueva detección/arribo FIRMS en celda durante (T, T+h]`.**
  Esta es la definición exacta del target, con ventana abierta en T
  (un arribo exactamente en T no cuenta como "futuro").
- **Horizonte experimental actual = 6 horas.** No generalizar a "predice
  a corto plazo" ni a ningún otro horizonte sin una corrida real que lo
  sostenga.
- **Los features temporales deben usar solamente información ≤ T.**
  Cualquier feature que use información posterior a T en un documento
  que describe el pipeline real es una descripción incorrecta del
  sistema.
- **Los joins temporales son backward/as-of**, nunca joins que miren
  hacia adelante en el tiempo.
- **`cell_id` no es un predictor directo.** El modelo no aprende
  "esta celda es peligrosa por su identidad"; aprende de features
  reales (historial, topografía, meteorología) que varían por celda.
- **Múltiples detecciones FIRMS pueden corresponder al mismo evento
  físico** (la misma pasada satelital puede capturar el mismo incendio
  varias veces, o incendios distintos muy próximos en el tiempo).
- **`event_id` (raw episode) es una agrupación algorítmica**
  (`assign_episodes()`, radio 2 km / gap 6 h, parámetros congelados), no
  un "incendio independiente" verificado en terreno. Nunca usar la frase
  "incendio independiente", "eventos independientes" ni equivalentes
  para describir `event_id`. La terminología correcta es "raw episode"
  o "episodio crudo del algoritmo de clustering".
- **La regla 30-30-30 es un indicador/feature operacional**, no un
  target. No presentarla como el criterio que define si hay o no un
  incendio.
- **El score del prototipo ≠ probabilidad calibrada de incendio.** Es un
  ranking relativo, exploratorio. Ver la sección siguiente para el
  lenguaje exacto permitido.
- **El prototipo ≠ sistema oficial de alerta.** Ningún documento debe
  insinuar que S.A.P.I., en su estado actual, opera como un sistema de
  alerta oficial o reemplaza a CONAF/SENAPRED.
- **Tests passing ≠ validación científica.** Que la suite de tests pase
  (470/470 al momento de escribir esto) demuestra corrección técnica del
  código, no que el sistema tenga capacidad predictiva demostrada. Estos
  son dos afirmaciones distintas y un documento nunca debe presentar la
  primera como evidencia de la segunda.
- **La evidencia experimental actual es limitada/exploratoria.** No
  afirmar generalización operacional sin evidencia adicional que hoy no
  existe.

## Lenguaje permitido vs. prohibido

| Prohibido (salvo que la evidencia citada lo sostenga explícitamente) | Usar en su lugar |
|---|---|
| "S.A.P.I. predice incendios" | "S.A.P.I. construye un ranking exploratorio de riesgo relativo para nuevas detecciones FIRMS futuras, condicionado a la información disponible en T" |
| "incendio independiente" / "evento independiente" (para `event_id`) | "raw episode" / "episodio crudo del algoritmo de clustering" |
| "probabilidad de incendio" (para el score del modelo) | "score relativo de riesgo exploratorio" |
| "sistema de alerta" | "prototipo de apoyo a decisión / priorización exploratoria" |
| "validado" (sin calificar qué tipo de validación) | especificar: "técnicamente verificado (tests)", "validado en un experimento exploratorio", o explícitamente "no validado científicamente todavía" |
| "el modelo distingue las celdas de alto riesgo" cuando hay empates masivos de score | describir el empate honestamente (ver más abajo) |

## Empates de score (hallazgo real, no ocultar)

En la corrida más reciente del prototipo, 41 de 50 celdas comparten
exactamente el mismo score (`HistGradientBoostingClassifier`, muy pocos
positivos históricos). Esto se investigó explícitamente: las filas de
features que entran al modelo son mayoritariamente distintas entre sí
(43 de 50 filas únicas), pero el modelo no las distingue en su salida
bajo esas condiciones meteorológicas. Un documento que describa el
prototipo debe mencionar esto como lo que es -- una limitación real del
soporte estadístico disponible, no un defecto del pipeline de datos --
en vez de omitirlo u ocultarlo detrás de un ranking que parece más
granular de lo que realmente es.

## Tres niveles de resultado (nunca colapsarlos en uno)

Todo documento que reporte resultados de S.A.P.I. debe distinguir estos
tres niveles explícitamente, y nunca presentar el nivel 2 como si fuera
el nivel 3:

1. **Técnico**: el código corre, los tests pasan, la causalidad temporal
   está verificada.
2. **Exploratorio**: números concretos de un experimento (PR-AUC,
   hit@K, etc.), presentados como lo que son -- resultado de una corrida
   exploratoria, no una conclusión.
3. **Evidencia de capacidad predictiva**: un criterio de éxito
   explícito y acordado (p. ej. mejora consistente en múltiples
   particiones temporales, con soporte estadístico adecuado) que, a la
   fecha de este archivo, ningún experimento de S.A.P.I. ha cumplido
   todavía.

## Terminología fijada (usar exactamente estos términos)

- "raw episode" (no "evento independiente", no "incendio confirmado").
- "score relativo de riesgo exploratorio" (no "probabilidad de
  incendio").
- "meteorología regional as-of-T" (no "meteorología de la celda").
- "ranking exploratorio" (no "predicción").
- "prototipo funcional local" (no "sistema en producción", no "sistema
  de alerta").

# Centro de Control SAPI (solo lectura)

Una sola pantalla para saber si SAPI está operativo, con qué datos evaluó, cuándo, qué
50 celdas priorizó y qué alerta generaría. Página Streamlit dentro de la app existente
(`app/pages/dashboard.py`, ruta `/dashboard`). No es otro proyecto ni otro framework.

## Lanzar

```bash
# Demo: fixture sintética local. Sin backend ni internet.
streamlit run app/app.py            # → http://localhost:8501/dashboard?demo=1
# Modo presentación (tipografía grande, sin detalles de desarrollo)
#                                   → http://localhost:8501/dashboard?demo=1&presentation=1

# En vivo: lee el bridge existente (tools/n8n_bridge/app.py)
SAPI_SCORE_URL=http://127.0.0.1:8600/score streamlit run app/app.py
#                                   → http://localhost:8501/dashboard
```

`SAPI_SCORE_URL` vale `http://127.0.0.1:8600/score` por defecto. `presentation=1` también
funciona en vivo (`/dashboard?presentation=1`).

## Fuente de datos

- **En vivo:** un único `GET /score` del bridge. `Actualizar vista` repite ese GET.
  **Actualizar vista no actualiza las fuentes de datos** (FIRMS, DMC, CURRENT).
- **Demo:** `app/data/demo_score_synthetic.json`, marcada `_synthetic`. Se ve con banda
  punteada, píldora `DEMO · DATOS DEMOSTRATIVOS` y un aviso grande `DATOS DEMOSTRATIVOS`.
  Si una respuesta en vivo trae `_synthetic`, también se presenta como demo.
- Demo y en vivo usan cachés separadas: si el modo en vivo falla, nunca muestra valores de la demo.

## Estados del sistema

| Estado            | Cuándo                                                                         |
| ----------------- | ------------------------------------------------------------------------------ |
| OPERATIVO         | `200` con un ranking que pasa la validación de presentación                    |
| DEMO              | fixture sintética                                                              |
| DATOS NO DISPONIBLES | `error_type=data_unavailable`                                               |
| EVALUACIÓN NO DISPONIBLE | `prototype_unavailable` / `internal_error`. Si el mensaje upstream es el de desfase FIRMS sobre el máximo, FIRMS se muestra **BLOQUEADO** con fecha y desfase (solo esos dos valores se extraen; el mensaje nunca se muestra) |
| RESULTADO INVÁLIDO | respuesta vacía, no JSON, HTTP inesperado o contrato roto                     |
| SERVICIO NO DISPONIBLE | error de conexión o tiempo de espera agotado                              |

Sin ranking válido no se dibuja Top 5, mapa ni tabla, y el panel dice que la ausencia de
ranking no indica que la situación sea segura.

**Validación de presentación** (`app/utils/score_contract.py`, no replica la del backend):
exactamente 50 celdas de la grilla oficial, `cell_id` y `rank` únicos, rank 1..50,
score finito en [0, 1], orden de score coherente con el rank, metadatos de empate
consistentes, `inputs_fingerprint` hex de 64, hora de evaluación ISO y metadatos FIRMS con
los valores que SAPI emite. Cualquier fallo descarta la respuesta entera.

## Qué muestra

1. **Estado del sistema** y evaluación: hora, celdas evaluadas, FIRMS, meteorología DMC, modelo.
2. **Top 5**: ranks 1–5 del servicio, score relativo y empates señalados sin cambiar el rank.
3. **Mapa**: las 50 celdas en su posición real (geometría de `src/geo/grid.py`, EPSG:4326,
   sin mapa base, así funciona sin internet). La intensidad es score / score máximo de la
   evaluación. El tooltip muestra celda, rank y score relativo.
4. **Estado de datos**: FIRMS, DMC, TOPOGRAFÍA y MODELO con texto y símbolo
   (✓ AL DÍA, ● DISPONIBLE, ▲ CON AVISO, ■ BLOQUEADO, ✕ NO DISPONIBLE, ? DESCONOCIDO).
   FIRMS y DMC reflejan la clasificación upstream (`FIRMS AL DÍA` / `FIRMS DESACTUALIZADO`,
   frescura DMC); el panel no define umbrales propios.
5. **Ranking completo**: las 50 filas en el orden del backend, con búsqueda por celda y
   un orden de vista por ID. El rank canónico siempre es visible y nunca cambia.
6. **Vista previa de alerta**: el interruptor `Vista previa` muestra el texto que generaría
   `src/notifications/alert_payload.py` (módulo puro). No hay botón de envío.
7. **Limitaciones** y **Detalles técnicos** (fingerprint, identidades y valores de estado sin
   procesar; los hashes completos aparecen en bloques copiables).

Identidades del modelo, de FIRMS, de DMC y de topografía se leen de `scoring_inputs` si la
respuesta lo trae. **El bridge actual no lo serializa**, así que en vivo esos campos dicen
`NO DISPONIBLE EN RESPUESTA`. La demo los incluye con hashes sintéticos.

## Lenguaje científico

- Siempre "score relativo" o "prioridad relativa", nunca probabilidad ni porcentaje.
  Texto fijo: *"El score representa prioridad relativa dentro de las celdas evaluadas. No
  corresponde a una probabilidad calibrada ni confirma la existencia de un incendio."*
- FIRMS = anomalías térmicas satelitales, no incendios confirmados.
- No hay niveles ALTO, MEDIO ni BAJO, ni textos como "seguro" o "sin incendios".
  Los tests lo verifican en todos los estados.

## Solo lectura (intencional)

La página no refresca FIRMS ni DMC, no publica ni revierte `CURRENT`, no limpia, no programa
tareas y no llama a Telegram ni a n8n. Solo usa `GET`. Solo se muestran campos de una lista
blanca, escapados: nunca credenciales (`NASA_FIRMS_API_KEY`, `DMC_USUARIO`, `DMC_TOKEN`,
`Authorization`), entornos, trazas ni mensajes de error upstream.

Tests: `tests/test_ops_dashboard.py`.

# Centro de Control SAPI (solo lectura)

Una sola pantalla para saber si SAPI está operativo, con qué datos evaluó, cuándo, qué
50 celdas priorizó y qué alerta generaría. Es la capa de presentación del MVP: la misma
página muestra datos DEMO o el resultado EN VIVO aceptado del bridge. Página Streamlit de
la app existente (`app/pages/dashboard.py`). No es otro proyecto ni otro framework.

## Lanzar (un comando)

```bash
python -m app.control_center --demo                 # presentación sin bridge, n8n ni internet
python -m app.control_center --demo --presentation  # modo presentación (César / Matías)
python -m app.control_center --live                 # lee SAPI_SCORE_URL con GET /score
python -m app.control_center --live --score-url http://127.0.0.1:8600/score
```

El comando abre `http://127.0.0.1:8501/` (`--port`, `--no-browser`). En la misma URL:
`/?demo=1`, `/?demo=1&presentation=1`, `/?presentation=1`.

- **Configuración:** `SAPI_SCORE_URL` en `src/config.py` (por variable de entorno o `.env`,
  como el resto de la configuración). Por defecto es `http://127.0.0.1:8600/score`. Desde
  el contenedor web se usa `http://host.docker.internal:8600/score`.
- **El lanzador no inicia nada más:** ni bridge, ni n8n, ni refresh FIRMS/DMC, ni Docker,
  ni el operador. En modo en vivo, el bridge tiene que estar corriendo antes.
- Sigue disponible como página de la app principal (`streamlit run app/app.py`, luego
  `/dashboard`).

### Los dos 404 del navegador

Eran `GET /dashboard/_stcore/health` y `GET /dashboard/_stcore/host-config`. No son
recursos del Centro de Control. Cuando una página se abre por subruta, el frontend de
Streamlit 1.62 prueba primero `<subruta>/_stcore/*` y después la raíz. Pasa con cualquier
subruta (también `/nonexistent_page`); el backend no responde nada de eso. El lanzador sirve
la página en la raíz, así que esos sondeos no existen: en demo, presentación y en vivo, el
navegador registra **0 respuestas ≥ 400 y 0 errores de consola** (lo verifica
`test_application_owned_resources_do_not_404` con Chromium). Si la página se abre como
`/dashboard` dentro de `app/app.py`, esos dos sondeos siguen apareciendo: son del framework
y no afectan el funcionamiento.

## Un solo contrato de presentación

```
GET /score (GridScoreResult serializado por tools/n8n_bridge)
  → canonical_result()   lista blanca, forma del bridge, valores intactos
     ├─ validación de presentación (app/utils/score_contract.py)
     └─ build_alert() de src/notifications/alert_payload.py (misma entrada)
  → DashboardView: panel + AlertPreview
```

Si cualquiera de las dos validaciones rechaza el resultado, **ambas salidas** quedan en
INVALID_RESULT; nunca hay un panel válido junto a una alerta que diga otra cosa. Por
ejemplo, un `firms_lag_days` que no calza con la cobertura y la hora de evaluación se
rechaza en los dos. El Top 5 del panel y el de la alerta se comparan
`(rank, display_rank, cell_id, score)` por `(rank, display_rank, cell_id, score)`.
**El rank del backend es la autoridad:** no se reordena; los empates solo se marcan.

Validación de presentación (no replica la del backend): exactamente 50 celdas de la grilla
oficial; `cell_id` y `rank` únicos; rank de 1 a 50; score finito en [0, 1]; orden coherente;
metadatos de empate consistentes; `inputs_fingerprint` hex de 64; hora ISO; metadatos FIRMS
con los valores que SAPI emite; y, si la respuesta trae geometría, que coincida con
`src/geo/grid.py`. El mapa siempre dibuja esa grilla oficial (EPSG:4326), que es la
geografía real de las 50 celdas, en demo y en vivo.

## Estados

| Estado                  | Cuándo                                         | Qué se ve                                   |
| ----------------------- | ---------------------------------------------- | ------------------------------------------- |
| `DEMO`                  | solo `?demo=1` o `--demo` (fixture local)       | ranking sintético, rotulado DATOS DEMOSTRATIVOS |
| `LOADING`               | mientras se espera el GET                      | esqueleto sin valores                       |
| `LIVE_READY`            | `200` que pasa ambas validaciones               | OPERATIVO, ranking completo                 |
| `DATA_UNAVAILABLE`      | `error_type=data_unavailable`                  | "No hay datos suficientes para generar la evaluación actual." |
| `PROTOTYPE_UNAVAILABLE` | `prototype_unavailable` / `internal_error`     | "El servicio de evaluación no está disponible." FIRMS **BLOQUEADO** si el desfase supera el máximo upstream |
| `INVALID_RESULT`        | vacío, no JSON, HTTP inesperado, contrato roto, o marca sintética en vivo | RESULTADO INVÁLIDO, sin celdas |
| `NETWORK_ERROR`         | sin conexión o tiempo de espera agotado         | "No fue posible consultar el servicio SAPI." |

Sin ranking válido no hay Top 5, mapa, tabla ni alerta de ranking, y la página dice que la
ausencia de ranking no indica que la situación sea segura. **Nunca hay recurso a la demo:**
demo y en vivo tienen cachés separadas, y una respuesta en vivo con `_synthetic` se
rechaza.

**Encabezado:** `MODO: DEMO` o `MODO: EN VIVO`. En vivo, también `CONEXIÓN: CONECTADO /
NO DISPONIBLE / RESPUESTA INVÁLIDA`, medida **solo en la última consulta**. Si esa consulta
falló, se muestra la hora de la última consulta exitosa, pero no sus datos.

**Tres horas distintas:**

- **Última consulta de vista:** cuándo el panel leyó el servicio. No indica frescura.
- **Hora de evaluación:** el momento puntuado por el modelo (`forecast_time`).
- **Cobertura FIRMS hasta:** fin del histórico satelital usado.

## Vista previa de alerta e identidad

El panel "Vista previa de alerta" muestra, desde el mismo resultado, el Top 5, la hora de
evaluación, la cobertura FIRMS y el aviso científico. El interruptor `Vista previa` muestra
el texto completo. **Nada se envía:** no hay Telegram, n8n ni botón de envío.

`alert_fingerprint` (sha256 determinista de la alerta; no incluye `generated_at`) aparece
truncado en **Detalles técnicos** y completo en un bloque copiable.

**`ALERT_IDENTITY_RECONCILIATION_REQUIRED_BEFORE_TELEGRAM`.** `alert_fingerprint` identifica
una evaluación: hora, entradas, modelo, FIRMS y Top 5. `notification_identity` de
`ops/n8n/policy.js` identifica una condición:
`['sapi-pilot-v1', categoría, modelo, estación, grupo display_rank 1, regla 30-30-30]`.
Hoy no son equivalentes, y el fingerprint **no** se usa para deduplicar. Antes de cualquier
envío por Telegram hay que decidir una sola semántica de identidad y alinear n8n con ella.
Esta tarea no modifica n8n.

## Qué muestra cada modo

- **Presentación:** SAPI, estado, modo, Top 5, mapa de 50 celdas, cobertura FIRMS, estado de
  datos sin hashes, vista previa de alerta y limitaciones. Sin tabla completa ni detalles
  técnicos.
- **Operador:** lo anterior, más el ranking completo (búsqueda por celda y orden de vista por
  ID; el rank no cambia) y **Detalles técnicos**: modo, conexión, endpoint (sin
  credenciales ni query), horas, celdas evaluadas, inputs/alert fingerprint, identidad del
  modelo y metadatos FIRMS/DMC. Identidades de modelo/FIRMS/DMC/topografía solo si la
  respuesta trae `scoring_inputs`. **El bridge actual no lo serializa**, así que en vivo
  esos campos dicen `NO DISPONIBLE EN RESPUESTA`.

## Lenguaje científico

Siempre "score relativo" o "prioridad relativa": *"El score representa prioridad relativa
dentro de las celdas evaluadas. No corresponde a una probabilidad calibrada ni confirma la
existencia de un incendio."* FIRMS = anomalías térmicas satelitales. No hay niveles
ALTO/MEDIO/BAJO, porcentajes, "seguro", "sin incendios" ni "no hay riesgo". Los tests lo
verifican en todos los estados.

## Solo lectura

Única acción: `Actualizar vista`, que repite el `GET /score` y **no actualiza las fuentes de
datos**. No hay rutas ni acciones POST/PUT/DELETE, refresh FIRMS/DMC, publicación de
`CURRENT`, scoring, n8n ni Telegram. Solo se muestran campos de una lista blanca, escapados:
nunca `NASA_FIRMS_API_KEY`, `DMC_USUARIO`, `DMC_TOKEN`, `Authorization`, cookies, entorno,
trazas ni mensajes de error upstream.

Tests: `tests/test_ops_dashboard.py` (incluye un stub HTTP local en 127.0.0.1 que imita
el bridge).

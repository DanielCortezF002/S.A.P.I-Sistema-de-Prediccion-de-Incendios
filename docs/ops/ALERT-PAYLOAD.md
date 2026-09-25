# Alert Payload y vista previa (sin envío)

`src/notifications/alert_payload.py` transforma un resultado de scoring válido en un **payload de alerta canónico**, un texto en español y una vista previa lista para Telegram.
Es una transformación pura: **no envía nada**. No hay red, base de datos, n8n ni Telegram, y un test verifica que el módulo no importa clientes de red.

## Entrada
- El JSON de `GET /score` del bridge: en éxito (`status: "ok"`) o en error (`status: "error"`, `error_type`).
- Un `GridScoreResult`.
- La evidencia de `tools/ops/capture_score.py` (`{"score": {...}}`).

Solo se leen campos de una **lista blanca**:
- `forecast_time` (tiempo de evaluación T, ISO con zona horaria);
- `inputs_fingerprint` (sha256);
- `model_version`, `model_status` (opcionales);
- `freshness` (opcional);
- `firms_origin`, `firms_coverage_end`, `firms_lag_days`, `firms_status`;
- `cells[]`: `cell_id`, `score`, `rank`, `display_rank`, `tie_group_size` y `geometry` opcional.

Todo lo demás se ignora y nunca se copia: headers, tokens, `scoring_inputs`, mensajes de error upstream y campos de depuración.

## Estados
| Estado | Cuándo | Contenido |
|---|---|---|
| `READY` | Resultado íntegro | Ranking, FIRMS, limitaciones, fingerprint |
| `UNAVAILABLE` | Upstream `prototype_unavailable` o `data_unavailable` | Motivo enumerado; sin celdas. "La falta de ranking no significa que la situación sea segura" |
| `INVALID` | Cualquier incumplimiento, o upstream `internal_error` | `reasons[]` estables; sin celdas; nunca se copian valores recibidos |

Un estado nunca se convierte en otro: UNAVAILABLE e INVALID no pasan a READY.

**Validación (fail-closed):**
- **Celdas:** 50 celdas con `cell_id` únicos de VP-001..VP-050; `rank` exactamente 1..50, único y con rank 1; score presente, finito y en [0, 1]; el orden del score respeta el rank; `display_rank` y `tie_group_size` coherentes con los empates.
- **Identidad:** `inputs_fingerprint` de 64 hex; T con zona horaria.
- **FIRMS:** origen ∈ `FirmsOrigin`; estado ∈ {`FIRMS AL DÍA`, `FIRMS DESACTUALIZADO`}; lag y estado coherentes con `classify_firms_lag`. Es decir, se **presenta** la política de frescura de SAPI, no se redefine.
- **Etiquetas opcionales:** `model_*` y `freshness`, si vienen, deben ser seguras: si no, INVALID; no se "limpian".

## Esquema `sapi-alert-v1` (READY)
```
schema_version, status, scoring_time, inputs_fingerprint,
model {version, status} | null,
firms {origin, coverage_end, lag_days, status},
summary {ranking_basis:"rank", cell_count, top_n, top_group_size, ties_beyond_top_n, meteo_freshness},
top_cells [{rank, display_rank, tie_group_size, cell_id, score, geometry?}],
limitations [{code, text}], alert_fingerprint, generated_at?
```
- `top_n` es solo presentación. Por defecto vale **5**, el mismo corte "Top-5" documentado en `prototype_service`, y acepta 1..50.
- La lista respeta el `rank` validado (no se reordena).
- Los empates muestran `display_rank` compartido, y `ties_beyond_top_n` dice cuántas celdas empatadas con la última mostrada quedaron fuera.
- **No hay umbrales de riesgo** (bajo/medio/alto): no existe una política aprobada para alertas. Los niveles visuales de la UI no son una política.
- Ubicación: solo `geometry` (bbox de la grilla) si viene en la entrada. No se inventan comunas, direcciones ni nombres.

## Fingerprint (`alert_fingerprint`)
```
sha256( UTF-8( json.dumps(identity, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False) ) )
identity (READY) = {schema_version, status, scoring_time, inputs_fingerprint, model, firms,
                    top_n, cells: [[rank, display_rank, tie_group_size, cell_id, score], ...]}
identity (UNAVAILABLE/INVALID) = {schema_version, status, reasons (ordenados)}
```
- Los scores se serializan con el `repr` de `float` (el más corto que reproduce el valor, determinista).
- **`generated_at` no participa:** la misma entrada da el mismo fingerprint en cualquier momento.
- `stable_json(alert)` devuelve el JSON canónico sin `generated_at`.
- El módulo no guarda estado de dedupe: solo produce la identidad.

## Lenguaje
**Se permite:** prioridad relativa, ranking de atención, celda priorizada, score relativo (`0.140`, nunca como porcentaje), evaluación exploratoria, anomalías térmicas FIRMS.

**Está prohibido** (y lo verifica `assert_claim_safe` en cada salida, sin tildes ni mayúsculas): "probabilidad de incendio", "% de probabilidad", "incendio confirmado/detectado", "predicción confirmada", "certeza", "riesgo bajo", "sin incendios", "todo normal". Si una plantilla llegara a producirlas, se lanza `ClaimSafetyError`, un bug que nunca se degrada en silencio.

**Limitaciones que acompañan siempre a la salida:**
- ranking relativo, no probabilidad calibrada;
- FIRMS son anomalías térmicas;
- solo hay validación histórica, sin validación point-in-time con NRT.

## Vista previa para Telegram
`render_telegram_preview(alert)` devuelve `{send: false, parse_mode: null, disable_web_page_preview: true, text, length, status, alert_fingerprint}`.
- Es **texto plano**: sin Markdown ni HTML, ningún campo puede inyectar formato.
- Además, los valores dinámicos ya están validados, `@` se neutraliza para no crear menciones, y se eliminan caracteres de control y bidi.
- El largo se acota a 4096; si se excede, el texto se trunca y lo indica.

## CLI
```powershell
python -m src.notifications.alert_preview --input score.json [--top 5] `
  [--format text|json|telegram-preview] [--generated-at <ISO>]
```

| Exit | Estado |
|---|---|
| 0 | READY |
| 1 | INVALID (incluye archivo ilegible o que no es JSON) |
| 2 | Uso inválido |
| 3 | UNAVAILABLE |

Solo lee el archivo: sin HTTP.

Demo: `tests/fixtures/alert_demo/` (**SYNTHETIC DEMO ONLY**: valores inventados y salidas esperadas `expected_*`).

## Integración futura con n8n
n8n (o el operador) podría llamar `build_alert(resultado_de_score)` después del scoring aceptado:
- usar `alert_fingerprint` como identidad de dedupe;
- enviar solo `status == "READY"` y detenerse en UNAVAILABLE o INVALID.

Esto **no** se conecta hoy. Requiere, en este orden:
1. la aceptación operacional del Attempt 2;
2. un **gate humano separado** para Telegram;
3. alinear esta identidad con la `notification_identity` de `ops/n8n/policy.js`, que hoy deduplica por categoría y grupo superior.

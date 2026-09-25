# BRIDGE-OUTPUT-CONTRACT — `GET /score` (n8n-bridge)

Puente local de desarrollo (no es el FastAPI objetivo de ADR-002). Validación en
`tools/n8n_bridge/contract.py`; pruebas en `tests/test_n8n_bridge_contract.py`.
Cierra BRIDGE-01: un resultado incompleto o inconsistente ya no sale como 200.

## Respuesta 200 (`status: "ok"`)

Solo si `score_current_grid()` devuelve un `GridScoreResult` que cumple todo lo siguiente.
Los nombres de campos del payload no cambian.

### Metadata requerida

| Campo | Regla | Fuente |
|---|---|---|
| `model_version`, `model_status`, `station_id` | string no vacío | metadata del modelo / `STATION_ID` |
| `forecast_time`, `weather_timestamp` | timestamp con zona horaria | `ScoringInputs` |
| `horizon_hours` | entero >= 1 | metadata del modelo |
| `age_hours` | número finito | `score_current_grid()` |
| `freshness` | uno de `FRESHNESS_RECENT/DELAYED/HISTORICAL` | `prototype_service` |
| `meteo_actual.regla_30_30_30` | booleano | fila DMC |
| `meteo_actual.momento_observacion` | timestamp con zona horaria | fila DMC |
| `inputs_fingerprint` | `^[0-9a-f]{64}$` (sha256 del manifest) | `ScoringInputs.fingerprint` |
| `firms_origin` | `reproducibility` \| `current` \| `baseline` | `FirmsOrigin` |
| `firms_coverage_end` | fecha de calendario (`YYYY-MM-DD`) | `ScoringInputs` |
| `firms_lag_days` | entero, igual a `fecha(forecast_time) - firms_coverage_end`, <= `FIRMS_LAG_MAX_DAYS` | `classify_firms_lag()` |
| `firms_status` | igual al estado que `classify_firms_lag()` da para ese lag (`FIRMS AL DÍA` / `FIRMS DESACTUALIZADO`) | `classify_firms_lag()` |

### Celdas (`cells`)

- Exactamente 50 celdas (`len(all_cells())`), con `cell_id` únicos que son exactamente VP-001..VP-050.
- `score`: número finito en [0, 1] (NaN, ±Infinity, null, string o bool se rechazan).
- `rank`: entero; los ranks forman exactamente 1..50 (únicos, sin huecos, un solo rank 1).
- Los scores no suben al avanzar el rank (el rank sigue el score de mayor a menor).
- `display_rank` = 1 + nº de celdas con score mayor (`method="min"`); `tie_group_size` = nº de celdas con el mismo score exacto.
  Los empates reales son válidos (por ejemplo, las 50 celdas con `display_rank` 1).

### Opcionales (no se validan)

`station_name`, `disclaimer` (tiene respaldo en `_FALLBACK_DISCLAIMER`),
`meteo_actual.temperatura/humedad_relativa/velocidad_viento_kmh`, y por celda `geometry`,
`elevation` y `slope` (pueden ser null por diseño) y `historical_count`.

### Fuera del alcance del puente (es política de n8n, `ops/n8n/policy.js`)

La estación esperada, la ventana de validez, `freshness == DATOS RECIENTES`, lag FIRMS de 0 a 3
días y la regla 30-30-30. El puente puntúa y entrega un lag FIRMS de 4 a 7 (`FIRMS DESACTUALIZADO`) o
**negativo** (cobertura FIRMS posterior a la fecha de T: la implementación lo trata como
`FIRMS AL DÍA`). Retenerlos le corresponde a n8n (`firms_not_current`).

## Respuesta 200: contrato canónico `sapi-output-v1`

Es el mismo resultado validado arriba, en su forma de transporte. No es un segundo
resultado. Lo consumen sin transformación el Control Center, `alert_payload` y
`ops/n8n/policy.js` (`tools/n8n_bridge/output_contract.py`). A los campos existentes se
agregan:

| Campo | Contenido |
|---|---|
| `output_schema_version` | `"sapi-output-v1"` |
| `input_identity` | Identidades de `ScoringInputs.manifest()`, filtradas por lista blanca: `model {sha256, name, version}`, `firms {sha256, origin, pointer_version, coverage_start, coverage_end}`, `dmc {manifest_sha256, pointer_version, coverage_start, coverage_end}`, `topography {sha256, origin}`, `reproducibility_mode`, `code` |
| `alert_identity` | `{schema_version: "sapi-alert-v1", alert_fingerprint, top_n: 5}` |
| `limitations` | Las del payload de alerta |

- **Equivalencias de nombres:** `forecast_time` es la hora de evaluación (`scoring_time`
  en la alerta). `cells`, `firms_*` e `inputs_fingerprint` no cambian. El rank del
  backend es la autoridad: nadie lo reordena.
- **Integridad de entradas:** si el resultado trae `scoring_inputs`, `inputs_fingerprint`
  tiene que ser su hash canónico; si no lo es, responde 500. Solo se publican hashes hex
  de 64, identificadores `[A-Za-z0-9._-]` y fechas ISO. Nada con espacios ni `:` fuera de
  una fecha, así que un valor como `Authorization: Bearer …` no pasa.
- **Sin inventar:** lo que no existe upstream queda en `null`. Hoy `code` (identidad de
  código o corrida) siempre es null, y sin `scoring_inputs` los cuatro bloques también.
  El DMC se pasa tal como viene en el manifest; este contrato no toca módulos DMC.
- **Identidad de alerta:** sale de la única receta de `src/notifications/alert_payload.py`.
  Si esa receta no acepta el resultado, responde 500 y nunca 200 sin identidad.
  `ops/n8n/policy.js` la recalcula y bloquea el resultado si falta o no coincide.
  Detalle en `docs/ops/ALERT-PAYLOAD.md`.
- **Deduplicación en n8n:** con la identidad por evaluación, reintentar el mismo resultado
  no notifica dos veces. Una **evaluación nueva** (entradas, hora o Top 5 distintos) es
  una alerta nueva aunque el grupo superior no cambie. La supresión anterior de
  "condición persistente" (por grupo superior) ya no existe; decidir si se reintroduce,
  como política y no como segunda identidad, queda para el gate humano de Telegram.

Fixtures para n8n: `ops/n8n/fixtures/canonical-notification.json` (la política lo acepta)
y `tampered-identity.json` (lo bloquea). Ambos son la salida real del bridge para un
resultado sintético y `tests/test_output_pipeline.py` los mantiene al día.

## Errores (taxonomía existente, sin tipos nuevos)

| HTTP | `error_type` | Significado |
|---|---|---|
| 503 | `prototype_unavailable` | insumo fijado ausente o ilegible, FIRMS con lag > 7, sin meteo, etc. (`PrototypeUnavailableError`) |
| 503 | `data_unavailable` | contenido corrupto de un insumo legible (`DATA_INPUT_ERRORS`) |
| 500 | `internal_error` | excepción inesperada al puntuar, **o un resultado que no cumple este contrato, o que no se puede serializar (BRIDGE-01)** |

- Un resultado inválido es un fallo **interno**, no indisponibilidad de datos, así que responde 500 y no 503.
- El detalle de cada incumplimiento va solo al log (`sapi.n8n_bridge`); la respuesta no expone detalles internos.
- Nunca se rellena: no hay celdas vacías, score 0 ni "riesgo bajo" con 200.
- n8n ya trata `500` + `internal_error` como `blocked('internal_error')`, categoría `error`, que falla cerrado.

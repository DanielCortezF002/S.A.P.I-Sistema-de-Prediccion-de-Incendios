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

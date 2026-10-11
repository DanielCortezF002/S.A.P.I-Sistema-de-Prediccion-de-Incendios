# SAPI-61 — Evidencia Etapa B

| Campo | Valor |
|---|---|
| HU | SAPI-61. Etapa B sobre `main` actual. Sin merge. |
| `origin/main` | `d8192f04f73e8cc0227c0cc2f4e508e5ac6ad67a` (no cambió durante la integración) |
| HEAD revisado (Etapa A + delta Astra) | `72bc1c5f389463cffda959a6978d0d90be803a4d` (sigue siendo ancestro) |
| Merge de `main` | `f25efd870e099693a7a777fb44cb8e82cc732b03` |
| Corrida Compose | `8cf48a219d3ebfdb9392e8d63673bb1b27686343` |
| HEAD de la etapa | `00a9d3c0166674fc85c2dd1952c4adb61599c358` |
| Divergencia antes | 7 commits por delante, 7 por detrás. Base `736e5b45c07e4104d3ba841d6a11c1a12c47d7fa` |
| Divergencia después | 10 por delante, 0 por detrás |
| Fecha | 2026-10-11 (UTC) |

El commit `00a9d3c` solo mueve la conversión de fechas adentro de `_ranking`
para cumplir el freeze del servicio ML. No cambia el cuerpo HTTP respecto de
`8cf48a2`, que es el SHA de la corrida Compose.

## Contrato

`schema_version` sigue siendo `sapi-ranking-v0`. Se agregaron exactamente
estos campos opcionales, emitidos por el servicio ML desde el resultado de
la evaluación:

`weather_timestamp`, `age_hours`, `freshness`, `station_id`, `station_name`,
`firms_origin`, `firms_coverage_end`, `firms_lag_days`, `firms_status`.

No se agregaron `model_status`, `meteo_actual` ni `historical_count`.
`age_hours` es el instante de captura de la evaluación menos
`weather_timestamp`. No usa la hora del navegador ni `forecast_time`.
`score_semantics` permanece `relative_rank` y
`scientific_model_validation` permanece `false`. FIRMS se describe como
archivo de anomalías térmicas. DMC es la estación regional.

## Compose

Proyecto aislado `sapi60-preflight`, clon limpio, `scripts/compose_v2_preflight.py --keep`.
Resultado: **28/28 PASS** (`preflight_summary.json`).

- `GET /api/v1/ranking` → 200, 50 celdas, ranks 1..50, `relative_rank`, validación científica false.
- Identidad estable igual entre Spring y un `POST /predict` independiente. Los sha256 del cuerpo difieren (`98ec24bc…` y `cb51312d…`) porque `age_hours` cambia con el reloj de captura.
- Las celdas y la cabecera del fixture reproducible no tienen delta.
- Persistencia: 0→1 ejecución y 0→50 predicciones. Un segundo GET no aumenta los conteos.
- Flyway V001–V003. `celdas_geom`: 50, válidas, SRID 4326.
- Reinicio sin `-v`: la ejecución y las 50 filas siguen.

Streamlit corrió en un contenedor de la imagen ML recién construida, unido a
la red v2, con `SAPI_BACKEND_BASE_URL=http://backend:8080`. El servicio
`web-v2` (profile `presentation`) declara esa misma URL y no forma parte de
`docker compose up`. Su imagen (`Dockerfile.web`) no se construyó en esta
corrida.

## Navegador

Chrome contra `http://127.0.0.1:8501`. Capturas en este directorio.

| Archivo | Qué muestra |
|---|---|
| `01-load.png` | Carga, 50 celdas, DMC Rodelillo 330007, aviso de datos históricos (964 h), disclaimer |
| `02-ranking.png` | Ranking con empates ×7 y ×41, celda VP-038 seleccionada |
| `03-selection.png` | Panel de VP-038, prioridad 49, empate ×2, score 0.102103 |
| `05-traceability.png` | Schema, fingerprint, weather timestamp, 963.5 h, FIRMS reproducibility / lag 2 |
| `06-backend-down.png` | Backend detenido y caché invalidada: mensaje genérico, sin host ni traza |

El texto visible no convierte el score en probabilidad ni trata FIRMS como incendio confirmado. La meteorología por celda y `model_status` figuran como no informados.

## Pruebas

| Comando | Resultado |
|---|---|
| pytest dirigido tras el merge, antes del producto (`test_backend_client`, `test_ranking_backend_view`, `test_sapi61_http_stub`, `test_architecture`, `test_app_integration`, `test_compose_v2`) | 322 passed |
| `python -m pytest -q` en el HEAD de la etapa | 2036 passed, 114 skipped, cobertura 85.15 % |
| `./mvnw -q test` en `services/backend` | 140 tests, 0 fallos, 4 omitidos |
| `python -B scripts/freeze_check.py` en un clon de un solo worktree | FREEZE CHECK PASS (`freeze_check_clean_clone.txt`) |

En el worktree de trabajo el freeze marca F8 porque queda otro worktree de SAPI-60 en la máquina. No es un cambio de artefacto congelado: el clon limpio pasa, y F2 mantiene el fingerprint del Modelo D.

## Limitaciones

- Jira no está integrado en este entorno. No se publicó comentario ni se cambió el estado.
- No se abrió pull request. La revisión independiente de este delta está pendiente.
- `web-v2` está declarado y cubierto por `tests/test_compose_v2.py`; el navegador usó la imagen del servicio ML en la misma red.
- La corrida Compose es el commit padre del tip. El tip no cambia el JSON emitido.

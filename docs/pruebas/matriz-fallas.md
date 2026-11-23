# HU-91: matriz de fallas (punto de quiebre y comportamiento ante fallas)

Subtareas HU-91.T1 (SAPI-145) y HU-91.T4 (SAPI-171, D-04). Versión 0.1, 22-11-2026. Base: `main` en `9e70867`.

Responde las preguntas del profesor Matías sobre el Hito 2: **¿cuándo deja de ser confiable el ranking y qué hace el sistema cuando algo falla?** Cada fila combina una falla, el comportamiento esperado y la prueba automatizada que ya existe en el repositorio. Esa prueba falla si el comportamiento se rompe. Las filas sin prueba se declaran como brecha.

> El ranking es relativo: no es una probabilidad. Ninguna fila convierte el score en una medida de riesgo absoluto.

## 1. Fallas de servicio (el sistema no puede responder)

| ID | Falla | Comportamiento esperado | Prueba que lo verifica | Resultado en `main` |
|---|---|---|---|---|
| F-01 | El servicio ML rechaza la conexión (caído, puerto cerrado) | Backend `503 upstream_unavailable` con el cuerpo del contrato; el panel muestra un error controlado, sin traza ni ruta interna | `RankingMlUnavailableTests` (Java); `MlServiceClientTests.connectionRefusedIsUnavailable`; `test_connection_refused_is_a_controlled_error` | PASS (job `backend-unit` y `python`, run 41932911572) |
| F-02 | El ML no responde a tiempo (antes de los headers o con el cuerpo detenido) | Backend `504 upstream_timeout` en menos de 2,8 s | `RankingEndpointIntegrationTests.timeoutBeforeHeadersIs504` y `timeoutAfterHeadersIs504`; `MlServiceClientTests.stalledBodyIsTimeoutWithStatus` | PASS |
| F-03 | El ML corta la conexión a mitad del cuerpo | `503 upstream_unavailable` | `MlServiceClientTests.midBodyDisconnectIsUnavailableWithStatus` | PASS |
| F-04 | El ML responde algo que no cumple el contrato (proxy 502, HTML, `error_type` desconocido, cuerpo sobredimensionado) | `502 upstream_invalid_response` o `503 upstream_unavailable` según el caso; nunca se reenvía un cuerpo inválido | `RankingEndpointIntegrationTests.mapsMlFailures` (parametrizada); `oversizedBodyDoesNotWaitForTheRest` | PASS |
| F-05 | El backend no responde al panel (caído o con timeout) | El panel muestra un mensaje controlado y no inventa un ranking | `test_apptest_backend_down_shows_controlled_message`; `test_read_timeout_is_a_controlled_error` | PASS |
| F-06 | El backend responde 4xx o 5xx | El panel mapea el estado a un error tipado; un `error_type` desconocido se descarta | `test_backend_error_statuses_are_mapped`; `test_apptest_backend_http_error_shows_controlled_message`; `test_unknown_error_type_is_dropped` | PASS |
| F-07 | El ranking llega con menos de 50 celdas, duplicados o campos fuera del contrato | El panel lo rechaza completo (fail-closed) y no reordena ni rellena | `test_apptest_invalid_ranking_fails_closed_in_the_ui` | PASS |
| F-08 | La base PostgreSQL está caída o el pool está saturado (D-05) | `500 internal_error` en menos de 10 s, sin reiniciar; M1 = 0 con el pool saturado | `RankingDatabaseUnavailableIT` | **Brecha**: la prueba y el cambio están en la rama local de HU-75 (`C:\SAPI-S3-D05-HARDEN-20261103`), no en `main` (DT-05) |

### D-04: el ML detenido devuelve 504, no 503

El contrato (`contracts/openapi/backend.v0.yaml`) describe el 503 como «servicio ML no accesible». Un contenedor ML detenido cuyo host no rechaza la conexión agota el timeout y devuelve **504 `upstream_timeout`**. El código hace lo correcto (ADR-010; `MlCallException.Kind.TIMEOUT`), y F-01 y F-02 lo prueban. El desajuste está solo en el texto del contrato.

**Por qué no se corrigió en el Sprint 3:** el contrato está congelado por hash en `scripts/freeze_check.py` (`CONTRACT_PINS`). Si se cambia su texto, el job `freeze` falla. Volver a fijar el hash es una decisión de gobierno (como el re-pin GOV-F4F7-R1 del 20-10-2026), no una corrección técnica.

**Propuesta para que Daniel decida:**
- (a) Volver a fijar el hash con un cambio solo documental en las descripciones de 503 y 504, con su acta.
- (b) Dejarlo como deuda documentada en `docs/riesgos.md`.

## 2. Datos degradados (el sistema responde, pero el resultado es menos confiable)

Estos son los **puntos de quiebre**: el ranking sigue apareciendo, pero con una advertencia que el usuario tiene que ver.

| ID | Condición | Qué pasa con el ranking | Qué ve el usuario | Prueba | Resultado |
|---|---|---|---|---|---|
| Q-01 | La meteorología del ranking tiene más de 24 h | El orden se calcula con datos viejos | Banner «DATOS HISTÓRICOS / DESACTUALIZADOS» con la fecha real del dato; nunca «próximas horas» | `test_freshness_historical_beyond_twentyfour_hours`; `test_stale_banner_shows_the_real_weather_timestamp`; `test_header_never_labels_a_stale_inference_as_proximas_horas` | PASS |
| Q-02 | Meteorología entre 12 y 24 h | Dato con retraso | Estado «con retraso» | `test_freshness_delayed_between_twelve_and_twentyfour_hours`; `test_header_never_labels_delayed_data_as_proximas_horas` | PASS |
| Q-03 | Celda sin DEM (20 de 50, B-13) | El modelo usa valores imputados para elevación y pendiente | «Sin cobertura DEM de referencia en esta celda» y N/D; nunca «0 m» | `test_selected_panel_without_dem_coverage_shows_nd`; `test_selected_panel_v0_territory_from_reference_and_unavailable_states` | PASS |
| Q-04 | No hay lectura meteorológica real para el `forecast_time` pedido, o el insumo está corrupto | El ML no puntúa | `503 prototype_unavailable` / `data_unavailable`, propagados al panel | `test_prototype_unavailable_is_503`; `test_corrupt_input_is_503_data_unavailable`; `test_predict_future_forecast_time_is_503` | PASS |
| Q-05 | Empate en el corte del Top 5 (82,3 % de los pronósticos, HU-83) | El orden entre celdas empatadas es arbitrario | Insignia «empate ×N» en la celda | `test_selected_panel_v0_territory_from_reference_and_unavailable_states` (verifica «×2») | PASS en la vista. Que el usuario lo entienda se valida en HU-91.V |
| Q-06 | Dato ausente en el ranking o en la observación DMC (campo fuera del contrato v0 o sin ingesta) | Sin efecto en el orden | Motivo explícito, nunca «no informado por el backend» | `test_sapi86_*` (PR #48) | PASS en el PR #48 |
| Q-07 | El Modelo D en sí (rendimiento con datos reales) | Con la regla Top 5 encuentra 12 de 82 casos con incendio (14,6 %) | Documento de una página (HU-88) y lectura de las figuras (HU-83) | `tests/test_sapi83_evaluacion_modelo_d.py` (57 casos) | Medido; ver `docs/hito3/hu83_lectura_figuras.md` |

## 3. Cómo se corrige el comportamiento ante una falla crítica

1. **Detectarla:** cada llamada al ML deja un evento `ml_predict` con `request_id`, `ml_responded`, `ml_http_status` y `outcome`. Lo verifica `RankingEndpointIntegrationTests.logsEachMlCall`.
2. **Contenerla:** el panel nunca muestra un ranking parcial ni inventado (F-07). El usuario ve el error y la hora del último dato válido.
3. **Recuperarse:** el backend no se reinicia. Cuando el ML o la base vuelven, la siguiente consulta funciona sin intervención. Para la base, esto queda pendiente de F-08.
4. **Revertir:** el cambio A4 (dos workers ML) tiene un rollback ensayado (SAPI-74).

## 4. Pendiente

- F-08: integrar el cambio de D-05 con su preinscripción (HU-75).
- D-04: lo decide Daniel.
- HU-91.T3 y HU-91.V: las 3 tareas guiadas con La Cruz. Las metas de tiempo y de clics siguen pendientes de Daniel.

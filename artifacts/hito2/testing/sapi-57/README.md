# SAPI-57 — Evidencia de la integración Spring Boot ↔ servicio ML (PR-2)

| Campo | Valor |
|---|---|
| HU | SAPI-57 (S2-04) Integrar Spring Boot con el microservicio FastAPI |
| Rama | `feat/SAPI-57-ranking-ml-client` |
| SHA de código | `569c8988ed648d7185a98d70fc123715f2eab5fd`; los commits posteriores son solo de evidencia |
| Fecha | 2026-10-10 (UTC) |
| Entorno | Sandbox Linux; OpenJDK 21.0.12.1; Spring Boot 4.1.1; Python 3.14.6 con FastAPI 0.141.1 y uvicorn 0.53.0; servicio ML en `SAPI_REPRODUCIBILITY_MODE=1` |
| Gate | `../../ci/gate/569c898/`: `freeze`, `python` y `backend-unit` en PASS |

## Criterios de aceptación

| CA | Verificación | Evidencia | Estado |
|---|---|---|---|
| CA1. Spring consume FastAPI (RestClient aprobado por Daniel, 2026-10-10) | `RankingEndpointIntegrationTests`: `POST /predict` por HTTP con cuerpo `{}` o `{"forecast_time": …}` sin modificar. `RankingRealMlServiceTests`: lo mismo contra FastAPI real | surefire del gate; `real_ml_surefire/` | PASS |
| CA2. Timeout y errores con respuesta controlada | Ver la lista debajo de esta tabla | surefire; `backend_ml_real_run.txt` §4–§9 | PASS |
| CA3. `GET /api/v1/ranking` con las 50 celdas ordenadas | Ver la lista debajo de esta tabla | surefire; `backend_ml_real_run.txt` §2–§3 | PASS |
| CA4. Integración Spring ↔ FastAPI (mock o real) | Mock: stub HTTP en 127.0.0.1. Real: 4/4 contra el servicio FastAPI | `real_ml_surefire/`, `real_ml_mvn_console.txt`, `backend_ml_real_run.txt` | PASS |
| CA5. Logs estructurados de cada llamada | Un único `ml_predict` en cada ruta: éxito, cada error y error inesperado. Lleva `request_id`, `ml_responded`, `ml_http_status`, `ml_latency_ms`, `outcome` y trazabilidad, y sale en JSON con `logstash` | surefire; `ml_predict_log_sample.jsonl` | PASS |

**CA2, qué se verificó:**
- Respuestas del ML mapeadas a 502/503/422/500.
- Timeouts antes y después de los headers → 504.
- Corte de conexión a mitad del cuerpo → 503.
- Cuerpo de exactamente 1 MiB → aceptado; 1 MiB + 1 byte → 502, con cualquier status.
- `forecast_time` que no es RFC 3339 → 422 sin llamar al ML, y `%ZZ` → 422.
- ML caído → 503.
- Timeouts sin unidad → segundos.
- Cada cuerpo de error se valida contra `backend.v0.yaml`.

**CA3, qué se verificó:**
- `RankingResultValidatorTests` prueba cada invariante con su motivo exacto (50 celdas VP-001..VP-050, rank 1..50, score en [0, 1] y no creciente, `display_rank` por el método min, `tie_group_size`), RFC 3339 y codificación UTF-8.
- La respuesta 200 son los mismos bytes del ML, probado con un cuerpo que una re-serialización cambiaría.
- La respuesta cumple `backend.v0.yaml` → `RankingResult` (networknt, dialecto OpenAPI 3.0, siguiendo `$ref`).

La HU sigue abierta hasta la revisión independiente, el merge y el cambio en Jira, que hace Daniel (DoD 7 y 9). Jira no se modificó.

## Tests ejecutados

| Suite | Resultado |
|---|---|
| `mvnw -B verify` (gate, `backend-unit`) | 118 tests, 0 fallas, 4 omitidos (opt-in contra el ML real, sin `SAPI_IT_ML_BASE_URL`) |
| `RankingRealMlServiceTests` contra FastAPI real (clon del SHA) | 4/4 PASS: mismos bytes que `POST /predict`, `forecast_time` anterior, offset `+03:00` enviado como `%2B`, 503 propagado |
| pytest completo (gate, `python`) | 1720 passed, 114 skipped, cobertura 84,56 % |

## Mutation testing (`mutation_testing.json`)

Cada mutación se aplicó al código de `569c898`. Luego se corrieron `Ranking*Tests,MlService*Tests` y se revirtió la mutación, verificando con `git diff --exit-code`.

| ID | Mutación | Resultado |
|---|---|---|
| M9 | El cuerpo del ML se re-serializa con Jackson | KILLED |
| M10 | Sin límite superior del score | KILLED |
| M10b | Sin límite inferior del score | KILLED |
| N1 | Sin la regla de plazo vencido (corte del cuerpo siempre 503) | KILLED |
| N2 | Sin cerrar el stream de un cuerpo mayor a 1 MiB | KILLED |
| N3 | Ignora si se envió `forecast_time` (422 del ML) | KILLED |
| N4 | RFC 3339 con `find()` en vez de `matches()` | KILLED |
| N5 | Sin rechazar bytes nulos (UTF-16/32) | KILLED |
| N5b | Sin exigir `{` como primer byte (BOM) | KILLED |
| N6 | Sin `@ExceptionHandler` para `%ZZ` | KILLED |
| N7 | Sin `@DurationUnit` (sin unidad = milisegundos) | KILLED |
| N8 | Sin capturar `RuntimeException` en `rank()` | KILLED |
| N9 | `ml_http_status` siempre presente | KILLED |
| N10 | Cuerpo mayor a 1 MiB revisado solo en el 200 | KILLED |

Las mutaciones M1–M8 ya habían quedado muertas en la revisión anterior.

## Ejecución real (`backend_ml_real_run.txt`)

El jar construido desde el clon de `569c898` corrió contra el servicio ML real, con `LOGGING_STRUCTURED_FORMAT_CONSOLE=logstash`.

| § | Caso | Resultado |
|---|---|---|
| 1 | `GET /health` | 200 `{"status":"UP"}` |
| 2 | `GET /api/v1/ranking` | 200; cuerpo idéntico byte a byte a `POST /predict` (5.333 bytes, mismo sha256); 50 celdas; `relative_rank`; `scientific_model_validation=false` |
| 3 | `forecast_time` con offset `+03:00` (`%2B`) | 200, igual a `POST /predict` con el mismo valor; evaluado como 2026-08-31T18:00:00Z |
| 4 | `forecast_time` futuro | 503 `prototype_unavailable` (propagado) |
| 5–6 | Sin zona horaria o sin segundos | 422 `invalid_request` sin llamar al ML |
| 7 | `%ZZ` | 422 `invalid_request` con `X-Request-Id`, sin errores en el log |
| 8 | ML caído | 503 `upstream_unavailable` |
| 9 | `SAPI_ML_READ_TIMEOUT=1` (sin unidad = 1 s) frente a un scoring de ~2 s | 504 `upstream_timeout` en 1,08 s |

`ml_predict_log_sample.jsonl` contiene solo los eventos `ml_predict` y `ranking_request_rejected` de esas tres instancias. Ninguna instancia registró líneas ERROR. El score es un ranking relativo entre las 50 celdas, no una probabilidad calibrada.

## Saneamiento y redacción

Las rutas locales pasan a marcadores entre corchetes. Se quitan las líneas con las opciones de la JVM del sandbox (proxy), el bloque `<properties>` de surefire (usuario, home y proxy) y el `hostname`. No se incluyen líneas de arranque con rutas ni usuario.

El grep de redacción (usuario y equipo de Windows, rutas personales y del sandbox, carpetas sincronizadas, dominio de Jira, proxy, contraseñas, tokens y API keys) sobre esta carpeta y `../../ci/gate/569c898/` resultó vacío.

## Reproducir

```bash
SAPI_REPRODUCIBILITY_MODE=1 uvicorn services.ml_api.main:app --port 8000
cd services/backend && ./mvnw -B verify                                         # suite completa
SAPI_IT_ML_BASE_URL=http://127.0.0.1:8000 ./mvnw -B test -Dtest=RankingRealMlServiceTests
./mvnw -q -DskipTests package && LOGGING_STRUCTURED_FORMAT_CONSOLE=logstash java -jar target/backend-0.0.1-SNAPSHOT.jar
```

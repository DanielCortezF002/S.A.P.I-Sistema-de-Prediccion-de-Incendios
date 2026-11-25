# k6 · RNF-03 a nivel API · 1 VU · 25-11-2026

> Prueba complementaria a nivel API (k6), ejecutada en el computador local, no en ambiente desplegado. No es la medición de KPI-03 (latencia visible en el navegador, que sigue congelada) y no acredita capacidad bajo concurrencia.

## Veredicto: NO CUMPLE

Hubo **1 fallo de 30** (iteración 5, HTTP 503) y el **p95 por rango más cercano es 8.604,2 ms**, por encima de 2.000 ms. k6 interpola y da 7.135,4 ms. Cumplir exigía las dos condiciones. La muestra fallida queda como está: no se reemplaza ni se descarta.

Comprobé estas cifras contra los archivos de la corrida y coinciden con las del Director.

## Estado de cierre (Director, 25-11)

- **Ejecutada.** Una sola corrida. La evidencia está en `4084a0e` (corrida, crudos y este reporte) y `173a5e2` (extractos de logs del 503). Resultado **NO CUMPLE**: 30 muestras, un HTTP 503 y p95 por rango más cercano de 8.604,2 ms. No se repite k6 ni se cambian parámetros.
- **Es una prueba complementaria de API.** KPI-03 (latencia visible en el navegador) mantiene su estado propio; esta corrida no lo reemplaza.
- **La causa de la muerte del proceso de uvicorn sigue siendo desconocida.** Los logs acreditan el incidente y la vuelta posterior a respuestas 200. No demuestran la causa raíz.

## Origen de los parámetros

RNF-03, `docs/requerimientos.md` en `9657bad` (sellado el 23-11-2026), sacado con `git show 9657bad:docs/requerimientos.md`:

- Línea 24: fila RNF-03 de la tabla («Latencia visible p95 por escenario», Must).
- Línea 67 (§3.2, Entorno): «una única carga en la máquina (sin cargas concurrentes); un solo usuario».
- Línea 69 (§3.2, Medida de respuesta): un calentamiento fuera de las muestras; 30 rondas; «p95 por rango más cercano (posición 29 de 30)»; «fallos y timeouts cuentan como +∞ y no se reemplazan»; «cero fallos» para declarar cumplimiento; «no acredita capacidad bajo concurrencia».

El RNF habla de latencia visible en el panel. Aquí se aplica su protocolo a `GET /api/v1/ranking` del backend. Es una adaptación, no la medida del RNF.

## Condiciones

| Dato | Valor |
|---|---|
| Fecha | 25-11-2026 |
| Inicio de la corrida | 11:54:02 UTC (08:54:02 Chile) |
| Calentamiento | 11:54:04 UTC (08:54:04 Chile), 1 iteración, 200, 5,79 s. No entra en las muestras |
| Medición | Desde 11:54:12 UTC (08:54:12 Chile) hasta 11:56:40 UTC (08:56:40 Chile) |
| Stack | Proyecto Compose `sapi-h3-518c0b5`, código `518c0b58e6b229317f51b1da56ac23346dc2ef74`, backend `127.0.0.1:18080` (desde k6: `host.docker.internal:18080`) |
| Image IDs | backend `738e2f76e7ed`, ml-api `54d486969316`, web-v2 `43e4b8116802`, db-v2 `3f4a5d48e0be` (`postgis/postgis:15-3.4`) |
| SHA del repo al correr | `2a9e2781b30f0bbb5fda0b07b57f3e5c33114b1a` |
| Hardware | AMD Ryzen AI 7 350 (8 núcleos, 16 hilos), 31 GB de RAM, Windows 11 Home 10.0.26200, Docker 29.9.2 |
| Herramienta | `grafana/k6:0.54.0` en un contenedor desechable (`docker run --rm`) |
| Carga | N = 1 VU, 30 iteraciones seguidas sin pausa (`per-vu-iterations`), timeout de 90 s por petición |
| Umbral | p95 por rango más cercano ≤ 2.000 ms **y** 0 fallos |
| Luz verde | Daniel, 25-11 08:50 Chile, vía Director (task_d961225e01aa) |

## Resultado (fase de medición, 30 muestras)

| Medida | Valor | Fuente |
|---|---|---|
| Muestras | 30 (29 con 200 y 1 con 503) | `medicion-muestras.json` |
| Fallos | **1**: iteración 5, HTTP 503, duró 6.636,3 ms | `analisis-rango-mas-cercano.json` → `fallos_detalle` |
| p50 por rango más cercano (posición 15, el fallo cuenta como +∞) | 4.502,5 ms | íd. |
| **p95 por rango más cercano** (posición 29, el fallo cuenta como +∞) | **8.604,2 ms** | íd. |
| Máximo con el fallo como +∞ | No es finito, así que queda `null` en el JSON (`max_ms_nota`). La corrida no cumple | íd. |
| Máximo entre las 29 respuestas 200 | 8.604,2 ms (iteración 13) | íd. → `max_ms_respuestas_200` |
| Mínimo | 4.221,6 ms | íd. |
| k6, `http_req_duration{endpoint:ranking}` (interpolado; incluye el 503 como 6.636,3 ms) | min 4.221,6, mediana 4.516,0, media 4.879,0, p90 5.508,5, **p95 7.135,4**, máx 8.604,2 ms, n = 30 | `medicion-summary-export.json` |
| k6, `http_req_failed` | 3,33 % (1 de 30) | íd. |
| k6, umbrales | Los dos se cruzaron; k6 salió con código 99 | `medicion-consola.txt` |
| `checks` | 87 de 90 (los tres checks fallan en la iteración del 503) | íd. |

El veredicto usa el p95 por rango más cercano, como pide el RNF. Con el fallo contado como +∞, la posición 29 de 30 es la respuesta 200 más lenta, de 8.604,2 ms. Sin ningún fallo, el p95 ya pasaría de 2.000 ms: la respuesta 200 más rápida tardó 4.221,6 ms.

Al reescribir el análisis cambió una cosa: antes el JSON decía `"max_ms": Infinity`, que no es JSON válido. Ahora dice `"max_ms": null` y trae `max_ms_nota`, `max_ms_respuestas_200`, `n_respuestas_200` y `fallos_detalle`. Se regeneró con `py -I analizar_rnf03.py corrida-rnf03-1vu-20261125T115402Z`, que solo lee las muestras ya guardadas. Las muestras, los estados y el p95 no cambiaron, y el archivo pasa `json.load`.

## Qué devolvió el 503

Para averiguarlo usé solo lo que ya estaba: la consola, las muestras y `docker logs --timestamps --since 2026-11-25T11:54:02Z --until 2026-11-25T11:56:41Z` de los cuatro contenedores de `sapi-h3-518c0b5`. Además leí, también en solo lectura, el log completo del ml-api, `docker inspect` de ese contenedor y `docker ps`. No reinicié nada.

Las horas siguientes están en UTC:

| Hora | Contenedor | Línea del log |
|---|---|---|
| 11:54:31.811 | ml-api | Último `POST /predict` 200 antes del fallo (iteración 4) |
| 11:54:37.320 | ml-api | `INFO: Waiting for child process [8]` |
| 11:54:38.469 | backend | `WARN … ml_predict request_id=007edb76-1e3e-4497-88ce-21251dd6bf2e … ml_responded=false ml_latency_ms=6625 outcome=upstream_unavailable backend_http_status=503` |
| 11:54:38.474 | k6 | Muestra con `status=503` y 6.636,3 ms (iteración 5) |
| 11:54:38.484 | ml-api | `INFO: Child process [8] died` |
| 11:54:45.149 | ml-api | `Started server process [5663]` … `Application startup complete.` |
| 11:54:46.002 | ml-api | `POST /predict` 200 (iteración 6, 7.543,8 ms; el backend registró `ml_latency_ms=7523`) |

Los extractos de log quedan commiteados junto a la corrida. Se sacaron el 25-11 a las 16:12:55 UTC (ml-api) y 16:12:57 UTC (backend), en solo lectura y de los mismos contenedores que corrieron la prueba: ambos se crearon a las 04:07:26 UTC y no se han recreado. Cada archivo lleva en su cabecera el comando exacto, el nombre y el ID del contenedor y la hora de extracción. El SHA-256 es el del blob en git (LF).

| Archivo | Contenedor | SHA-256 | Líneas que sostienen la atribución |
|---|---|---|---|
| [logs-503-ml-api.txt](corrida-rnf03-1vu-20261125T115402Z/logs-503-ml-api.txt) | `sapi-h3-518c0b5-ml-api-1` (`48aefe903df8`) | `9640caccba01ba89d82a35143e240f3840333fac168c6ab6f27271cd151ef7cc` | 15 (último `/predict` 200 antes del fallo), 17 (`Waiting for child process [8]`), 18 (`Child process [8] died`), 19 (`Started server process [5663]`), 23 (primer `/predict` 200 después) |
| [logs-503-backend.txt](corrida-rnf03-1vu-20261125T115402Z/logs-503-backend.txt) | `sapi-h3-518c0b5-backend-1` (`1b3e510e8083`) | `4da560973080a415fa6f16ea05dc403884b034d1c5f1373da636df6076210e6e` | 12 (iteración 4, 200), **13** (`ml_responded=false … outcome=upstream_unavailable backend_http_status=503`), 14 (iteración 6, 200) |

Comando: `docker logs --timestamps --since 2026-11-25T11:54:02Z --until 2026-11-25T11:56:40Z <contenedor> 2>&1`.

| Afirmación | Clasificación |
|---|---|
| Quien respondió el 503 fue el **backend**, con `outcome=upstream_unavailable`, porque el ml-api no respondió (`ml_responded=false`). No hay gateway entre k6 y el backend | **Verificado hoy** ([logs-503-backend.txt](corrida-rnf03-1vu-20261125T115402Z/logs-503-backend.txt), línea 13) |
| Mientras corría esa petición murió un **proceso hijo de uvicorn del ml-api** (PID 8, uno de los 2 workers). El supervisor levantó otro (PID 5663) y desde la iteración 6 todo volvió a 200 | **Verificado hoy** ([logs-503-ml-api.txt](corrida-rnf03-1vu-20261125T115402Z/logs-503-ml-api.txt), líneas 17–19 y 23) |
| El contenedor no se reinició: `RestartCount=0`, `OOMKilled=false`, sin límite de memoria (`Memory=0`), y `docker ps` lo sigue mostrando Up y healthy. Su comando es `uvicorn services.ml_api.main:app --host 0.0.0.0 --port 8000 --workers 2` | **Verificado hoy** (`docker inspect`, `docker ps`) |
| En las ~8 h de log del ml-api, desde que arrancó a las 04:07:38 UTC, esta es la única muerte de un hijo | **Verificado hoy** (grep del log completo) |
| El log no explica **por qué** murió el hijo: no hay traceback, `MemoryError` ni `Killed`. Una hipótesis: el supervisor multiproceso de uvicorn reinicia un hijo que no contesta su chequeo de vida a tiempo, y aquí el hijo estaba ocupado con un `/predict` de más de 6 s. No se comprobó | **Pendiente.** Con lo disponible no se puede saber |
| La versión de uvicorn fijada en `requirements-dev.txt` de `518c0b5` es 0.53.0. No revisé cuál está instalada en la imagen (no ejecuté nada dentro del contenedor) | Versión fijada: **verificado hoy** (`git grep`). Versión instalada: **pendiente** |
| El cuerpo de la respuesta 503 no quedó guardado: k6 con `--out json` no registra cuerpos | **No se puede saber** con lo disponible |

## Una única carga en la máquina

Según la cabecera (`00-cabecera.txt`), el `docker ps` tomado al iniciar mostraba solo los 4 contenedores de `sapi-h3-518c0b5` y los 4 de `sapi`. No había contenedores de Trivy, de k6 ni de builds. El stack `sapi` estaba arriba, sin tráfico declarado. Esto es **histórico**: lo registró el worker anterior a las 11:54:02 UTC.

Registro previo a la corrida: el mensaje de Orca `msg_aa7fe01c40e6`, enviado al coordinador antes del inicio (anuncia el lanzamiento para las 11:54 UTC). Dice, textual: «Verificado 11:51 UTC: solo los 8 contenedores de sapi y sapi-h3 en marcha, sin Trivy, builds, pruebas ni recorridos». La salida de esa revisión de contenedores y procesos **no se archivó** en el repositorio: el mensaje declara el resultado, pero no lo prueba.

**Limitación que se mantiene:** fuera de lo que muestra el `docker ps` de la cabecera, la ausencia de otra carga en el host no tiene evidencia archivada. No se reconstruye después de la corrida.

## Archivos

- [rnf03_api_1vu.js](rnf03_api_1vu.js): el guion k6.
- [correr_rnf03_api_1vu.sh](correr_rnf03_api_1vu.sh): el lanzador, que hace una sola corrida.
- [analizar_rnf03.py](analizar_rnf03.py): calcula el rango más cercano desde las muestras crudas.
- [corrida-rnf03-1vu-20261125T115402Z/](corrida-rnf03-1vu-20261125T115402Z/): cabecera, consola, muestras crudas (`--out json`) y `summary-export` de las dos fases, más `analisis-rango-mas-cercano.json`.

No se volvió a correr k6 y no se tocaron contenedores. No se corrió pytest.

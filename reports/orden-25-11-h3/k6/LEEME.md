# k6 · orden 25-11 · `sapi-h3-518c0b5`

- Fecha de preparación: 2026-11-25. SHA del código: `518c0b58e6b229317f51b1da56ac23346dc2ef74`.
- Hardware: AMD Ryzen AI 7 350 (8 núcleos, 16 hilos), 31 GB de RAM, Windows 11 Home 10.0.26200; Docker 29.9.2.
- Ejecutado en el computador local, no en ambiente desplegado.
- **Estado: LISTO, NO EJECUTADO. N de VUs ejecutados: 0.** Cada corrida necesita luz verde explícita y propia del Director (sesión SUS de Daniel en curso).

## Archivos

- [sapi_h3_carga.js](sapi_h3_carga.js): guion k6 con 4 escenarios seleccionables.
- [Invoke-K6Corrida.ps1](Invoke-K6Corrida.ps1): lanza **una** corrida; exige `-LuzVerde "<referencia del mensaje>"`, escribe cabecera (fecha, SHA, imágenes, hardware, VUs, frase de alcance), consola, `resumen.json` y `SHA256SUMS` en `corrida-<escenario>-<UTC>/`.

## Escenarios

| Escenario | VUs | Duración | Endpoint | Pausa |
|---|---|---|---|---|
| `humo` | 1 | 5 iteraciones (máx. 3 min) | `/health` y `/api/v1/ranking` | 1 s |
| `l1` | 2 constantes | 3 min | `/api/v1/ranking` | 1 s |
| `l2` | 5 constantes | 3 min | `/api/v1/ranking` | 1 s |
| `rampa` | 0 → 10 → 0 | 2 min subida + 2 min + 30 s bajada | `/api/v1/ranking` | 1 s |

Métricas: `http_req_duration` (min, mediana, media, p90, p95, p99, máx.) por endpoint, `http_req_failed`, `checks` (200, 50 celdas, `score_semantics=relative_rank`), iteraciones/s y `ranking_ms`.

Umbrales **propuestos, no adoptados**: p95 del ranking < 10 000 ms (`-P95Ms`), errores < 1 %, checks > 99 %. Referencia: hoy, sin carga pero con Trivy en paralelo, el ranking tardó 15,4 s en frío y `ml_predict` 9,4–27,1 s; con esas cifras el umbral de 10 s puede fallar ya en `humo`. Hay que fijarlo antes de leer PASS/FAIL.

## Barreras

- `BASE_URL` por defecto `http://host.docker.internal:18080` (stack h3). Si apunta a `:8080`, `:8000` o `:8501` (stack `sapi`), el guion aborta salvo `-e PERMITIR_STACK_SAPI=si`, que no debe usarse en esta orden.
- No crea volúmenes ni toca contenedores; solo `docker run --rm grafana/k6:0.54.0`.

## Validación hecha sin carga

`k6 inspect` (solo analiza el guion, no envía peticiones) devolvió para cada escenario el ejecutor y los VUs de la tabla, y la barrera abortó con `BASE_URL=http://host.docker.internal:8080` (verificado hoy).

## Orden sugerido, cada uno con su luz verde

1. `.\Invoke-K6Corrida.ps1 -Escenario humo -LuzVerde "<ref>"`
2. `l1`, 3. `l2`, 4. `rampa`, solo si el anterior no dejó errores y el Director lo autoriza.

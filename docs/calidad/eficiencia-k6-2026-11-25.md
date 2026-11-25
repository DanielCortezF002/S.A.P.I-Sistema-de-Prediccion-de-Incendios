# C4 · Eficiencia · k6 contra `GET /api/v1/ranking` · 25-11-2026

> **Esto no es KPI-03.** KPI-03 es la latencia visible en Edge, con su propio protocolo sellado y congelado (`docs/objetivos.md` §5.2 en `9657bad`). Esta prueba mide la API del backend bajo concurrencia; sus cifras no se comparan con la meta de 2.000 ms ni se presentan como latencia de la interfaz.

- Stack: `sapi-h3-518c0b5`, código `518c0b58e6b229317f51b1da56ac23346dc2ef74`, backend en `127.0.0.1:18080`. El ml-api corre con `--workers 2` (`docker-compose.yml`).
- Hardware: AMD Ryzen AI 7 350 (8 núcleos, 16 hilos), 31 GB de RAM, Windows 11 Home 10.0.26200; Docker 29.9.2. Ejecutado en el computador local, no en ambiente desplegado.
- Herramienta: `grafana/k6:0.54.0` en contenedor desechable.

## 1. Declaración (commiteada antes de correr)

| Parte | Valor |
|---|---|
| Fuente | k6, **N = 2 usuarios virtuales** constantes |
| Estímulo | Cada VU pide `GET /api/v1/ranking` (sin `forecast_time`), espera la respuesta y hace una pausa de 1 s |
| Entorno | Stack `sapi-h3-518c0b5` con sus 4 servicios arriba. El stack `sapi` sigue arriba y sin tráfico. Ninguna otra carga en la máquina (sin Trivy, sin recorridos de Edge, sin builds) |
| **Calentamiento** | 1 VU, 2 peticiones secuenciales, en una invocación separada de k6. **Se guarda y no entra en las métricas.** Si no termina con 2 de 2 respuestas 200 con 50 celdas y `score_semantics=relative_rank`, no se mide y la corrida queda NO_EVALUABLE |
| **Duración de la medición** | 3 min con 2 VUs constantes; las peticiones en vuelo al terminar tienen hasta 90 s para cerrar (`gracefulStop`) |
| Timeout | 90 s por petición. El backend corta antes: su read-timeout hacia el ML es 60 s (devuelve 504). Los timeouts y los 5xx cuentan como errores; no se descartan ni se reemplazan |
| Medida | p95 de `http_req_duration` del ranking y tasa de errores (`http_req_failed`) en la fase de medición. También se informan mínimo, mediana, media, p90, p99, máximo, número de peticiones y `checks` |
| **Criterio** | **Cumple** si p95 ≤ 20.000 ms **y** errores < 1 %. Si falta uno, no cumple. No se ajusta después de medir |
| Corridas | Una. No se repite para mejorar el resultado. Si se anula (calentamiento no ok o carga ajena), se dice y se pide otra luz verde |

Por qué estos valores (para que se juzguen antes de ver resultados):

- **N = 2** coincide con los 2 procesos de uvicorn del ml-api: cada VU puede tener un proceso. Con más VUs habría cola en el ML, que es otro escenario (punto de quiebre, sección 2 de fiabilidad).
- **20.000 ms** lo propone Plataforma hoy. No es una meta adoptada del proyecto: no hay ninguna meta de latencia de la API en `docs/requerimientos.md` ni en `docs/objetivos.md` (`9657bad`). Referencia histórica (25-11, 01:06–01:29, con Trivy en paralelo): un ranking en frío tardó 15,4 s y `ml_predict` 9,4–27,1 s. Con esas cifras **el umbral puede no cumplirse**; se fija igual antes de medir. Si el Director o Daniel quieren otro umbral, debe cambiarse en este archivo y commitearse antes de la corrida.

Guion y lanzador: [k6_ranking.js](evidencia/2026-11-25-eficiencia/k6_ranking.js), [Invoke-K6Eficiencia.ps1](evidencia/2026-11-25-eficiencia/Invoke-K6Eficiencia.ps1). Validados hoy solo con `k6 inspect` (no envía peticiones): la fase `calentamiento` da `shared-iterations`, 1 VU, 2 iteraciones; la fase `medicion` da `constant-vus`, 2 VUs, 3 min, con los umbrales `p(95)<=20000` y `rate<0.01`. Con `BASE_URL=http://host.docker.internal:8080` el guion aborta (barrera contra el stack `sapi`).

## 2. Estado

**NO EJECUTADO. N de VUs ejecutados: 0.** Espera luz verde explícita (vía SAPI-Plataforma, de Daniel o del Director). Comando cuando llegue:

```powershell
.\docs\calidad\evidencia\2026-11-25-eficiencia\Invoke-K6Eficiencia.ps1 -LuzVerde "<referencia del mensaje>"
```

## 3. Resultado

Pendiente de la corrida.

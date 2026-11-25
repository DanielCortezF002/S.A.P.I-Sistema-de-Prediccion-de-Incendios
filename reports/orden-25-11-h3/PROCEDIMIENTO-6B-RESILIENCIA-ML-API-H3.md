# Paso 6b: resiliencia de ml-api sobre `sapi-h3-518c0b5` (pasos PowerShell)

- Fecha de preparación: 2026-11-25 (America/Santiago).
- SHA del código: `518c0b58e6b229317f51b1da56ac23346dc2ef74`, rama local `DanielCortezF002/h3-518c0b5-verificacion`.
- Hardware: AMD Ryzen AI 7 350 (8 núcleos, 16 hilos), 31 GB de RAM, Windows 11 Home 10.0.26200, Docker 29.9.2 (16 CPU y 15,1 GiB asignados al motor).
- Ejecutado en el computador local, no en ambiente desplegado.
- **Estado: preparado, NO ejecutado.** Lo corre Daniel a mano, en una ventana acordada con Dirección y UX, fuera de cualquier medición KPI y fuera de la sesión SUS.

Este documento reemplaza, solo para el stack h3, a `PROCEDIMIENTO-6B-RESILIENCIA-ML-API.md` (24-11, escrito para `sapi-kpi03-a3d08ee`). Al final está el cotejo línea por línea.

## Qué se toca y qué no

- Solo el contenedor `sapi-h3-518c0b5-ml-api-1`, con `docker stop` y `docker start` sobre el mismo ID.
- No se toca el stack `sapi` (puertos 8501, 8080, 8000, 5432) ni sus volúmenes.
- No se reconstruye, no se recrea y no se borra nada: nada de `up --build`, `down`, `rm`, `prune` ni `-v`.
- Si algo no coincide con lo esperado, **detente**, anota lo que viste y avisa al Director.

## Valores de referencia (verificados hoy, 2026-11-25 ~01:10 Santiago)

| Elemento | Valor esperado |
|---|---|
| Proyecto Compose | `sapi-h3-518c0b5` |
| Contenedores | `sapi-h3-518c0b5-web-v2-1`, `-backend-1`, `-ml-api-1`, `-db-v2-1` |
| Imagen web | `sha256:43e4b8116802bbeed355a7f356602a33a2c6de4f3c9551a582a06d823612eeda` |
| Imagen backend | `sha256:738e2f76e7eda6c4056d4070e967104ef9ffb7986b552653cd353570b80be369` |
| Imagen ml-api | `sha256:54d48696931638db3de0180128487999ba2af9712336f6e77b8949bf2a8915dd` |
| Imagen db | `sha256:3f4a5d48e0be9580ed70ed618cd039ce57bbb2dd113053d3836e28513f1f87cd` |
| Web | `http://127.0.0.1:18501/` (health `/_stcore/health`) |
| ML | `http://127.0.0.1:18000/health` |
| Backend | `http://127.0.0.1:18080/health` y `http://127.0.0.1:18080/api/v1/ranking` |

Si alguien reconstruyó el stack h3 después de esta fecha, las imágenes cambian: el paso 2 lo detecta y debes detenerte.

## Estado inicial y cómo volver a él

El estado inicial es: los 4 contenedores `Up`; backend, ml-api y db `healthy`; web sin healthcheck. **La única acción que lo altera es el paso 4.** Para volver al estado inicial desde cualquier punto basta con:

```powershell
docker start sapi-h3-518c0b5-ml-api-1
```

y esperar `healthy` (paso 6). Los demás pasos solo leen.

---

## Paso 0. Carpeta de evidencia y transcript

Abre **PowerShell** (no CMD) y pega:

```powershell
$P  = 'sapi-h3-518c0b5'
$ML = "$P-ml-api-1"
$ev = "C:\SAPI-EVIDENCIA-6B-H3-$([DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ'))"
New-Item -ItemType Directory -Path $ev | Out-Null
Set-Location $ev
Start-Transcript -Path "$ev\00-transcript.txt"
[DateTime]::UtcNow.ToString('o')
```

- **Esperado:** `Transcript started, output file is C:\SAPI-EVIDENCIA-6B-H3-...\00-transcript.txt` y la hora UTC.
- **Volver al estado inicial:** no hace falta; solo crea una carpeta. Si quieres deshacerlo: `Stop-Transcript` y borra esa carpeta a mano.

## Paso 1. Confirmar el SHA del código

```powershell
git -C "C:\Users\danie\orca\workspaces\SAPI\soapfish" rev-parse HEAD
```

- **Esperado (PASS):** exactamente `518c0b58e6b229317f51b1da56ac23346dc2ef74`. Si el worktree ya tiene commits de informes encima, usa en su lugar `git -C "C:\Users\danie\orca\workspaces\SAPI\soapfish" merge-base --is-ancestor 518c0b5 HEAD; $LASTEXITCODE` (debe dar `0`) y `git -C "C:\Users\danie\orca\workspaces\SAPI\soapfish" diff --stat 518c0b5 HEAD -- app services Dockerfile.web Dockerfile.ml-api requirements.txt requirements-dev.txt` (debe salir vacío).
- **FALLA:** otro SHA o diferencias en código. No sigas.
- **Volver al estado inicial:** solo lectura.

## Paso 2. Identidad de contenedores e imágenes

```powershell
docker compose -p $P ps
$esperado = @{
  'web-v2'  = 'sha256:43e4b8116802bbeed355a7f356602a33a2c6de4f3c9551a582a06d823612eeda'
  'backend' = 'sha256:738e2f76e7eda6c4056d4070e967104ef9ffb7986b552653cd353570b80be369'
  'ml-api'  = 'sha256:54d48696931638db3de0180128487999ba2af9712336f6e77b8949bf2a8915dd'
  'db-v2'   = 'sha256:3f4a5d48e0be9580ed70ed618cd039ce57bbb2dd113053d3836e28513f1f87cd'
}
$inicial = @{}
foreach ($n in 'web-v2','backend','ml-api','db-v2') {
  $l = docker inspect --format '{{.Id}} {{.Image}} {{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{end}}' "$P-$n-1"
  $inicial[$n] = $l
  $img = ($l -split ' ')[1]
  "{0,-8} {1}  imagen_ok={2}" -f $n, $l, ($img -eq $esperado[$n])
}
$mlId = docker inspect --format '{{.Id}}' $ML
if ($LASTEXITCODE -ne 0 -or $mlId -notmatch '^[0-9a-f]{64}$') { throw 'ID de ML no confirmado' }
"ML_ID=$mlId"
```

- **Esperado (PASS):**
  - `docker compose ps` lista 4 servicios `Up`; backend, ml-api y db-v2 con `(healthy)`.
  - Las 4 líneas terminan en `imagen_ok=True`.
  - Se imprime `ML_ID=` con 64 caracteres hexadecimales. **Cópialo a un papel o a otra ventana**: es lo que arrancas si se corta la consola.
- **FALLA:** algún `imagen_ok=False`, un servicio caído o `unhealthy`, o el `throw`.
- **Volver al estado inicial:** solo lectura.

## Paso 3. Línea base HTTP

```powershell
foreach ($u in 'http://127.0.0.1:18501/_stcore/health','http://127.0.0.1:18000/health','http://127.0.0.1:18080/health') {
  "== $u"; curl.exe --noproxy '*' --max-time 20 -sS -i $u | Select-Object -First 1; curl.exe --noproxy '*' --max-time 20 -sS $u; ''
}
curl.exe --noproxy '*' --max-time 60 -sS -o "$ev\03-ranking-antes.json" -w "ranking HTTP %{http_code} en %{time_total} s`n" http://127.0.0.1:18080/api/v1/ranking
(Get-Content "$ev\03-ranking-antes.json" -Raw | ConvertFrom-Json).cells.Count
```

- **Esperado (PASS):**
  - web: `HTTP/1.1 200 OK` y `ok`;
  - ML: `HTTP/1.1 200 OK` y `{"status":"ok","model_version":"prototype_model_d_v1"}`;
  - backend: `HTTP/1.1 200` y `{"status":"UP"}`;
  - `ranking HTTP 200 en ... s` y luego `50`.
  - Nota: la primera llamada al ranking tras arrancar tardó 15,4 s hoy (verificado hoy); por eso `--max-time 60`.
- **FALLA:** cualquier código distinto de 200 o un número de celdas distinto de 50.
- **Edge (línea base):** abre `http://127.0.0.1:18501/`, pulsa «Actualizar ranking» en la barra lateral y selecciona una celda. Captura con la hora visible y guárdala como `$ev\03-edge-antes.png`.
- **Volver al estado inicial:** solo lectura.

## Paso 4. Parar ml-api (único paso que altera el estado)

```powershell
$tStop = [DateTime]::UtcNow; $tStop.ToString('o')
docker stop $mlId
if ($LASTEXITCODE -ne 0) { throw 'Docker no confirmó la parada' }
docker inspect --format '{{.Id}} {{.State.Status}}' $mlId
docker compose -p $P ps
```

- **Esperado (PASS):** `docker stop` imprime el ID completo; `docker inspect` muestra ese ID y `exited`; `docker compose ps` lista web, backend y db `Up` y ya no lista ml-api (Compose solo muestra los que corren).
- **FALLA:** error de Docker o que caiga otro servicio. Ve directo al paso 6.
- **Volver al estado inicial:** `docker start $mlId` y paso 6.

## Paso 5. Comportamiento con ml-api parada

```powershell
curl.exe --noproxy '*' --max-time 20 -sS -i http://127.0.0.1:18000/health
curl.exe --noproxy '*' --max-time 20 -sS -i http://127.0.0.1:18080/health
curl.exe --noproxy '*' --max-time 30 -sS -i -w "`ntiempo %{time_total} s`n" http://127.0.0.1:18080/api/v1/ranking | Tee-Object "$ev\05-ranking-caido.txt"
curl.exe --noproxy '*' --max-time 20 -sS -i http://127.0.0.1:18501/_stcore/health | Select-Object -First 1
```

- **Esperado:**
  - ML: `curl: (7) Failed to connect to 127.0.0.1 port 18000` (normal: está parada).
  - Backend `/health`: `HTTP/1.1 200` y `{"status":"UP"}`.
  - Ranking: `HTTP/1.1 503` con `"error_type":"upstream_unavailable"` y el mensaje `El servicio ML no está disponible.` en pocos segundos (el backend usa `SAPI_ML_CONNECT_TIMEOUT=2s`). No debe ser 500 ni agotar los 30 s. Si sale `504`/`upstream_timeout`, anótalo tal cual: no es el resultado esperado.
  - Web: `HTTP/1.1 200 OK`.
- **Edge:** abre una **ventana InPrivate nueva**, carga `http://127.0.0.1:18501/` y pulsa «Actualizar ranking».
  - **PASS:** el panel carga y muestra un aviso controlado. El texto que el código de 518c0b5 asigna al 503 es «El servicio de ranking no está disponible en este momento (HTTP 503).» (`app/utils/backend_client.py:101`). Copia el texto que veas, exacto, al informe. La aplicación sigue navegable: sin traceback, sin pantalla en blanco, sin error genérico de Streamlit y sin un ranking presentado como actual.
  - **FALLA:** traceback, «Error» genérico, la página no carga, o aparece un ranking con datos presentados como actuales.
  - Guarda `$ev\05-edge-caido.png` con el aviso y la hora visibles.
- Restaura en cuanto tengas la captura.
- **Volver al estado inicial:** paso 6.

## Paso 6. Arrancar de nuevo ml-api

```powershell
$tStart = [DateTime]::UtcNow; $tStart.ToString('o')
docker start $mlId
if ($LASTEXITCODE -ne 0) { Write-Error 'Restauración no confirmada: avisa ya al Director y suspende KPI' }
$t = 0; do { Start-Sleep 5; $t += 5; $h = docker inspect --format '{{.State.Health.Status}}' $mlId; "$t s: $h" } until ($h -eq 'healthy' -or $t -ge 180)
docker inspect --format '{{.Id}} {{.Image}} {{.State.Status}} {{.State.Health.Status}}' $mlId
"caida total: {0:N0} s" -f ([DateTime]::UtcNow - $tStop).TotalSeconds
```

- **Esperado (PASS):** `docker start` imprime el mismo ID; el bucle termina en `healthy` antes de 180 s (el healthcheck tiene `start_period: 30s` e `interval: 10s`, así que lo normal es entre 10 y 40 s); la última línea muestra el **mismo ID** que `ML_ID` y la imagen `sha256:54d48696…`. Anota los segundos.
- **FALLA:** no llega a `healthy`, cambia el ID o cambia la imagen. Avisa al Director.
- **Volver al estado inicial:** este paso es la vuelta al estado inicial.

## Paso 7. Recuperación

```powershell
foreach ($u in 'http://127.0.0.1:18501/_stcore/health','http://127.0.0.1:18000/health','http://127.0.0.1:18080/health') {
  "== $u"; curl.exe --noproxy '*' --max-time 20 -sS -i $u | Select-Object -First 1
}
curl.exe --noproxy '*' --max-time 60 -sS -o "$ev\07-ranking-despues.json" -w "ranking HTTP %{http_code} en %{time_total} s`n" http://127.0.0.1:18080/api/v1/ranking
(Get-Content "$ev\07-ranking-despues.json" -Raw | ConvertFrom-Json).cells.Count
$a = Get-Content "$ev\03-ranking-antes.json" -Raw | ConvertFrom-Json
$d = Get-Content "$ev\07-ranking-despues.json" -Raw | ConvertFrom-Json
"mismo inputs_fingerprint: $($a.inputs_fingerprint -eq $d.inputs_fingerprint)"
```

- **Esperado (PASS):** tres `200`; `ranking HTTP 200`; `50`; `mismo inputs_fingerprint: True` (modo reproducible: mismas entradas que antes de la caída).
- **Edge:** en la **misma ventana InPrivate** del aviso, recarga si hace falta, pulsa «Actualizar ranking» y selecciona una celda. **PASS:** vuelve el ranking y el detalle se puede seleccionar. Guarda `$ev\07-edge-recuperado.png`.
- **Volver al estado inicial:** solo lectura.

## Paso 8. Estado final, cierre y hashes

```powershell
docker compose -p $P ps
foreach ($n in 'web-v2','backend','ml-api','db-v2') {
  $l = docker inspect --format '{{.Id}} {{.Image}} {{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{end}}' "$P-$n-1"
  "{0,-8} igual_al_paso_2={1}  {2}" -f $n, ($l -eq $inicial[$n]), $l
}
[DateTime]::UtcNow.ToString('o')
Stop-Transcript
Get-FileHash "$ev\*" -Algorithm SHA256 | ForEach-Object { "$($_.Hash.ToLower())  $(Split-Path $_.Path -Leaf)" } | Set-Content "$ev\SHA256SUMS" -Encoding utf8
Get-Content "$ev\SHA256SUMS"
```

- **Esperado (PASS):** las 4 líneas con `igual_al_paso_2=True`. Si ml-api tenía `healthy` al inicio y vuelve a `healthy`, la línea es idéntica. Después aparece `SHA256SUMS` con un hash por archivo.
- **FALLA:** algún `False`. Anota la diferencia.
- **Volver al estado inicial:** solo lectura.

## Si se corta la consola después del paso 4

Abre otra PowerShell y ejecuta `docker start <ML_ID anotado en el paso 2>` (o `docker start sapi-h3-518c0b5-ml-api-1`). Luego define `$P='sapi-h3-518c0b5'; $mlId='<ML_ID>'; $ev='<carpeta>'` y repite los pasos 6, 7 y 8. Si no se recupera dentro de la ventana, avisa al Director y a UX y mantén KPI suspendido.

## Evidencia (en `$ev`)

| Archivo | Contenido |
|---|---|
| `00-transcript.txt` | Toda la consola, con horas UTC |
| `03-ranking-antes.json`, `03-edge-antes.png` | Línea base |
| `05-ranking-caido.txt`, `05-edge-caido.png` | 503 `upstream_unavailable` y aviso en la UI |
| `07-ranking-despues.json`, `07-edge-recuperado.png` | Recuperación |
| `SHA256SUMS` | Hashes de todo lo anterior |

Veredicto: **PASS** si 1 a 8 dan PASS; **FALLA** si alguno falla; **NO_EVALUABLE** si no se completó (comando rechazado, falta una captura).

---

## Cotejo con el procedimiento del 24-11 (`PROCEDIMIENTO-6B-RESILIENCIA-ML-API.md`)

| Elemento del 24-11 | Contra h3 hoy | Cambio |
|---|---|---|
| Proyecto `sapi-kpi03-a3d08ee` | No aplica: el stack es `sapi-h3-518c0b5` | Reemplazado |
| SHA candidato `a3d08ee…` / app `f8c5218…` | El código es `518c0b5…` (dos commits de lenguaje de UI sobre `f8c5218`) | Reemplazado |
| Imágenes `aa6ec8b7…`, `ca4e83ba…`, `11f420ee…` | Las de h3 son `54d48696…`, `738e2f76…`, `43e4b811…` | Reemplazadas |
| Imagen DB `3f4a5d48…` | Coincide | Sin cambio |
| Puertos 8501/8000/8080 | Son del stack `sapi`; h3 usa 18501/18000/18080 | Corregido: con los puertos antiguos el procedimiento habría probado el stack `sapi` |
| Contenedores `-web-v2-1`, `-db-v2-1` | Mismos sufijos en h3 | Sin cambio |
| 503 `upstream_unavailable` con ML caída | El código de 518c0b5 lo mantiene: `RankingService.java:84-85` y `RankingError.java:14` | Sin cambio; se añade el texto del mensaje y el tiempo |
| «aviso degradado controlado» sin texto concreto | El texto del 503 en la UI está en `app/utils/backend_client.py:101` | Añadido como referencia |
| `docker compose ps` tras la parada | Compose no lista contenedores parados sin `-a` | Aclarado el resultado esperado |
| Comparación final «a ojo» | Se compara con lo guardado en el paso 2 | Automatizado (`igual_al_paso_2`) |
| Sin cómo volver al estado inicial por paso | — | Añadido en cada paso |
| Nota de numeración 6b en `MATRIZ.md` | Sigue pendiente de alinear | Sin cambio (pendiente) |

## Clasificación de afirmaciones

- **Verificado hoy (2026-11-25):** SHA del worktree, image IDs de h3, puertos, health 200 de los tres servicios, ranking 200 con 50 celdas (15,4 s en frío), ubicación en el código del 503 y del texto de la UI.
- **Histórico:** identidades del stack `sapi-kpi03-a3d08ee` y el procedimiento del 24-11.
- **Pendiente:** la ejecución entera. No se paró ni se arrancó ningún contenedor para preparar este documento.

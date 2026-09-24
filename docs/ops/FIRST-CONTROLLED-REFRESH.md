# Primer refresh controlado — gate operacional del 24-09-2026

Procedimiento para una operación humana futura. Este documento no autoriza un
refresh ni un envío. FIRMS son anomalías térmicas satelitales; Model D entrega un
ranking exploratorio, no probabilidades calibradas ni confirmaciones de incendio.
Streamlit se conserva. El bridge local no es el servicio ML de la arquitectura objetivo.

## GO: precondiciones y estado de partida

1. Autorización explícita de Daniel: «AUTORIZO EL PRIMER REFRESH CONTROLADO».
2. Usar `D:\portafolio y seminario\SAPI-71-postmerge-worktree`, con la revisión
   aprobada y los gates de su informe en verde. Nunca el worktree histórico WIP.
3. n8n original despublicado, contenedor detenido, sin ejecuciones pendientes;
   piloto solo manual, sin Telegram. No republicar el workflow original ni conectar
   credenciales a la vista previa. Detener bridge y Streamlit durante publicaciones.
4. Sin otros escritores, ni locks de refresco. No romper locks automáticamente.
5. Credenciales DMC/FIRMS inyectadas al proceso del operador desde su almacenamiento
   privado. No copiarlas al repo, logs ni imágenes. Logging INFO o superior, nunca
   DEBUG ni trazas HTTP detalladas. Revisar solo presencia, nunca imprimir valores.
6. Evidencia inicial de ausencia de CURRENT en ambas fuentes. Si ya existe uno,
   revisar su identidad y usar rollback a versión anterior: no es una primera publicación.

PowerShell (variables de ejemplo completas; registrar el SHA aprobado en evidencia):

```powershell
Set-Location -LiteralPath 'D:\portafolio y seminario\SAPI-71-postmerge-worktree'
$Python = 'D:\portafolio y seminario\S.A.P.I-Sistema-de-Prediccion-de-Incendios-main\.venv\Scripts\python.exe'
# Los status imprimen JSON UTF-8 (FIRMS AL DÍA); sin esto PowerShell 5.1 lo decodifica mal.
$env:PYTHONIOENCODING = 'utf-8'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$Evidence = Join-Path 'D:\portafolio y seminario\SAPI-71-evidence' ('first-refresh-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $Evidence -ErrorAction Stop | Out-Null
git rev-parse HEAD 'HEAD^{tree}' origin/main
git status --short
docker inspect n8n --format '{{.State.Status}}'
docker stop sapi-n8n-bridge sapi-web
& $Python -m src.refresh.firms_refresh status | Tee-Object -FilePath "$Evidence\firms-before.json"
if ($LASTEXITCODE -ne 0) { throw 'FIRMS status falló' }
& $Python -m src.refresh.dmc_refresh status | Tee-Object -FilePath "$Evidence\dmc-before.json"
if ($LASTEXITCODE -ne 0) { throw 'DMC status falló' }
if ((Get-Content "$Evidence\dmc-before.json" -Raw | ConvertFrom-Json).origin -ne 'none') { throw 'No es primera publicación DMC' }
if (Test-Path -LiteralPath 'data/processed/firms/CURRENT.json') { throw 'Ya existe CURRENT FIRMS' }
if (Test-Path -LiteralPath 'data/processed/dmc/.refresh.lock') { throw 'DMC bloqueado' }
if (Test-Path -LiteralPath 'data/processed/firms/.refresh.lock') { throw 'FIRMS bloqueado' }
& $Python -m tools.ops.capture_score --mode reproducible > "$Evidence\repro-before.json"
if ($LASTEXITCODE -ne 0) { throw 'Baseline reproducible indisponible' }
```

El SHA de ranking esperado es
`33c2eacc49bd0cc130928b5bd182ec523e63614f0e3dd97a129a8d4657f231ff`.
Modelo SHA-256: `ac017bef1f42a30ac74ba3e3787368c4418798b2d562adcfba01c923cff2173f`.
Verificar ambos antes de continuar. Guardar inventario y hashes de legacy, versiones,
punteros e insumos topográficos TIF; el hash de topografía de ScoringInputs corresponde
a la tabla derivada, no a todos los bytes TIF.

## GO: publicación explícita, FIRMS primero

Los siguientes comandos están reservados a la operación posterior autorizada.
No ejecutarlos como parte del readiness ni durante un ensayo.

```powershell
& $Python -m src.refresh.firms_refresh refresh *> "$Evidence\firms-refresh.log"
if ($LASTEXITCODE -ne 0) { throw 'ABORT: FIRMS no publicado; no ejecutar DMC' }
& $Python -m src.refresh.firms_refresh status > "$Evidence\firms-after.json"
if ($LASTEXITCODE -ne 0) { throw 'ABORT: FIRMS status' }
& $Python -m src.refresh.dmc_refresh refresh *> "$Evidence\dmc-refresh.log"
if ($LASTEXITCODE -ne 0) { throw 'ABORT: DMC; mantener consumidores detenidos' }
& $Python -m src.refresh.dmc_refresh status > "$Evidence\dmc-after.json"
if ($LASTEXITCODE -ne 0) { throw 'ABORT: DMC status' }
$Dmc = Get-Content "$Evidence\dmc-after.json" -Raw | ConvertFrom-Json
if ($Dmc.origin -ne 'current' -or $Dmc.locked) { throw 'ABORT: puntero/lock DMC' }
```

`status` puede salir con código 0 y `origin=invalid_pointer`: el JSON también es gate.
Verificar FIRMS schema 2, DMC schema 1; hashes, cobertura, ausencia de regresión
temporal y `row_quality` por mes. DMC permite hasta 1% de filas explícitamente nulas
según el contrato integrado; ausentes/no numéricas se rechazan. No flexibilizarlo
durante la operación para forzar una publicación.

`CURRENT.record_count` cuenta filas válidas del almacén versionado. La serie fijada
para scoring contiene legacy ordenado/deduplicado, más filas versionadas válidas con
timestamp estrictamente posterior al máximo legacy. En solapes gana legacy.
Por tanto **no exigir** `len(inputs.meteo_series) == CURRENT.record_count` cuando hay
legacy. Tampoco confundir el hash de manifest del puntero con `dmc_manifest_sha256`
del conjunto completo de entradas fijadas.

## GO: evaluación de la misma captura y observación

```powershell
& $Python -m tools.ops.capture_score --mode operational > "$Evidence\operational-after.json"
if ($LASTEXITCODE -ne 0) { throw 'ABORT: scoring operacional' }
& $Python -m tools.ops.capture_score --mode reproducible > "$Evidence\repro-after.json"
if ($LASTEXITCODE -ne 0) { throw 'ABORT: scoring reproducible' }
$Repro = Get-Content "$Evidence\repro-after.json" -Raw | ConvertFrom-Json
if ($Repro.ranking_fingerprint -ne '33c2eacc49bd0cc130928b5bd182ec523e63614f0e3dd97a129a8d4657f231ff') { throw 'ABORT: fingerprint cambió' }
```

`capture_score` ejecuta exactamente `inputs = capture_scoring_inputs()` y luego
`result = score_current_grid(inputs=inputs)`. Conserva manifest privado y respuesta
serializada de ese mismo resultado. `/score` realiza otra captura: compararla no
demuestra identidad de objeto. El fingerprint operacional puede cambiar, el
reproducible debe conservarse. Confirmar 50 celdas, todos los empates `display_rank=1`,
T vigente, timestamp de la fila usada por el modelo, FIRMS y fingerprint de entradas.

Tras validar los dos stores, arrancar solo el bridge construido desde la revisión
aprobada (`docker compose up -d --build n8n-bridge` desde este checkout); nunca todo
Compose, que incluye servicios legacy. Usar `Invoke-RestMethod` para `/health` y
`/score` en `http://127.0.0.1:8600`. `/health` HTTP 200/degraded no prueba disponibilidad
de datos. Ejecutar una única vista previa manual n8n, sin solapamientos y sin envíos.
Reanudar Streamlit solo tras verificar el resultado. Ningún paso autoriza Telegram.

## Vista previa n8n (piloto sin entrega)

Importar `ops/n8n/controlled-preview.json` en una instancia n8n normal (servidor/editor),
inactivo y sin credenciales. No usar `n8n execute`: en 2.39.10 el comando CLI no inicializa
el módulo Data Tables y falla con «module is disabled»; el servidor normal sí lo inicializa.
El nodo HTTP (fullResponse + texto) entrega el cuerpo en `data`; `policy.js` lo lee ahí.
El piloto exige FIRMS con lag ≤ 3 días respecto de T aunque el servicio acepte hasta 7:
es un filtro operacional conservador, no un umbral científico. `would_notify` es solo
vista previa (`delivery=NOT_SENT`); la deduplicación persiste en la Data Table
`sapi_controlled_preview_v1` y asume ejecuciones manuales sin solapamiento.

## ABORT

Mantener consumidores detenidos ante 65 (datos), 69 (red), 75 (lock), 78
(credenciales), JSON de status inválido, corrupción, cambio del fingerprint
reproducible/modelo/Hito1, T regresivo, grilla distinta de 50, 500 del bridge o fuga.
503 significa indisponibilidad, nunca riesgo bajo ni ausencia de incendios.
No hacer un segundo refresh automático. Guardar salidas sanitizadas e inventario.

## ROLLBACK

No existe transacción conjunta FIRMS/DMC. Recuperar ambos al estado inicial coherente
con consumidores detenidos. Si había versiones anteriores válidas:

```powershell
# Reemplazar los valores por IDs verificados en evidencia; nunca adivinarlos.
& $Python -m src.refresh.dmc_refresh rollback --to $PreviousDmcManifestSha12
if ($LASTEXITCODE -ne 0) { throw 'Rollback DMC rechazado' }
& $Python -m src.refresh.firms_refresh rollback --to $PreviousFirmsVersion
if ($LASTEXITCODE -ne 0) { throw 'Rollback FIRMS rechazado' }
```

En primera publicación DMC no hay CLI `rollback --to baseline`. Se utiliza el helper
revisado y ensayado, únicamente con evidencia inicial `origin=none`, escritores y
consumidores detenidos y el hash de los bytes CURRENT que se van a retirar:

```powershell
$Current = Join-Path (Get-Location).Path 'data/processed/dmc/330007/CURRENT.json'
$ReviewedSha = (Get-FileHash -LiteralPath $Current -Algorithm SHA256).Hash.ToLower()
# Guardar/revisar este hash y copia sanitizada del puntero en evidencia antes de seguir.
& $Python -m tools.ops.dmc_recovery --root 'data/processed/dmc' --expected-sha256 $ReviewedSha --initial-current-absent --consumers-stopped
if ($LASTEXITCODE -ne 0) { throw 'Retorno a ausencia rechazado' }
& $Python -m src.refresh.firms_refresh rollback --to baseline
if ($LASTEXITCODE -ne 0) { throw 'Rollback FIRMS rechazado' }
```

El helper toma el mismo lock DMC y nunca rompe uno existente. Renombra solo CURRENT
a `330007/recovery/CURRENT-<uuid>.json`, preserva sus bytes incluso si está corrupto,
versiones, snapshots e historial; agrega eventos intent/complete. Las banderas son
atestaciones del operador, no detectores automáticos de consumidores.
Si hay caída entre intent y complete, inspeccionar CURRENT y quarantine por hash;
no repetir a ciegas ni borrar evidencia. Si CURRENT permanece, no hubo retiro;
si falta y quarantine coincide, hubo retiro aunque falte complete. Documentar la
reconciliación antes de reabrir consumidores. No limpiar versiones huérfanas.

Finalizar verificando ausencia/punteros válidos, history preservado, locks liberados
y mismo fingerprint reproducible. Guardar evidencia con hashes fuera del repo.

# S.A.P.I. / Normalizacion tecnica en espanol / 2026-10-24
# NO modifica Jira, no reescribe commits, no hace merges ni borra ramas.
# Vista previa por defecto; ejecutar con -Apply solo si la auditoria es correcta.
param(
    [switch]$Apply,
    [string]$RepoPath = 'C:\SAPI'
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path $RepoPath)) { throw "Ruta inexistente: $RepoPath" }
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'No se encontro git.' }
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { throw 'No se encontro GitHub CLI (gh). No instalar a ciegas.' }

$Repo = 'DanielCortezF002/S.A.P.I-Sistema-de-Prediccion-de-Incendios'
$Origin = (& git -C $RepoPath remote get-url origin).Trim()
if ($LASTEXITCODE -ne 0 -or $Origin -notmatch 'DanielCortezF002/S\.A\.P\.I-Sistema-de-Prediccion-de-Incendios(\.git)?$') {
    throw "El remote origin no corresponde al repositorio S.A.P.I.: $Origin"
}
& gh auth status 1>$null
if ($LASTEXITCODE -ne 0) { throw 'gh no tiene autenticacion valida. Ejecuta gh auth login.' }

$Csv = @'
Actual;Propuesto;Jira;Proposito
chore/hito2-w0-gate;verificacion/hito2-puerta-calidad-w0;;Ejecucion y evidencia del gate Hito 2
docs/sprint2-evidence-consolidation;documentacion/sprint2-consolidacion-evidencias;;Expediente de evidencia del cierre Sprint 2
feat/SAPI-43-daily-pipeline-prep;funcionalidad/SAPI-43-preparacion-ejecucion-diaria;SAPI-43;Pipeline diario real e idempotente
feat/SAPI-57-ranking-ml-client;integracion/SAPI-57-cliente-inferencia-ml;SAPI-57;Cliente de servicio ML desde Spring Boot
feat/SAPI-59-persist-ranking-postgis;funcionalidad/SAPI-59-persistencia-ranking-postgis;SAPI-59;Persistencia del ranking en PostGIS
feat/SAPI-60-docker-compose-v2;infraestructura/SAPI-60-entorno-docker-compose;SAPI-60;Entorno reproducible Spring Boot FastAPI PostGIS
feat/SAPI-61-streamlit-backend-rest;integracion/SAPI-61-streamlit-servicio-rest;SAPI-61;Consumo del backend REST desde Streamlit
feat/SAPI-69-centralize-firms-dmc-guard;refactorizacion/SAPI-69-fuente-firms-validacion-dmc;SAPI-69;Centralizacion FIRMS y validacion de formato DMC
feat/SAPI-70-docker-build-hardening;seguridad/SAPI-70-exclusion-secretos-docker;SAPI-70;Exclusion de secretos y artefactos del build
feat/SAPI-71-dmc-refresh;funcionalidad/SAPI-71-actualizacion-versionada-dmc;SAPI-71;Actualizacion mensual de DMC versionada
feat/SAPI-71-dmc-validation;validacion/SAPI-71-control-integridad-dmc;SAPI-71;Control de formato e integridad DMC
feat/SAPI-71-firms-baseline-guard;proteccion/SAPI-71-linea-base-firms;SAPI-71;Preservacion de baseline FIRMS para ciencia
feat/SAPI-71-firms-refresh-v2;funcionalidad/SAPI-71-actualizacion-incremental-firms;SAPI-71;Incremento versionado FIRMS sin sobreescribir baseline
feat/SAPI-71-n8n-bridge;integracion/puente-n8n-datos-operacionales;;Puente de orquestacion; no asignar SAPI-71 sin validar alcance
feat/SAPI-71-scoring-inputs-final;integracion/SAPI-71-entradas-inferencia-fijadas;SAPI-71;Congelacion de entradas al iniciar scoring
feat/sapi-operational-readiness;operaciones/preparacion-actualizacion-controlada;;Preparacion del refresh operacional seguro
feat/ui-academic-defense-hardening;interfaz/hito2-preparacion-defensa-academica;;Usabilidad y datos para defensa academica
feature/dmc-live-card;interfaz/tarjeta-clima-actual-dmc;;Tarjeta de estado meteorologico DMC
review/SAPI-66-hardening;validacion/SAPI-66-evidencias-extremo-a-extremo;SAPI-66;Revalidacion de pruebas E2E
'@ | ConvertFrom-Csv -Delimiter ';'

$prRaw = & gh api "repos/$Repo/pulls?state=open&per_page=100" --jq '.[].head.ref'
if ($LASTEXITCODE -ne 0) { throw 'No se pudo consultar PR abiertas. No se cambia ninguna rama.' }
$prHeads = @($prRaw | ForEach-Object { $_.Trim() })
$worktreeRaw = @(& git -C $RepoPath worktree list --porcelain)
if ($LASTEXITCODE -ne 0) { throw 'No se pudo leer git worktree list.' }
$ocupadas = @($worktreeRaw | Where-Object { $_ -like 'branch refs/heads/*' } | ForEach-Object { $_.Substring(18) })

$refsRaw = @(& git -C $RepoPath ls-remote --heads origin)
if ($LASTEXITCODE -ne 0) { throw 'No se pudieron recuperar referencias remotas.' }
$refs = @{}
foreach ($line in $refsRaw) {
  if ($line -match '^([0-9a-f]{40})\s+refs/heads/(.+)$') { $refs[$Matches[2]] = $Matches[1] }
}

$plan = foreach ($row in $Csv) {
    $old=$row.Actual; $new=$row.Propuesto; $why=''; $status='READY'
    & git -C $RepoPath check-ref-format --branch $new 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { $status='INVALIDA'; $why='Nombre invalido para Git.' }
    elseif (-not $refs.ContainsKey($old)) { $status='NO_EXISTE'; $why='Rama remota ausente.' }
    elseif ($refs.ContainsKey($new)) { $status='CONFLICTO'; $why='Ya existe nombre remoto destino.' }
    elseif ($prHeads -contains $old) { $status='PROTEGIDA_PR'; $why='Renombrarla cerraria una PR abierta.' }
    elseif ($ocupadas -contains $old) { $status='WORKTREE_ACTIVO'; $why='Rama ocupada en un worktree.' }
    else {
        & git -C $RepoPath show-ref --verify --quiet "refs/heads/$old"
        if ($LASTEXITCODE -eq 0) {
            $localSha=(& git -C $RepoPath rev-parse "refs/heads/$old").Trim()
            if ($localSha -ne $refs[$old]) { $status='LOCAL_DIVERGENTE'; $why='SHA local distinto del remoto.' }
        }
        & git -C $RepoPath show-ref --verify --quiet "refs/heads/$new"
        if ($LASTEXITCODE -eq 0) { $status='CONFLICTO_LOCAL'; $why='Rama local destino ya existe.' }
    }
    [pscustomobject]@{ Actual=$old; Propuesto=$new; Jira=$row.Jira; Estado=$status; Razon=$why; SHA=$refs[$old] }
}
$plan | Format-Table -AutoSize Actual,Propuesto,Jira,Estado,Razon
if (-not $Apply) {
    Write-Host "`nPREVISUALIZACION: GitHub y ramas locales NO fueron modificados." -ForegroundColor Cyan
    Write-Host 'Para ejecutar exclusivamente las READY: .\sapi_renombrar_ramas_espanol.ps1 -Apply'
    return
}
$ready = @($plan | Where-Object { $_.Estado -eq 'READY' })
if ($ready.Count -eq 0) { Write-Host 'Sin operaciones READY.'; return }
$done = @()
foreach ($item in $ready) {
   $old=$item.Actual; $new=$item.Propuesto
   $encoded=[uri]::EscapeDataString($old)
   $result = & gh api --method POST "repos/$Repo/branches/$encoded/rename" -f "new_name=$new" 2>&1
   if ($LASTEXITCODE -ne 0) {
      Write-Host "ERROR en $old : $result" -ForegroundColor Red
      Write-Host 'Se detuvo para conservar lo ya realizado. Revisar GitHub antes de reintentar.' -ForegroundColor Yellow
      break
   }
   try { $resp=($result | Out-String | ConvertFrom-Json) } catch { throw "Respuesta no JSON para $old; verificar en GitHub antes de reintentar." }
   if ($resp.name -ne $new -or $resp.commit.sha -ne $item.SHA) {
      Write-Host "ALERTA: verificar $old -> $new manualmente. Resultado inesperado." -ForegroundColor Red
      break
   }
   $done += $item
   Write-Host "REMOTA OK: $old -> $new (SHA conservado)" -ForegroundColor Green
}
if ($done.Count -gt 0) {
    & git -C $RepoPath fetch origin --prune
    if ($LASTEXITCODE -ne 0) { throw 'La sincronizacion de origin fallo. Las ramas de GitHub ya renombradas permanecen intactas.' }
    foreach ($item in $done) {
       & git -C $RepoPath show-ref --verify --quiet "refs/heads/$($item.Actual)"
       if ($LASTEXITCODE -eq 0) {
           & git -C $RepoPath branch -m $item.Actual $item.Propuesto
           if ($LASTEXITCODE -ne 0) { Write-Host "Revisar renombrado local de $($item.Actual)" -ForegroundColor Yellow; continue }
           & git -C $RepoPath branch --set-upstream-to="origin/$($item.Propuesto)" $item.Propuesto
       }
    }
}
Write-Host "Renombradas en GitHub: $($done.Count). Otras ramas en PR, worktrees y certificaciones permanecen sin modificar." -ForegroundColor Cyan

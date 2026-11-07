# S.A.P.I. - Normalizacion de nombres de ramas
# Modo predeterminado: solo previsualizacion. Para ejecutar, usar -Apply.
# No altera commits, PR, autores, timestamps, contenido ni reglas de proteccion.
[CmdletBinding()]
param(
    [switch]$Apply,
    [string]$Repository = 'DanielCortezF002/S.A.P.I-Sistema-de-Prediccion-de-Incendios'
)

$ErrorActionPreference = 'Stop'

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw 'Falta GitHub CLI (gh). Instala con: winget install --id GitHub.cli -e'
}

& gh auth status 1>$null
if ($LASTEXITCODE -ne 0) {
    throw 'Autentica GitHub CLI ejecutando: gh auth login'
}

function Get-RemoteBranches {
    param([string]$Repo)
    $output = & gh api "repos/$Repo/branches?per_page=100" 2>&1
    if ($LASTEXITCODE -ne 0) { throw "No se pudo consultar las ramas: $output" }
    return @( ($output -join "`n") | ConvertFrom-Json )
}

# Mapa respaldado por los cambios verificados en cada rama (2026-10-24).
# No incluye ramas con PR activas ni ramas de despliegue/certificacion.
$renames = @(
    [pscustomobject]@{
        Old='claude/bold-mccarthy-32oawe'
        New='docs/hito2-academic-report'
        Purpose='Informe academico Hito 2'
    },
    [pscustomobject]@{
        Old='claude/overnight-sprint2-evidence-20261020'
        New='docs/sprint2-evidence-consolidation'
        Purpose='Expediente de pruebas y cierre Sprint 2'
    },
    [pscustomobject]@{
        Old='feat/sapi-ai-environment'
        New='chore/repository-structure-governance'
        Purpose='Gobernanza y estructura del repositorio'
    }
)

$branches = Get-RemoteBranches -Repo $Repository
if ($branches.Count -ge 100) {
    throw 'El repositorio tiene >=100 ramas: falta paginacion. No se realizo ninguna modificacion.'
}
$index = @{}
foreach ($item in $branches) { $index[$item.name] = $item }

$repoInfoRaw = & gh api "repos/$Repository" 2>&1
if ($LASTEXITCODE -ne 0) { throw "No se pudo consultar metadata del repo: $repoInfoRaw" }
$repoInfo = ($repoInfoRaw -join "`n") | ConvertFrom-Json

$prsRaw = & gh pr list --repo $Repository --state open --limit 100 --json number,headRefName,baseRefName 2>&1
if ($LASTEXITCODE -ne 0) { throw "No se pudieron revisar PR abiertas: $prsRaw" }
$openPRs = @( ($prsRaw -join "`n") | ConvertFrom-Json )
if ($openPRs.Count -ge 100) {
    throw 'Hay >=100 PR abiertas: revisar paginacion. No se realizo ninguna modificacion.'
}

$plan = @()
foreach ($entry in $renames) {
    $state='READY'; $reason=''
    if (-not $index.ContainsKey($entry.Old)) {
        if ($index.ContainsKey($entry.New)) { $state='ALREADY_RENAMED' }
        else { $state='MISSING_SOURCE' }
    } elseif ($index.ContainsKey($entry.New)) {
        $state='NAME_CONFLICT'
    } elseif ($entry.Old -eq $repoInfo.default_branch) {
        $state='DEFAULT_BRANCH'; $reason='Nunca renombrar la rama principal en esta operacion'
    } elseif ($index[$entry.Old].protected) {
        $state='PROTECTED'; $reason='Requiere revision manual de reglas'
    } else {
        $linked = @($openPRs | Where-Object {
            $_.headRefName -eq $entry.Old -or $_.baseRefName -eq $entry.Old
        })
        if ($linked.Count -gt 0) {
            $state='OPEN_PR_BLOCKED'
            $reason=('PR activas: '+(($linked | ForEach-Object { $_.number }) -join ', '))
        }
    }
    $plan += [pscustomobject]@{
        Old=$entry.Old; New=$entry.New; Purpose=$entry.Purpose
        State=$state; Reason=$reason
        SHA=if($index.ContainsKey($entry.Old)){$index[$entry.Old].commit.sha}else{''}
    }
}

Write-Host "`nS.A.P.I. - Plan de normalizacion de ramas ($Repository)" -ForegroundColor Cyan
$plan | Format-Table Old,New,State,Reason -AutoSize

if (-not $Apply) {
    Write-Host 'PREVISUALIZACION: no se ha modificado GitHub.' -ForegroundColor Yellow
    Write-Host 'Si el plan es correcto, ejecutar de nuevo con -Apply.'
    return
}

if (@($plan | Where-Object { $_.State -in @('NAME_CONFLICT','OPEN_PR_BLOCKED','PROTECTED','DEFAULT_BRANCH') }).Count -gt 0) {
    throw 'Hay conflictos o referencias protegidas. No se aplicara ningun cambio hasta resolverlos.'
}

foreach ($entry in $plan) {
    if ($entry.State -eq 'ALREADY_RENAMED') {
        Write-Host "Ya renombrada: $($entry.New)" -ForegroundColor DarkGreen
        continue
    }
    if ($entry.State -eq 'MISSING_SOURCE') {
        Write-Warning "No se encontro la rama original: $($entry.Old). Se omite."
        continue
    }
    if ($entry.State -ne 'READY') { throw "Estado no permitido: $($entry.State)" }

    $encodedOld = [Uri]::EscapeDataString($entry.Old)
    Write-Host "Renombrando $($entry.Old) -> $($entry.New)..." -ForegroundColor Cyan
    $output = & gh api -X POST "repos/$Repository/branches/$encodedOld/rename" -f "new_name=$($entry.New)" 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Fallo el renombrado de $($entry.Old): $output. Se detiene sin modificar otras ramas."
    }
    $answer = ($output -join "`n") | ConvertFrom-Json
    if ($answer.name -ne $entry.New) {
        throw "GitHub no confirmo el nuevo nombre $($entry.New): $($answer.name)"
    }
    if ($entry.SHA -and $answer.commit.sha -ne $entry.SHA) {
        throw "ALERTA: la rama $($entry.New) apunta a SHA distinto. Revisar antes de continuar."
    }
    Write-Host "OK: $($entry.New) conserva commit $($entry.SHA)" -ForegroundColor Green
}

Write-Host "`nNormalizacion terminada. Si usas un clon local: cd C:\SAPI ; git fetch origin --prune" -ForegroundColor Green
Write-Host 'Si alguna de las ramas renombradas es tu rama local actual, renombrala con git branch -m y configura upstream.'

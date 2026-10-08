# S.A.P.I. - W0 host checks (Quality Gate W0.2 / W0.3 / W0.4 / W0.5).
#
# One script, two callers: Daniel runs it on Windows/Omen (PowerShell 5.1) and
# the GitHub Actions jobs run it through scripts/merge_gate.py (pwsh on
# ubuntu-latest). Same checks, same pass criteria, same evidence layout.
#
# Checks (-Check, comma separated):
#   selftest                        < 1 min: PowerShell, git, Docker CLI/daemon, Compose,
#                                   evidence folder writable (run it first)
#   hostfacts                 W0.5  Docker/Compose versions, free ports, sapi_pgdata
#                                   present (read-only), git core.autocrlf, java/python
#   container-smoke-ml        W0.2  build Dockerfile.ml-api, POST /predict in
#                                   reproducible mode: 200, 50 cells, fingerprint 33c2...
#   container-smoke-backend   W0.3  build services/backend, GET /health = {"status":"UP"}
#   flyway-integration        W0.4  REAL FLYWAY INTEGRATION VALIDATION: Flyway CLI
#                                   12.4.0 migrate/validate/info/migrate on a clean PostGIS
#   sql-migration-validation        SQL MIGRATION VALIDATION (psql only, no Flyway):
#                                   wraps scripts/sapi58_migration_integration.ps1
#
# Safety: every resource is named sapi-w0-*; containers run without published
# ports (the backend gets one random 127.0.0.1 port), PostGIS lives on tmpfs,
# no named volume is created, nothing is pruned and the legacy sapi_pgdata volume
# is only listed, never touched. No .env is read or printed. Results are never
# simulated: a check that cannot run is FAIL with its reason.
#
# Usage (repository root):
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\w0_host_checks.ps1 `
#       -Check hostfacts,container-smoke-ml -OutDir C:\path\to\evidence
# Exit code 0 = every requested check PASS, 1 = at least one FAIL.
param(
    [string[]]$Check = @("hostfacts"),
    [Parameter(Mandatory = $true)][string]$OutDir
)

$ErrorActionPreference = "Continue"
$KnownChecks = @(
    "selftest",
    "hostfacts",
    "container-smoke-ml",
    "container-smoke-backend",
    "flyway-integration",
    "sql-migration-validation"
)
$ExpectedFingerprint = "33c2eacc49bd0cc130928b5bd182ec523e63614f0e3dd97a129a8d4657f231ff"
$ExpectedForecast = "2026-09-01T00:00:00Z"
$PostgisImage = "postgis/postgis:15-3.4"
$FlywayImage = "flyway/flyway:12.4.0"
$MinCompose = [version]"2.24.0"
$DemoPorts = @(8501, 8080, 8000, 5432)

$repo = Split-Path -Parent $PSScriptRoot
# `powershell -File` passes "a,b" as one string: split it here.
$Check = @($Check | ForEach-Object { $_ -split "," } | ForEach-Object { $_.Trim() } | Where-Object { $_ })
$unknown = @($Check | Where-Object { $KnownChecks -notcontains $_ })
if ($unknown.Count -gt 0) {
    Write-Host ("Unknown check(s): " + ($unknown -join ", ") + ". Known: " + ($KnownChecks -join ", "))
    exit 2
}
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$OutDir = (Resolve-Path $OutDir).Path
$rand = [guid]::NewGuid().ToString("N").Substring(0, 8)
$utf8 = New-Object System.Text.UTF8Encoding $false

function UtcNow { (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ") }

function Write-Text([string]$Path, [string]$Text) {
    [System.IO.File]::WriteAllText($Path, $Text, $utf8)
}

function Add-Log([string]$LogFile, [string]$Text) {
    [System.IO.File]::AppendAllText($LogFile, $Text + "`n", $utf8)
}

function Invoke-Native([string]$LogFile, [string]$Exe, [string[]]$NativeArgs, [string]$Shown = "") {
    if (-not $Shown) { $Shown = $Exe + " " + ($NativeArgs -join " ") }
    Add-Log $LogFile ('$ ' + $Shown)
    if (-not (Get-Command $Exe -ErrorAction SilentlyContinue)) {
        # Never reuse a stale $LASTEXITCODE when the tool is not installed.
        Add-Log $LogFile "$Exe not found on PATH`nexit=127"
        return @{ code = 127; out = "$Exe not found on PATH" }
    }
    $global:LASTEXITCODE = 0
    $lines = & $Exe @NativeArgs 2>&1 | ForEach-Object { "$_" }
    $code = $LASTEXITCODE
    $text = ($lines -join "`n")
    Add-Log $LogFile $text
    Add-Log $LogFile ("exit=" + $code)
    return @{ code = $code; out = $text }
}

function Last-JsonLine([string]$Text) {
    $line = @($Text -split "`r?`n" | Where-Object { $_.Trim().StartsWith("{") }) | Select-Object -Last 1
    if (-not $line) { return $null }
    try { return ($line | ConvertFrom-Json) } catch { return $null }
}

function Python-B64([string]$Code) {
    $b64 = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($Code))
    return "import base64;exec(base64.b64decode('$b64').decode('utf-8'))"
}

function Get-FreePort {
    $listener = New-Object System.Net.Sockets.TcpListener ([System.Net.IPAddress]::Loopback), 0
    $listener.Start()
    $port = $listener.LocalEndpoint.Port
    $listener.Stop()
    return $port
}

function Test-PortFree([int]$Port) {
    foreach ($address in @([System.Net.IPAddress]::Loopback, [System.Net.IPAddress]::Any)) {
        $listener = New-Object System.Net.Sockets.TcpListener $address, $Port
        try { $listener.Start(); $listener.Stop() } catch { return $false }
    }
    return $true
}

function New-Result([string]$Name, [string]$Kind) {
    return [ordered]@{
        check = $Name
        kind = $Kind
        status = "FAIL"
        started_utc = (UtcNow)
        finished_utc = $null
        expected = [ordered]@{}
        observed = [ordered]@{}
        failures = @()
        log = "$Name.txt"
    }
}

function Expect($Result, [string]$Key, $Expected, $Observed, [bool]$Ok) {
    $Result.expected[$Key] = $Expected
    $Result.observed[$Key] = $Observed
    if (-not $Ok) { $Result.failures += $Key }
}

function Remove-Container([string]$LogFile, [string]$Name) {
    Invoke-Native $LogFile "docker" @("rm", "-f", $Name) | Out-Null
}

function Docker-Ready([string]$LogFile) {
    $v = Invoke-Native $LogFile "docker" @("version", "--format", "{{.Server.Version}}")
    return ($v.code -eq 0 -and $v.out.Trim())
}

# --- selftest (< 1 min, no builds) -------------------------------------------
function Check-SelfTest($r, [string]$log) {
    $r.observed.powershell = $PSVersionTable.PSVersion.ToString()
    $probe = Join-Path $OutDir "selftest.write-probe"
    $writable = $true
    try { Write-Text $probe "ok"; Remove-Item -Force $probe } catch { $writable = $false }
    Expect $r "evidence_folder_writable" $true $writable $writable
    $git = Invoke-Native $log "git" @("-C", $repo, "rev-parse", "HEAD")
    Expect $r "git" "HEAD readable" $git.out.Trim() ($git.code -eq 0)
    $client = Invoke-Native $log "docker" @("version", "--format", "{{.Client.Version}}")
    Expect $r "docker_cli" "installed" $client.out.Trim() ($client.code -eq 0 -or $client.out -match "\d+\.\d+")
    $server = Invoke-Native $log "docker" @("version", "--format", "{{.Server.Version}}")
    Expect $r "docker_daemon" "running (start Docker Desktop if this fails)" $server.out.Trim() ($server.code -eq 0 -and $server.out.Trim() -ne "")
    $compose = Invoke-Native $log "docker" @("compose", "version", "--short")
    Expect $r "docker_compose" "installed" $compose.out.Trim() ($compose.code -eq 0)
}

# --- hostfacts (W0.5) --------------------------------------------------------
function Check-HostFacts($r, [string]$log) {
    $r.observed.os = [System.Environment]::OSVersion.VersionString
    $r.observed.powershell = $PSVersionTable.PSVersion.ToString()
    $r.observed.machine = [System.Environment]::MachineName

    $server = Invoke-Native $log "docker" @("version", "--format", "{{.Server.Version}}")
    Expect $r "docker_server" "running" $server.out.Trim() ($server.code -eq 0 -and $server.out.Trim() -ne "")

    $compose = Invoke-Native $log "docker" @("compose", "version", "--short")
    $composeVersion = $null
    if ($compose.out -match "(\d+)\.(\d+)\.(\d+)") { $composeVersion = [version]("{0}.{1}.{2}" -f $Matches[1], $Matches[2], $Matches[3]) }
    Expect $r "docker_compose" (">= " + $MinCompose) $compose.out.Trim() ($compose.code -eq 0 -and $composeVersion -ne $null -and $composeVersion -ge $MinCompose)

    $info = Invoke-Native $log "docker" @("info", "--format", "{{.OperatingSystem}} | CPUs={{.NCPU}} | MemTotal={{.MemTotal}}")
    $r.observed.docker_info = $info.out.Trim()

    $busy = @($DemoPorts | Where-Object { -not (Test-PortFree $_) })
    Expect $r "demo_ports_free" ($DemoPorts -join ",") ("busy=" + ($(if ($busy.Count) { $busy -join "," } else { "-" }))) ($busy.Count -eq 0)

    $vol = Invoke-Native $log "docker" @("volume", "ls", "--format", "{{.Name}}")
    $legacy = @($vol.out -split "`r?`n" | Where-Object { $_.Trim() -eq "sapi_pgdata" }).Count -gt 0
    $r.observed.legacy_volume_sapi_pgdata = $(if ($legacy) { "present (listed only, not touched)" } else { "absent" })

    $root = [System.IO.Path]::GetPathRoot($repo)
    try {
        $drive = New-Object System.IO.DriveInfo $root
        $r.observed.disk_free_gb = [math]::Round($drive.AvailableFreeSpace / 1GB, 1)
    } catch { $r.observed.disk_free_gb = "n/d" }

    $autocrlf = Invoke-Native $log "git" @("-C", $repo, "config", "--get", "core.autocrlf")
    $acValue = $autocrlf.out.Trim()
    Expect $r "git_core_autocrlf" "false or unset" $(if ($acValue) { $acValue } else { "unset" }) ($acValue -ne "true")
    $head = Invoke-Native $log "git" @("-C", $repo, "rev-parse", "HEAD")
    $r.observed.git_head = $head.out.Trim()
    $status = Invoke-Native $log "git" @("-C", $repo, "status", "--porcelain")
    $dirty = @($status.out -split "`r?`n" | Where-Object { $_.Trim() -and $_ -notmatch [regex]::Escape((Split-Path -Leaf $OutDir)) }).Count
    Expect $r "git_worktree_clean" 0 $dirty ($dirty -eq 0)

    foreach ($tool in @("java", "python", "py")) {
        if (Get-Command $tool -ErrorAction SilentlyContinue) {
            $args1 = $(if ($tool -eq "java") { @("-version") } else { @("--version") })
            $v = Invoke-Native $log $tool $args1
            $lines = @($v.out -split "`r?`n" | Where-Object { $_ -and $_ -notmatch "JAVA_TOOL_OPTIONS" })
            $versionLine = @($lines | Where-Object { $_ -match "version|Python" }) | Select-Object -First 1
            $r.observed[$tool] = $(if ($versionLine) { $versionLine } else { $lines | Select-Object -First 1 })
        } else {
            $r.observed[$tool] = "not installed (informative)"
        }
    }
    if (Get-Command Get-ExecutionPolicy -ErrorAction SilentlyContinue) {
        try { $r.observed.execution_policy = (Get-ExecutionPolicy).ToString() } catch { $r.observed.execution_policy = "n/d" }
    }
}

# --- container-smoke-ml (W0.2) -----------------------------------------------
function Check-MlContainer($r, [string]$log, [string]$short) {
    if (-not (Docker-Ready $log)) { Expect $r "docker" "running" "unavailable" $false; return }
    $image = "sapi-w0-ml:$short"
    $build = Invoke-Native $log "docker" @("build", "--progress=plain", "-f", (Join-Path $repo "Dockerfile.ml-api"), "-t", $image, $repo)
    Expect $r "image_build" "exit 0" ("exit " + $build.code) ($build.code -eq 0)
    if ($build.code -ne 0) { return }

    $name = "sapi-w0-ml-$rand"
    try {
        $run = Invoke-Native $log "docker" @("run", "-d", "--name", $name, "-e", "SAPI_REPRODUCIBILITY_MODE=1", $image)
        Expect $r "container_start" "exit 0" ("exit " + $run.code) ($run.code -eq 0)
        if ($run.code -ne 0) { return }

        $healthCode = @'
import json, urllib.request, urllib.error
try:
    with urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=5) as r:
        print(json.dumps({"status": r.status, "body": json.load(r)}))
except urllib.error.HTTPError as e:
    print(json.dumps({"status": e.code}))
except Exception as e:
    print(json.dumps({"status": None, "error": type(e).__name__}))
'@
        $health = $null
        for ($i = 0; $i -lt 90; $i++) {
            $h = Invoke-Native $log "docker" @("exec", $name, "python", "-c", (Python-B64 $healthCode)) "docker exec $name python -c <health probe>"
            $health = Last-JsonLine $h.out
            if ($health -and $health.status -eq 200) { break }
            Start-Sleep -Seconds 2
        }
        $hOk = ($health -and $health.status -eq 200 -and $health.body.status -eq "ok")
        Expect $r "health" "200 status=ok" $(if ($health) { "status=" + $health.status + " body=" + ($health.body | ConvertTo-Json -Compress) } else { "no response" }) $hOk

        $predictCode = @'
import hashlib, json, urllib.request, urllib.error
req = urllib.request.Request("http://127.0.0.1:8000/predict", data=b"{}",
                             headers={"Content-Type": "application/json"}, method="POST")
try:
    with urllib.request.urlopen(req, timeout=900) as r:
        status, body = r.status, json.load(r)
except urllib.error.HTTPError as e:
    print(json.dumps({"status": e.code, "error_body": e.read().decode("utf-8", "replace")[:400]}))
    raise SystemExit(0)
cells = body.get("cells", [])
payload = "\n".join(f"{c['cell_id']},{c['score']!r},{c['rank']}" for c in cells)
first = cells[0] if cells else {}
print(json.dumps({
    "status": status,
    "n_cells": len(cells),
    "forecast_time": body.get("forecast_time"),
    "first_cell": first.get("cell_id"),
    "first_score": first.get("score"),
    "ranking_fingerprint": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
    "score_semantics": body.get("score_semantics"),
    "scientific_model_validation": body.get("scientific_model_validation"),
    "model_version": body.get("model_version"),
}))
'@
        $p = Invoke-Native $log "docker" @("exec", $name, "python", "-c", (Python-B64 $predictCode)) "docker exec $name python -c <POST /predict {} + fingerprint>"
        $pred = Last-JsonLine $p.out
        if (-not $pred) { Expect $r "predict" "JSON response" "no response" $false; return }
        Expect $r "predict_status" 200 $pred.status ($pred.status -eq 200)
        Expect $r "n_cells" 50 $pred.n_cells ($pred.n_cells -eq 50)
        Expect $r "forecast_time" $ExpectedForecast $pred.forecast_time ($pred.forecast_time -eq $ExpectedForecast)
        Expect $r "ranking_fingerprint" $ExpectedFingerprint $pred.ranking_fingerprint ($pred.ranking_fingerprint -eq $ExpectedFingerprint)
        Expect $r "score_semantics" "relative_rank" $pred.score_semantics ($pred.score_semantics -eq "relative_rank")
        Expect $r "scientific_model_validation" $false $pred.scientific_model_validation ($pred.scientific_model_validation -eq $false)
        $r.observed.first_cell = "$($pred.first_cell) $($pred.first_score)"
        $r.observed.model_version = $pred.model_version

        $uid = Invoke-Native $log "docker" @("exec", $name, "id", "-u")
        Expect $r "container_uid" "10001" $uid.out.Trim() ($uid.out.Trim() -eq "10001")
        Invoke-Native $log "docker" @("logs", "--tail", "40", $name) | Out-Null
    } finally {
        Remove-Container $log $name
    }
}

# --- container-smoke-backend (W0.3) ------------------------------------------
function Check-BackendContainer($r, [string]$log, [string]$short) {
    if (-not (Docker-Ready $log)) { Expect $r "docker" "running" "unavailable" $false; return }
    $image = "sapi-w0-backend:$short"
    $build = Invoke-Native $log "docker" @("build", "--progress=plain", "-t", $image, (Join-Path $repo "services/backend"))
    Expect $r "image_build" "exit 0" ("exit " + $build.code) ($build.code -eq 0)
    if ($build.code -ne 0) { return }

    $name = "sapi-w0-backend-$rand"
    $port = Get-FreePort
    try {
        $run = Invoke-Native $log "docker" @("run", "-d", "--name", $name, "-p", "127.0.0.1:${port}:8080", $image)
        Expect $r "container_start" "exit 0" ("exit " + $run.code) ($run.code -eq 0)
        if ($run.code -ne 0) { return }
        $body = $null
        $code = $null
        for ($i = 0; $i -lt 60; $i++) {
            try {
                $resp = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$port/health" -TimeoutSec 5
                $code = [int]$resp.StatusCode
                $body = $resp.Content
                if ($code -eq 200) { break }
            } catch { Start-Sleep -Seconds 2 }
        }
        Add-Log $log ("GET http://127.0.0.1:$port/health -> " + $code + " " + $body)
        $status = $null
        try { $status = ($body | ConvertFrom-Json).status } catch { }
        Expect $r "health" "200 {""status"":""UP""}" ("" + $code + " " + $body) ($code -eq 200 -and $status -eq "UP")
        $uid = Invoke-Native $log "docker" @("exec", $name, "id", "-u")
        Expect $r "container_uid" "10001" $uid.out.Trim() ($uid.out.Trim() -eq "10001")
        Invoke-Native $log "docker" @("logs", "--tail", "40", $name) | Out-Null
    } finally {
        Remove-Container $log $name
    }
}

# --- flyway-integration (W0.4): REAL FLYWAY INTEGRATION VALIDATION -----------
function Check-FlywayIntegration($r, [string]$log) {
    if (-not (Docker-Ready $log)) { Expect $r "docker" "running" "unavailable" $false; return }
    $net = "sapi-w0-net-$rand"
    $pg = "sapi-w0-pg-$rand"
    $db = "sapiw0"
    $user = "sapiw0"
    $password = "sapi-w0-local-test"
    $migrations = (Resolve-Path (Join-Path $repo "db/migration")).Path
    $r.observed.migrations = (Get-ChildItem $migrations -Filter "V*__*.sql" | Sort-Object Name | ForEach-Object { $_.Name }) -join ", "

    function Psql([string]$Sql) {
        $res = Invoke-Native $log "docker" @("exec", $pg, "psql", "-X", "-q", "-v", "ON_ERROR_STOP=1", "-At", "-U", $user, "-d", $db, "-h", "127.0.0.1", "-c", $Sql)
        return $res.out.Trim()
    }

    function Flyway([string]$Command) {
        $fwArgs = @(
            "run", "--rm", "--network", $net,
            "--mount", "type=bind,source=$migrations,target=/flyway/sql,readonly",
            "-e", "FLYWAY_URL=jdbc:postgresql://${pg}:5432/$db",
            "-e", "FLYWAY_USER=$user",
            "-e", "FLYWAY_PASSWORD=$password",
            $FlywayImage,
            "-locations=filesystem:/flyway/sql", $Command
        )
        return Invoke-Native $log "docker" $fwArgs ("docker run --rm $FlywayImage -locations=filesystem:/flyway/sql " + $Command)
    }

    # Number of migrations a `migrate` applied, read from Flyway's text output.
    function Executed($Res) {
        if ($Res.out -match "Successfully applied (\d+) migration") { return [int]$Matches[1] }
        if ($Res.out -match "is up to date\. No migration necessary") { return 0 }
        return -1
    }

    try {
        $n = Invoke-Native $log "docker" @("network", "create", $net)
        Expect $r "network" "created" ("exit " + $n.code) ($n.code -eq 0)
        $run = Invoke-Native $log "docker" @(
            "run", "-d", "--name", $pg, "--network", $net, "--tmpfs", "/var/lib/postgresql/data",
            "-e", "POSTGRES_USER=$user", "-e", "POSTGRES_PASSWORD=$password", "-e", "POSTGRES_DB=$db", $PostgisImage)
        Expect $r "postgis_start" "exit 0" ("exit " + $run.code) ($run.code -eq 0)
        if ($run.code -ne 0) { return }
        $ready = $false
        for ($i = 0; $i -lt 60 -and -not $ready; $i++) {
            Start-Sleep -Seconds 1
            $isReady = Invoke-Native $log "docker" @("exec", $pg, "pg_isready", "-h", "127.0.0.1", "-U", $user, "-d", $db)
            if ($isReady.code -eq 0) { $ready = ((Psql "SELECT 1") -eq "1") }
        }
        Expect $r "postgis_ready" $true $ready $ready
        if (-not $ready) { return }

        $m1 = Flyway "migrate"
        $e1 = Executed $m1
        Expect $r "migrate_1_exit" 0 $m1.code ($m1.code -eq 0)
        Expect $r "migrate_1_executed" 3 $e1 ($e1 -eq 3)
        $v = Flyway "validate"
        Expect $r "validate_exit" 0 $v.code ($v.code -eq 0)
        $info = Flyway "info"
        Expect $r "info_exit" 0 $info.code ($info.code -eq 0)
        $m2 = Flyway "migrate"
        $e2 = Executed $m2
        Expect $r "migrate_2_exit" 0 $m2.code ($m2.code -eq 0)
        Expect $r "migrate_2_executed" 0 $e2 ($e2 -eq 0)

        $history = Psql "SELECT string_agg(version || ':' || success, ',' ORDER BY installed_rank) FROM flyway_schema_history WHERE version IS NOT NULL"
        Expect $r "flyway_schema_history" "1:true,2:true,3:true" $history ($history -eq "1:true,2:true,3:true")
        $tables = Psql "SELECT string_agg(tablename, ',' ORDER BY tablename) FROM pg_tables WHERE schemaname='public' AND tablename IN ('celdas_geom','ejecuciones','predicciones_celda')"
        Expect $r "tables" "celdas_geom,ejecuciones,predicciones_celda" $tables ($tables -eq "celdas_geom,ejecuciones,predicciones_celda")
        $cells = Psql "SELECT count(*) FROM celdas_geom"
        Expect $r "cells" "50" $cells ($cells -eq "50")
        $invalid = Psql "SELECT count(*) FROM celdas_geom WHERE NOT ST_IsValid(geom) OR ST_SRID(geom) <> 4326"
        Expect $r "invalid_geometries" "0" $invalid ($invalid -eq "0")
    } finally {
        Remove-Container $log $pg
        Invoke-Native $log "docker" @("network", "rm", $net) | Out-Null
    }
}

# --- sql-migration-validation: SQL MIGRATION VALIDATION (psql, no Flyway) ----
function Check-SqlMigrationValidation($r, [string]$log) {
    if (-not (Docker-Ready $log)) { Expect $r "docker" "running" "unavailable" $false; return }
    $script = Join-Path $repo "scripts/sapi58_migration_integration.ps1"
    $sqlLog = Join-Path $OutDir "sql-migration-validation.detail.txt"
    Add-Log $log ('$ ' + "sapi58_migration_integration.ps1 -LogPath $sqlLog")
    & $script -LogPath $sqlLog *>&1 | ForEach-Object { Add-Log $log "$_" }
    $code = $LASTEXITCODE
    Add-Log $log ("exit=" + $code)
    Expect $r "sapi58_migration_integration" "exit 0 (PASS)" ("exit " + $code) ($code -eq 0)
    $r.observed.detail_log = (Split-Path -Leaf $sqlLog)
}

# --- main --------------------------------------------------------------------
$sha = (& git -C $repo rev-parse HEAD 2>$null)
if (-not $sha) { $sha = "unknown" }
$short = $(if ($sha.Length -ge 7) { $sha.Substring(0, 7) } else { $sha })
$started = UtcNow
$results = @()
foreach ($name in $Check) {
    $kind = switch ($name) {
        "selftest" { "preflight self-test" }
        "hostfacts" { "W0.5 host facts" }
        "container-smoke-ml" { "W0.2 ML image smoke" }
        "container-smoke-backend" { "W0.3 backend image smoke" }
        "flyway-integration" { "W0.4 REAL FLYWAY INTEGRATION VALIDATION" }
        "sql-migration-validation" { "SQL MIGRATION VALIDATION (psql, not Flyway)" }
    }
    $r = New-Result $name $kind
    $log = Join-Path $OutDir "$name.txt"  # *.log is git-ignored in this repo
    Write-Text $log ("# $name - $kind`n# sha=$sha utc=$(UtcNow)`n")
    Write-Host ("[{0}] {1} ..." -f (UtcNow), $name)
    try {
        switch ($name) {
            "selftest" { Check-SelfTest $r $log }
            "hostfacts" { Check-HostFacts $r $log }
            "container-smoke-ml" { Check-MlContainer $r $log $short }
            "container-smoke-backend" { Check-BackendContainer $r $log $short }
            "flyway-integration" { Check-FlywayIntegration $r $log }
            "sql-migration-validation" { Check-SqlMigrationValidation $r $log }
        }
    } catch {
        Add-Log $log ("EXCEPTION " + $_.Exception.Message)
        $r.failures += "exception"
    }
    if ($r.expected.Count -eq 0 -and $r.failures.Count -eq 0) { $r.failures += "no-assertions" }
    $r.status = $(if ($r.failures.Count -eq 0) { "PASS" } else { "FAIL" })
    $r.finished_utc = UtcNow
    Write-Text (Join-Path $OutDir "$name.json") ($r | ConvertTo-Json -Depth 8)
    Write-Host ("[{0}] {1}: {2}{3}" -f (UtcNow), $name, $r.status, $(if ($r.failures.Count) { " (" + ($r.failures -join ", ") + ")" } else { "" }))
    $results += $r
}

$overall = $(if (@($results | Where-Object { $_.status -ne "PASS" }).Count -eq 0) { "PASS" } else { "FAIL" })
$summary = [ordered]@{
    schema = "sapi-w0-host-checks-v1"
    sha = $sha
    started_utc = $started
    finished_utc = (UtcNow)
    machine = [System.Environment]::MachineName
    powershell = $PSVersionTable.PSVersion.ToString()
    checks = @($results | ForEach-Object { [ordered]@{ check = $_.check; kind = $_.kind; status = $_.status; failures = $_.failures } })
    overall = $overall
}
Write-Text (Join-Path $OutDir "summary.json") ($summary | ConvertTo-Json -Depth 6)

$manifest = Get-ChildItem -Path $OutDir -File | Where-Object { $_.Name -ne "manifest.sha256" } | Sort-Object Name | ForEach-Object {
    (Get-FileHash -Algorithm SHA256 -Path $_.FullName).Hash.ToLower() + "  " + $_.Name
}
Write-Text (Join-Path $OutDir "manifest.sha256") (($manifest -join "`n") + "`n")

Write-Host ""
Write-Host "==================== W0 HOST CHECKS ===================="
foreach ($x in $results) { Write-Host ("{0,-26} {1}" -f $x.check, $x.status) }
Write-Host ("OVERALL                    " + $overall)
Write-Host ("Evidence: " + $OutDir)
if ($overall -eq "PASS") { exit 0 } else { exit 1 }

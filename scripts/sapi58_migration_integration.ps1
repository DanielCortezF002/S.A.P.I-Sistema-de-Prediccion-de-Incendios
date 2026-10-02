# SAPI-58 - Integration test of the v2 migrations on a DEDICATED, DISPOSABLE PostGIS.
#
# Isolation guarantees (see db/README.md):
#   - creates its own container with a unique name, no volume (tmpfs data dir)
#     and NO published port: every command runs inside the container;
#   - never reads DATABASE_URL or any external connection setting: it only
#     touches the container it created itself;
#   - always removes the container in `finally`, even on failure.
#
# Usage (from the repository root):
#   powershell -ExecutionPolicy Bypass -File scripts\sapi58_migration_integration.ps1 [-LogPath <file>]
# Exit code 0 = PASS, 1 = FAIL.
param(
    [string]$Image = "postgis/postgis:15-3.4",
    [string]$LogPath = ""
)

# "Continue": negative tests expect psql to fail and write to stderr; with
# "Stop", Windows PowerShell 5.1 turns that stderr into a terminating error.
# Every native call is checked explicitly through $LASTEXITCODE instead.
$ErrorActionPreference = "Continue"
$repo = Split-Path -Parent $PSScriptRoot
$migrations = Get-ChildItem (Join-Path $repo "db\migration") -Filter "V*__*.sql" | Sort-Object Name
$name = "sapi58-mig-" + [guid]::NewGuid().ToString("N").Substring(0, 12)
$db = "sapi58"
$user = "sapi58"
$failures = New-Object System.Collections.Generic.List[string]
$log = New-Object System.Collections.Generic.List[string]

function Say([string]$msg) { $log.Add($msg); Write-Host $msg }

function Psql([string]$sql) {
    # Returns @{ code; out } ; -At for unaligned, tuples-only output.
    # -q: no command tags ("INSERT 0 1"), so RETURNING values come back alone.
    $out = & docker exec $name psql -X -q -v ON_ERROR_STOP=1 -At -U $user -d $db -h 127.0.0.1 -c $sql 2>&1
    return @{ code = $LASTEXITCODE; out = ($out | Out-String).Trim() }
}

function Expect([string]$label, [bool]$ok, [string]$detail) {
    if ($ok) { Say "PASS  $label  $detail" } else { Say "FAIL  $label  $detail"; $failures.Add($label) }
}

function ExpectRejected([string]$label, [string]$sql, [string]$constraint) {
    $r = Psql "BEGIN; $sql; ROLLBACK;"
    $ok = ($r.code -ne 0) -and ($r.out -match [regex]::Escape($constraint))
    Expect $label $ok ("(rejected by " + $constraint + ")")
}

Say "SAPI-58 migration integration - $(Get-Date -Format o)"
Say "image=$Image container=$name (no volume, no published port)"
if ($env:DATABASE_URL) { Say "note: DATABASE_URL is set in this shell and is deliberately IGNORED" }
Say ("migrations: " + (($migrations | ForEach-Object { $_.Name }) -join ", "))

try {
    & docker run -d --name $name --tmpfs /var/lib/postgresql/data `
        -e POSTGRES_USER=$user -e POSTGRES_PASSWORD=sapi58-local-test -e POSTGRES_DB=$db `
        $Image | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "docker run failed" }

    # TCP readiness (127.0.0.1) avoids the image's temporary init server, which
    # only listens on the unix socket.
    $ready = $false
    for ($i = 0; $i -lt 60 -and -not $ready; $i++) {
        Start-Sleep -Seconds 1
        & docker exec $name pg_isready -h 127.0.0.1 -U $user -d $db 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) { $ready = ((Psql "SELECT 1").out -eq "1") }
    }
    Expect "postgis-ready" $ready ""
    if (-not $ready) { throw "PostGIS not ready" }

    foreach ($m in $migrations) {
        & docker cp $m.FullName "${name}:/tmp/$($m.Name)" | Out-Null
        $out = & docker exec $name psql -X -v ON_ERROR_STOP=1 -U $user -d $db -h 127.0.0.1 -f "/tmp/$($m.Name)" 2>&1
        Expect ("apply " + $m.Name) ($LASTEXITCODE -eq 0) ""
        if ($LASTEXITCODE -ne 0) { Say ($out | Out-String); throw "migration failed: $($m.Name)" }
    }

    # --- Inspection -----------------------------------------------------------
    $tables = (Psql "SELECT string_agg(tablename, ',' ORDER BY tablename) FROM pg_tables WHERE schemaname='public' AND tablename IN ('celdas_geom','ejecuciones','predicciones_celda')").out
    Expect "tables" ($tables -eq "celdas_geom,ejecuciones,predicciones_celda") $tables

    $gist = (Psql "SELECT indexdef FROM pg_indexes WHERE indexname='celdas_geom_geom_gist'").out
    Expect "gist-index" ($gist -match "USING gist \(geom\)") $gist

    $cellTime = (Psql "SELECT indexdef FROM pg_indexes WHERE indexname='predicciones_celda_cell_time_idx'").out
    Expect "cell-time-index" ($cellTime -match "\(cell_id, forecast_time DESC\)") $cellTime

    $count = (Psql "SELECT count(*) FROM celdas_geom").out
    Expect "50-cells" ($count -eq "50") "count=$count"

    $ids = (Psql "SELECT min(cell_id) || '..' || max(cell_id) || ' distinct=' || count(DISTINCT cell_id) FROM celdas_geom").out
    Expect "cell-ids" ($ids -eq "VP-001..VP-050 distinct=50") $ids

    $invalid = (Psql "SELECT count(*) FROM celdas_geom WHERE NOT ST_IsValid(geom) OR ST_SRID(geom) <> 4326").out
    Expect "geometry-valid-4326" ($invalid -eq "0") "invalid=$invalid"

    $overlap = (Psql "SELECT count(*) FROM celdas_geom a JOIN celdas_geom b ON a.cell_id < b.cell_id AND ST_Area(ST_Intersection(a.geom, b.geom)) > 1e-12").out
    Expect "cells-do-not-overlap" ($overlap -eq "0") "overlapping_pairs=$overlap"

    $area = (Psql "SELECT round((avg(ST_Area(geom::geography)) / 1e6)::numeric, 2) FROM celdas_geom").out
    Expect "cell-area-km2" ([double]$area -gt 14 -and [double]$area -lt 16) "avg_km2=$area"

    $probCols = (Psql "SELECT count(*) FROM information_schema.columns WHERE table_schema='public' AND column_name ILIKE '%probab%'").out
    Expect "no-probability-columns" ($probCols -eq "0") "count=$probCols"

    # --- Valid data is accepted (and cascades) ----------------------------------
    $fp = "a" * 64
    $ins = Psql ("INSERT INTO ejecuciones (forecast_time, model_version, inputs_fingerprint, schema_version, horizon_hours) " +
        "VALUES ('2026-09-01T00:00:00Z', 'prototype_model_d_v1', '$fp', 'sapi-ranking-v0', 6) RETURNING id")
    Expect "insert-ejecucion" ($ins.code -eq 0) ("id=" + $ins.out)
    $ejId = ($ins.out -split "`r?`n")[0].Trim()
    if ($ejId -notmatch '^\d+$') { throw "unexpected ejecucion id: $($ins.out)" }
    $pred = Psql ("INSERT INTO predicciones_celda (ejecucion_id, forecast_time, cell_id, score, rank, display_rank, tie_group_size) VALUES " +
        "($ejId, '2026-09-01T00:00:00Z', 'VP-001', 0.13, 1, 1, 2), ($ejId, '2026-09-01T00:00:00Z', 'VP-002', 0.13, 2, 1, 2)")
    Expect "insert-predicciones" ($pred.code -eq 0) ""

    # --- Negative tests: each must be rejected by the named constraint ----------
    ExpectRejected "fk-unknown-cell" "INSERT INTO predicciones_celda VALUES ($ejId, '2026-09-01T00:00:00Z', 'VP-999', 0.1, 3, 3, 1)" "predicciones_celda_celda_fk"
    ExpectRejected "fk-forecast-time-mismatch" "INSERT INTO predicciones_celda VALUES ($ejId, '2026-09-01T06:00:00Z', 'VP-003', 0.1, 3, 3, 1)" "predicciones_celda_ejecucion_fk"
    ExpectRejected "score-above-1" "INSERT INTO predicciones_celda VALUES ($ejId, '2026-09-01T00:00:00Z', 'VP-003', 1.5, 3, 3, 1)" "predicciones_celda_score_rango"
    ExpectRejected "duplicate-rank" "INSERT INTO predicciones_celda VALUES ($ejId, '2026-09-01T00:00:00Z', 'VP-003', 0.1, 2, 2, 1)" "predicciones_celda_rank_unico"
    ExpectRejected "display-rank-above-rank" "INSERT INTO predicciones_celda VALUES ($ejId, '2026-09-01T00:00:00Z', 'VP-003', 0.1, 3, 4, 1)" "predicciones_celda_display_rank_min"
    ExpectRejected "score-semantics" "INSERT INTO ejecuciones (forecast_time, model_version, inputs_fingerprint, schema_version, score_semantics) VALUES ('2026-09-01T06:00:00Z', 'm', '$fp', 'sapi-ranking-v0', 'probability')" "ejecuciones_score_semantics_ranking"
    ExpectRejected "scientific-validation-true" "INSERT INTO ejecuciones (forecast_time, model_version, inputs_fingerprint, schema_version, scientific_model_validation) VALUES ('2026-09-01T06:00:00Z', 'm', '$fp', 'sapi-ranking-v0', true)" "ejecuciones_sin_validacion_cientifica"
    ExpectRejected "duplicate-natural-key" "INSERT INTO ejecuciones (forecast_time, model_version, inputs_fingerprint, schema_version) VALUES ('2026-09-01T00:00:00Z', 'prototype_model_d_v1', '$fp', 'sapi-ranking-v0')" "ejecuciones_clave_natural"
    ExpectRejected "fingerprint-not-hex" "INSERT INTO ejecuciones (forecast_time, model_version, inputs_fingerprint, schema_version) VALUES ('2026-09-01T06:00:00Z', 'm', '$('Z' * 64)', 'sapi-ranking-v0')" "ejecuciones_fingerprint_hex"
    ExpectRejected "bad-cell-id" "INSERT INTO celdas_geom VALUES ('X-1', ST_MakeEnvelope(0, 0, 1, 1, 4326))" "celdas_geom_cell_id_formato"

    $del = Psql "DELETE FROM ejecuciones WHERE id = $ejId"
    $left = (Psql "SELECT count(*) FROM predicciones_celda WHERE ejecucion_id = $ejId").out
    Expect "cascade-delete" ($del.code -eq 0 -and $left -eq "0") "remaining=$left"
}
catch {
    Say ("ERROR  " + $_.Exception.Message)
    $failures.Add("exception")
}
finally {
    & docker rm -f $name 2>&1 | Out-Null
    $gone = -not (& docker ps -a --filter "name=^/$name$" --format "{{.Names}}")
    Expect "container-removed" $gone $name
}

$result = if ($failures.Count -eq 0) { "PASS" } else { "FAIL (" + ($failures -join ", ") + ")" }
Say "RESULT: SAPI-58 clean PostGIS migration integration $result"
if ($LogPath) { $log | Out-File -FilePath $LogPath -Encoding utf8 }
if ($failures.Count -eq 0) { exit 0 } else { exit 1 }

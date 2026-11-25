<#
.SYNOPSIS
  C4 · Eficiencia. Una corrida: calentamiento (excluido) y luego medición, contra sapi-h3-518c0b5.
.DESCRIPTION
  Exige -LuzVerde con la referencia del mensaje que autoriza ESTA corrida. Si el calentamiento
  no termina con 2 de 2 respuestas 200, no se mide y la corrida queda NO_EVALUABLE.
  No toca contenedores ni crea volúmenes: solo `docker run --rm grafana/k6:0.54.0`.
.EXAMPLE
  .\Invoke-K6Eficiencia.ps1 -LuzVerde "msg_<id> <quién> 2026-11-25 hh:mm"
#>
param([Parameter(Mandatory)][string]$LuzVerde)
$ErrorActionPreference = 'Stop'
if ([string]::IsNullOrWhiteSpace($LuzVerde)) { throw 'Sin luz verde explícita no se corre.' }
$aqui = Split-Path -Parent $MyInvocation.MyCommand.Path
$base = 'http://host.docker.internal:18080'
$dir = Join-Path $aqui ("corrida-" + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ'))
New-Item -ItemType Directory -Path $dir | Out-Null

$cpu = Get-CimInstance Win32_Processor; $os = Get-CimInstance Win32_OperatingSystem
@(
  "fecha_utc: $([DateTime]::UtcNow.ToString('o'))"
  "sha_repo_HEAD: $(git -C $aqui rev-parse HEAD)"
  "sha_codigo_stack: 518c0b58e6b229317f51b1da56ac23346dc2ef74"
  "imagenes: " + ((docker compose -p sapi-h3-518c0b5 images --format json | ConvertFrom-Json | ForEach-Object { "$($_.Repository)=$($_.ID)" }) -join ', ')
  "contenedores: " + ((docker ps --format '{{.Names}}={{.Status}}') -join '; ')
  "hardware: $($cpu.Name.Trim()), $($cpu.NumberOfCores) núcleos/$($cpu.NumberOfLogicalProcessors) hilos, $([math]::Round($os.TotalVisibleMemorySize/1MB,1)) GB RAM, $($os.Caption) $($os.Version)"
  "declaracion: docs/calidad/eficiencia-k6-2026-11-25.md"
  "calentamiento: 1 VU, 2 iteraciones (excluido)  medicion: 2 VUs constantes, 3 min, pausa 1 s, timeout 90 s"
  "umbral: p95 <= 20000 ms y http_req_failed < 1 % (solo medicion)"
  "luz_verde: $LuzVerde"
  "No es KPI-03. Ejecutado en el computador local, no en ambiente desplegado."
) | Set-Content "$dir\00-cabecera.txt" -Encoding utf8

function Invoke-Fase([string]$fase) {
  docker run --rm -v "${aqui}:/scripts:ro" -v "${dir}:/out" grafana/k6:0.54.0 run `
    -e FASE=$fase -e BASE_URL=$base -e SALIDA=/out/$fase-resumen.json `
    /scripts/k6_ranking.js 2>&1 | Tee-Object "$dir\$fase-consola.txt"
  "k6 exit=$LASTEXITCODE" | Tee-Object -Append "$dir\$fase-consola.txt"
}

Invoke-Fase 'calentamiento'
$cal = Get-Content "$dir\calentamiento-resumen.json" -Raw | ConvertFrom-Json
$ok = $cal.metrics.checks.values.passes -eq 6 -and $cal.metrics.checks.values.fails -eq 0
if (-not $ok) {
  "NO_EVALUABLE: el calentamiento no terminó con 2 de 2 respuestas válidas; no se midió." | Tee-Object "$dir\02-veredicto.txt"
} else {
  Invoke-Fase 'medicion'
}
Get-FileHash "$dir\*" -Algorithm SHA256 | ForEach-Object { "$($_.Hash.ToLower())  $(Split-Path $_.Path -Leaf)" } | Set-Content "$dir\SHA256SUMS" -Encoding utf8

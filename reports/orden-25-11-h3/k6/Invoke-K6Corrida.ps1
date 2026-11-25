<#
.SYNOPSIS
  Lanza UNA corrida k6 contra sapi-h3-518c0b5. PREPARADO, NO EJECUTADO.
.DESCRIPTION
  Exige -LuzVerde con la referencia del mensaje de autorización del Director para
  ESA corrida. Registra fecha, SHA, hardware, N de VUs y la frase de alcance.
  No toca el stack 'sapi'. No crea volúmenes. Usa la imagen grafana/k6:0.54.0.
.EXAMPLE
  .\Invoke-K6Corrida.ps1 -Escenario humo -LuzVerde "msg-<id> Director 2026-11-25 hh:mm"
#>
param(
  [Parameter(Mandatory)][ValidateSet('humo','l1','l2','rampa')][string]$Escenario,
  [Parameter(Mandatory)][string]$LuzVerde,
  [string]$BaseUrl = 'http://host.docker.internal:18080',
  [int]$P95Ms = 10000
)
$ErrorActionPreference = 'Stop'
if ([string]::IsNullOrWhiteSpace($LuzVerde)) { throw 'Sin luz verde explícita no se corre.' }
$vus = @{ humo = '1 (5 iteraciones)'; l1 = '2'; l2 = '5'; rampa = '0 -> 10 -> 0' }[$Escenario]
$aqui = Split-Path -Parent $MyInvocation.MyCommand.Path
$stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$dir = Join-Path $aqui "corrida-$Escenario-$stamp"
New-Item -ItemType Directory -Path $dir | Out-Null

$cpu = Get-CimInstance Win32_Processor; $os = Get-CimInstance Win32_OperatingSystem
$cab = @(
  "fecha_utc: $([DateTime]::UtcNow.ToString('o'))"
  "sha_codigo: $(git -C $aqui rev-parse HEAD)"
  "stack: sapi-h3-518c0b5"
  "imagenes: " + ((docker compose -p sapi-h3-518c0b5 images --format json | ConvertFrom-Json | ForEach-Object { "$($_.Repository)=$($_.ID)" }) -join ', ')
  "hardware: $($cpu.Name.Trim()), $($cpu.NumberOfCores) núcleos/$($cpu.NumberOfLogicalProcessors) hilos, $([math]::Round($os.TotalVisibleMemorySize/1MB,1)) GB RAM, $($os.Caption) $($os.Version)"
  "escenario: $Escenario  VUs: $vus  base: $BaseUrl  p95_ms_propuesto: $P95Ms"
  "luz_verde: $LuzVerde"
  "Ejecutado en el computador local, no en ambiente desplegado."
)
$cab | Set-Content "$dir\00-cabecera.txt" -Encoding utf8
$cab

# Las variables van como flags de k6 (-e): las de `docker run -e` no llegan a __ENV.
docker run --rm -v "${aqui}:/scripts:ro" -v "${dir}:/out" grafana/k6:0.54.0 run `
  -e ESCENARIO=$Escenario -e BASE_URL=$BaseUrl -e P95_MS=$P95Ms -e SALIDA=/out/resumen.json `
  /scripts/sapi_h3_carga.js 2>&1 | Tee-Object "$dir\01-consola.txt"
"k6 exit=$LASTEXITCODE" | Tee-Object -Append "$dir\01-consola.txt"
Get-FileHash "$dir\*" -Algorithm SHA256 | ForEach-Object { "$($_.Hash.ToLower())  $(Split-Path $_.Path -Leaf)" } | Set-Content "$dir\SHA256SUMS" -Encoding utf8

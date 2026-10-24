# Evidencia E2E — S.A.P.I. v2 (2026-10-24)

Paquete de evidencia de la certificación física del stack v2 en el worktree
`C:\SAPI-OC-E2E-20261024`, rama `test/oc-fullstack-e2e-20261024`.

**Informe principal:** `reports/OC-E2E-20261024-CERTIFICACION.md`.

## Lectura recomendada

| Archivo | Qué demuestra |
|---|---|
| `logs/35-final-suite.log` | 8 tests full-stack + CA4, corrida final (48,76 s) |
| `logs/36-final-negative.log` | 5 tests de fallos por salto, corrida final (101,29 s) |
| `logs/08-vertical-slice-tests.log` | 5 tests vertical slice preexistentes (sin cambios) |
| `logs/09-backend-surefire.log` | Maven: 163 tests, 0 fallos, 0 errores, 5 skipped |
| `e2e/ranking-http.json` | Respuesta HTTP real del ranking, hash y request id |
| `e2e/postgis-verification.json` | Flyway, ejecución, 50 predicciones, comparación 1:1 |
| `e2e/idempotency.json` | Segunda llamada: mismas celdas, 1 ejecución |
| `e2e/openapi-conformance.json` | Validación contra contratos OpenAPI congelados |
| `e2e/browser-verification.json` | Edge real, 50 rectángulos Leaflet, fingerprint, consola |
| `timings/ca4-timings.csv` / `.json` | Cold/update/cached con deltas de `ml_predict` |
| `negative/*.json` | 422/503/500, cero escrituras y recuperación |
| `postgis-snapshot.txt` | Snapshot SQL final: Flyway, ranking, geometría, integridad |
| `restart-persistence.json` | Persistencia tras `down` sin `-v` y `up` |
| `final-state.json` | Salud, ranking, base, contenedores y volúmenes al cierre |
| `environment.txt` | Versiones del entorno |
| `git-state.txt` | HEAD, tree y estado del worktree |
| `SHA256SUMS.txt` | SHA-256 del paquete de evidencia (bytes exactos) |

## Estructura

- `e2e/`: JSON y PNG producidos por `test_full_stack_browser.py`.
- `timings/`: CSV, JSON y PNG de CA4 (`test_full_stack_timings.py`).
- `negative/`: JSON y PNG de la matriz de fallos.
- `logs/`: salidas de Compose, pytest, Maven y comandos de ciclo de vida.
- `screenshots/`: capturas auxiliares de la UI (backend caído/arriba).
- `ranking-response-01.json` / `ranking-response-02-idempotent.json`: cuerpos
  HTTP crudos de la primera corrida.

## Nota sobre logs intermedios

Los logs `26-final-suite.log` y `28-final-suite.log` conservan fallos de
selector del arnés de navegador (el desplegable de Streamlit quedaba fuera del
viewport tras abrir el expander). Se corrigió el test nuevo con
`scroll_into_view_if_needed()` y espera explícita; la corrida final es
`35-final-suite.log`. **No son fallos del producto.**

Los logs `12`–`34` documentan iteraciones de instrumentación CA4 (esperas de
asentamiento de CSS, reinicios de `web-v2` para obtener caché fría). La
medición final es la de `35-final-suite.log` y `timings/ca4-timings.csv`.

## Reproducción

Ver §13 del informe. En resumen:

```powershell
$env:SAPI_DB_PORT='55432'
$env:SAPI_ML_PORT='58000'
$env:SAPI_BACKEND_PORT='58080'
$env:SAPI_WEB_PORT='58501'
docker compose -f docker-compose.yml -f tests/e2e/docker-compose.e2e-oc.yml `
  -p sapi-oc-e2e-20261024 --profile presentation up -d

$env:SAPI_E2E_FULL_STACK='1'
python -m pytest tests/e2e/test_full_stack_timings.py `
  tests/e2e/test_full_stack_browser.py -v --no-cov
$env:SAPI_E2E_FAULT_INJECTION='1'
python -m pytest tests/e2e/test_full_stack_negative.py -v --no-cov
```

El paquete no contiene contraseñas ni el contenido del volumen de secretos.

## Verificación de integridad

`SHA256SUMS.txt` cubre todos los archivos de este directorio excepto el propio
manifiesto. El `.gitattributes` local fija `-text` para que el blob de Git
conserve los bytes y los hashes sean válidos en Windows, Linux y macOS.

```powershell
Get-Content artifacts/oc-e2e-20261024/SHA256SUMS.txt | ForEach-Object {
  $h, $p = $_ -split '  ', 2
  $calc = (Get-FileHash -Algorithm SHA256 -Path $p).Hash.ToLower()
  if ($calc -ne $h) { "MISMATCH $p" }
}
```

Sin salida significa que las 79 entradas del manifiesto coinciden.

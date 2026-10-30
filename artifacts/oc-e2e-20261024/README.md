# Evidencia E2E — S.A.P.I. v2 (2026-10-24)

Paquete de evidencia de la certificación física del stack v2. Contiene **dos
corridas** claramente separadas:

- **R1:** publicada en la rama `test/oc-fullstack-e2e-20261024`, commit
  `426605f`, PR #41 (draft). Mediciones CA4 superadas; ver §4.
- **R2:** remediación de hallazgos P1 en la rama
  `test/oc-fullstack-e2e-r2-20261024`, base
  `origin/recovery/s2-academic-20261024` (`eb1b370`). Es la evidencia vigente de
  este paquete.

**Informe principal:** `reports/OC-E2E-20261024-CERTIFICACION.md`  
**Procedencia:** `PROVENANCE.md`  
**Redacción de datos:** `REDACTION-NOTICE.md`

## 1. Estado de la evidencia

| Criterio | Estado | Evidencia |
|---|---|---|
| CA4 — cold/update/cached con gates duros | **PASS en esta corrida (R2)** | `timings/ca4-timings.*`, `timings/ca4-raw-*.log`, `timings/ca4-request-correlation.json`, `logs/42-r2-ca4.log` |
| CA2 — contratos por servicio | **PARCIAL** | `e2e/contracts-r2.json`, `logs/41-r2-contracts.log` |
| CA1, CA3 — navegador/PostGIS | PASS (R1, sin cambios de producto) | `e2e/*`, `postgis-snapshot.txt` |
| CA5 literal | **BLOQUEADO** | `docs/architecture-stack-freeze-sprint2.md` |
| Gate B / SAPI-43 `current` | **NO GO / NO ACREDITADO** | fuera del alcance de este paquete |

CA4 R2 exige y verifica: reinicio de `web-v2` dentro del test, ≥1 `ml_predict`
real en frío, ≥1 `POST /predict 200` en FastAPI, `request_id` nuevo en la
actualización y **cero** inferencias en el rerun cacheado. Si algo falla, el test
falla.

## 2. Lectura recomendada

| Archivo | Qué demuestra | Corrida |
|---|---|---|
| `logs/42-r2-ca4.log` | CA4 R2: test pasado con gates duros (37,16 s) | R2 |
| `logs/41-r2-contracts.log` | Contratos por servicio: 1 test pasado (10,77 s) | R2 |
| `timings/ca4-timings.json` | Tiempos, deltas, request IDs, procedencia y gates | R2 |
| `timings/ca4-request-correlation.json` | Correlación por acción con líneas crudas | R2 |
| `e2e/contracts-r2.json` | 200/422 reales de ML y backend + cobertura PARCIAL | R2 |
| `logs/40-r2-compose-up.log` / `logs/43-r2-compose-config.log` | Levantamiento y configuración resuelta | R2 |
| `r2-final-state.json` | Salud, ranking, base y contenedores al cierre R2 | R2 |
| `logs/35-final-suite.log` | 8 tests full-stack + CA4 de R1 (48,76 s) | R1 |
| `logs/36-final-negative.log` | 5 tests de fallos por salto de R1 (101,29 s) | R1 |
| `logs/08-vertical-slice-tests.log` | 5 tests vertical slice preexistentes | R1 |
| `logs/09-backend-surefire.log` | Maven: 163 tests, 0 fallos, 0 errores, 5 skipped | R1 |
| `e2e/ranking-http.json` | Respuesta HTTP real del ranking, hash y request id | R1 |
| `e2e/postgis-verification.json` | Flyway, ejecución, 50 predicciones, comparación 1:1 | R1 |
| `e2e/idempotency.json` | Segunda llamada: mismas celdas, 1 ejecución | R1 |
| `e2e/browser-verification.json` | Edge real, 50 rectángulos Leaflet, fingerprint, consola | R1 |
| `negative/*.json` | 422/503/500, cero escrituras y recuperación | R1 |
| `postgis-snapshot.txt` | Snapshot SQL final: Flyway, ranking, geometría, integridad | R1 |
| `restart-persistence.json` | Persistencia tras `down` sin `-v` y `up` | R1 |
| `r1-final-state.json` | Salud, ranking, base, contenedores y volúmenes al cierre R1 | R1 |
| `r1-git-state.txt` / `r2-git-state.txt` | HEAD, tree y estado del worktree de cada corrida | R1 / R2 |
| `environment.txt` | Versiones del entorno (R2) | R2 |
| `SHA256SUMS.txt` | SHA-256 del paquete completo (91 entradas) | R1 + R2 |

## 3. Estructura

- `e2e/`: JSON y PNG de navegador/contratos. `contracts-r2.json` es R2; el resto
  es R1.
- `timings/`: CSV, JSON, PNG, logs crudos y correlación de CA4 (R2).
- `negative/`: JSON y PNG de la matriz de fallos (R1).
- `logs/`: salidas de Compose, pytest, Maven y ciclo de vida. `01`–`39` son R1;
  `40`–`43` son R2.
- `screenshots/`: capturas auxiliares de la UI (R1).
- `ranking-response-*.json`: cuerpos HTTP crudos de R1.
- `PROVENANCE.md`: qué arnés y qué commit produjeron cada grupo.
- `REDACTION-NOTICE.md`: qué se redactó, cuántas veces y qué exposición histórica
  queda abierta.

## 4. Relación R1 → R2

R1 midió CA4 con la caché fría preparada **a mano** fuera del test. El arnés R1
no fallaba si la caché estaba tibia. Por eso sus números
(`6.065,26 / 2.649,82 / 893,25 ms`) **no se reutilizan** ni se presentan como
vigentes: quedan como registro histórico en el commit `426605f` y en la copia
local de auditoría. R2 incorpora el reinicio de `web-v2` y los gates duros; sus
números son los de `timings/ca4-timings.json`. Los valores R1 no se publican en
este paquete para evitar que se citen como si fueran reproducibles.

## 5. Privacidad

R1 publicó un IPv4 globalmente enrutable y el nombre del perfil local en logs.
R2 los retiró de los artefactos (3 IP y 31 ocurrencias del nombre, en 20
archivos) y regeneró los hashes. **La historia de `426605f`/PR #41 sigue
conteniendo los valores originales**; cerrarla o reescribirla requiere
autorización del Product Owner. Detalle y opciones en `REDACTION-NOTICE.md`.

## 6. Reproducción

Ver §13 del informe. En resumen:

```powershell
$env:SAPI_DB_PORT='55432'
$env:SAPI_ML_PORT='58000'
$env:SAPI_BACKEND_PORT='58080'
$env:SAPI_WEB_PORT='58501'
docker compose -f docker-compose.yml -f tests/e2e/docker-compose.e2e-oc.yml `
  -p sapi-oc-e2e-20261024 --profile presentation up -d

$env:SAPI_E2E_FULL_STACK='1'
python -m pytest tests/e2e/test_full_stack_contracts.py -v --no-cov
python -m pytest tests/e2e/test_full_stack_timings.py -v --no-cov
python -m pytest tests/e2e/test_full_stack_browser.py -v --no-cov
$env:SAPI_E2E_FAULT_INJECTION='1'
python -m pytest tests/e2e/test_full_stack_negative.py -v --no-cov
```

`test_full_stack_timings.py` reinicia **solo** `web-v2` al comenzar; por eso se
ejecuta antes que la suite de navegador. `--no-cov` es necesario porque
`pytest.ini` exige 80 % de cobertura global.

## 7. Nota sobre logs intermedios

Los logs `26-final-suite.log` y `28-final-suite.log` conservan fallos de selector
del arnés de navegador (el desplegable de Streamlit quedaba fuera del viewport
tras abrir el expander). Se corrigió con `scroll_into_view_if_needed()` y espera
explícita; la corrida final R1 es `35-final-suite.log`. **No son fallos del
producto.**

Los logs `12`–`34` documentan iteraciones de instrumentación CA4 de R1 (esperas
de asentamiento de CSS, reinicios manuales de `web-v2`). La medición vigente es
la de R2.

## 8. Verificación de integridad

`SHA256SUMS.txt` cubre los 91 archivos de este directorio excepto el propio
manifiesto. El `.gitattributes` local fija `-text` para que el blob de Git
conserve los bytes y los hashes sean válidos en Windows, Linux y macOS.

```powershell
Get-Content artifacts/oc-e2e-20261024/SHA256SUMS.txt | ForEach-Object {
  $h, $p = $_ -split '  ', 2
  $calc = (Get-FileHash -Algorithm SHA256 -LiteralPath $p).Hash.ToLower()
  if ($calc -ne $h) { "MISMATCH $p" }
}
```

Sin salida significa que las 91 entradas coinciden.

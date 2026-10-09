# Corrida de host W0 — Windows/Omen, SHA `df29550`: HARNESS_EVIDENCE_OUTPUT_FAILURE

**No existe un ZIP válido de esta corrida.** Este registro conserva el incidente
como evidencia histórica. Fuente: reporte de Daniel del 2026-10-09 (consola del
bloque PowerShell sobre `df295500ad9fe6f431aa3f7f5d6b05a64d43b4e1`).

## Lo observado (reportado por Daniel)

| Check | Consola |
|---|---|
| selftest | PASS |
| hostfacts | PASS |
| container-smoke-ml | PASS |
| container-smoke-backend | "PASS", pero durante el check empezaron los `DirectoryNotFoundException` sobre `C:\Users\danie\OneDrive\Escritorio\sapi-w0-host-df29550` |
| flyway-integration | `FAIL (no-assertions)`: no se pudieron escribir `flyway-integration.txt` ni `.json` |
| cierre | Fallaron `summary.json`, `manifest.sha256` y `Compress-Archive` |

Clasificación: **HARNESS_EVIDENCE_OUTPUT_FAILURE**. Es una falla del instrumento,
no del backend, de Flyway, de PostGIS ni del producto. Ninguno de los PASS de esta
corrida cuenta como evidencia: sin JSON ni manifest no se pueden verificar, y el de
container-smoke-backend quedó con aserciones incompletas.

## Causa raíz

1. **Disparador externo.** La carpeta de evidencia dejó de existir a mitad de la
   corrida. El script no contiene ninguna línea que borre o mueva `OutDir`: el
   único `Remove-Item` es el del archivo de prueba de selftest. La carpeta estaba en
   `...\OneDrive\Escritorio\`, es decir, dentro del Escritorio sincronizado por
   OneDrive. El bloque además borraba y volvía a crear carpetas con el mismo nombre
   (`foreach ($p in @($Work, $Out, $Zip)) { Remove-Item ... }`). El actor más probable
   es el cliente de OneDrive; no se puede probar sin sus registros.
2. **Defectos del harness que convirtieron eso en resultados engañosos**
   (`scripts/w0_host_checks.ps1` en `df29550`):
   - **L66–68 `Write-Text` y L70–72 `Add-Log`:** escribían directamente con
     `[System.IO.File]` y lanzaban `DirectoryNotFoundException` si faltaba la carpeta.
   - **L76 `Invoke-Native`:** registraba el comando *antes* de ejecutarlo. Si esa
     escritura fallaba, el comando no corría; eso incluye el `docker rm` del
     `finally` (`Remove-Container`, L330). Puede haber quedado un contenedor
     `sapi-w0-backend-*` sin eliminar.
   - **L511–514, `catch` del bucle principal:** volvía a escribir en el log, así que
     relanzaba la excepción y `$r.failures += "exception"` nunca se ejecutaba. Por eso
     container-smoke-backend quedó en "PASS" con aserciones a medias, y
     flyway-integration en "no-assertions" (falló en su primera escritura, dentro de
     `Docker-Ready`, antes de llegar a Flyway).
   - **L534/L539 (`summary.json`, `manifest.sha256`) y L546 (exit):** con
     `ErrorActionPreference = Continue`, los errores de escritura no detenían el
     script, y el código de salida no consideraba la evidencia perdida.

## Reproducción

`reproduction_sandbox.txt` reproduce el incidente en Linux con pwsh 7.4.6 y un
`docker` falso que borra `OutDir` cuando hostfacts ejecuta `docker volume ls`.
- Con el script de `df29550`, hostfacts termina en **PASS** aunque su evidencia se
  perdió, y no quedan ni `summary.json` ni `manifest.sha256` (exit 1).
- Con el script corregido, hostfacts termina en **FAIL (evidence-write-error)**,
  `summary.json` y `manifest.sha256` se escriben, y la corrida sale con
  **exit 3 (HARNESS_EVIDENCE_OUTPUT_FAILURE)**.

Los fallos de `git` y `git_worktree_clean` de esa reproducción vienen del montaje
de prueba (una copia del script fuera del repo y un worktree con cambios sin
commitear), no del incidente.

## Resolución

Ver el commit del fix y `tests/test_w0_host_checks_evidence.py`. La nueva corrida
en el Omen se registra aparte como evidencia de resolución. El bloque nuevo deja la
evidencia fuera de OneDrive (`%LOCALAPPDATA%`), usa nombres únicos por corrida, no
borra nada y solo comprime si el harness sale con evidencia completa.

# Evidencia de host W0 — Windows/Omen, SHA `7618cce` (corrida final de certificación)

| Campo | Valor |
|---|---|
| Fuente | `sapi-w0-host-7618cce-20261009-142010.zip`, generado por `scripts/w0_host_checks.ps1` en el Omen de Daniel (`DANIEL`, Windows 10.0.26200, PowerShell 5.1.26100) |
| Fecha | 2026-10-09, 14:20:14–14:20:46 UTC (selftest y luego los 4 checks; la caché de Docker ya estaba caliente) |
| Clon | `core.autocrlf=false`, HEAD `7618cce00123ac0b3f0c18e2ba8ec6778f19059a`, worktree limpio |
| Carpeta de evidencia | `%LOCALAPPDATA%\sapi-w0\…`, fuera de OneDrive (`outdir_cloud_synced: false`) |
| sha256 del ZIP | `d486fa97404e2e6f61a9dd4103dab843db90c7450f5a4654c35b1000edf4c100` |
| Integridad | `manifest.sha256` 9/9 y `00-selftest/manifest.sha256` 3/3, verificados antes y después de extraer; `harness_evidence.status = PASS`, `write_errors = []` |

| Check | Gate | Resultado | Lo observado |
|---|---|---|---|
| selftest | — | PASS | Docker 29.8.1, Compose 5.5.1, carpeta escribible |
| hostfacts | G7 | PASS | Docker Desktop (16 CPU, ~7,75 GiB para Docker), puertos 8501/8080/8000/5432 libres, `sapi_pgdata` ausente (solo listado), `core.autocrlf=false`, worktree limpio, JDK 21.0.12, Python 3.14.7, 418,9 GB libres, ExecutionPolicy de proceso Bypass |
| container-smoke-ml | G3 | PASS | `/health` 200 (`prototype_model_d_v1`); `POST /predict` 200, 50 celdas, `forecast_time` 2026-09-01T00:00:00Z, fingerprint `33c2eacc49bd0cc130928b5bd182ec523e63614f0e3dd97a129a8d4657f231ff`, `relative_rank`, `scientific_model_validation=false`, uid 10001 |
| container-smoke-backend | G4 | PASS | `/health` 200 `{"status":"UP"}`, uid 10001 |
| flyway-integration | G5 | PASS | Ver detalle abajo |

**Detalle de G5 (Flyway real).** Flyway 12.4.0 sobre `postgis/postgis:15-3.4` limpio:
- `migrate`: exit 0, 3 aplicadas;
- `validate` e `info`: exit 0;
- segundo `migrate`: exit 0, 0 pendientes;
- historial: literal `001:true,002:true,003:true`, derivado de `db/migration`, equivalente a `1:true,2:true,3:true` normalizado;
- tablas `celdas_geom`, `ejecuciones` y `predicciones_celda`; 50 celdas; 0 geometrías inválidas.

La contraseña desechable de PostGIS aparece enmascarada (`POSTGRES_PASSWORD=***`).

`sql-migration-validation` (G6) no se repitió en esta corrida. Su PASS es el de
`../43c17fd/`, y sigue vigente porque ni `db/` ni
`scripts/sapi58_migration_integration.ps1` cambiaron entre `43c17fd` y `7618cce`
(`merge_gate.py --evidence-valid 43c17fd --job sql-migration-validation` → VIGENTE).

Historia de las corridas de host de W0:

| SHA | Carpeta | Resultado |
|---|---|---|
| `43c17fd` | `../43c17fd/` | flyway FAIL = HARNESS_FALSE_NEGATIVE (se conserva) |
| `df29550` | `../df29550/` | HARNESS_EVIDENCE_OUTPUT_FAILURE, sin ZIP (se conserva) |
| `7618cce` | esta carpeta | todo PASS, evidencia de resolución |

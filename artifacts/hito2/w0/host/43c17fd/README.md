# Evidencia de host W0 — Windows/Omen, SHA `43c17fd` (primera corrida, histórica)

| Campo | Valor |
|---|---|
| Fuente | `sapi-w0-host-43c17fd.zip` generado por `scripts/w0_host_checks.ps1` en el Omen de Daniel (`DANIEL`, Windows 10.0.26200, PowerShell 5.1.26100) |
| Fecha | 2026-10-09, 00:12–00:15 UTC |
| Clon | `core.autocrlf=false`, HEAD `43c17fd9cc8614fa70e27e03aa1ff49d2462aed6` |
| sha256 del ZIP | `52ca87a51a896367de7d580ca575ea9b26b70295824206f2e9efc1b2038b914e` |
| Integridad | Los dos `manifest.sha256` (12/12 y 3/3) verificados antes y después de extraer; `extracted/` contiene los mismos bytes del ZIP, solo con `\` → `/` en las rutas |

## Resultado tal como se generó (no se edita)

| Check | Resultado | Lo observado |
|---|---|---|
| selftest | PASS | Docker 29.8.1, Compose 5.5.1, carpeta de evidencia escribible |
| hostfacts | PASS | Docker Desktop (16 CPU, ~8,3 GB), puertos 8501/8080/8000/5432 libres, `sapi_pgdata` ausente (no se tocó), `core.autocrlf=false`, worktree limpio, JDK 21.0.12, Python 3.14.7, 428 GB libres |
| container-smoke-ml | PASS | `/health` 200; `POST /predict` 200, 50 celdas, `forecast_time` 2026-09-01T00:00:00Z, fingerprint `33c2eacc49bd…`, `relative_rank`, `scientific_model_validation=false`, uid 10001 |
| container-smoke-backend | PASS | `/health` 200 `{"status":"UP"}`, uid 10001 |
| flyway-integration | **FAIL** (`flyway_schema_history`) | Ver la clasificación abajo |
| sql-migration-validation | PASS | `sapi58_migration_integration.ps1`: todas las aserciones y pruebas negativas en PASS |

## Clasificación del FAIL de Flyway: HARNESS_FALSE_NEGATIVE

La evidencia (`extracted/flyway-integration.{json,txt}`) muestra que Flyway OSS
12.4.0 sobre PostgreSQL 15.8 hizo todo lo esperado:

- `migrate`: exit 0, "Successfully applied 3 migrations to schema "public", now at version v003".
- `validate`: exit 0, "Successfully validated 3 migrations".
- `info`: exit 0, las versiones 001, 002 y 003 en estado "Success".
- Segundo `migrate`: exit 0, "Schema "public" is up to date. No migration necessary." (0 aplicadas).
- Tablas `celdas_geom`, `ejecuciones` y `predicciones_celda` presentes; 50 celdas; 0 geometrías inválidas o con SRID ≠ 4326.

La única aserción en FAIL compara la columna `flyway_schema_history.version`:

| Esperado (checker) | Observado (Flyway) |
|---|---|
| `1:true,2:true,3:true` | `001:true,002:true,003:true` |

**Causa raíz:** Flyway guarda la versión tal como aparece en el nombre del archivo,
con los ceros a la izquierda (`V001__…` → `001`). El checker de `43c17fd`
(`scripts/w0_host_checks.ps1`, check `flyway-integration`) tenía escrita a mano
una expectativa sin ceros. Es un falso negativo del instrumento de medición, no
una falla de Flyway, de PostGIS ni de las migraciones V001–V003 (que no se
modificaron).

**Resolución:** el checker se corrige en el commit siguiente: la versión esperada
se deriva de `db/migration/V*__*.sql` y se compara semánticamente, con tests de
regresión. Como el arreglo cambia `w0_host_checks.ps1`, se vuelven a ejecutar en el
Omen, sobre el nuevo SHA, todos los checks que dependen de ese script (selftest,
hostfacts, container-smoke-ml, container-smoke-backend y flyway-integration). Esa
corrida se registra aparte como evidencia de resolución. `sql-migration-validation`
no se repite: usa `scripts/sapi58_migration_integration.ps1` y `db/migration`, que
no cambian, así que su PASS sigue vigente.

Nota: el log de `flyway-integration` contiene la contraseña desechable
`sapi-w0-local-test` del contenedor PostGIS de prueba (tmpfs, sin puertos,
eliminado al terminar). No es una credencial real; desde el commit siguiente el
script ya no la imprime.

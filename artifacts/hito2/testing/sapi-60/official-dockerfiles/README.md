# SAPI-60 — validación con Dockerfiles oficiales (sin shim)

Esta carpeta **no** es la corrida del sandbox que usó
`sandbox-shims/Dockerfile.ml-api.sandbox` y `--skip-build`. Tampoco es el PC
Omen de Daniel. Es un host Linux limpio (x86_64, kernel de contenedor) donde
los mirrors de Debian responden, con Docker 29.1.3 y Compose 2.40.3.

| Campo | Valor |
|---|---|
| SHA | `0d5f13cfd02ae72bd73cdd36780cc0d6762cb59c` |
| Rama | `feat/SAPI-60-docker-compose-v2` |
| Base | `origin/main` `736e5b45c07e4104d3ba841d6a11c1a12c47d7fa` (sin cambios respecto de lo esperado) |
| Fecha | 2026-10-11 (UTC) |
| Comando | `python scripts/compose_v2_preflight.py --out-dir ../sapi60-evidence` |
| Build | **oficial**: `Dockerfile.ml-api`, `services/backend/Dockerfile`, imagen `postgis/postgis:15-3.4`. Sin `--skip-build`, sin Dockerfile sustituto |
| Veredicto | **PREFLIGHT PASS 28/28** (`preflight.json`) |

## Ajuste de host, no del producto

La primera ejecución construyó las imágenes oficiales (`compose.build` exit 0)
y falló en `up`: el backend no llegaba a `db-v2:5432` (timeout). Desde otro
contenedor de la misma red el TCP también expiraba, mientras el puerto
publicado en 127.0.0.1 sí aceptaba conexiones. Causa: `iptables-legacy` tenía
`FORWARD` en `DROP` y no aceptaba el bridge de Compose (nftables sí). Se cambió
solo la política del host a `ACCEPT`. No se modificó el repositorio para
sortearlo. La corrida de esta carpeta es la repetición posterior a ese ajuste.

## CA

| CA | Resultado | Evidencia |
|---|---|---|
| CA1 | PASS | `backend` 127.0.0.1:8080, `ml-api` 127.0.0.1:8000, `db-v2` 127.0.0.1:5432, los tres running |
| CA2 | PASS | los tres `healthy`; backend `{"status":"UP"}` 200; ML `status=ok`, `model_version=prototype_model_d_v1` 200; `pg_isready` accepting connections. Se repite tras `down`/`up` |
| CA3 | PASS | `SAPI_DB_PASSWORD` exigido con `:?` (sin default); `.env.example` usa el placeholder de desarrollo; `.env` está en `.gitignore` y no se versiona. Cubierto además por `tests/test_compose_v2.py` |
| CA4 | PASS | `down` sin `-v` y `up` de nuevo: 1 ejecución y 50 predicciones siguen ahí; Flyway 001–003 sin cambios (`ca4.data_survives_down_up`) |
| CA5 | PASS | README, Opción A: `.env` desde el ejemplo, `docker compose up --build`, URLs, health, ranking, psql, `down` (conserva volúmenes) y el aviso de `down -v` |
| CA6 | PASS en este host | `checkout.clean` + `docker compose build` exit 0 de los Dockerfiles del repositorio + la pila opera con Python/Java/PostGIS **dentro** de las imágenes. El host tenía Python y JDK instalados; el stack no los usa |

## Cadena real (modo reproducible, ADR-009)

No se fabricaron stores CURRENT. `SAPI_REPRODUCIBILITY_MODE=1` en `ml-api`.

- Ranking: HTTP 200, 50 celdas, ranks 1..50, `score_semantics=relative_rank`, `scientific_model_validation=false`, `forecast_time=2026-09-01T00:00:00Z`, `model_version=prototype_model_d_v1`.
- Passthrough: el cuerpo de `GET /api/v1/ranking` es idéntico al de `POST /predict` (sha256 `f55de2c47d55cc5ad34ed0dd504cdcf66592efed0ff4f365feac8331022d3a2f`).
- Persistencia: 0→1 ejecución, 0→50 `predicciones_celda`, orden igual a la respuesta.
- Idempotencia: repetir los mismos insumos deja 1 ejecución y 50 filas, misma respuesta.
- `db/queries/latest_ranking.sql` por psql: 50 filas, sin problemas (`latest_ranking_psql.txt`).
- Flyway: `001:true`, `002:true`, `003:true`. Geometrías: `50|true|4326|4326`.
- El score es un ranking relativo entre las 50 celdas. No es una probabilidad calibrada ni una alerta oficial.

## Otras comprobaciones en el mismo SHA

| Check | Resultado |
|---|---|
| `freeze_check` (clon de un solo worktree, con `ls-remote`) | PASS (`freeze_check.txt`) |
| `./mvnw -B verify` | BUILD SUCCESS. Surefire 127 tests, 0 failures, 4 skipped. Failsafe `RankingPersistenceIT` 11 tests, 0 failures |
| `pytest` completo, sin `.env` en el checkout | **1744 passed, 114 skipped, 0 failed**, cobertura 84,55 % (gate 80 %). Un `.env` local cambia `SAPI_DATA_MODE` y dispara WS-016; por eso la corrida de regresión se hizo sin ese archivo |
| `merge_gate.py --job container-smoke` | ML **PASS** (build oficial de `Dockerfile.ml-api`, `/health` 200, `/predict` 50 celdas, fingerprint del Modelo D, uid 10001). Backend **FAIL**: la imagen sale con código 1 porque Flyway/Hikari no tienen Postgres (`connection refused` a localhost). El harness W0.3 hace `docker run` del jar solo, sin base. Con Compose (esta HU) el mismo jar queda `healthy`. No se tocó `merge_gate.py` |

El proyecto Compose de la prueba es `sapi60-preflight`. Al terminar, el script ejecuta `down -v` solo sobre ese proyecto.

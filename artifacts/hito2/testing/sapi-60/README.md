# Evidencia SAPI-60 — Entorno reproducible con Docker Compose (PR-4)

| Campo | Valor |
|---|---|
| HU | SAPI-60 · S2-07 — Entorno reproducible con Docker Compose (Spring Boot + FastAPI + PostgreSQL) |
| SHA de código | `150837ed2b98b1bcd1e87492def1bc5c614337b4` (rama `feat/SAPI-60-docker-compose-v2`, base `main` `736e5b4`) |
| Fecha | 2026-10-10 (UTC) |
| Entorno | Sandbox Linux x86_64 en la nube, Docker 29.8.2, Docker Compose v5.6.0 |
| Herramienta | `scripts/compose_v2_preflight.py` (CA → comando → resultado; proyecto Compose aislado `sapi60-preflight`) |
| Veredicto del preflight | **PASS, 27/27 checks** (`preflight/preflight.json`) |

## Cómo se obtuvo

1. Clon nuevo de la rama desde GitHub en `150837e`. `data/raw` y `data/processed`
   quedan vacíos, y el único archivo ignorado es `.env`.
2. `cp .env.example .env`, sin cambiar ningún valor (flujo del README).
3. Imágenes construidas desde ese clon con `--no-cache` (ver "Ajustes del sandbox").
4. Desde el clon:
   `python scripts/compose_v2_preflight.py --out-dir <fuera del repo> --skip-build`.
   El preflight:
   - borra el proyecto `sapi60-preflight` y arranca de cero;
   - ejecuta `up -d --wait`, revisa estado y health, Flyway, ranking, persistencia, idempotencia y psql;
   - hace `down` sin `-v` y vuelve a hacer `up`;
   - al final ejecuta `down -v`, solo sobre ese proyecto.

Para reproducirlo en un equipo con acceso normal a internet:

```bash
git clone https://github.com/DanielCortezF002/S.A.P.I-Sistema-de-Prediccion-de-Incendios.git
cd S.A.P.I-Sistema-de-Prediccion-de-Incendios && git checkout feat/SAPI-60-docker-compose-v2
cp .env.example .env
python scripts/compose_v2_preflight.py --out-dir ../sapi60-evidence   # sin --skip-build: construye con docker compose build
```

## Criterios de aceptación

| CA | Comando | Resultado |
|---|---|---|
| CA1. `docker-compose up` levanta Spring Boot (8080), FastAPI (8000) y PostgreSQL/PostGIS (5432) | `docker compose config --services`, `up -d --wait`, `ps --format json` | Servicios por defecto: `backend`, `db-v2`, `ml-api`. Los tres `running`, publicados en `127.0.0.1:8080`, `127.0.0.1:8000` y `127.0.0.1:5432`. `GET /api/v1/ranking` → 200 |
| CA2. Health checks en todos los servicios | `ps` (Health), `GET /health` del backend y del ML, `pg_isready -h 127.0.0.1` | Los tres `healthy`. Backend 200 `{"status":"UP"}`; ML 200 `status=ok`, `model_version=prototype_model_d_v1`; base `accepting connections`. Se repite después del `down`/`up` |
| CA3. Variables en `.env.example`, sin secretos hardcodeados | `tests/test_compose_v2.py` (gate `python`) | `SAPI_DB_PASSWORD` sin valor por defecto (`:?`). Cada variable de la ruta v2 está en `.env.example`, la contraseña de ejemplo es un placeholder y `.env` lo ignora git |
| CA4. Volumen persistente para PostgreSQL | `down` (sin `-v`) + `up -d --wait` + conteos | Antes 1 ejecución y 50 filas, después 1 y 50. `flyway_schema_history` no cambia (`001`–`003`) |
| CA5. README con instrucciones actualizadas | Lectura del README (Opción A) | Requisitos, `.env`, comando, URLs, health, ranking, psql, `down` y reset (solo v2 o total) |
| CA6. Funciona en entorno limpio | Clon nuevo + `cp .env.example .env` + build + preflight | **PARCIAL.** Checkout limpio (`checkout.clean`) y Flyway V001→V003 desde un volumen vacío, pero con imágenes construidas con ajustes de sandbox (ver abajo). Falta el build completo en el host |

**Integración de la cadena (`preflight.json`):**
- `ranking.backend`: 200, 50 celdas, ranks 1..50, `score_semantics=relative_rank`,
  `scientific_model_validation=false`, `forecast_time` 2026-09-01T00:00:00Z y
  `X-Request-Id` devuelto.
- `ranking.passthrough`: los bytes de `GET /api/v1/ranking` son idénticos a los de
  `POST /predict` del ML (SAPI-57).
- `ranking.reproducible_fixture`: sha256 `f55de2c4…3a2f`, igual al fixture versionado
  `services/backend/src/test/resources/ml/predict-reproducible-2026-09-01.json`
  (modo reproducible, ADR-009).
- `persistence.write_through`: se pasa de 0 a 1 ejecución y de 0 a 50 predicciones,
  con el mismo orden de celdas que la respuesta (SAPI-59 dentro del Compose).
- `backend.logs`: Flyway "Successfully applied 3 migrations" y un evento
  `ml_predict` con `outcome=ok` y `ml_http_status=200`
  (`preflight/backend_log_excerpt.txt`).

El score es un ranking relativo entre las 50 celdas. No es una probabilidad de
incendio ni una alerta oficial.

## Evidencia complementaria de SAPI-59 (no reabre SAPI-59)

- **`db/queries/latest_ranking.sql` por psql dentro de `db-v2`.** Devuelve 50 filas
  de la ejecución que persistió el backend, con rank 1..50 ascendente, score no
  creciente y el mismo orden de celdas que la respuesta
  (`preflight/latest_ranking_psql.txt`, check `sapi59.latest_ranking_psql`).
- **Idempotencia** (`persistence.idempotent_replay`): repetir el ranking da la misma
  respuesta y no cambian los conteos (1 y 50). La propiedad del CA4 de SAPI-59,
  "una misma ejecución no se duplica", se implementa en el servicio JDBC
  transaccional y no en un script aparte. Ver la nota en
  `docs/hito2/requerimientos-sprint2.md`.
- **ITs reales con Docker en este sandbox:** `./mvnw -B verify` sobre `150837e`.
  - Surefire: 127 tests, 0 failures, 0 errors, 4 skipped.
  - Failsafe, `RankingPersistenceIT`: 11 tests, 0 failures, 0 errors, 0 skipped,
    con Testcontainers 2.0.5 sobre `postgis/postgis:15-3.4`.
  - CA3: muestras `[2,2,2,1,1,1,1,1,1,1]` ms, máximo 2 ms frente a un umbral de 1000 ms.
  - Ver `backend_verify_with_its/`.

## Ajustes del sandbox (declarados, no versionados en el código)

Este entorno cloud no tiene acceso normal a internet.
- La política de egress bloquea los mirrors de Debian.
- El HTTPS sale por un proxy que vuelve a terminar el TLS.
- Maven Central responde 429 a la IP compartida.

Por eso:

1. **Build versionado:** `docker compose build` con los Dockerfiles versionados
   falla en el sandbox por egress (`builds/compose_build_committed_attempt.txt`).
   No es un defecto del cambio.
2. **Backend:** se construyó con el `services/backend/Dockerfile` versionado. Su
   etapa de build usó una imagen Maven local con la CA del proxy y un mirror de
   Maven Central (`sandbox-shims/maven-build-stage.Dockerfile`,
   `sandbox-shims/maven-settings.xml`). La etapa final es el
   `eclipse-temurin:21-jre` oficial, sin cambios. Build en 127 s
   (`builds/final_backend_build.txt`).
3. **ML:** con autorización de Daniel se usó una imagen **sustituta**
   (`sandbox-shims/Dockerfile.ml-api.sandbox`). Tiene el mismo código, el mismo
   Modelo D, el mismo snapshot de Hito 1 y los mismos requirements, instalados
   como wheels. No incluye el `apt-get` de GDAL, y `libexpat` se copia de la
   imagen PostGIS. Build en 200 s (`builds/final_ml_build.txt`). **No prueba el
   build de `Dockerfile.ml-api`.** Su ranking coincide byte a byte con el fixture
   reproducible de SAPI-57.

**Pendiente en el host** (para cerrar CA6 y refrescar `container-smoke`):
- el preflight completo **sin** `--skip-build`, desde un clon limpio y en Windows;
- `python scripts/merge_gate.py --job container-smoke`.

## Revisión adversarial (acotada a SAPI-60)

La revisión usó 4 lentes:
- secretos y configuración;
- red, arranque y healthchecks;
- volúmenes, pérdida de datos y legacy;
- entorno limpio, docs y preflight.

**Resultado:** 22 hallazgos, ninguno BLOCKER ni MAJOR.

**Corregidos en `150837e`:**
- red propia `sapi-v2-net`;
- `SPRING_FLYWAY_FAILONMISSINGLOCATIONS=true` (verificado: sin la carpeta de
  migraciones, el backend no arranca);
- healthchecks que no pasan por un proxy inyectado;
- un mensaje de `:?` que no invita a reemplazar un `.env` existente;
- en el preflight: arranque desde un volumen nuevo con conteos verificados,
  `-f` fijo, check de checkout limpio, redacción de secretos de `.env` y la
  carpeta padre no se redacta si es la raíz;
- notas de README, deploy, notebooks y ADR-008;
- tests más estrictos.

**Refutado:** "`docker compose down` no detiene los servicios de Hito 1". Con
Compose v5.6.0, `down` sin profiles sí detiene y elimina esos contenedores, y
conserva los volúmenes.

**Fuera de alcance:** puertos fijos del preflight (CA1 exige los puertos por
defecto) y el nombre de volumen que usa `w0_host_checks.ps1` (preexistente).

**Riesgo documentado:** `docker compose down -v` borra todos los volúmenes del
archivo, incluido `sapi_pgdata` de Hito 1 aunque su profile no esté activo.
El README indica cómo reiniciar solo la base v2.

## Saneamiento

- Rutas reemplazadas por marcadores (`[repo]`, `[clean-clone]`, `[scratch]`, `[home]`).
- Dirección del proxy del sandbox reemplazada por `[proxy-sandbox]`.
- Sin bloques `<properties>` de surefire, sin opciones de la JVM, `hostname` → `[host]`.
- Sin `.env`, contraseñas, tokens ni claves.

El grep de redacción sobre esta carpeta queda vacío. Los registros que el preflight escribe como `.log` (y los logs de build) se versionan como `.txt`, porque `.gitignore` excluye `*.log`; el contenido es el mismo.
`ranking_response.json` se guarda en bytes crudos: su sha256 es el que registra
`preflight.json`.

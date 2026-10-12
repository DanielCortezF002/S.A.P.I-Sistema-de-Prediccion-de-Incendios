# SAPI-43 — evidencia preparatoria

TEST_FIXTURE_ONLY
OPERATIONAL_CURRENT_USED=NO
REAL_DAILY_PIPELINE_PASS=NO
CURRENT_OPERATIONAL_PASS=NO

Corrida de mecanismo sobre fixtures. No usa punteros CURRENT operacionales,
no llama al backend real y no declara una corrida diaria real.
`docker compose config` no arranca contenedores.

## Checkout

- Rama: `feat/SAPI-43-daily-pipeline-prep`
- Base de la rama: `64c37f21492041db62adad42a3a574a22918b7cf` (`origin/main`)
- Delta correctivo desde: `6ab30f7bdc7a535a3eea3be9584509b81a29bf40`
- Intérprete de esta corrida de pytest: Python 3.12.3
- Imagen del servicio ML: `Dockerfile.ml-api` usa `python:3.14-slim`
- Directorio: `/workspace`
- Fecha: 2026-10-12

No había un `docker-compose.operational.yml` en este checkout, en el
historial ni en las otras ramas locales. El overlay de este delta sigue
la decisión 2 de `docs/adr/ADR-009.md`: modo operacional aparte, datos en
solo lectura y volumen de base distinto.

## Comandos y resultados

Los `addopts` de `pytest.ini` (`--cov-fail-under=80`) no se aplicaron.

```text
python3 -m pytest tests/test_sapi43_daily_run.py tests/test_sapi43_operational_compose.py -o addopts= --tb=short -p no:cacheprovider
40 passed in 0.40s
exit 0
```

De esos 40, `tests/test_sapi43_daily_run.py` aporta 34 (incluye 8 casos
negativos de procedencia) y `tests/test_sapi43_operational_compose.py`
aporta 6, entre ellos `docker compose config` del archivo base y del
overlay.

```text
python3 -m pytest tests/test_backend_client.py tests/test_compose_v2.py -o addopts= --tb=line -q -p no:cacheprovider
213 passed in 0.21s
exit 0
```

```text
python3 -m pytest tests/test_architecture.py -o addopts= --tb=no -q -p no:cacheprovider
4 failed, 4 passed in 0.82s
exit 1
```

Los 4 fallos son sondas en subproceso. Se detienen al importar módulos
que esta VM no tiene (`geopandas` en `app/app.py` y en
`src/procesamiento/raw_parser.py`). Los 4 tests estáticos del mismo
archivo pasaron. No se reclama PASS de `tests/test_architecture.py`.

Lint de los archivos Python de este delta:

```text
flake8 --max-line-length=100 --extend-ignore=E203,W503 scripts/sapi43_daily_run.py tests/test_sapi43_daily_run.py tests/test_sapi43_operational_compose.py
LINT_OK
```

## Qué cubre el fixture

- Puntero ausente o ilegible: salida 2, sin GET.
- Un objeto JSON vacío es legible. No se exigen campos de SAPI-71.
- Sin `firms_origin=current` el ranking no se acepta. Eso incluye ausencia,
  `reproducibility`, `baseline` y metadata FIRMS incompleta.
- `scientific_model_validation=true` no se acepta.
- HTTP 500 es salida 4. No se presenta como prueba de un fallo de PostGIS.
- El puntero DMC legible no demuestra que el almacén versionado se haya
  consumido. El contrato no trae un origen DMC.
- El Compose base sigue en `SAPI_REPRODUCIBILITY_MODE=1` y
  `sapi_v2_pgdata`. El overlay pone el modo en `0` solo en `ml-api`,
  monta `./data` en `/app/data` como solo lectura y usa
  `sapi_v2_operational_pgdata`.

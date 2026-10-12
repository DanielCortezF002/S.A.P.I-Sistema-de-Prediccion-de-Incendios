# SAPI-43 — evidencia preparatoria

TEST_FIXTURE_ONLY
OPERATIONAL_CURRENT_USED=NO
REAL_DAILY_PIPELINE_PASS=NO
CURRENT_OPERATIONAL_PASS=NO

Corrida de mecanismo sobre fixtures. No usa punteros CURRENT operacionales,
no llama al backend real y no declara una corrida diaria real.

## Checkout

- Rama: `feat/SAPI-43-daily-pipeline-prep`
- Base: `64c37f21492041db62adad42a3a574a22918b7cf` (`origin/main`)
- Intérprete de esta corrida: Python 3.12.3 (el contenedor del proyecto pide 3.11; aquí no había 3.11)
- Directorio: `/workspace`
- Fecha: 2026-10-12

## Comandos y resultados

Los `addopts` de `pytest.ini` (`--cov-fail-under=80`) no se aplicaron: esta
corrida no ejecuta la suite completa ni el gate de cobertura.

```text
python3 -m pytest tests/test_sapi43_daily_run.py -o addopts= --tb=short -p no:cacheprovider
26 passed in 0.19s
exit 0
```

```text
python3 -m pytest tests/test_backend_client.py -o addopts= --tb=no -q -p no:cacheprovider
188 passed in 0.16s
exit 0
```

```text
python3 -m pytest tests/test_architecture.py -o addopts= --tb=no -q -p no:cacheprovider
4 failed, 4 passed in 0.77s
exit 1
```

Los 4 fallos son sondas en subproceso que no llegan a evaluar el entrypoint
nuevo. Se detienen al importar módulos que esta VM no tiene instalados
(`geopandas` en `app/app.py` y en `src/procesamiento/raw_parser.py`). Los 4
tests estáticos del mismo archivo pasaron. No se reclama PASS de
`tests/test_architecture.py`.

Lint de los archivos nuevos, antes de la corrida de pytest:

```text
black --line-length 100 scripts/sapi43_daily_run.py tests/test_sapi43_daily_run.py
flake8 --max-line-length=100 --extend-ignore=E203,W503 scripts/sapi43_daily_run.py tests/test_sapi43_daily_run.py
LINT_OK
```

## Qué cubre el fixture

- Puntero ausente o ilegible: salida 2, sin GET.
- Objeto JSON vacío: se considera legible y no se exigen campos de SAPI-71.
- GET único a `/api/v1/ranking` con timeout explícito y sin `forecast_time`.
- HTTP 422/502/503/504, timeout y conexión rechazada: salida 3.
- HTTP 500: salida 4. Spring usa ese código tanto para un fallo de
  persistencia como para un 500 del servicio de ranking.
- `scientific_model_validation=true` no se acepta.
- Misma clave natural en dos respuestas 200: el entrypoint no inserta; el
  contrato esperado contra `RankingRepository` (`ON CONFLICT … DO NOTHING`)
  y V002 es 0 ejecuciones nuevas. No se contaron filas en PostGIS.

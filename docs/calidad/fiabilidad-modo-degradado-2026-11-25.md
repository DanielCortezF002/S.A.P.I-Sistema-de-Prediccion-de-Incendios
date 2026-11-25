# Fiabilidad · punto de quiebre y modo degradado · 25-11-2026

- Stack: `sapi-h3-518c0b5`, código `518c0b58e6b229317f51b1da56ac23346dc2ef74`. Rama `DanielCortezF002/plan-25-11-c4-c5`, sin push.
- Hardware: AMD Ryzen AI 7 350 (8 núcleos, 16 hilos), 31 GB de RAM, Windows 11 Home 10.0.26200. Ejecutado en el computador local, no en ambiente desplegado.
- Regla de hoy: **no se paró ni reinició ningún servicio.** `docker ps` antes y después de la observación en vivo muestra los mismos 8 contenedores Up ([antes](evidencia/2026-11-25-fiabilidad/docker-ps-antes.txt), [después](evidencia/2026-11-25-fiabilidad/docker-ps-despues.txt)). Lo que solo se puede observar parando algo queda **NO_EVALUABLE** en el stack.
- pytest: solo 3 archivos, en un contenedor desechable de la imagen `sapi-h3-518c0b5-ml-api` (`--rm --network none`, repo en solo lectura), con `--ignore=tests/test_f1_ca8_operational_overlay_dynamic.py` y `-o addopts=""` (sin el gate de cobertura, que no aplica a un subconjunto). La prueba ignorada no se modificó.

## Resumen

| ID | Condición | En el stack, hoy | En el código (pruebas, hoy) | Estado |
|---|---|---|---|---|
| F-1 | Meteorología faltante (DMC «NO DISPONIBLE») | **Observado.** El ranking se sigue entregando y la falta se declara | Pasan las pruebas del estado sin datos | **Modo degradado observado** |
| F-2 | ml-api caída | No se paró | Pasa la prueba de la UI ante 503/504 `upstream_unavailable`. Las pruebas Java del backend no se corrieron hoy | **NO_EVALUABLE en el stack.** Lo ejecuta Daniel con el procedimiento 6b |
| F-3 | Backend caído o lento (vista de la UI) | No se paró | Pasan las pruebas de conexión rechazada, timeout de lectura y backend caído | **NO_EVALUABLE en el stack** |
| F-4 | Base de datos caída | No se paró | No se corrió `RankingDatabaseUnavailableIT` | **NO_EVALUABLE.** Histórico: D-05, NO GO a 3.000 y 5.000 ms (`docs/pruebas/plan-sprint3.md` en `9657bad`) |
| F-5 | Punto de quiebre bajo carga | Requiere carga creciente; k6 no tiene luz verde | — | **NO_EVALUABLE hoy** |

## F-1 · Meteorología faltante

**Qué pasa en el stack (verificado hoy).**

- Interfaz, recorrido Edge de hoy a las 04:29 UTC ([04-datos.txt](../../reports/orden-25-11-h3/recorrido-edge/04-datos.txt), líneas 33–42 y 121–123): la barra DMC muestra «ÚLTIMA OBSERVACIÓN DMC · RODELILLO (330007) · NO DISPONIBLE», cada campo dice «sin dato en la última ingesta», el motivo es «sin lectura: no hay observación ingerida de Rodelillo», y se aclara que «La meteorología DMC reciente no se utilizó para calcular el ranking histórico». La ficha de la celda dice «sin dato: el ranking histórico no trae la meteorología que usó (campo fuera del contrato API v0)». La cabecera marca «DATOS HISTÓRICOS · última observación hace 2044 h». El ranking de 50 celdas sigue visible. La captura del paso 4 es la misma del paso 3 (ver la corrección B-3 en la MATRIZ).
- API, hoy a las 11:17:14 UTC, **una sola** petición `GET /api/v1/ranking` ([observacion-en-vivo.json](evidencia/2026-11-25-fiabilidad/observacion-en-vivo.json), guion [observacion_en_vivo.py](evidencia/2026-11-25-fiabilidad/observacion_en_vivo.py)): 200, 50 celdas, `freshness = "DATOS HISTÓRICOS / DESACTUALIZADOS"`, `age_hours = 2051,29`, `weather_timestamp = 2026-09-01T00:00:00Z`, `score_semantics = relative_rank`, `scientific_model_validation = false`. Antes, los 3 `/health` respondieron 200. Tardó 7.365 ms; es una sola petición y **no es una medición de rendimiento ni de KPI-03**.

**Qué cubren las pruebas (verificado hoy, nivel código).** [pytest-degradado.txt](evidencia/2026-11-25-fiabilidad/pytest-degradado.txt): 128 de 128 pasan, 11:15:45–11:16:55 UTC (es la segunda corrida; la primera, 11:14:29–11:15:45 UTC, también dio 128 pasan, pero no guardé su salida completa). Las que tocan F-1: `test_observation_without_ingested_file_is_not_available`, `test_kpi_strip_v0_declares_meteo_unavailable_and_counts_cells`, `test_sapi86_panel_sin_meteo_da_motivo_y_no_texto_legado` y `test_sapi86_barra_dmc_sin_datos_da_motivo`.

**Lectura.** Con la meteorología faltante, SAPI no se cae ni rellena valores: entrega el ranking histórico y declara la falta y su motivo. **Límite:** el ranking del modo reproducible se calcula con el snapshot congelado del 01-09-2026. Con esta evidencia no se puede afirmar qué pasaría en una corrida operacional en la que falte la meteorología de entrada al modelo: eso no se observó.

## F-2 · ml-api caída

**NO_EVALUABLE en el stack:** observarla exige detener el ml-api. La respuesta esperada (`503 upstream_unavailable`) y cómo comprobarla están en [PROCEDIMIENTO-6B-RESILIENCIA-ML-API-H3.md](../../reports/orden-25-11-h3/PROCEDIMIENTO-6B-RESILIENCIA-ML-API-H3.md). **No se ejecutó; lo hace Daniel.**

Nivel código (verificado hoy): `services/backend/src/main/java/cl/sapi/backend/ranking/RankingError.java:14` define `UPSTREAM_UNAVAILABLE(503, "upstream_unavailable", …)`. `test_apptest_backend_http_error_shows_controlled_message[503]` y `[504]` pasan: la UI muestra el código y `upstream_unavailable`, no muestra el mensaje remoto y no pinta un ranking. Las pruebas Java (`RankingMlUnavailableTests`) existen pero no se corrieron hoy.

## F-3 · Backend caído o lento, visto desde la UI

**NO_EVALUABLE en el stack.** Nivel código (verificado hoy): pasan `test_connection_refused_is_a_controlled_error`, `test_read_timeout_is_a_controlled_error` y `test_apptest_backend_down_shows_controlled_message` (mensaje controlado, sin `127.0.0.1` ni `Traceback`, sin «Grupo prioritario»).

## F-4 · Base de datos caída

**NO_EVALUABLE.** No se paró la base ni se corrió la prueba Testcontainers. Histórico: D-05 (fallo rápido con la base caída o el pool saturado) figura como NO GO a 3.000 ms y a 5.000 ms en `docs/pruebas/plan-sprint3.md` (`9657bad`).

## F-5 · Punto de quiebre

**NO_EVALUABLE hoy.** Encontrar el punto de quiebre exige carga creciente sobre `GET /api/v1/ranking`, y k6 no tiene luz verde. El único escenario de carga declarado (N = 2 constante, [eficiencia-k6-2026-11-25.md](eficiencia-k6-2026-11-25.md)) no busca el quiebre. Histórico, no verificable en esta rama: `docker-compose.yml` comenta que con un solo proceso de uvicorn `/predict` hacía cola y L1/L2 superaban el p95, y con dos pasaban; el acta que cita (`ACTA_OCC_S3_A4_CLEAN_REPRODUCIBILITY_R1.md`) no está en esta rama.

## Clasificación

- **Verificado hoy:** F-1 en el stack (madrugada y 11:17 UTC); las 128 pruebas; `docker ps` sin cambios; la línea de `RankingError.java`.
- **Histórico:** D-05 (`9657bad`); el comentario del compose sobre los workers.
- **Pendiente:** F-2 (procedimiento 6b, Daniel); F-3 y F-4 en el stack; F-5 (requiere una corrida de carga escalonada con su propia declaración y luz verde); las pruebas Java del backend.

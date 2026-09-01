# Matriz de riesgo — S.A.P.I. (Hito 1)

**Proyecto:** Sistema de Alerta y Predicción de Incendios Forestales  
**Última actualización:** 31-08-2026  
**Responsable:** Equipo S.A.P.I.

Esta matriz documenta riesgos materializados, mitigaciones aplicadas con evidencia verificable, y riesgos abiertos con decisión explícita de gestión. No sustituye el registro de Jira; es el artefacto de evidencia para la rúbrica del Hito 1.

---

## Riesgos cerrados

| Campo | Contenido |
|-------|-----------|
| **ID** | R-NASA-FIRMS-01 |
| **Riesgo** | La API NASA FIRMS rechazaba solicitudes por formato incorrecto: el código usaba querystring (`?area=...&dayrange=...`) en lugar de la ruta posicional oficial, produciendo HTTP 400 (*Invalid area* / *Invalid day range*). |
| **Impacto** | Ingesta diaria sin focos reales; pipeline de incendios vacío; imposibilidad de alimentar el dataset histórico de entrenamiento. |
| **Probabilidad original** | Media |
| **Estado** | **Cerrado** (30-08-2026) |
| **Mitigación aplicada** | Corrección del contrato de URL a formato posicional: `/api/area/csv/{MAP_KEY}/{SOURCE}/{AREA}/{DAY_RANGE}[/{DATE}]` en [`src/ingesta/parallel_ingester.py`](../src/ingesta/parallel_ingester.py) y módulo de backfill [`src/ingesta/nasa_firms_backfill.py`](../src/ingesta/nasa_firms_backfill.py). |
| **Evidencia verificable** | (1) Ingesta diaria real: 8 focos VIIRS en BBOX Valparaíso (`data/raw/nasa_firms_2026-08-31.csv`). (2) Backfill histórico 5 años: 366 ventanas, 12.477 registros únicos, 0 errores HTTP 429, duración ~3 min 36 s. (3) Manifest: [`data/processed/nasa_firms_2021-08-30_2026-08-30_manifest.json`](../data/processed/nasa_firms_2021-08-30_2026-08-30_manifest.json). (4) SHA256 del CSV consolidado (campo `sha256` del manifest, verificado en disco 30-08-2026, 64 caracteres): `a9a85db4431b3e54f936b724e4de5a7fbb0cc19f5721f5e1a344a192bf9bb271`. (5) Validación de solapamiento SP/NRT: 0 duplicados; 0 fechas compartidas entre fuentes; corte limpio SP hasta 2026-04-27 / NRT desde 2026-04-28. |
| **Riesgo residual** | Rate limit 429 en backfills masivos (límite oficial: 5.000 transacciones / 10 min). Mitigado con `delay_seconds=0.25` y retry con backoff en el cliente de backfill. |

---

## Riesgos abiertos

| Campo | Contenido |
|-------|-----------|
| **ID** | R-DMC-01 |
| **Riesgo** | Histórico de telemetría DMC incompleto para el corredor Valparaíso: el endpoint actual (`getDatosRecientesEma/{codigo}`) cubre solo las últimas 12 horas; el endpoint histórico mensual no está validado en producción; 2 de 3 estaciones configuradas (330004 Quilpué, 330005 Villa Alemana) devuelven *Información no disponible* — solo 330007 Rodelillo entrega datos reales. |
| **Impacto** | SAPI-28 (join ignición ↔ meteo) no puede cubrir 5 años de histórico antes del Hito 1 con la cobertura estacional deseada. |
| **Probabilidad** | Alta (ya materializado parcialmente) |
| **Estado** | **Abierto** — mitigación en curso |
| **Decisión de gestión** | Diferir backfill DMC completo (mes × estación × 5 años) a post-Hito 1. Para el Hito 1: implementar join con muestra de 3–6 meses sobre estación 330007 y validar arquitectura + tests (SAPI-28 opción B). |
| **Próxima acción** | Spike de 1 mes contra API histórica — **completado** (feb-2025 / 330007); `meteo_fire_joiner` implementado con tolerancia ±15 min y estación más cercana. Pendiente: backfill multi-mes post-hito. |

| Campo | Contenido |
|-------|-----------|
| **ID** | R-CONAF-01 |
| **Riesgo** | No existe fuente real de incendios CONAF integrada en el repositorio. La ingesta actual (`_ingest_conaf` en [`src/ingesta/parallel_ingester.py`](../src/ingesta/parallel_ingester.py)) consulta la API WordPress de conaf.cl (`/wp-json/wp/v2/posts`) — no datos de incendios — e ignora la respuesta para cargar un seed local (`data/raw/conaf_historico_seed.json`) que **no existe en el repo**. El script `scripts/ingesta_conaf.py` referenciado en el README tampoco existe. |
| **Impacto** | SAPI-26 no puede cerrarse del lado CONAF; el dataset de entrenamiento depende exclusivamente de NASA FIRMS (focos satelitales) hasta resolver la fuente institucional. |
| **Probabilidad** | Alta |
| **Estado** | **Abierto** — diferido con decisión explícita |
| **Investigación activa (30-08-2026)** | Se revisó el código fuente (`parallel_ingester.py`, `config.py`, `data_processor.py`), la configuración (`.env.example`), tests (`test_ingesta_degradation.py`, `test_procesamiento.py`), documentación (`docs/alcance-prototipo.md`, README) y el filesystem del repo (0 archivos `*conaf*` en `data/raw/`). Conclusión verificada: no hay endpoint, parser ni dataset histórico CONAF implementado; solo un stub documentado como placeholder y 10 puntos sintéticos `conaf_seed` en el seed SQL de demo. |
| **Decisión de gestión** | **Diferir integración CONAF real a Sprint 2** (post-Hito 1). Esta decisión fue explícita tras la investigación del 30-08 — no es una omisión ni un descuido. Para el Hito 1, NASA FIRMS (12.477 focos georreferenciados, 2021–2026) cubre la necesidad de histórico de igniciones satelitales; CONAF queda como riesgo abierto con plan de resolución documentado. |
| **Próxima acción (Sprint 2)** | Spike de fuente oficial (portal datos abiertos CONAF / SNIF / shapefile institucional); implementar `backfill_conaf_incendios.py` + parser; conectar al consolidador de incendios históricos. |

| Campo | Contenido |
|-------|-----------|
| **ID** | R-COBERTURA-01 |
| **Riesgo** | La cobertura de tests medida con `pytest tests/ -v --cov=app --cov=src --cov-fail-under=80` es **80.34%** (corrida Docker `analytics-backend`, Python 3.11, **31-08-2026**), cumpliendo el umbral del 80% en `pytest.ini` / CI. Línea base al inicio del sprint de cobertura: **63.21%** (86 tests). Corrida intermedia mismo día: **72.22%** (134 tests). |
| **Impacto** | SAPI-45 cierra el gate de cobertura del repositorio; `pytest` con `--cov-fail-under=80` termina exit code 0 (**188/188 PASS**, 31-08-2026). |
| **Probabilidad** | Baja (cerrado) |
| **Estado** | **Cerrado** — gate 80% alcanzado 31-08-2026 |
| **Desglose verificable (31-08-2026, corrida final)** | **Total:** 80.34% (1872 stmts, 368 miss). **Suite:** 188/188 PASS (+54 tests vs corrida inicial del sprint: 134). **Módulos clave:** `nasa_firms_backfill.py` 100%, `parallel_ingester.py` 99%, `meteo_fire_joiner.py` 100%, `features.py` 100%. Módulos en 0% (sprints posteriores): [`inference_engine.py`](../src/modelo/inference_engine.py), [`persister.py`](../src/procesamiento/persister.py), [`spatial_joiner.py`](../src/procesamiento/spatial_joiner.py). **Otros gaps:** `app/app.py` 49% (`main()` Streamlit), `app/utils/demo_seed.py` 31%. |
| **Decisión de gestión** | **Mantener umbral 80%** en `pytest.ini` y CI. Esfuerzo de cobertura **cortado en 80.34%** para este sprint: brecha residual en módulos de sprints posteriores y `app.main()` no ejercitado en unit tests. |
| **Próxima acción** | Sprint 2 / post-Hito 1: tests de `persister`, `spatial_joiner` e `inference_engine` al integrar pipeline de producción; migrar scripts raíz (`test_spatial_join.py`, etc.); opcionalmente E2E ligero de `app.main()`. |

| Campo | Contenido |
|-------|-----------|
| **ID** | R-INTEGRACION-01 |
| **Riesgo** | El flujo de **riesgo por celda** ([`baseline.py`](../src/modelo/baseline.py), [`optimizer.py`](../src/modelo/optimizer.py), [`inference_engine.py`](../src/modelo/inference_engine.py), vía `matriz_features` / `predicciones_riesgo` en PostGIS) y el flujo de **join ignición ↔ meteo** (SAPI-28/32, vía [`fires_meteo_join_*.parquet`](../data/processed/fires_meteo_join_2025-02_clean.parquet)) **no están conectados**. Las 164 igniciones reales de feb-2025 — incluido el pico de viento real del 09-feb winsorizado por Z-score — no alimentan ningún cálculo de `probabilidad` / `nivel_riesgo` hoy. |
| **Impacto** | El dataset limpio de entrenamiento/análisis (ignición puntual + meteo en instante) no cierra el ciclo hacia el mapa de riesgo ni hacia el modelo; el dashboard sigue en demo por celda o seed SQL desacoplado de igniciones históricas reales. |
| **Probabilidad** | Alta (ya materializado) |
| **Estado** | **Abierto** — documentado 30-08-2026 tras cierre de SAPI-32 |
| **Evidencia verificable** | Corrida feb-2025: [`fires_meteo_join_2025-02_clean.parquet`](../data/processed/fires_meteo_join_2025-02_clean.parquet) + manifest con 164 filas `matched`; sin referencias en código de `inference_engine`, `spatial_joiner` ni `data_processor` al parquet de join. Riesgo por celda solo en `demo_seed` / `PredictionQuery` → `predicciones_riesgo`. |
| **Decisión de gestión** | **Diferido a Sprint 2** (post-Hito 1). SAPI-28/32 validan ingesta y limpieza del puente ignición–meteo; la integración espacial (ignición → grilla VP-XXX) → features → inferencia queda como siguiente hito de arquitectura. |
| **Próxima acción (Sprint 2)** | Diseñar puente `fires_meteo_join_*` → agregación o etiquetado por celda; conectar `spatial_joiner` / `persister` al pipeline real; validar que igniciones históricas influyan en entrenamiento o en validación del modelo. |
| **Relación con SAPI-44 (verificado 31-08-2026)** | El badge `_render_data_mode_badge()` declara la fuente del **mapa en runtime** (`demo_seed` o `postgis_inference`), no el estado de ingesta NASA/DMC en `data/raw/`. Pueden coexistir telemetrías reales en disco y mapa en modo demo — gap documentado, no bug de UI; resolución en Sprint 2 vía R-INTEGRACION-01. |

---

## Resumen ejecutivo

| ID | Estado | Severidad residual |
|----|--------|-------------------|
| R-NASA-FIRMS-01 | Cerrado | Baja (residual: rate limit en backfills futuros) |
| R-DMC-01 | Abierto (mitigado parcialmente) | Media |
| R-CONAF-01 | Abierto (diferido Sprint 2, investigado 30-08) | Media |
| R-COBERTURA-01 | Cerrado (suite verde **188** tests; cobertura **80.34%** — gate 80% alcanzado 31-08-2026) | Baja |
| R-INTEGRACION-01 | Abierto (join ignición–meteo y riesgo por celda desconectados; diferido Sprint 2) | Media |

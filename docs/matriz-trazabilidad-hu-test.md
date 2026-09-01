# Matriz de trazabilidad — Historia de usuario ↔ Prueba

**Proyecto:** S.A.P.I. — Sistema de Alerta y Predicción de Incendios Forestales  
**Última actualización:** 31-08-2026  
**Alcance:** Hito 1 (evaluación 07-09-2026)

Esta matriz conecta cada historia de usuario / ticket Jira con su criterio de aceptación, el módulo de código correspondiente y la prueba o evidencia **verificable en el repositorio** — no supuestos del portafolio.

**Leyenda de estado**

| Estado | Significado |
|--------|-------------|
| Cerrado | Evidencia verificada en repo o corrida real documentada |
| Parcial | Implementación o tests incompletos; gap documentado |
| Pendiente | No iniciado o bloqueado |
| Manual | Evidencia documental (sin test automatizado) |

---

## Matriz principal

| HU / Jira | Criterio de aceptación (resumen) | Módulo / artefacto | Test(s) o evidencia verificable | Estado | Gap |
|-----------|----------------------------------|--------------------|---------------------------------|--------|-----|
| **SAPI-26** — Histórico incendios NASA FIRMS | Backfill 5 años idempotente, dedup SP/NRT, manifest con conteos | [`src/ingesta/nasa_firms_backfill.py`](../src/ingesta/nasa_firms_backfill.py), [`scripts/backfill_nasa_firms.py`](../scripts/backfill_nasa_firms.py) | `tests/test_nasa_firms_backfill.py` (5 tests); manifest [`data/processed/nasa_firms_2021-08-30_2026-08-30_manifest.json`](../data/processed/nasa_firms_2021-08-30_2026-08-30_manifest.json) — 12.477 registros; SHA256 CSV: `a9a85db4431b3e54f936b724e4de5a7fbb0cc19f5721f5e1a344a192bf9bb271` | **Cerrado** (lado NASA) | CONAF sin fuente real (ver R-CONAF-01) |
| **SAPI-28** — Telemetría DMC + igniciones | Join T/HR/viento en instante de ignición; estación más cercana (Haversine); cobertura mensual antes de elegir estación; ±15 min | [`src/procesamiento/meteo_fire_joiner.py`](../src/procesamiento/meteo_fire_joiner.py), [`src/procesamiento/station_catalog.py`](../src/procesamiento/station_catalog.py), [`src/procesamiento/raw_parser.py`](../src/procesamiento/raw_parser.py) | `tests/test_meteo_fire_joiner.py` (10 tests); corrida real feb-2025: manifest [`fires_meteo_join_2025-02_manifest.json`](../data/processed/fires_meteo_join_2025-02_manifest.json) — **164/164 `matched`**, **0 `out_of_tolerance`** (δ máx 7 min); rama `out_of_tolerance` cubierta por tests sintéticos (`test_join_out_of_tolerance_*`) | **Parcial** | Join feb-2025 validado en datos reales. **`out_of_tolerance` no observado en corrida real** (solo `matched` en manifest). Ampliar a más meses/estaciones post-hito. Backfill DMC 3–6 meses pendiente. |
| **SAPI-30** — Topografía DEM | Altitud, pendiente, orientación por celda 1 km² | — | — | **Post-hito** | Sin DEM ni `rasterio`; `_add_topography()` sintético |
| **SAPI-32** — Limpieza y normalización | Z-Score outliers (winsoriza a μ), imputación mediana solo en `matched`, dedup FIRMS, recorte físico meteo | [`src/procesamiento/dataset_cleaner.py`](../src/procesamiento/dataset_cleaner.py), [`data_processor.py`](../src/procesamiento/data_processor.py) | **Sub-tarea feb-2025:** `tests/test_dataset_cleaner.py` (5 tests) + [`fires_meteo_join_2025-02_clean.parquet`](../data/processed/fires_meteo_join_2025-02_clean.parquet) (164 filas, 7 winsorizados). **HU end-to-end:** pendiente R-INTEGRACION-01 | **Parcial** | **Sub-tarea limpieza feb-2025: Cerrada** (manifest + tests). **HU SAPI-32 integración:** Parcial — join limpio no alimenta `probabilidad`/`nivel_riesgo` del mapa (R-INTEGRACION-01). `data_processor` legacy sin dedup en grilla demo. |
| **SAPI-44** — Separación demo vs real | UI y docs marcan fuente demo vs pipeline real | [`src/config.py`](../src/config.py) (`SAPI_DATA_MODE`), [`app/app.py`](../app/app.py), [`app/utils/demo_seed.py`](../app/utils/demo_seed.py) | `pytest tests/test_app.py` — **13/13 PASS** (Docker `analytics-backend`, Python 3.11, 31-08-2026); badge verificado en código: no refleja ingesta NASA/DMC en `data/raw/` (R-INTEGRACION-01) | **Cerrado** | `postgis_inference` reservado Sprint 2; badge declara fuente del mapa, no pipeline ETL |
| **SAPI-45** — Imports y tests estables | `app.utils.*` sin UnboundLocalError Cloud; suite verde; cobertura ≥80% | [`app/app.py`](../app/app.py), [`app/utils/`](../app/utils/), [`src/db.py`](../src/db.py), [`src/ingesta/parallel_ingester.py`](../src/ingesta/parallel_ingester.py), [`src/ingesta/nasa_firms_backfill.py`](../src/ingesta/nasa_firms_backfill.py) | `pytest tests/ -v --cov=app --cov=src --cov-fail-under=80` — **188/188 PASS** (Docker, Python 3.11, 31-08-2026); cobertura **80.34%** (1872 stmts, 368 miss) | **Cerrado** | Gate 80% alcanzado. Tests nuevos: `test_nasa_firms_backfill_client.py`, ampliación `test_ingesta.py`, `test_date_helpers.py`, `test_metrics_loader.py`, `test_config.py`, `test_features.py`, `test_query.py`, `test_baseline.py`. |
| **SAPI-47** — Matriz de riesgo | Riesgo NASA cerrado con evidencia; abiertos documentados | [`docs/matriz-riesgo.md`](matriz-riesgo.md) | Revisión manual; R-NASA-FIRMS-01, R-DMC-01, R-CONAF-01, R-COBERTURA-01, R-INTEGRACION-01 | **Cerrado** | — |
| **SAPI-48** — Esta matriz | HU conectada a test real verificable | Este documento | Revisión manual | **Cerrado** | SAPI-45 cerrado 31-08-2026 (80.34%, 188 tests); SAPI-44 cerrado 31-08-2026 |

---

## Trazabilidad por capa técnica

### Ingesta y degradación

| Requisito | Módulo | Test(s) | Estado |
|-----------|--------|---------|--------|
| Ingesta paralela NASA/DMC/CONAF | [`src/ingesta/parallel_ingester.py`](../src/ingesta/parallel_ingester.py) | `tests/test_ingesta.py` (10 tests), `tests/test_ingesta_degradation.py` (4 tests) | **Cerrado** (reintentos, estaciones sin datos, degradación) |
| Degradación R-03 PostGIS | idem | `tests/test_ingesta_degradation.py` (4 tests) | **Cerrado** |
| Backfill NASA ventanas SP/NRT | [`src/ingesta/nasa_firms_backfill.py`](../src/ingesta/nasa_firms_backfill.py) | `tests/test_nasa_firms_backfill.py` | **Cerrado** |
| Parser DMC/NASA real | [`src/procesamiento/raw_parser.py`](../src/procesamiento/raw_parser.py) | `tests/test_raw_parser.py` (7 tests) | **Cerrado** |
| Catálogo estaciones DMC | [`src/procesamiento/station_catalog.py`](../src/procesamiento/station_catalog.py) | `tests/test_station_catalog.py` (5 tests) | **Cerrado** |
| Join ignición ↔ meteo DMC (±15 min, Haversine) | [`meteo_fire_joiner.py`](../src/procesamiento/meteo_fire_joiner.py) | `tests/test_meteo_fire_joiner.py` (10 tests) | **Parcial** — corrida real feb-2025 solo `matched`; `out_of_tolerance` vía sintético |
| Observabilidad / conexión DB | [`src/db.py`](../src/db.py) | `tests/test_db.py` (6 tests) | **Cerrado** |

### Procesamiento y features

| Requisito | Módulo | Test(s) | Estado |
|-----------|--------|---------|--------|
| Limpieza join ignición ↔ meteo (sub-tarea SAPI-32) | [`dataset_cleaner.py`](../src/procesamiento/dataset_cleaner.py) | `tests/test_dataset_cleaner.py` (5 tests) + manifest clean feb-2025 | **Cerrado** (sub-tarea feb-2025) |
| Limpieza Z-score + mediana (grilla demo) | [`data_processor.py`](../src/procesamiento/data_processor.py) | `test_clean_staging_tables_removes_outliers`, `test_impute_nulls_fills_missing` | Parcial |
| Regla 30-30-30 + lags | [`src/procesamiento/features.py`](../src/procesamiento/features.py) | `tests/test_features.py` (4 tests) | Verificar en CI |
| Join espacial grilla | [`src/procesamiento/spatial_joiner.py`](../src/procesamiento/spatial_joiner.py) | Script manual `test_spatial_join.py` | Gap — no en pytest |
| Persistencia PostGIS | [`src/procesamiento/persister.py`](../src/procesamiento/persister.py) | Script manual `test_persistence_postgis.py` | Gap — no en pytest |

### Modelo ML

| Requisito | Módulo | Test(s) | Estado |
|-----------|--------|---------|--------|
| Baseline Random Forest | [`src/modelo/baseline.py`](../src/modelo/baseline.py) | `tests/test_baseline.py` (2 tests) | Verificar en CI |
| XGBoost + optimización | [`src/modelo/optimizer.py`](../src/modelo/optimizer.py) | `tests/test_optimizer.py` (3 tests) | Verificar en CI |
| Serialización .pkl | [`src/modelo/serialization.py`](../src/modelo/) | `tests/test_serialization.py` | Verificar en CI |
| Pipeline diario | [`src/pipeline/run_daily.py`](../src/pipeline/run_daily.py) | `tests/test_pipeline.py::test_run_daily_pipeline` | Mock only |

### Query PostGIS (contrato datos)

| Requisito | Módulo | Test(s) | Estado |
|-----------|--------|---------|--------|
| `exact-date-v1` mapa espacial | [`src/query/prediction_query.py`](../src/query/prediction_query.py) | `tests/test_query.py` (13 tests) | Verificar en CI — **no usado en dashboard demo** |
| Fechas demo / fallback | [`app/utils/date_helpers.py`](../app/utils/date_helpers.py) | `tests/test_date_helpers.py` (8 tests) | **Cerrado** |

### Dashboard Streamlit

| Requisito | Módulo | Test(s) | Estado |
|-----------|--------|---------|--------|
| Mapa Folium + colormap | [`app/utils/map_renderer.py`](../app/utils/map_renderer.py) | `tests/test_ui_cache.py` (5 tests), `tests/test_risk_colors.py` (9 tests) | **Cerrado** |
| Tabla celdas + selección mapa | [`app/utils/cell_table.py`](../app/utils/cell_table.py) | `tests/test_cell_table.py` (9 tests) | Verificar en CI |
| Zonificación VP-XXX | [`app/utils/cell_zones.py`](../app/utils/cell_zones.py) | `tests/test_cell_zones.py` (4 tests) | **Cerrado** |
| Métricas ML panel | [`app/utils/metrics_loader.py`](../app/utils/metrics_loader.py) | `tests/test_metrics_loader.py` (4 tests) | Verificar en CI |
| App principal / export (SAPI-44) | [`app/app.py`](../app/app.py) | `tests/test_app.py` (13 tests) — 13/13 PASS 31-08-2026 | **Cerrado** (demo_seed + badge; `main()` sin cobertura — R-COBERTURA-01) |
| Data contract (app no importa ETL) | — | `tests/test_architecture.py` | **Cerrado** |

---

## Gaps documentados (sin test automatizado)

| Ítem | Motivo | Plan |
|------|--------|------|
| HU-10 Export PDF | `test_export_report_pdf` valida footer `data_source=demo_seed` y `SAPI_DATA_MODE` | — |
| CONAF histórico | Stub sin fuente; ver R-CONAF-01 | Sprint 2 |
| DEM topografía | SAPI-30 post-hito | Sprint 2 |
| Cobertura global ≥80% | Umbral 80% en `pytest.ini`; real **80.34%** (31-08-2026, **188** tests PASS); anterior 72.22% (134 tests) | **Cerrado** — R-COBERTURA-01 |
| Join DMC `out_of_tolerance` en datos reales | Feb-2025 manifest: 164/164 `matched`, **0 `out_of_tolerance`**; rama cubierta solo en tests sintéticos | Post-hito: backfill DMC multi-mes |
| Scripts raíz (`test_spatial_join.py`, etc.) | Fuera de `pytest.ini` `testpaths` | Sprint 2 — migrar a `tests/` |
| Integración join → riesgo por celda | `fires_meteo_join_*_clean.parquet` no alimenta `matriz_features` ni `predicciones_riesgo` | Sprint 2 — **R-INTEGRACION-01** |
| Dashboard modo PostGIS | `PredictionQuery` no usado en runtime demo (`SAPI_DATA_MODE=demo_seed`) | Sprint 2 — `postgis_inference` |

---

## Inventario de tests (referencia rápida)

**Total archivos en `tests/`:** 22 (+ `test_nasa_firms_backfill.py` con unittest). **Total pytest (31-08-2026):** 134 tests.

| Archivo | # tests |
|---------|---------|
| `test_query.py` | 13 |
| `test_ingesta.py` | 10 |
| `test_dataset_cleaner.py` | 5 |
| `test_meteo_fire_joiner.py` | 10 |
| `test_app.py` | 13 |
| `test_risk_colors.py` | 9 |
| `test_cell_table.py` | 9 |
| `test_raw_parser.py` | 7 |
| `test_db.py` | 6 |
| `test_date_helpers.py` | 8 |
| `test_station_catalog.py` | 5 |
| `test_ingesta_degradation.py` | 4 |
| `test_features.py` | 4 |
| `test_metrics_loader.py` | 4 |
| `test_cell_zones.py` | 4 |
| `test_ui_cache.py` | 5 |
| `test_procesamiento.py` | 5 |
| `test_nasa_firms_backfill.py` | 5 |
| `test_optimizer.py` | 3 |
| `test_baseline.py` | 2 |
| `test_pipeline.py` | 1 |
| `test_serialization.py` | 1 |
| `test_architecture.py` | 1 |

**Comando de verificación:** `docker compose run --rm --no-deps -v "${PWD}:/app" analytics-backend pytest tests/ -v --cov=app --cov=src --cov-fail-under=80` (Python 3.11). Última corrida **31-08-2026:** **188 PASS**, cobertura **80.34%** (gate 80% alcanzado). Corrida anterior mismo día: 134 PASS, 72.22%.

---

## Referencias cruzadas

- Matriz de riesgo: [`docs/matriz-riesgo.md`](matriz-riesgo.md)
- Alcance prototipo: [`docs/alcance-prototipo.md`](alcance-prototipo.md)
- Plan Hito 1: `PLAN_HITO1.md` (externo al repo)

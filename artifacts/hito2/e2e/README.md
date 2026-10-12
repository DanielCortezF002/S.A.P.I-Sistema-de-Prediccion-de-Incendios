# Evidencia de Verificación E2E — Vertical Slice (SAPI-66 / S2-13)

Este directorio contiene las evidencias reproducibles de la prueba end-to-end completa del vertical slice de S.A.P.I. v2:
`Streamlit` (UI/AppTest/web-v2) → `Spring Boot` (backend REST) → `FastAPI / Modelo D` (ml-api) → `PostgreSQL / PostGIS` (db-v2).

## Criterios de Aceptación Cumplidos

- **SAPI-66.CA1**: Vertical slice completo probado y verificado de extremo a extremo.
- **SAPI-66.CA2**: Contratos OpenAPI (`backend.v0.yaml`, `ml-service.v0.yaml`) y caminos de error (422, backend caído sin fallback) validados en cada salto.
- **SAPI-66.CA3**: Persistencia en PostGIS comprobada con `db/queries/latest_ranking.sql` (50 filas, orden idéntico a REST), idempotencia de clave natural verificada, e integridad espacial (`ST_IsValid=true`, `SRID=4326`, `ST_Polygon`).
- **SAPI-66.CA4**: Tiempos de respuesta frío y caliente registrados en `timings.csv` sin umbrales arbitrarios de latencia.
- **SAPI-66.CA5**: Ejecución automatizada sobre Docker Compose con aislamiento de proyecto y puertos parametrizados (`scripts/e2e_slice.py`).

## Artefactos Incluidos en `e2e-run-evidence/`

- `E2E_VERIFICATION_REPORT.md`: Informe ejecutivo con la tabla completa de 27 verificaciones automáticas (27/27 PASS).
- `e2e_report.json`: Reporte machine-readable con metadatos de ejecución, hechos del entorno y resultados por check.
- `timings.csv`: Registro de latencias por salto y fase (cold/warm).
- `latest_ranking_psql.txt`: Salida textual directa de la ejecución SQL dentro del contenedor `db-v2`.
- `compose_ps.json`: Inspección de servicios y contenedores de la pila Compose.

## Modos de Ejecución

1. **Suite Pytest**:
   ```bash
   python -m pytest -o addopts="" --noconftest tests/e2e/test_vertical_slice.py -v
   ```

2. **Runner Autónomo de Ciclo de Vida**:
   ```bash
   python scripts/e2e_slice.py --out-dir artifacts/hito2/e2e/e2e-run-evidence
   ```

# Informe de verificación E2E / integración

Entorno: nube Linux, Python 3.13, Java 21, Maven wrapper con Maven Central vía proxy. **Sin daemon Docker, sin PowerShell,
sin Playwright, sin datos reales (`data/raw`, `data/processed`)**. Modelo D versionado (`models/prototype_model_d.pkl`) y modo
`SAPI_REPRODUCIBILITY_MODE=1` sí disponibles.

## 1. Rutas reales (verificadas, no supuestas)

| Servicio | Rutas | Fuente |
|---|---|---|
| ML FastAPI | `GET /health`, `POST /predict` (única entrada: `forecast_time` opcional) | `services/ml_api/main.py`, `ml-service.v0.yaml`, `app.openapi()` |
| Backend Spring | `GET /health`, `GET /api/v1/ranking?forecast_time=` | `RankingController`, `backend.v0.yaml` |
| Streamlit | Solo llama `GET /api/v1/ranking` | `app/utils/backend_client.py` |

**`/infer` no existe en ningún servicio** (grep en código, contratos y pruebas). Comprobado en vivo con uvicorn real:
`POST /infer` → 404; `POST /predict` → 200. `/predict` y `/ranking` tampoco son intercambiables (ML no tiene
`/api/v1/ranking`; backend no tiene `/predict`). Fijado por pruebas nuevas.

## 2. Pruebas ejecutadas (clasificación obligatoria)

| Conjunto | Clase | Resultado | Acredita |
|---|---|---|---|
| Suite Python completa (2292 casos) en `0ac6c05` | UNITARIA/INTEGRACIÓN/ESTÁTICA mezcladas | **2154 ok, 138 omitidas, 0 fallos**, cobertura 85,30 % (gate 80 %) | regresión del candidato en Linux |
| Maven `./mvnw test` (162 casos) | UNITARIA/INTEGRACIÓN (Spring con ML *stub* HTTP) | 158 ok, 4 omitidas, 0 fallos | contrato y errores del backend contra stub |
| **NUEVO** `tests/test_overnight_s2_chain_integrity.py` (12) | ver abajo | 12 ok | ver abajo |
| `RankingRealMlServiceTests` contra uvicorn real | **E2E REAL parcial** (Spring real ↔ FastAPI real, sin BD ni Streamlit) | **3 fallos / 4** (ver §3) | — |
| Mismo con parche propuesto | idem | 4 ok | el backend relaya verbatim el cuerpo del ML |
| `ops/n8n/policy.test.js` (node) | UNITARIA | 45/45 | política n8n; **no** hay n8n vivo |

### Pruebas nuevas (12), cobertura por fase del plan

| Prueba | Clase | Flujo cubierto |
|---|---|---|
| `test_static_ml_contract_exposes_predict_not_infer` | ESTÁTICA | rutas ML |
| `test_static_backend_contract_exposes_ranking_only_...` | ESTÁTICA | rutas backend |
| `test_static_streamlit_client_targets_backend_ranking_path_only` | ESTÁTICA | Streamlit no llama `/predict` ni `/infer` |
| `test_static_scientific_warning_in_metadata_and_fallback` | ESTÁTICA | advertencia científica (metadata y respaldo) |
| `test_integration_ml_has_no_other_routes` ×3 | INTEGRACIÓN | `/infer`, `/api/v1/ranking`, `/api/v1/infer` → 404 |
| `test_integration_predict_is_post_only` | INTEGRACIÓN | GET /predict → 405 |
| `test_integration_real_model_carries_scientific_flags` | INTEGRACIÓN | Modelo D real: flags + disclaimer |
| `test_e2e_stub_real_ml_ranking_reaches_streamlit_with_warnings` | **E2E CON STUB** | ML real → relevo HTTP (sustituye a Spring) → cliente → `app.py`: fingerprint, 50 celdas, advertencia visibles |
| `test_e2e_stub_ml_unavailable_is_controlled_and_hides_internals` | **E2E CON STUB** | `PrototypeUnavailableError` → 503 → mensaje UI genérico, sin rutas |
| `test_e2e_stub_unexpected_ml_failure_never_renders_a_ranking` | **E2E CON STUB** | `RuntimeError` → 500 → sin ranking, sin internals |

Las E2E con stub **no acreditan** el sistema completo: Spring Boot, PostGIS y Docker no participan.

### Cobertura de la lista de la misión

1 datos de entrada / 2 frescura / 3 ML: suites existentes (`test_prototype_freshness`, `test_ml_api`) `[N]` verdes;
frescura sobre datos **reales CURRENT** no ejecutable (sin datos). 4 backend consume ranking: Maven `[N]` (stub) y real parcial.
5 Streamlit: `test_sapi61_http_stub` + nuevas. 6 errores controlados: nuevas + existentes. 7 advertencias científicas: nuevas.
8 SAPI-66: CA1/CA3/CA4/CA5 **no ejecutables** (Docker); CA2 parcial.

## 3. Hallazgo: `RankingRealMlServiceTests` falla contra el ML real (SAPI-57.CA4)

- Síntoma: `backendReturnsSameBytesAsMlService`, `explicitEarlierForecastTimeRoundTrips`, `positiveOffsetRoundTrips` → `expected bytes ≠ actual`.
- Causa raíz (reproducida con dos `POST /predict` seguidos, `evidence/p1.json` vs `p2.json`): el único campo que difiere es
  `age_hours` (1182,7147 → 1182,7160); `cells` idénticas. `age_hours = captured_at(now) − weather_timestamp`
  (`src/inference/prototype_service.py:344,501`), así que **dos respuestas del ML nunca son iguales byte a byte**; `freshness`
  también es derivada. `scripts/compose_v2_preflight.py` ya excluye `age_hours/freshness`; la prueba Java no.
- Es defecto de **la prueba**, no del backend (relaya sin reordenar). Está oculto en CI porque la prueba se omite sin
  `SAPI_IT_ML_BASE_URL`.
- Parche propuesto, verificado 4/4 y **revertido** (no toca el candidato): `evidence/proposed-fix-RankingRealMlServiceTests.patch`.
- Error original conservado: `evidence/mvn_real_ml_original_failure.txt`.
- Riesgo: si el mismo patrón byte-a-byte existe en la demo del Omen contra ML vivo, fallaría. Verificar en la demo.

## 4. No ejecutable en la nube

Docker/Compose/Testcontainers (`*IT`, SAPI-60 CA1–CA6, SAPI-66, CA8 dinámico), navegador Edge/Playwright, FIRMS/DMC reales,
PostGIS, n8n vivo, PowerShell. No se simuló ningún resultado.

## 5. Reproducir

```
python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest tests/test_overnight_s2_chain_integrity.py --no-cov -q
# real ML parcial:
SAPI_REPRODUCIBILITY_MODE=1 .venv/bin/python -m uvicorn services.ml_api.main:app --port 18012 &
(cd services/backend && SAPI_IT_ML_BASE_URL=http://127.0.0.1:18012 ./mvnw test -Dtest=RankingRealMlServiceTests)
```

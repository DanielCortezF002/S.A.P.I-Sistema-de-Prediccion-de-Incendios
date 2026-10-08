# Contratos OpenAPI v0 — S.A.P.I. v2

Contratos de la arquitectura v2 (Streamlit → Spring Boot → FastAPI/Modelo D →
PostgreSQL/PostGIS), definidos antes que los servicios (contract-first,
SAPI-56). Estado al checkpoint de Sprint 2 (`cd6b58e`): el servicio ML
implementa `ml-service.v0.yaml` completo (SAPI-55); el backend implementa solo
`GET /health` (SAPI-54) y `GET /api/v1/ranking` sigue pendiente (SAPI-57).

| Archivo | Servicio | Puerto | Endpoints | Implementa |
|---|---|---|---|---|
| `ml-service.v0.yaml` | Servicio ML (FastAPI), interno | 8000 | `GET /health`, `POST /predict` | SAPI-55 |
| `backend.v0.yaml` | Backend (Spring Boot), público | 8080 | `GET /health`, `GET /api/v1/ranking` | SAPI-54, SAPI-57 |

Son dos documentos porque cada servicio expone su propio `GET /health`. Los
schemas compartidos (`RankingResult`, `CellRanking`, `Error`) se definen una
sola vez en `ml-service.v0.yaml`, y `backend.v0.yaml` los referencia con `$ref`.

## Semántica

- `score` es un ranking relativo entre las 50 celdas de una misma evaluación
  (`score_semantics: relative_rank`). No es una probabilidad calibrada de
  incendio, y ningún campo se nombra como tal.
- `scientific_model_validation` es `false`. El Modelo D es el baseline
  experimental; cambiar ese valor exige una nueva versión del contrato.
- Una evaluación válida tiene exactamente 50 celdas. Los empates reales se
  conservan con `display_rank` (método min) y `tie_group_size`.
- Las features las resuelve el servicio ML desde los stores versionados
  FIRMS/DMC. El backend no envía features ni reordena el ranking.

## Correspondencia con `sapi-output-v1`

Se reutilizan los nombres del contrato actual del bridge
(`tools/n8n_bridge/BRIDGE-OUTPUT-CONTRACT.md`, `src/output/contract.py`):
`model_version`, `forecast_time`, `inputs_fingerprint` y, por celda, `cell_id`,
`score`, `rank`, `display_rank` y `tie_group_size`, con las mismas reglas. La
taxonomía de errores (`prototype_unavailable`, `data_unavailable`,
`internal_error`) se mantiene, y se agregan los errores del salto
backend → servicio ML (`upstream_*`) y `invalid_request`. El bridge no cambia.

## Versionado

- Versión del documento: `info.version` 0.1.0. Versión del schema de
  respuesta: `schema_version: sapi-ranking-v0`.
- Después del checkpoint del contrato solo se admiten cambios compatibles:
  campos opcionales nuevos, valores nuevos de `error_type` o endpoints
  nuevos. Un cambio incompatible exige una nueva versión.
- Los clientes deben ignorar campos desconocidos en las respuestas.

## Validación

```bash
pip install openapi-spec-validator
openapi-spec-validator contracts/openapi/ml-service.v0.yaml contracts/openapi/backend.v0.yaml
```

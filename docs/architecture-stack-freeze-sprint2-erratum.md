# Erratum Sprint 2 — `architecture-stack-freeze-sprint2.md`

Fecha: 2026-10-08 (Quality Gate W0.10). Baseline: `cd6b58e`.

El freeze de arquitectura (2026-09-20) es un documento congelado y fechado,
así que su cuerpo **no se reescribe**. Este erratum registra los pasajes que
quedaron superados por lo implementado en Sprint 2 o que se contradicen dentro
del mismo documento. Ante una diferencia, rige la columna "Resolución".

| # | Líneas | Texto del freeze (resumen fiel) | Evidencia que lo supera | Resolución |
|---|---|---|---|---|
| E1 | L60-63 | El esquema PostGIS es `LEGACY_ONLY` | SAPI-58 creó el esquema v2 en `db/migration/` | Correcto para `docker/initdb/`, que sigue siendo legacy. El esquema operacional de Sprint 2 es `db/migration/V001-V003` (`db/README.md:13-26`) |
| E2 | L139 frente a L201 | Spring Boot "aplica autenticación/autorización" (L139); el slice "no requiere autenticación real" (L201) | Backend sin seguridad (`services/backend/pom.xml`) | La autenticación queda fuera del alcance de Sprint 2 y se registra como riesgo aceptado para el Hito 3. Los puertos se publican solo en 127.0.0.1 (ADR-008) |
| E3 | L160-163 | FastAPI puede leer y escribir, y "persiste resultados de inferencia cuando el backend se lo solicita" | `services/ml_api/main.py:14` ("no persiste nada"); ADR-007 | Spring Boot es el único escritor de la base. El servicio ML no persiste |
| E4 | L175-178 | El esquema (`matriz_features`, `predicciones_riesgo`) "se define una sola vez (SQL en `docker/initdb/`)" | `db/README.md:13-26`; V002 | El esquema compartido de la arquitectura v2 es `db/migration/` (`celdas_geom`, `ejecuciones`, `predicciones_celda`); `docker/initdb/` es legacy y no se reutiliza |
| E5 | L196-197 | El resultado "se persiste en `predicciones_riesgo` (o tabla equivalente)" | V002 L24-74 | La tabla equivalente es `ejecuciones` + `predicciones_celda`. `predicciones_riesgo` tiene semántica de probabilidad y no se usa |
| E6 | L272-273 | ADR-002: "necesidad de versionar el contrato de features esperado por el modelo" | `ml-service.v0.yaml` (`PredictRequest`, `additionalProperties: false`) | El cliente no envía features: el contrato versionado es el de entrada (`forecast_time`) y salida (`RankingResult`). Las features se resuelven dentro del servicio ML |
| E7 | L277-278 | ADR-003, contexto: "el esquema PostGIS ya existe (`docker/initdb/`)" | E1, E4 | Ver E1/E4 y `docs/adr/ADR-003.md` |
| E8 | L288-293 | ADR-003, consecuencia: "reactivar y adaptar `persister.py`"; riesgo: `UNIQUE(cell_id, fecha)` | `db/README.md:24-26`; V002 L41-43 | Superado: el pipeline v2 no reutiliza `persister.py`, y la clave natural de V002 es `(forecast_time, model_version, inputs_fingerprint)` |
| E9 | L297-299 | ADR-004, contexto: existen `Dockerfile.analytics` y `Dockerfile.web` | Commits de SAPI-54 y SAPI-55 | Hoy existen además `Dockerfile.ml-api` y `services/backend/Dockerfile`; ninguno está en Compose (SAPI-60) |
| E10 | L356-357 | Decisión abierta: "diseño físico exacto de tablas para Sprint 2" | SAPI-58 (V002) | Resuelto por SAPI-58. Siguen abiertas solo la migración V004 (ADR-007) y el runner (ADR-008) |

Fuera de estas filas, el freeze sigue vigente. Los ADR-001..006 se
mantienen en `docs/adr/`, cada uno con su estado de decisión e
implementación.

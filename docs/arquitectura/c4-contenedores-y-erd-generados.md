# C4 de contenedores y ERD generados (no editar a mano)

Generado por [evidencia/generar_c4_erd.py](evidencia/generar_c4_erd.py) desde [evidencia/compose-config-518c0b5.json](evidencia/compose-config-518c0b5.json) y `db/migration/` (V001__enable_postgis.sql, V002__create_sapi_v2_schema.sql, V003__seed_celdas_geom.sql, V004__add_firms_origin.sql). Para regenerarlo: `py -I docs/arquitectura/evidencia/generar_c4_erd.py > docs/arquitectura/c4-contenedores-y-erd-generados.md`.

## C4 nivel 2 · contenedores según `docker compose config` (profile `presentation`)

Las flechas de llamada salen de las variables de entorno que apuntan a otro servicio por nombre; las punteadas, de `depends_on`; las del anfitrión, de `ports`.

```mermaid
flowchart LR
    host["Equipo anfitrión<br/>(navegador, k6, curl)"]
    subgraph sapi_v2_net["red sapi-v2-net"]
      backend["backend<br/>build ./services/backend · Dockerfile"]
      db_v2[("db-v2<br/>postgis/postgis:15-3.4<br/>postgres")]
      ml_api["ml-api<br/>build . · Dockerfile.ml-api<br/>uvicorn services.ml_api.main:app --host 0.0.0.0 --port 8000 --workers 2"]
      web_v2["web-v2<br/>build . · Dockerfile.web<br/>python -m streamlit run app/app.py<br/>profile: presentation"]
    end
    host -- "127.0.0.1:18080 → 8080" --> backend
    host -- "127.0.0.1:15432 → 5432" --> db_v2
    host -- "127.0.0.1:18000 → 8000" --> ml_api
    host -- "127.0.0.1:18501 → 8501" --> web_v2
    backend -. "depends_on: service_healthy" .-> db_v2
    backend -. "depends_on: service_started" .-> ml_api
    web_v2 -. "depends_on: service_started" .-> backend
    backend -- "SAPI_ML_BASE_URL" --> ml_api
    backend -- "SPRING_DATASOURCE_URL" --> db_v2
    web_v2 -- "SAPI_BACKEND_BASE_URL" --> backend
```

| Servicio | Imagen o build | Puertos en el anfitrión | Volúmenes | Red | depends_on |
|---|---|---|---|---|---|
| backend | `./services/backend` (Dockerfile) | 127.0.0.1:18080→8080 | ./db/migration→/app/db/migration (ro), sapi_v2_secrets→/run/sapi-secrets (ro) | sapi-v2-net | db-v2 (service_healthy), ml-api (service_started) |
| db-v2 | postgis/postgis:15-3.4 | 127.0.0.1:15432→5432 | sapi_v2_pgdata→/var/lib/postgresql/data, sapi_v2_secrets→/run/sapi-secrets | sapi-v2-net | — |
| ml-api | `.` (Dockerfile.ml-api) | 127.0.0.1:18000→8000 | — | sapi-v2-net | — |
| web-v2 | `.` (Dockerfile.web) | 127.0.0.1:18501→8501 | — | sapi-v2-net | backend (service_started) |

## ERD · desde `db/migration`

Cada columna lleva la migración que la crea. PK, FK y UK según las restricciones declaradas.

```mermaid
erDiagram
    celdas_geom {
        text cell_id PK "V002__create_sapi_v2_schema.sql"
        geometry geom "V002__create_sapi_v2_schema.sql"
        timestamptz created_at "V002__create_sapi_v2_schema.sql"
    }
    ejecuciones {
        bigint id PK,UK "V002__create_sapi_v2_schema.sql"
        timestamptz forecast_time UK "V002__create_sapi_v2_schema.sql"
        text model_version UK "V002__create_sapi_v2_schema.sql"
        char inputs_fingerprint UK "V002__create_sapi_v2_schema.sql"
        text schema_version "V002__create_sapi_v2_schema.sql"
        text score_semantics "V002__create_sapi_v2_schema.sql"
        boolean scientific_model_validation "V002__create_sapi_v2_schema.sql"
        integer horizon_hours "V002__create_sapi_v2_schema.sql"
        timestamptz created_at "V002__create_sapi_v2_schema.sql"
        text firms_origin "V004__add_firms_origin.sql"
    }
    predicciones_celda {
        bigint ejecucion_id PK,FK,UK "V002__create_sapi_v2_schema.sql"
        timestamptz forecast_time FK "V002__create_sapi_v2_schema.sql"
        text cell_id PK,FK "V002__create_sapi_v2_schema.sql"
        double_precision score "V002__create_sapi_v2_schema.sql"
        integer rank UK "V002__create_sapi_v2_schema.sql"
        integer display_rank "V002__create_sapi_v2_schema.sql"
        integer tie_group_size "V002__create_sapi_v2_schema.sql"
    }
    ejecuciones ||--o{ predicciones_celda : "predicciones_celda_ejecucion_fk (ejecucion_id, forecast_time)"
    celdas_geom ||--o{ predicciones_celda : "predicciones_celda_celda_fk (cell_id)"
```

### Cotejo con la base del stack `sapi-h3-518c0b5`

Fuente: [evidencia/esquema-vivo-h3.txt](evidencia/esquema-vivo-h3.txt) (information_schema y `flyway_schema_history`).

| Tabla | Columnas según migraciones | Columnas en la base h3 | ¿Iguales y en el mismo orden? |
|---|---|---|---|
| celdas_geom | 3 | 3 | Sí |
| ejecuciones | 10 | 10 | Sí |
| predicciones_celda | 7 | 7 | Sí |

Claves foráneas: 2 según migraciones, 2 en la base h3. Resultado del cotejo: **coinciden**.

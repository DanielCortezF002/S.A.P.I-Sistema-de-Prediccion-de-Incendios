-- SAPI-58 · V002: esquema operacional v2 de S.A.P.I.
--
-- Persiste cada ejecución del Modelo D y su ranking de las 50 celdas, alineado
-- con contracts/openapi/ml-service.v0.yaml (RankingResult / CellRanking).
-- El score es un ranking relativo entre las 50 celdas de una misma ejecución,
-- no un valor calibrado de ocurrencia de incendio
-- (scientific_model_validation = false). Independiente del esquema legacy de
-- docker/initdb (LEGACY_ONLY): no lo modifica ni reutiliza sus tablas.

-- Geometría de las 50 celdas (cajas de src/geo/grid.py, ≈3,8 × 3,9 km).
CREATE TABLE celdas_geom (
    cell_id    text PRIMARY KEY,
    geom       geometry(Polygon, 4326) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT celdas_geom_cell_id_formato CHECK (cell_id ~ '^VP-[0-9]{3}$'),
    CONSTRAINT celdas_geom_geom_valida CHECK (ST_IsValid(geom))
);
CREATE INDEX celdas_geom_geom_gist ON celdas_geom USING gist (geom);

COMMENT ON TABLE celdas_geom IS
    'Las 50 celdas de la grilla (VP-001..VP-050); geometría desde src/geo/grid.py.';

-- Una fila por ejecución del Modelo D (una evaluación de las 50 celdas).
CREATE TABLE ejecuciones (
    id                          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    forecast_time               timestamptz NOT NULL,
    model_version               text NOT NULL,
    inputs_fingerprint          char(64) NOT NULL,
    schema_version              text NOT NULL,
    score_semantics             text NOT NULL DEFAULT 'relative_rank',
    scientific_model_validation boolean NOT NULL DEFAULT false,
    horizon_hours               integer,
    created_at                  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ejecuciones_model_version_no_vacia CHECK (model_version <> ''),
    CONSTRAINT ejecuciones_fingerprint_hex CHECK (inputs_fingerprint ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ejecuciones_schema_version_formato
        CHECK (schema_version ~ '^sapi-ranking-v[0-9]+$'),
    CONSTRAINT ejecuciones_score_semantics_ranking CHECK (score_semantics = 'relative_rank'),
    CONSTRAINT ejecuciones_sin_validacion_cientifica CHECK (scientific_model_validation = false),
    CONSTRAINT ejecuciones_horizon_positivo CHECK (horizon_hours IS NULL OR horizon_hours >= 1),
    -- Clave natural: la misma evaluación (T, modelo, insumos) no se guarda dos
    -- veces. Base de la inserción idempotente de SAPI-59.
    CONSTRAINT ejecuciones_clave_natural UNIQUE (forecast_time, model_version, inputs_fingerprint),
    -- Destino de la FK compuesta de predicciones_celda.
    CONSTRAINT ejecuciones_id_forecast_time UNIQUE (id, forecast_time)
);
CREATE INDEX ejecuciones_forecast_time_idx ON ejecuciones (forecast_time DESC);

COMMENT ON TABLE ejecuciones IS
    'Una ejecución del Modelo D. Score = ranking relativo; scientific_model_validation = false.';

-- El ranking de las 50 celdas de cada ejecución. forecast_time se repite aquí
-- (garantizado por la FK compuesta) para indexar el historial por celda y fecha.
CREATE TABLE predicciones_celda (
    ejecucion_id   bigint NOT NULL,
    forecast_time  timestamptz NOT NULL,
    cell_id        text NOT NULL,
    score          double precision NOT NULL,
    rank           integer NOT NULL,
    display_rank   integer NOT NULL,
    tie_group_size integer NOT NULL,
    CONSTRAINT predicciones_celda_pk PRIMARY KEY (ejecucion_id, cell_id),
    CONSTRAINT predicciones_celda_rank_unico UNIQUE (ejecucion_id, rank),
    CONSTRAINT predicciones_celda_ejecucion_fk FOREIGN KEY (ejecucion_id, forecast_time)
        REFERENCES ejecuciones (id, forecast_time) ON DELETE CASCADE,
    CONSTRAINT predicciones_celda_celda_fk FOREIGN KEY (cell_id)
        REFERENCES celdas_geom (cell_id),
    CONSTRAINT predicciones_celda_score_rango CHECK (score >= 0 AND score <= 1),
    CONSTRAINT predicciones_celda_rank_rango CHECK (rank BETWEEN 1 AND 50),
    CONSTRAINT predicciones_celda_display_rank_rango CHECK (display_rank BETWEEN 1 AND 50),
    CONSTRAINT predicciones_celda_tie_rango CHECK (tie_group_size BETWEEN 1 AND 50),
    -- display_rank usa el método min: nunca supera la posición única.
    CONSTRAINT predicciones_celda_display_rank_min CHECK (display_rank <= rank)
);
CREATE INDEX predicciones_celda_cell_time_idx
    ON predicciones_celda (cell_id, forecast_time DESC);

COMMENT ON TABLE predicciones_celda IS
    'Ranking de las 50 celdas por ejecución. Las 50 filas por ejecución las garantiza quien persiste (SAPI-59).';
COMMENT ON COLUMN predicciones_celda.score IS
    'Score relativo del Modelo D en [0, 1]; solo comparable dentro de la misma ejecución.';

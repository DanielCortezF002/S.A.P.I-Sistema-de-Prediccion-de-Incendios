-- Esquema analítico S.A.P.I. - Región de Valparaíso

CREATE TABLE IF NOT EXISTS staging_incendios (
    id SERIAL PRIMARY KEY,
    fecha TIMESTAMPTZ NOT NULL,
    latitud DOUBLE PRECISION NOT NULL,
    longitud DOUBLE PRECISION NOT NULL,
    fuente VARCHAR(50) NOT NULL,
    geom GEOMETRY(POINT, 4326),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS staging_meteo (
    id SERIAL PRIMARY KEY,
    fecha TIMESTAMPTZ NOT NULL,
    temperatura DOUBLE PRECISION,
    humedad_relativa DOUBLE PRECISION,
    velocidad_viento DOUBLE PRECISION,
    estacion_id VARCHAR(50),
    geom GEOMETRY(POINT, 4326),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS matriz_features (
    id SERIAL PRIMARY KEY,
    cell_id VARCHAR(32) NOT NULL,
    fecha DATE NOT NULL,
    temperatura REAL,
    humedad_relativa REAL,
    velocidad_viento REAL,
    altitud REAL,
    pendiente REAL,
    ndvi REAL,
    regla_30_30_30 SMALLINT,
    lag_temp_24h REAL,
    lag_temp_48h REAL,
    ignicion SMALLINT DEFAULT 0,
    geom GEOMETRY(POLYGON, 4326) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (cell_id, fecha)
);

CREATE TABLE IF NOT EXISTS predicciones_riesgo (
    id SERIAL PRIMARY KEY,
    cell_id VARCHAR(32) NOT NULL,
    fecha DATE NOT NULL,
    probabilidad REAL NOT NULL CHECK (probabilidad >= 0 AND probabilidad <= 1),
    nivel_riesgo VARCHAR(10) NOT NULL CHECK (nivel_riesgo IN ('bajo', 'medio', 'alto')),
    temperatura REAL,
    humedad_relativa REAL,
    velocidad_viento REAL,
    regla_30_30_30 SMALLINT,
    modelo_version VARCHAR(50) DEFAULT 'xgboost_v1.0',
    geom GEOMETRY(POLYGON, 4326) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (cell_id, fecha)
);

CREATE TABLE IF NOT EXISTS observability_logs (
    id SERIAL PRIMARY KEY,
    componente VARCHAR(100) NOT NULL,
    evento VARCHAR(255) NOT NULL,
    detalle TEXT,
    nivel VARCHAR(20) DEFAULT 'INFO',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

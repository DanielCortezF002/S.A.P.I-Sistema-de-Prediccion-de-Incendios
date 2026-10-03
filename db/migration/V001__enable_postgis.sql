-- SAPI-58 · V001: habilita PostGIS para el esquema operacional v2.
-- Fuente canónica de migraciones: db/migration/ (nombres compatibles con Flyway).
CREATE EXTENSION IF NOT EXISTS postgis;

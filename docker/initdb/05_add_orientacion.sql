-- Migración: agrega orientación de ladera (aspect, grados brújula 0-360, -1 = plano)
-- a matriz_features. Ver src/procesamiento/dem_terrain.py (Horn 1981) y
-- src/procesamiento/dem_features.py (media zonal circular por celda).
--
-- Nota sobre docker-entrypoint-initdb.d: este archivo solo se ejecuta
-- automáticamente cuando el volumen de Postgres se crea por primera vez.
-- Sobre un volumen ya inicializado hay que aplicarlo a mano (psql/sqlalchemy)
-- contra la instancia viva — este archivo queda como historial versionado
-- del esquema, no como mecanismo de aplicación automática en ese caso.
--
-- Nullable, sin default: no rompe filas existentes (si las hay) ni exige
-- backfill inmediato.
ALTER TABLE matriz_features
    ADD COLUMN IF NOT EXISTS orientacion REAL;

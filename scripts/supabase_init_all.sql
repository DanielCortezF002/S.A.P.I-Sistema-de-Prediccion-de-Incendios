-- S.A.P.I. — DDL unificado para Supabase PostGIS (puerto 5432 directo)
-- Ejecutar: psql "$DATABASE_URL_DIRECT" -f scripts/supabase_init_all.sql
-- Orden: extensiones → esquema → índices → seed demo (50 celdas)

\echo '>> 01_extensions.sql'
\ir ../docker/initdb/01_extensions.sql
\echo '>> 02_schema.sql'
\ir ../docker/initdb/02_schema.sql
\echo '>> 03_gist_indexes.sql'
\ir ../docker/initdb/03_gist_indexes.sql
\echo '>> 04_seed_valparaiso.sql'
\ir ../docker/initdb/04_seed_valparaiso.sql
\echo '>> Supabase init complete'

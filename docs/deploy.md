# Despliegue Prototipo S.A.P.I. — Streamlit Cloud + Supabase PostGIS

Este documento describe el despliegue del **prototipo funcional de demostración académica**.
No es una guía de infraestructura industrial en producción.

## Arquitectura cloud (conexión híbrida)

| Capa | Puerto | Variable | Uso |
|------|--------|----------|-----|
| Streamlit Cloud | 6543 | `DATABASE_URL` | Connection Pooler (UI serverless) |
| Pipeline batch | 5432 | `DATABASE_URL_DIRECT` | Ingesta y escrituras PostGIS |
| Migraciones DDL | 5432 | manual | `psql` contra instancia directa |

## 1. Provisionar Supabase PostGIS

1. Crear proyecto en [supabase.com](https://supabase.com).
2. Habilitar extensión PostGIS en SQL Editor:

```sql
CREATE EXTENSION IF NOT EXISTS postgis;
```

3. Ejecutar scripts locales **desde tu máquina** contra el host directo (puerto 5432):

```bash
psql "postgresql://postgres.[PROJECT]:[PASSWORD]@db.[PROJECT].supabase.co:5432/postgres?sslmode=require" \
  -f docker/initdb/01_extensions.sql
psql ... -f docker/initdb/02_schema.sql
psql ... -f docker/initdb/03_gist_indexes.sql
psql ... -f docker/initdb/04_seed_valparaiso.sql
```

> **Importante:** No pegar SQL PostGIS en PowerShell. Usar `psql` o el SQL Editor de Supabase.

## 2. Variables en Streamlit Community Cloud

En [share.streamlit.io](https://share.streamlit.io), conectar `github.com/dcortez/sapi-valparaiso`:

| Secreto | Valor |
|---------|-------|
| `DATABASE_URL` | `postgresql://...@aws-0-....pooler.supabase.com:6543/postgres?sslmode=require` |
| `NASA_FIRMS_API_KEY` | (opcional para demo con seed) |

Main file: `app/app.py`

## 3. Pipeline batch en cloud (opcional)

Ejecutar una vez con conexión directa:

```bash
DATABASE_URL_DIRECT="postgresql://...@db....supabase.co:5432/postgres?sslmode=require" \
  python -m src.pipeline.run_daily
```

## 4. Validación demo

- Mapa muestra **50 celdas** de riesgo en Valparaíso
- Popup incluye Regla 30-30-30
- `reports/metrics.json`: Recall XGBoost ≥ 0.75

## Desarrollo local (recomendado)

```bash
copy .env.example .env
docker compose up --build
# Dashboard: http://localhost:8501
```

Todo el SQL y el bucle analítico corren **dentro de contenedores Linux**, no en PowerShell.

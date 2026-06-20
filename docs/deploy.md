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
> En Windows sin `psql`, usar Docker contra el **pooler puerto 5432** (ver sección anterior del chat).

4. Si el seed ya estaba cargado (v1 cuadrados/aleatorio), **reemplazar** con seed v2:

```bash
psql ... -f docker/initdb/04_seed_valparaiso.sql
```

El seed v2 (`scripts/generate_seed.py`) usa microclimas costa/urbano/precordillera y celdas circulares ~1 km² (no series MeteoChile en vivo).

## 2. Streamlit Community Cloud — Python 3.11 (obligatorio)

Streamlit Cloud **no usa** `runtime.txt`. Debes elegir la versión en el panel:

1. [share.streamlit.io](https://share.streamlit.io) → tu app → **Manage app**
2. **Settings** → sección **Python version** (o **Advanced settings** al crear la app)
3. Selecciona **3.11** (no 3.13 ni 3.14)
4. **Save** → **Reboot app**

Si la app ya se creó con Python 3.14, los logs mostrarán fallos al compilar `pandas==2.1.4` y `psycopg2-binary`. Cambiar a 3.11 y reiniciar.

Repo: `DanielCortezF002/S.A.P.I-Sistema-de-Prediccion-de-Incendios` · Main file: `app/app.py`

## 3. Variables en Streamlit Community Cloud

En [share.streamlit.io](https://share.streamlit.io), conectar el repositorio:

| Secreto | Valor |
|---------|-------|
| `DATABASE_URL` | `postgresql://...@aws-0-....pooler.supabase.com:6543/postgres?sslmode=require` |
| `NASA_FIRMS_API_KEY` | (opcional para demo con seed) |

Main file: `app/app.py`

## 4. Pipeline batch en cloud (opcional)

Ejecutar una vez con conexión directa:

```bash
DATABASE_URL_DIRECT="postgresql://...@db....supabase.co:5432/postgres?sslmode=require" \
  python -m src.pipeline.run_daily
```

## 5. Validación demo

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

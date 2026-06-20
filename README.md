# S.A.P.I. - Sistema de Alerta y Predicción de Incendios

**Prototipo funcional de demostración académica** para la Región de Valparaíso, Chile.
Predice probabilidad de ignición forestal mediante XGBoost y visualiza riesgo en mapa Streamlit/Folium.

> Alcance demo: **50 celdas** de 1 km². Todo el pipeline y PostGIS corren en **Docker Linux**;
> no ejecutar SQL ni bash directamente en PowerShell.

## Arquitectura

- **db-postgis**: PostgreSQL 15 + PostGIS (SSoT)
- **analytics-backend**: Bucle 24h ingesta → procesamiento → ML
- **web-presentation**: Dashboard Streamlit (puerto 8501)

Ver [docs/arquitectura.md](docs/arquitectura.md) y [docs/deploy.md](docs/deploy.md).

## Inicio rápido (Docker)

```bash
cd sapi-valparaiso
copy .env.example .env
docker compose up --build
# Dashboard: http://localhost:8501
```

## Desarrollo local (sin rebuild completo)

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env

docker compose up db-postgis -d
python -m src.pipeline.run_daily
streamlit run app/app.py
```

## Pruebas

```bash
pytest
pytest --cov=app --cov=src --cov-report=html
```

## Despliegue cloud

Streamlit Community Cloud + Supabase PostGIS (conexión híbrida 6543/5432).
Instrucciones: [docs/deploy.md](docs/deploy.md).

## Métricas objetivo (prototipo)

- Recall XGBoost ≥ 75%
- Mapa semafórico 50 celdas Valparaíso
- Cobertura pytest ≥ 80%

## Licencia

Proyecto académico — Universidad Andrés Bello, 2026.

# Guía completa de funcionamiento — S.A.P.I.

Documento técnico y operativo del prototipo **Sistema de Alerta y Predicción de Incendios** (Región de Valparaíso). Describe qué hace cada capa, de dónde salen los datos, cómo fluye una consulta desde el navegador hasta PostGIS y qué es real vs sintético.

---

## 1. Qué es S.A.P.I. en este prototipo

S.A.P.I. es una plataforma de **apoyo a la decisión preventiva** que:

1. Integra variables ambientales (en el informe: meteo, topografía, histórico de igniciones).
2. Estima **probabilidad de ignición** por celda territorial (~1 km²).
3. Visualiza el riesgo en un **mapa interactivo** antes de que ocurra un foco visible.

En **esta demo académica**:

- El mapa lee predicciones ya guardadas en **PostgreSQL + PostGIS** (no ejecuta ML en el navegador).
- Los datos del dashboard provienen de un **seed sintético multi-fecha** (7 días × 50 celdas).
- El modelo XGBoost está entrenado y documentado (`reports/metrics.json`), pero **las celdas del mapa cloud/local usan el seed SQL**, no una corrida en vivo del modelo.

**No sustituye** alertas oficiales CONAF/SENAPRED ni el Botón Rojo.

---

## 2. Cómo arrancar la aplicación

### 2.1 Demo en la nube (recomendada para defensa)

1. Abrir la URL de **Streamlit Community Cloud** (rama `main`, entrada `app/app.py`).
2. Python **3.11** en configuración de la app.
3. Secrets: `DATABASE_URL` (Supabase pooler **6543**) y `GRID_MAX_CELLS=50`.
4. Verificar sidebar: build `demo-50cells-v8-professional`, query `exact-date-v1`.

### 2.2 Demo local (Chrome)

**Requisitos:** Python 3.11, dependencias (`pip install -r requirements.txt`), **Docker Desktop** encendido para PostGIS local.

```powershell
cd C:\Users\danie\Desktop\sapi-valparaiso

# 1) Base de datos con seed automático (initdb)
docker compose up db-postgis -d

# 2) Variables (copiar .env.example si no existe .env)
# DATABASE_URL=postgresql://sapi:sapi_secret@localhost:5432/sapi_db
# GRID_MAX_CELLS=50

# 3) Dashboard
$env:GRID_MAX_CELLS="50"
streamlit run app/app.py
```

Abrir en Chrome: **http://localhost:8501**

Si Docker no está activo, la UI puede cargar con **fechas demo de respaldo** (2025-02-09 → 2025-02-15) pero el mapa quedará vacío hasta conectar PostGIS.

---

## 3. Arquitectura de capas

```mermaid
flowchart TB
    subgraph browser [Navegador Chrome]
        UI[app/app.py Streamlit]
    end
    subgraph contract [Data Contract]
        PQ[PredictionQuery]
        DH[date_helpers]
        MR[map_renderer]
    end
    subgraph db [PostGIS SSoT]
        PR[predicciones_riesgo]
        LOG[observability_logs]
    end
    subgraph batch [Pipeline batch - no en caliente en UI]
        ING[ParallelIngester]
        PROC[DataProcessor]
        ML[XGBoost]
    end
    UI --> PQ
    UI --> DH
    UI --> MR
    PQ --> PR
    PQ --> LOG
    ING --> PROC --> ML
    ML -.->|futuro producción| PR
```

| Capa | Carpeta | Rol |
|------|---------|-----|
| Presentación | `app/` | Streamlit + Folium; **solo** importa `src.query` |
| Consulta | `src/query/` | `PredictionQuery`, SQL espacial, fecha exacta |
| Persistencia | PostGIS | `predicciones_riesgo` = serving layer del mapa |
| Analítica | `src/ingesta`, `procesamiento`, `modelo` | ETL + ML (informe; no invocado por la UI) |

Regla blindada por `tests/test_architecture.py`: `app/` **no puede** importar ingesta, procesamiento, modelo ni pipeline.

---

## 4. Flujo exacto de una consulta en el dashboard

### Paso a paso (usuario cambia fecha)

1. **Inicio** — `main()` en `app/app.py` crea `SapiDashboard` y `PredictionQuery()`.

2. **Rango de fechas** — `_cached_date_range()` llama a `resolve_date_range()`:
   - Intenta `PredictionQuery.get_available_date_range()` → SQL `MIN(fecha)`, `MAX(fecha)` en `predicciones_riesgo`.
   - Si falla la BD: fallback **2025-02-09** … **2025-02-15**.

3. **Lista de días** — `_cached_available_dates()` devuelve fechas distintas con datos o las 7 fechas demo.

4. **Selector** — Sidebar:
   - **Slider** `select_slider` sobre fechas disponibles.
   - **Calendario** `date_input` acotado al rango.
   - Si el calendario elige un día sin filas, se usa el valor del slider.

5. **Consulta del mapa** — `query.get_spatial_risk_map(selected_date)`:
   - SQL (`exact-date-v1`): `WHERE p.fecha = :fecha` (fecha **exacta**, no “último snapshot ≤ fecha”).
   - `LIMIT GRID_MAX_CELLS` (50).
   - Retorna `GeoDataFrame` EPSG:4326 con geometría circular desde `geom`.

6. **Error de red/BD** — `try/except` muestra error y llama `get_contingency_cache()` (último estado por celda en ventana desde `MIN(fecha)` del seed).

7. **KPIs y banner** — Conteos `bajo` / `medio` / `alto`, probabilidad máxima, regla 30-30-30.

8. **Mapa** — `render_folium_map(gdf)`:
   - Un `folium.Circle` por celda, radio **564 m** (≈ 1 km²).
   - Color por `nivel_riesgo`: verde / amarillo / rojo.
   - Popup: celda, zona climática, meteo, regla.

9. **Tabla** — 50 filas, columna `#` 1–50, `zona_climatica` derivada de `cell_id`.

10. **Reporte TXT** — Bytes con fecha, build, métricas ML y conteos por nivel.

11. **Logs** — `get_observability_logs(20)` desde `observability_logs`.

### Caché Streamlit

| Función | TTL | Qué cachea |
|---------|-----|------------|
| `_cached_date_range` | 300 s | Min/max fechas |
| `_cached_available_dates` | 300 s | Lista de fechas |
| `_cached_ml_metrics` | 3600 s | `reports/metrics.json` |
| Clave `_build` | — | Invalida caché al cambiar `APP_BUILD` |

---

## 5. Origen de los datos (seed)

### 5.1 ¿De dónde sale el seed?

**No se descargó de DMC, CONAF ni NASA.** Se **genera en el repositorio**:

```text
scripts/generate_seed.py
    → docker/initdb/04_seed_valparaiso.sql
    → PostGIS (Docker initdb o psql a Supabase)
    → reports/seed_summary.json
```

Comando para regenerar:

```powershell
python scripts/generate_seed.py
python scripts/validate_seed.py
```

### 5.2 Grilla espacial (50 celdas)

| Parámetro | Valor | Significado |
|-----------|-------|-------------|
| Diseño | 5 filas × 10 columnas | VP-001 … VP-050 |
| Ancla | lon -71.52, lat -33.04 | Corredor Viña–Quilpué–Villa Alemana |
| Paso | 0.008° (~740–890 m) | Centros de celda |
| Geometría | `ST_Buffer(564 m)` | Círculo ≈ 1 km² de área |
| Zonas (columnas) | 0–2 costa, 3–6 urbano, 7–9 precordillera | Microclimas sintéticos |

Los círculos en el mapa **se superponen** porque el diámetro (~1,1 km) es mayor que la separación entre centros. En producción se usaría un teselado regional sin solape; aquí cada círculo es un **radio de influencia** demo.

### 5.3 Ventana temporal (7 días)

| Fecha | Narrativa | Altos | Regla 30-30-30 |
|-------|-----------|-------|----------------|
| 2025-02-09 | Perfil suave, costa húmeda | 0 | 0 |
| 2025-02-10 … 14 | Calentamiento / sequedad progresiva hacia el este | 0 | 0 |
| **2025-02-15** | Día crítico demo | **2** | **2** (VP-038, VP-049) |

Meteo por día: función `_interp()` con progresión `_day_progress()`. Solo el día pico fuerza T=32.5 °C, HR=24 %, viento=34 km/h en celdas 38 y 49.

### 5.4 Probabilidad y nivel de riesgo

- **Regla 30-30-30:** T > 30 °C, HR < 30 %, viento > 30 km/h → `regla_30_30_30 = 1`, prob = 0.97, nivel `alto`.
- **Sin regla:** `_prob_from_meteo()` con techo por zona (costa ≤ 0.32, urbano ≤ 0.62, precordillera ≤ 0.64).
- **Clasificación:** &lt; 0.33 bajo · &lt; 0.66 medio · ≥ 0.66 alto.

Día pico calibrado: ~15 bajo, ~33 medio, **2 alto**.

### 5.5 Qué NO es el seed

- Series horarias reales MeteoChile (DMC).
- Focos NASA FIRMS en vivo.
- Histórico CONAF 5 años.
- Salida del XGBoost ejecutado sobre esas fechas en el dashboard.

El **informe** describe esas fuentes; el **prototipo** demuestra arquitectura y UX con datos sintéticos coherentes.

---

## 6. Modelo de machine learning (informe vs demo)

| Aspecto | Estado en repo |
|---------|----------------|
| Entrenamiento | `src/modelo/baseline.py`, `optimizer.py` |
| Métricas | `reports/metrics.json`: RF Recall 0.71, XGBoost Recall **0.78**, AUC **0.83** |
| Validación | Temporal + SMOTE solo en train |
| Panel UI | Sidebar lee `metrics.json` (no reentrena) |
| Mapa cloud | Lee `predicciones_riesgo` del **seed SQL** |

Mensaje para defensa: *“Métricas ML verificables en offline; serving layer desacoplada lista para recibir predicciones batch reales.”*

---

## 7. Interfaz — elemento por elemento

### Sidebar

| Elemento | Función |
|----------|---------|
| Build / Query | Versión deploy (`demo-50cells-v8-professional`, `exact-date-v1`) |
| Datos disponibles | Rango min → max desde PostGIS |
| Modelo ML | Recall, AUC, RF baseline |
| Recorrido demo | Slider de 7 fechas |
| Calendario | Selección alternativa |

### Área principal

| Bloque | Contenido |
|--------|-----------|
| Banner azul | Alcance demo, ventana de fechas, disclaimer institucional |
| Banner verde/amarillo | Resumen del día consultado |
| 5 métricas | Celdas, bajo, medio, alto, prob. máxima |
| Mapa Folium | 50 círculos, leyenda oeste→este |
| Tabla | Detalle auditables VP-001…050 |
| Regla 30-30-30 | Texto explicativo |
| Descarga TXT | Reporte ejecutivo |
| Logs | Auditoría `observability_logs` |

---

## 8. Guion de demostración (8 min)

1. **2025-02-09** — Slider al primer día: mayoría verde/amarillo, **0 rojos**, KPI alto = 0.
2. **2025-02-15** — Último día: **2 rojos** (este), regla activa, prob. máx ~97 %.
3. Clic **VP-038** — Popup precordillera, regla activa.
4. Tabla — Filas **#38** y **#49**, columna `regla_30_30_30 = 1`.
5. Sidebar — Recall 0.78 ≥ meta 0.75.
6. Descargar reporte TXT y abrirlo.
7. Cierre — *“Seed sintético calibrado; arquitectura PostGIS + contrato de datos listos para DMC en producción.”*

---

## 9. Despliegue cloud (Supabase + Streamlit)

| Uso | Puerto | Variable |
|-----|--------|----------|
| Streamlit UI | 6543 | `DATABASE_URL` (pooler) |
| DDL / seed batch | 5432 | Conexión directa o pooler 5432 en Windows |

Reaplicar seed:

```powershell
docker run --rm -v "${PWD}:/work" -w /work postgres:15 psql "$env:DATABASE_URL_POOLER" -f docker/initdb/04_seed_valparaiso.sql
```

Verificar:

```sql
SELECT fecha, COUNT(*) FROM predicciones_riesgo GROUP BY fecha ORDER BY fecha;
-- 7 filas × 50 celdas
```

Tras deploy: **Reboot app** en Streamlit Cloud.

---

## 10. Archivos clave

| Archivo | Rol |
|---------|-----|
| `app/app.py` | Dashboard Streamlit |
| `app/utils/map_renderer.py` | Folium, colores, popups |
| `app/utils/cell_zones.py` | Zona climática por VP-XXX |
| `app/utils/date_helpers.py` | Rango/fechas con fallback |
| `app/utils/metrics_loader.py` | Carga `metrics.json` |
| `src/query/prediction_query.py` | Data Contract + SQL |
| `scripts/generate_seed.py` | Generador seed sintético |
| `docker/initdb/04_seed_valparaiso.sql` | 350 INSERTs |
| `reports/seed_summary.json` | Resumen por día |
| `tests/test_architecture.py` | Auditoría Data Contract |

---

## 11. Preguntas frecuentes (evaluadores)

| Pregunta | Respuesta |
|----------|-----------|
| ¿Son datos reales de hoy? | No. Seed zonal multi-fecha calibrado para demo. |
| ¿Por qué cambia el mapa al mover la fecha? | Consulta `fecha = :fecha` sobre 7 snapshots distintos. |
| ¿El modelo corre en Streamlit? | No. UI solo lee `predicciones_riesgo`. |
| ¿Por qué se solapan los círculos? | Radio ~1 km² con centros cada ~0,8 km; demo de influencia, no teselado oficial. |
| ¿Cubre toda la región? | No. 50 celdas en corredor Viña–Quilpué–Villa Alemana. |

---

## 12. Referencias cruzadas

- [Alcance prototipo vs informe](alcance-prototipo.md)
- [Manual presentación defensa](manual-uso-presentacion.md)
- [Checklist entrega](entrega-prototipo.md)
- [Arquitectura](arquitectura.md)
- [Despliegue cloud](deploy.md)

---

*S.A.P.I. — Prototipo académico, Región de Valparaíso, 2026.*

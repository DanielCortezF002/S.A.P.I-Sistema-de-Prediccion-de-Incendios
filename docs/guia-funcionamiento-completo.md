# Guía completa de funcionamiento — S.A.P.I.

Documento técnico y operativo del prototipo **Sistema de Alerta y Predicción de Incendios** (Región de Valparaíso). Describe qué hace cada capa, de dónde salen los datos, cómo fluye una consulta desde el navegador hasta PostGIS y qué es real vs sintético.

---

## 1. Qué es S.A.P.I. en este prototipo

S.A.P.I. es una plataforma de **apoyo a la decisión preventiva** que:

1. Integra variables ambientales (en el informe: meteo, topografía, histórico de igniciones).
2. Estima **probabilidad de ignición** por celda territorial (resolución objetivo del informe: ~1 km²; esta demo usa 50 celdas de ~11,5 km² para que el corredor completo entre en pantalla — ver [`alcance-prototipo.md`](alcance-prototipo.md)).
3. Visualiza el riesgo en un **mapa interactivo** antes de que ocurra un foco visible.

En **esta demo académica** (`SAPI_DATA_MODE=demo_seed` por defecto en [`src/config.py`](../src/config.py)):

- El mapa lee el **escenario sembrado en memoria** (`demo_seed` vía `get_demo_gdf`), no ejecuta ML en el navegador.
- Los datos del dashboard son un **seed sintético multi-fecha** (7 días × 50 celdas), calibrado por zona climática.
- El modelo XGBoost está entrenado y documentado (`reports/metrics.json`); las celdas del mapa **no** son salida del modelo en runtime. En particular, **VP-038** y **VP-049** el **2025-02-15** son escenario sembrado para la presentación.

**No sustituye** alertas oficiales CONAF/SENAPRED ni el Botón Rojo.

---

## 2. Cómo arrancar la aplicación

### 2.1 Demo en la nube (recomendada para defensa)

1. Abrir la URL de **Streamlit Community Cloud** (rama `main`, entrada `app/app.py`).
2. Python **3.11** en configuración de la app.
3. Secrets: `DATABASE_URL` (Supabase pooler **6543**) y `GRID_MAX_CELLS=50`.
4. Verificar sidebar, dentro de “Detalles técnicos”: build `demo-corredor-50cells-v9`, query `exact-date-v1`.

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

> **Runtime Hito 1:** `SAPI_DATA_MODE=demo_seed` (default). El flujo PostGIS descrito al final aplica solo con `postgis_inference` (Sprint 2).

### Paso a paso (usuario cambia fecha) — modo `demo_seed`

1. **Inicio** — `main()` en `app/app.py` crea `SapiDashboard` (incluye `PredictionQuery()` para compatibilidad futura, pero **no lo usa** para cargar el mapa en demo).

2. **Rango de fechas** — `_cached_date_range()` lee `get_all_demo_dates()` del seed en memoria → **2025-02-09** … **2025-02-15**.

3. **Lista de días** — `_cached_available_dates()` devuelve las 7 fechas del seed demo.

4. **Selector** — Sidebar: `selectbox` de días con datos + calendario acotado al rango demo.

5. **Carga del mapa** — `get_demo_gdf(selected_date)` (lru_cache en RAM). **No** hay SQL ni PostGIS en este paso.

6. **KPIs y banner** — Conteos `bajo` / `medio` / `alto`, probabilidad máxima, regla 30-30-30. Banner azul (`_render_demo_scope_banner`) indica `SAPI_DATA_MODE`, ventana demo y aclara que **VP-038** / **VP-049** el 15-feb son **escenario sembrado**, no predicción XGBoost en runtime. Badge sidebar (`_render_data_mode_badge`) declara fuente del mapa.

7. **Mapa** — `render_folium_map(gdf)`:
   - Un `folium.Circle` por celda, radio **1.917 m** (≈ 11,5 km²), derivado de `app/utils/grid.py`.
   - Color por `nivel_riesgo`: verde / ámbar / rojo.
   - Popup: celda, zona climática, meteo, regla.

8. **Tabla** — 50 filas, columna `#` 1–50, `zona_climatica` derivada de `cell_id`.

9. **Reporte TXT** — Bytes con fecha, build, métricas ML, conteos por nivel y footer `data_source=demo_seed` + `SAPI_DATA_MODE`.

10. **Logs** — En demo: tabla vacía con mensaje “Sin conexión a PostGIS activa”.

### Flujo alternativo — modo `postgis_inference` (Sprint 2)

1. `PredictionQuery.get_available_date_range()` → SQL `MIN(fecha)`, `MAX(fecha)` en `predicciones_riesgo`.
2. `query.get_spatial_risk_map(selected_date)` con contrato `exact-date-v1` (`WHERE p.fecha = :fecha`, `LIMIT GRID_MAX_CELLS`).
3. Fallback `get_contingency_cache()` si falla la BD.

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

### 5.2 Grilla espacial del seed PostGIS (50 celdas)

> Desde la unificación de grillas (2026-09-06), el seed de PostGIS
> (`scripts/generate_seed.py`) usa **la misma geometría que el dashboard**:
> `src/geo/grid.py`, re-exportada por `app/utils/grid.py`. Antes tenía su
> propia copia, ~15x más pequeña por celda; ver *Deuda técnica: dos grillas
> conviviendo* en [`alcance-prototipo.md`](alcance-prototipo.md) para el
> historial.

| Parámetro | Valor | Significado |
|-----------|-------|-------------|
| Diseño | 5 filas × 10 columnas | VP-001 … VP-050 |
| Ancla | lon -71.58, lat -33.14 | Corredor Viña–Quilpué–precordillera |
| Paso | 0.0411° / 0.035° (~3,8 km) | Centros de celda |
| Geometría | `ST_Buffer(1.917 m)` | Círculo ≈ 11,5 km² de área |
| Zonas (columnas) | 0–1 costa, 2–6 urbano, 7–9 precordillera | Microclimas sintéticos |

El radio (`CELL_RADIUS_METERS` en `src/geo/grid.py`) se deriva de la
separación real entre centros de celda, no es un literal calibrado a mano:
los círculos se tocan en los bordes sin superponerse.

### 5.3 Ventana temporal (7 días)

| Fecha | Narrativa | Altos | Regla 30-30-30 |
|-------|-----------|-------|----------------|
| 2025-02-09 | Perfil suave, costa húmeda | 0 | 0 |
| 2025-02-10 … 14 | Calentamiento / sequedad progresiva hacia el este | 0 | 0 |
| **2025-02-15** | Día crítico demo (escenario sembrado) | **2** | **2** (VP-038, VP-049) |

Meteo por día: función `_interp()` con progresión `_day_progress()`. Solo el día pico fuerza T=32.5 °C, HR=24 %, viento=34 km/h en celdas 38 y 49. Esos dos puntos rojos **no** provienen de una corrida del XGBoost en el dashboard; están definidos en el seed para ilustrar la regla 30-30-30.

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
| Métricas | `reports/metrics.json`: **sin corrida real de recall/AUC-ROC todavía** (0.71/0.78/0.83 eran mock de test en `tests/test_pipeline.py`, hallazgo y corrección en `c22c9a1`). Exploratorio R-ETIQUETA-01 (n=12, Sprint 2): percentil de riesgo 92-99 en los 3 casos sin fuga de datos, sin calibración suficiente para umbral de decisión. |
| Validación | Temporal + SMOTE solo en train |
| Panel UI | Sidebar lee `metrics.json` (no reentrena) |
| Mapa cloud | Lee `predicciones_riesgo` del **seed SQL** |

Mensaje para defensa: *”Pipeline ML implementado y funcional (RF + XGBoost + SMOTE, validación temporal); métrica real de recall/AUC-ROC pendiente de una corrida en temporada de incendios (hallazgo de métricas fabricadas corregido en `c22c9a1`); serving layer desacoplada lista para recibir predicciones batch reales.”*

---

## 7. Interfaz — elemento por elemento

### Sidebar

De arriba abajo, en el orden en que aparecen:

| Elemento | Función |
|----------|---------|
| **Modo Demo** (badge) | Primero y sin colapsar: `SAPI_DATA_MODE=demo_seed` — fuente escenario sembrado, no inferencia en runtime |
| Recorrido demo | `selectbox` con los 7 días que tienen datos (no un slider) |
| Calendario | Selección alternativa, acotada al rango del seed |
| **Detalles técnicos** (colapsado) | Al fondo: panel ML (Recall XGBoost, AUC-ROC, Recall RF baseline — muestran `—` mientras no haya una corrida real), Build / Query, rango de fechas y el valor crudo de `SAPI_DATA_MODE` |

La jerarquía es deliberada: lo que declara si los datos son reales va arriba y
visible; la metadata de trazabilidad académica va un clic más adentro.

### Área principal

> Reescrito 06-09-2026: la tabla anterior describía un layout de pestañas
> ("Mapa de riesgo" / "Detalle por celda") que ya no existe en `app/app.py`.
> Esto es el orden real de `main()`, componente por componente
> (`app/components/ops_layout.py`, `banner.py`, `day_alerts.py`,
> `risk_sparkline.py`, `risk_map.py`).

| # | Bloque | Contenido |
|---|--------|-----------|
| 1 | Header + interruptor de apariencia | Marca S.A.P.I., chip DMC en vivo/sin dato, chip de escenario (`SAPI_DATA_MODE`), hora local; claro/oscuro a la derecha |
| 2 | Banner de corredor | Alcance demo, extensión y resolución de la grilla, comunas con evidencia real de detecciones, VP-038/VP-049 como escenario sembrado, disclaimer institucional, nota de verificación SUBDERE |
| 3 | **Mayor riesgo ahora** | Bloque dominante: celda de mayor riesgo, nivel, ubicación, desglose de la regla 30-30-30 (condición por condición, con valor y umbral) |
| 3b | **Top zonas prioritarias** / **Tendencia del riesgo** | Dos columnas: lista de todas las celdas en riesgo alto (no solo la #1) ordenadas por probabilidad, con botón para seleccionar cualquiera; y evolución del máximo diario de probabilidad en la ventana de 7 días del seed (`app/components/day_alerts.py`, `risk_sparkline.py`) |
| 4 | Tarjetas de variable | Temperatura, humedad relativa y viento de la celda foco + tarjeta DMC Rodelillo en vivo, con tendencia respecto al día anterior |
| 5 | Buscador de comuna + Mapa + Panel de detalle | Buscador filtra por banda climática; mapa Folium (izq., ~55% del ancho) con círculos de riesgo y clic para seleccionar; panel de detalle (der.) con meteo, regla 30-30-30, topografía DEM, historial FIRMS y procedencia de la celda seleccionada |
| 6 | Leyenda de 4 estados | Bajo, Medio, Alto, Sin dato — con descripción de cada uno |
| 7 | Auditoría y transparencia | Qué está verificado con datos reales, qué es simulado en esta vista, riesgo abierto R-ETIQUETA-01 |
| 8 | Descarga TXT | Reporte ejecutivo con footer `data_source=demo_seed` |

Mapa y panel de detalle están en **columnas lado a lado** (~55/45), no en
pestañas: en escritorio se ven ambos a la vez; en móvil, Streamlit apila las
columnas verticalmente. "Top zonas prioritarias" reutiliza la selección de
celda (clic en una alerta o en el mapa apuntan al mismo estado —
`app.state.select_cell`), así que ambos caminos llevan al mismo panel de
detalle.

---

## 8. Guion de demostración (8 min)

1. **2025-02-09** — Selector al primer día: mayoría verde/ámbar, **0 rojos**, KPI alto = 0.
2. **2025-02-15** — Último día: **2 rojos** (este), regla activa, prob. máx ~97 %.
3. Clic **VP-038** — Popup precordillera, regla activa.
4. Detalle — tarjeta de **VP-038** / **VP-049**, regla 30-30-30 activa.
5. Sidebar — muestra "sin corrida real todavía" (no 0.78/0.83); si preguntan, mencionar el hallazgo de métricas fabricadas (`c22c9a1`) y el exploratorio R-ETIQUETA-01.
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
| ¿Por qué quedan huecos entre los círculos? | El radio (1.917 m) es la mitad de la separación entre centros (~3,8 km): se tocan en los bordes y dejan hueco en las esquinas. Radio de influencia demo, no teselado oficial. |
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

# Manual de uso y guion de presentación — S.A.P.I.

**Audiencia:** comisión evaluadora, profesor guía y perfiles tipo analista CONAF / SENAPRED.  
**Versión:** prototipo académico (demo 50 celdas, ventana multi-día).  
**Ventana demo:** 2025-02-09 → 2025-02-15 (7 días). **Día crítico de referencia:** 2025-02-15.

---

## 1. Qué es S.A.P.I. (mensaje para organismos de emergencia)

**S.A.P.I.** (Sistema de Alerta y Predicción de Incendios) es una plataforma de **apoyo a la decisión preventiva** que:

1. Integra variables ambientales (meteorología, topografía, histórico de igniciones — en la versión objetivo del informe).
2. Estima la **probabilidad de ignición** por celda territorial (~1 km²).
3. Visualiza el riesgo en un **mapa interactivo** antes de que ocurra un foco visible.

**No reemplaza** protocolos oficiales, el Botón Rojo, ni el despacho de brigadas. El analista humano sigue siendo quien decide.

**Cambio de paradigma que propone:** pasar de “actuar cuando ya hay humo” a **priorizar cuadrantes de mayor riesgo** al inicio de la jornada crítica.

---

## 2. Cómo funcionaría en operación real (visión institucional)

Flujo objetivo para CONAF / SENAPRED en temporada estival:

```text
Madrugada (automático)          Mañana (analista)              Terreno (brigadas)
─────────────────────          ─────────────────              ──────────────────
Ingesta APIs (DMC, NASA,       Abre dashboard S.A.P.I.        Pre-posicionamiento
CONAF) → PostGIS               Revisa mapa y tabla            en celdas rojas/ámbar
Pipeline ML precalcula         Exporta reporte al comité       Patrullaje reforzado
predicciones por celda         07:00 COGRID / sala de mando    en interfaz crítica
```

| Rol | Uso de S.A.P.I. |
|-----|-----------------|
| **Analista de sala** | Consulta mapa diario, identifica celdas alto/medio, cruza con protocolo interno. |
| **Jefe de operaciones** | Usa reporte TXT/export para reunión de coordinación matinal. |
| **Brigada** | Recibe priorización geográfica (en producción: integración futura vía API/webhook). |

En **este prototipo**, el paso nocturno automático está simulado: los datos vienen de un **seed calibrado** en PostGIS, no de APIs en vivo.

---

## 3. Acceso al prototipo

### Demo en la nube (recomendado para la presentación)

1. Abrir la URL publicada en **Streamlit Community Cloud** (repositorio `S.A.P.I-Sistema-de-Prediccion-de-Incendios`, rama `main`, entrada `app/app.py`).
2. Navegador: Chrome, Firefox o Edge (escritorio).
3. No requiere instalación ni cuenta de usuario.

### Demo local (respaldo si falla internet)

```bash
docker compose up db-postgis -d
streamlit run app/app.py
```

Abrir `http://localhost:8501`.

---

## 4. Recorrido por la interfaz (5 minutos)

### 4.1 Barra lateral

| Elemento | Significado |
|----------|-------------|
| **Build** | Versión del prototipo demo (ej. `demo-corredor-50cells-v9`), dentro de “Detalles técnicos”. |
| **Query** | Motor de consulta PostGIS (`exact-date-v1`) — activo cuando `SAPI_DATA_MODE=postgis_inference`. |
| **Modo Demo** (badge) | `SAPI_DATA_MODE=demo_seed`: probabilidades y niveles provienen del **escenario sembrado**, no de inferencia XGBoost en runtime. |
| **Métricas ML** | Panel sidebar: **sin corrida real de recall/AUC-ROC todavía** (el 0.78/0.83 citado antes era mock de test en `reports/metrics.json`, corregido en `c22c9a1`). Exploratorio R-ETIQUETA-01 (n=12, Sprint 2): percentil de riesgo 92-99 en los 3 casos sin fuga de datos, sin calibración suficiente para umbral de decisión. |
| **Recorrido demo** | Selector de los 7 días con datos + calendario acotado a esa ventana. |
| **Fecha de consulta** | Día exacto con predicciones cargadas. Rango demo: **2025-02-09** a **2025-02-15**. Default: **2025-02-15** (último día). |

### 4.2 Banners informativos

- **Banner azul superior:** aclara demo académica, `SAPI_DATA_MODE=demo_seed`, 50 celdas, ventana **2025-02-09 → 2025-02-15**, datos sintéticos calibrados. **Importante:** **VP-038** y **VP-049** el **2025-02-15** son un **escenario sembrado** para la presentación — **no** salida del modelo XGBoost en tiempo real.
- **Banner de consulta:** resume celdas cargadas, conteos bajo/medio/alto y regla 30-30-30 para la **fecha exacta** seleccionada.

### 4.3 Indicadores (KPIs)

| KPI | Interpretación operativa |
|-----|--------------------------|
| **Celdas monitoreadas** | Cuántos cuadrantes de ~11,5 km² hay en la grilla (50 en demo). |
| **Riesgo bajo / medio / alto** | Conteo por nivel para la fecha seleccionada. |
| **Día 2025-02-15** | 15 bajo · 33 medio · **2 alto** (VP-038, VP-049). |
| **Día 2025-02-09** | Sin celdas rojas; mayoría verde/ámbar. |

### 4.4 Mapa interactivo

- Cada **círculo** ≈ 11,5 km² de radio de influencia (radio 1.917 m).
- **Verde:** riesgo bajo (costa / condiciones húmedas).
- **Ámbar:** riesgo medio (zona urbana de transición).
- **Rojo:** riesgo alto (precordillera con condiciones extremas).
- **Clic en una celda:** popup con celda (`VP-XXX`), zona climática, probabilidad, temperatura, humedad, viento y estado de la regla 30-30-30.
- Controles: zoom (+/−) y capa opcional con las detecciones NASA FIRMS del 2024-02-03. Mapa base Esri World Light Gray.
- El mapa y la tabla están en **pestañas** (“Mapa de riesgo” / “Detalle por celda”), no lado a lado — así el mapa usa el ancho completo y la vista funciona en teléfono.

**Distribución esperada en demo (2025-02-15):**

- Oeste (litoral): mayormente verde.
- Centro: ámbar.
- Este (precordillera): solo **VP-038** y **VP-049** en rojo con regla activa.

### 4.5 Tabla “Detalle por celda”

- Columna **#** del **1 al 50** (orden VP-001 → VP-050).
- Permite auditar celda por celda sin depender solo del mapa.
- Pie de tabla: `50 registros (VP-001 a VP-050)`.

### 4.6 Regla del 30-30-30

Condición crítica simultánea:

- Temperatura **> 30 °C**
- Humedad relativa **< 30 %**
- Viento **> 30 km/h**

En demo, solo **VP-038** y **VP-049** cumplen las tres (32.5 °C, 24 %, 34 km/h). El sistema las marca con `regla_30_30_30 = 1`.

### 4.7 Descarga de reporte

- Botón **“Descargar reporte (TXT)”**: resumen ejecutivo (fecha, conteo por nivel, probabilidad máxima).
- Pie del archivo: `data_source=demo_seed` y `SAPI_DATA_MODE=demo_seed` (trazabilidad de fuente).
- Útil para simular envío a comité de emergencia cuando no hay conectividad al dashboard.

### 4.8 Logs de observabilidad

- Expander inferior: trazas de ingesta, consultas y eventos del sistema (auditoría técnica).

---

## 5. Guion sugerido para el viernes (10–12 min)

### Minuto 0–2 — Problema y propuesta

> “Hoy las alertas suelen ser reactivas y a escala comunal. S.A.P.I. anticipa **dónde** es más probable una ignición mañana, a resolución objetivo de 1 km², para apoyar el posicionamiento preventivo de brigadas. La demo que van a ver usa 50 celdas de ~11,5 km² sobre el corredor, para que el corredor completo entre en pantalla.”

### Minuto 2–4 — Arquitectura (una diapositiva)

Mostrar: fuentes → PostGIS (SSoT) → ML precalculado → dashboard desacoplado.  
Enfatizar: **la UI no ejecuta el modelo en caliente**; lee predicciones ya guardadas.

### Minuto 4–8 — Demo en vivo (cambio de fecha)

1. Abrir dashboard; señalar badge **Modo Demo** y banner de demo académica (VP-038/VP-049 = escenario sembrado).
2. Fecha: **2025-02-09** → mapa mayormente verde/ámbar, **0 rojos**, KPI alto = 0.
3. Cambiar a **2025-02-15** → mapa evoluciona; **2 rojos** (VP-038, VP-049), regla activa.
4. Verificar KPIs: **50 celdas**, **2 alto**, conteos bajo/medio coherentes.
5. Mapa: oeste verde → centro ámbar → este dos rojos.
6. Clic en **VP-038**: leer popup (precordillera, regla activa).
7. Tabla: scroll a **# 38** y **# 49**; mostrar columna `regla_30_30_30`.
8. Descargar reporte TXT (incluye fecha consultada) y abrirlo 5 segundos.

### Minuto 8–10 — Métricas ML y alcance

> “Encontramos y corregimos un hallazgo de ingeniería: `reports/metrics.json` citaba Recall 0.78 / AUC 0.83 desde junio, pero eran valores de mock de `tests/test_pipeline.py` — nunca hubo una corrida real detrás (commit `c22c9a1`). Hoy no tenemos una métrica de recall/AUC-ROC de producción; sí una exploración honesta con los 12 incendios reales confirmados disponibles: en los ÚNICOS 3 casos disponibles sin fuga de datos (de un total de apenas 12), el modelo ubicó al incendio real por encima del percentil 90 frente a los negativos de ese fold — un indicio, no una validación, dado el tamaño de muestra. Queda como investigación abierta para Sprint 2 (R-ETIQUETA-01). Este despliegue usa **50 celdas sintéticas** del corredor Viña–Quilpué–Villa Alemana; la arquitectura escala a región completa con las mismas APIs del informe.”

Ver [`reports/metrics.json`](../reports/metrics.json) y [`docs/alcance-prototipo.md`](alcance-prototipo.md).

### Minuto 10–12 — Preguntas frecuentes

Tener preparadas las respuestas de la sección 7.

---

## 6. Escenario narrativo para la comisión (role-play)

**Contexto:** viernes 15 de febrero de 2025, 06:30, sala regional Valparaíso.

1. El analista abre S.A.P.I. y selecciona la fecha del día.
2. Identifica **VP-038** y **VP-049** en precordillera con regla 30-30-30 activa.
3. Comunica al jefe de operaciones: “Dos cuadrantes al este de Quilpué con condición extrema; recomiendo reforzar patrullaje antes de las 10:00.”
4. El resto de la grilla permanece en verde/ámbar → no dispersar brigadas en toda la provincia.
5. A las 07:00, adjunta el **reporte TXT** al acta del comité.

**Mensaje clave:** el sistema **prioriza** recursos; no emite órdenes automáticas.

---

## 7. Preguntas que pueden hacer y cómo responder

| Pregunta | Respuesta honesta |
|----------|-------------------|
| ¿Son datos reales de hoy? | No. Es un **seed zonal calibrado** para demo. La arquitectura está lista para conectar DMC/CONAF/NASA. |
| ¿Cubre toda la región? | No. **50 celdas** en corredor crítico. El informe proyecta cobertura completa. |
| ¿Sustituye al Botón Rojo? | No. Lo **complementa** con resolución fina y probabilidad por celda. |
| ¿Quién decide el despacho? | Siempre el **analista institucional** (human-in-the-loop). |
| ¿Por qué solo 2 celdas rojas? | Por diseño del **escenario sembrado**: solo VP-038 y VP-049 cumplen regla 30-30-30 el 15-feb; no es predicción del XGBoost en runtime. |
| ¿VP-049 es predicción del modelo? | **No.** Es celda del seed demo calibrada para ilustrar riesgo alto + regla activa en precordillera. |
| ¿Qué pasa si falla una API? | En producción: degradación con último snapshot válido (escenario 2 del informe). |
| ¿Cómo se validó el modelo? | RF baseline + XGBoost, SMOTE en train, validación temporal — implementado y funcional, pero **sin corrida real de recall/AUC-ROC todavía** (el 0.78 citado antes era mock de test, corregido en `c22c9a1`). Exploratorio honesto (n=12 incendios reales, Sprint 2): percentil de riesgo 92-99 en los 3 casos sin fuga de datos, sin calibración suficiente para una decisión binaria. |

---

## 8. Límites explícitos de este prototipo (decirlo en voz alta)

- Sin integración directa a sistemas cerrados CONAF/SENAPRED.
- Sin cobertura 100 % regional ni ingesta horaria en cloud.
- Sin export PDF institucional (solo TXT en demo).
- Sin NDVI/EVI ni DEM en el seed actual.
- Sin geolocalización de brigadas en tiempo real.

Detalle técnico: [`docs/alcance-prototipo.md`](alcance-prototipo.md).

---

## 9. Checklist pre-presentación (viernes)

- [ ] Streamlit Cloud en **Python 3.11** y app en estado *Running*.
- [ ] URL del dashboard abierta en pestaña de respaldo.
- [ ] Fechas probadas: **2025-02-09** (0 rojos) y **2025-02-15** (2 rojos).
- [ ] Badge **Modo Demo** visible (`SAPI_DATA_MODE=demo_seed`).
- [ ] Build `demo-corredor-50cells-v9`, Query `exact-date-v1` (en “Detalles técnicos”).
- [ ] Panel ML sidebar visible (muestra "sin corrida real todavía", **no** 0.78/0.83).
- [ ] Mapa con gradiente oeste→este y 2 rojos (VP-038, VP-049).
- [ ] Tabla con columna # 1–50.
- [ ] Reporte TXT descarga correctamente (footer `data_source=demo_seed`).
- [ ] Diapositiva con el hallazgo de métricas fabricadas (commit `c22c9a1`) y el exploratorio R-ETIQUETA-01 (percentil >90, n=3 sin fuga de 12) — no Recall/AUC como si fueran de producción.
- [ ] Frase de cierre: *“Prototipo de viabilidad técnica; arquitectura transferible a operación institucional.”*

---

## 10. Referencias rápidas

| Recurso | Ubicación |
|---------|-----------|
| Código dashboard | [`app/app.py`](../app/app.py) |
| Arquitectura | [`docs/arquitectura.md`](arquitectura.md) |
| Despliegue cloud | [`docs/deploy.md`](deploy.md) |
| Alcance vs informe | [`docs/alcance-prototipo.md`](alcance-prototipo.md) |
| Checklist entrega | [`docs/entrega-prototipo.md`](entrega-prototipo.md) |
| Métricas modelo | [`reports/metrics.json`](../reports/metrics.json) |
| Repositorio | [github.com/DanielCortezF002/S.A.P.I-Sistema-de-Prediccion-de-Incendios](https://github.com/DanielCortezF002/S.A.P.I-Sistema-de-Prediccion-de-Incendios) |

---

*Documento elaborado para defensa de titulación — S.A.P.I., Región de Valparaíso, 2026.*

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
| **Build** | Versión del prototipo demo (ej. `demo-50cells-v7-multiday`). |
| **Query** | Motor de consulta PostGIS (`exact-date-v1`). |
| **Fecha de consulta** | Día exacto con predicciones cargadas. Rango demo: **2025-02-09** a **2025-02-15**. Default: **2025-02-15** (último día). |

### 4.2 Banners informativos

- **Banner azul superior:** aclara demo académica, 50 celdas, ventana **2025-02-09 → 2025-02-15**, datos sintéticos calibrados.
- **Banner de consulta:** resume celdas cargadas, conteos bajo/medio/alto y regla 30-30-30 para la **fecha exacta** seleccionada.

### 4.3 Indicadores (KPIs)

| KPI | Interpretación operativa |
|-----|--------------------------|
| **Celdas monitoreadas** | Cuántos cuadrantes de ~1 km² hay en la grilla (50 en demo). |
| **Riesgo bajo / medio / alto** | Conteo por nivel para la fecha seleccionada. |
| **Día 2025-02-15** | 15 bajo · 33 medio · **2 alto** (VP-038, VP-049). |
| **Día 2025-02-09** | Sin celdas rojas; mayoría verde/amarillo. |

### 4.4 Mapa interactivo

- Cada **círculo** ≈ 1 km² de radio de influencia.
- **Verde:** riesgo bajo (costa / condiciones húmedas).
- **Amarillo:** riesgo medio (zona urbana de transición).
- **Rojo:** riesgo alto (precordillera con condiciones extremas).
- **Clic en una celda:** popup con celda (`VP-XXX`), zona climática, probabilidad, temperatura, humedad, viento y estado de la regla 30-30-30.
- Controles: zoom (+/−), capas OpenStreetMap.

**Distribución esperada en demo (2025-02-15):**

- Oeste (litoral): mayormente verde.
- Centro: amarillo.
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
- Útil para simular envío a comité de emergencia cuando no hay conectividad al dashboard.

### 4.8 Logs de observabilidad

- Expander inferior: trazas de ingesta, consultas y eventos del sistema (auditoría técnica).

---

## 5. Guion sugerido para el viernes (10–12 min)

### Minuto 0–2 — Problema y propuesta

> “Hoy las alertas suelen ser reactivas y a escala comunal. S.A.P.I. anticipa **dónde** es más probable una ignición mañana, a resolución de 1 km², para apoyar el posicionamiento preventivo de brigadas.”

### Minuto 2–4 — Arquitectura (una diapositiva)

Mostrar: fuentes → PostGIS (SSoT) → ML precalculado → dashboard desacoplado.  
Enfatizar: **la UI no ejecuta el modelo en caliente**; lee predicciones ya guardadas.

### Minuto 4–8 — Demo en vivo (cambio de fecha)

1. Abrir dashboard; señalar banner de demo académica y rango de fechas.
2. Fecha: **2025-02-09** → mapa mayormente verde/amarillo, **0 rojos**, KPI alto = 0.
3. Cambiar a **2025-02-15** → mapa evoluciona; **2 rojos** (VP-038, VP-049), regla activa.
4. Verificar KPIs: **50 celdas**, **2 alto**, conteos bajo/medio coherentes.
5. Mapa: oeste verde → centro amarillo → este dos rojos.
6. Clic en **VP-038**: leer popup (precordillera, regla activa).
7. Tabla: scroll a **# 38** y **# 49**; mostrar columna `regla_30_30_30`.
8. Descargar reporte TXT (incluye fecha consultada) y abrirlo 5 segundos.

### Minuto 8–10 — Métricas ML y alcance

> “XGBoost alcanza Recall **0.78** (umbral informe ≥ 0.75) y AUC **0.83** sobre validación temporal. Este despliegue usa **50 celdas sintéticas** del corredor Viña–Quilpué–Villa Alemana; la arquitectura escala a región completa con las mismas APIs del informe.”

Ver [`reports/metrics.json`](../reports/metrics.json) y [`docs/alcance-prototipo.md`](alcance-prototipo.md).

### Minuto 10–12 — Preguntas frecuentes

Tener preparadas las respuestas de la sección 7.

---

## 6. Escenario narrativo para la comisión (role-play)

**Contexto:** viernes 15 de febrero de 2025, 06:30, sala regional Valparaíso.

1. El analista abre S.A.P.I. y selecciona la fecha del día.
2. Identifica **VP-038** y **VP-049** en precordillera con regla 30-30-30 activa.
3. Comunica al jefe de operaciones: “Dos cuadrantes al este de Quilpué con condición extrema; recomiendo reforzar patrullaje antes de las 10:00.”
4. El resto de la grilla permanece en verde/amarillo → no dispersar brigadas en toda la provincia.
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
| ¿Por qué solo 2 celdas rojas? | Por diseño del seed corregido: solo 2 cumplen regla 30-30-30; el resto refleja microclimas costa/urbano. |
| ¿Qué pasa si falla una API? | En producción: degradación con último snapshot válido (escenario 2 del informe). |
| ¿Cómo se validó el modelo? | RF baseline + XGBoost, SMOTE en train, validación temporal; Recall XGBoost 0.78. |

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
- [ ] Build `demo-50cells-v7-multiday`, Query `exact-date-v1`.
- [ ] Mapa con gradiente oeste→este y 2 rojos (VP-038, VP-049).
- [ ] Tabla con columna # 1–50.
- [ ] Reporte TXT descarga correctamente.
- [ ] Diapositiva con métricas ML (Recall 0.78, AUC 0.83).
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

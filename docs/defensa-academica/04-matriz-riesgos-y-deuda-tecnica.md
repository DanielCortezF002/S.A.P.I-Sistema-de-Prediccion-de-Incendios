# S.A.P.I. — Matriz de Riesgos, Deuda Técnica y Limitaciones

**Documento de Transparencia Académica y Gobernanza de Software**  
**Proyecto:** Sistema de Alerta y Priorización de Riesgo de Incendios Forestales (S.A.P.I.)  
**Fecha:** Octubre 2026  
**Rama:** `feat/ui-academic-defense-hardening`  

---

## 1. Propósito del Documento

En una defensa académica de ingeniería, la madurez de un equipo no se demuestra ocultando los problemas, sino **clasificándolos, midiéndolos y gestionándolos con transparencia**. Este documento discrimina taxativamente entre:

1. **Defectos Visuales:** Problemas de contraste, tipografía y componentes en la interfaz.
2. **Deuda Técnica:** Compromisos de diseño o implementación asumidos conscientemente para cumplir plazos sin violar la estabilidad.
3. **Funcionalidades Pendientes (Backlog):** Capacidades planificadas para versiones posteriores que no formaban parte del alcance del Sprint 2.
4. **Limitaciones Científicas:** Restricciones matemáticas y estadísticas intrínsecas del Modelo D que impiden su uso como sistema de alerta oficial.

---

## 2. Clasificación Cuadridimensional

```
┌────────────────────────────────────────────────────────────────────────┐
│                   MAPA DE RIESGOS Y LIMITACIONES                       │
│                                                                        │
│   [1. DEFECTOS VISUALES]              [2. DEUDA TÉCNICA]               │
│   • Contraste selectores (Resuelto)   • Duplicación config theme       │
│   • Expansores ilegibles (Resuelto)   • Dependencia GDAL en Docker     │
│   • Tipografía proyectada (Resuelto)  • TTL estático de 5 min en UI    │
│                                                                        │
│   [3. BACKLOG / PENDIENTES]           [4. LIMITACIONES CIENTÍFICAS]    │
│   • Telemetría en contrato v1         • F4 en FAIL (Sin validación op) │
│   • Filtro espacial por comuna v2     • Ranking relativo, no % prob    │
│   • Autenticación OAuth2 / JWT        • Sin datos satelitales en vivo  │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Matriz Detallada de Elementos

### Categoría 1: Defectos Visuales y de UX

| ID | Elemento | Estado | Diagnóstico | Resolución / Mitigación |
| :--- | :--- | :--- | :--- | :--- |
| **VIS-01** | Encabezados de Expansores (`st.expander`) | **RESUELTO** | En modo oscuro nativo, el encabezado heredaba estilos tenues de bajo contraste, haciendo invisible el texto *"Ver ranking completo"*. | Se incorporaron reglas CSS forzadas en `app/theme/css.py` con fondo de tarjeta `surface_card`, borde definido y chevron en color de acento. |
| **VIS-02** | Contraste de Selectores (`st.selectbox`) | **RESUELTO** | El dropdown de selección de celdas generaba menús flotantes claros con bordes desfasados del fondo general. | Se estilizó el contenedor BaseWeb (`div[data-baseweb="select"]` y `div[data-baseweb="popover"]`) con tokens oscuros consistentes. |
| **VIS-03** | Tipografía para Proyección en Sala | **RESUELTO** | Textos en 10px-11px resultaban ilegibles en proyectores a 5 metros de distancia. | Se escaló la tipografía base: títulos a 2.1rem, números KPI a 1.55rem, etiquetas a 0.85rem y cuerpo a 0.95rem. |
| **VIS-04** | Dependencia de Overlay Temporal (`$env:TEMP`) | **RESUELTO** | La corrección de tema dependía de un archivo `.yml` temporal en la máquina del operador. | Se consolidó la configuración directamente en `docker-compose.yml` (`command` con parámetros `--theme.*`), haciéndola reproducible en cualquier equipo. |
| **VIS-05** | Indicadores de Meteorología *"no informados"* | **MITIGADO** | Cuatro tarjetas de KPI mostraban *"no informado por el backend"* generando sensación de fallo. | Se mantuvo la integridad del contrato v0 y se agregó una nota aclaratoria destacada explicando que las variables son procesadas por el modelo en inferencia y catalogadas para exposición en v1. |

---

### Categoría 2: Deuda Técnica Asumida

| ID | Título | Severidad | Justificación de la Deuda | Plan de Remediación |
| :--- | :--- | :--- | :--- | :--- |
| **DEB-01** | Duplicación de Colores en `config.toml` | **Media** | Streamlit lee `.streamlit/config.toml` antes de iniciar el intérprete Python, impidiendo importar dinámicamente desde `tokens.py`. | Se mantiene sincronizado mediante la prueba unitaria automatizada `test_theme_config_matches_tokens`. |
| **DEB-02** | Peso de la Imagen de Inferencia (`ml-api`) | **Baja** | `Dockerfile.ml-api` requiere compiladores de C++ y librerías geoespaciales (`libgdal-dev`, `libgeos-dev`), resultando en una imagen de ~1.8 GB. | Para producción se evaluará multistage build o uso de imágenes base optimizadas de Conda-Forge. |
| **DEB-03** | Invalidador de Caché Manual en UI | **Baja** | La invalidación de caché en Streamlit ante nuevos datos requiere presionar *"Actualizar ranking"* o esperar 300 segundos. | Implementar WebSockets o Server-Sent Events (SSE) desde Spring Boot en el Sprint 3. |

---

### Categoría 3: Funcionalidades Pendientes (Backlog Futuro)

| ID | Funcionalidad | Alcance Original Sprint 2 | Estado Actual | Roadmap Futuro |
| :--- | :--- | :--- | :--- | :--- |
| **FUT-01** | Contrato REST v1 con Telemetría Instantánea | Excluido (Contrato congelado en `sapi-ranking-v0`). | No implementado en backend. | Agregar objeto `meteo_actual` (T, HR, Viento) en el DTO de Spring Boot. |
| **FUT-02** | Filtrado Espacial por Comuna en Backend v2 | Excluido (La grilla v2 evalúa siempre las 50 celdas del corredor). | Solo disponible en vista demo legacy. | Exponer parámetro opcional `GET /api/v1/ranking?comuna=Valparaiso` en el backend. |
| **FUT-03** | Autenticación y Perfiles de Usuario (RBAC) | Excluido (\$0 CLP / Demostración local loopback). | Sin autenticación perimetral. | Implementar Spring Security con JWT / Keycloak para perfiles Comandante vs. Analista. |

---

### Categoría 4: Limitaciones Científicas Estrictas (No Negociables)

| ID | Restricción Científica | Impacto Operativo | Por qué no se puede violar |
| :--- | :--- | :--- | :--- |
| **SCI-01** | **`scientific_model_validation = false`** | **CRÍTICO** | La compuerta F4 permanece en estado **FAIL**. El modelo no cuenta con validación epidemiológica de incendios en tiempo real frente a temporadas completas. | Declarar el modelo como "validado" incurriría en negligencia técnica y falta de ética académica. |
| **SCI-02** | **Ranking Relativo vs. Probabilidad Calibrada** | **CRÍTICO** | Los scores de `0.102` a `0.147` representan una ordenación matemática relativa entre celdas, NO un "14.7% de probabilidad estadística de ignición". | Sin calibración de Platt o regresión isotónica, transformar scores en porcentajes inventaría una falsa precisión peligrosa para los brigadistas. |
| **SCI-03** | **Uso de Datos Históricos Congelados (2026-09-01)** | **MEDIO** | El stack corre en modo reproducibilidad ADR-009 sobre un dataset congelado; no refleja el clima ni los focos de hoy en la mañana. | Garantizar que las pruebas, los contrastes y las evaluaciones sean 100% reproducibles e idénticas en cada ejecución. |
| **SCI-04** | **Prohibición de Emisión de Alertas Oficiales** | **CRÍTICO** | S.A.P.I. es un prototipo académico de ingeniería de software y apoyo a la toma de decisiones, no un canal oficial de emergencia. | Las únicas entidades legalmente facultadas para declarar alertas de incendio en Chile son CONAF y SENAPRED. |

---

## 4. Guía de Respuesta ante Preguntas Incómodas de la Comisión

### Pregunta: *"¿Por qué faltan datos del clima en las tarjetas superiores?"*
> **Respuesta:**  
> *"No es un defecto, es una decisión deliberada de arquitectura. En el Sprint 2 congelamos el contrato REST v0 para asegurar la persistencia y ordenación estricta de las 50 celdas en PostGIS. Las variables meteorológicas sí son consumidas internamente por el microservicio de inferencia en Python, pero no están expuestas como campos del DTO de respuesta v0. Nos negamos a inventar datos simulados para rellenar la pantalla: preferimos la transparencia técnica. Su inclusión como campo aditivo ya está documentada para el contrato v1."*

### Pregunta: *"¿Por qué hay 7 celdas empatadas en el primer lugar con el mismo score?"*
> **Respuesta:**  
> *"Porque el Modelo D, al evaluar las condiciones de entrada de esas 7 celdas (cercanas geográficamente y con variables meteorológicas homogéneas), arrojó idéntico valor de salida (0.131293). En lugar de aplicar un desempate arbitrario que falsee la realidad matemática, el sistema respeta el empate real: las 7 comparten la prioridad #1. Esto demuestra la fidelidad de nuestro pipeline de datos frente a interfaces cosméticas que enmascaran los empates."*

### Pregunta: *"¿Se puede usar este sistema mañana en una central de bomberos?"*
> **Respuesta:**  
> *"Como plataforma de software sí: la arquitectura Docker, el backend en Spring Boot, el microservicio FastAPI y la base PostGIS son estables, reproducibles y robustos. Sin embargo, **científicamente no**: el Modelo D no cuenta con validación operacional de campo (F4 FAIL) y produce rankings relativos, no probabilidades calibradas. El rol de un ingeniero de software también es saber cuándo poner un límite ético a la aplicación de su tecnología."*

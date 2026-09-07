# Acta de pruebas de aceptación con usuario — Sprint 1 / Hito 1

**Proyecto:** S.A.P.I. — Sistema de Alerta de Predicción de Incendios
**Fecha de la sesión:** 01-09-2026
**Responsable:** Daniel Cortez Fierro

## 1. Antecedente — observación de Matías (semestre anterior)

El profesor Matías, en una corrección verbal sobre el prototipo de S.A.P.I.
de un semestre anterior, señaló que el dashboard podría funcionar mejor en
vista móvil que en la disposición actual pensada para escritorio. Esta
observación es el punto de partida de la sesión de esta semana: en vez de
una demo genérica, se diseñó específicamente para responder a este punto.

## 2. Prueba de aceptación — vista móvil

| Campo | Contenido |
|-------|-----------|
| **Participante** | Daniel Cortez Fierro (desarrollador) — **auto-evaluación**, no usuario externo |
| **Nota sobre el tipo de prueba** | Esta sesión es una verificación funcional del propio desarrollador, no una prueba de aceptación con usuario externo neutral. No hubo ningún "Analista de Protección Civil" ni evaluador externo — se documenta así explícitamente para no sobrerrepresentar el alcance de la prueba. |
| **Dispositivo** | Smartphone (Android/iOS), navegador móvil estándar |
| **Versión probada** | Commit correspondiente al tag `v1.0.0-sprint1-verified`, confirmado por la presencia del badge "🟡 Modo Demo" en el sidebar (existe desde SAPI-44) |
| **Escenario mostrado** | Escenario sembrado (`demo_seed`, VP-049, 2025-02-15) — se aclaró que es demostración, no predicción en tiempo real |

### Hallazgo

**Confirmado: el dashboard no fue pensado para móvil.** Varias partes del
dashboard —no solo el mapa Folium— se cortan o quedan fuera de pantalla en
navegador móvil. El problema aparece distribuido en el layout, consistente
con un diseño pensado originalmente para escritorio (ancho fijo, columnas
laterales) sin adaptación responsiva.

Esto **confirma directamente** la observación de Matías del semestre
anterior: sigue siendo válida hoy sobre el prototipo actual.

### Criterio de aceptación

**No cumplido para uso móvil sin fricción.** El dashboard es funcional en
escritorio (entorno objetivo declarado en `docs/alcance-prototipo.md`),
pero presenta desbordamiento de layout en móvil. Se documenta como
**hallazgo de usabilidad confirmado, no bloqueante del Hito 1** — el
alcance del prototipo nunca prometió paridad móvil completa, pero la
observación de Matías queda formalmente investigada y verificada, no
ignorada.

**Recomendación para Sprint 2:** evaluar layout responsivo (CSS adaptativo
o `st.columns` con proporciones dependientes de viewport) o una vista móvil
simplificada.

## 3. Cierre del hallazgo móvil (post–Hito 1)

| Campo | Contenido |
|-------|-----------|
| **Fecha de cierre** | 05-09-2026 |
| **Versión verificada** | Tip de `main` posterior a `v1.1.0-corredor-verified` (rediseño mobile-first en `app/`) |
| **Evidencia automatizada** | Suite local: tests de componentes (`tests/test_app.py`), theme/touch targets (`tests/test_theme.py`, `tests/test_risk_colors.py`) y arquitectura (`tests/test_architecture.py`) en verde |
| **Evidencia manual** | Vista local Streamlit (`http://localhost:8501`): pestañas Mapa/Detalle a ancho completo; lista de tarjetas en Detalle (sin tabla de 8 columnas); botones con `min-height` ≥ 44 px |

### Cambios que cierran la causa

- Layout 48/52 reemplazado por `st.tabs` (Mapa / Detalle).
- Tabla de 8 columnas reemplazada por tarjetas (`st.container(border=True)` + botón por celda).
- Eliminado `inject_table_checkbox_colors()` (MutationObserver sobre el DOM de Streamlit).
- Métricas de cabecera reducidas a dos columnas + caption de distribución.
- Tipografía y touch targets centralizados en `app/theme/tokens.py`.

### Criterio de aceptación (actualizado)

**Cumplido para el alcance del prototipo demo.** El hallazgo de la §2 queda
**cerrado** respecto a la causa de layout (columnas + tabla ancha). Queda
como mejora continua cualquier ajuste fino de densidad de las 50 tarjetas en
teléfonos muy angostos — no reabre el desbordamiento estructural original.

# Acta de Pruebas de Aceptación con Usuario (UAT)
**Proyecto:** S.A.P.I. — Sistema de Alerta y Predicción de Incendios Forestales
**Sprint:** Sprint 1 (Cierre — Semana 5)
**Fecha:** 31-08-2026
**Participantes:** Daniel Cortez (Desarrollador) / Analista de Protección Civil (Usuario Evaluador)

---

## 1. Criterios de Aceptación Evaluados

| ID | Requerimiento / HU | Criterio de Aceptación | Resultado | Observaciones |
| :---: | :--- | :--- | :---: | :--- |
| **CA-01** | HU-01 (NASA FIRMS) | Ingesta y georreferenciación de focos térmicos sobre la Región de Valparaíso. | **Aprobado** | Datos satelitales procesados correctamente en grilla regular. |
| **CA-02** | HU-02 (DMC Meteo) | Ingesta de variables climáticas horarias (Temperatura, Humedad, Viento). | **Aprobado** | Integración exitosa con telemetría de estaciones meteorológicas. |
| **CA-03** | HU-03 (PostGIS) | Persistencia y consultas espaciales en celdas de 1 km² con índices GiST. | **Aprobado** | Tiempos de respuesta y joins espaciales óptimos. |
| **CA-04** | HU-08 (Dashboard UI) | Visualización interactiva web con mapa semafórico de riesgo. | **Aprobado con Observación** | Operativo en navegadores de escritorio. |

---

## 2. Hallazgos y Deuda Técnica Detectada
* **Hallazgo Crítico de Usabilidad Móvil:** La interfaz web desarrollada en Streamlit presenta degradación de navegación y desajuste de controles táctiles al ser consultada desde dispositivos móviles/smartphones en terreno.
* **Acción Correctiva:** Se registra la adaptación *responsive* móvil y la exposición de una API REST liviana como requerimiento priorizado para la siguiente iteración del proyecto (Sprint 2).

---

## 3. Dictamen Final
* **Estado:** **Aprobado para Cierre de Hito 1**
* **Firma Evaluador:** Analista de Protección Civil / Gestión del Riesgo

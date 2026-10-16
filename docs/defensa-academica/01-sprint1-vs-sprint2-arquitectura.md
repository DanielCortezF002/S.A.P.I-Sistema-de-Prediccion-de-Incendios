# S.A.P.I. — Comparativa de Arquitectura: Sprint 1 vs. Sprint 2

**Documento de Preparación para Defensa de Título**  
**Proyecto:** Sistema de Alerta y Priorización de Riesgo de Incendios Forestales (S.A.P.I.)  
**Autor:** Equipo de Desarrollo / Estudiante de Ingeniería Civil en Informática  
**Fecha:** Octubre 2026  
**Rama:** `feat/ui-academic-defense-hardening`  

---

## 1. Resumen Ejecutivo de la Evolución

El proyecto S.A.P.I. nació con el objetivo de priorizar territorialmente zonas de riesgo de incendios en el corredor de Valparaíso (50 celdas normalizadas). Entre el Sprint 1 (Hito 1) y el Sprint 2 (Hito 2), el sistema experimentó una transición arquitectónica fundamental: de un prototipo monolítico acoplado a una arquitectura orientada a servicios (SOA/Microservicios) contenerizada y desacoplada.

```
┌────────────────────────────────────────────────────────────────────────┐
│ SPRINT 1: Monolito Acoplado en Proceso                                │
│                                                                        │
│   Streamlit Dashboard ───(In-Process Python Call)───> Modelo D / Files │
│            │                                                           │
│            └──────────────(SQL Directo)─────────────> DB Legacy        │
└────────────────────────────────────────────────────────────────────────┘

                                    ▼

┌────────────────────────────────────────────────────────────────────────┐
│ SPRINT 2: Arquitectura Empresarial por Capas (Objetivo)                │
│                                                                        │
│   Streamlit Web (web-v2)                                               │
│            │ (HTTP GET /api/v1/ranking)                                │
│            ▼                                                           │
│   Spring Boot REST API (backend)                                       │
│      ├── Flyway Migrations (db/migration)                              │
│      ├── Cache & Idempotencia de Evaluación                            │
│      │                                                                 │
│      ├──(HTTP POST /infer)───────────> FastAPI Microservice (ml-api)  │
│      │                                    └── Modelo D (Frozen Artefact)│
│      │                                                                 │
│      └──(JDBC / PostGIS)─────────────> PostgreSQL 15 + PostGIS 3.4     │
│                                           └── Tabla corridas y ranking │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Cuadro Comparativo Detallado

| Dimensión | Sprint 1 (Hito 1) | Sprint 2 (Hito 2 - Actual) | Razón Técnica del Cambio |
| :--- | :--- | :--- | :--- |
| **Patrón Arquitectónico** | Monolito interactivo de inferencia local. | Microservicios distribuidos contenerizados. | Separación de responsabilidades (SoC), escalabilidad y gobernanza de datos. |
| **Inferencia del Modelo ML** | Directa en el runtime de Streamlit (`score_current_grid()` en proceso). | Microservicio Python/FastAPI (`ml-api`, Uvicorn) en red aislada. | Aislar dependencias pesadas de ML (GDAL, scikit-learn, C++ libs) del frontend. |
| **Capa de Negocio / Orquestación** | Lógica dispersa entre componentes de UI y módulos utilitarios. | API REST Spring Boot (Java 21) empresarial. | Centralizar contratos, validaciones de integridad, trazabilidad e idempotencia. |
| **Persistencia de Resultados** | Opcional, script de carga batch hacia base de datos unificada. | PostGIS 15-3.4 estructurado con Flyway migrations automáticas al boot. | Trazabilidad histórica auditable de cada corrida y ranking generado. |
| **Contrato de Integración** | Interfaces Python internas (`tuple`, `dict`, `GeoDataFrame`). | Contrato REST JSON formal (`GET /api/v1/ranking`, schema versionado). | Interoperabilidad estandarizada, desacoplamiento de plataforma y lenguaje. |
| **Aislamiento de Red** | Red Docker bridge simple (`sapi-net`), puertos expuestos directamente. | Red interna privada `sapi-v2-net` con publicación loopback exclusiva (`127.0.0.1`). | Principio de mínimo privilegio y seguridad perimetral de servicios. |
| **Gestión de Configuración** | Archivos `.env` leídos arbitrariamente por múltiples servicios. | Inyección estricta de variables de entorno por Docker Compose (sin secretos hardcodeados). | Higiene operativa de 12-Factor App y protección de credenciales. |
| **Validación de Integridad** | Heurística local de frescura sin sellos criptográficos. | Huella digital de inputs (`inputs_fingerprint`), semántica estricta `relative_rank`. | Reproducibilidad científica verificable ante auditorías técnicas. |

---

## 3. ¿Por qué se cambió la Arquitectura? (Justificación Técnica)

Ante la comisión evaluadora, la justificación de este cambio debe articularse en 4 pilares:

### A. Desacoplamiento de Ciclos de Vida y Dependencias
En Sprint 1, Streamlit compartía el mismo entorno de ejecución Python que `scikit-learn`, `GDAL` y `geopandas`. Cualquier actualización de la interfaz de usuario ponía en riesgo el entorno del modelo matemático. En Sprint 2, la inferencia corre en un microservicio autónomo con dependencias congeladas (`Dockerfile.ml-api`), mientras que la interfaz sólo consume un cliente HTTP liviano (`Dockerfile.web`).

### B. Robustez Empresarial y Gobernanza con Spring Boot
Streamlit es una excelente herramienta de prototipado rápido, pero no está diseñada para actuar como API Gateway corporativo, ni para gestionar transacciones ACID, migraciones controladas de esquemas relacionales, ni pools de conexiones concurrentes. La incorporación de Spring Boot 3 con Java 21 proporciona un núcleo transaccional robusto, respaldado por Flyway para versionamiento de la base de datos y validaciones estrictas de contratos.

### C. Persistencia Espacial y Auditoría en PostGIS
En emergencias ambientales, no basta con mostrar una visualización efímera; se requiere un registro histórico inmutable de qué se predijo, cuándo se predijo, con qué datos de entrada y qué brigadas o recursos se priorizaron. La persistencia en PostgreSQL con extensión PostGIS asegura que cada ejecución queda registrada con geometrías vectoriales estándar y metadatos de trazabilidad.

### D. Idempotencia y Consistencia de Decisiones
Si dos analistas u operadores consultan el ranking para una misma ventana de pronóstico (`forecast_time`), el sistema debe entregar exactamente los mismos resultados sin re-ejecutar inferencias redundantes ni provocar condiciones de carrera. El backend en Spring Boot implementa esta garantía de idempotencia.

---

## 4. Cómo Demostrarlo en Vivo a la Comisión (Evidencia Práctica)

Durante la defensa, la demostración de la arquitectura no debe ser teórica; se prueba en terminal y navegador con estos pasos reproducibles:

### Paso 1: Mostrar los Contenedores Activos y sus Roles
Ejecutar en la terminal del IDE:
```powershell
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```
**Qué explicar:**  
"Como observan, el sistema opera con 4 servicios independientes: `db-v2` (PostGIS), `ml-api` (FastAPI en Python), `backend` (Spring Boot en Java 21) y `web-v2` (Streamlit). Todos los puertos están publicados exclusivamente en `127.0.0.1` respetando el principio de mínimo privilegio."

### Paso 2: Demostrar que el Frontend es un Consumidor REST Puro
Mostrar en el navegador la pantalla principal de S.A.P.I. (`http://127.0.0.1:18504`), abrir el panel inferior *"Información técnica y fuentes"* y destacar:
- **Origen:** Backend Spring Boot (`GET /api/v1/ranking`).
- **Esquema:** `sapi-ranking-v0` con `score_semantics: relative_rank`.
- **Inputs fingerprint:** Identificador único de las características de entrada.
- **Sin inferencia local:** El contenedor web no tiene acceso a los pesos del modelo ni ejecuta scoring en proceso.

### Paso 3: Demostrar la Inferencia en Microservicio y Persistencia en PostGIS
Consultar directamente el endpoint REST del backend:
```powershell
curl -s http://127.0.0.1:18092/api/v1/ranking | jq '{schema: .schema_version, model: .model_version, cells_count: (.cells | length), top_score: .cells[0].score}'
```
**Qué explicar:**  
"El backend Spring Boot consulta al microservicio de Machine Learning, recibe el vector de inferencia para las 50 celdas territoriales, persiste la corrida en PostGIS y devuelve el DTO validado al dashboard. La consulta es reproducible e idempotente."

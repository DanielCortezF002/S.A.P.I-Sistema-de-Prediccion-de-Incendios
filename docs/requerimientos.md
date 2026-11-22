# S.A.P.I. — Requerimientos, alcance del MPV y escenarios de calidad (Hito 3)

Artefacto A2 de la rúbrica del Hito 3 (profesor Matías, 10-11-2026). Subtarea HU-92.T6 (SAPI-173). Versión 0.1 del 22-11-2026, **previa a toda medición del Sprint 3**.

> **Origen de los IDs.** RF-01..RF-05 y RNF-01..RNF-06 son el catálogo del Informe del Hito 2 (§6.5, Tablas 15 y 16). Los IDs marcados **(propuesto)** los agrega este documento para HU del Sprint 3 que no tenían requerimiento en ese catálogo (HU-64, HU-65, HU-83 y otras). Son una propuesta de Gobernanza y requieren el visto bueno de Daniel. No reemplazan los IDs de Jira.

## 1. Catálogo

| ID | Tipo | Requerimiento | Prioridad | Objetivo | HU (Sprint) | Origen |
|---|---|---|---|---|---|---|
| RF-01 | Funcional | Consultar el ranking de 50 celdas con metadatos temporales | Must | OE1, OE3 | SAPI-55/57/61 (S2); HU-80, HU-86 (S3) | Hito 2, Tabla 15 |
| RF-02 | Funcional | Generar la inferencia mediante un servicio HTTP con contrato | Must | OE1 | SAPI-55/56/57 (S2) | Hito 2, Tabla 15 |
| RF-03 | Funcional | Persistir ejecuciones y resultados por celda | Must | OE2 | SAPI-58/59 (S2) | Hito 2, Tabla 15 |
| RF-04 | Funcional | Navegar el mapa y la tabla del ranking | Must | OE3 | SAPI-61/66 (S2); HU-80 (S3) | Hito 2, Tabla 15 |
| RF-05 | Funcional | Ejecutar y recuperar insumos versionados | Must | OE5 | SAPI-43/71 (S2) | Hito 2, Tabla 15 |
| RF-06 | Funcional (científico) | Evaluar el Modelo D con días reales con y sin incendio: matriz de confusión por zona (Top 5) y por día, más curva de entrenamiento | Must | OE5 | HU-83 (S3) | **(propuesto)** |
| RF-07 | Funcional (científico) | Entrenar una red con memoria temporal como experimento comparativo, sin reemplazar el Modelo D | Must en Jira; **bloqueado** | OE5 | HU-64 (S3) | **(propuesto)**; bloqueado hasta la respuesta escrita de César (SAPI-165) |
| RF-08 | Funcional (científico) | Comparar el Modelo D, el Modelo A y el modelo temporal con la incertidumbre declarada y un ADR | Must | OE5 | HU-65 (S3) | **(propuesto)**; la parte temporal está bloqueada (SAPI-165) |
| RF-09 | Funcional | Mostrar la predicción temporal rotulada «Experimental — no validado» | Could; **bloqueado** | OE3 | HU-93 (S3) | **(propuesto)**; bloqueado (SAPI-165) |
| RF-10 | Funcional | Sellar y verificar la trazabilidad científica de cada experimento | Should | OE5 | HU-76 (S3) | **(propuesto)** |
| RF-11 | Funcional | Explicar el Modelo D en lenguaje simple (qué ordena y qué no) | Must | OE3 | HU-88 (S3) | **(propuesto)** |
| RNF-01 | Fiabilidad (integridad/idempotencia) | Replay sin duplicados | Must | OE2 | SAPI-58/59 (S2) | Hito 2, Tabla 16 |
| RNF-02 | Compatibilidad (interoperabilidad) | Contratos OpenAPI v0 y errores tipados | Must | OE1 | SAPI-56/57 (S2); HU-91.T4 (S3) | Hito 2, Tabla 16 |
| RNF-03 | Eficiencia de desempeño | Latencia visible p95 por escenario | Must | OE4 | HU-90.T2 (S3) | Hito 2, Tabla 16; escenario en §3.2 |
| RNF-04 | Mantenibilidad | Separación de capas, linters y gate en verde en el SHA de entrega | Must | OE4 | HU-85 (S3) | Hito 2, Tabla 16 |
| RNF-05 | Capacidad de interacción (interpretabilidad) | El score se entiende como ranking relativo, no como probabilidad | Must | OE3 | HU-88, HU-91 (S3) | Hito 2, Tabla 16 |
| RNF-06 | Seguridad | Sin vulnerabilidades críticas abiertas sin justificar y sin secretos versionados | Must | Transversal | HU-89 (S3) | Hito 2, Tabla 16; escenario en §3.1 |
| RNF-07 | Fiabilidad (tolerancia a fallos) | Fallo rápido y controlado con la base de datos caída o el pool saturado | Must | OE4 | HU-75 (S3) | **(propuesto)**; escenario en §3.3 |
| RNF-08 | Portabilidad (instalabilidad) | El stack arranca con un solo comando desde un clon limpio | Must | OE4 | HU-90.T1 (S3) | **(propuesto)** |

HU-79 (validación con La Cruz) y HU-92 (trazabilidad) son transversales de proceso: no tienen un requerimiento de producto propio.

## 2. Alcance del MPV del Hito 3

| Elemento | Decisión | Justificación (fuente) |
|---|---|---|
| RF-01..RF-05, RNF-01..RNF-06 | Incluido | Ya forman el vertical slice del Hito 2 |
| RF-06, RF-10, RF-11, RNF-07, RNF-08 | Incluido | HU comprometidas en el Sprint 3 (Jira, sprint id 37) |
| RF-07, RF-09 y la parte temporal de RF-08 | **Condicionado** | Bloqueado hasta que César confirme por escrito (SAPI-165). Si la respuesta es negativa, pasan a Won't (SAPI-165) |
| Despliegue cloud (SAPI-68) | Excluido, versión futura | Presupuesto adicional de $0 CLP (SAPI-67, 16-10-2026) |
| Regla 30-30-30 (SAPI-82) | Excluido | Descartada en Jira (label y comentario de SAPI-82) |
| Módulo o interfaz ciudadana | Excluido | Propuesta del 16-11-2026 no aprobada |
| Estudio de mercado | Excluido (WON'T) | Revisión de César del Hito 2: «No aplica a un prototipo académico» |
| E3, Modelo D v2, reentrenamiento del D desplegado, rediseño general del frontend | Excluido del Sprint 3 | Tickets SAPI-75 y SAPI-76 («Fuera del Sprint 3 comprometido») |
| Completar el DEM de las 20 celdas (B-13) | Pendiente de decisión | SAPI-119: lo decide César |

## 3. Escenarios de calidad (ISO/IEC 25010)

Las medidas numéricas que todavía no están acordadas dicen **«meta pendiente de Daniel»**. No se miden antes de que estén selladas (HU-92.T6).

### 3.1. RNF-06 Seguridad (HU-89)

| Parte | Valor |
|---|---|
| Fuente | Un atacante o un error del equipo de desarrollo |
| Estímulo | Una dependencia con una vulnerabilidad conocida, o un secreto agregado al repositorio |
| Entorno | Pipeline de CI sobre una PR contra `main` |
| Respuesta | El escáner lo detecta, el reporte queda versionado y la PR se bloquea si hay un secreto |
| Medida de respuesta | 0 secretos detectados (SAPI-89 CA2). 0 hallazgos críticos abiertos sin justificación escrita (SAPI-89 CA1). Umbral para hallazgos altos: **meta pendiente de Daniel** |

### 3.2. RNF-03 Eficiencia (HU-90.T2)

| Parte | Valor |
|---|---|
| Fuente | El usuario del panel |
| Estímulo | Carga en frío y acción «actualizar» del ranking |
| Entorno | Stack local con Docker Compose, una única carga en la máquina |
| Respuesta | El panel muestra el ranking completo |
| Medida de respuesta | p95 por escenario, con n declarado: **meta pendiente de Daniel**. Línea base del Hito 2 en `docs/objetivos.md` (KPI-03) |

### 3.3. RNF-07 Fiabilidad (HU-75)

| Parte | Valor |
|---|---|
| Fuente | La base de datos PostgreSQL/PostGIS |
| Estímulo | Base caída (A1) o pool de conexiones saturado (P1b) |
| Entorno | Stack local con carga, una única carga en la máquina |
| Respuesta | El backend responde `500 internal_error` sin reiniciarse; con el pool saturado no aparecen errores atribuibles a PostgreSQL |
| Medida de respuesta | A1: 100 % `500 internal_error`, cada uno en menos de 10 s (SAPI-75 CA2). P1b/S1: M1 = 0 (SAPI-75 CA3/CA4). Margen de M2 frente a la base: **meta pendiente de Daniel**, que se fija en la preinscripción SAPI-128 |

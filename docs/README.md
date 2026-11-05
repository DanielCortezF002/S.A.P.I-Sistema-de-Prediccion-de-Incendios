# S.A.P.I. — Índice Maestro de Documentación

Bienvenido a la base de conocimiento y documentación técnica de **S.A.P.I. (Sistema de Alerta y Predicción de Incendios)**.
Este índice proporciona acceso navegable y estructurado a la totalidad de las especificaciones de arquitectura, decisiones de diseño, contratos de datos, guías operacionales y defensas académicas del proyecto.

---

## 🧭 Mapa Rápido de Navegación

| Área | Propósito Principal | Documento de Entrada |
|---|---|---|
| **Gobernanza del Repositorio** | Auditoría, mapa de código y propuestas de ordenamiento | [`docs/repository-governance/`](repository-governance/REPOSITORY_MAP.md) |
| **Arquitectura y Stack** | Congelamiento técnico de Sprint 2 y decisiones ADR | [`docs/architecture-stack-freeze-sprint2.md`](architecture-stack-freeze-sprint2.md) |
| **Modelo y Ciencia** | Ficha del Modelo D, invariantes y reproducibilidad | [`docs/model_card_baseline.md`](model_card_baseline.md) |
| **Entregables Hito 2** | Informe final, DoD y matrices de rúbricas UNAB | [`docs/hito2/`](hito2/INFORME_HITO2_FINAL.md) |
| **Defensa Académica** | Guiones de presentación, preguntas de comisión y riesgos | [`docs/defensa-academica/`](defensa-academica/01-sprint1-vs-sprint2-arquitectura.md) |
| **Operaciones y Tooling** | Manuales de contingencia, refresco FIRMS/DMC y n8n | [`docs/ops/`](ops/CONTROL-CENTER.md) |
| **Contratos e Interfaces** | Especificaciones OpenAPI de microservicios v2 | [`contracts/openapi/`](../contracts/openapi/README.md) |
| **Agentes e IA** | Contexto permanente, seguridad MCP y gobernanza de skills | [`docs/ai/`](ai/SAPI_CONTEXT.md) |

---

## 1. Gobernanza del Repositorio y Colaboración

Documentos formalizados bajo la **Directiva R1 (2026-10-18)** para garantizar la integridad, trazabilidad y seguridad del repositorio:

- **[Mapa del Repositorio](repository-governance/REPOSITORY_MAP.md):** Estructura jerárquica de directorios, clasificación de componentes por categoría (Core, Docs, Académico, Evidencia) y puntos de contacto.
- **[Auditoría Integral de Gobernanza](repository-governance/REPOSITORY_AUDIT_20261018.md):** Diagnóstico de estado Git, worktrees, revisión remota de GitHub CLI, análisis de PRs/Issues y resultados de pruebas.
- **[Propuesta de Limpieza Estructural](repository-governance/CLEANUP_PROPOSAL.md):** Plan no destructivo por fases para reorganización de activos, higiene de ramas remotas y reglas de protección en GitHub.
- **[Guía de Contribución](../CONTRIBUTING.md):** Estándares de desarrollo, flujo Git, mensajes de commit convencionales, invariantes científicos y protocolo de evidencia.

---

## 2. Arquitectura de Software y Decisiones Técnicas (ADR)

### 2.1. Arquitectura Base y Congelamiento
- **[Architecture & Stack Freeze — Sprint 2](architecture-stack-freeze-sprint2.md):** Documento normativo que congela el stack tecnológico (Streamlit, Spring Boot, FastAPI, PostgreSQL/PostGIS v2) y define el vertical slice.
- **[Erratum de Arquitectura](architecture-stack-freeze-sprint2-erratum.md):** Fe de erratas técnica sobre dimensiones y resoluciones espaciales.
- **[Arquitectura General SAPI](arquitectura.md):** Visión conceptual y desacoplamiento de componentes.
- **[Guía de Despliegue y Reproducibilidad](deploy.md):** Instrucciones de levantamiento en Docker Compose y validación bit a bit del Modelo D.
- **[Alcance del Prototipo](alcance-prototipo.md):** Definición territorial de la malla de 50 celdas en el corredor Viña del Mar – Quilpué.

### 2.2. Registros de Decisiones Arquitectónicas (ADRs)
Ubicados en [`docs/adr/`](adr/):
- [`ADR-001`](adr/ADR-001.md): Adopción de Spring Boot como backend de aplicación y orquestador REST.
- [`ADR-002`](adr/ADR-002.md): Adopción de FastAPI como microservicio de Machine Learning dedicado.
- [`ADR-003`](adr/ADR-003.md): PostgreSQL y PostGIS como persistencia geoespacial operacional v2.
- [`ADR-004`](adr/ADR-004.md): Docker Compose v2 como entorno reproducible unificado.
- [`ADR-005`](adr/ADR-005.md): Especificación REST con OpenAPI v0 como contratos entre servicios.
- [`ADR-006`](adr/ADR-006.md): Modelo D como baseline congelado y modelos secuenciales como experimentos.
- [`ADR-007`](adr/ADR-007.md): Tokens centralizados de diseño y paleta accesible (WCAG 2.1 AA).
- [`ADR-008`](adr/ADR-008.md): Punteros atómicos y almacenamiento inmutable para refresco de datos satelitales.
- [`ADR-009`](adr/ADR-009.md): Modo reproducible por defecto para evaluaciones académicas y demostraciones.
- [`ADR-010`](adr/ADR-010.md): Desacoplamiento seguro de automatizaciones y puente n8n.
- [`ADR-011`](adr/ADR-011-cloud-provider.md): Evaluación comparativa y propuesta de proveedor cloud (AWS / GCP / Azure).

---

## 3. Integridad Científica y Machine Learning

- **[Model Card — Modelo D Baseline](model_card_baseline.md):** Ficha técnica formal del clasificador `HistGradientBoostingClassifier`, validación temporal walk-forward causal y métricas de ranking.
- **[Directiva Permanente para Agentes (`AGENTS.md`)](../AGENTS.md):** Invariantes no negociables: score como ranking relativo exploratorio, `scientific_model_validation = false`, F4 FAIL y no fabricación de datos.
- **[Spike SAPI-49 — Datos Históricos CONAF](spikes/SAPI-49-CONAF-historical-source.md):** Análisis de viabilidad y limitaciones de integración del catálogo de incendios CONAF.
- **[Estudio de Viabilidad LSTM SAPI-63](../reports/sapi63_lstm_viability_report.json):** Demostración empírica de la inviabilidad de modelos secuenciales profundos bajo el volumen actual de eventos positivos.

---

## 4. Entregables Académicos y Defensa (Hito 2 — UNAB)

### 4.1. Cierre de Hito 2
Ubicados en [`docs/hito2/`](hito2/):
- **[Informe Académico Final Hito 2](hito2/INFORME_HITO2_FINAL.md):** Documento principal de cierre de Sprint 2.
- **[Matriz de Rúbrica — Profesor César](hito2/MATRIZ_RUBRICA_CESAR_FINAL.md):** Verificación de cumplimiento criterio por criterio.
- **[Matriz de Rúbrica — Profesor Matías](hito2/MATRIZ_RUBRICA_MATIAS_FINAL.md):** Evaluación de estándares de arquitectura e integración.
- **[Trazabilidad HU / CA / Evidencias](hito2/TRAZABILIDAD_HU_CA_EVIDENCIAS.md):** Mapeo entre historias Jira y pruebas automatizadas.
- **[Checklist de Entrega](hito2/CHECKLIST_ENTREGA_HITO2.md):** Verificación previa a la entrega final.
- **[Definition of Done](hito2/definition-of-done.md):** Criterios rigurosos de aceptación para declarar un componente terminado.

### 4.2. Preparación para Examen y Defensa Técnica
Ubicados en [`docs/defensa-academica/`](defensa-academica/):
- **[01. Comparativa de Arquitectura Sprint 1 vs Sprint 2](defensa-academica/01-sprint1-vs-sprint2-arquitectura.md):** Evolución desde el monolito hacia la arquitectura de microservicios v2.
- **[02. Guion de Demostración de 5 Minutos](defensa-academica/02-guion-demostracion-5-minutos.md):** Protocolo paso a paso para la demo en vivo ante la comisión evaluadora.
- **[03. Banco de Preguntas y Respuestas de la Comisión](defensa-academica/03-preguntas-defensa-tecnica.md):** Respuestas técnicas a posibles cuestionamientos de la comisión examinadora.
- **[04. Matriz de Riesgos y Deuda Técnica](defensa-academica/04-matriz-riesgos-y-deuda-tecnica.md):** Análisis de riesgos operacionales y mitigaciones.

---

## 5. Operaciones, Resiliencia y Tooling

Ubicados en [`docs/ops/`](ops/):
- **[Centro de Control Operacional](ops/CONTROL-CENTER.md):** Documentación del panel de telemetría y estado de servicios.
- **[Primer Refresco Controlado](ops/FIRST-CONTROLLED-REFRESH.md):** Procedimiento paso a paso para actualización de datos FIRMS/DMC.
- **[Operador Attempt 2](ops/ATTEMPT2-OPERATOR.md):** Flujo de contingencia y resiliencia en pruebas automatizadas.
- **[Payload de Alertas](ops/ALERT-PAYLOAD.md):** Estructura del contrato JSON de notificación generado por el sistema.
- **[Sondeo DMC en Vivo](ops/DMC-LIVE-CONTRACT-PROBE.md):** Verificación de la API de la Dirección Meteorológica de Chile.
- **[Diagnóstico y Remediación de Esquema FIRMS](ops/FIRMS-LIVE-SCHEMA-FAILURE-2026-09-24.md):** Lecciones aprendidas y control de cambios en la ingesta satelital.

---

## 6. Asistencia de Inteligencia Artificial y Gobernanza

Ubicados en [`docs/ai/`](ai/):
- **[Contexto de Dominio S.A.P.I.](ai/SAPI_CONTEXT.md):** Contexto unificado de alto nivel para agentes Claude Code, Antigravity y Codex.
- **[Seguridad y Gobernanza MCP](ai/MCP_SECURITY_AND_SETUP.md):** Políticas de menor privilegio para servidores MCP (PostGIS en solo lectura SELECT, GitHub sin escrituras directas).
- **[Guía de Integración Claude Desktop](ai/CLAUDE_DESKTOP_GUIDE.md):** Configuración de asistentes locales de escritorio.
- **[Matriz de Rúbricas y Gates](ai/RUBRIC_MATRIX.md):** Reglas automatizables de auditoría técnica.
- **[Quality Gate de Cierre de Sprint 2](ai/SPRINT2_CLOSURE_GATE.md):** Protocolo de verificación G0-G7.

---

## 7. Archivo Histórico de Hito 1

Documentos fundacionales correspondientes al cierre del primer hito del proyecto (conservados para trazabilidad histórica inmutable):
- [`docs/informe-hito1-final.md`](informe-hito1-final.md)
- [`docs/informe-1-seminario-licenciatura.md`](informe-1-seminario-licenciatura.md)
- [`docs/presentacion-hito1.md`](presentacion-hito1.md)
- [`docs/cierre-sprint1-hito1.md`](cierre-sprint1-hito1.md)
- [`docs/architecture-4plus1-hito1.md`](architecture-4plus1-hito1.md)
- [`docs/atributos-calidad-hito1.md`](atributos-calidad-hito1.md)
- [`docs/testing-evidencia-hito1.md`](testing-evidencia-hito1.md)
- [`docs/trazabilidad-hito1.md`](trazabilidad-hito1.md)

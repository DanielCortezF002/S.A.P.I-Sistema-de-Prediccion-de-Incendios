---
name: sapi-roadmap-strategy
description: "Planificar futuro técnico-científico de S.A.P.I. tras Hito 2: validación del Modelo D, datos CONAF, experimentos LSTM, despliegue cloud y mejoras de n8n."
---

# S.A.P.I. / Roadmap y priorización
Leer `docs/ai/ROADMAP_FUTURE.md`. Revalidar backlog y restricciones de cuotas académicas/tiempo, deuda técnica y aprobación docente.
Priorizar por: riesgo científico, valor docente/usuario, dependencias, costo técnico, evidencia y fechas.
Primer frente: validación externa del modelo (labels reales, split temporal/espacial, métricas sin leakage) y acuerdos expertos; F4 permanece FAIL.
Segundo: dataset temporal causal y benchmark LSTM SAPI-64/65 contra Modelo D, sin sustituir baseline por moda.
Tercero: ADR cloud SAPI-67 y deployment SAPI-68 solo con seguridad, observabilidad, protección de datos y costos.
Cuarto: n8n seguro y explicabilidad/UX; no alertas operacionales ni integración institucional no aprobada.
Planificar entregables, CA, pruebas, recursos y decision gate por sprint; no presentar plan como trabajo ejecutado.

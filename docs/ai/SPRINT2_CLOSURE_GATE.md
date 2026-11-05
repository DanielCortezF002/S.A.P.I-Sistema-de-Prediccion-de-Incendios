# Gate académico de cierre de Sprint 2 / Hito 2

La **fecha y estado de Sprint 2 en Jira** se distinguen del cierre académico del **Hito 2**. Consultar en vivo los sprints, issues comprometidas, resolución y la rúbrica **antes** de marcar gates como PASS.

| Gate | Entregable verificable | Estado inicial | Dueño/decisión |
|---|---|---|---|
| G0 | Referencia de sprint closed, issues reales, SP totales, alcance originalmente comprometido y cambios formalizados | Sprint closed (verificado 17-10), resto REVALIDAR | Agente consulta, humano aprueba narrativa |
| G1 | Baseline release SHA de main, PR #30 estado, diff, checks remotos, suites locales con alcance correcto | PR #30 abierto; autorización merge NO dada | Humano autoriza merge |
| G2 | Demo vertical slice con 50 celdas, arquitectura, persistencia, trazabilidad datos, documentación de fallos/rollback | Evaluar evidencias reales | QA |
| G3 | Matriz CA/HU→Jira→PR/commit→test→captura (incluyendo F4 FAIL y DEM N/D) | INCOMPLETO hasta auditar | QA |
| G4 | Matriz completa de **dos** rúbricas; identificar item Excelente/penalización/fuente, dudas al docente | PENDIENTE | Académico |
| G5 | Informe(s), formato/portada real, bibliografía, gráficos, resultados y limitaciones fieles | PENDIENTE verificar entregas | Académico |
| G6 | Demo guiada, presentación, simulacro defensa, contingencia Docker y demo offline | PENDIENTE | Presentador |
| G7 | Retro Sprint 2, riesgos abiertos, ADRs, backlog próximo sprint y traspaso | PENDIENTE | Product Owner |

## Orden de trabajo con prioridad
1. NO lanzar refactors ni experimentos nuevos antes de consolidar la entrega académica.
2. Extraer evidencias ya disponibles; detectar faltantes reales, no generar capturas ficticias ni repetir auditorías por cuota.
3. Validar contra ambas rúbricas y solicitar respuesta de César sobre evidencia científica exigida (no inventar criterio).
4. Documento de cierre: qué se completó, qué se diferió de forma explícita, qué está abierto y justificación. Nunca decir 100% de alcance si backlog incompleto.
5. Revisión final humana; solamente después publicar documentos o cerrar tareas adicionales.

## Formato de reporte de salida
`Fecha / Baseline Git main / PRs abiertos / estado del sprint y fuente / matriz de rúbricas / pruebas reproducibles / brechas exactas / riesgos F4+DEM / top 3 acciones / decisiones humanas / veredicto GO|NO-GO`.

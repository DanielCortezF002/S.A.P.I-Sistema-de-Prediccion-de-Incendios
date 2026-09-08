const { annexTitle, sourceNote, body, bullet, heading2, table } = require("./generate_docx.js");

const W = (...cm) => cm.map((c) => Math.round(c * 566.929));

function annexes() {
  const out = [];

  // ---------------- Anexo A ----------------
  out.push(annexTitle("A", "Arquitectura"));
  out.push(sourceNote("Fuente: docs/arquitectura-hito1.md (congelado). Resumen de la tabla de componentes."));
  out.push(table(
    ["Componente", "Implementación real"],
    [
      ["Ingesta FIRMS", "src/ingesta/nasa_firms_backfill.py"],
      ["Ingesta DMC", "scripts/backfill_dmc_historico.py"],
      ["Ingesta DEM", "src/ingesta/dem_ingester.py"],
      ["Meteorología regional", "src/procesamiento/regional_meteo.py → load_regional_meteo_series()"],
      ["Clustering de episodios", "src/procesamiento/episodes.py → assign_episodes() (2 km / 6 h)"],
      ["Topografía por celda", "src/procesamiento/dem_features.py → load_grid_topography()"],
      ["Features temporales", "src/procesamiento/temporal_features.py (lags <= T)"],
      ["Definición del target", "src/procesamiento/target_builder.py → build_targets()"],
      ["Validación de causalidad", "src/procesamiento/causality_validator.py"],
      ["Constructor del dataset", "scripts/build_temporal_dataset.py"],
      ["Experimento A/B/C/D", "scripts/experiment_abcd.py"],
      ["Entrenamiento del artefacto", "scripts/build_prototype_model.py"],
      ["Grilla espacial", "src/geo/grid.py → all_cells()"],
      ["Servicio de inferencia", "src/inference/prototype_service.py → score_current_grid()"],
      ["Dashboard (modo Prototipo)", "app/components/prototype_view.py"],
      ["Selector de modo", "app/app.py → _resolve_dashboard_mode()"],
    ],
    W(6.5, 8.5)
  ));
  out.push(heading2("Límites arquitectónicos declarados"));
  [
    "Una sola estación meteorológica (DMC 330007, Rodelillo) — meteorología siempre regional.",
    "Los datos mostrados pueden ser históricos/desactualizados (banner de frescura explícito).",
    "Prototipo local, ejecutado on-demand, sin SLA.",
    "No existe un pipeline diario automatizado para el flujo temporal nuevo.",
    "Integración con CONAF pendiente.",
    "PostGIS no es parte de la ruta operacional del prototipo (solo del pipeline legacy).",
    "El score no es una probabilidad calibrada de incendio.",
    "La evidencia experimental es limitada y exploratoria.",
  ].forEach((t) => out.push(bullet(t)));

  // ---------------- Anexo B ----------------
  out.push(annexTitle("B", "Trazabilidad"));
  out.push(sourceNote("Fuente: docs/trazabilidad-hito1.md (congelado). Estado Jira actual, export externo `Jira (4).doc`, estado disponible al 07-09-2026."));
  out.push(table(
    ["ID", "Resumen", "SP", "Estado Jira actual", "Estado técnico"],
    [
      ["SAPI-26", "Histórico NASA FIRMS", "8", "En curso", "Cerrado lado NASA; CONAF pendiente"],
      ["SAPI-28", "Telemetría DMC↔ignición", "8", "Finalizado (07-09-2026)", "Parcial (join real feb-2025)"],
      ["SAPI-30", "Topografía DEM", "5", "Finalizado (07-09-2026)", "Avanzado, integrado al prototipo"],
      ["SAPI-32", "Limpieza/integración", "5", "Por hacer", "Sub-tarea limpieza cerrada; integración pendiente"],
      ["SAPI-33", "Gestión/documentación", "—", "Finalizado", "Manual, sin evidencia de código"],
      ["SAPI-44", "Separación demo/real", "2", "Finalizado", "Cerrado, 13/13 tests"],
      ["SAPI-45", "Gate cobertura ≥80%", "3", "Finalizado", "Cerrado, 80.34%→91.72%"],
      ["SAPI-46", "Gestión/documentación", "—", "Finalizado", "Manual, sin evidencia de código"],
      ["SAPI-47", "Matriz de riesgo", "1", "Finalizado", "docs/matriz-riesgo.md real"],
      ["SAPI-48", "Trazabilidad HU↔prueba", "2", "Finalizado", "docs/matriz-trazabilidad-hu-test.md"],
    ],
    W(2.1, 4.4, 1.0, 3.5, 4.5)
  ));
  out.push(heading2("Requerimientos del pipeline temporal sin HU Jira (PENDIENTE DE VINCULAR)"));
  out.push(table(
    ["REQ", "Descripción", "Criterio técnico (AC-T)", "Resultado"],
    [
      ["REQ-10", "DMC regional, nunca por celda", "AC-T02", "PASS"],
      ["REQ-11", "Causalidad estricta (<= T)", "AC-T03", "PASS"],
      ["REQ-12", "Target honesto (T,T+6h], cooldown", "AC-T04", "PASS"],
      ["REQ-13", "Aislamiento legacy/demo", "AC-T01 / AC-T10", "PASS"],
      ["REQ-14", "Ranking relativo por celda", "AC-T05 / AC-T06 / AC-T07", "PASS"],
      ["REQ-15", "DEM N/D, nunca 0", "AC-T08", "PASS (datos) / parcial (UI)"],
      ["REQ-16", "App carga sin excepción", "AC-T09", "PASS"],
    ],
    W(1.8, 5.2, 4.5, 4)
  ));

  // ---------------- Anexo C ----------------
  out.push(annexTitle("C", "Evidencia de testing"));
  out.push(sourceNote("Fuente: docs/testing-evidencia-hito1.md y artifacts/hito1/testing/ (congelados)."));
  out.push(body("Ejecución fresca (07-09-2026): 470 collected, 470 passed, 0 failed, 0 skipped, duración 297,97 s. Cobertura app+src: 91,72% (gate 80% configurado en pytest.ini, superado). Smoke Streamlit dedicado: 5 passed."));
  out.push(heading2("Categorías del inventario de pruebas (58 archivos en tests/)"));
  out.push(table(
    ["Categoría", "Ejemplos de archivo"],
    [
      ["Causalidad / anti-leakage", "test_causality_validator.py, test_temporal_features.py, test_target_builder.py"],
      ["Integridad de datos", "test_nan_journey_real_data.py, test_pipeline_validators.py"],
      ["Integración", "test_backfill_dmc_historico.py, test_dem_features.py, test_temporal_dataset_integration.py"],
      ["Contratos / regresión", "test_architecture.py, test_experiment_abcd_contract.py, test_grid_consistency.py"],
      ["Prototipo / inferencia", "test_prototype_service.py, test_prototype_freshness.py"],
      ["UI / Streamlit", "test_app.py, test_app_integration.py, test_theme.py"],
      ["Modelo ML (legacy)", "test_baseline.py, test_optimizer.py, test_serialization.py"],
    ],
    W(4.5, 10.5)
  ));
  out.push(heading2("Criterios técnicos de verificación del cierre (AC-T01..AC-T10, 07-09-2026)"));
  out.push(table(
    ["ID", "Criterio", "Resultado"],
    [
      ["AC-T01", "Prototipo usa pipeline temporal, no demo_seed", "PASS"],
      ["AC-T02", "DMC 330007 tratada como meteorología regional", "PASS"],
      ["AC-T03", "Features temporales usan solo información <= T", "PASS"],
      ["AC-T04", "Target positivo = FIRMS válido en (T, T+6h]", "PASS"],
      ["AC-T05", "score_current_grid produce las 50 celdas", "PASS"],
      ["AC-T06", "Ranking conserva empates reales", "PASS"],
      ["AC-T07", "cell_id alineado con su score bajo reordenamiento", "PASS"],
      ["AC-T08", "DEM sin cobertura permanece NaN/N-D, nunca 0", "PASS (datos) / parcial (UI)"],
      ["AC-T09", "App Streamlit carga sin excepción fatal", "PASS"],
      ["AC-T10", "Legacy/demo no participa en la inferencia", "PASS"],
    ],
    W(2, 9.5, 3.5)
  ));

  // ---------------- Anexo D ----------------
  out.push(annexTitle("D", "Atributos de calidad"));
  out.push(sourceNote("Fuente: docs/atributos-calidad-hito1.md (congelado)."));
  out.push(table(
    ["ID", "Atributo", "Requerimiento", "Estado"],
    [
      ["QA-01", "Fiabilidad", "REQ-06, 13, 14, 16", "VERIFICADO"],
      ["QA-02", "Integridad de datos", "REQ-10, 11, 12", "VERIFICADO"],
      ["QA-03", "Mantenibilidad", "REQ-06, 13", "PARCIALMENTE_VERIFICADO"],
      ["QA-04", "Robustez a datos faltantes", "REQ-15", "PARCIALMENTE_VERIFICADO"],
      ["QA-05", "Reproducibilidad", "(transversal)", "VERIFICADO"],
      ["QA-06", "Auditabilidad / trazabilidad", "REQ-07, 08, 10-16", "PARCIALMENTE_VERIFICADO"],
      ["QA-07", "Usabilidad", "REQ-05, 16", "PARCIALMENTE_VERIFICADO"],
      ["QA-08", "Rendimiento", "—", "NO_VERIFICADO (NOT_MEASURED)"],
      ["QA-09", "Seguridad", "—", "NO_VERIFICADO (NOT_PERFORMED)"],
      ["QA-10", "Disponibilidad", "—", "NO_APLICA"],
    ],
    W(1.5, 4.5, 3.5, 6.0)
  ));

  // ---------------- Anexo E ----------------
  out.push(annexTitle("E", "Matriz de riesgos"));
  out.push(sourceNote("Fuente: docs/riesgos-hito1.md (congelado). 23 riesgos; escala P×I reconstruida al cierre 07-09-2026 (no histórica)."));
  const riskRows = [
    ["R-NASA-FIRMS-01", "Dato", 2, 3, "Alta", "MATERIALIZADO_Y_CORREGIDO"],
    ["R-GRILLA-01", "Técnico", 3, 3, "Alta", "MATERIALIZADO_Y_CORREGIDO"],
    ["R-DMC-01", "Dato", 3, 2, "Alta", "MITIGADO"],
    ["R-CONAF-01", "Dato", 3, 2, "Alta", "TRANSFERIDO_A_SPRINT_2"],
    ["R-COBERTURA-01", "Técnico", 1, 2, "Baja", "MATERIALIZADO_Y_CORREGIDO"],
    ["R-INTEGRACION-01", "Técnico", 3, 3, "Alta", "TRANSFERIDO_A_SPRINT_2"],
    ["R-ETIQUETA-01", "Científico", 3, 3, "Alta", "ABIERTO"],
    ["R-METEO-POSICIONAL-01", "Dato", 3, 3, "Alta", "MATERIALIZADO_Y_CORREGIDO"],
    ["R-TARGET-OVERCOUNT-01", "Técnico", 2, 2, "Media", "MATERIALIZADO_Y_CORREGIDO"],
    ["R-BACKFILL-CONFLICTO-01", "Dato", 2, 2, "Media", "MATERIALIZADO_Y_CORREGIDO"],
    ["R-MINCLASS-01", "Técnico", 2, 2, "Media", "MATERIALIZADO_Y_CORREGIDO"],
    ["R-ALIGN-CELLID-01", "Técnico", 1, 3, "Media", "MITIGADO"],
    ["R-DEM-NAN-01", "Dato", 1, 2, "Baja", "MITIGADO"],
    ["R-LEGACY-CONTAM-01", "Técnico", 1, 3, "Media", "MITIGADO"],
    ["R-FRESCURA-01", "Dato", 2, 2, "Media", "MITIGADO"],
    ["R-HU-PIPELINE-01", "Metodológico", 3, 2, "Alta", "TRANSFERIDO_A_SPRINT_2"],
    ["R-ACEPT-EXT-01", "Metodológico", 3, 2, "Alta", "ABIERTO"],
    ["R-SPRINT-MGMT-01", "Metodológico", 3, 2, "Alta", "NO_RESUELTO"],
    ["R-MANTEN-01", "Técnico", 2, 1, "Baja", "ABIERTO"],
    ["R-PERF-SEC-01", "Técnico", 2, 2, "Media", "NO_RESUELTO"],
    ["R-CIENT-POSITIVOS-01", "Científico", 3, 2, "Alta", "ACEPTADO"],
    ["R-CIENT-MEGAEVENTO-01", "Científico", 2, 2, "Media", "ACEPTADO"],
    ["R-CIENT-GENERALIZACION-01", "Científico", 3, 3, "Alta", "ACEPTADO"],
  ];
  out.push(table(
    ["ID", "Categoría", "P", "I", "Prioridad", "Estado actual"],
    riskRows.map((r) => [r[0], r[1], String(r[2]), String(r[3]), r[4], r[5]]),
    W(3.4, 2.3, 0.7, 0.7, 1.7, 5.2)
  ));
  out.push(heading2("Control contable por estado"));
  out.push(table(
    ["Estado actual", "Cantidad"],
    [
      ["MATERIALIZADO_Y_CORREGIDO", "7"],
      ["MITIGADO", "5"],
      ["TRANSFERIDO_A_SPRINT_2", "3"],
      ["ABIERTO", "3"],
      ["NO_RESUELTO", "2"],
      ["ACEPTADO", "3"],
      ["TOTAL", "23"],
    ],
    W(10, 4)
  ));

  // ---------------- Anexo F ----------------
  out.push(annexTitle("F", "Versionamiento y calidad de código"));
  out.push(sourceNote("Fuente: docs/versionamiento-hito1.md y docs/calidad-codigo-hito1.md (congelados); artifacts/hito1/versioning/."));
  out.push(heading2("Tags reales del repositorio"));
  out.push(table(
    ["Tag", "Fecha", "Tipo"],
    [
      ["v1.0.0-data", "2026-06-20", "Anotado"],
      ["v2.0.0-baseline", "2026-06-20", "Anotado"],
      ["v3.0.0-final-release", "2026-06-20", "Anotado"],
      ["v3.2.0-demo-professional", "2026-06-20", "Anotado"],
      ["v1.0.0-sprint1-verified", "2026-08-31 (tagger date propio)", "Anotado"],
      ["v1.1.0-corredor-verified", "2026-09-05", "Anotado"],
    ],
    W(5, 5.5, 3.5)
  ));
  out.push(heading2("Partición temporal de commits (main, 68 total)"));
  out.push(table(
    ["Ventana", "Definición", "Commits"],
    [
      ["PRE_SPRINT", "fecha < 03-08-2026", "23"],
      ["SPRINT_1_WINDOW", "03-08 a 31-08-2026", "13"],
      ["POST_PLANNED_CLOSE", "fecha > 31-08-2026", "32"],
    ],
    W(4.5, 5.5, 4)
  ));
  out.push(heading2("Calidad de código — resumen"));
  out.push(table(
    ["Aspecto", "Estado"],
    [
      ["Modularidad", "FUERTE"],
      ["Nomenclatura", "ADECUADO"],
      ["Manejo de errores", "ADECUADO"],
      ["Aislamiento legacy", "VERIFICADO (test dedicado)"],
      ["Linting", "NOT_CONFIGURED"],
      ["Type checking", "NOT_CONFIGURED"],
      ["Complejidad ciclomática", "NOT_MEASURED"],
      ["Seguridad", "NOT_PERFORMED"],
    ],
    W(6, 8)
  ));

  // ---------------- Anexo G ----------------
  out.push(annexTitle("G", "Cierre de Sprint 1"));
  out.push(sourceNote("Fuente: docs/cierre-sprint1-hito1.md (congelado)."));
  out.push(heading2("Acciones para Sprint 2"));
  out.push(table(
    ["#", "Acción", "Momento", "Criterio de cierre"],
    [
      ["1", "Definir Sprint Goal antes de iniciar", "Día 1 Sprint 2", "Documento fechado al inicio"],
      ["2", "Definir DoD antes del desarrollo", "Día 1 Sprint 2", "DoD aplicado a la primera HU Done"],
      ["3", "Capturar snapshot inicial del backlog", "Día 1 Sprint 2", "Export Jira fechado al inicio"],
      ["4", "Registrar revisión semanal de riesgos", "Cada semana", "≥1 entrada real por semana"],
      ["5", "Vincular pipeline temporal a HU Jira", "Inicio Sprint 2", "HU con AC-T01-10 enlazados"],
      ["6", "Sesión real con evaluador externo", "Durante Sprint 2", "Protocolo completado por evaluador real"],
      ["7", "Completar integración CONAF (SAPI-26)", "Sprint 2", "SAPI-26 Finalizado con evidencia"],
      ["8", "Completar integración SAPI-32 a producción", "Sprint 2", "R-INTEGRACION-01 cerrado"],
      ["9", "Mejorar trazabilidad commit↔Jira", "Continuo", "Tasa >50% (vs. 10,3% actual)"],
      ["10", "Definir responsables individuales", "Inicio Sprint 2", "Campo responsable con nombre real"],
    ],
    W(0.8, 5.2, 3, 5)
  ));

  return out;
}

module.exports = { annexes };

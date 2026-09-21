---
name: sapi-scientific-integrity
description: Verificar integridad cientifica de S.A.P.I. al modificar features, targets, modelos, evaluacion o textos del dashboard y documentos.
---
# Integridad cientifica S.A.P.I.
Consultar docs/architecture-stack-freeze-sprint2.md y contrastar sus afirmaciones con el codigo y los artefactos relevantes. El documento distingue estado actual de arquitectura objetivo.
- Unidad: (cell_id, T); horizonte 6 horas. Features disponibles hasta T; target positivo en T < t <= T+6h. Verificar disponibilidad real, no solo fecha nominal. Ajustar transformaciones solo con entrenamiento.
- FIRMS representa detecciones satelitales de anomalias termicas; no confirma incendios ni igniciones en terreno.
- Presentar el score como ranking relativo exploratorio. No llamarlo probabilidad calibrada ni afirmar generalizacion sin evidencia. No describir el sistema como predictor validado de incendios.
- DMC es contexto regional/de estaciones; no meteorologia medida por celda.
- Baseline documentado: Modelo D, HistGradientBoostingClassifier. XGBoost y PostGIS del pipeline legacy no prueban que el prototipo activo los utilice.
- No inventar datos ni metricas. Identificar escenarios sinteticos y separar tests de software de validez cientifica.
- Al evaluar, considerar desbalance, validacion temporal causal, dependencia espacial y concentracion del evento 2024-02-03. Verificar conteos actuales antes de citarlos.
Reportar evidencia, limitaciones e impacto cientifico de un cambio. Si el usuario cambia el alcance, documentar la decision y reevaluar las afirmaciones afectadas.

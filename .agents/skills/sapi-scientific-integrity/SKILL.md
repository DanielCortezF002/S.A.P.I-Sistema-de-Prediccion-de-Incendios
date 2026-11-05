---
name: sapi-scientific-integrity
description: "Auditar científicamente el Modelo D, score relativo, FIRMS/DMC, DEM y F4 FAIL de S.A.P.I.; útil en modelos, datasets, métricas y afirmaciones académicas."
---

# S.A.P.I. / Ciencia responsable
BASELINE: `scientific_model_validation=false`, F4 FAIL, score relativo NO probabilidad calibrada.
Antes de decir "predicción validada": exigir ground truth externo apropiado, ventana objetivo, separación temporal/espacial, evitar leakage, metodología reproducible, métricas pertinentes y revisión humana.
Datos: distinguir detección FIRMS y evento real validado; DMC regional vs local; DEM Copernicus celdas N/D; versionado, causalidad ≤ T y licencias. No completar faltantes artificialmente.
NUNCA generar números sintéticos etiquetados como reales ni alterar pesos de Modelo D sin una tarea y protocolo experimental aprobado.
Si se pide F1/accuracy, buscar evaluación sobre datos etiquetados reales y reportar ausencia como NO VALIDADO si no existe.
Retener alertas/disclaimers: prototipo académico exploratorio, sin autorización institucional de alertas.
Salida: hipótesis, evidencia, limitaciones, riesgo de interpretación, plan de evaluación y decisión requerida a César.

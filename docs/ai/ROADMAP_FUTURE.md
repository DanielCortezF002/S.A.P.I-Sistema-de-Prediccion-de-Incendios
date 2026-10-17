# S.A.P.I. — Ruta de evolución posterior al Hito 2 (propuesta, no commits)

## Horizonte inmediato — cierre de Hito 2
Congelar baseline reproducible, enlazar evidencias a rúbricas, documento(s) académicos y demo robusta; resolver PR #30 SOLO con autorización; registrar retro y riesgos. No sacrificar credibilidad científica por un “100%” aparente.

## Horizonte siguiente — validez y datos (más alto impacto académico)
1. Acordar **pregunta de investigación** y criterio de validación con César. Formalizar variable objetivo (qué cuenta como incendio observado, ventana, geografía, fuente, sesgo de reporte).
2. Integrar fuente histórica confiable y permisos de uso (CONAF/u organismos competentes) sólo tras trazabilidad y licencia; documentar cobertura temporal/espacial y no equivaler puntos FIRMS a eventos verificados.
3. Evaluar integridad temporal/espacial: cortes por fecha y área, fuga de información, muestreo negativo, duplicados, valores faltantes, baseline congelado.
4. Diseñar baseline y benchmarks validados: precision/recall/F1/PR-AUC según desbalance; separar score ranking de probabilidades; calibración/Brier/ECE sólo si existe salida probabilística calibrable. Reportar intervalos de confianza si hay muestra suficiente.
5. Presentar error por zona/periodo, cobertura DEM, sesgos de estación, drift y metodología reproducible.
6. Solicitar juicio experto/uso simulado, SIN declarar validez científica u operación oficial antes de aprobación.

## Horizonte técnico
- Cerrar ADR proveedor cloud y spike `SAPI-67`, luego evaluar `SAPI-68` despliegue con seguridad, costos y protección credenciales, no como prioridad antes de defensa.
- Preparar experimentos temporales `SAPI-64` y comparativa `SAPI-65`; un LSTM NO reemplaza automáticamente Modelo D.
- Robustecer observabilidad de Spring/FastAPI/n8n/PostGIS, pruebas contractuales, performance y E2E multiambiente, manejo de incidentes, versionamiento y rollback.
- Integrar n8n para orquestación controlada; no emitir alertas externas reales ni activar automatizaciones sensibles sin autorización.
- Evolucionar UX de mapa, accesibilidad y explicación del ranking sin inducir falsa certeza.

## Regla de planificación
Por cada mejora: `decisión docente o problema → issue Jira → CA → ADR si hace falta → rama+PR → test → evidencia → aceptación`; estimar SP solo con datos del equipo, no inventar velocity.

---
name: sapi-e2e-quality
description: "Ejecutar o revisar pruebas unitarias, contrato, Docker Compose, Playwright/Edge, Folium y ranking S.A.P.I.; usar en QA de integración y frontend."
---

# S.A.P.I. / QA end-to-end
Construir matriz CA → prueba reproducible → evidencia, identificar happy/negative paths.
Stack: Streamlit/Folium → Spring Boot → FastAPI/Modelo D → PostGIS. Verificar ranking API y persistencia, 50 celdas si corresponde a contrato vivo, fingerprint inputs, idempotencia y fail-closed.
En UI: controles tabla↔mapa, clic celda texto/score/checkbox, filtros, orden, zoom/foco, DEM N/D, disclaimer F4, dark/light, no bucles de rerun, adaptativo 1366×768 y 1920×1080.
Probar fallos: API indisponible, payload inválido/corrupción DMC, store CURRENT ausente, inconsistencia geográfica, errores de red, datos no disponibles.
E2E de UI no equivale evaluación científica. Conservar reporte versión navegador, resolución, runid/SHA, evidencia visual y resultado PASS/FAIL.
No ejecutar comandos destructivos de DB/Docker; usar fixture/contendor aislado en cambios a estado.
Salida: tests ejecutados, alcance, fallos, errores observables, evidencias y acciones mínimas.

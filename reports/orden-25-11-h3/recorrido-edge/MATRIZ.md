# Recorrido Edge · `sapi-h3-518c0b5` · orden 25-11, punto 3

- Fecha: 2026-11-25, 04:28:39 a 04:29:33 UTC (01:28 a 01:29 Santiago).
- SHA del código: `518c0b58e6b229317f51b1da56ac23346dc2ef74`.
- Imágenes: web `43e4b811…`, backend `738e2f76…`, ml-api `54d48696…`, db `3f4a5d48…` (IDs completos en `../INFORME.md`).
- Hardware: AMD Ryzen AI 7 350 (8 núcleos, 16 hilos), 31 GB de RAM, Windows 11 Home 10.0.26200.
- Navegador: Edge 158.0.4370.33, canal `msedge`, headless, 1600 × 1000, un usuario, modo «Prototipo (datos reales)». Guion Playwright [recorrido_edge_h3.py](recorrido_edge_h3.py), una sola corrida, sin reintentos. Salida: [resultado.json](resultado.json), [consola.txt](consola.txt).
- Ejecutado en el computador local, no en ambiente desplegado.
- Condición de carga: durante el recorrido corría en paralelo un escaneo Trivy de imágenes. Los tiempos de abajo **no son mediciones de rendimiento**.

| Paso | Acción | Esperado | Observado | Evidencia | SHA | Veredicto |
|---|---|---|---|---|---|---|
| 1. Abrir | Cargar `http://127.0.0.1:18501/` | Cabecera, ranking y mapa visibles, sin traceback | Cabecera, avisos «PROTOTIPO EXPLORATORIO», «BACKEND REST», «DATOS HISTÓRICOS», 5 KPI y selector «Seleccionar celda (50 disponibles)». Sin traceback ni errores de consola. El selector tardó 45 s en aparecer (primer `ml_predict`, 27,1 s en ML según el log del backend). En la captura el mapa aún está vacío; en la captura del paso 4 ya está pintado. | [PNG](01-abrir.png), [texto](01-abrir.txt) | 518c0b5 | PASS (con nota: mapa sin pintar al capturar) |
| 2. Leer ranking | Leer aviso científico y grupo prioritario | Queda explícito que el score ordena por riesgo relativo y no es probabilidad calibrada | Aviso: «El score es un ranking relativo de riesgo, NO una probabilidad calibrada de incendio». Grupo prioritario #1 con 7 celdas empatadas en 0.1313. Datos identificados como históricos (2044 h). | [PNG](02-leer-ranking.png), [texto](02-leer-ranking.txt) | 518c0b5 | PASS |
| 3. Seleccionar | Elegir la 2.ª opción del selector | Selector y ficha muestran la celda elegida | Selector y ficha muestran VP-002, prioridad #1, empate ×7. | [PNG](03-seleccionar.png), [texto](03-seleccionar.txt) | 518c0b5 | PASS |
| 4. Entender datos | Leer la ficha de VP-002 | Distinguir score, datos de referencia, ventana y datos ausentes | 285 m, 11,2°, score 0.131293, ventana 01 sep 2026 00:00–06:00 UTC. Meteorología marcada «sin dato» y explicada como fuera del contrato v0; DMC reciente «no disponible» y aclarado que no se usó en el ranking. | [PNG](04-datos.png), [texto](04-datos.txt) | 518c0b5 | PASS |
| 5. Actualizar | Abrir barra lateral y pulsar «Actualizar ranking» una vez | Nueva consulta y panel utilizable | El clic se hizo a las ~04:29:29 UTC. El backend registró `ml_predict` 200 a las 04:29:38.9 UTC (9,4 s en ML). La captura (04:29:32) quedó tomada **durante** la recarga: página atenuada y hora de consulta aún «04:29». No hay captura del estado final tras la actualización. | [PNG](05-actualizar.png), [texto](05-actualizar.txt), log backend en `../INFORME.md` | 518c0b5 | PARCIAL (consulta acreditada por log; la UI final no quedó capturada) |
| 6a. Abrir grilla | Desplegar «Ver ranking completo (50 celdas) y filtros» | Grilla y controles visibles | Columnas Prioridad, Celda, Score relativo, Empate, Grupo; filtro «Todos los grupos (50 celdas)»; insignia «50 celdas evaluadas». La página sigue atenuada por la recarga del paso 5. | [PNG](06-grilla.png), [texto](06-grilla.txt) | 518c0b5 | PASS (con nota de atenuación) |
| 6b. Consultar las 50 filas | — | — | No se hizo en este recorrido (no se desplazó la grilla fila por fila). La API devolvió 50 celdas en un GET directo hecho hoy antes del recorrido (HTTP 200, 15,4 s). | `../INFORME.md` | 518c0b5 | NO_EVALUABLE en UI |
| Resiliencia ml-api | — | — | No ejecutada: procedimiento preparado en `../PROCEDIMIENTO-6B-RESILIENCIA-ML-API-H3.md`. | — | 518c0b5 | NO_EVALUABLE (pendiente de Daniel) |

## Defectos y limitaciones observados

- Persiste la tarjeta «Origen del ranking: GET /api/v1/ranking · Spring Boot (cache 5 min)», ya señalada en el ítem 40 (histórico): la caché de 300 s es de la vista Streamlit, no del backend. [Captura](04-datos.png)
- Persisten las tarjetas «Temp. reg. T» y «Viento reg. T» truncadas («sin dato en el rank…»), ya señaladas en el ítem 40. [Captura](04-datos.png)
- El guion espera 2,5 s tras «Actualizar ranking»; con la recarga tardando ~9 s, el paso 5 se capturó antes de terminar. Es un límite del guion, no un defecto acreditado del producto. Se respetó «un solo recorrido» y no se repitió.

## Clasificación

- **Verificado hoy:** todo lo de la tabla, con hora UTC en cada `.txt`.
- **Histórico:** las dos observaciones de defectos ya registradas el 24-11 en el ítem 40.
- **Pendiente:** captura final del paso 5, paso 6b en UI y resiliencia ml-api.

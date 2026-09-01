# Matriz de Trazabilidad de Requerimientos y Atributos de Calidad (ISO 25010)
**Proyecto:** S.A.P.I. — Sistema de Alerta y Predicción de Incendios Forestales
**Sprint:** Sprint 1 (Cierre — Semana 5)
**Fecha:** 31-08-2026

| ID Req | Historia de Usuario | Componente / Módulo | Atributo de Calidad (ISO 25010) | Criterio de Aceptación / Métrica | Caso de Prueba Pytest |
| :---: | :--- | :--- | :--- | :--- | :--- |
| **RF-01** | HU-01: Ingesta NASA FIRMS | src/ingesta/parallel_ingester.py | Confiabilidad / Tolerancia a fallos | Reintentos con tenacity ante fallos HTTP | tests/test_ingesta.py |
| **RF-02** | HU-02: Ingesta Telemetría DMC | src/ingesta/parallel_ingester.py | Eficiencia de desempeño | Ingesta concurrente vía hilos en < 30s | tests/test_ingesta.py |
| **RF-03** | HU-03: Persistencia Espacial | src/db.py / PostGIS | Integridad de datos | Geometrías EPSG:4326 con índices GiST | tests/test_cell_zones.py |
| **RF-04** | HU-04: Lógica 30-30-30 | src/procesamiento/features.py | Exactitud funcional | Flag binario activo si T>30, HR<30, V>30 | tests/test_features.py |
| **RF-05** | HU-05: Motor XGBoost + SMOTE | src/modelo/optimizer.py | Efectividad analítica | Recall >= 75% para mitigar falsos negativos | tests/test_optimizer.py |
| **RF-06** | HU-06: Mitigación Latencia (R-10) | app/utils/map_renderer.py | Eficiencia de tiempo | Renderizado interactivo en memoria RAM < 0.2s | tests/test_baseline.py |
| **RF-07** | HU-07: Exportación de Reporte | app/utils/cell_table.py | Portabilidad / Interoperabilidad | Generación de archivo .txt para radiofrecuencia | tests/test_cell_table.py |
| **RF-08** | HU-08: Dashboard Web UI | app/app.py (Streamlit) | Usabilidad (Escritorio) | Validación mediante acta UAT con usuario | tests/test_architecture.py |

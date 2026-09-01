# Matriz de Gestión de Riesgos v1
**Proyecto:** S.A.P.I. — Sistema de Alerta y Predicción de Incendios Forestales
**Sprint:** Sprint 1 (Cierre — Semana 5)
**Fecha:** 31-08-2026

| ID | Riesgo Identificado | Categoría | Prob. | Impacto | Nivel | Estrategia de Mitigación / Contingencia |
| :---: | :--- | :--- | :---: | :---: | :--- |
| **R-01** | Datos NASA FIRMS con nulos o baja resolución | Técnico (Datos) | Media | Alto | **Alto** | Filtrado por sensor VIIRS (375m) e imputación estadística. |
| **R-02** | Indisponibilidad o cambios en API DMC | Técnico (Infra) | Media | Medio | **Medio** | Reintentos con tenacity y fallback a staging PostGIS. |
| **R-03** | Desbalance severo de igniciones (1:1000) | Técnico (ML) | Alta | Alto | **Crítico** | Balanceo SMOTE y calibración de umbral por F-beta (beta=2). |
| **R-04** | Latencia cartográfica y colapso OOM en servidor (1 GB RAM) | Técnico (Software) | Alta | Crítico | **Crítico** | Transformación a centroides Point, índices GiST y caché RAM. |
| **R-05** | Inconsistencia de entornos Dev / Prod | Técnico (DevOps) | Media | Medio | **Medio** | Contenerización con Docker y docker-compose.yml. |
| **R-06** | Degradación de usabilidad en móviles | Técnico (UI/UX) | Alta | Medio | **Alto** | Documentado en Acta UAT; desarrollo de API REST en Sprint 2. |

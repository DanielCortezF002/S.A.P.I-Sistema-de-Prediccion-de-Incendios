# Guion de presentaci?n Hito 2 ? S.A.P.I. (20 minutos)

**Candidato Consolidado:** Commit `8010e4421cf91b80e6dc66d732ef6e98dfd1e4d8` (Base F7: `51ec3c06b67959d3daad6349c962a1be643906b4`).  
**Fecha de Consolidaci?n:** 24 de octubre de 2026.  
**Evaluaci?n Normativa:** Mat?as Vargas ? Proyecto de T?tulo Hito 2 (Cobertura integral de criterios M1 a M8).  
**Estructura Cronometrada:** 5 + 5 + 7 + 3 = 20 minutos estrictos.  

### Matriz de Mapeo Normativo a la R?brica de Mat?as Vargas (M1?M8)

| Criterio Evaluado | Ponderaci?n | Bloque del Guion | Minutos | Evidencia T?cnica Verificable |
| :--- | :---: | :--- | :---: | :--- |
| **M1. Incremento Funcional del Sprint 2** | 20% | Bloque 3: Demostraci?n en vivo | 10?17 | 4 microservicios en Docker, flujo completo Streamlit -> Spring Boot -> FastAPI -> PostGIS. |
| **M2. An?lisis y Especificaci?n de Requerimientos** | 15% | Bloque 1: Contexto y requerimientos | 00?05 | Backlog 14 HU / 58 SP, conciliaci?n con Jira (12 finalizadas, 1 por hacer, 1 pendiente). |
| **M3. Arquitectura de Software** | 15% | Bloque 2: Arquitectura y datos | 05?07 | Topolog?a desacoplada en Docker, 11 ADRs versionados, contratos OpenAPI fijados por SHA-256. |
| **M4. Dise?o de Datos, Procesos y Plataformas** | 15% | Bloque 2 y Bloque 3 | 07?10, 15?17 | DER PostGIS, Flyway V001-V004, clave natural idempotente y `scientific_model_validation=false`. |
| **M5. Implementaci?n y Calidad T?cnica** | 15% | Bloque 2 y Bloque 3 | 05?17 | Spring Boot 3 con fail-closed, FastAPI async, `HistGradientBoostingClassifier` desacoplado. |
| **M6. Validaci?n y Pruebas del Incremento** | 10% | Bloque 4: Evidencias y cierre | 17?18 | 102 tests Python PASS, 137 tests Java Surefire PASS, 91 evidencias R2 con SHA-256 verificado. |
| **M7. Integraci?n T?cnica y Atributos de Calidad** | 5% | Bloque 3: Demostraci?n en vivo | 13?15 | Latencias CA4 R2 (cold 6.867 ms, update 3.723 ms, cached 424 ms), red privada `sapi-v2-net`. |
| **M8. Evidencia T?cnica, Trazabilidad y Evoluci?n** | 5% | Bloque 1 y Bloque 4 | 01?02, 18?20 | Superaci?n del monolito Hito 1, matriz de 19 riesgos y Gate B en NO GO como ?tica de software. |

---

## Bloque 1 — Contexto y requerimientos (5 min)

**Minuto 0-1 — Portada y problema.**
"S.A.P.I. prioriza el riesgo relativo de incendio forestal en 50 celdas de la
interfaz urbano-forestal de Valparaíso —la misma zona del megaincendio de
Viña del Mar de 2024— combinando datos satelitales NASA FIRMS y meteorología
de la DMC. No predice con certeza; ordena dónde mirar primero."

**Minuto 1-2 — Lección del Hito 1.**
"El Hito 1 dejó un prototipo técnico sólido pero sin backend formal, sin
frontend desplegable independiente y sin explicar la técnica de puntaje de
riesgo. Matías y César lo señalaron explícitamente."

**Minuto 2-4 — Requerimientos del Sprint 2.**
"Comprometimos 14 historias, 58 puntos. Hoy, 9 historias (37 SP) están
formalmente terminadas con evidencia ejecutada; 5 historias (21 SP) tienen
brechas reales que voy a mostrar sin maquillar, no a esconder."

**Minuto 4-5 — Pregunta de investigación.**
"La pregunta central: ¿es viable un sistema desacoplado y reproducible que
priorice riesgo relativo sin afirmar probabilidad calibrada, y es una LSTM
superior a un modelo tabular dado el desbalance real de los datos? La
segunda mitad de esa pregunta tiene una respuesta experimental, no una
opinión — la muestro en el bloque 4."

---

## Bloque 2 — Arquitectura y datos (5 min)

**Minuto 5-7 — Arquitectura de 4 servicios.**
Mostrar el diagrama (`INFORME_HITO2_FINAL.md` §7): Streamlit v2 → Spring Boot
→ FastAPI/Modelo D → PostgreSQL/PostGIS, en red Docker privada. Decir:
"Esto no es un diagrama aspiracional: el freeze científico verifica en cada
corrida que el servicio ML es idéntico al congelado, y los contratos OpenAPI
están fijados por hash. 11 ADRs documentan cada decisión."

**Minuto 7-9 — Modelo de datos PostGIS.**
Mostrar el DER (`INFORME_HITO2_FINAL.md` §8). Decir: "El score nunca puede
persistirse como probabilidad calibrada — no es una regla de negocio en
prosa, es un `CHECK` de PostgreSQL que rechaza la escritura. Lo mismo para la
procedencia del dato: `firms_origin` es obligatorio desde la migración V004."

**Minuto 9-10 — Qué cambió desde el Hito 1.**
"Eliminamos el monolito: Streamlit ya no ejecuta el modelo, consume una API
REST. Pasamos de archivos JSON en disco a un esquema relacional-espacial con
idempotencia garantizada por clave natural."

---

## Bloque 3 — Demostración en vivo (7 min)

**Minuto 10-11 — Arranque de servicios.**
*Comando:* `python scripts/bootstrap_compose_v2.py` (alternativa aprobada
formalmente por el Product Owner para CA5 de SAPI-66, Jira `#10156` —
decirlo explícitamente, no esconder que el `docker-compose up` desnudo
requiere este paso).
*Mostrar:* 4 contenedores `Up (healthy)`.

**Minuto 11-13 — Navegación y ranking.**
Abrir `http://localhost:8501`. Mostrar las 50 celdas rectangulares VP-001 a VP-050, badge "Semántica:
relative_rank (no calibrado)", KPI "50 celdas evaluadas".

**Minuto 13-15 — Actualización interactiva.**
Clic en "Actualizar ranking". Mostrar el cambio de timestamp y la latencia
medida (tiempos R2 certificados: cold 6.867 ms, update interactivo 3.723 ms, cached 424 ms).

**Minuto 15-17 — Persistencia e idempotencia en PostGIS.**
*Comando:* `docker exec -it <db> psql -U sapi -d sapi_v2 -c "SELECT id, forecast_time, model_version, firms_origin FROM ejecuciones;"`
Mostrar que múltiples clics no duplican filas (clave natural + `ON CONFLICT`).

---

## Bloque 4 — Evidencias y evolución (3 min)

**Minuto 17-18 — Gate de calidad.**
"5 de 6 subpuertas pasan con evidencia real atada a este SHA. La sexta
(freeze) falla por tres causas explicadas, no por defectos nuevos — las
muestro sin filtrar." (señalar la tabla de `INFORME_HITO2_FINAL.md` §9).

**Minuto 18-19 — SAPI-63: resultado científico negativo.**
"Reproduje este experimento yo mismo hoy, contra el dato real: 107 positivos
en 362 883 filas, 26 de 49 folds de prueba sin ningún positivo. Una LSTM no
es viable con este volumen — y la literatura revisada confirma el mismo
patrón en dominios comparables. Mantenemos el baseline tabular con HistGradientBoostingClassifier."

**Minuto 19-20 — Cierre honesto.**
"Lo que falta no es ingeniería oculta: es autorización humana para el primer
refresco con datos reales, la firma del ADR de proveedor cloud, y tres
un defecto arquitectónico (ADV-05, atomicidad de publicación bajo fallo de IO) que mantenemos abierto a propósito, bloqueado en change-control hasta decidir el diseño correcto."

---

## Plan de contingencia

| Falla | Acción inmediata | Respaldo |
|---|---|---|
| Docker lento/no arranca | Usar contenedores ya inicializados o capturas pre-certificadas | `artifacts/hito2/d26/`, capturas Selenium |
| Colisión de puertos | `bootstrap_compose_v2.py --web-port 18509` (puertos altos parametrizables) | Script ya probado con puertos no estándar |
| Streamlit se desconecta | F5; si persiste, mostrar capturas de navegador real | `artifacts/hito2/d21/ca4_browser_*.png` |
| Pregunta difícil sobre LSTM | Proyectar la reproducción de hoy y la literatura citada | `docs/evidence/sapi63-reproduction-20261015/`, §4 del Informe |
| Pregunta sobre por qué SAPI-43 sigue abierto | Explicar el runbook listo y la decisión humana pendiente, sin inventar una ejecución que no ocurrió | `docs/ops/FIRST-CONTROLLED-REFRESH.md` |

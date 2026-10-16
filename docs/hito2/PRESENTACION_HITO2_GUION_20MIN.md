# Guion de presentación Hito 2 — S.A.P.I. (20 minutos)

Candidato: `d11428a6165dd0dd26f3440cb850ab08ab09f06a`. Estructura exigida por
la Directiva 33: 5 + 5 + 7 + 3 minutos. Reemplaza el borrador previo
(placeholders `[ATTEMPT2_RESULT]` etc., ya resueltos en
`docs/evidence/actualizacion-informe-y-guion-20261015/`).

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
Abrir `http://localhost:8501`. Mostrar las 50 celdas H3, badge "Semántica:
relative_rank (no calibrado)", KPI "50 celdas evaluadas".

**Minuto 13-15 — Actualización interactiva.**
Clic en "Actualizar ranking". Mostrar el cambio de timestamp y la latencia
medida (~1.7 s, dato real, no estimado).

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
patrón en dominios comparables. Mantenemos XGBoost."

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

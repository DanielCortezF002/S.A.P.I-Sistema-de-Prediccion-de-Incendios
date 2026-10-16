# Preguntas anticipadas de la comisión y respuestas preparadas — Hito 2

Basado en la retroalimentación real de Hito 1 (R-01 a R-09,
`retroalimentacion hito 1 sprint 2.md`) y en las brechas identificadas en
esta sesión. Cada respuesta cita evidencia real, no opinión.

## Sobre arquitectura (César IL2.3 / Matías criterio 3)

**P: "¿Por qué Spring Boot y no se quedaron con el bridge de n8n?"**
R: El Hito 1 usaba un bridge HTTP ligero para scoring local; el Sprint 2
construyó un backend Spring Boot formal como orquestador de aplicación
(R-02/R-03 de la retroalimentación de Matías), separando la responsabilidad
de negocio del motor científico. Verificado con 162 pruebas JUnit reales.

**P: "¿Cómo garantizan que el microservicio ML no se les fue de las manos en complejidad?"**
R: El check `F4c` del freeze científico compara el servicio ML contra una
versión congelada en cada corrida del gate; solo se permiten los campos
declarados de `RankingResult`. No es confianza, es un chequeo automatizado.

## Sobre datos y persistencia (César IL2.4 / Matías criterio 4)

**P: "¿Por qué PostgreSQL/PostGIS y no MongoDB, como se sugirió en Hito 1?"**
R: (R-04) Se evaluó explícitamente antes de decidir: el pipeline necesita
geometrías, series temporales y restricciones relacionales estrictas
(idempotencia por clave natural, checks de rango). MongoDB se reserva para
un caso de uso documental real que aún no existe. PostGIS permite
restricciones a nivel de base de datos que una colección documental no
ofrece igual de nativamente (p.ej., `CHECK (score_semantics = 'relative_rank')`).

**P: "¿Qué pasa si alguien intenta guardar un score como probabilidad?"**
R: La base de datos lo rechaza. `ejecuciones_sin_validacion_cientifica CHECK
(scientific_model_validation = false)` y `ejecuciones_score_semantics_ranking
CHECK (score_semantics = 'relative_rank')` hacen que sea imposible, no solo
una convención de código.

## Sobre el modelo científico (César IL2.1 / evaluación experimental)

**P: "¿Por qué no probaron una red neuronal recurrente, como sugerí en Hito 1?"**
R: (R-06/R-07) Se probó, con un protocolo walk-forward causal riguroso
(entrenar hasta año X, evaluar en X+1, sin fuga temporal) — no la propuesta
original de entrenar con 2025 y evaluar en 2024, que habría introducido
leakage. El resultado, reproducido hoy de forma independiente: 1:3390 de
desbalance, 26 de 49 folds de prueba sin ningún positivo. Una LSTM colapsa a
predicción trivial en ese régimen — consistente con literatura reciente
sobre redes recurrentes bajo desbalance severo (Informe 2, §4).

**P: "¿Cómo saben que ese resultado no es un error de su código?"**
R: El experimento se ejecutó de nuevo, de forma independiente, en esta
sesión, contra el dataset real (hash SHA-256 verificado), y produjo una
salida idéntica byte a byte al reporte ya versionado. Además, 25 pruebas
unitarias verifican con datos sintéticos que la ventana causal nunca incluye
el paso objetivo y que no hay solape temporal entre folds.

**P: "¿El Modelo D fue reentrenado para este sprint?"**
R: No. Su fingerprint de reproducibilidad se verifica sin cambios en cada
corrida del freeze científico (`F2`).

## Sobre gestión y honestidad de estado (César criterio 5-6 / Matías 1, 6, 8)

**P: "¿Por qué el gate no pasa al 100%?"**
R: Por diseño, no lo ocultamos: el subgate de freeze falla por tres causas
explicadas (sin remoto Git real en este flujo de clones locales, tres hashes
de migración preexistentes idénticos al origen sin tocar, y cambios
autorizados de SAPI-71 con su propia cadena de aprobación documentada). Los
otros 5 subgates —lint, pruebas Python, Maven, SQL/Flyway, contenedores—
pasan con evidencia real.

**P: "¿Por qué SAPI-43 sigue sin cerrar si la arquitectura está probada?"**
R: Porque probar la arquitectura con datos sintéticos no es lo mismo que
operar con datos reales. Eso requiere credenciales y una autorización humana
explícita que no están en nuestras manos decidir unilateralmente; el
procedimiento ya está escrito y lo mostramos (runbook
`FIRST-CONTROLLED-REFRESH.md`), pero no fingimos haberlo ejecutado.

**P: "¿El criterio de aceptación CA5 de SAPI-66 se cumplió o no?"**
R: Tal como fue escrito literalmente ("`docker-compose up` sin configuración
adicional"), no — lo comprobamos ejecutándolo. El Product Owner aprobó
formalmente una alternativa (`bootstrap_compose_v2.py`), documentada en Jira
con la justificación técnica de por qué es más segura que copiar una
contraseña estática. Eso resuelve ese criterio específico, no toda la
historia: las dependencias con datos reales siguen abiertas.

## Sobre el proveedor cloud (Matías criterio 7, SAPI-67)

**P: "¿Ya decidieron dónde van a desplegar?"**
R: No. El ADR-011 compara 4 proveedores con 9 criterios y recomienda dos
alternativas (Railway, AWS Lightsail), pero permanece en estado "Propuesto",
sin firma. No se despliega nada hasta que exista esa decisión formal — y no
la fabricamos para esta presentación.

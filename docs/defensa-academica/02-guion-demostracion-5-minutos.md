# S.A.P.I. — Guion de Demostración en Vivo (5 Minutos)

**Audiencia:** Comisión Evaluadora / Profesores Guía y Corrector  
**Rol del Expositor:** Ingeniero de Software / Arquitecto Técnico  
**Tiempo Límite:** 05:00 minutos  
**Entorno de Demostración:** `http://127.0.0.1:18504` (Dashboard Streamlit) + Terminal IDE  

---

## Preparación Previa a la Exposición (Checklist 2 min antes)

1. Verificar que los 4 contenedores Docker estén activos:
   - `sapi-demo-academico-web-v2-1` (`127.0.0.1:18504`)
   - `sapi-demo-academico-backend-1` (`127.0.0.1:18092`)
   - `sapi-demo-academico-ml-api-1` (`127.0.0.1:18012`)
   - `sapi-demo-academico-db-v2-1` (`127.0.0.1:15442`)
2. Tener el navegador abierto en `http://127.0.0.1:18504`.
3. Tener una pestaña de terminal abierta en el directorio del proyecto.

---

## Cronograma Minuto a Minuto

### [00:00 – 01:00] Minuto 1: Contexto, Problema y Propósito

**Acción en Pantalla:** Mostrar la pantalla de inicio de S.A.P.I. (`web-v2`).

**Discurso sugerido:**
> *"Buenos días estimada comisión. Hoy presento el Sistema de Alerta y Priorización de Incendios, S.A.P.I.*
> 
> *En escenarios de emergencia forestal, los recursos de combate —brigadas terrestres y aeronaves— son limitados. El problema que resolvemos no es adivinar el futuro, sino **priorizar el territorio**. Hemos delimitado un corredor de estudio de 50 celdas georreferenciadas en la Región de Valparaíso.*
> 
> *Durante el Sprint 1 validamos la viabilidad matemática de un modelo de gradiente (`HistGradientBoostingClassifier`). En este Sprint 2, el desafío fue migrar de un script aislado a una **arquitectura de software empresarial, distribuida, auditable e idempotente**."*

---

### [01:00 – 02:00] Minuto 2: La Arquitectura de Microservicios en Acción

**Acción en Pantalla:** Alternar 10 segundos a la terminal para mostrar `docker ps` o señalar los badges del encabezado: `PROTOTIPO EXPLORATORIO`, `BACKEND REST`, `POSTGIS PERSISTED`, `HISTGRADIENTBOOST (MODELO D)`.

**Discurso sugerido:**
> *"La interfaz que están viendo no ejecuta machine learning en el navegador ni lee archivos de disco locales. Está desacoplada en una arquitectura de cuatro capas:*
> 1. *El frontend **Streamlit** consume la API REST empresarial.*
> 2. *El backend en **Spring Boot (Java 21)** orquesta las consultas, gestiona las migraciones de base de datos con Flyway y asegura la persistencia de auditoría.*
> 3. *El microservicio de inferencia en **FastAPI** sirve el Modelo D congelado de forma aislada.*
> 4. *Una base de datos **PostgreSQL 15 con PostGIS** registra espacialmente cada evaluación.*
> 
> *Toda la infraestructura se despliega con Docker Compose sin costos de nube (\$0 CLP), en redes internas seguras y con puertos expuestos únicamente en loopback."*

---

### [02:00 – 03:00] Minuto 3: Exploración Territorial y Selección de Celda

**Acción en Pantalla:**
1. Interactuar con el mapa Folium en pantalla completa.
2. Hacer clic en una celda roja/naranja (por ejemplo, `VP-013` o `VP-001`).
3. Observar cómo se actualiza el panel lateral derecho con el detalle de la celda.

**Discurso sugerido:**
> *"En el centro de operaciones observamos la grilla territorial sobre la cartografía base de OpenStreetMap. Cada celda cubre un área estandarizada del corredor.*
> 
> *Al seleccionar una celda en el mapa, como la `VP-013`, el panel de la derecha refleja inmediatamente su estado: su identificador territorial, su posición en el ranking, su score relativo y sus variables físicas de referencia: elevación y pendiente derivadas de nuestro modelo digital de elevación (DEM).*
> 
> *Podemos alternar entre ver 'Todas las celdas' y la vista filtrada de 'Prioridades', lo que permite a un comandante de incidente concentrar su atención en el cuartel crítico del territorio."*

---

### [03:00 – 04:00] Minuto 4: Semántica Científica y Manejo Riguroso de Empates

**Acción en Pantalla:**
1. Señalar la tarjeta de **Grupo Prioritario**: `#1 · 7 celdas empatadas (Score: 0.131293)`.
2. Señalar el banner del **Aviso Científico**: *"El score corresponde a un ranking relativo exploratorio y no a una probabilidad calibrada de incendio"*.

**Discurso sugerido:**
> *"Aquí radica la honestidad y rigurosidad técnica de S.A.P.I.:*
> 
> *Como observan en la tarjeta superior, el Grupo 1 está compuesto por **7 celdas que comparten exactamente el mismo score relativo (0.131293)**. Un error común en sistemas novatos es forzar un orden artificial —por ejemplo ordenar por ID alfabético— engañando al operador. S.A.P.I. reporta el empate real: las 7 celdas comparten la prioridad #1.*
> 
> *Además, respetamos estrictamente el estado científico del proyecto: el flag `scientific_model_validation` permanece en `false` porque la compuerta F4 no ha sido liberada operacionalmente. Por lo tanto, el sistema prohíbe taxativamente presentar estos scores como probabilidades calibradas porcentuales o emitir alertas oficiales de evacuación CONAF/SENAPRED. Es una herramienta de priorización relativa para apoyo a la decisión."*

---

### [04:00 – 05:00] Minuto 5: Trazabilidad, Contrato REST y Conclusión

**Acción en Pantalla:**
1. Abrir el expansor inferior: *"Información técnica y fuentes"*.
2. Destacar los metadatos de trazabilidad: `inputs_fingerprint`, timestamp UTC, dataset hash, estación meteorológica Rodelillo DMC.
3. Abrir el expansor *"Ver ranking completo"* para mostrar la tabla ordenada de 50 celdas.

**Discurso sugerido:**
> *"Finalmente, abro el panel de trazabilidad técnica:*
> 
> *Aquí queda en evidencia el cumplimiento del contrato REST `sapi-ranking-v0`: visualizamos el inputs fingerprint que garantiza que los datos no fueron alterados, la estación meteorológica Rodelillo y la procedencia de focos satelitales NASA FIRMS.*
> 
> *Respecto a la meteorología, el contrato v0 del ranking consume estas variables dentro de la inferencia del Modelo D; su exposición directa como telemetría instantánea en el JSON ya está catalogada formalmente como mejora aditiva para el contrato v1.*
> 
> *En conclusión: hemos entregado un sistema funcional, visualmente adaptado para modo oscuro y pantallas de alta resolución, que corre sobre microservicios reales y mantiene una integridad científica intachable. Quedo a disposición de sus preguntas."*

---

## Consejos Clave para el Expositor

- **No hables rápido:** Mantén un tono calmado, profesional y seguro. 5 minutos es tiempo suficiente si sigues este guion.
- **Si el mapa tarda medio segundo en cargar:** Explica que Folium se renderiza en el cliente sobre una grilla de 50 polígonos vectoriales nativos.
- **Si preguntan por qué no hay datos de hoy en vivo:** "La demostración utiliza la fecha histórica congelada del 1 de septiembre de 2026 bajo el modo de reproducibilidad estricta ADR-009, garantizando paridad con los experimentos de laboratorio."

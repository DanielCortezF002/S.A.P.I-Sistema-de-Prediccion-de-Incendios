# S.A.P.I. — Banco de Preguntas y Respuestas para Defensa Técnica

**Documento de Preparación para Examen de Título**  
**Proyecto:** Sistema de Alerta y Priorización de Riesgo de Incendios Forestales (S.A.P.I.)  
**Nivel:** Ingeniería Civil en Informática / Software Engineering  

---

## Índice Temático

1. [Docker, Contenedores y Redes](#1-docker-contenedores-y-redes)
2. [Arquitectura REST y Diseño de Contratos](#2-arquitectura-rest-y-diseño-de-contratos)
3. [Spring Boot y Capa de Negocio](#3-spring-boot-y-capa-de-negocio)
4. [FastAPI y Servicio de Machine Learning](#4-fastapi-y-servicio-de-machine-learning)
5. [PostgreSQL y PostGIS](#5-postgresql-y-postgis)
6. [Idempotencia, Caché y Reproducibilidad](#6-idempotencia-caché-y-reproducibilidad)
7. [Manejo de Errores, Resiliencia y Seguridad](#7-manejo-de-errores-resiliencia-y-seguridad)
8. [Integridad Científica y Limitaciones del Modelo D](#8-integridad-científica-y-limitaciones-del-modelo-d)

---

## 1. Docker, Contenedores y Redes

### P1.1: ¿Por qué utilizar Docker Compose y cómo estructuraron los servicios?
**Respuesta:**  
Docker Compose permite definir y ejecutar aplicaciones multi-contenedor como código versionable (IaC). En S.A.P.I. separamos responsabilidades en 4 servicios principales para el Sprint 2:
- `db-v2`: Motor relacional y espacial (PostgreSQL 15 + PostGIS 3.4).
- `ml-api`: Microservicio de inferencia en Python con FastAPI y dependencias científicas (GDAL, scikit-learn).
- `backend`: Orquestador empresarial en Spring Boot (Java 21) que ejecuta migraciones Flyway y persistencia.
- `web-v2`: Frontend interactivo en Streamlit.

Adicionalmente, usamos **Docker Compose Profiles** (`presentation`, `legacy`, `ops`). La ruta por defecto (`docker compose up`) levanta únicamente el pipeline objetivo (`db-v2`, `ml-api`, `backend`), mientras que la capa web se levanta de forma controlada bajo el perfil `presentation`, asegurando que no se mezclen los entornos de desarrollo con los servicios legados del Sprint 1.

### P1.2: ¿Cómo gestionan la comunicación entre contenedores y por qué los puertos se publican en 127.0.0.1?
**Respuesta:**  
Los contenedores se comunican internamente mediante una red puente dedicada (`sapi-v2-net`) utilizando **DNS interno de Docker** por nombre de servicio (p. ej., `http://backend:8080`, `http://ml-api:8000`, `jdbc:postgresql://db-v2:5432/sapi_v2`). Nunca usan `localhost` para hablar entre ellos.  
Hacia el exterior (el host del operador), los puertos se publican con la directiva explícita `127.0.0.1:${PORT}:${PORT}`. Esto restringe el acceso exclusivamente a la interfaz loopback local, impidiendo que escuchen en `0.0.0.0` y evitando exponer servicios sin autenticación perimetral hacia la red de la universidad o internet.

### P1.3: ¿Cómo funcionan los Healthchecks configurados?
**Respuesta:**  
Cada contenedor cuenta con un healthcheck no trivial que prueba el endpoint real de salud:
- En `backend`: `curl -fsS --noproxy * http://127.0.0.1:8080/health`. El flag `-f` hace fallar el comando ante códigos HTTP >= 400, y `--noproxy` evita desvíos si el sistema anfitrión tiene proxies configurados.
- En `ml-api`: Un script inline de Python que consulta `http://127.0.0.1:8000/health` mediante `urllib.request` configurado con un proxy handler vacío, devolviendo código de salida 0 solo si el modelo y su metadata están cargados en RAM.
- En `db-v2`: `pg_isready -h 127.0.0.1 -p 5432` sobre TCP.  
Esto permite que Spring Boot espere a que PostGIS esté verdaderamente saludable (`condition: service_healthy`) antes de lanzar las migraciones Flyway al boot.

---

## 2. Arquitectura REST y Diseño de Contratos

### P2.1: ¿Cuál es el contrato REST principal entre Streamlit y Spring Boot?
**Respuesta:**  
El contrato es `GET /api/v1/ranking`. Devuelve una proyección JSON que incluye:
- Metadatos de la corrida: `schema_version` (`sapi-ranking-v0`), `model_version`, `forecast_time`, `inputs_fingerprint`, `score_semantics` (`relative_rank`), `scientific_model_validation` (`false`).
- Parámetros de la ventana temporal: `horizon_hours`, `weather_timestamp`, `age_hours`, `freshness`.
- Datos de procedencia: `station_id`, `station_name`, `firms_origin`, `firms_coverage_end`, `firms_lag_days`, `firms_status`.
- Colección de celdas: Lista de exactamente 50 objetos conteniendo `cell_id`, `score`, `rank`, `display_rank` y `tie_group_size`.

### P2.2: ¿Por qué el contrato v0 no incluye valores meteorológicos directos en cada celda?
**Respuesta:**  
Por diseño de separación de responsabilidades y alcance del Sprint 2. El endpoint `/api/v1/ranking` es una proyección de priorización territorial, no una API meteorológica. El Modelo D utiliza la meteorología (temperatura, humedad, viento) internamente en el microservicio ML como variables de inferencia (features). El DTO de respuesta v0 se enfocó en garantizar la integridad del ranking de las 50 celdas, los empates y la trazabilidad. La exposición directa de telemetría instantánea está catalogada formalmente como una mejora aditiva para el contrato v1.

---

## 3. Spring Boot y Capa de Negocio

### P3.1: ¿Qué rol cumple Spring Boot si el modelo ML está en Python?
**Respuesta:**  
Spring Boot actúa como el **Backbone Empresarial**:
1. **API Gateway y Fachada:** Provee un endpoint REST estandarizado y tipado con DTOs inmutables en Java 21 (Records).
2. **Control de Versiones de Base de Datos:** Orquesta las migraciones estructurales con Flyway sobre PostGIS al momento de inicializar el servicio.
3. **Persistencia Transaccional:** Al recibir la respuesta del microservicio ML, persiste atómicamente la corrida (`run`) y los 50 registros de celdas en la base de datos relacional.
4. **Idempotencia y Validación:** Valida los payloads contra el esquema contractual antes de servirlos al cliente, impidiendo la propagación de datos corruptos o valores nulos no permitidos.

### P3.2: ¿Cómo se gestionan las migraciones de base de datos con Flyway?
**Respuesta:**  
Las migraciones viven en archivos SQL versionados dentro de `db/migration/` (ej. `V1__init_schema.sql`, `V2__create_ranking_tables.sql`). En `docker-compose.yml`, este directorio se monta en solo lectura (`:ro`) dentro del contenedor de backend en `/app/db/migration`.  
La propiedad `SPRING_FLYWAY_FAILONMISSINGLOCATIONS: "true"` asegura que si el directorio montado no existe o no se puede leer, el contenedor aborta inmediatamente el arranque en lugar de iniciar con un esquema vacío.

---

## 4. FastAPI y Servicio de Machine Learning

### P4.1: ¿Por qué FastAPI para servir el modelo en lugar de Flask o Django?
**Respuesta:**  
FastAPI está construido sobre Starlette y Pydantic, ofreciendo:
- Alto rendimiento asíncrono sobre servidores ASGI (Uvicorn).
- Validación automática de tipos de entrada y salida mediante esquemas Pydantic.
- Generación automática de especificaciones OpenAPI / Swagger (`/docs`), facilitando la verificación del contrato con el equipo de backend.
- Huella de memoria mínima en comparación con frameworks full-stack como Django.

### P4.2: ¿Cómo garantiza el microservicio ML la reproducibilidad científica?
**Respuesta:**  
El microservicio opera bajo la variable `SAPI_REPRODUCIBILITY_MODE: "1"` (definida en el ADR-009). En este modo, no realiza descargas dinámicas ni scraping en tiempo de ejecución, sino que carga el snapshot inmutable y congelado de artefactos del Hito 1 (`artifacts/hito1/reproducibility/`), correspondiente a la ventana del 1 de septiembre de 2026. Cualquier inferencia sobre este dataset devuelve exactamente los mismos 50 scores relativos.

---

## 5. PostgreSQL y PostGIS

### P5.1: ¿Qué ventajas aporta PostGIS frente a una base de datos relacional tradicional?
**Respuesta:**  
PostGIS extiende PostgreSQL añadiendo tipos de datos geométricos (`GEOMETRY`, `POLYGON`, `POINT`) e índices espaciales (`GIST` basados en R-Trees). Esto permite:
- Almacenar los límites geográficos exactos de las 50 celdas territoriales del corredor en coordenadas UTM (EPSG:32719) o WGS84 (EPSG:4326).
- Realizar consultas topológicas nativas (intersecciones `ST_Intersects`, contención `ST_Contains`, distancias `ST_Distance`) en microsegundos, sin procesar la geometría en la memoria de la aplicación.
- Facilitar la integración futura con herramientas GIS profesionales como QGIS o ArcGIS Server.

### P5.2: ¿Qué se almacena exactamente al ejecutar un ranking?
**Respuesta:**  
Se almacena un registro en la tabla de ejecuciones (`runs`) con el timestamp de predicción, la huella digital (`inputs_fingerprint`), la versión del modelo y los metadatos de FIRMS y DMC. Asociados a esa corrida, se insertan exactamente 50 registros en la tabla de celdas (`cell_ranking`), con el ID de la celda (`VP-001` a `VP-050`), su score matemático, su posición relativa (`display_rank`) y su multiplicidad de empate (`tie_group_size`).

---

## 6. Idempotencia, Caché y Reproducibilidad

### P6.1: ¿Qué es la idempotencia y cómo se demuestra en S.A.P.I.?
**Respuesta:**  
En ciencias de la computación, una operación es idempotente si realizarla múltiples veces produce el mismo resultado y el mismo estado del sistema que realizarla una sola vez.  
En S.A.P.I., si se invoca `GET /api/v1/ranking` de manera consecutiva:
1. El backend reconoce la huella de entrada y la ventana de pronóstico.
2. No duplica corridas redundantes en PostGIS.
3. El frontend mantiene un caché en memoria con TTL de 5 minutos (`@st.cache_data(ttl=300)`).
4. El ranking resultante conserva idéntico orden, idénticos 50 scores e idénticos empates.

---

## 7. Manejo de Errores, Resiliencia y Seguridad

### P7.1: ¿Qué ocurre si el microservicio de ML (`ml-api`) se cae o tarda demasiado?
**Respuesta:**  
El backend Spring Boot tiene configurados timeouts estrictos: `SAPI_ML_CONNECT_TIMEOUT: 2s` y `SAPI_ML_READ_TIMEOUT: 60s`.  
Si `ml-api` no responde o arroja un error 500, el backend atrapa la excepción y devuelve al cliente un código HTTP 503 (Service Unavailable) o 504 (Gateway Timeout) con un JSON estructurado que tipifica el error (`error_type: "inference_failed"` o `"ml_timeout"`).  
En Streamlit, la clase `BackendRankingClient` procesa este error y renderiza una tarjeta de advertencia controlada (`_render_backend_error`), sin exponer jamás trazas de pila (stack traces), rutas de archivos en el servidor ni credenciales al usuario.

---

## 8. Integridad Científica y Limitaciones del Modelo D

### P8.1: ¿Por qué la aplicación enfatiza que los scores son un "ranking relativo" y no probabilidades calibradas?
**Respuesta:**  
Esta es una decisión de **ética e integridad profesional en ingeniería**.  
Un modelo de Machine Learning clasificador (como `HistGradientBoostingClassifier`) produce salidas numéricas entre 0 y 1 mediante una función sigmoide o softmax. Sin embargo, estas cifras son **scores de decisión matemática**, no probabilidades estadísticas calibradas del mundo real. Decir que una celda tiene un "72% de probabilidad de incendio" sin calibración isotónica o de Platt y sin validación temporal exhaustiva es irresponsable en protección civil.  
S.A.P.I. categoriza el resultado como un ranking relativo de priorización: la celda con score 0.147 presenta mayores indicadores comparativos de riesgo que la celda con 0.102, orientando los recursos de vigilancia hacia donde el modelo detecta mayor concentración de señales.

### P8.2: ¿Qué significa que `scientific_model_validation` esté en `false` y F4 permanezca en FAIL?
**Respuesta:**  
Dentro del marco metodológico de S.A.P.I., la compuerta F4 evalúa la validez científica del modelo frente a series temporales no vistas y métricas operacionales de desbalance extremo.  
Debido a que el modelo no ha sido validado en escenarios operacionales en tiempo real con datos meteorológicos continuos de múltiples temporadas, la compuerta F4 está formalmente registrada como **FAIL** y el flag `scientific_model_validation` es estrictamente `false`.  
Por esta razón, S.A.P.I. Sprint 2 se defiende como una **plataforma arquitectónica de demostración y priorización exploratoria**, no como un sistema de despacho oficial de emergencias.

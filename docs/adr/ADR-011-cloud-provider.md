# ADR-011 — Selección de Proveedor Cloud para el Vertical Slice de S.A.P.I. v2

| Campo | Valor |
|---|---|
| **Documento** | `docs/adr/ADR-011-cloud-provider.md` |
| **Historia Jira** | SAPI-67 (`S2-14 — Spike y ADR de selección de proveedor cloud`) |
| **Épica** | SAPI-25 (`Infraestructura y Persistencia`) |
| **Relacionado** | ADR-001 (Spring Boot), ADR-002 (FastAPI ML), ADR-003 / SAPI-58 (PostGIS), ADR-004 / SAPI-60 (Docker Compose v2), ADR-008 (Flyway), ADR-009 (Modo Reproducible), ADR-010 (Cliente HTTP / Timeouts) |
| **Estado de la Decisión** | **Propuesto** (Evaluación técnica terminada; dos alternativas viables con decisión humana pendiente; sin contratación de servicios) |
| **Estado de Despliegue** | **No desplegado.** Conforme a las condiciones del Sprint 2 y GO W0, no se ejecutan despliegues en infraestructura cloud ni se firman contratos |
| **Autor / Rol** | Senior Data Engineer, Cloud Architect y Technical Research Lead (Antigravity) |
| **Fecha de Elaboración** | 14 de octubre de 2026 |

> [!NOTE]
> **Nota de Nomenclatura:** Este documento formaliza el entregable de la historia SAPI-67 como **ADR-011** dentro de la serie canónica de decisiones arquitectónicas de S.A.P.I. (`ADR-001..011`). Preserva de manera íntegra e independiente el archivo `docs/adr/ADR-003.md`, el cual rige exclusivamente la adopción de PostgreSQL/PostGIS como persistencia operacional. Este ADR no reemplaza ni modifica `ADR-003.md`.

---

## 1. Contexto y Requisitos del Sistema

S.A.P.I. v2 evoluciona desde un monolito Streamlit exploratorio hacia una arquitectura desacoplada multicontenedor orientada a microservicios (`docker-compose.yml`, SAPI-60). Para preparar una eventual migración o despliegue piloto en la nube (planificado para el Hito 3 / Sprint post-congelamiento en SAPI-68), es indispensable evaluar proveedores de infraestructura cloud considerando la viabilidad económica, estabilidad operativa y compatibilidad técnica estricta con la arquitectura congelada.

### 1.1 Perfil de Carga y Requisitos Técnicos Mínimos

El vertical slice v2 de S.A.P.I. está compuesto por 4 componentes interconectados:

1. **Base de Datos Operacional (`db-v2`):**
   - Motor: PostgreSQL 15 + extensión PostGIS 3.4 (`postgis/postgis:15-3.4`).
   - Esquema: Gestionado exclusivamente mediante migraciones Flyway (V001..V003 / V004, ADR-008).
   - Consumo observado en reposo (idle): **~75 MB RAM** con extensiones espaciales cargadas y migraciones ejecutadas.
   - Requisito de persistencia: Volumen persistente inmutable ante reinicios de contenedores.
2. **Servicio ML (`ml-api`):**
   - Framework: FastAPI (Python 3.11+, Uvicorn).
   - Carga: Modelo D (XGBoost 1.7+, artefacto serializado `prototype_model_d.pkl`, features geoespaciales con geopandas/shapely).
   - Consumo observado en reposo (idle): **~216 MB RAM** con el modelo cargado en memoria.
   - Invocación: HTTP sincrónico interno (`POST /predict`). Tiempo de scoring observado en la medición D15 del backend: **1,9 s – 3,3 s** (ejecución síncrona en contenedor para las 50 celdas del piloto, reemplazando la estimación informal inicial de ~10–14 s). Alcance de la medición: scoring local en red interna dockerizada, con una única solicitud y sin concurrencia de analistas ni latencia WAN.
   - Nota sobre consumo en inferencia: El pico de memoria durante la inferencia activa de las 50 celdas no ha sido medido formalmente bajo carga estresada en contenedor.
3. **Backend de Aplicación (`backend`):**
   - Framework: Spring Boot 3.x sobre Java 21 (Eclipse Temurin).
   - Funciones: Exposición REST pública (`GET /api/v1/ranking`), ejecución de Flyway al boot, cliente HTTP RestClient hacia ML, persistencia write-through en PostGIS.
   - Consumo observado en reposo (idle): **~282 MB RAM** (JVM heap base + metaspace).
4. **Capa de Presentación (`web-v2`):**
   - Framework: Streamlit v2 (Python 3.11).
   - Funciones: Consumo de la API REST de Spring Boot, renderizado de mapas folium/pydeck interactivos.
   - Consumo observado en reposo (idle): **~145 MB RAM**.
5. **Red, Seguridad y Consumo Acumulado:**
   - Red interna privada aislada: Comunicación inter-servicio por nombres DNS de contenedor (`ml-api:8000`, `db-v2:5432`). El ML y la base de datos **nunca** deben exponerse a la internet pública sin autenticación.
   - Terminación TLS/HTTPS automática para los endpoints públicos (`backend:8080` y `web-v2:8501`).
   - Consumo acumulado observado del stack en reposo (idle): **~718 MB (~720 MB RAM)** (Backend: 282 MB, ML: 216 MB, Streamlit: 145 MB, PostgreSQL: 75 MB). El pico de memoria durante inferencia y concurrencia activa no está medido.

---

## 2. Alternativas Evaluadas

Se analizaron 4 proveedores cloud representativos de modelos PaaS, CaaS (Containers-as-a-Service) e IaaS:

1. **Railway (`railway.com`):** PaaS moderno orientado a microservicios. Despliega servicios independientes a partir de Dockerfiles, imágenes o templates dentro de un proyecto compartido con red privada interna. **Aclaración técnica:** Railway no ejecuta directamente archivos multi-contenedor `docker-compose.yml` en su runtime de producción; requiere desacoplar el compose en 4 servicios individuales interconectados mediante variables y DNS privado.
2. **Render (`render.com`):** Plataforma PaaS ampliamente difundida para aplicaciones web y bases de datos gestionadas.
3. **Fly.io (`fly.io`):** Plataforma de microVMs globales (Firecracker) sobre contenedores OCI con red Anycast y WireGuard mesh.
4. **Amazon Web Services (AWS) — Free Tier / Lightsail / ECS:** IaaS y CaaS estándar de la industria cloud corporativa. Con Lightsail permite ejecutar directamente `docker-compose.yml` en una instancia virtual Linux unificada.

---

## 3. Matriz Comparativa Detallada

La siguiente matriz evalúa cada proveedor frente a los criterios operativos exigidos, contrastando información vigente a 2026:

| Criterio de Evaluación | Railway | Render | Fly.io | AWS (Lightsail / Free Tier / ECS) |
|---|---|---|---|---|
| **1. Soporte Docker / Multi-contenedor** | **Desacoplado por servicio.** Despliega cada componente como un servicio independiente a partir de Dockerfile, imagen o template dentro de un mismo proyecto compartido. No ejecuta directamente `docker-compose.yml` en runtime. | **Parcial.** Admite Dockerfile por servicio. Para multi-servicio requiere configurar `render.yaml` (Blueprints). No ejecuta `docker-compose.yml` directo en runtime. | **Nativo por App.** Cada servicio es una Fly Machine independiente generada desde Dockerfile. Orquestación mediante `fly.toml` por componente. | **Completo en Lightsail.** Permite clonar y ejecutar `docker compose up` idéntico al entorno local sobre la VM Linux. ECS Fargate requiere definiciones de tarea complejas en JSON/Terraform. |
| **2. PostgreSQL / PostGIS Administrado** | **Excelente.** Template de Postgres gestionado con soporte nativo de extensiones (`CREATE EXTENSION postgis;`) o contenedor `postgis/postgis` propio con volumen persistente. | **Restringido.** Postgres administrado soporta PostGIS en planes de pago. En el Free Tier la base de datos **se elimina automáticamente a los 30 días**. | **No administrado.** Ofrece Postgres como app sobre microVM (Fly Postgres). La instalación de PostGIS exige imagen personalizada y mantenimiento manual de backups. | **Robusto.** RDS PostgreSQL soporta PostGIS nativo con alta disponibilidad y backups automáticos. En Lightsail puede usarse Postgres en contenedor Docker idéntico al local. |
| **3. Red Privada Inter-servicio** | **Automática.** Red privada dentro del proyecto vía DNS interno (ej. `backend.railway.internal`, `db.railway.internal`). Sin exposición de puertos sensibles a internet. | **Soportada.** Red privada entre servicios de la misma región (`<service-name>:port`). El puerto de la base puede mantenerse privado. | **Excelente.** Malla global WireGuard IPv6 (6PN) nativa. Conexión privada vía `<app-name>.internal`. | **Excelente.** VPC, Subnets y Security Groups en AWS corporativo; firewall simplificado por puertos en Lightsail. |
| **4. Capacidad de Memoria vs Stack SAPI (~720 MB en reposo)** | **Flexible.** Asignación elástica sin techo rígido de 512 MB por servicio; escala verticalmente según demanda. Adecuado para absorber picos de inferencia no medidos. | **Margen crítico en Free Tier.** Plan gratuito limitado a **512 MB RAM** por servicio. Deja margen exiguo frente al consumo observado (Backend: ~282 MB, ML: ~216 MB), presentando alto riesgo operativo bajo carga. | **Flexible.** Configurable por microVM (256MB / 512MB / 1GB / 2GB). Permite dimensionar memoria holgada por servicio pagando por recurso activo. | **Lightsail:** Instancias de 2 GB a 4 GB RAM cubren holgadamente los ~720 MB en reposo del stack completo en una sola máquina. **EC2 Free Tier (t2.micro):** 1 GB RAM total deja margen muy estrecho (<300 MB libres). |
| **5. Terminación HTTPS y Dominios** | **Automática.** Certificados SSL Let's Encrypt aprovisionados y renovados sin intervención para subdominios `.up.railway.app` y dominios propios. | **Automática.** Certificados SSL gratuitos y automáticos para `onrender.com` y dominios personalizados. | **Automática.** Terminación TLS en borde Anycast global con certificados automáticos. | **Lightsail:** Certificado Let's Encrypt mediante reverse proxy (Caddy/Nginx) o distribución Lightsail. **AWS ECS:** Requiere ALB (~$16–$20/mo) + ACM. |
| **6. Facilidad de CI/CD** | **Excelente.** Integración directa con GitHub. Trigger automático ante commits, despliegue de previsualización (PR review apps) y rollback instantáneo con un clic. | **Buena.** Auto-deploy ante push a rama git. Soporte de Deploy Hooks mediante webhooks HTTP. | **Buena.** CLI `flyctl` potente y GitHub Actions mediante tokens de organización. | **Media en Lightsail.** Git push mediante SSH runner o script de deploy automatizado. **Compleja en ECS:** Requiere pipelines con AWS OIDC IAM. |
| **7. Persistencia y Seguridad de Datos** | **Sólida.** Volúmenes persistentes SSD montables por servicio ($0.25/GB/mes). Cifrado de variables de entorno en reposo. Backups de base de datos. | **Limitada en Free.** Discos persistentes solo en planes pagos. El Free Tier no admite persistencia garantizada y destruye la BD a los 30 días. | **Buena.** Volúmenes NVMe cifrados en reposo (`fly volumes`). Backups automáticos requieren configuración de scripts por el usuario. | **Sólida en Lightsail:** Disco SSD incluido con snapshots manuales y automáticos programables. **Empresarial en RDS:** EBS cifrado con KMS y Point-in-Time Recovery. |
| **8. Modelo Tarifario y Costo Mensual** | **Tarifa publicada:** Base Hobby $5/mes + cómputo ($0.000231/vCPU/h y $0.000231/GB-RAM/h) + volumen ($0.25/GB/mes). **Estimación SAPI:** ~$12 – $18 USD/mes según horas de actividad efectiva de los 4 servicios. | **Tarifa publicada:** Starter $7/mes por servicio + Postgres Starter $7/mes. **Estimación SAPI:** ~$28 – $35 USD/mes para mantener 4 componentes pagos sin borrado a 30 días. | **Tarifa publicada:** ~$3.19/mes por microVM 512MB + almacenamiento ($0.15/GB/mes). **Estimación SAPI:** ~$16 – $22 USD/mes para 4 microVMs. | **Tarifa publicada:** Paquete fijo mensual de **$10 USD/mes** (2 GB RAM) o **$20 USD/mes** (4 GB RAM); cargo adicional de IPv4 pública si aplica (~$2.50–$4/mes). **Estimación SAPI:** $10 – $24 USD/mes predecible. |
| **9. Riesgos de Operación y Mantenimiento** | **Bajo.** Entorno PaaS administrado. Sin parches de sistema operativo, reinicios transparentes y observabilidad integrada con métricas de RAM/CPU. | **Alto en tier gratuito; Medio en pago.** Riesgo crítico de degradación si se confía en capas gratuitas (spin-down de 15 min causa demoras de 50s en requests). | **Medio.** Responsabilidad del operador en el mantenimiento de la base de datos (Postgres unmanaged) y resolución de problemas vía CLI `flyctl`. | **Muy Bajo en Lightsail** (máquina virtual unificada con firewall simple y paridad Compose); **Alto en ECS puro** (VPC, IAM, NAT Gateway). |

---

## 4. Análisis Crítico: Evaluación de Factibilidad en Capas Gratuitas

Uno de los hallazgos de esta evaluación técnica es que **los planes gratuitos disponibles en el mercado presentan restricciones operacionales incompatibles con la estabilidad mínima requerida para el vertical slice S.A.P.I. v2**:

1. **Render Free Tier:**
   - La base de datos PostgreSQL gratuita expira y se purga de forma irreversible a los **30 días corridos de su creación**, impidiendo la continuidad del piloto.
   - Los servicios web gratuitos se suspenden tras 15 minutos de inactividad (*idle spin-down*). Un cold start de Spring Boot (Java 21) tarda entre 35 y 60 segundos en levantar la JVM y ejecutar las migraciones de Flyway, excediendo los timeouts de clientes HTTP.
   - El límite estricto de 512 MB de RAM por servicio deja un margen exiguo frente al consumo observado en reposo (Backend: ~282 MB, ML: ~216 MB), lo que introduce alto riesgo operativo de inestabilidad durante la ejecución o procesamiento simultáneo.
2. **AWS Free Tier (12 meses):**
   - La instancia elegible `t2.micro` ofrece únicamente **1 vCPU y 1 GB de memoria RAM**. Frente al consumo acumulado del stack observado en reposo (~720 MB RAM entre los 4 contenedores), una máquina de 1 GB deja menos de 300 MB libres para el sistema operativo base, buffers de I/O y fluctuaciones de carga, imponiendo severo riesgo de degradación por swap sin que se haya medido aún el pico real durante inferencia.
   - Componentes adicionales para producción como Application Load Balancer (ALB) y transferencias salientes generan costos recurrentes no cubiertos por la capa gratuita.
3. **Railway y Fly.io:**
   - Ambas plataformas han sustituido sus esquemas de uso gratuito ilimitado por modelos de consumo tarifado por segundo sobre cuentas con tarjeta de crédito o cuotas base de suscripción mensual.

**Conclusión:** Un despliegue cloud para el vertical slice S.A.P.I. v2 requiere presupuestar formalmente un costo operacional base de entre **$10 y $24 USD mensuales**. Intentar forzar la arquitectura en capas gratuitas introduce riesgos severos de pérdida periódica de base de datos a los 30 días, latencias por cold-start y márgenes de memoria estrechos.

---

## 5. Alternativas Propuestas para Decisión Humana

Se definen **dos alternativas técnicas viables**, con trade-offs complementarios, quedando la selección final y autorización formal exclusivamente sujeta a la decisión humana del responsable del proyecto:

### Alternativa 1 (Modelo PaaS / Microservicios): RAILWAY
- **Fundamento técnico:** Plataforma PaaS donde cada uno de los 4 componentes (`db-v2`, `ml-api`, `backend`, `web-v2`) se aprovisiona como un servicio desacoplado dentro de un proyecto compartido, comunicándose por DNS privado interno (`.railway.internal`).
- **Consideración de orquestación:** Requiere desacoplar el archivo `docker-compose.yml` en servicios individuales con sus respectivos Dockerfiles/imágenes y variables de entorno; no ejecuta directamente el archivo compose en runtime.
- **Régimen de costos (fuente oficial railway.com/pricing, 2024–2026):** Tarifa base Hobby de $5 USD/mes + cómputo granular por segundo ($0.000231/vCPU/h y $0.000231/GB-RAM/h) + volumen persistente ($0.25/GB/mes). Consumo mensual estimado para el stack SAPI: **~$12 a $18 USD/mes** según régimen de actividad efectiva.
- **Ventaja:** Observabilidad individual por contenedor, escalabilidad independiente de recursos y red privada sin configuración de firewall manual.

### Alternativa 2 (Modelo VPS / Paridad Directa Docker Compose): AWS LIGHTSAIL
- **Fundamento técnico:** Servidor virtual unificado (Linux) con Docker Engine y Docker Compose preinstalados, permitiendo clonar el repositorio y ejecutar exactamente el comando local `docker compose up` sin reescribir la orquestación ni desacoplar servicios.
- **Régimen de costos (fuente oficial aws.amazon.com/lightsail/pricing, 2024–2026):** Tarifa de paquete fija mensual predecible:
  - Plan 2 GB RAM / 1 vCPU / 60 GB SSD: **$10 USD/mes** base (+~$2.50 USD/mes con IPv4 dedicada según región).
  - Plan 4 GB RAM / 2 vCPUs / 80 GB SSD: **$20 USD/mes** base (+~$4.00 USD/mes con IPv4 dedicada según región).
- **Ventaja:** Paridad absoluta 100% con el entorno de pruebas local, predictibilidad de costo mensual fijo y holgura de memoria comprobada frente a los ~720 MB en reposo.

---

## 6. Consecuencias de la Decisión

### Consecuencias Positivas
- **Aislamiento de Red:** Cumplimiento de estándares de seguridad al no exponer la capa de inferencia ni la persistencia a internet.
- **Trazabilidad de Despliegue:** Despliegues automáticos o reproducibles desde la rama principal aprobada (`main`) trazables a commits específicos en GitHub.
- **Continuidad de Datos:** Eliminación del riesgo de borrado de esquemas o particiones temporales que aqueja a las opciones gratuitas.
- **Paridad de Entornos:** La configuración de variables de entorno respetará exactamente los nombres del contrato formalizados en `.env.example` (`SAPI_ML_BASE_URL`, `SPRING_DATASOURCE_URL`, etc.).

### Consecuencias Negativas y Mitigaciones
- **Costo Operacional:** Requiere asignar una tarjeta de crédito institucional o personal con un límite de gasto mensual configurado (mitigación: configurar *Hard Spend Limits* o presupuestos en AWS/Railway a $25 USD para evitar sorpresas).
- **Consumo de Ancho de Banda:** La descarga de imágenes Docker pesadas durante el CI/CD puede consumir cuotas (mitigación: optimizar Dockerfiles con imágenes slim y multi-stage builds).

---

## 7. Referencias Verificables

1. **Railway Documentation:**
   - Pricing & Usage: `https://railway.com/pricing` (revisado con tarifas vigentes 2024–2026)
   - Private Networking: `https://docs.railway.com/guides/private-networking`
   - Persistent Volumes: `https://docs.railway.com/databases/volume-storage`
2. **Render Documentation:**
   - Free Tier Limits & Inactivity Spin-Down: `https://render.com/docs/free`
   - PostgreSQL 30-Day Expiration Policy: `https://render.com/docs/free#free-postgresql-databases`
   - PostGIS Support: `https://render.com/docs/databases#postgis`
3. **Fly.io Documentation:**
   - Fly Machines & MicroVMs: `https://fly.io/docs/machines/`
   - Fly Postgres Architecture: `https://fly.io/docs/postgres/`
   - WireGuard Private Networking (6PN): `https://fly.io/docs/reference/private-networking/`
4. **Amazon Web Services:**
   - AWS Free Tier Details: `https://aws.amazon.com/free/`
   - AWS Lightsail Pricing & Bundles: `https://aws.amazon.com/lightsail/pricing/` (actualizado con política de IPv4 pública 2024)
   - PostGIS on Amazon RDS for PostgreSQL: `https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Appendix.PostgreSQL.CommonDBATasks.PostGIS.html`
5. **S.A.P.I. Repositorio:**
   - Congelamiento de Arquitectura: `docs/architecture-stack-freeze-sprint2.md`
   - Especificación Docker Compose: `docker-compose.yml` (SAPI-60)
   - Variables de Entorno: `.env.example`
   - Medición de Latencia Backend D15: `1,9 s – 3,3 s` (`src/backend`)

---

## 8. Registro de Aprobación Formal

Este ADR ha sido elaborado con base en evidencia técnica rigurosa y verificable. Su estado es **PROPUESTO**. Se presentan dos alternativas viables (Railway y AWS Lightsail) para resolución humana. No se ha firmado ningún contrato ni contratado infraestructura cloud en el marco de este spike. La formalización, selección final y eventual aprovisionamiento de credenciales o recursos queda exclusivamente bajo la autoridad del responsable humano del proyecto.

```
ESTADO DE APROBACIÓN: PENDIENTE DE REVISIÓN Y FIRMA FORMAL

Responsable Humano: Daniel Gonzalo Cortez Fierro
Rol: Project Lead / Architect
Firma / Decisión: _____________________________________________
Fecha de Resolución: [PENDIENTE]
```

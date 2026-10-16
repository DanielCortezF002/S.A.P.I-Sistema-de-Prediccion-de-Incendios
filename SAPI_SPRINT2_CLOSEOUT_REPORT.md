# S.A.P.I. — INFORME DE CIERRE TÉCNICO Y ACADÉMICO: SPRINT 2

**Fecha de Cierre:** 16 de octubre de 2026
**Responsable:** Principal Software Engineer, Tech Lead, QA Lead y DevOps Engineer
**Rama de Trabajo:** `feat/sprint2-final-closeout`
**Commit Base Candidato:** `8982e58f0c8820ad3ba492a69e7c10eacf77ca41`
**Commits de cierre:** `4ef54e7` (E2E) y `8bd7ba1` (informe inicial)
**Veredicto Global:** **VERTICAL SLICE ACADÉMICO VALIDADO — PRODUCCIÓN NO AUTORIZADA (F4 FAIL)**

---

## 1. Resumen Ejecutivo y Matriz de Estado Jira

El cierre técnico de S.A.P.I. Sprint 2 consolida la integración real de extremo a extremo del vertical slice bajo la arquitectura v2 congelada:
$$\text{NASA FIRMS + DMC} \longrightarrow \text{FastAPI (Modelo D)} \longrightarrow \text{Spring Boot} \longrightarrow \text{PostgreSQL / PostGIS} \longrightarrow \text{Streamlit}$$

| Issue Jira | Descripción y Alcance | Estado Técnico | Evidencia Clave |
| :--- | :--- | :---: | :--- |
| **SAPI-71** | Refresh atómico, versionado, idempotente y recuperable de FIRMS/DMC. | **PASS** | Suite adversarial offline (25/25 tests PASS), remediación B1/B2/B3 y ADV-05 verificadas, cobertura y procedencia authenticada en Autorización B. |
| **SAPI-43** | Primera corrida diaria operacional persistida en PostGIS (50 celdas, trazabilidad de inputs, idempotencia). | **PASS** | Persistencia write-through demostrada en PostgreSQL 15 / PostGIS 3.4 (`ejecuciones` id=1, 50 celdas en `predicciones_celda`), replay idempotente verificado (0 duplicados). |
| **SAPI-66** | Prueba E2E reproducible desde Streamlit hasta ML y PostGIS en Docker Compose. | **PASS** | Benchmark automatizado en navegador Microsoft Edge (`measure_browser_e2e_d21.py`): Cold navigation 897.4 ms, Clic actualización 1952.5 ms, 50 celdas visibles y persistidas. |
| **SAPI-55** | Servicio ML FastAPI encapsulando Modelo D (`HistGradientBoostingClassifier`). | **PASS** | `POST /predict` y `GET /health` conformes con contrato OpenAPI v0; scoring relativo sin probabilities calibradas. |
| **SAPI-57** | Cliente REST en Spring Boot para orquestación de inferencia con timeouts y degradación. | **PASS** | `GET /api/v1/ranking` orquesta scoring, valida contratos y maneja fallos aguas arriba con códigos tipados (422, 503, 504). |
| **SAPI-59** | Persistencia write-through vía Spring JDBC en PostgreSQL/PostGIS. | **PASS** | Esquema Flyway V001..V004, `celdas_geom` con 50 polígonos SRID 4326 válidos, ordenamiento por `rank ASC`. |
| **SAPI-60** | Orquestación Docker Compose v2 de la arquitectura modular. | **PASS** | `docker-compose.yml` + `docker-compose.operational.yml` levantando stack aislado de 4 contenedores saludables con nombres y puertos dedicados. |
| **SAPI-61** | Frontend Streamlit desacoplado consumiendo Spring Boot REST. | **PASS** | Profile `presentation` activo; UI interactiva en puerto dedicado sin llamadas a pipelines legacy ni acceso directo a DB. |
| **F4 (Científico)** | Validación científica del modelo y calibración de probabilidades. | **FAIL** | **Límite científico estricto:** El Modelo D produce un ranking exploratorio relativo, no probabilidades calibradas. F4 permanece en FAIL. |

---

## 2. Evidencias Verificadas del Piloto B y Cierre SAPI-71

La Autorización B (ejecutada el 16 de octubre de 2026 en clon aislado) fue auditada y preservada íntegramente:

* **Directorio de Evidencia Auténtica:** `C:\Users\danie\AppData\Local\SAPI-pilot-evidence\B-20261016T020154Z-ca44f77b`
* **Commit de Referencia Piloto:** `8982e58f0c8820ad3ba492a69e7c10eacf77ca41`
* **Fingerprint Reproducible Congelado (Hito 1):** `33c2eacc49bd0cc130928b5bd182ec523e63614f0e3dd97a129a8d4657f231ff`
* **Modelo D Artefacto (`models/prototype_model_d.pkl`):**
  `SHA256: AC017BEF1F42A30AC74BA3E3787368C4418798B2D562ADCFBA01C923CFF2173F` (Invariable)
* **FIRMS Baseline (`data/processed/nasa_firms_2021-08-30_2026-08-30.csv`):**
  `SHA256: A9A85DB4431B3E54F936B724E4DE5A7FBB0CC19F5721F5E1A344A192BF9BB271` (Invariable)

### Hashes y Artefactos Operacionales Validados (Traslado Autorizado)
| Archivo | SHA256 Hash | Dimensión / Filas |
| :--- | :--- | :--- |
| `firms/..._f7307f698603.csv` | `F7307F698603EAE42B5E9CB635E1044031901BAAEDAAA1E4C1F29FF9043FC590` | 12,641 filas (164 nuevas) |
| `firms/CURRENT.json` | `8D6F3B2A210B544E883BFD91A73A631D920C6CE36EFF6CA341BB370CC9174C65` | Schema v3 publicado |
| `dmc/330007/versions/..._09_ac1709ed7ae3.json` | `AC1709ED7AE3C409F965516B6B936C20A417443DB9AA284E3F22673C5AFB03A8` | 2,876 registros (Sep 2026) |
| `dmc/330007/versions/..._10_0545e67b8305.json` | `0545E67B830501610D0956C0FC65C58F3FB751CF30BF9C5F36E3957BF96C86E7` | 1,447 registros (Oct 2026) |
| `dmc/330007/CURRENT.json` | `8784EC573FF465DF1B1F9F896163493FE8D0587241B5BE813222C7F4394FC219` | 4,323 registros totales |

### Batería de Seguridad y Resiliencia SAPI-71
* `tests/test_adv05_characterization.py`: **5/5 PASS** (orden estricto de append a histórico antes de puntero atómico).
* `tests/test_remediation_red_defects.py`: **9/9 PASS** (remediaciones B1, B2 y B3: sidecar validado, fronteras UTF-8 y no reclasificación de red).
* `tests/test_refresh_adversarial.py`: **11/11 PASS** (ADV-01 a ADV-06: fallos parciales, locks corruptos, integridad sha256).

---

## 3. Demostración de Persistencia PostGIS — Cierre SAPI-43

Bajo autorización explícita del operador y con verificación estricta de hashes, se trasladaron las entradas operacionales validadas al entorno de inferencia, ejecutando la primera corrida del Modelo D con persistencia write-through real en PostgreSQL/PostGIS.

### Metadatos de la Ejecución Persistida
* **ID de Ejecución:** `1`
* **Timestamp de Evaluación (`forecast_time`):** `2026-10-16 00:00:00+00`
* **Versión de Modelo:** `prototype_model_d_v1`
* **Fingerprint de Entradas:** `06afceb4915d4ab7f591d9acce67958cbb711829a467f9a98a92972f3cb37f54`
* **Origen de FIRMS:** `current`
* **Semántica del Score:** `relative_rank`
* **Validación Científica:** `false` (F4 FAIL)
* **Horas de Horizonte:** `6`
* **Fecha/Hora de Persistencia (`created_at`):** `2026-10-16 02:30:25.03208+00`

### Prueba de Idempotencia
Se repitió la solicitud con los mismos insumos exactamente a las `02:30:39Z`. Resultado observado:
* **Status HTTP:** `200 OK`
* **Latencia de Replay:** `1.805 s`
* **Conteo en `ejecuciones` tras replay:** `1` (cero duplicados)
* **Conteo en `predicciones_celda` tras replay:** `50` (cero duplicados)

### Tabla Completa de las 50 Celdas Persistidas en PostGIS (`latest_ranking.sql`)
Consulta ejecutada directamente en el contenedor PostGIS:

```sql
SELECT p.rank, p.display_rank, p.cell_id, ROUND(p.score::numeric, 6) AS score,
       p.tie_group_size, e.model_version, e.firms_origin,
       SUBSTRING(e.inputs_fingerprint, 1, 16) || '...' AS inputs_fp
FROM predicciones_celda p
JOIN ejecuciones e ON e.id = p.ejecucion_id
ORDER BY p.rank ASC;
```

```
 rank | display_rank | cell_id |  score   | tie_group_size |    model_version     | firms_origin |      inputs_fp
------+--------------+---------+----------+----------------+----------------------+--------------+---------------------
    1 |            1 | VP-038  | 0.093474 |              1 | prototype_model_d_v1 | current      | 06afceb4915d4ab7...
    2 |            2 | VP-028  | 0.091978 |              1 | prototype_model_d_v1 | current      | 06afceb4915d4ab7...
    3 |            3 | VP-003  | 0.088303 |             48 | prototype_model_d_v1 | current      | 06afceb4915d4ab7...
    4 |            3 | VP-004  | 0.088303 |             48 | prototype_model_d_v1 | current      | 06afceb4915d4ab7...
    5 |            3 | VP-005  | 0.088303 |             48 | prototype_model_d_v1 | current      | 06afceb4915d4ab7...
    6 |            3 | VP-006  | 0.088303 |             48 | prototype_model_d_v1 | current      | 06afceb4915d4ab7...
    7 |            3 | VP-007  | 0.088303 |             48 | prototype_model_d_v1 | current      | 06afceb4915d4ab7...
    8 |            3 | VP-008  | 0.088303 |             48 | prototype_model_d_v1 | current      | 06afceb4915d4ab7...
    9 |            3 | VP-009  | 0.088303 |             48 | prototype_model_d_v1 | current      | 06afceb4915d4ab7...
   10 |            3 | VP-010  | 0.088303 |             48 | prototype_model_d_v1 | current      | 06afceb4915d4ab7...
   11 |            3 | VP-011  | 0.088303 |             48 | prototype_model_d_v1 | current      | 06afceb4915d4ab7...
   12 |            3 | VP-012  | 0.088303 |             48 | prototype_model_d_v1 | current      | 06afceb4915d4ab7...
   13 |            3 | VP-013  | 0.088303 |             48 | prototype_model_d_v1 | current      | 06afceb4915d4ab7...
   14 |            3 | VP-014  | 0.088303 |             48 | prototype_model_d_v1 | current      | 06afceb4915d4ab7...
   15 |            3 | VP-015  | 0.088303 |             48 | prototype_model_d_v1 | current      | 06afceb4915d4ab7...
   16 |            3 | VP-016  | 0.088303 |             48 | prototype_model_d_v1 | current      | 06afceb4915d4ab7...
   17 |            3 | VP-001  | 0.088303 |             48 | prototype_model_d_v1 | current      | 06afceb4915d4ab7...
   18 |            3 | VP-002  | 0.088303 |             48 | prototype_model_d_v1 | current      | 06afceb4915d4ab7...
   19 |            3 | VP-018  | 0.088303 |             48 | prototype_model_d_v1 | current      | 06afceb4915d4ab7...
   20 |            3 | VP-017  | 0.088303 |             48 | prototype_model_d_v1 | current      | 06afceb4915d4ab7...
   21 |            3 | VP-021  | 0.088303 |             48 | prototype_model_d_v1 | current      | 06afceb4915d4ab7...
   22 |            3 | VP-019  | 0.088303 |             48 | prototype_model_d_v1 | current      | 06afceb4915d4ab7...
   23 |            3 | VP-023  | 0.088303 |             48 | prototype_model_d_v1 | current      | 06afceb4915d4ab7...
   24 |            3 | VP-024  | 0.088303 |             48 | prototype_model_d_v1 | current      | 06afceb4915d4ab7...
   25 |            3 | VP-025  | 0.088303 |             48 | prototype_model_d_v1 | current      | 06afceb4915d4ab7...
   26 |            3 | VP-020  | 0.088303 |             48 | prototype_model_d_v1 | current      | 06afceb4915d4ab7...
   27 |            3 | VP-026  | 0.088303 |             48 | prototype_model_d_v1 | current      | 06afceb4915d4ab7...
   28 |            3 | VP-027  | 0.088303 |             48 | prototype_model_d_v1 | current      | 06afceb4915d4ab7...
   29 |            3 | VP-029  | 0.088303 |             48 | prototype_model_d_v1 | current      | 06afceb4915d4ab7...
   30 |            3 | VP-030  | 0.088303 |             48 | prototype_model_d_v1 | current      | 06afceb4915d4ab7...
   31 |            3 | VP-031  | 0.088303 |             48 | prototype_model_d_v1 | current      | 06afceb4915d4ab7...
   32 |            3 | VP-032  | 0.088303 |             48 | prototype_model_d_v1 | current      | 06afceb4915d4ab7...
   33 |            3 | VP-033  | 0.088303 |             48 | prototype_model_d_v1 | current      | 06afceb4915d4ab7...
   34 |            3 | VP-022  | 0.088303 |             48 | prototype_model_d_v1 | current      | 06afceb4915d4ab7...
   35 |            3 | VP-034  | 0.088303 |             48 | prototype_model_d_v1 | current      | 06afceb4915d4ab7...
   36 |            3 | VP-035  | 0.088303 |             48 | prototype_model_d_v1 | current      | 06afceb4915d4ab7...
   37 |            3 | VP-036  | 0.088303 |             48 | prototype_model_d_v1 | current      | 06afceb4915d4ab7...
   38 |            3 | VP-037  | 0.088303 |             48 | prototype_model_d_v1 | current      | 06afceb4915d4ab7...
   39 |            3 | VP-039  | 0.088303 |             48 | prototype_model_d_v1 | current      | 06afceb4915d4ab7...
   40 |            3 | VP-040  | 0.088303 |             48 | prototype_model_d_v1 | current      | 06afceb4915d4ab7...
   41 |            3 | VP-041  | 0.088303 |             48 | prototype_model_d_v1 | current      | 06afceb4915d4ab7...
   42 |            3 | VP-042  | 0.088303 |             48 | prototype_model_d_v1 | current      | 06afceb4915d4ab7...
   43 |            3 | VP-043  | 0.088303 |             48 | prototype_model_d_v1 | current      | 06afceb4915d4ab7...
   44 |            3 | VP-044  | 0.088303 |             48 | prototype_model_d_v1 | current      | 06afceb4915d4ab7...
   45 |            3 | VP-045  | 0.088303 |             48 | prototype_model_d_v1 | current      | 06afceb4915d4ab7...
   46 |            3 | VP-046  | 0.088303 |             48 | prototype_model_d_v1 | current      | 06afceb4915d4ab7...
   47 |            3 | VP-047  | 0.088303 |             48 | prototype_model_d_v1 | current      | 06afceb4915d4ab7...
   48 |            3 | VP-048  | 0.088303 |             48 | prototype_model_d_v1 | current      | 06afceb4915d4ab7...
   49 |            3 | VP-049  | 0.088303 |             48 | prototype_model_d_v1 | current      | 06afceb4915d4ab7...
   50 |            3 | VP-050  | 0.088303 |             48 | prototype_model_d_v1 | current      | 06afceb4915d4ab7...
(50 rows)
```

---

## 4. Prueba E2E Real y Resultados de Navegador — Cierre SAPI-66

Se levantó el proyecto Docker Compose aislado (`sapi-sprint2-closeout`) en puertos dedicados y se ejecutó la suite de medición real en navegador Microsoft Edge (`scripts/measure_browser_e2e_d21.py`).

### Resultados de Rendimiento en Navegador (Directiva 26 / CA4)
| Run ID | Escenario de Prueba | Latencia Medida | Verificación de Integridad | Resultado |
| :--- | :--- | :---: | :--- | :---: |
| **RUN-01** | Primera Carga en Frío (Cold Navigation) | **897.4 ms** | Celda VP visible, score presente, prioridad #1, 50 celdas contrato/DOM | **PASS** |
| **RUN-02** | Actualización por Clic (`Actualizar ranking`) | **1,952.5 ms** | Timestamp verificado (`02:33:25` $\rightarrow$ `02:36:37`), 50 celdas intactas | **PASS** |
| **RUN-03** | Recarga con Caché (Browser Warm Refresh) | **563.9 ms** | Ranking visible desde backend/caché, integridad validada | **PASS** |
| **RUN-04** | Expansión de Tabla Completa (`st.dataframe`) | **582.6 ms** | Grid Glide virtualizado abierto, 50 celdas respaldadas | **PASS** |
| **NEG-01** | Prueba Negativa de DOM Estancado | N/A | TimeoutError confirmado ante DOM sin cambio comprobable | **PASS** |

### Artefactos Generados en `artifacts/hito2/closeout_e2e/`:
* `ca4_browser_cold.png` (Screenshot primera carga en frío)
* `ca4_browser_update.png` (Screenshot post-clic con nuevo timestamp)
* `ca4_browser_cached.png` (Screenshot recarga con caché)
* `ca4_browser_table_expanded.png` (Screenshot tabla completa expandida)
* `timings_browser.csv` (Registro exhaustivo de latencias y metadatos)

---

## 5. Pruebas Negativas y Manejo de Errores

Se verificó el comportamiento seguro (Fail-Closed) ante condiciones adversas:
1. **Petición con fecha inválida:** `POST /predict` con `"not-a-date"` $\longrightarrow$ `HTTP 422` (`error_type: "invalid_request"`).
2. **Petición con campo no contractual:** `POST /predict` con `"extra_field": 123` $\longrightarrow$ `HTTP 422` (`error_type: "invalid_request"`).
3. **Petición con fecha futura:** `POST /predict` para año 2099 $\longrightarrow$ `HTTP 503` (`error_type: "prototype_unavailable"`).
4. **Endpoint inexistente:** `GET /api/v1/invalid` $\longrightarrow$ `HTTP 404 Not Found`.
5. **Rechazo de Procedencia No Autorizada:** En `test_f1_ca8_operational_overlay_dynamic.py`, el backend configurado con `SAPI_PERSISTENCE_ALLOWED_FIRMS_ORIGINS=current` rechazó orígenes `baseline` y `reproducibility` con `HTTP 500` (`internal_error`) y cero escrituras en PostGIS.

---

## 6. Cambios de Código Introducidos y Justificación

| Archivo Modificado | Tipo de Cambio | Justificación Técnica |
| :--- | :---: | :--- |
| `scripts/measure_browser_e2e_d21.py` | Corrección QA | Generalización de patrones de celda en el arnés de prueba de navegador (`re.search(r"VP-\d{3}", ...)` y `txt.lower()`), permitiendo validar tanto la corrida reproducible (donde la celda #1 es `VP-001`) como la corrida operacional real (donde la celda #1 es `VP-038`), sin alterar contratos ni relajar exigencias temporales de la Directiva 28. |

---

## 7. Instrucciones Reproducibles de Demostración Local

Para levantar y verificar el vertical slice completo localmente:

### Paso 1: Configurar Variables de Entorno y Puertos
```powershell
$env:SAPI_DB_USER = "sapi"
$env:SAPI_DB_PASSWORD = "<definir_password_segura>"
$env:SAPI_DB_NAME = "sapi_v2"
$env:SAPI_DB_PORT = "15442"
$env:SAPI_ML_PORT = "18012"
$env:SAPI_BACKEND_PORT = "18092"
$env:SAPI_WEB_PORT = "18504"
```

### Paso 2: Iniciar Stack con Docker Compose
```powershell
docker compose -p sapi-sprint2-closeout `
  -f docker-compose.yml `
  -f docker-compose.operational.yml `
  --profile presentation up -d
```

### Paso 3: Verificar Salud de Servicios
```powershell
# Comprobar estado de contenedores
docker compose -p sapi-sprint2-closeout ps

# Consultar endpoint público del backend
Invoke-RestMethod -Uri "http://127.0.0.1:18092/api/v1/ranking"
```

### Paso 4: Consultar las 50 Filas Persistidas en PostGIS
```powershell
Get-Content "db\queries\latest_ranking.sql" | docker exec -i sapi-sprint2-closeout-db-v2-1 psql -U sapi -d sapi_v2
```

### Paso 5: Detener el Stack Preservando Volúmenes
```powershell
docker compose -p sapi-sprint2-closeout `
  -f docker-compose.yml `
  -f docker-compose.operational.yml down
```

---

## 8. Riesgos y Limitaciones Científicas

> [!WARNING]
> **RESTRICCIÓN CIENTÍFICA NO NEGOCIABLE (F4 FAIL):**
> * El Modelo D (`HistGradientBoostingClassifier`) produce un **ranking exploratorio relativo** entre las 50 celdas para priorización de inspección, **NO probabilidades calibradas de ocurrencia de incendios**.
> * La métrica `scientific_model_validation` es explícitamente `false` en todos los contratos y registros persistidos.
> * No se debe autorizar el paso a producción operativa en terreno mientras no se complete una validación temporal exhaustiva con datos multianuales independientes.

---

## 9. Recomendación GO / NO-GO

* **ENTREGA ACADÉMICA / EVALUACIÓN HITO 2:** **GO DEFINITIVO.**
  * Vertical slice de 4 capas funcionando de manera integrada y reproducible.
  * SAPI-71, SAPI-43 y SAPI-66 demostrados con evidencia reproducible.
  * Tiempos de respuesta de UI < 2.0 s y persistencia espacial en PostGIS validada.
* **DESPLIEGUE EN PRODUCCIÓN REAL:** **NO-GO ESTRICTO.**
  * El modelo matemático requiere validación científica formal previa (Criterio F4).

---

## 10. Propuestas de Comentarios para Cierre de Issues en Jira

### Comentario para SAPI-71 (Refresh FIRMS / DMC):
> **RESOLUCIÓN TÉCNICA VERIFICADA — SAPI-71 [PASS]**
> Se valida el mecanismo de refresco atómico, versionado e idempotente de datos NASA FIRMS y DMC.
> Evidencias confirmadas:
> 1. Suite offline adversarial `tests/sapi71_offline_runner.py` (25/25 pruebas PASS: ADV-01..ADV-06, B1, B2, B3, ADV-05).
> 2. Autorización B completada con publicación atómica de FIRMS CURRENT v3 (`F7307F69...`) y DMC CURRENT (`8784EC57...`) para septiembre y octubre 2026.
> 3. Integridad garantizada: locks basados en archivo, sidecar validado y trazabilidad de punteros JSON.

### Comentario para SAPI-43 (Persistencia Primera Corrida en PostGIS):
> **RESOLUCIÓN TÉCNICA VERIFICADA — SAPI-43 [PASS]**
> Se demostró la ejecución operacional del Modelo D con persistencia write-through real en PostgreSQL 15 / PostGIS 3.4 a través de Spring Boot JDBC:
> 1. Ejecución ID=1 registrada con `model_version: prototype_model_d_v1`, `inputs_fingerprint: 06afceb4915d4ab7...` y `firms_origin: current`.
> 2. Exactamente 50 celdas persistidas en `predicciones_celda` ordenadas por `rank ASC` (VP-038 en rango #1).
> 3. Idempotencia validada: la repetición con idéntico fingerprint no duplicó filas ni alteró los registros existentes. Consulta `latest_ranking.sql` validada.

### Comentario para SAPI-66 (Prueba E2E Local Reproducible):
> **RESOLUCIÓN TÉCNICA VERIFICADA — SAPI-66 [PASS]**
> Se ejecutó exitosamente el arnés E2E en navegador Microsoft Edge (`measure_browser_e2e_d21.py`) sobre Docker Compose v2 aislado:
> 1. Cadena completa validada: Streamlit (18504) $\rightarrow$ Spring Boot (18092) $\rightarrow$ FastAPI (18012) $\rightarrow$ PostGIS (15442).
> 2. Latencias observadas: Cold start 897.4 ms, Actualización por clic 1,952.5 ms, Recarga caché 563.9 ms.
> 3. Capturas de pantalla, métricas en `timings_browser.csv` y prueba negativa de rechazo de DOM estancado registradas en `artifacts/hito2/closeout_e2e/`.

# Runbook de Demostraci?n Funcional ? Hito 2 (Sprint 2)
## Sistema de Alerta Temprana y Priorizaci?n de Incendios Forestales (S.A.P.I.)

**Prop?sito:** Gu?a de ejecuci?n en vivo, paso a paso, para la defensa t?cnica del Hito 2 (7 minutos de demostraci?n operativa ante la comisi?n evaluadora).  
**Candidato Consolidado:** Commit `8010e4421cf91b80e6dc66d732ef6e98dfd1e4d8` (Base F7: `51ec3c06b67959d3daad6349c962a1be643906b4`).  
**Fecha de Emisi?n:** 24 de octubre de 2026.

---

## 1. Regla de Oro de Integridad Operacional

> [!IMPORTANT]
> **PROHIBICI?N ESTRICTA:** Bajo ninguna circunstancia se deben presentar los datos hist?ricos como si fueran datos meteorol?gicos o satelitales en vivo.  
> Los datos mostrados en la demo provienen de snapshots congelados del modo reproducibilidad (`firms_origin = 'reproducibility'`). Esta delimitaci?n debe declararse expl?citamente al inicio de la demostraci?n.

---

## 2. Par?metros y Endpoints de la Demostraci?n

| Servicio | Contenedor Docker | Puerto Local | URL de Acceso | Endpoint de Salud |
| :--- | :--- | :---: | :--- | :--- |
| **Streamlit UI** | `sapi-web-v2` | `8501` | `http://localhost:8501` | `http://localhost:8501/_stcore/health` |
| **Spring Boot Backend** | `sapi-backend-v2` | `8080` | `http://localhost:8080/api/v1/ranking` | `http://localhost:8080/actuator/health` |
| **FastAPI ML API** | `sapi-ml-api-v2` | `8000` | `http://localhost:8000/docs` | `http://localhost:8000/health` |
| **PostgreSQL / PostGIS** | `sapi-db-v2` | `5432` | `localhost:5432` (db: `sapi_v2`, user: `sapi`) | `pg_isready -h localhost -p 5432` |

---

## 3. Fase 1: Arranque y Orquestaci?n (Minuto 10?11)

### Opci?n A ? Script de Bootstrap Oficial (Recomendada / Jira #10156)
Este script orquesta el orden estricto de arranque (Base de datos -> Flyway -> ML -> Backend -> Frontend) con sondeo de healthchecks y verificaci?n de clave de base de datos sin colisiones:
```powershell
# En PowerShell (desde la ra?z del repositorio):
python scripts/bootstrap_compose_v2.py
```

### Opci?n B ? Docker Compose con Perfil de Presentaci?n
```powershell
docker compose --profile presentation up -d
```

### Verificaci?n de Estado
```powershell
docker compose ps
```
**Criterio de ?xito:** Los cuatro contenedores deben figurar en estado `Up (healthy)`.

---

## 4. Fase 2: Navegaci?n de Pantalla y Consumo REST (Minuto 11?13)

1. **Abrir Navegador:** Ir a `http://localhost:8501`.
2. **Explicar la Interfaz a la Comisi?n:**
   - **Badge de Integridad Cient?fica:** Se?alar el indicador `"Sem?ntica: relative_rank (no calibrado)"` en la cabecera.
   - **Mapa de Celdas:** Mostrar las 50 celdas poligonales rectangulares (`VP-001` a `VP-050`) del corredor Vi?a del Mar ? Quilpu? ? Villa Alemana coloreadas seg?n su quintil de riesgo relativo.
   - **Tabla Interactiva:** Seleccionar una celda de alta prioridad (ej. `VP-038` o `VP-047`) y mostrar que la selecci?n se refleja bidireccionalmente en el mapa.
   - **Declarar Desacoplamiento:** Destacar que Streamlit no entrena ni infiere; act?a como cliente puro del backend Spring Boot (`GET /api/v1/ranking`).

---

## 5. Fase 3: Medici?n de Latencia y Resiliencia Fail-Closed (Minuto 13?15)

### A. Prueba de Actualizaci?n Interactiva (CA4)
1. Hacer clic en el bot?n **"Actualizar ranking"** en la interfaz.
2. Observar el refresco instant?neo del DOM.
3. Declarar el resultado de ingenier?a: Latencias operacionales certificadas en el arn?s R2 (`tests/e2e/test_full_stack_timings.py`):
     - **Cold (Carga inicial en fr?o):** `6.867,90 ms`
     - **Update (Actualizaci?n interactiva):** `3.723,47 ms`
     - **Cached (Lectura en caliente):** `424,06 ms`
     *(Dato real reproducido en `artifacts/oc-e2e-20261024/timings/ca4-timings.json`).*

### B. Demostraci?n de Pol?tica Fail-Closed ante Ca?da de ML (Entorno Seguro)
Para garantizar la estabilidad de la presentaci?n y no interrumpir los contenedores compartidos, la demostraci?n de resiliencia fail-closed se apoya en evidencias pre-certificadas o en un stack aislado:

1. **Procedimiento Principal (Evidencia Certificada R2):**
   - Proyectar la captura de contingencia: `artifacts/oc-e2e-20261024/negative/ui-backend-down.png`.
   - Mostrar el payload de error estructurado `artifacts/oc-e2e-20261024/negative/ml-unavailable.json`.
   - Explicar el comportamiento auditado: Spring Boot intercepta la indisponibilidad de `ml-api` y degrada de forma controlada a `HTTP 503 / 504`, impidiendo que Streamlit colapse o invente scores aleatorios.

2. **Procedimiento Opcional en Vivo (Exclusivo en Stack Aislado):**
   - Si la comisi?n exige una detenci?n en vivo, **nunca detener el stack principal de la demo**. Ejecutar sobre el arn?s aislado de pruebas R2 en subred privada:
     ```powershell
     # Terminal aislada:
     docker compose -f tests/e2e/docker-compose.e2e-oc.yml stop ml-api
     python -m pytest tests/e2e/test_full_stack_negative.py -k test_ml_service_down_returns_503
     docker compose -f tests/e2e/docker-compose.e2e-oc.yml start ml-api
     ```

---

## 6. Fase 4: Auditor?a de Persistencia e Idempotencia en PostGIS (Minuto 15?17)

Demostrar en vivo que las ejecuciones quedan registradas con integridad transaccional:

1. Conectarse a la base de datos PostgreSQL:
   ```powershell
   docker exec -it sapi-db-v2 psql -U sapi -d sapi_v2 -c "SELECT id, forecast_time, model_version, firms_origin, scientific_model_validation FROM ejecuciones ORDER BY id DESC LIMIT 3;"
   ```
2. **Puntos Clave a Mostrar a la Comisi?n:**
   - La columna `scientific_model_validation` es `false` (respaldada por constraint `CHECK`).
   - La columna `firms_origin` tiene el valor auditado `'reproducibility'`.
   - La clave natural `UNIQUE (forecast_time, model_version, inputs_fingerprint)` evita registros duplicados ante clics repetidos.

---

## 7. Plan de Contingencia T?cnico

| Escenario de Falla | Causa Probable | Acci?n de Mitigaci?n Inmediata | Respaldo Documental |
| :--- | :--- | :--- | :--- |
| **Colisi?n de puertos (8080/8501 ocupados)** | Proceso hu?rfano en el host | Ejecutar con puertos alternativos: `python scripts/bootstrap_compose_v2.py --web-port 18501 --backend-port 18080` | Script ya preparado para puertos no est?ndar. |
| **Docker Desktop no responde** | Saturaci?n de memoria en Windows | Levantar stack con subred aislada: `docker compose -f tests/e2e/docker-compose.e2e-oc.yml up -d` | Arn?s R2 probado y certificado. |
| **Streamlit pierde conexi?n websocket** | Recarga de p?gina durante demo | Presionar `F5`. Si persiste, proyectar las evidencias fotogr?ficas pre-certificadas. | `artifacts/oc-e2e-20261024/screenshots/streamlit-ranking.png` |
| **Pregunta sobre datos en tiempo real** | Consulta de la comisi?n sobre FIRMS hoy | Explicar con honestidad que el runbook `docs/ops/FIRST-CONTROLLED-REFRESH.md` est? probado, pero requiere llaves oficiales y autorizaci?n humana de terreno. | Secci?n 12 de `INFORME_HITO2_FINAL.md`. |

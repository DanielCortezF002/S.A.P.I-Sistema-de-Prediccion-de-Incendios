# Resumen Ejecutivo de Evidencias E2E R2 y Resultados de Integraci?n Continua (CI)
## S.A.P.I. ? Sprint 2 / Hito 2

**Candidato Consolidado:** Commit `8010e4421cf91b80e6dc66d732ef6e98dfd1e4d8` (Base F7: `51ec3c06b67959d3daad6349c962a1be643906b4`).  
**Fecha:** 24 de octubre de 2026.

---

## 1. Certificaci?n de Evidencias E2E R2
* **Ubicaci?n en Repositorio:** `artifacts/oc-e2e-20261024/`
* **Total de Archivos Auditados:** 91 artefactos
* **Resultado de Verificaci?n Criptogr?fica:** **91 de 91 hashes SHA-256 coinciden exactamente** con `artifacts/oc-e2e-20261024/SHA256SUMS.txt`.
* **Arneses E2E Incluidos:**
  - `tests/e2e/docker-compose.e2e-oc.yml` (Subred IPAM aislada `10.99.99.0/24`).
  - `tests/e2e/test_full_stack_contracts.py` (Validaci?n de esquemas HTTP/JSON).
  - `tests/e2e/test_full_stack_timings.py` (Medici?n de latencia interactiva CA4: 1709.5 ms).
  - `tests/e2e/test_full_stack_negative.py` (Pruebas fail-closed ante ca?da de ML o DB).
  - `tests/e2e/test_full_stack_browser.py` (Validaci?n E2E sobre navegador real).
* **Documentaci?n y Privacidad:**
  - `artifacts/oc-e2e-20261024/PROVENANCE.md` (Trazabilidad y cadena de custodia).
  - `artifacts/oc-e2e-20261024/REDACTION-NOTICE.md` (Sanitizaci?n rigurosa de IPs y usuarios locales).
  - `reports/OC-E2E-20261024-CERTIFICACION.md` (Informe exhaustivo de certificaci?n E2E).

---

## 2. Resultados de Pruebas Automatizadas Locales
* **Python Suites (pytest):**
  - **102 pruebas PASSED, 1 SKIPPED, 0 FAILED** (Tiempo: 141.28 s).
  - Cobertura de contratos OpenAPI, arquitectura, inputs de scoring, API ML y Docker Compose V2.
* **Java Backend (Spring Boot 3 / Surefire):**
  - **137 pruebas PASSED, 0 FAILURES, 0 ERRORS, 0 SKIPPED** (Tiempo: 32.38 s / BUILD SUCCESS).
  - Cobertura de ranking, validadores, pol?ticas de origen FIRMS, persistencia PostGIS y degradaci?n fail-closed (503/504).
* **Total de Pruebas Verificadas en Staging:** **239 pruebas automatizadas pasando al 100%**.

---

## 3. Estado de Workflows de GitHub Actions
Las tres Pull Requests previas (#39, #40 y #42) cuentan con certificaci?n **6/6 SUCCESS** en todos sus workflows remotos:
1. `freeze`: PASS.
2. `python`: PASS.
3. `backend-unit`: PASS.
4. `sql-migration-validation`: PASS.
5. `flyway-integration`: PASS.
6. `container-smoke`: PASS.

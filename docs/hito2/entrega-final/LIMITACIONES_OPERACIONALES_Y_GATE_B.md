# Declaraci?n de Limitaciones Operacionales y Dictamen Gate B
## S.A.P.I. ? Sprint 2 / Hito 2

**Candidato Consolidado:** Commit `8010e4421cf91b80e6dc66d732ef6e98dfd1e4d8` (Base F7: `51ec3c06b67959d3daad6349c962a1be643906b4`).  
**Fecha:** 24 de octubre de 2026.

---

## 1. Principio ?tico Fundamental de Ingenier?a
S.A.P.I. adopta un principio ?tico estricto: **separar la madurez de la ingenier?a de software alcanzada en el Hito 2 de la certificaci?n de seguridad para uso en emergencias reales**.  
En un sistema orientado a la toma de decisiones sobre incendios forestales, la responsabilidad civil e institucional exige no promover a producci?n un modelo predictivo que no cuente con calibraci?n emp?rica biof?sica en terreno.

---

## 2. Estado Normativo de Gate B
* **Dictamen Vigente:** **ESTRICTAMENTE NO GO (v5)**.
* **Justificaci?n Cient?fica:**
  - `score_semantics = relative_rank`: El modelo produce un ordenamiento heur?stico relativo de 50 celdas, no una probabilidad calibrada de ignici?n.
  - `scientific_model_validation = false`: Constraint a nivel de base de datos PostgreSQL que impide persistir un score como probabilidad v?lida para despacho t?ctico de brigadas.
  - Ninguna prueba de software, refactorizaci?n ni avance de cobertura sustituye la validaci?n cient?fica en campo.

---

## 3. Inventario de Limitaciones Operacionales Reales

| Identificador | Componente | Limitaci?n Real Documentada | Estado / Tratamiento para Hito 2 |
| :--- | :--- | :--- | :--- |
| **SAPI-71 / 43** | Pipeline Diario | Intento 2 de refresco controlado est? "NOT STARTED". Requiere llaves de API vivas (NASA FIRMS / DMC) y operador humano. | **Condicionado a Operaci?n en Producci?n**. No penaliza el software de Hito 2 (probado con fixtures sint?ticos). |
| **SAPI-66 CA5** | Orquestaci?n | El comando literal `docker compose up` omite `web-v2` por la presencia de `profiles: ["presentation"]`. | **Mitigado proceduralmente** mediante script oficial `scripts/bootstrap_compose_v2.py` (Jira #10156). Pendiente de pronunciamiento acad?mico. |
| **SAPI-67** | Infraestructura | ADR-011 para proveedor cloud permanece como propuesto sin firma formal. | **Alineado a Presupuesto $0 CLP**. Se mantiene en Docker local sin incurrir en costos cloud. |
| **ADV-05** | Atomicidad IO | Defecto adversarial de atomicidad en publicaci?n de historial bajo fallo de IO. | **Abierto en Change-Control**. Caracterizado con pruebas; pendiente de decisi?n arquitect?nica (compensaci?n vs reconciliaci?n). |

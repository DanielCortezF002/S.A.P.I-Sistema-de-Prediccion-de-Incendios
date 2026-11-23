# Reporte de seguridad del Sprint 3 (A6), SAPI-89

Fecha: 22-11-2026. Base: `main` en `9e70867`. Rama: `feat/SAPI-89-escaneo-seguridad`. Se ejecutó en local con Python 3.13; en CI corre con el workflow `.github/workflows/security.yml`.

## Escenario de calidad (A2, ISO/IEC 25010: seguridad)

| Parte | RNF-06 Seguridad |
|---|---|
| Fuente | Desarrollador o dependencia de terceros |
| Estímulo | Se versiona un secreto o se usa una dependencia con vulnerabilidad conocida |
| Entorno | Repositorio, en cada push y PR |
| Respuesta | El escaneo falla y el PR queda bloqueado mientras el hallazgo no se corrija o no tenga una aceptación escrita |
| Medida de respuesta | 0 secretos nuevos fuera de la línea base auditada; 0 vulnerabilidades sin aceptación escrita; 100 % de los casos negativos detectados |

## Resultados

| Control | Herramienta | Resultado | Evidencia |
|---|---|---|---|
| Secretos en archivos versionados | detect-secrets 1.5.0 + `scripts/secret_scan.py` | PASS: 0 secretos nuevos en 956 archivos versionados | `.secrets.baseline` y job `secrets` |
| Vulnerabilidades en dependencias Python | pip-audit 2.10.1 + `scripts/dependency_audit.py` | PASS: 133 paquetes y 0 vulnerabilidades sin aceptación. 42 aceptadas, todas de pillow (ver hallazgos) | `docs/calidad/pip_audit_20261122.json` y job `dependencies` |
| Caso negativo de secretos | `tests/test_secret_scan.py::test_caso_negativo_secreto_nuevo_hace_fallar` | PASS: una clave con formato AWS en un árbol git hace fallar el escaneo | pytest |
| Caso negativo de dependencias | `tests/test_secret_scan.py::test_caso_negativo_vulnerabilidad_sin_aceptacion_falla` | PASS | pytest |

## Hallazgos

| ID | Hallazgo | Severidad | Decisión | Riesgo que queda |
|---|---|---|---|---|
| SEC-01 | black 26.5.1 con CVE-2026-114134. Se instala en las imágenes `ml-api`, `n8n-bridge` y `analytics`, porque esas imágenes instalan `requirements-dev.txt` | Sin nivel informado por pip-audit | **Corregido**: actualizado a black 26.10.1. Se verificó que no cambia el formato del alcance de lint v2 | Ninguno |
| SEC-02 | pillow 12.3.0 con 42 avisos (el primero es PYSEC-2026-4326); la versión corregida es la 13.0.0 | Sin nivel informado por pip-audit | **Aceptado con justificación**: streamlit 1.63.0 exige `pillow<13` y `requirements.txt` está congelado. La app no abre imágenes de usuarios: no hay `file_uploader` ni uso propio de PIL | Aprovechable solo con imágenes maliciosas que hoy la app no recibe. Se elimina al subir streamlit, en un ciclo posterior |
| SEC-03 | `src/config.py:17` trae por defecto la URL de la base local con la contraseña `sapi_secret` | Media | **Aceptado con plan**: es la credencial de la base PostgreSQL de desarrollo en `localhost`, no la de un servicio desplegado. Docker Compose usa variables de entorno. Plan: que falle cerrado si falta `DATABASE_URL` | Alguien podría reutilizar la contraseña por defecto en un despliegue real |
| SEC-04 | 412 falsos positivos de detect-secrets: hashes SHA-256 de evidencias y de commits citados en avisos de pip-audit, credenciales sintéticas de pruebas (marcadas `NOT-REAL`) y placeholders de documentación | Ninguna | En la línea base. El 22-11-2026 se revisaron uno por uno los 34 que no son hexadecimales; los hexadecimales son hashes dentro de archivos de evidencia y se revisaron por archivo | Una línea base desactualizada podría ocultar un secreto nuevo en un archivo ya listado. detect-secrets compara por hash de la línea, así que un valor nuevo igual se detecta |

0 hallazgos críticos o altos abiertos sin justificación. pip-audit no informa severidad CVSS, así que SEC-01 y SEC-02 se trataron sin asumir que eran bajos.

## Limitaciones

- **Imágenes Docker sin escanear.** No se pudo usar Trivy en este entorno, porque no se permitió descargar el binario. Para cubrir las imágenes y las dependencias Maven del backend, hay que correr en la máquina de Daniel:

  ```
  trivy image sapi-v2-ml-api
  trivy fs services/backend
  ```

  Los reportes van a esta carpeta.
- **Historial de git sin escanear.** El escaneo cubre los archivos versionados, no el historial completo.
- **El PR todavía no se bloquea.** Para que los jobs `secrets` y `dependencies` bloqueen el PR, deben marcarse como obligatorios en la protección de `main`. Esa configuración la hace Daniel en GitHub.

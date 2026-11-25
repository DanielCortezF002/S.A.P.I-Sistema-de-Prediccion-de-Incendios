## Trivy (imágenes)

### sapi-h3-518c0b5-backend

SO base: ubuntu 26.04. Escaneo: 2026-11-25T04:34:37Z.

| Objetivo | Clase | CRITICAL | HIGH | MEDIUM | LOW | UNKNOWN | Total (únicas) |
|---|---|---|---|---|---|---|---|
| sapi-h3-518c0b5-backend:latest (ubuntu 26.04) | os-pkgs | 0 | 0 | 58 | 12 | 0 | 70 |
| Java | lang-pkgs | 4 | 5 | 2 | 0 | 0 | 11 |
| pebble | lang-pkgs | 0 | 0 | 1 | 0 | 0 | 1 |

CRITICAL/HIGH con versión corregida publicada (paquete, instalada -> corregida):

- `org.apache.tomcat.embed:tomcat-embed-core` 11.0.24 -> 11.0.25 (CRITICAL)
- `tools.jackson.core:jackson-core` 3.1.5 -> 3.1.7 (HIGH)
- `tools.jackson.core:jackson-databind` 3.1.5 -> 3.1.7 (HIGH)
- `tools.jackson.core:jackson-databind` 3.1.5 -> 3.2.2 (HIGH)

### sapi-h3-518c0b5-ml-api

SO base: debian 13.8. Escaneo: 2026-11-25T04:37:05Z.

| Objetivo | Clase | CRITICAL | HIGH | MEDIUM | LOW | UNKNOWN | Total (únicas) |
|---|---|---|---|---|---|---|---|
| sapi-h3-518c0b5-ml-api:latest (debian 13.8) | os-pkgs | 2 | 162 | 656 | 1606 | 122 | 2548 |
| Node.js | lang-pkgs | 0 | 0 | 0 | 0 | 0 | 0 |
| Python | lang-pkgs | 5 | 30 | 16 | 1 | 0 | 52 |

CRITICAL/HIGH con versión corregida publicada (paquete, instalada -> corregida):

- `black` 26.5.1 -> 26.10.1 (HIGH)
- `msgpack` 1.1.2 -> 1.2.1 (HIGH)
- `msgpack` 1.1.2 -> 1.2.3 (HIGH)
- `pillow` 12.3.0 -> 13.0.0 (CRITICAL/HIGH)
- `setuptools` 70.3.0 -> 78.1.1 (HIGH)
- `urllib3` 2.7.0 -> 2.8.0 (HIGH)

### sapi-h3-518c0b5-web-v2

SO base: debian 13.8. Escaneo: 2026-11-25T04:29:53Z.

| Objetivo | Clase | CRITICAL | HIGH | MEDIUM | LOW | UNKNOWN | Total (únicas) |
|---|---|---|---|---|---|---|---|
| sapi-h3-518c0b5-web-v2:latest (debian 13.8) | os-pkgs | 2 | 162 | 656 | 1606 | 122 | 2548 |
| Node.js | lang-pkgs | 0 | 0 | 0 | 0 | 0 | 0 |
| Python | lang-pkgs | 5 | 29 | 16 | 1 | 0 | 51 |

CRITICAL/HIGH con versión corregida publicada (paquete, instalada -> corregida):

- `msgpack` 1.1.2 -> 1.2.1 (HIGH)
- `msgpack` 1.1.2 -> 1.2.3 (HIGH)
- `pillow` 12.3.0 -> 13.0.0 (CRITICAL/HIGH)
- `setuptools` 70.3.0 -> 78.1.1 (HIGH)
- `urllib3` 2.7.0 -> 2.8.0 (HIGH)

## pip-audit (site-packages instalados en cada imagen)

### sapi-h3-518c0b5-ml-api

Paquetes auditados: 117. Con avisos: 2.

- `black` 26.5.1: 1 avisos; corregida en 26.10.1
- `pillow` 12.3.0: 42 avisos; corregida en 13.0.0

### sapi-h3-518c0b5-web-v2

Paquetes auditados: 62. Con avisos: 1.

- `pillow` 12.3.0: 42 avisos; corregida en 13.0.0

## OSV-Scanner (Maven)

### services/backend/pom.xml

- `org.apache.tomcat.embed:tomcat-embed-core` 11.0.24: 4 avisos (GHSA-9xv2-5v5q-p794, GHSA-f525-44xv-f2qj, GHSA-gcx9-497g-6cp6, GHSA-h3x4-894j-xpx5)
- `tools.jackson.core:jackson-core` 3.1.5: 2 avisos (GHSA-7hhh-6rmp-j9qf, GHSA-p6pp-m3f8-5c89)
- `tools.jackson.core:jackson-databind` 3.1.5: 5 avisos (GHSA-cxp5-3px4-pw24, GHSA-gx83-3vf8-gh7j, GHSA-q4xh-88c3-wmh7, GHSA-wjgm-6hv5-3cvf, GHSA-wv8q-qhhj-9h54)

## Agregado manual (2026-11-25, corrección del Auditor B-1 y B-2)

Esta sección no la genera `resumir_escaneos.py`; se agregó a mano después de generar el resumen.

### Entorno de ejecución (B-1)

Hardware: AMD Ryzen AI 7 350 (8 núcleos, 16 hilos), 31 GB de RAM, Windows 11 Home 10.0.26200 (mismo equipo que `reports/orden-25-11-h3/INFORME.md`).

Ejecutado en el computador local, no en ambiente desplegado.

### `pillow` 12.3.0: Trivy y pip-audit no cuentan lo mismo (B-2)

- Trivy: 43 CVE únicos para `pillow` 12.3.0 en cada imagen (`web-v2` y `ml-api`); el JSON crudo trae 86 entradas para ese paquete (cada CVE aparece dos veces). Verificado el 2026-11-25 contando `VulnerabilityID` distintos en `crudos/trivy-sapi-h3-518c0b5-{web-v2,ml-api}.json.gz`.
- pip-audit: 42 avisos para `pillow` 12.3.0 en cada imagen (`crudos/pip-audit-sapi-h3-518c0b5-{web-v2,ml-api}.json`).
- La diferencia de 1 entre 43 y 42 queda sin resolver: no se cruzó aviso por aviso y no se explica aquí sin esa evidencia.

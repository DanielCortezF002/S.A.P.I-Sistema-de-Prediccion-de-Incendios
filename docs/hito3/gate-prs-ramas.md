# HU-85: estado del gate, PR abiertos y ramas (22-11-2026)

Datos consultados en la API de GitHub el 22-11-2026, cerca de las 22:30 (Chile). Los PR y las ramas se listan como **propuestas**. Ninguno se cerró ni se borró: esa decisión es de Daniel y queda en el registro de decisiones (S3-23.T3).

## 1. Gate oficial sobre `main`

| Dato | Valor |
|---|---|
| SHA de `main` | `9e70867` (A4, dos workers ML; integrado el 03-11-2026) |
| Run de push | [41932911572](https://github.com/DanielCortezF002/S.A.P.I-Sistema-de-Prediccion-de-Incendios/actions/runs/41932911572), 04-11-2026 |
| Jobs del gate (`scripts/merge_gate.py`) | `freeze`, `python`, `backend-unit`, `sql-migration-validation`, `flyway-integration` y `container-smoke`: **6 de 6 en verde** |

Lectura frente a la observación MUST de César (13-11-2026):

| Punto observado el 28-10 | Estado al 22-11 | Evidencia |
|---|---|---|
| Gate 4 de 6 | **Resuelto**: 6 de 6 en `main` | Run 41932911572 |
| Lint v2 en rojo (D-01) | **Resuelto**: el job `python` incluye black y flake8 v2 y pasa | Run 41932911572, job `python` |
| Prueba de estilos que falla en `main` (D-02) | **Resuelto**: el job `python` ejecuta la suite completa y pasa | Ídem |
| IT-13 | **Abierto**: IT-13 es la prueba de Compose sin `.env` (SAPI-66.CA5). No corre en CI; según el acta F2, pasó solo en Windows local. Falta repetirla en Linux sobre el SHA del tag (HU-85.T1 y T7) | `docs/hito2/TRAZABILIDAD_HU_CA_EVIDENCIAS.md` |
| Sin tag del Hito 2 | No se crea retroactivamente. El tag `hito3` se crea al cierre (HU-85.T4) | — |
| 11 PR abiertos | Hay 9 antiguos, más 5 del Sprint 3 (sección 2) | API de GitHub |

## 2. PR abiertos

### Sprint 3 (vigentes)

| PR | HU | Estado | CI |
|---|---|---|---|
| #45 | SAPI-92 plan, metas y DoD | Borrador | 6 de 6 |
| #46 | SAPI-88 explicación del Modelo D | Listo para revisión | 6 de 6 |
| #47 | SAPI-83 evaluación con datos reales | Listo para revisión | 6 de 6 |
| #48 | SAPI-86 clima con motivo explícito y D-03 | Borrador | En curso |
| #49 | SAPI-89 escaneo de seguridad | Borrador | En curso |

### Antiguos: propuesta por PR

| PR | Título | Estado | Propuesta | Motivo |
|---|---|---|---|---|
| #30 | Navegación tabla ↔ mapa | Conflictos con `main` | Cerrar y registrar como deuda | Mejora de UI del Sprint 2 fuera del alcance comprometido (el rediseño del frontend está excluido) |
| #31 | Gobernanza del repositorio R1 | Borrador, sin conflictos | Revisar el contenido; candidato a integrar como documentación de A8 | Sin conflictos y aporta a A8 si sigue vigente |
| #32 | Arreglo del gate Python (W0) | Conflictos | Cerrar como superado | El gate Python ya pasa en `main` |
| #33 | Arreglo del gate Python (R3) | Conflictos | Cerrar como superado | Ídem |
| #34 | Política F4 de excepción criptográfica | Conflictos | Cerrar como superado | Remediación del Sprint 2 ya cerrada; el freeze pasa en `main` |
| #35 | Endurecer prueba CA8 | Conflictos | Cerrar como superado, salvo que la prueba CA8 vuelva a fallar de forma intermitente | El job correspondiente pasa en `main` |
| #37 | Informe del Hito 2 sobre la plantilla | Sin cambios efectivos (+0/−0) | Cerrar | El informe se entregó fuera del repositorio |
| #38 | Estructura del repositorio | Inestable, 25 archivos | Revisar; integrar solo lo que ordene carpetas para A8 | Toca muchos archivos; riesgo de conflicto con los PR del Sprint 3 |
| #41 | Evidencia E2E full-stack de SAPI-66 | Conflictos, 85 archivos | Mantener y rehacer sobre `main` dentro de HU-85.T7 | Es la evidencia E2E que pide la rúbrica (A5); hay que regenerarla sobre el SHA del tag |

## 3. Ramas remotas sin ID de ticket

Hay 51 ramas remotas: 22 llevan `SAPI-NN` y 29 no. La columna «Ahead/behind» cuenta commits frente a `main`; ahead = 0 significa que todo su contenido ya está en `main`.

| Rama | Ahead/behind | Propuesta |
|---|---|---|
| `perf/a4-ml-workers2` | 0/0 | Borrar: integrada (A4) |
| `sprint-1`, `sprint-2`, `develop` | 0/196, 0/193, 0/269 | Conservar como históricas o convertir en tags; están integradas |
| `cert/r66-…`, `cert/r68-…`, `code/rc1-convergence-contract-fix`, `feat/sprint2-publicacion-segura`, `fix/oc-ci-pr39-20261024`, `integracion/puente-n8n-datos-operacionales`, `operaciones/preparacion-actualizacion-controlada`, `recovery/s2-academic-20261024`, `test/oc-fullstack-e2e-r2-20261024`, `validacion/sprint2-candidato-20261030`, `validacion/sprint2-candidato-f4p-20261030`, `verificacion/hito2-puerta-calidad-w0` | ahead 0 | Borrar: integradas |
| `checkpoint/preformateo-20261107` | 2/0 | Revisar: 2 commits que no están en `main` |
| `interfaz/hito2-preparacion-defensa-academica` | 11/41 | Revisar: 11 commits que no están en `main` |
| `ci/rc1-release-gate-harness` | 7/162 | Revisar o cerrar |
| `interfaz/tarjeta-clima-actual-dmc` | 2/218 | Revisar: relacionada con HU-86, posiblemente superada por #48 |
| Ramas de los PR #30, #31, #34, #35, #37, #38 y #41 | 1 a 3 ahead | Siguen la decisión de su PR |

Regla desde el Sprint 3: toda rama nueva lleva `feat/SAPI-NN-…` o `fix/SAPI-NN-…` (la cumplen #45 a #49).

## 4. Pendiente de HU-85

- T1 y T7: repetir IT-13 y el E2E en Linux sobre el SHA del tag. Requiere Docker; aquí no hay.
- T3: Daniel decide las secciones 2 y 3; después se cierran PR y se borran ramas.
- T4: tag `hito3` al final, con las HU integradas.
- T6: acta del Gate B (GB-04, GB-05, GB-09 y GB-10).
- La protección de `main` no se pudo consultar (la API respondió 403 a esta integración). Hay que verificarla en Settings → Branches.

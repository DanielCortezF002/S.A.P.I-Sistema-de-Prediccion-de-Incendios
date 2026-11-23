# S.A.P.I.: registro único de riesgos, impedimentos y deuda técnica (A9)

Subtarea HU-92.T7 (SAPI-174). Versión 0.1, 22-11-2026.

Unifica en un solo código `R-xx` tres registros anteriores, que siguen en el repositorio como historia:
- `docs/matriz-riesgo.md` (Hito 1, códigos `R-NASA-FIRMS-01` y similares);
- `docs/hito2/MATRIZ_RIESGOS_SPRINT2.md` (R1 a R19);
- los R-01 a R-06 y C1 del Informe del Hito 2.

Cada riesgo indica el requisito u objetivo que amenaza (catálogo en `docs/requerimientos.md`).

Escalas: probabilidad e impacto en Baja/Media/Alta. Nivel = combinación (Alta×Alta = Crítico; Alta×Media o Media×Alta = Alto; Media×Media = Medio; el resto, Bajo).

## 1. Registro

| ID | Riesgo | Amenaza a | Prob. | Impacto | Nivel | Mitigación | Contingencia | Estado al 22-11-2026 | Historial |
|---|---|---|---|---|---|---|---|---|---|
| R-01 | Tablero Jira desalineado del estado técnico (incluye 11 PR abiertos y ramas huérfanas) | RNF-04, criterios 2 y 6 de Matías | Alta | Medio | Alto | Comentarios con SHA y CI en cada HU; inventario de PR y ramas (`docs/hito3/gate-prs-ramas.md`) | Reconciliar antes del tag | **Materializado** (Hito 1 → Sprint 3); en mitigación | Antes R14 (S2) y R-01 (Informe H2). 28-10: 11 PR; 22-11: 9 antiguos y 6 del S3 |
| R-02 | Gate oficial incompleto (4 de 6 jobs) | RNF-04 | Media | Alto | Alto | Corrección de lint (D-01) y de estilos (D-02) | Gate B diferido con acta | **Cerrado en CI**: `main` 6/6 (run 41932911572). IT-13 sigue abierto (ver DT-01) | Antes R-02 (H2) |
| R-03 | Fuente de incendios CONAF inexistente | RF-05, OE5 | Alta | Medio | Alto | Usar solo NASA FIRMS como verdad terreno | Declararlo como limitación | **Materializado**; aceptado | Antes R-CONAF-01 (H1) |
| R-04 | Histórico DMC incompleto (12 h por endpoint; estaciones sin datos) | RF-05, OE5 | Alta | Medio | Alto | Join con estación 330007 y tolerancia de ±15 min | Declararlo como limitación | **Materializado**; aceptado | Antes R-DMC-01 (H1), R10 (S2) |
| R-05 | Sin credenciales de producción DMC/FIRMS: no hay CURRENT operativo vivo | RF-01, OE3 | Alta | Medio | Alto | Snapshots congelados y rotulados como históricos | Demo con datos fechados | Abierto | Antes R10 y R11 (S2) |
| R-06 | El Modelo D no supera a un baseline simple (A supera a D en PR-AUC en 3 de 4 años; Top 5 capta 12 de 82 positivos) | OE5, RF-06 | Alta | Alto | **Crítico** | Presentarlo como ranking relativo; HU-83 y HU-65 con incertidumbre; `scientific_model_validation=false` | ADR del D frente al A (HU-65.T3); OE5 como análisis comparativo | **Materializado**; se declara | Antes C1 (H2). Cifras de HU-83, 22-11 |
| R-07 | 20 de 50 celdas sin DEM (B-13) | RF-01, RF-06 | Alta | Medio | Alto | El panel lo declara («Sin cobertura DEM de referencia») | Completar el DEM y reentrenar (decide César) | **Materializado**; decisión pendiente (HU-86.T2) | B-13 (H2) |
| R-08 | Contradicción de César: congelar ML (revisión del 13-11) frente a entrenar una red temporal (audio del 20-11) | RF-07, RF-08, RF-09 | Alta | Alto | **Crítico** | No se entrena sin su confirmación escrita (SAPI-165) | Las HU de la red temporal pasan a Won't | Abierto | Nuevo, S3 |
| R-09 | Sprint sobrecomprometido (71 SP abiertos para ~4 días) | Todos los Must | Alta | Alto | **Crítico** | Orden de recorte: SAPI-93, 80, 76; luego 64 | Declarar lo no hecho en A4 | **Materializado** | Nuevo, S3 |
| R-10 | Dataset `14b36ad8…` no localizado en el equipo | RF-06 | Media | Alto | Alto | Búsqueda y verificación de hash (HU-83.T5) | Reconstrucción con SAPI-78 | **Materializado y cerrado** (22-11): localizado; hash verificado en HU-83 | Nuevo, S3 |
| R-11 | Disponibilidad de Bomberos de La Cruz para validar las 15 HU | A3, criterios 1 y 2 de Matías | Media | Alto | Alto | Validación remota por HU (captura y 2–3 preguntas) | Sesión consolidada (HU-79) | Abierto. Mauricio aprobó el backlog; falta la aprobación por HU | Nuevo, S3 |
| R-12 | Matías no acepta el entorno local con Docker Compose como «desplegado» | RNF-08, criterio 7 | Media | Alto | Alto | Consulta por escrito (HU-90.T3) | Opción gratuita sin tarjeta, previa aprobación | Abierto | Antes R13 (ADR-011 sin firma) |
| R-13 | Caída de la orquestación con agentes (cuota agotada en Orca, 22-11) y pérdida de la revisión independiente | Criterio 7, A5 | Alta | Medio | Alto | Un solo ejecutor (Claude) con CI como verificación | Declarar la limitación de autoauditoría | **Materializado** (22-11) | Nuevo, S3 |
| R-14 | La grilla no cubre La Cruz: la opinión de los validadores es hipotética | OE3, criterio 1 | Alta | Medio | Alto | Preguntas «si fuera tu cuartel» | Declararlo en la tabla de limitaciones | Aceptado | Nuevo, S3 |
| R-15 | Pillow 12.3.0 con avisos de seguridad, bloqueado por streamlit `<13` | RNF-06 | Baja | Medio | Bajo | La app no procesa imágenes de usuarios | Actualizar streamlit en el próximo ciclo | Aceptado (SEC-02) | Nuevo, S3 |
| R-16 | Atomicidad de publicación bajo un fallo de IO en el refresco (ADV-05) | RF-05, RNF-01 | Media | Alto | Alto | 5 pruebas de caracterización | Decisión humana pendiente | Abierto | Antes R8 (S2) |
| R-17 | Fallas en la demo en vivo (puertos, Docker lento) | Criterio 7 | Media | Medio | Medio | Puertos parametrizables y capturas de respaldo | Plan de contingencia del guion | Abierto | Antes R17 (S2) |
| R-18 | Defectos de publicación y robustez de SAPI-71 (B1, B2, B3) | RF-05 | — | — | — | Corregidos con pruebas | — | **Cerrado** (S2) | Antes R5, R6 y R7 (S2) |
| R-19 | Falsos positivos de actualización y persistencia en E2E (CA4, CA5) | A5 | — | — | — | Normalización y comparación de `firms_origin` | — | **Cerrado** (S2) | Antes R1 y R2 (S2) |
| R-20 | Gate de contenedor sin base de datos; constraint de V004 en la prueba SQL | RNF-04 | — | — | — | Postgres desechable; insert corregido | — | **Cerrado** (S2) | Antes R3 y R4 (S2) |
| R-21 | Seguridad del bootstrap (`.env` sobrescrito, contraseña de volumen) | RNF-06 | — | — | — | `O_CREAT` y `O_EXCL` | — | **Cerrado** (S2) | Antes R9 (S2) |
| R-22 | API NASA FIRMS con formato de ruta incorrecto | RF-05 | — | — | — | Ruta posicional oficial | — | **Materializado y cerrado** (30-08) | Antes R-NASA-FIRMS-01 (H1) |
| R-23 | Grilla de la demo inconsistente con el corredor declarado | RF-01 | — | — | — | Fuente única de geometría | — | **Materializado y cerrado** (05/06-09) | Antes R-GRILLA-01 (H1) |
| R-24 | Documentación desactualizada respecto del código (informe sobre una arquitectura anterior; matriz S2 fuera del repo) | Criterio 6 | — | — | — | Reescritura contra el SHA | — | **Cerrado** (S2) | Antes R18 y R19 (S2) |

## 2. Tabla de equivalencias

| Código anterior | Código nuevo |
|---|---|
| R-NASA-FIRMS-01 | R-22 |
| R-GRILLA-01 | R-23 |
| R-DMC-01 | R-04 |
| R-CONAF-01 | R-03 |
| R-COBERTURA-01 | Cerrado en el H1 (cobertura del 80 %). Hoy la cubre KPI-04, sin riesgo propio |
| R-INTEGRACION-01 | Resuelto en el S2 por el vertical slice (SAPI-55 a 61) |
| R1, R2 | R-19 |
| R3, R4 | R-20 |
| R5, R6, R7 | R-18 |
| R8 | R-16 |
| R9 | R-21 |
| R10, R11 | R-04 y R-05 |
| R12 | Cerrado en el S2 (bootstrap aprobado); su residuo es IT-13 (DT-01) |
| R13 | R-12 |
| R14 | R-01 |
| R15 | Cerrado: la rama quedó excluida; ver el inventario de ramas |
| R16 | R-10 |
| R17 | R-17 |
| R18, R19 | R-24 |
| C1 (Informe H2) | R-06 |

## 3. Impedimentos del Sprint 3

| ID | Impedimento | Abierto | Cerrado | Responsable | Ticket |
|---|---|---|---|---|---|
| I-01 | Confirmación escrita de César sobre la red temporal | 21-11 | — | Daniel | SAPI-165 |
| I-02 | Fecha y formato del informe del Hito 3 | 21-11 | — | Daniel | SAPI-158 |
| I-03 | Respuesta de Matías sobre el entorno local | 21-11 | — | Daniel | SAPI-138 |
| I-04 | Dataset `14b36ad8…` no localizado | 21-11 | 22-11 | ML | SAPI-164 |
| I-05 | `gh auth` para listar PR | 21-11 | 22-11 (acceso por API) | Daniel / Claude | — |
| I-06 | PyTorch con Python 3.14 | 21-11 | — (sin probar; depende de I-01) | ML | SAPI-64 |
| I-07 | Firma de ADR-011 por otra persona | 16-10 | — | Daniel | SAPI-138 |
| I-08 | El capitán de Viña del Mar no responde | nov | — | Daniel | — |
| I-09 | Cuota de Orca agotada (Gemini, ~141 h) | 22-11 | 22-11 (se sigue con Claude) | Daniel | — |
| I-10 | Metas KPI «pendientes de Daniel» que bloquean mediciones | 22-11 | — | Daniel | SAPI-173 |

## 4. Deuda técnica priorizada

| ID | Deuda | Impacto | Prioridad | Plan |
|---|---|---|---|---|
| DT-01 | IT-13 (Compose sin `.env`) solo pasó en Windows local; no corre en CI | Alto (RNF-08, criterio 7) | 1 | Repetirla en Linux sobre el SHA del tag (HU-85.T1, T7) |
| DT-02 | Imágenes Docker y dependencias Maven sin escaneo (Trivy) | Medio (RNF-06) | 2 | Trivy local y reporte en `docs/calidad/` (HU-89) |
| DT-03 | Credencial de desarrollo por defecto en `src/config.py` (SEC-03) | Medio | 3 | Fallar cerrado si falta `DATABASE_URL` |
| DT-04 | Campo `figuras` del JSON de HU-83 con rutas absolutas de Windows | Bajo | 4 | Las rutas válidas están en `docs/hito3/hu83_lectura_figuras.md`; corregirlo en la próxima ejecución |
| DT-05 | Cambio de D-05 sin commit; evidencia fuera del repositorio (`C:\SAPI-S3-D05-HARDEN-20261103`) | Alto (RNF-07) | 1 | HU-75: commitear con la preinscripción y versionar la evidencia |
| DT-06 | 9 PR antiguos y 29 ramas sin ID de ticket | Medio (criterio 6) | 2 | Decidir según `docs/hito3/gate-prs-ramas.md` |
| DT-07 | Sin auditor independiente desde el 22-11 | Medio (credibilidad de A5) | 2 | Declararlo; revisión de Daniel antes de cada merge |

## 5. Plan de mejoras (después del Hito 3)

1. Subir streamlit para liberar pillow 13 (R-15).
2. Completar el DEM de las 20 celdas y reentrenar con preinscripción, si César lo aprueba (R-07).
3. Integrar una fuente oficial de incendios (CONAF/SNIF) como segunda verdad terreno (R-03).
4. Despliegue gratuito reproducible si Matías no acepta el entorno local (R-12).

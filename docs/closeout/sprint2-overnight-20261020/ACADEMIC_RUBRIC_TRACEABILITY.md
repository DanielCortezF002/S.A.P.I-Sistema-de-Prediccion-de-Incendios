# Trazabilidad académica — cobertura de rúbricas (sin calificar)

Ambas rúbricas se leyeron íntegras desde los `.md` adjuntos a la sesión. **Limitación:** son transcripciones; los originales
(`Rubrica_Hito_2_Proyecto_de_Titulo.xlsx` y `Syllabus ... Versión2.docx`) no son accesibles desde la nube, así que no pude
cotejar la transcripción contra ellos. **No asigno niveles ni notas**: eso queda para revisión humana. Las matrices
`docs/hito2/MATRIZ_RUBRICA_*_FINAL.md` existentes contienen autocalificaciones sobre otro commit (`f965483`) y no se reutilizan.

Distinción de fuentes: la **rúbrica de Matías** (8 criterios) y el **instrumento del syllabus de César** (6 criterios) son
documentos distintos. Las ponderaciones de César que figuran abajo son las **escritas en el archivo recibido** (suman 100 %);
no las derivo de otra fuente.

## A. Rúbrica de Matías (Proyecto de Título, Hito 2)

| # | Criterio (pond.) | Evidencia verificada hoy `[N]` | Evidencia solo documental `[R]` | Brecha de evidencia |
|---|---|---|---|---|
| 1 | Incremento funcional (20 %) | Servicios ML/backend/Streamlit con pruebas verdes; cadena con stub | Demo real y capturas (`closeout_e2e`, otro commit) | La **demo en vivo sin intervención manual** debe repetirse en Omen sobre la candidata |
| 2 | Requerimientos (15 %) | `requerimientos-sprint2.md` con CA/RN trazados | Jira | Discrepancias de estado (matriz §3) |
| 3 | Arquitectura (15 %) | `test_architecture.py` verde (reglas de capas, Streamlit no ejecuta Modelo D) | ADRs 001–011 | ADR-011 sin firma |
| 4 | Datos/procesos/plataformas (15 %) | contratos OpenAPI validados; Flyway/SQL en CI | DER en informe | PostGIS real no verificado aquí |
| 5 | Calidad técnica (15 %) | cobertura 85,3 %; black/flake8 en rutas v2; errores tipados | — | deuda legacy reportada, no bloqueante |
| 6 | Validación y pruebas (10 %) | 2154+162 pruebas; 12 nuevas; hallazgo `age_hours` | JUnit CI | 65+4 omisiones ocultan integración real; ver auditoría |
| 7 | Integración y atributos de calidad (5 %) | contrato, degradación 503/504, límites de cuerpo (MAX_BODY) | latencias del Omen | rendimiento/seguridad no medidos aquí |
| 8 | Evidencia, trazabilidad, evolución (5 %) | 194 commits, `artifacts/hito2/**` | matriz HU→código→prueba | matriz de riesgos: revisar vigencia; evidencia de otro SHA |

Entrega exigida por Matías para la defensa: demo técnica de 7 min **en vivo, sin intervenciones simuladas**. Este expediente no
puede sustituirla; el ensayo y la BD poblada con datos realistas son acciones humanas. Lista de chequeo §7 de su rúbrica:
pruebas automatizadas ejecutables ✔ (reproducibles con los comandos de `E2E_VERIFICATION_REPORT.md`); repositorio/commits
balanceados entre integrantes: **no evaluado** (requiere `git shortlog` y criterio humano).

## B. Instrumento del syllabus de César (INSW421, Informe 2 y presentación)

| # | Criterio (pond. según archivo) | Qué aporta este expediente | Pendiente humano |
|---|---|---|---|
| 1 | Propuesta de solución y modelo de investigación (20 %) | Marco científico explícito: ranking relativo, F4 FAIL | Redacción y bibliografía (Hernández Sampieri; Cruz Lemus) |
| 2 | Requerimientos (20 %) | CA verificables, matriz de cierre | — |
| 3 | Arquitectura (20 %) | Rutas reales y capas verificadas por pruebas | Diagrama que coincida con carpetas |
| 4 | Datos, procesos y plataformas (20 %) | Contratos y esquema | Justificación de plataforma (ADR-011 vs presupuesto $0) |
| 5 | Gestión Sprint 2: pruebas y riesgos (10 %) | Plan de pruebas ejecutable con clasificación honesta | Matriz de riesgos actualizada (incluir R-nuevo: omisiones 65+4, defecto `age_hours`) |
| 6 | Calidad documental e informe/defensa (10 %) | — | Informe 2 (IEEE/APA), ensayo de 20 min |

Fecha del hito en el syllabus: presentación Semana 11 (19-10-2026), **anterior a hoy (20-10)**; confirmar con el docente la
fecha efectiva de defensa/entrega, porque el cierre técnico descrito aquí no puede recuperar esa fecha.

## C. Coherencia científica exigida en cualquier material académico

Usar siempre: prototipo exploratorio; ranking relativo (no probabilidad calibrada); sin validación científica independiente;
no apto para decisiones reales de emergencia; target = detección FIRMS en `T < t ≤ T+6h`, nunca "ignición confirmada".
Cifras de latencia o "PASS" del informe raíz deben citar commit y entorno.

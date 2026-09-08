---
titulo: "S.A.P.I. — Sistema de Alerta y Priorización de Riesgo de Incendios"
subtitulo: "Informe de Hito 1 — Sprint 1"
institucion: "Universidad Andrés Bello"
asignatura: "INSW421 — Seminario de Licenciatura"
autor: "Daniel Gonzalo Cortez Fierro"
fecha: "07-09-2026"
version_evaluada: "commit 9f076172adca3dbce0285f5d942d2803ac6f68a4 (rama main)"
estado: "Documento canónico para generación de DOCX/PDF — no modificar sin regenerar desde las fuentes congeladas"
---

# S.A.P.I. — Informe de Hito 1 / Sprint 1

**Estado del documento:** canónico, ensamblado el 07-09-2026 a partir de
ocho documentos ya congelados (arquitectura, testing, trazabilidad,
atributos de calidad, riesgos, versionamiento, calidad de código, cierre
de Sprint 1). No introduce evidencia nueva ni recalcula métricas — cada
cifra citada aquí proviene de uno de esos documentos o de un artefacto
que ya los respalda.

---

## Resumen ejecutivo

S.A.P.I. estima y prioriza el riesgo relativo de nuevas detecciones de
fuego en una grilla espacial, utilizando información disponible antes de
la ventana futura. El Hito 1 cierra Sprint 1 con dos entregas
complementarias: un avance real pero desigual sobre las cuatro historias
de usuario técnicas planificadas (ingesta NASA FIRMS, telemetría DMC,
topografía DEM, limpieza e integración), y un pipeline temporal nuevo,
construido y auditado durante el propio Hito, que reformula
metodológicamente cómo el sistema calcula un ranking exploratorio de
riesgo: meteorología regional nunca reetiquetada por celda, causalidad
temporal estricta, y un target futuro honesto sobre detecciones FIRMS
reales.

La suite automatizada del repositorio pasa en su totalidad (470
pruebas, 0 fallos) con una cobertura de código de 91,72% sobre `app` y
`src`, por encima del umbral de 80% exigido en la configuración del
proyecto. El prototipo local resultante ensambla y opera sobre las 50
celdas del corredor Viña del Mar–Quilpué–Villa Alemana, con
trazabilidad técnica verificable de requerimiento a evidencia.

El cierre de Sprint 1, sin embargo, no alcanza el mismo nivel en su
dimensión de gestión: no existe evidencia histórica de un Sprint Goal
definido, una Definition of Done previa al desarrollo, una revisión
semanal de riesgos, una Sprint Review formal ni una aceptación externa
del incremento. Estas brechas se documentan explícitamente en la
sección 16 y se convierten en un plan de acción concreto para Sprint 2
(sección 17). El presente informe evita deliberadamente presentar la
solidez técnica del incremento como si compensara la ausencia de estas
prácticas de gestión — ambas dimensiones se evalúan y se reportan por
separado.

---

## 1. Introducción

Este informe documenta el estado del proyecto S.A.P.I. (Sistema de
Alerta y Priorización de Riesgo de Incendios) al cierre del Hito 1, correspondiente a
Sprint 1 del curso INSW421. Consolida ocho auditorías independientes
realizadas sobre el repositorio real del proyecto — arquitectura,
testing, trazabilidad, atributos de calidad, riesgos, versionamiento,
calidad de código y cierre metodológico — en un documento único,
pensado para su lectura y evaluación académica.

El criterio editorial seguido en todo el informe es el mismo que guio
cada auditoría individual: ninguna afirmación se sostiene sin evidencia
verificable en el repositorio (código, tests, commits, manifests), y
donde la evidencia no existe, el informe lo declara explícitamente en
vez de omitirlo o suponerlo.

## 2. Problemática y contexto

La interfaz urbano-forestal del corredor Viña del Mar–Quilpué–Villa
Alemana, en la Región de Valparaíso, concentra un riesgo de incendio
forestal con alta exposición demográfica. El proyecto explora si
información pública y gratuita — detecciones satelitales de calor
(NASA FIRMS), meteorología terrestre (Dirección Meteorológica de
Chile) y topografía (Copernicus DEM) — permite construir, de forma
honesta y verificable, un ranking exploratorio de riesgo relativo por
celda espacial, sin pretender sustituir a los organismos oficiales de
prevención y respuesta (CONAF, SENAPRED).

## 3. Objetivos del Hito 1

El Hito 1 exige evidencia verificable, no solo declarativa, en ocho
dimensiones: arquitectura de la solución, testing, trazabilidad de
requerimientos, atributos de calidad de software, gestión de riesgos,
versionamiento, calidad de código, y cierre metodológico de Sprint 1
conforme a Scrum. Este informe reporta el resultado de auditar cada una
de esas ocho dimensiones contra el estado real del repositorio al
07-09-2026.

## 4. Alcance del incremento

El incremento evaluado es un **prototipo local**, ejecutado bajo
demanda (`streamlit run app/app.py`), no un servicio desplegado con
disponibilidad monitoreada. Cubre el corredor de 50 celdas ya
mencionado, con un horizonte de predicción congelado de 6 horas.
Explícitamente fuera de alcance en este Hito: integración operacional
con CONAF, cobertura meteorológica multi-estación, un pipeline diario
automatizado para el nuevo flujo temporal, y cualquier forma de
despliegue con SLA. El detalle completo de qué es demostración de
arquitectura y qué sería producción real está en el Anexo A.

## 5. Requerimientos y Sprint 1

Dieciséis requerimientos reales fueron identificados a partir de la
evidencia del repositorio (funcionales, no funcionales,
técnico-arquitectónicos y científico-metodológicos), nueve de ellos
vinculados a una historia de usuario o tarea Jira verificable. Diez
tickets Jira son verificables de forma independiente en dos documentos
distintos del repositorio: cuatro historias de usuario técnicas
(ingesta NASA FIRMS, telemetría DMC, topografía DEM, limpieza e
integración) y seis tareas de gestión/documentación.

Del export externo de Jira más reciente disponible (estado del tablero
al 07-09-2026, no un snapshot tomado al cierre planificado del Sprint):
**34 story points están actualmente asociados a Sprint 1, de los
cuales 21 figuran Finalizados y 13 no Finalizados.** Dos de las cuatro
historias técnicas (telemetría DMC y topografía DEM) se resolvieron el
07-09-2026 — es decir, después de la fecha de cierre planificada
(31-08-2026) — mientras que la ingesta CONAF y la integración completa
del flujo de limpieza permanecen sin finalizar. No existe un snapshot
del compromiso de story points tomado al inicio del Sprint, por lo que
la velocidad real de Sprint 1 **no es reconstruible** con la evidencia
disponible; en particular, los 21 SP Finalizados no deben leerse como
"velocidad del Sprint". El detalle completo HU por HU está en el
Anexo B.

Siete requerimientos, correspondientes al pipeline temporal nuevo
(secciones 6-9), no tienen todavía una historia de usuario Jira
vinculada — se construyeron como una auditoría y reconstrucción
metodológica dentro de la ventana del Hito, después del corte de
información Jira disponible. Esta es la brecha de trazabilidad más
relevante del informe y se retoma en las secciones 11 y 17.

## 6. Arquitectura de la solución

El pipeline temporal — la arquitectura que este Hito congela y audita
— combina tres fuentes (NASA FIRMS, meteorología regional DMC,
topografía DEM) mediante un procesamiento causal y espacial, produce un
dataset temporal etiquetado honestamente, entrena un artefacto
exploratorio (Modelo D) y expone una única interfaz de inferencia
(`score_current_grid()`) que alimenta el dashboard Streamlit. Un
segundo diagrama documenta el flujo causal de una predicción puntual en
un instante T: toda la información usada debe tener timestamp anterior
o igual a T, las 50 celdas comparten la misma lectura meteorológica
regional, y el resultado es un ranking con empates explícitos, nunca
una cifra de probabilidad.

Dos decisiones arquitectónicas sostienen la integridad del sistema y
están verificadas por prueba automatizada, no solo documentadas: la
meteorología de la estación DMC 330007 (Rodelillo) se trata siempre
como una serie **regional**, nunca reetiquetada como si fuera una
medición propia de cada una de las 50 celdas; y el prototipo permanece
completamente aislado del pipeline legacy y de los datos de
demostración (`demo_seed`), verificado por un test de arquitectura que
bloquea, mediante análisis estático, cualquier import prohibido desde
`app/` hacia los módulos analíticos internos. El detalle completo de
componentes, decisiones y límites arquitectónicos está en el Anexo A.

## 7. Fuentes de datos y metodología

Tres fuentes reales alimentan el pipeline temporal. **NASA FIRMS**
aporta el histórico de detecciones satelitales de calor sobre el
período 2021-08-30 a 2026-08-29. **DMC**, estación 330007 (Rodelillo),
aporta la única serie meteorológica real disponible para el corredor:
sobre el período de solapamiento con FIRMS, la estación registra
lectura en 1.818 de 1.826 días posibles (99,6% de cobertura temporal).
**Copernicus DEM** aporta elevación, pendiente y orientación por celda,
con los valores sin cobertura de raster preservados explícitamente como
dato faltante — nunca fabricados como cero.

Sobre esa base se construyeron 7.260 instantes candidatos de predicción
(`forecast_times`, uno cada 6 horas con al menos una lectura real),
que junto a las 50 celdas producen 363.000 filas del dataset temporal,
de las cuales 362.883 son elegibles para entrenamiento (las 117
restantes se excluyen explícitamente por cooldown, nunca se etiquetan
como negativas). De esas filas elegibles, **107 corresponden a un
arribo FIRMS positivo** — un desbalance de clases severo, consistente
con la escasez real de eventos de fuego en el corredor durante el
período observado.

La unidad experimental del sistema es el par `(cell_id, forecast_time)`.
El target se define como la existencia de un arribo FIRMS válido — una
nueva detección satelital, agrupada algorítmicamente en un "raw
episode" por proximidad espacial (2 km) y temporal (6 horas) — durante
la ventana estrictamente futura `T < t <= T+6h`, con el horizonte de 6
horas congelado para todo el Hito. Una fila cuya celda está en periodo
de cooldown tras un arribo anterior se excluye por completo del
entrenamiento, en vez de etiquetarse falsamente como "sin riesgo". Es
indispensable no confundir esta definición con una confirmación de
incendio: **una detección FIRMS es una detección satelital, no un
incendio independiente confirmado en terreno.**

La validación del modelo (Modelo D: historial temporal, meteorología
regional con lags causales, y topografía por celda) se realizó mediante
particiones temporales walk-forward, entrenando siempre sobre años
anteriores al año de prueba. La evidencia empírica resultante es
limitada: el fold correspondiente a 2024 obtiene un desempeño
`ADECUADO` en las métricas exploratorias definidas, pero ese año
coincide con el megaevento de incendio real del 03-02-2024, que
concentra una fracción desproporcionada de las 107 detecciones
positivas del dataset — el resultado de ese fold no debe leerse como
evidencia de un desempeño estable frente a eventos ordinarios. Los
folds restantes, con menos positivos aún, ofrecen soporte estadístico
más débil. Esta limitación se declara explícitamente y no se oculta: el
proyecto no afirma generalización predictiva demostrada bajo ningún
criterio (sección 16).

## 8. Implementación del incremento

El pipeline temporal se organiza en módulos con responsabilidad única y
verificada por prueba: `regional_meteo` (serie meteorológica sin
`cell_id` propio), `episodes` (agrupación de detecciones FIRMS),
`temporal_features` (lags y features "as of T"), `target_builder`
(definición honesta del target), `causality_validator` ("test de no
futuro"), y `prototype_service` como única interfaz de inferencia hacia
el dashboard. Seis hallazgos técnicos — cuatro defectos materializados
(meteorología asignada por posición de fila, sobreconteo de filas
positivas, mezcla de archivos de conflicto del backfill, un fallo de
entrenamiento con clase minoritaria insuficiente) y dos riesgos
preventivos (alineación de índices y manejo de datos faltantes) — fueron
identificados y blindados con una prueba de regresión cada uno; el
detalle completo está en el Anexo E.

## 9. Prototipo funcional

El dashboard Streamlit, en su modo "Prototipo (datos reales)"
(seleccionado por defecto), consume exclusivamente
`score_current_grid()` y presenta un mapa y un panel de detalle sobre
las 50 celdas del corredor. El ranking expone explícitamente los
empates de score cuando el modelo no distingue entre celdas — en la
corrida más reciente, 41 de 50 celdas comparten exactamente el mismo
score, un hallazgo que el dashboard muestra en vez de ocultar
artificialmente detrás de un orden más granular de lo real. Un valor
topográfico sin cobertura de DEM se muestra como "N/D", nunca como
cero. Un banner explícito advierte cuando la lectura meteorológica
usada tiene más de 12 o de 24 horas de antigüedad, para que el ranking
mostrado nunca se confunda con una vigilancia en tiempo real. El
prototipo es, en toda su extensión, una herramienta exploratoria de
apoyo a la priorización — no un sistema operacional, no una alerta
oficial, y no un reemplazo de CONAF o SENAPRED.

## 10. Estrategia de pruebas y resultados

La suite automatizada del repositorio, ejecutada de forma fresca contra
el commit evaluado, reporta **470 pruebas recolectadas, 470 exitosas, 0
fallidas y 0 omitidas**, con una cobertura de código de **91,72%** sobre
`app` y `src` — por encima del umbral de 80% configurado en el
proyecto. Un smoke test dedicado, que ensambla la aplicación Streamlit
de punta a punta mediante el framework oficial de pruebas de Streamlit,
pasa 5 de 5 casos. Diez criterios técnicos de verificación del cierre
(no criterios de aceptación históricos de Sprint 1, sino verificaciones
construidas específicamente para auditar el pipeline temporal el
07-09-2026) confirman, entre otros: que el prototipo no usa datos de
demostración, que la meteorología se trata como regional, que las
features respetan causalidad estricta, que el ranking mantiene sus 50
celdas alineadas con su score correcto bajo cualquier reordenamiento
interno, y que un dato DEM faltante nunca se convierte en cero.

Esta evidencia demuestra corrección técnica del código y del pipeline
— no demuestra, por sí sola, capacidad predictiva científica. Que la
suite completa pase no es evidencia de validez científica del modelo;
son dos afirmaciones distintas que este informe nunca colapsa en una
sola (ver también sección 7). El detalle completo de la estrategia de
pruebas, clasificación por tipo, y los diez criterios técnicos
verificados está en el Anexo C.

## 11. Trazabilidad

La cadena requerimiento→historia de usuario→criterio de
aceptación→prueba→resultado→evidencia es verificable para las diez
historias/tareas Jira ya identificadas (sección 5), pero no está
completa de extremo a extremo: el eslabón de criterio de aceptación
histórico solo está documentado para seis de esos diez tickets (sección
16); los eslabones de prueba→resultado→evidencia sí están completos
para los diez. A esto se suman brechas puntuales ya documentadas
(integración CONAF pendiente, integración de limpieza a producción
pendiente). Para los siete
requerimientos del pipeline temporal, la cadena técnica
prueba→resultado→evidencia es igualmente completa — pero **no existe
todavía una historia de usuario Jira que la respalde**. Esta es la
brecha metodológica más relevante identificada en todo el Hito: un
incremento técnico real, auditado y verificado, construido sin el
respaldo de gestión que la metodología exige. Se documenta como tal, no
se disimula creando una historia retroactiva. El Anexo B contiene la
matriz completa.

## 12. Atributos de calidad

De diez atributos de calidad de software evaluados con criterio medible
y evidencia real (no como lista genérica de ISO/IEC 25010), **tres
quedan verificados** (fiabilidad, integridad de datos,
reproducibilidad), **cuatro parcialmente verificados** (mantenibilidad,
robustez a datos faltantes, auditabilidad/trazabilidad, usabilidad),
**dos no verificados** por ausencia total de medición (rendimiento,
seguridad) y **uno no aplicable** al incremento actual (disponibilidad,
al no existir un requisito de despliegue o SLA). Rendimiento y
seguridad no se presentan en ningún caso como atributos aceptables por
default — su ausencia de evaluación se declara explícitamente como tal.
El Anexo D contiene la matriz completa, incluida su vinculación
requerimiento por requerimiento.

## 13. Riesgos e impedimentos

Veintitrés riesgos fueron identificados y clasificados: siete
provienen de una matriz de riesgo histórica ya existente en el
proyecto, trece se reconstruyeron durante el cierre de este Hito a
partir de hallazgos técnicos y metodológicos reales (auditados y
fechados como tales, nunca presentados como registro histórico), y tres
son limitaciones científicas documentadas. Por estado actual: **siete
materializados y corregidos** (con test de regresión cada uno), **cinco
mitigados**, **tres transferidos formalmente a Sprint 2** (integración
CONAF, integración de limpieza a producción, y el vínculo Jira del
pipeline temporal), **tres abiertos y dos no resueltos** (entre ellos,
la ausencia de Sprint Goal/DoD/snapshot inicial, no recuperable
retroactivamente), y **tres aceptados como limitación científica**
explícita — nunca presentados como defectos corregibles. No existe
evidencia de una revisión semanal de riesgos durante Sprint 1. La
matriz completa, con probabilidad, impacto, exposición, responsable y
evidencia de cada riesgo, está en el Anexo E.

## 14. Versionamiento y calidad de código

El historial de Git muestra 68 commits en la rama principal, con
mensajes descriptivos y consistentes (97% con un prefijo de tipo de
cambio identificable), y una brecha real de 53 días sin actividad entre
julio y agosto de 2026. Existe un **tag anotado real**,
`v1.0.0-sprint1-verified`, con fecha de creación propia registrada por
Git el 31-08-2026 — mismo día del cierre planificado de Sprint 1 — cuyo
mensaje cita la evidencia de esa fecha: 188 de 188 pruebas exitosas y
80,34% de cobertura de código, ejecutadas sobre Docker con
Python 3.11. Esa cifra histórica del 31-08 y el 470/470 con 91,72% de
cobertura reportado en la sección 10 **no son contradictorios**:
describen el mismo repositorio en dos instantes distintos, separados
por una semana de trabajo adicional (el pipeline temporal completo se
construyó después del cierre planificado del Sprint). La estrategia de
ramas usa nomenclatura consistente (`feature/`, `experiment/`,
`design/`) pero sin evidencia de un flujo de integración formal
documentado; solo 10,3% de los commits referencian explícitamente un
ticket Jira.

El código de `src/` y `app/` (más de 10.000 líneas en conjunto) muestra
modularidad fuerte — la frontera entre interfaz, inferencia y
procesamiento está verificada por análisis estático, no solo declarada
— nomenclatura adecuada, y un manejo de errores adecuado, con tres
excepciones de dominio propias y cero bloques `except` desnudos. El
aislamiento del pipeline temporal respecto al código legacy está
verificado por prueba dedicada. Las brechas reales: no existe
configuración de lint, verificación de tipos ni medición de complejidad
ciclomática; un puñado de funciones (la más notable, el punto de
entrada de la aplicación Streamlit) supera las 130 líneas; y algunos
bloques de manejo de errores usan `except Exception` de forma amplia,
justificada por la degradación ante fuentes externas pero no ideal en
general. No se afirma cumplimiento global de los principios SOLID: solo
dos de los cinco tienen evidencia concreta suficiente para evaluarse
(responsabilidad única observable y separación de capas); los otros
tres se dejan explícitamente sin evaluar. El detalle completo está en
el Anexo F.

## 15. Cierre metodológico de Sprint 1

El cierre de Sprint 1 distingue con cuidado la evidencia técnica (sólida,
ya descrita) de la evidencia de gestión Scrum (ausente). No existe
registro de un Sprint Goal acordado, de una Definition of Done definida
antes del desarrollo, de una revisión semanal de riesgos, de una Sprint
Review formal con participación externa, ni de una aceptación del
incremento por alguien distinto al propio desarrollador. La única
sesión con una persona real interactuando con el prototipo —documentada
en un acta real— es una autoevaluación del propio desarrollador sobre
usabilidad móvil de un componente distinto del dashboard, y se etiqueta
como tal, nunca como una validación externa. Una retrospectiva de
cierre, fechada explícitamente el 07-09-2026 y no atribuida a una fecha
anterior, identifica qué funcionó y qué no tanto a nivel de producto
como de proceso, y de ella derivan las acciones para Sprint 2 (sección
17). El detalle completo, incluida la tabla de historias de usuario con
su estado actual y fecha de resolución, está en el Anexo G.

## 16. Limitaciones

**Limitaciones de gestión y documentación** (no defectos técnicos del
modelo ni del código):

- Sin Sprint Goal histórico definido.
- Sin Definition of Done definida antes del desarrollo.
- Criterios de aceptación históricos parciales — completos solo para
  seis de diez tickets Jira; el pipeline temporal se verifica con
  criterios técnicos construidos al cierre, no con CA de Sprint.
- Sin snapshot del compromiso de story points al inicio del Sprint —
  la velocidad real de Sprint 1 no es reconstruible.
- Sin evidencia de seguimiento/revisión semanal de riesgos ni de
  reuniones registradas durante el Sprint.
- Sin Sprint Review formal ni aceptación externa del incremento.
- El pipeline temporal, aunque técnicamente completo y verificado, no
  tiene todavía una historia de usuario Jira que lo respalde.

**Limitaciones científicas** (inherentes al estado actual de la
evidencia, no corregibles con más pruebas de software):

- Evidencia empírica limitada: 107 positivos sobre 362.883 filas
  elegibles, con el fold de mejor desempeño coincidiendo con un
  megaevento histórico atípico.
- Validación walk-forward sobre pocos años de histórico real con
  meteorología DMC — folds limitados.
- El score del prototipo es un ranking relativo exploratorio, nunca una
  probabilidad calibrada de incendio.
- Ninguna corrida hasta la fecha satisface un criterio explícito de
  "evidencia de capacidad predictiva" generalizable — no se declara
  generalización demostrada.
- Una detección FIRMS sigue siendo una detección satelital, nunca una
  confirmación de incendio en terreno.

Ninguna de estas limitaciones se resuelve por la suite de tests: los
470/470 verifican corrección de código y de pipeline, no capacidad
predictiva ni disciplina de gestión de Sprint.

## 17. Trabajo pendiente / Sprint 2

Diez acciones concretas, cada una con responsable, momento, evidencia
esperada y criterio de cierre (detalle en el Anexo G), agrupadas en tres
frentes: **gestión de Sprint** (definir Sprint Goal y Definition of
Done antes de iniciar, capturar un snapshot inicial de story points,
registrar revisión semanal de riesgos, ejecutar una sesión real de
aceptación con un evaluador externo); **integración de datos**
(completar la fuente CONAF, conectar la integración de limpieza a
producción); y **disciplina técnica** (vincular el pipeline temporal a
una historia de usuario Jira real, mejorar la tasa de trazabilidad
commit↔Jira, y definir responsables individuales si el equipo crece más
allá de una persona).

## 18. Conclusiones

El Hito 1 entrega un incremento funcional real: integración verificada
de tres fuentes de datos públicas, un pipeline temporal causal con seis
hallazgos técnicos (cuatro defectos materializados y dos riesgos
preventivos) blindados por prueba, trazabilidad técnica
de requerimiento a evidencia, una suite reproducible que pasa en su
totalidad, y un prototipo GIS funcional que expone honestamente sus
propios límites (empates de score, datos faltantes, frescura de la
meteorología). La evidencia empírica sobre capacidad predictiva sigue
siendo limitada, y así se declara explícitamente. La disciplina de
gestión de Sprint —la dimensión donde este cierre es más débil— no
tiene evidencia histórica recuperable, y se convierte en el punto de
partida concreto para Sprint 2, no en una brecha que este informe
minimice. El proyecto llega a este Hito con una base técnica sólida y
verificable, y con una lista explícita, priorizada y accionable de lo
que falta por construir en la dimensión de proceso.

## 19. Referencias

Cada referencia se clasifica como `VERIFIED` (URL/endpoint confirmado
de forma literal contra el código fuente del proyecto en esta misma
fase) o `PENDING_VERIFICATION` (dato bibliográfico citado en el código
solo de forma parcial, sin verificar su edición/DOI exactos contra la
fuente original).

- **[VERIFIED]** NASA FIRMS (Fire Information for Resource Management
  System) — API de detecciones de incendio activo,
  `https://firms.modaps.eosdis.nasa.gov/api` (constante
  `FIRMS_API_BASE`, verificada línea por línea en
  `src/ingesta/nasa_firms_backfill.py`).
- **[VERIFIED]** Dirección Meteorológica de Chile (DMC) — estación
  automática 330007 (Rodelillo), base `https://climatologia.meteochile.gob.cl`,
  endpoint `getDatosRecientesEma` (verificado en `src/config.py` y
  `scripts/backfill_dmc_historico.py`).
- **[VERIFIED]** OpenTopography / Copernicus GLO-30 DEM,
  `https://portal.opentopography.org/API/globaldem` (constante
  `OPENTOPO_BASE_URL`, verificada en `src/ingesta/dem_ingester.py`).
- **[PENDING_VERIFICATION]** Horn, B.K.P. (1981) — el código
  (`src/procesamiento/dem_terrain.py`) cita únicamente "Horn (1981)"
  como el algoritmo usado para pendiente/orientación de ladera, sin
  título de artículo, revista, volumen ni páginas en ningún comentario
  del repositorio. El título/revista/páginas exactos no están
  verificados contra el repositorio en esta fase — se mantiene
  pendiente en vez de completarse de memoria.
- **[VERIFIED]** Repositorio del proyecto: `S.A.P.I-Sistema-de-Prediccion-de-Incendios`
  (nombre histórico del repositorio, usado aquí únicamente para
  identificar la ruta/repo, no como nombre del producto — ver sección
  1 de este mapa editorial), commit
  `9f076172adca3dbce0285f5d942d2803ac6f68a4`, rama `main`.
- **[VERIFIED]** Documentos internos citados a lo largo de este
  informe: `docs/arquitectura-hito1.md`, `docs/testing-evidencia-hito1.md`,
  `docs/trazabilidad-hito1.md`, `docs/atributos-calidad-hito1.md`,
  `docs/riesgos-hito1.md`, `docs/versionamiento-hito1.md`,
  `docs/calidad-codigo-hito1.md`, `docs/cierre-sprint1-hito1.md` —
  los ocho existen en el repositorio y fueron congelados en fases
  previas de este mismo Hito.

**Total: 5 referencias VERIFIED, 1 PENDING_VERIFICATION.** No se
completó de memoria ningún dato bibliográfico faltante; donde el
repositorio no documenta el detalle exacto, la referencia queda
explícitamente pendiente.

## Anexos

- **Anexo A — Arquitectura.** Diagramas completos, tabla de
  componentes, modelo lógico de datos, decisiones arquitectónicas y
  límites. Fuente: `docs/arquitectura-hito1.md`.
- **Anexo B — Trazabilidad.** Inventario completo de HU/issues,
  matriz requerimiento→HU, matriz HU→CA→prueba→resultado→evidencia,
  story points por ticket. Fuente: `docs/trazabilidad-hito1.md`.
- **Anexo C — Evidencia de testing.** Inventario completo de pruebas
  por categoría, los diez criterios técnicos de verificación del
  cierre, y el detalle de ejecución de la suite. Fuente:
  `docs/testing-evidencia-hito1.md` y `artifacts/hito1/testing/`.
- **Anexo D — Atributos de calidad.** Matriz completa de diez
  atributos con criterio, método, evidencia y vinculación por
  requerimiento. Fuente: `docs/atributos-calidad-hito1.md`.
- **Anexo E — Matriz de riesgos.** Las 23 filas completas con
  probabilidad, impacto, exposición, respuesta, responsable y
  seguimiento semanal. Fuente: `docs/riesgos-hito1.md`.
- **Anexo F — Versionamiento y calidad de código.** Capturas de
  `git log`/`git tag`/`git branch`, cálculo de trazabilidad Git↔Jira, y
  la matriz de calidad de código completa. Fuente:
  `docs/versionamiento-hito1.md`, `docs/calidad-codigo-hito1.md` y
  `artifacts/hito1/versioning/`.
- **Anexo G — Cierre de Sprint 1.** Tabla completa de HU con fecha de
  resolución, seguimiento semanal, retrospectiva de cierre y las diez
  acciones para Sprint 2 con responsable/evidencia/criterio de cierre.
  Fuente: `docs/cierre-sprint1-hito1.md`.

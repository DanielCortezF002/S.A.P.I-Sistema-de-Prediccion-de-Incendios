# S.A.P.I. — Outline de presentación, Hito 1 / Sprint 1

**Estado:** borrador para revisión de outline antes de crear el diseño en
Canva. No se ha creado ningún diseño todavía.

**Fuente de contenido:** `docs/informe-hito1-final.md` (documento
canónico, no modificado). El fold-by-fold de la sección 5 (Slide 6) se
verificó adicionalmente contra `docs/auditoria-consistencia-2026-09-06.md`
(Fase 3, tabla de folds walk-forward) porque el informe maestro no
detalla el resultado año por año — solo el fold 2024. La verificación
de que no existe una captura real del dashboard en el repositorio (Slide
7) se hizo contra el estado real de `reports/screenshots/` (vacío salvo
`.gitkeep`).

**Duración objetivo:** exposición 15 min máx.; diseño para 13:30–14:00
antes de la demo (5 min). Suma real de los tiempos por slide asignados
abajo: **13:35** (815 s) — ver sección "Control de tiempos".

**Estructura:** 11 slides, formato 16:9.

---

## Slide 1 — Portada

**Mensaje principal:** identificación del proyecto, autor e institución.

**Texto visible:**
```
S.A.P.I.
Sistema de Alerta y Priorización de Riesgo de Incendios

Hito 1 · Sprint 1

Daniel Gonzalo Cortez Fierro
Universidad Andrés Bello · INSW421
```

**Visual sugerido:** portada tipográfica limpia sobre fondo `#F6F7F4`,
texto en `#20282A`, un único filete o bloque discreto en verde
`#315E56`. Sin foto ni ícono decorativo, sin logo institucional (no hay
uno verificable en el repositorio).

**Guion oral:** Saludo breve. "Este es S.A.P.I., Sistema de Alerta y
Priorización de Riesgo de Incendios, el trabajo de Hito 1 / Sprint 1
para INSW421." Nombre y contexto institucional en una frase.

**Qué NO decir:** no adelantar cifras ni resultados todavía.

**Tiempo:** 30 s.

**Transición:** "Empecemos por el problema que motiva este proyecto."

---

## Slide 2 — Problema y propuesta

**Mensaje principal:** por qué existe S.A.P.I. y con qué datos trabaja.

**Texto visible:**
```
¿Dónde conviene priorizar la atención utilizando información
disponible antes de una ventana futura?

Viña del Mar · Quilpué · Villa Alemana — 50 celdas

NASA FIRMS · DMC 330007 · Copernicus DEM
```

**Visual sugerido:** esquema simple del corredor con la grilla de 50
celdas superpuesta (forma geométrica, no mapa satelital real) y tres
etiquetas de fuente (FIRMS / DMC / DEM). Sin fotografías decorativas de
incendios ni de bomberos.

**Guion oral:** la interfaz urbano-forestal del corredor concentra
riesgo con alta exposición demográfica; el proyecto explora si datos
públicos y gratuitos permiten construir un ranking de priorización
honesto, sin sustituir a CONAF o SENAPRED.

**Qué NO decir:** no decir "predice incendios" ni "alerta oficial".

**Tiempo:** 65 s.

**Transición:** "Con esas tres fuentes, ¿qué construye exactamente este
Hito?"

---

## Slide 3 — Qué entrega el Hito 1

**Mensaje principal:** panorama de extremo a extremo, del dato crudo al
prototipo.

**Texto visible:**
```
DATOS REALES → PIPELINE TEMPORAL CAUSAL → MODELO D →
RANKING DE 50 CELDAS → PROTOTIPO GIS

363.000 filas · 7.260 forecast_times · 107 positivos · 50 celdas
```

**Visual sugerido:** diagrama vertical de 5 cajas conectadas por
flechas (una idea por caja), cifras clave debajo en tipografía grande.

**Guion oral:** en una frase, este Hito entrega un pipeline temporal
completo construido sobre datos reales y un prototipo funcional; el
detalle de arquitectura viene a continuación.

**Qué NO decir:** no entrar todavía en el detalle técnico del modelo
(eso es Slide 4-5).

**Tiempo:** 65 s.

**Transición:** "Veamos cómo se conecta cada pieza de esa cadena."

---

## Slide 4 — Arquitectura

**Mensaje principal:** de las tres fuentes al dashboard, en un único
flujo verificado.

**Texto visible (mínimo, el diagrama es el contenido):**
```
NASA FIRMS · DMC 330007 · Copernicus DEM
      ↓
procesamiento temporal / espacial
      ↓
dataset temporal
      ↓
Modelo D
      ↓
score_current_grid()
      ↓
ranking
      ↓
dashboard Streamlit

DMC = meteorología REGIONAL
```

**Visual sugerido:** diagrama vectorial editable en Canva (formas +
flechas), redibujando limpiamente la Figura 1 de
`docs/arquitectura-hito1.md` — no reutilizar una imagen del DOCX. La
etiqueta "DMC = meteorología regional" destacada visualmente (recuadro
o color de acento).

**Guion oral:** recorrer el diagrama de arriba a abajo, enfatizando que
la meteorología DMC es una sola serie regional aplicada por igual a las
50 celdas — no 50 estaciones independientes.

**Qué NO decir:** no decir que cada celda tiene su propia estación
meteorológica.

**Tiempo:** 85 s.

**Transición:** "Esa arquitectura descansa sobre una decisión
metodológica clave: cómo se define el futuro."

---

## Slide 5 — La decisión metodológica clave

**Título sugerido:** "Predecir sin mirar el futuro"

**Mensaje principal:** causalidad temporal estricta y definición honesta
del target.

**Texto visible:**
```
PASADO / PRESENTE          FUTURO
features <= T   ───────── T ┃────────── T+6h
                            ┃ target FIRMS

(cell_id, T) → ¿detección FIRMS válida en T < t <= T+6h?

causalidad temporal · cooldown · FIRMS ≠ incendio confirmado
```

**Visual sugerido:** línea temporal horizontal con T marcado como punto
de quiebre, zona "features ≤ T" a la izquierda y ventana futura
"T < t ≤ T+6h" a la derecha, con un ícono de detección FIRMS dentro de
esa ventana. Esta es la slide visualmente más fuerte del deck.

**Guion oral:** todo feature usado tiene timestamp anterior o igual a
T; el target es si aparece una detección FIRMS nueva en las 6 horas
siguientes; una celda en cooldown se excluye del entrenamiento, nunca
se etiqueta como "sin riesgo"; una detección FIRMS es una detección
satelital, no una confirmación de incendio en terreno.

**Qué NO decir:** no decir "probabilidad de incendio"; no presentar la
causalidad como si eliminara toda incertidumbre del dato.

**Tiempo:** 95 s.

**Transición:** "Con esa definición honesta del target, ¿qué tan bien
generaliza el modelo?"

---

## Slide 6 — Validación y limitación científica

**Mensaje principal:** la evidencia de desempeño es exploratoria y
desigual año a año.

**Texto visible:**
```
2022 — NO ENTRENABLE
2023 — LIMITADO
2024 — ADECUADO*
2025 — LIMITADO
2026 — LIMITADO / PARCIAL

* 2024 coincide con el megaevento del 03-02-2024.

Evidencia exploratoria, no generalización predictiva demostrada.
```

**Visual sugerido:** línea de 5 tramos (uno por año de test walk-forward),
cada uno con su etiqueta de soporte; asterisco visualmente destacado en
2024, con nota al pie corta.

**Guion oral:** la validación es walk-forward, año calendario por año
calendario; solo el fold de test 2024 alcanza soporte "adecuado", y
coincide con un megaevento real que concentra buena parte de los
positivos — por lo que ese resultado no puede leerse como desempeño
estable frente a eventos ordinarios.

**Qué NO decir:** no presentar el resultado de 2024 como prueba de que
"el modelo funciona"; no mostrar curvas ROC/PR como logro de producto.

**Tiempo:** 85 s.

**Transición:** "Con esos límites explícitos, veamos el prototipo
funcionando."

---

## Slide 7 — Prototipo funcional

**Mensaje principal:** el dashboard real, con sus propios límites
visibles.

**Texto visible:**
```
Ranking relativo · Datos reales/históricos · Trazabilidad por celda

Score relativo exploratorio ≠ probabilidad calibrada.
```

**Visual sugerido — condicionado a `ADD_LOCAL_ASSETS: PARTIAL`:**
en el repositorio no existe hoy una captura real del dashboard
(`reports/screenshots/` está vacía salvo `.gitkeep`, verificado antes de
diseñar esta slide) y las herramientas Canva disponibles en esta sesión
no permiten subir un archivo desde disco local (solo desde una URL
pública). Por lo tanto la slide debe construirse con un **frame
claramente marcado**:

```
[ INSERTAR CAPTURA REAL DEL DASHBOARD S.A.P.I. ]
```

con 3 callouts discretos alrededor del frame: "Ranking relativo",
"Datos reales/históricos", "Trazabilidad por celda". No se inventa ni
se recrea artificialmente una captura. Cuando exista un archivo de
captura real (mapa de 50 celdas, panel Prioridades, banner de frescura
histórica, panel de detalle), reemplazar el frame subiéndolo a Canva
mediante una URL pública o el flujo de assets disponible en ese momento.

**Guion oral:** describir lo que la captura, una vez insertada, muestra:
mapa de 50 celdas, panel de Prioridades con el ranking, banner que
advierte antigüedad de la meteorología, panel de detalle con "N/D"
cuando falta cobertura DEM.

**Qué NO decir:** no describir el placeholder como si fuera ya la
captura real frente a la audiencia — si el frame sigue vacío el día de
la exposición, decirlo explícitamente.

**Tiempo:** 85 s.

**Transición:** "Esa interfaz se apoya en una base de código verificada.
Veamos la evidencia técnica."

---

## Slide 8 — Evidencia técnica

**Mensaje principal:** la suite de pruebas pasa en su totalidad, con
cobertura sobre el umbral exigido.

**Texto visible:**
```
470 / 470 — PRUEBAS EXITOSAS
91,72 % — COBERTURA APP + SRC
5 / 5 — SMOKE STREAMLIT

Tests passing ≠ validez científica.
```

**Visual sugerido:** tres cifras grandes en tipografía destacada, sin
inventario de tests ni tablas.

**Guion oral:** la suite completa pasa, con cobertura por encima del
80% configurado en el proyecto; esto certifica corrección de código y
del pipeline, no capacidad predictiva del modelo.

**Qué NO decir:** no decir "validado científicamente"; no mezclar
cobertura de código con desempeño del modelo.

**Tiempo:** 65 s.

**Transición:** "La evidencia técnica también cubre trazabilidad,
calidad y gestión de riesgos."

---

## Slide 9 — Trazabilidad, calidad, riesgos y Git

**Mensaje principal:** panorama de auditoría técnica, con brechas
declaradas donde existen.

**Texto visible:**
```
TRAZABILIDAD
10 tickets Jira auditados
CA históricos completos: 6/10
7 REQ temporales sin HU Jira

CALIDAD
3 verificados · 4 parciales · 2 no verificados · 1 no aplica

RIESGOS
23 identificados

GIT
68 commits
tag Sprint 1 verificado
```

**Visual sugerido:** cuatro bloques/tarjetas iguales en una grilla 2x2,
texto mínimo dentro de cada uno, sin tabla de Excel.

**Guion oral:** recorrer los cuatro bloques con brevedad; en
trazabilidad, decir explícitamente que 7 requerimientos del pipeline
temporal no tienen todavía una historia de usuario Jira que los
respalde — la brecha metodológica más relevante del Hito.

**Qué NO decir:** no decir "trazabilidad completa"; no omitir los 7 REQ
sin HU.

**Tiempo:** 100 s.

**Transición:** "Toda esa evidencia técnica convive con brechas reales
de gestión de Sprint, que cerramos con honestidad."

---

## Slide 10 — Cierre de Sprint

**Mensaje principal:** la solidez técnica no compensa la ausencia de
prácticas de gestión Scrum — ambas se reportan por separado.

**Texto visible:**
```
FORTALEZA TÉCNICA              BRECHAS DE GESTIÓN
✓ pipeline temporal causal     — Sprint Goal histórico
✓ datos reales                 — Definition of Done histórica
✓ prototipo funcional          — seguimiento semanal
✓ 470/470 tests                — Sprint Review formal
✓ arquitectura verificable     — aceptación externa

No se reconstruyó evidencia retroactivamente.
```

**Visual sugerido:** dos columnas de igual peso visual (ninguna en rojo
"error"; brechas en gris/neutro, no como fracaso). El mensaje final
centrado debajo, con tono de honestidad metodológica.

**Guion oral:** la evidencia técnica es sólida y verificable; en
paralelo, no existe registro histórico de Sprint Goal, Definition of
Done previa, seguimiento semanal, Sprint Review formal ni aceptación
externa — se documenta así en vez de disimularlo.

**Qué NO decir:** no decir que estas brechas "ya se resolvieron"; no
minimizarlas como detalles menores; no reconstruir una fecha retroactiva
para ninguna de ellas.

**Tiempo:** 100 s.

**Transición:** "Con esa base honesta, así cerramos y miramos a Sprint
2."

---

## Slide 11 — Conclusión + demo

**Título:** "Una base técnica verificable para Sprint 2"

**Texto visible:**
```
DATOS REALES · PIPELINE CAUSAL · LIMITACIONES EXPLÍCITAS

S.A.P.I. prioriza riesgo relativo;
no reemplaza una alerta oficial.

DEMO →
```

**Visual sugerido:** tres etiquetas/íconos simples en línea, frase final
centrada en mayor tamaño, elemento "DEMO →" en la esquina inferior como
puente visual hacia la demo en vivo.

**Guion oral:** cerrar resumiendo los tres conceptos y anunciar la demo
de 5 minutos sobre el prototipo real.

**Qué NO decir:** no prometer en la conclusión resultados que la demo no
va a mostrar.

**Tiempo:** 40 s.

**Transición:** pasar directamente a la demo (`demo-script.md`).

---

## Control de tiempos

| Slide | Tiempo | Acumulado |
|---|---:|---:|
| 1. Portada | 30 s | 0:30 |
| 2. Problema y propuesta | 65 s | 1:35 |
| 3. Qué entrega el Hito 1 | 65 s | 2:40 |
| 4. Arquitectura | 85 s | 4:05 |
| 5. Decisión metodológica clave | 95 s | 5:40 |
| 6. Validación y limitación científica | 85 s | 7:05 |
| 7. Prototipo funcional | 85 s | 8:30 |
| 8. Evidencia técnica | 65 s | 9:35 |
| 9. Trazabilidad/calidad/riesgos/Git | 100 s | 11:15 |
| 10. Cierre de Sprint | 100 s | 12:55 |
| 11. Conclusión + demo | 40 s | 13:35 |

**Total exposición: 13:35** (dentro del rango objetivo 13:30–14:00, con
margen real bajo el máximo de 15 min). **Demo: hasta 5:00 min** (ver
`demo-script.md`, objetivo real 4:00–4:30 con margen).

## Narrativa (verificación de secuencia)

PROBLEMA (2) → PROPUESTA (2) → QUÉ ENTREGA (3) → ARQUITECTURA (4) →
CAUSALIDAD (5) → VALIDACIÓN (6) → PROTOTIPO (7) → EVIDENCIA TÉCNICA (8)
→ GESTIÓN/RIESGOS (9-10) → CONCLUSIÓN (11) → DEMO. Coincide con la
secuencia exigida.

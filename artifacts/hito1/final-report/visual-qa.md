# QA visual — DOCX/PDF final Hito 1

Ciclo obligatorio ejecutado: generar DOCX → convertir a PDF → renderizar
TODAS las páginas a PNG (`pdftoppm`, 110 dpi) → inspeccionar cada imagen
→ corregir hallazgos reales → repetir. Tres iteraciones hasta
`CRITICAL_VISUAL_ISSUES: 0`.

## Iteración 1 — 23 páginas

**Hallazgo crítico:** `figure()` en `generate_docx.js` recibía una
altura en píxeles incorrecta para ambas figuras (valor supuesto en vez
del real de los PNG generados) y aplicaba una fórmula de escala que
producía imágenes de aproximadamente 10,4 × 13 pulgadas — muy por
encima del área de página disponible (~6,1 × 11 pulgadas). Efecto
observado: página 5 quedó ~90% en blanco (solo 3 líneas de texto
arrastradas de la sección anterior) porque la imagen completa, al no
caber, se desplazó entera a la página siguiente.

- Página 1 (portada): PASS. Sin logo (ninguno disponible/verificable),
  sin número visible, datos institucionales correctos, sin profesor
  inventado.
- Página 2 (TOC): campo de tabla de contenido vacío — **limitación
  conocida y documentada de LibreOffice headless** (no recalcula campos
  TOC al convertir; el campo es real y Word sí lo actualiza al abrir el
  archivo). No se cuenta como `CRITICAL`, se documenta explícitamente
  (mismo tratamiento que en el smoke test editorial de esta misma
  skill).
- Páginas 3-4: PASS.
- **Página 5: FIX REQUERIDO** — página casi vacía sin justificación
  editorial real (causa: bug de tamaño de imagen, no una decisión de
  diseño).
- Páginas 6-23: no se completó la inspección exhaustiva de esta
  iteración porque el hallazgo de la página 5 ya era suficiente para
  requerir una nueva generación (corregir y volver a renderizar en vez
  de catalogar defectos sobre una versión que se sabía rota).

## Iteración 2 — 20 páginas

Corrección aplicada: tamaño de imagen recalculado (ancho fijo 13,5 cm,
alto proporcional a las dimensiones reales de cada PNG). Inspección
completa de las 20 páginas:

- Páginas 1-4: PASS (sin cambios respecto a iteración 1).
- Página 5: **corregida** — Figura 1 + caption completos, sin
  desbordamiento; ~35% de espacio en blanco al final de la página,
  justificado (la Figura 2 completa, con `keepNext` a su caption, no
  cabía en el espacio restante y se desplazó entera a la página 6 — es
  el comportamiento esperado de mantener figura+caption juntos, no un
  salto de página mal puesto).
- Página 6: PASS — Figura 2 + caption + texto + nueva sección, sin
  huérfanos.
- Páginas 7-13: PASS. Densidad alta pero sin desbordes, sin títulos
  huérfanos, sin viudas/huérfanas visibles, negritas/código inline
  renderizando correctamente.
- Página 13 (Anexo A): PASS — tabla de 16 filas completa en una página,
  encabezado sombreado, bordes finos consistentes.
- Página 14 (Anexo B): PASS.
- Página 15 (Anexo C): PASS.
- **Página 16 (Anexo D): FIX REQUERIDO** — "PARCIALMENTE_VERIFICADO" se
  parte a mitad de palabra ("PARCIALMENTE_VERIFICAD" + "O" en línea
  aparte) en 4 de las 10 filas. Causa: la tabla sumaba 16,0 cm de ancho
  de columna contra 15,5 cm disponibles entre márgenes.
- Página 17 (Anexo E): mismo tipo de causa (tabla de 14,0 cm, dentro del
  límite, pero columna "Estado actual" angosta) — legible pero con
  cortes de palabra menores en los tokens más largos
  (`MATERIALIZADO_Y_CORREGIDO`); no crítico pero se decidió pulir.
- Página 18 (Anexo E cont. + control contable): PASS — la tabla de
  control renderiza completa y limpia; el salto de tabla entre página
  17 y 18 repite el encabezado correctamente (fila huérfana única al
  inicio de página 18, comportamiento normal de una tabla de 23 filas
  que no cabe entera en una página, no un defecto).
- Página 19 (Anexo F): PASS.
- Página 20 (Anexo G): PASS.

Se identificaron 2 hallazgos (Anexo D crítico por ruptura de palabra,
Anexo E menor) y se corrigieron los anchos de columna de 3 tablas
(Anexo B ×2, Anexo D) que excedían el ancho disponible.

## Iteración 3 — 20 páginas (final)

Verificación dirigida a las páginas corregidas:

- Página 14 (Anexo B): PASS — ambas tablas sin cambios de layout
  negativos, contenido idéntico, columnas mejor proporcionadas.
- Página 16 (Anexo D): **corregido** — "PARCIALMENTE_VERIFICADO" y
  todos los demás estados en una sola línea, sin cortes de palabra.
- Páginas 17-18 (Anexo E): **mejorado** — "Metodológico" ya no se corta;
  el token más largo (`MATERIALIZADO_Y_CORREGIDO`) sigue ocupando 2
  líneas dentro de su celda (`...CORREGI` / `DO`) — legible, sin
  solapamiento ni truncamiento, aceptado como ajuste menor no crítico
  dado que es contenido de referencia tabular (Anexo), no cuerpo
  principal.
- Resto de páginas: sin cambios respecto a iteración 2 (confirmado por
  re-render completo, 20 páginas, mismo conteo).

### Checklist final (las 20 páginas, aplicado sección por sección)

| Verificación | Resultado |
|---|---|
| Títulos huérfanos / solos al final de página | Ninguno detectado |
| Tablas cortadas de forma absurda | Ninguna — solo el salto normal de una tabla de 23 filas entre dos páginas, con encabezado repetido |
| Columnas desbordadas | Corregido (Anexo B, D) |
| Texto sobrepuesto | Ninguno |
| Páginas casi vacías sin justificación | Corregido (página 5, iteración 1) |
| Saltos de página erróneos | Ninguno — solo saltos automáticos por `pageBreakBefore` en cada Anexo (intencional) |
| Captions separados de su figura | Ninguno — `keepNext` mantiene figura+caption juntos en ambos casos |
| Imágenes pixeladas | Ninguna — PNG generado a 200 dpi nominal, escalado hacia abajo |
| Texto demasiado pequeño | Ninguno — cuerpo 11 pt, tablas 9,5 pt, captions 9 pt, todos legibles en el render |
| Jerarquía inconsistente | Ninguna — H1/H2/H3 diferenciados consistentemente en las 20 páginas |
| Pies/encabezados incorrectos | Ninguno — "S.A.P.I. — Hito 1" / "Universidad Andrés Bello \| INSW421" + número, ausentes solo en portada (correcto) |
| Números de página incorrectos | Correctos y secuenciales desde la página posterior a portada |
| Índice roto | El campo TOC no se recalcula en LibreOffice headless (limitación conocida, documentada, no crítica — ver iteración 1) |
| Referencias partidas de forma desagradable | Ninguna — la lista de Referencias no se corta a mitad de ítem |
| Exceso de espacio | Ninguno crítico (ver nota de página 5, justificada) |
| Densidad excesiva | Ninguna — párrafos largos pero dentro de márgenes, sin bloques agobiantes |

**CRITICAL_VISUAL_ISSUES: 0**

## Iteración 4 — actualización de campos con Word real (post-QA, 21 páginas)

Corrección solicitada por revisión externa: el campo TOC no se recalcula
en LibreOffice headless. Word está instalado en esta máquina
(`C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE`), así que
se automatizó vía COM (PowerShell) en vez de pedirle al usuario que lo
hiciera a mano: abrir el `.docx`, `Fields.Update()` +
`TablesOfContents.Update()`, guardar, exportar a PDF con el motor nativo
de Word (`SaveAs wdFormatPDF`).

- Repaginación real (Word, con Aptos instalado y el TOC ya poblado):
  20 → 22 páginas. Verificado con render completo: el índice ahora
  muestra las 26 entradas correctamente con líder de puntos y número de
  página, pero desbordaba 6 líneas a una página 3 casi vacía (estilo
  `TDC 1`/`TDC 2` con `SpaceAfter=5pt`, insuficiente para compactar 26
  entradas en una sola página con el resto del documento sin tocar).
- **Fix:** `SpaceAfter=0` + interlineado sencillo en los estilos
  integrados `TDC 1`/`TDC 2` (nombre en español de `TOC 1`/`TOC 2`;
  primer intento con los nombres en inglés y con los IDs de estilo
  incorrectos no tuvo efecto — verificado por inspección de
  `doc.Styles` antes de reintentar con los nombres reales). Campos
  vueltos a actualizar, documento guardado, PDF re-exportado.
- Resultado: **21 páginas**, TOC completo en una sola página (página 2,
  hasta "Anexo G" inclusive), sin páginas casi vacías nuevas.
- Verificación de que el cambio de estilo no dañó las cabeceras del
  cuerpo (H1/H2 tienen espaciado por párrafo directo, que en Word tiene
  prioridad sobre el estilo — confirmado visualmente en páginas 5-6, sin
  cambios de jerarquía/espaciado).
- Verificación de que las 3 tablas corregidas en la iteración 2 (Anexo
  B ×2, Anexo D) siguen sin romperse bajo Aptos real — de hecho mejoran:
  "PARCIALMENTE_VERIFICADO" y "NO_VERIFICADO (NOT_MEASURED)" caben en
  una sola línea (Aptos es más condensado que la fuente serif de
  reemplazo de LibreOffice usada en las iteraciones 1-3).
- Beneficio adicional no buscado: todo el documento ahora renderiza con
  la tipografía Aptos real (Word la tiene instalada), no con el
  sustituto serif de LibreOffice — mejora visual general.

**CRITICAL_VISUAL_ISSUES (tras iteración 4): 0.** Total de páginas
final: **21** (no 20 — actualizado en `final-rubric-location-map.md`).

## Iteración 5 — corrección quirúrgica de contenido + orfandad de Anexos (21 páginas)

Corrección solicitada tras revisión externa del PDF de la iteración 4.
Cuatro correcciones factuales de texto (sincronizadas en
`docs/informe-hito1-final.md` y en `generate_docx.js`, verificadas con
`grep` para confirmar ausencia total de las frases incorrectas y
presencia de las corregidas):

1. **§6 Arquitectura:** "combina cuatro fuentes" → "combina tres
   fuentes" (se enumeran exactamente tres: NASA FIRMS, DMC, Copernicus
   DEM). Verificado en página 5.
2. **§11 Trazabilidad:** ya no afirma que la cadena completa
   (requerimiento→HU→CA→prueba→resultado→evidencia) es completa para
   los 10 tickets — ahora distingue explícitamente que el eslabón de CA
   histórico solo está documentado para 6/10, consistente con §16
   (`HISTORICAL_CA: PARTIAL`). Verificado en página 8.
3. **§8 y §18:** "seis defectos reales" → "seis hallazgos técnicos
   (cuatro defectos materializados y dos riesgos preventivos)",
   consistente con la enumeración real del propio texto. Verificado en
   páginas 7 y 11.
4. **§1 Introducción:** eliminada la meta-referencia "y como base para
   el documento DOCX/PDF final" (este documento ya es el entregable
   final). Verificado en página 3.

**Hallazgo real de maquetación (confirmado por render directo, no
supuesto):** la lista-índice de "Anexos" (encabezado + 7 viñetas A-G) se
partía entre dos páginas — 2 viñetas al final de la página 12 (cerrando
Referencias) y las 5 restantes solas al inicio de una página 13 con
~75% de espacio en blanco. Corregido **solo mediante reflow/spacing**:
se encadenó `keepNext` a través de las 7 viñetas (más el `keepNext` ya
existente del encabezado H1), forzando a Word a tratar el bloque
completo como atómico. Resultado verificado: el bloque completo
"Anexos" + 7 viñetas se desplazó entero a la página 13, dejando la
página 12 con el cierre natural de Referencias y la página 13
completamente ocupada por el índice de anexos — sin viñetas huérfanas,
sin reducir tamaño de fuente, sin tocar el contenido.

Re-generado (build.js → Word COM: actualizar campos/TOC → guardar →
exportar PDF con Word) y re-renderizadas las 21 páginas. Verificación
dirigida a las páginas con texto modificado (3, 5, 7, 8, 9, 11, 12, 13,
14) más spot-check de página 1, 2 y 21: todas correctas, sin
regresiones respecto a la iteración 4. Total de páginas: **21**
(sin cambio — las correcciones de texto no alteraron la paginación
global).

**CRITICAL_VISUAL_ISSUES (tras iteración 5): 0.**

## Nota permanente (resuelta en la iteración 4)

El campo de tabla de contenido no se recalcula en la conversión headless
de LibreOffice — limitación documentada de esa herramienta, no del
documento. Ya no aplica al entregable final: en la iteración 4 se
actualizó el campo real con Word (vía automatización COM) y se
reexportó el PDF desde Word, por lo que `deliverables/SAPI_Hito1_Informe_Final.pdf`
ya contiene el índice recalculado, no uno vacío.

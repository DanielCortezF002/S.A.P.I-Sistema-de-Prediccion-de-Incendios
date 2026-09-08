---
name: sapi-professional-word
description: "Use this skill whenever S.A.P.I. needs a professional academic/technical Word document (.docx) -- a Hito report, an architecture write-up, a risk matrix, a traceability report, or any similar deliverable. It layers S.A.P.I.-specific rules (scientific claims, source policy, design system, mandatory visual QA) on top of the official document-skills docx mechanics. Do NOT use for quick internal notes, for Jira content, or for editing application code/tests/data -- this skill produces documentation artifacts only. Do NOT use to fabricate results: if the requested document needs evidence that does not exist yet, stop and say so instead of inventing it."
license: Internal to this project. Built on top of the official Anthropic docx skill (see 'Foundation' below); does not replace or modify it.
---

# sapi-professional-word

Genera documentación académica/técnica de S.A.P.I. en DOCX con estructura
Word real, fuentes verificadas, afirmaciones científicamente defendibles y
QA visual obligatorio -- nunca "Markdown → Pandoc → declarar que quedó
profesional".

## Fundamento (Foundation)

Este skill NO reimplementa la mecánica de generación de DOCX. Se apoya en
el skill oficial `docx` de `document-skills`
(`~/.claude/plugins/marketplaces/anthropic-agent-skills/skills/docx/`),
que sigue siendo la referencia metodológica para:

- Construcción con `docx` (npm) para documentos nuevos.
- Edición de DOCX existentes (unzip → editar `document.xml` → zip).
- Lectura con `pandoc -t markdown`.
- Validación XSD (`scripts/office/validate.py`).

**Nunca se copia ni se modifica el skill oficial.** Lo que este skill
agrega es todo lo que el smoke test editorial (2026-09-07,
`artifacts/editorial-smoke/`) demostró que hacía falta además de la
mecánica: reglas de diseño, de redacción académica, de fuentes, de
afirmaciones científicas específicas de S.A.P.I., el adaptador Windows
para LibreOffice, y un proceso de QA visual obligatorio que no se puede
saltar.

## Cuándo usar cada referencia

| Pregunta | Archivo |
|---|---|
| ¿Cómo se ve/tipografía/color de un documento S.A.P.I. (a falta de una referencia institucional/humana)? | `references/design-system.md` (provisional, nivel 4 -- ver jerarquía dentro del archivo) |
| ¿Cómo se redacta el texto (tono, precisión, qué evitar)? | `references/academic-writing.md` |
| ¿De dónde puede salir una cifra o cita? ¿Cómo se verifica? | `references/source-policy.md` |
| ¿Qué se puede y qué NO se puede afirmar sobre S.A.P.I.? | `references/sapi-scientific-claims.md` |
| ¿Cómo se revisa visualmente antes de entregar? | `references/visual-qa.md` |
| ¿Existe una plantilla humana que deba usarse en vez de partir de cero? | `templates/README.md` |

Cárgalas TODAS antes de redactar contenido real -- no solo la de diseño.
Un documento con diseño perfecto y una afirmación inventada sigue siendo
un documento inaceptable.

## Principio central

El skill NO debe limitarse a:

```
redactar Markdown -> convertirlo a Word -> declarar que quedó profesional
```

Debe controlar explícitamente, para cada documento: estilos Word,
secciones, márgenes, encabezados, pies, numeración, tablas, figuras,
captions, tabla de contenidos, saltos de página, jerarquía, control de
paginación, referencias bibliográficas, y QA visual real (ver
`references/visual-qa.md`).

## Alcance del smoke test (léelo antes de la sección siguiente)

**El smoke test valida el pipeline editorial, no la identidad visual
definitiva.** Demostró que la cadena DOCX → PDF → PNG con QA visual
iterativo funciona en esta máquina, y que se puede lograr un documento
sobrio sin estética de IA -- eso es todo lo que valida. Los colores,
tipografía y demás decisiones concretas que aparecen en
`references/design-system.md` son un ejemplo de nivel 4 (design system
provisional), no una identidad visual de S.A.P.I. **Las referencias
institucionales o humanas aprobadas (niveles 1-3 de la jerarquía en
`references/design-system.md` y `templates/README.md`) tienen prioridad
sobre el design system provisional en cualquier decisión visual.**

## Lecciones obligatorias del smoke test editorial (2026-09-07)

Estas lecciones son sobre el **proceso** (mecánica de generación,
paginación, QA), no sobre la estética. Vienen de una ejecución real
(`artifacts/editorial-smoke/`, 3 iteraciones), no de teoría. Se resumen
aquí; el detalle vive en cada referencia.

**Tabla de contenidos.** Constrúyela con un campo real de Word
(`TableOfContents`, basado en estilos Heading) y `features.updateFields:
true`. LibreOffice en modo headless **no** recalcula ese campo al
convertir a PDF -- el render mostrará la TOC vacía. Esto es una limitación
conocida del mecanismo, no un error de construcción: documéntalo
explícitamente en las notas de QA del documento (nunca simules o
"rellenes a mano" el índice como si estuviera actualizado).

**Saltos de página.** No uses saltos de página manuales como mecanismo
habitual de diseño. El smoke test demostró ambos extremos del error:
demasiados saltos manuales produjeron páginas artificialmente vacías
(una tabla aislada con la mitad de la página en blanco, una TOC sola en su
página); eliminarlos todos de golpe produjo un documento excesivamente
denso (tres secciones mayores comprimidas en una sola página). La regla:
apóyate en paginación estructural (`keepNext`, `keepLines`, `cantSplit`,
`widowControl`) para que Word/LibreOffice decidan dónde cortar de forma
natural, y agrega un salto manual únicamente cuando hay una razón
editorial real (el ejemplo válido del smoke test: abrir "Referencias" en
página propia, una convención estándar, no relleno).

**Densidad y extensión.** No persigas un número de páginas prefijado ni
rellenando contenido vacío ni comprimiendo secciones para que quepan. La
extensión del documento debe emerger del contenido real y de una
composición legible -- si un documento real necesita 4 páginas o 12,
esa es su extensión correcta.

**QA.** Nunca apruebes la primera generación automáticamente. El smoke
test usó 3 iteraciones reales, cada una con un hallazgo genuino corregido.
Un documento real de S.A.P.I. debe pasar por el mismo ciclo -- ver
`references/visual-qa.md`.

## Pipeline Windows (DOCX → PDF → PNG)

En esta máquina Windows, la cadena verificada (2026-09-07,
`artifacts/toolchain-test/` y `artifacts/editorial-smoke/`) es:

```
DOCX
  |
  v
tools/document_pipeline/libreoffice_convert.py
  |
  v
soffice.com --headless   (NUNCA soffice.exe -- se cuelga indefinidamente
  |                        en esta máquina; ver docstring del adaptador)
  v
PDF
  |
  v
pdftoppm (Poppler)
  |
  v
PNG por página
```

`tools/document_pipeline/libreoffice_convert.py` es un adaptador local,
propio de este repositorio -- **nunca se modifica ni se copia el helper
`scripts/office/soffice.py` del skill oficial** (ese script asume
Linux/macOS: `AF_UNIX`, `LD_PRELOAD`, `SAL_USE_VCLPLUGIN=svp`; en Windows
falla con `FileNotFoundError` o, si se apunta a `soffice.exe`, cuelga
indefinidamente -- confirmado empíricamente).

En otros sistemas operativos, usa el mecanismo nativo apropiado para ese
sistema (en Linux/macOS, el helper `run_soffice()` del skill oficial
funciona sin adaptador).

## Proceso de trabajo (para cada documento real)

1. Identifica el propósito exacto del documento y, si existe, la rúbrica
   o criterio de aceptación contra el que se evaluará.
2. Recupera evidencia real del repositorio/artefactos -- nunca redactes
   primero y busques evidencia después.
3. Verifica cada fuente citada contra `references/source-policy.md`
   antes de escribirla.
4. Construye un outline (estructura de secciones) separado del texto
   final -- decide la arquitectura del documento antes de redactar
   prosa.
5. Separa contenido de diseño: escribe el texto sin pensar en estilos
   Word todavía; aplica `references/design-system.md` al construir el
   DOCX, no al redactar.
6. Genera el DOCX con `docx` (npm), con estilos reales (ver
   "Estilos Word mínimos" abajo) -- nunca formato manual repetido.
7. Renderiza: DOCX -> PDF -> PNG de TODAS las páginas (pipeline de
   arriba).
8. Inspecciona TODAS las páginas, una por una, contra
   `references/visual-qa.md`.
9. Corrige cualquier hallazgo real, regenera, vuelve a renderizar e
   inspeccionar. Repite hasta que no haya hallazgos nuevos.
10. Entrega solo después de que el QA visual esté limpio -- nunca antes.

## Estilos Word mínimos

Todo documento producido con este skill debe definir, como mínimo, estos
estilos de párrafo reales (no negrita/tamaño aplicados a mano párrafo por
párrafo):

`Title`, `Subtitle`, `Heading 1`, `Heading 2`, `Heading 3`, `Normal`
(cuerpo), `Caption`, `Table Text`, `Reference`.

Control de paginación esperado:
- `keepNext` en todos los encabezados (para que nunca quede un título
  solo al final de una página) y en el párrafo inmediatamente anterior a
  una figura o tabla.
- `keepLines` en captions.
- `cantSplit: true` en filas de tabla (para que una fila nunca se corte
  entre dos páginas).
- `widowControl` activo a nivel de documento.

## Tablas

Caption consistente y visible, encabezado inequívoco (negrita y/o sombreado
sutil, nunca color chillón), padding interno suficiente, bordes discretos
(gris claro, nunca gruesos ni de color), alineación consistente por
columna, ancho coherente con el margen de página. Nunca: filas cortadas
innecesariamente entre páginas, texto por debajo de un tamaño legible,
una tabla usada como sustituto de un párrafo que debería ser prosa,
zebra-striping fuerte.

## Figuras y diagramas

Planas, técnicas, con flujo visual claro, alta resolución, vectoriales
cuando sea viable (si se rasterizan, mínimo ~300 DPI equivalente). Nunca:
íconos cartoon, servidores 3D, nubes decorativas, emojis, degradados,
flechas ornamentales. Figura y caption deben permanecer juntas
(`keepNext`/`keepLines`) y nunca separarse por un salto de página. Una
arquitectura no debe convertirse en un diagrama enorme e ilegible --
si no cabe con texto legible en el ancho de página, simplifícala o
divídela en más de una figura.

## Qué NO hacer en esta fase (Fase 5)

No crear el informe del Hito 1. No crear la arquitectura real de S.A.P.I.
No hacer investigación de fuentes todavía. No tocar Jira. No tocar
`src/`, `app/`, `tests/`, `data/`. No hacer commit. Esta fase construye
únicamente el skill.

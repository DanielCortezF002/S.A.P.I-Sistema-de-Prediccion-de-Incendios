# Registro de construcción del DOCX/PDF final — Hito 1

Fecha: 07-09-2026. Fuente única de contenido: `docs/informe-hito1-final.md`
(congelado, no modificado en esta fase). Ningún dato, cifra, conclusión o
brecha se reescribió, reinterpretó ni eliminó al pasar a Word — el texto
de cuerpo se transcribió literalmente; las tablas de los Anexos A-G son
resúmenes de las tablas canónicas de los ocho documentos congelados que
`docs/informe-hito1-final.md` ya cita, no contenido nuevo.

## 1. Skills / pipeline usado

- `docx` (plugin `document-skills`, oficial) — leído primero, seguido
  para la mecánica de creación (`docx` npm) y gotchas (TOC, tablas,
  imágenes, saltos de página).
- `sapi-professional-word` (skill del proyecto) — no estaba en la lista
  de skills descubribles por el tool `Skill` en esta sesión (el working
  directory declarado de la sesión no coincide con la raíz de este
  repositorio, por lo que el descubrimiento automático de skills de
  proyecto no lo encontró). Se aplicó igualmente de forma manual, leyendo
  directamente `SKILL.md` y sus `references/` (`design-system.md`,
  `academic-writing.md`, `source-policy.md`, `sapi-scientific-claims.md`,
  `visual-qa.md`) ya conocidos de fases anteriores de este mismo Hito —
  mismo criterio, mismo proceso de QA visual, misma jerarquía de
  referencias (nivel 4 provisional, sin plantilla institucional real
  disponible).
- Pipeline de conversión: `tools/document_pipeline/libreoffice_convert.py`
  (adaptador Windows del proyecto — `soffice.com`, nunca `soffice.exe`) +
  `pdftoppm` (Poppler, instalado vía winget en una fase anterior de este
  mismo proyecto, en `%LOCALAPPDATA%\Microsoft\WinGet\Packages\...\poppler-25.07.0\`).

## 2. Fuentes editoriales de referencia (BUENO.docx / MALO.docx)

Búsqueda explícita en todo el repositorio: no existen. Se continuó sin
inventarlos, aplicando el design system provisional (nivel 4) del skill
`sapi-professional-word` como único punto de partida — sobrio, técnico,
sin degradados/emojis/iconografía decorativa, un único acento discreto
(`#3E5C58`, usado solo en el recuadro "Modelo D" de las figuras).

## 3. Estructura generada

Portada tipográfica (sin logo — ninguno disponible localmente y
verificable; nunca se descargó ni se inventó uno) → tabla de contenido
(campo real de Word) → resumen ejecutivo → 19 secciones numeradas →
Referencias → índice de Anexos → Anexos A-G (cada uno en página nueva,
con tabla(s) resumen real(es) tomada(s) del documento congelado que le
corresponde). Encabezado "S.A.P.I. — Hito 1" y pie "Universidad Andrés
Bello | INSW421" + número de página desde la primera página posterior a
portada (portada sin encabezado/pie/número).

## 4. Figuras

Dos figuras generadas con un script propio (PIL,
`artifacts/hito1/final-report/build/generate_figures.py`), visualizando
en PNG los dos diagramas ASCII que `docs/arquitectura-hito1.md` (Figura
1 y Figura 2) ya documenta — no se inventó ningún componente ni
resultado nuevo, solo se representó gráficamente contenido ya congelado,
con estilo plano/técnico (sin iconografía decorativa). No se usaron
imágenes genéricas de incendios/bosques. No existían capturas reales del
dashboard localizables en el repositorio (solo assets internos de
librerías de terceros en `.venv/`, irrelevantes) — se optó por no incluir
galería de prototipo en vez de usar una imagen no representativa.

## 5. Formato aplicado

A4, márgenes 2.5/2.5/3.0/2.5 cm (sup/inf/izq/der). Fuente especificada:
**Aptos, 11 pt** (cuerpo), tal como exige el encargo. **Nota de entorno
verificada:** esta máquina Windows no tiene la fuente Aptos instalada
(`C:\Windows\Fonts` no la contiene) — LibreOffice, al renderizar el PDF
de verificación, sustituye Aptos por una fuente serif de reemplazo (no
se instaló ninguna fuente para esta fase, según instrucción explícita).
El DOCX en sí especifica "Aptos" correctamente en sus estilos; al abrirse
en una instalación de Microsoft Word con Aptos disponible (Office 365 /
2021+), se renderizará con la tipografía correcta. Esto se documenta
como limitación del entorno de verificación, no como defecto del
archivo. Jerarquía: H1 16 pt bold con regla inferior fina, H2 13 pt bold,
H3 11 pt bold itálica, cuerpo 11 pt interlineado 1.15 justificado, tablas
9-10 pt (`TableTextPar`, 9.5 pt), captions 9 pt.

## 6. Referencias — decisión sobre Horn (1981)

No se completó título, revista, volumen ni páginas de memoria. El código
del proyecto (`src/procesamiento/dem_terrain.py`) solo cita "Horn
(1981)" sin esos datos. No hubo acceso verificable a una fuente
bibliográfica primaria en esta fase para completar la cita con
seguridad. **Decisión:** la referencia se mantiene en la bibliografía
del informe explícitamente marcada `[PENDING_VERIFICATION]`, con una
nota que explica exactamente qué falta verificar — no se omitió (porque
sí sustenta una afirmación real del texto, el algoritmo de
pendiente/orientación) y no se completó con datos ficticios.

**HORN_1981: PARTIAL** — autor y año verificados (aparecen en el código);
título/revista/páginas no verificados, marcados como tales.

## 7. Iteraciones de QA visual (resumen — detalle en visual-qa.md)

- **Iteración 1** (23 páginas): defecto crítico real encontrado — las
  dos figuras se generaron con dimensiones en píxeles mal calculadas
  (una `heightPx` incorrecta pasada a la función `figure()`, más una
  fórmula de escala que producía imágenes de ~10×13 pulgadas), causando
  que ambas imágenes se desbordaran de la página y dejaran páginas casi
  vacías antes de ellas (página 5: ~90% en blanco).
- **Iteración 2** (20 páginas): corregido el cálculo de tamaño de
  imagen (ancho fijo 13,5 cm, alto proporcional real). Nuevo defecto
  encontrado: 3 tablas (Anexo B ×2, Anexo D) excedían el ancho disponible
  entre márgenes (16,0 cm contra 15,5 cm disponibles), causando que
  "PARCIALMENTE_VERIFICADO" se partiera a mitad de palabra en el Anexo D.
- **Iteración 3** (20 páginas): anchos de columna corregidos en las 3
  tablas señaladas más un ajuste de legibilidad en la tabla del Anexo E
  (Categoría/Prioridad). `CRITICAL_VISUAL_ISSUES: 0` confirmado por
  inspección completa de las 20 páginas.

## 8. Corrección quirúrgica post-entrega (07-09-2026)

Tras revisión externa del PDF de la iteración 4, se aplicaron 4
correcciones factuales de texto y 1 corrección de maquetación,
todas descritas en detalle en `visual-qa.md`, iteración 5:

1. `docs/informe-hito1-final.md` (fuente canónica) corregido en los 4
   puntos exactos — este es el único documento "congelado" que se
   modificó, y solo porque el propio DOCX no puede contradecir a su
   fuente sin invalidar el principio de fuente única de contenido.
2. `generate_docx.js` actualizado línea por línea para que el texto
   transcrito coincida exactamente con el Markdown corregido —
   verificado con `grep` (ausencia de las 4 frases incorrectas,
   presencia de las 4 correctas, en ambos archivos).
3. Corrección de maquetación (orfandad del índice de Anexos): ver
   detalle técnico en `visual-qa.md`, iteración 5. Solo se tocó
   espaciado/`keepNext` en `generate_docx.js` — cero cambios de
   contenido, cero reducción de fuente.
4. Ningún otro documento congelado (`arquitectura-hito1.md`,
   `testing-evidencia-hito1.md`, `trazabilidad-hito1.md`,
   `atributos-calidad-hito1.md`, `riesgos-hito1.md`,
   `versionamiento-hito1.md`, `calidad-codigo-hito1.md`,
   `cierre-sprint1-hito1.md`) fue reabierto ni modificado.

## 9. Contenido — verificación de no alteración

Cifras verificadas contra `docs/informe-hito1-final.md` tras la
generación (470/470, 91,72%, 188/188, 80,34%, 34/21/13,
`v1.0.0-sprint1-verified`, las cinco secciones de limitaciones, las 16
brechas históricas): coinciden exactamente. `CONTENT_CHANGED: NO`.

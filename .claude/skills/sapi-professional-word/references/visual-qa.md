# Visual QA — sapi-professional-word

QA visual obligatorio, no opcional, para todo DOCX producido con este
skill. Verificado como proceso real en el smoke test editorial
(2026-09-07, `artifacts/editorial-smoke/`, 3 iteraciones, 2 hallazgos
reales corregidos).

## Lo que NUNCA cuenta como QA

No se permite reportar `VISUAL_QA: PASS` únicamente porque:

- el DOCX abre sin error,
- el PDF existe en disco,
- el script de conversión terminó sin lanzar una excepción.

Estas tres cosas son precondiciones para hacer QA, no el QA en sí.

## Ciclo obligatorio

```
generar DOCX
   |
   v
validar estructura (scripts/office/validate.py del skill oficial)
   |
   v
convertir a PDF (tools/document_pipeline/libreoffice_convert.py en Windows)
   |
   v
renderizar TODAS las páginas a PNG (pdftoppm)
   |
   v
inspeccionar TODAS las páginas, una por una (leer cada imagen)
   |
   v
corregir cualquier hallazgo real
   |
   v
regenerar -> reconvertir -> re-renderizar -> re-inspeccionar
```

Repetir el ciclo hasta que una pasada completa no produzca hallazgos
nuevos. No hay un número fijo de iteraciones -- el smoke test usó 3
porque hicieron falta 3; un documento distinto puede necesitar más o
menos, pero el mínimo es una inspección completa que efectivamente no
encuentre nada que corregir.

## Qué revisar en CADA página (no solo en las que "parecen importantes")

- **Márgenes**: consistentes con el resto del documento, sin texto
  pegado al borde.
- **Clipping**: ningún texto, tabla o imagen cortado por el borde de la
  página o por un elemento superpuesto.
- **Overflow**: ningún contenido que se salga del área de texto (una
  tabla más ancha que el margen, una imagen que invade el header/footer).
- **Jerarquía**: los encabezados presentes en la página se distinguen
  correctamente entre sí y del cuerpo.
- **Tipografía**: la fuente y el tamaño son los definidos por los
  estilos, sin mezcla accidental de fuentes.
- **Densidad**: ni un bloque de texto agobiante sin respiro, ni una
  página con una sola línea de contenido perdida en blanco.
- **Whitespace**: el espacio en blanco es intencional (cierre de
  sección, margen) y no el síntoma de un salto de página mal puesto.
- **Tablas**: encabezado distinguible, bordes finos consistentes,
  ninguna fila cortada de forma absurda entre dos páginas.
- **Figuras**: legibles a la resolución renderizada, sin pixelado
  visible, con su caption inmediatamente debajo y sin separarse de él.
- **Captions**: presentes, con el estilo `Caption`, numeración
  consistente (Figura 1, Tabla 1, Tabla 2... sin saltos ni repeticiones).
- **Headers/footers**: presentes donde corresponde, ausentes donde el
  diseño lo pide (p. ej. la portada sin número de página), texto
  correcto, sin duplicarse con el título de la página.
- **Numeración de página**: correcta, secuencial, coherente con dónde
  arranca la numeración visible.
- **Títulos huérfanos**: ningún encabezado solo al final de una página
  con su contenido empezando en la siguiente.
- **Viudas/huérfanas**: ninguna página que termine con una sola línea de
  un párrafo que continúa en la siguiente (o que empiece con la última
  línea de un párrafo de la anterior).
- **Páginas casi vacías**: ninguna página con menos de ~30% de
  contenido real salvo que exista una razón editorial explícita y
  documentada (p. ej. el cierre natural de una sección justo antes de
  que la siguiente abra en página propia por convención).

## Registro de la revisión

Cada revisión real se documenta en un `qa-notes.md` propio del
documento (mismo formato usado en
`artifacts/editorial-smoke/qa-notes.md`):

```
## Iteraciones
1. vX: <qué se generó, qué se encontró>
2. vY: <qué se corrigió, qué pasó>
...

## Revisión página por página (versión final)

**Página N (<contenido>) — PASS / FIX**
<observaciones concretas -- qué se revisó y qué se vio, no solo "se ve bien">
```

Un veredicto sin observaciones concretas por página no es una revisión,
es una afirmación sin evidencia -- exactamente lo que este skill existe
para evitar.

## Caso especial: campos de Word que no se actualizan en conversión headless

Si el documento usa un campo de Word (tabla de contenidos, numeración
automática de figuras/tablas vía `SEQ`, etc.) que depende de que Word
recalcule su valor al abrir el archivo, y la herramienta de conversión
usada para el render (LibreOffice headless, en esta configuración) no
ejecuta esa actualización, **documentarlo explícitamente en las notas de
QA de esa página** -- nunca simular el resultado esperado ni describir
el campo como "actualizado" cuando el render muestra lo contrario. Esto
no es un fallo de QA en sí mismo si está documentado; sí lo es si se
oculta.

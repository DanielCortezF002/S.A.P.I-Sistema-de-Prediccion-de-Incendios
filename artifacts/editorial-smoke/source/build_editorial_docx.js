/**
 * Smoke test editorial DOCX (2026-09-07) -- documento FICTICIO de prueba,
 * no forma parte de la documentación oficial de S.A.P.I. ni del Hito.
 *
 * Construye editorial-smoke.docx con control explícito de: estilos de
 * párrafo (Title/Subtitle/Heading 1-3/Normal/Caption/Table Text/
 * Reference), dos secciones (portada sin numeración + cuerpo con
 * header/footer/numeración), tabla de contenidos por campo (requiere
 * actualización de campos -- ver qa-notes.md), dos tablas, una figura
 * con caption, referencias cruzadas en el cuerpo, control de
 * paginación (keepNext/keepLines/widowControl/cantSplit) y tres
 * referencias bibliográficas ficticias marcadas [DEMO].
 *
 * Infraestructura de prueba únicamente (artifacts/editorial-smoke/).
 * No modifica src/, app/, tests/, data/ ni el skill oficial.
 */

const fs = require("fs");
const path = require("path");
const {
  Document,
  Packer,
  Paragraph,
  TextRun,
  HeadingLevel,
  AlignmentType,
  Header,
  Footer,
  PageNumber,
  Table,
  TableRow,
  TableCell,
  WidthType,
  BorderStyle,
  ImageRun,
  TableOfContents,
  LevelFormat,
  convertInchesToTwip,
} = require("docx");

// ---- Paleta y tipografía --------------------------------------------
const INK = "2B2B2B";
const MUTED = "595959";
const ACCENT = "3E5C58"; // único acento (verde-azulado apagado), no azul/morado
const RULE = "BFBFBF";

const FONT_HEADING = "Calibri Light";
const FONT_HEADING_BOLD = "Calibri";
const FONT_BODY = "Constantia";

// A4, márgenes ~2.5 cm.
const PAGE = {
  size: { width: 11906, height: 16838 },
  margin: { top: 1417, bottom: 1417, left: 1417, right: 1417 },
};

const FIGURE_PATH = path.join(__dirname, "figures", "architecture-figure.png");
const OUT_PATH = path.join(__dirname, "..", "editorial-smoke.docx");

// ---- Helpers -----------------------------------------------------------

function body(text, opts = {}) {
  return new Paragraph({
    style: "NormalPar",
    children: [new TextRun({ text, italics: opts.italics, bold: opts.bold })],
  });
}

function heading1(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(text)] });
}
function heading2(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(text)] });
}
function heading3(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_3, children: [new TextRun(text)] });
}

function caption(text) {
  return new Paragraph({
    style: "CaptionPar",
    keepLines: true,
    children: [new TextRun(text)],
  });
}

function cellText(text, opts = {}) {
  return new TableCell({
    width: opts.width ? { size: opts.width, type: WidthType.PERCENTAGE } : undefined,
    shading: opts.header ? { fill: "EDEDED" } : undefined,
    margins: { top: 80, bottom: 80, left: 120, right: 120 },
    children: [
      new Paragraph({
        style: "TableTextPar",
        alignment: opts.align || AlignmentType.LEFT,
        children: [new TextRun({ text, bold: !!opts.header })],
      }),
    ],
  });
}

const THIN_BORDER = { style: BorderStyle.SINGLE, size: 4, color: "8C8C8C" };
const TABLE_BORDERS = {
  top: THIN_BORDER,
  bottom: THIN_BORDER,
  left: THIN_BORDER,
  right: THIN_BORDER,
  insideHorizontal: { style: BorderStyle.SINGLE, size: 2, color: "D9D9D9" },
  insideVertical: { style: BorderStyle.SINGLE, size: 2, color: "D9D9D9" },
};

function makeTable(headerRow, rows) {
  return new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    borders: TABLE_BORDERS,
    rows: [
      new TableRow({
        cantSplit: true,
        tableHeader: true,
        children: headerRow.map((t) => cellText(t, { header: true })),
      }),
      ...rows.map(
        (r) => new TableRow({ cantSplit: true, children: r.map((t) => cellText(t)) })
      ),
    ],
  });
}

// ---- Estilos -------------------------------------------------------

const styles = {
  default: {
    document: {
      run: { font: FONT_BODY, size: 22, color: INK }, // 11pt
      paragraph: {
        spacing: { line: 276, after: 160 }, // ~1.15, 8pt después
        widowControl: true,
      },
    },
  },
  paragraphStyles: [
    {
      id: "Title",
      name: "Title",
      basedOn: "Normal",
      next: "Normal",
      run: { font: FONT_HEADING, size: 56, bold: false, color: INK },
      paragraph: { spacing: { after: 120 }, alignment: AlignmentType.LEFT },
    },
    {
      id: "Subtitle",
      name: "Subtitle",
      basedOn: "Normal",
      next: "Normal",
      run: { font: FONT_HEADING, size: 26, color: MUTED, italics: true },
      paragraph: { spacing: { after: 480 }, alignment: AlignmentType.LEFT },
    },
    {
      id: "Heading1",
      name: "Heading 1",
      basedOn: "Normal",
      next: "Normal",
      quickFormat: true,
      run: { font: FONT_HEADING_BOLD, size: 30, bold: true, color: INK },
      paragraph: {
        spacing: { before: 480, after: 200 },
        keepNext: true,
        border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: RULE, space: 4 } },
      },
    },
    {
      id: "Heading2",
      name: "Heading 2",
      basedOn: "Normal",
      next: "Normal",
      quickFormat: true,
      run: { font: FONT_HEADING_BOLD, size: 25, bold: true, color: INK },
      paragraph: { spacing: { before: 320, after: 140 }, keepNext: true },
    },
    {
      id: "Heading3",
      name: "Heading 3",
      basedOn: "Normal",
      next: "Normal",
      quickFormat: true,
      run: { font: FONT_HEADING_BOLD, size: 22, bold: true, italics: true, color: MUTED },
      paragraph: { spacing: { before: 240, after: 120 }, keepNext: true },
    },
    {
      id: "NormalPar",
      name: "Body Text",
      basedOn: "Normal",
      next: "NormalPar",
      run: { font: FONT_BODY, size: 22, color: INK },
      paragraph: {
        alignment: AlignmentType.JUSTIFIED,
        spacing: { line: 276, after: 160 },
      },
    },
    {
      id: "CaptionPar",
      name: "Caption",
      basedOn: "Normal",
      next: "NormalPar",
      run: { font: FONT_HEADING_BOLD, size: 18, italics: true, color: MUTED },
      paragraph: { alignment: AlignmentType.CENTER, spacing: { before: 80, after: 320 } },
    },
    {
      id: "TableTextPar",
      name: "Table Text",
      basedOn: "Normal",
      next: "TableTextPar",
      run: { font: FONT_BODY, size: 19, color: INK },
      paragraph: { spacing: { after: 40 } },
    },
    {
      id: "ReferencePar",
      name: "Reference",
      basedOn: "Normal",
      next: "ReferencePar",
      run: { font: FONT_BODY, size: 20, color: INK },
      paragraph: {
        spacing: { after: 160 },
        indent: { left: 720, hanging: 720 },
      },
    },
    {
      id: "CoverMeta",
      name: "Cover Meta",
      basedOn: "Normal",
      next: "CoverMeta",
      run: { font: FONT_BODY, size: 22, color: INK },
      paragraph: { spacing: { after: 60 } },
    },
  ],
};

// ---- Portada ---------------------------------------------------------

const coverChildren = [
  new Paragraph({ spacing: { before: 2600 }, children: [] }),
  new Paragraph({
    style: "Title",
    children: [new TextRun("Sistema Geoespacial Experimental de Priorización de Riesgo")],
  }),
  new Paragraph({
    style: "Subtitle",
    children: [new TextRun("Informe técnico de prueba — documento ficticio de demostración editorial")],
  }),
  new Paragraph({
    border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: RULE, space: 8 } },
    spacing: { after: 400 },
    children: [],
  }),
  new Paragraph({ spacing: { before: 1600 }, children: [] }),
  new Paragraph({ style: "CoverMeta", children: [new TextRun({ text: "Institución: ", bold: true }), new TextRun("Universidad Ficticia de Ingeniería Aplicada")] }),
  new Paragraph({ style: "CoverMeta", children: [new TextRun({ text: "Asignatura: ", bold: true }), new TextRun("Seminario de Sistemas de Información Geoespacial (DEMO-101)")] }),
  new Paragraph({ style: "CoverMeta", children: [new TextRun({ text: "Autor: ", bold: true }), new TextRun("J. Pérez Soto (autor ficticio, documento de prueba)")] }),
  new Paragraph({ style: "CoverMeta", children: [new TextRun({ text: "Fecha: ", bold: true }), new TextRun("7 de septiembre de 2026")] }),
  new Paragraph({ spacing: { before: 600 }, children: [
    new TextRun({ text: "Documento de prueba editorial. No forma parte de la documentación oficial de ningún proyecto ni contiene resultados reales.", italics: true, color: MUTED, size: 18 }),
  ] }),
];

// ---- Cuerpo -------------------------------------------------------

const tocSection = [
  heading1("Tabla de contenidos"),
  new Paragraph({
    style: "NormalPar",
    children: [new TextRun({ text: "(Los números de página se actualizan al abrir el documento en Word — ver nota en qa-notes.md.)", italics: true, color: MUTED, size: 18 })],
  }),
  new TableOfContents("Tabla de contenidos", {
    hyperlink: true,
    headingStyleRange: "1-2",
  }),
];

const introSection = [
  heading1("1. Introducción"),
  body(
    "Este informe describe, con fines exclusivamente demostrativos, el diseño conceptual de un sistema geoespacial experimental orientado a la priorización relativa de zonas de interés a partir de variables ambientales y territoriales. El contenido técnico presentado a continuación es ficticio: no corresponde a ningún proyecto real, ni a resultados obtenidos de datos genuinos."
  ),
  body(
    "El propósito de este documento no es comunicar hallazgos, sino servir de prueba de maquetación editorial: verificar que un flujo de generación de documentos Word pueda producir un informe técnico con la sobriedad y consistencia tipográfica esperadas de un trabajo académico redactado cuidadosamente."
  ),
  body(
    "Las secciones siguientes describen, en un nivel puramente ilustrativo, la arquitectura conceptual del sistema de prueba, la metodología asumida y un conjunto de resultados ficticios presentados únicamente para ejercitar el diseño de tablas y figuras."
  ),
  body(
    "Cabe insistir en que la ausencia de resultados reales es intencional: el objetivo de este ejercicio es exclusivamente editorial, no científico. Cualquier similitud entre el contenido de este documento y un sistema existente es incidental y no debe interpretarse como una descripción técnica válida de ningún proyecto en curso."
  ),
];

const architectureSection = [
  heading1("2. Arquitectura"),
  body(
    "La arquitectura conceptual del sistema de prueba se organiza en cuatro etapas secuenciales, alimentadas por un conjunto de fuentes de datos ficticias. Como se observa en la Figura 1, cada etapa recibe la salida de la etapa anterior sin retroalimentación directa, lo que simplifica el análisis de trazabilidad entre insumos y resultados."
  ),
  new Paragraph({
    keepNext: true,
    alignment: AlignmentType.CENTER,
    spacing: { before: 160 },
    children: [
      new ImageRun({
        type: "png",
        data: fs.readFileSync(FIGURE_PATH),
        transformation: { width: 500, height: 175 },
      }),
    ],
  }),
  caption("Figura 1. Arquitectura conceptual del sistema experimental (demo)."),
  heading2("2.1 Componentes principales"),
  body(
    "La Tabla 1 resume los componentes conceptuales considerados en esta prueba, junto con su función declarada y su estado dentro del ejercicio de demostración. Ningún componente listado corresponde a una implementación real."
  ),
  new Paragraph({ keepNext: true, children: [] }),
  makeTable(
    ["Componente", "Función declarada (demo)", "Estado"],
    [
      ["Adquisición de datos", "Recepción de insumos experimentales ficticios", "Ilustrativo"],
      ["Procesamiento", "Normalización de formatos de entrada (demo)", "Ilustrativo"],
      ["Modelo de inferencia", "Cálculo de una prioridad relativa ficticia", "Ilustrativo"],
      ["Panel de visualización", "Presentación tabular de resultados de prueba", "Ilustrativo"],
    ]
  ),
];

const methodologySection = [
  heading1("3. Metodología"),
  body(
    "La metodología descrita en esta sección es enteramente ficticia y se presenta únicamente para ejercitar la jerarquía de encabezados de tres niveles y la redacción de párrafos de extensión natural, similares a los que aparecerían en un informe técnico real."
  ),
  heading2("3.1 Recolección de datos (ficticia)"),
  body(
    "En este escenario de prueba se asume la existencia de un conjunto de observaciones sintéticas recolectadas en un periodo arbitrario. No se utilizó ninguna fuente de datos real para construir este documento; cualquier cifra mencionada más adelante tiene carácter puramente ilustrativo."
  ),
  heading2("3.2 Procesamiento y evaluación (ficticia)"),
  body(
    "El procesamiento hipotético descrito aquí seguiría un esquema convencional de limpieza, normalización y evaluación comparativa entre escenarios. Este párrafo existe principalmente para dar cuerpo a la sección y comprobar que el interlineado y el espaciado posterior se comportan de manera consistente en párrafos de varias líneas."
  ),
  heading3("3.2.1 Detalle experimental (ficticio)"),
  body(
    "Este subapartado de tercer nivel se incluye únicamente para verificar que la jerarquía Heading 3 se distingue con claridad de Heading 2, sin resultar visualmente excesiva."
  ),
];

const resultsSection = [
  heading1("4. Resultados"),
  body(
    "Los resultados presentados en esta sección son completamente ficticios y se incluyen solo para evaluar el diseño de una tabla de datos con encabezado distinguible. La Tabla 2 resume tres escenarios hipotéticos y dos métricas de referencia, sin ninguna relación con resultados reales de ningún sistema."
  ),
  new Paragraph({ keepNext: true, children: [] }),
  makeTable(
    ["Escenario (demo)", "Métrica A (ficticia)", "Métrica B (ficticia)", "Observación"],
    [
      ["Escenario 1", "0.41", "0.62", "Valor de referencia ilustrativo"],
      ["Escenario 2", "0.58", "0.49", "Valor de referencia ilustrativo"],
      ["Escenario 3", "0.33", "0.71", "Valor de referencia ilustrativo"],
    ]
  ),
  body(
    "Como puede observarse, los valores ficticios anteriores no permiten ni pretenden sostener ninguna conclusión sustantiva; su único objetivo es ejercitar el formato tabular del documento."
  ),
  heading2("4.1 Discusión de los resultados (ficticia)"),
  body(
    "Aun tratándose de cifras inventadas, esta subsección se incluye para comprobar que un encabezado de segundo nivel inmediatamente posterior a una tabla conserva un espaciado consistente con el resto del documento, sin quedar visualmente pegado a la fila final de la Tabla 2."
  ),
  body(
    "En un informe real, esta subsección discutiría las diferencias entre escenarios, su significancia y las limitaciones metodológicas correspondientes. Aquí basta con señalar que ninguna de esas discusiones aplica, dado el carácter puramente demostrativo del contenido."
  ),
];

const conclusionsSection = [
  heading1("5. Conclusiones"),
  body(
    "Este documento demostró, sobre contenido ficticio, la generación de un informe técnico con portada sobria, tabla de contenidos por campo, jerarquía de encabezados de tres niveles, dos tablas con encabezado distinguible, una figura con caption y referencias cruzadas naturales en el cuerpo del texto."
  ),
  body(
    "Ninguna de las afirmaciones, cifras o componentes descritos en este informe corresponde a un sistema real. El documento cumple exclusivamente una función de prueba editorial dentro de un flujo de generación de documentos Word."
  ),
  body(
    "Como siguiente paso dentro del ejercicio de prueba, este flujo de generación se convertiría en un skill reutilizable, con reglas de estilo fijas, para producir informes técnicos reales con la misma consistencia editorial demostrada aquí."
  ),
];

const referencesSection = [
  new Paragraph({ children: [], pageBreakBefore: true }),
  heading1("Referencias"),
  new Paragraph({
    style: "ReferencePar",
    children: [
      new TextRun("[DEMO] Pérez Soto, J. (2026). "),
      new TextRun({ text: "Modelos conceptuales de priorización geoespacial: un ejercicio ilustrativo. ", italics: true }),
      new TextRun("Editorial Ficticia Universitaria."),
    ],
  }),
  new Paragraph({
    style: "ReferencePar",
    children: [
      new TextRun("[DEMO] Gómez Ruiz, A. y Fernández Lara, T. (2025). "),
      new TextRun({ text: "Arquitecturas de referencia para sistemas de apoyo a decisión (demo). ", italics: true }),
      new TextRun("Revista Ficticia de Ingeniería Aplicada, 12(3), 45–58."),
    ],
  }),
  new Paragraph({
    style: "ReferencePar",
    children: [
      new TextRun("[DEMO] Instituto Ficticio de Estudios Territoriales. (2024). "),
      new TextRun({ text: "Guía metodológica de prueba para sistemas experimentales. ", italics: true }),
      new TextRun("Documento interno de demostración."),
    ],
  }),
];

// ---- Documento -------------------------------------------------------

const bodyHeader = new Header({
  children: [
    new Paragraph({
      border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: RULE, space: 4 } },
      alignment: AlignmentType.RIGHT,
      children: [new TextRun({ text: "Informe técnico experimental", size: 16, color: MUTED, font: FONT_HEADING_BOLD })],
    }),
  ],
});

const bodyFooter = new Footer({
  children: [
    new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [new TextRun({ children: [PageNumber.CURRENT], size: 18, color: MUTED, font: FONT_HEADING_BOLD })],
    }),
  ],
});

const doc = new Document({
  creator: "Documento de prueba (ficticio)",
  title: "Sistema Geoespacial Experimental de Priorización de Riesgo (DEMO)",
  description: "Smoke test editorial DOCX -- documento ficticio, no forma parte de S.A.P.I.",
  features: { updateFields: true },
  styles,
  sections: [
    {
      properties: { page: PAGE, titlePage: true },
      headers: { default: new Header({ children: [new Paragraph({ children: [] })] }) },
      footers: { default: new Footer({ children: [new Paragraph({ children: [] })] }) },
      children: coverChildren,
    },
    {
      properties: {
        page: { ...PAGE, pageNumbers: { start: 1 } },
      },
      headers: { default: bodyHeader },
      footers: { default: bodyFooter },
      children: [
        // Iteración 2 (QA visual): se retiraron los saltos de página
        // manuales que había aquí antes -- forzaban una página casi vacía
        // tras la TOC (el campo no se puebla en la conversión headless) y
        // dejaban la Tabla 1 aislada con exceso de blanco debajo. El flujo
        // natural + keepNext en encabezados/figuras/filas de tabla ya
        // resuelve la paginación sin desperdiciar página.
        ...tocSection,
        ...introSection,
        ...architectureSection,
        ...methodologySection,
        ...resultsSection,
        ...conclusionsSection,
        ...referencesSection,
      ],
    },
  ],
});

Packer.toBuffer(doc).then((buffer) => {
  fs.writeFileSync(OUT_PATH, buffer);
  console.log(`Escrito ${OUT_PATH} (${buffer.length} bytes)`);
});

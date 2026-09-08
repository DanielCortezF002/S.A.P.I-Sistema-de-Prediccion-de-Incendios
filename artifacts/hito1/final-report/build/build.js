const fs = require("fs");
const path = require("path");
const {
  Document, Packer, HeadingLevel, AlignmentType, BorderStyle,
  Header, Footer, Paragraph, TextRun, PageNumber, LevelFormat,
} = require("docx");

const { cover, tocPage, front, sec, CM } = require("./generate_docx.js");
const { annexes } = require("./generate_annexes.js");

const INK = "2B2B2B";
const INK_SOFT = "595959";
const LINE_LIGHT = "BFBFBF";
const ACCENT = "3E5C58";

const margins = {
  top: CM(2.5), bottom: CM(2.5), left: CM(3.0), right: CM(2.5),
};

const header = new Header({
  children: [new Paragraph({
    border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: LINE_LIGHT, space: 4 } },
    children: [new TextRun({ text: "S.A.P.I. — Hito 1", size: 18, color: INK_SOFT })],
  })],
});

const footer = new Footer({
  children: [new Paragraph({
    alignment: AlignmentType.CENTER,
    border: { top: { style: BorderStyle.SINGLE, size: 4, color: LINE_LIGHT, space: 4 } },
    children: [
      new TextRun({ text: "Universidad Andrés Bello | INSW421   ", size: 18, color: INK_SOFT }),
      new TextRun({ children: [PageNumber.CURRENT], size: 18, color: INK_SOFT }),
    ],
  })],
});

const emptyHeader = new Header({ children: [new Paragraph({ children: [] })] });
const emptyFooter = new Footer({ children: [new Paragraph({ children: [] })] });

const doc = new Document({
  creator: "Daniel Gonzalo Cortez Fierro",
  title: "S.A.P.I. — Informe de Hito 1 / Sprint 1",
  features: { updateFields: true },
  numbering: {
    config: [{
      reference: "bullets",
      levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: CM(0.6), hanging: CM(0.35) } } } }],
    }],
  },
  styles: {
    default: {
      document: { run: { font: "Aptos", size: 22, color: INK } }, // 11pt
    },
    paragraphStyles: [
      {
        id: "NormalPar", name: "Normal Par", basedOn: "Normal", next: "NormalPar",
        run: { font: "Aptos", size: 22, color: INK },
        paragraph: { spacing: { line: 276, after: 120 } }, // 1.15 interlineado, 6pt despues
      },
      {
        id: "TableTextPar", name: "Table Text", basedOn: "Normal", next: "TableTextPar",
        run: { font: "Aptos", size: 19, color: INK }, // 9.5pt
        paragraph: { spacing: { line: 260, after: 0 } },
      },
      {
        id: "CaptionPar", name: "Caption Par", basedOn: "Normal", next: "NormalPar",
        run: { font: "Aptos", size: 18, color: INK_SOFT, italics: true },
      },
      {
        id: "ReferencePar", name: "Reference Par", basedOn: "Normal", next: "NormalPar",
        run: { font: "Aptos", size: 19, color: INK_SOFT },
      },
      {
        id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "NormalPar", quickFormat: true,
        run: { font: "Aptos", size: 32, bold: true, color: INK }, // 16pt
        paragraph: { spacing: { before: 360, after: 200 }, keepNext: true,
          border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: LINE_LIGHT, space: 4 } } },
      },
      {
        id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "NormalPar", quickFormat: true,
        run: { font: "Aptos", size: 26, bold: true, color: INK }, // 13pt
        paragraph: { spacing: { before: 240, after: 140 }, keepNext: true },
      },
      {
        id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "NormalPar", quickFormat: true,
        run: { font: "Aptos", size: 22, bold: true, italics: true, color: INK }, // 11pt bold italic
        paragraph: { spacing: { before: 180, after: 100 }, keepNext: true },
      },
    ],
  },
  sections: [
    {
      properties: {
        page: { size: { width: CM(21.0), height: CM(29.7) }, margin: margins },
        titlePage: true,
      },
      headers: { default: emptyHeader, first: emptyHeader },
      footers: { default: emptyFooter, first: emptyFooter },
      children: cover,
    },
    {
      properties: {
        page: {
          size: { width: CM(21.0), height: CM(29.7) },
          margin: margins,
          pageNumberStart: 1,
        },
      },
      headers: { default: header },
      footers: { default: footer },
      children: [...tocPage, ...front, ...sec, ...annexes()],
    },
  ],
});

const outDir = path.join(__dirname, "out");
fs.mkdirSync(outDir, { recursive: true });
Packer.toBuffer(doc).then((buf) => {
  const outFile = path.join(outDir, "SAPI_Hito1_Informe_Final.docx");
  fs.writeFileSync(outFile, buf);
  console.log("OK ->", outFile, buf.length, "bytes");
});

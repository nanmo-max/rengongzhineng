"use strict";

const fs = require("fs");
const path = require("path");
const {
  AlignmentType,
  BorderStyle,
  Document,
  Footer,
  HeadingLevel,
  PageBreak,
  PageNumber,
  Packer,
  Paragraph,
  ShadingType,
  Table,
  TableCell,
  TableOfContents,
  TableRow,
  TextRun,
  VerticalAlign,
  WidthType,
} = require("docx");

const ROOT = path.resolve(__dirname, "..");
const sourcePath = process.argv[2]
  ? path.resolve(process.argv[2])
  : path.join(ROOT, "docs", "SUBMISSION_DOCUMENT.md");
const outputPath = process.argv[3]
  ? path.resolve(process.argv[3])
  : path.join(ROOT, "artifacts", "submission", "BRACE-MSI-作品说明书.docx");

const markdown = fs.readFileSync(sourcePath, "utf8").replace(/\r\n/g, "\n");
const lines = markdown.split("\n");

const borders = {
  top: { style: BorderStyle.SINGLE, size: 1, color: "B7C5D5" },
  bottom: { style: BorderStyle.SINGLE, size: 1, color: "B7C5D5" },
  left: { style: BorderStyle.SINGLE, size: 1, color: "B7C5D5" },
  right: { style: BorderStyle.SINGLE, size: 1, color: "B7C5D5" },
  insideHorizontal: { style: BorderStyle.SINGLE, size: 1, color: "DCE4EC" },
  insideVertical: { style: BorderStyle.SINGLE, size: 1, color: "DCE4EC" },
};

function inlineRuns(text, options = {}) {
  const result = [];
  const pattern = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let cursor = 0;
  let match;
  while ((match = pattern.exec(text)) !== null) {
    if (match.index > cursor) {
      result.push(new TextRun({ text: text.slice(cursor, match.index), ...options }));
    }
    const token = match[0];
    if (token.startsWith("**")) {
      result.push(new TextRun({ text: token.slice(2, -2), bold: true, ...options }));
    } else {
      result.push(
        new TextRun({
          text: token.slice(1, -1),
          font: "Consolas",
          color: "315C86",
          ...options,
        })
      );
    }
    cursor = match.index + token.length;
  }
  if (cursor < text.length) {
    result.push(new TextRun({ text: text.slice(cursor), ...options }));
  }
  return result.length ? result : [new TextRun({ text, ...options })];
}

function makeTable(rows) {
  const columnCount = Math.max(...rows.map((row) => row.length));
  const totalWidth = 9026;
  const baseWidth = Math.floor(totalWidth / columnCount);
  const widths = Array.from({ length: columnCount }, (_, index) =>
    index === columnCount - 1 ? totalWidth - baseWidth * (columnCount - 1) : baseWidth
  );
  return new Table({
    width: { size: totalWidth, type: WidthType.DXA },
    columnWidths: widths,
    borders,
    rows: rows.map(
      (row, rowIndex) =>
        new TableRow({
          tableHeader: rowIndex === 0,
          children: widths.map(
            (width, columnIndex) =>
              new TableCell({
                width: { size: width, type: WidthType.DXA },
                verticalAlign: VerticalAlign.CENTER,
                shading:
                  rowIndex === 0
                    ? { fill: "DCEAF7", type: ShadingType.CLEAR, color: "auto" }
                    : undefined,
                margins: { top: 100, bottom: 100, left: 120, right: 120 },
                children: [
                  new Paragraph({
                    spacing: { before: 0, after: 0 },
                    children: inlineRuns(row[columnIndex] || "", {
                      bold: rowIndex === 0,
                      size: 18,
                    }),
                  }),
                ],
              })
          ),
        })
    ),
  });
}

function parseBody() {
  const children = [];
  let index = 0;
  let skippedTitle = false;
  while (index < lines.length) {
    const raw = lines[index].trimEnd();
    const line = raw.trim();
    if (!line) {
      index += 1;
      continue;
    }
    if (line.startsWith("# ") && !skippedTitle) {
      skippedTitle = true;
      index += 1;
      continue;
    }
    if (line.startsWith("> ")) {
      index += 1;
      continue;
    }
    if (line.startsWith("## ")) {
      children.push(
        new Paragraph({
          text: line.slice(3),
          heading: HeadingLevel.HEADING_1,
          pageBreakBefore: line.startsWith("## 1.") && children.length > 0,
        })
      );
      index += 1;
      continue;
    }
    if (line.startsWith("### ")) {
      children.push(
        new Paragraph({ text: line.slice(4), heading: HeadingLevel.HEADING_2 })
      );
      index += 1;
      continue;
    }
    if (line.startsWith("|") && index + 1 < lines.length) {
      const tableLines = [];
      while (index < lines.length && lines[index].trim().startsWith("|")) {
        tableLines.push(lines[index].trim());
        index += 1;
      }
      const rows = tableLines
        .filter((value, rowIndex) => rowIndex !== 1 || !/^\|[\s:|-]+\|$/.test(value))
        .map((value) =>
          value
            .slice(1, -1)
            .split("|")
            .map((cell) => cell.trim())
        );
      children.push(makeTable(rows));
      children.push(new Paragraph({ spacing: { after: 80 } }));
      continue;
    }
    if (line.startsWith("- ")) {
      children.push(
        new Paragraph({
          numbering: { reference: "brace-bullets", level: 0 },
          children: inlineRuns(line.slice(2)),
        })
      );
      index += 1;
      continue;
    }
    if (/^\d+\.\s/.test(line)) {
      children.push(
        new Paragraph({
          numbering: { reference: "brace-numbers", level: 0 },
          children: inlineRuns(line.replace(/^\d+\.\s/, "")),
        })
      );
      index += 1;
      continue;
    }
    const paragraphLines = [line];
    index += 1;
    while (index < lines.length) {
      const next = lines[index].trim();
      if (
        !next ||
        next.startsWith("#") ||
        next.startsWith(">") ||
        next.startsWith("|") ||
        next.startsWith("- ") ||
        /^\d+\.\s/.test(next)
      ) {
        break;
      }
      paragraphLines.push(next);
      index += 1;
    }
    children.push(
      new Paragraph({
        alignment: AlignmentType.JUSTIFIED,
        children: inlineRuns(paragraphLines.join(" ")),
      })
    );
  }
  return children;
}

const cover = [
  new Paragraph({ spacing: { before: 1200, after: 300 } }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 260 },
    children: [
      new TextRun({
        text: "BRACE-MSI",
        bold: true,
        size: 52,
        color: "194F78",
        font: "Microsoft YaHei",
      }),
    ],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 720 },
    children: [
      new TextRun({
        text: "面向工业模型漂移的预算—风险约束自主迭代引擎",
        bold: true,
        size: 30,
        color: "243B53",
        font: "Microsoft YaHei",
      }),
    ],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 140 },
    children: [new TextRun({ text: "智训引擎赛题作品说明书", size: 26 })],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 900 },
    children: [new TextRun({ text: "BRACE-MSI-0.3.0rc3", size: 22, color: "52677B" })],
  }),
  new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun("参赛团队：BRACE-MSI项目组")] }),
  new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun("指导教师：暂不填写")] }),
  new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun("2026年11月13日")] }),
  new Paragraph({ children: [new PageBreak()] }),
  new Paragraph({ text: "目录", heading: HeadingLevel.HEADING_1 }),
  new TableOfContents("目录", { hyperlink: true, headingStyleRange: "1-2" }),
  new Paragraph({ children: [new PageBreak()] }),
];

const doc = new Document({
  creator: "BRACE-MSI Team",
  title: "BRACE-MSI作品说明书",
  description: "面向工业模型漂移的预算—风险约束自主迭代引擎",
  styles: {
    default: {
      document: {
        run: { font: "Microsoft YaHei", size: 21, color: "1F2933" },
        paragraph: { spacing: { line: 360, after: 120 } },
      },
      heading1: {
        run: { font: "Microsoft YaHei", size: 30, bold: true, color: "194F78" },
        paragraph: { spacing: { before: 280, after: 140 }, outlineLevel: 0 },
      },
      heading2: {
        run: { font: "Microsoft YaHei", size: 25, bold: true, color: "315C86" },
        paragraph: { spacing: { before: 220, after: 100 }, outlineLevel: 1 },
      },
    },
  },
  numbering: {
    config: [
      {
        reference: "brace-bullets",
        levels: [
          {
            level: 0,
            format: "bullet",
            text: "•",
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 720, hanging: 360 } } },
          },
        ],
      },
      {
        reference: "brace-numbers",
        levels: [
          {
            level: 0,
            format: "decimal",
            text: "%1.",
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 720, hanging: 360 } } },
          },
        ],
      },
    ],
  },
  sections: [
    {
      properties: {
        page: {
          size: { width: 11906, height: 16838 },
          margin: { top: 1276, right: 1276, bottom: 1276, left: 1276 },
        },
      },
      footers: {
        default: new Footer({
          children: [
            new Paragraph({
              alignment: AlignmentType.CENTER,
              children: [
                new TextRun({ text: "BRACE-MSI  |  " }),
                new TextRun({ children: [PageNumber.CURRENT] }),
              ],
            }),
          ],
        }),
      },
      children: [...cover, ...parseBody()],
    },
  ],
});

fs.mkdirSync(path.dirname(outputPath), { recursive: true });
Packer.toBuffer(doc).then((buffer) => {
  fs.writeFileSync(outputPath, buffer);
  process.stdout.write(`${outputPath}\n`);
});


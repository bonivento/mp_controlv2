// Tabla de ingreso manual: borrador editable, pegado desde Excel/Sheets y conversión a CSV.
// Solo maneja texto; interpretar los números (coma decimal incluida) es trabajo de la API
// (`/api/data/parse`), igual que con un archivo subido.

export interface Draft {
  headers: string[];
  /** Filas de texto; todas con `headers.length` celdas. */
  cells: string[][];
}

export const MAX_ROWS = 2000;
export const MAX_COLS = 50;

/** Borrador inicial según el tipo de estudio; los nombres los reconoce el mapeo automático. */
export function initialDraft(attribute: boolean): Draft {
  const headers = attribute ? ["muestra", "inspeccionados", "defectuosos"] : ["subgrupo", "x1", "x2", "x3", "x4", "x5"];
  return { headers, cells: Array.from({ length: 10 }, () => headers.map(() => "")) };
}

/** Filas con algún dato (las totalmente vacías no se envían). */
export const filledRows = (d: Draft) => d.cells.filter((r) => r.some((c) => c.trim() !== ""));

/** Texto pegado desde una hoja de cálculo -> matriz (tabuladores y saltos de línea). */
export function parsePasted(text: string): string[][] {
  const lines = text.replace(/\r\n?/g, "\n").split("\n");
  if (lines.length > 1 && lines[lines.length - 1] === "") lines.pop(); // salto final que añade Excel
  return lines.map((l) => l.split("\t").map((c) => c.trim()));
}

/** ¿El texto pegado ocupa más de una celda? Si no, se deja el pegado normal del navegador. */
export const isBlock = (text: string) => /[\t\n\r]/.test(text.replace(/[\r\n]+$/, ""));

export interface PasteResult {
  draft: Draft;
  /** El bloque superaba MAX_ROWS o MAX_COLS y se recortó. */
  truncated: boolean;
}

/**
 * Reparte `block` desde la celda (row, col). `row = -1` es la fila de encabezados: la primera línea
 * del bloque sustituye nombres de columna y el resto cae en el cuerpo desde la fila 0.
 * Crea filas y columnas si faltan, hasta MAX_ROWS y MAX_COLS.
 */
export function pasteBlock(d: Draft, row: number, col: number, block: string[][]): PasteResult {
  let truncated = false;
  const headers = [...d.headers];
  const cells = d.cells.map((r) => [...r]);
  const width = Math.max(...block.map((r) => r.length));
  const newWidth = Math.min(MAX_COLS, Math.max(headers.length, col + width));
  if (col + width > MAX_COLS) truncated = true;
  while (headers.length < newWidth) headers.push(`columna_${headers.length + 1}`);
  for (const r of cells) while (r.length < newWidth) r.push("");

  let lines = block;
  if (row === -1) {
    lines[0].forEach((v, j) => {
      if (col + j < newWidth) headers[col + j] = v;
    });
    lines = block.slice(1);
  }
  const start = Math.max(row, 0);
  lines.forEach((line, i) => {
    const r = start + i;
    if (r >= MAX_ROWS) {
      truncated = true;
      return;
    }
    while (cells.length <= r) cells.push(headers.map(() => ""));
    line.forEach((v, j) => {
      if (col + j < newWidth) cells[r][col + j] = v;
    });
  });
  return { draft: { headers, cells }, truncated };
}

/**
 * CSV para `/api/data/parse`. Separador `;` y todas las filas con el mismo número de campos, de modo
 * que la detección del lector (que cuenta campos por línea) elige siempre `;` aunque haya comas
 * decimales. Los valores con coma, `;`, comillas o tabulador van entre comillas y se envían tal cual:
 * la API convierte la coma decimal y deja el aviso en la bitácora, como con un archivo.
 */
export function toCsv(d: Draft): string {
  const quote = (v: string) => (/[;,"\t]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v);
  // En los nombres de columna se eliminan comas y `;` para que la primera línea nunca sea ambigua.
  const head = d.headers.map((h) => quote(h.replace(/[;,\t\r\n]+/g, " ").trim()));
  const body = filledRows(d).map((r) => r.map((c) => quote(c.replace(/[\r\n]+/g, " ").trim())));
  return [head, ...body].map((r) => r.join(";")).join("\r\n") + "\r\n";
}

/** Archivo en memoria con el contenido de la tabla, para el mismo camino que una subida. */
export const draftToFile = (d: Draft) => new File([toCsv(d)], "ingreso-manual.csv", { type: "text/csv" });

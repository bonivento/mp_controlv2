// Módulo 1 en modo de ejemplo: lectura de CSV (real, en el navegador) y tabla resumen.

import { fmt, type S } from "./common";
import { MockHttpError, excessKurtosis, mean, quantile, skewness, std } from "./engine";

function splitCsv(text: string): string[][] {
  const clean = text.replace(/^﻿/, "");
  const first = clean.split(/\r?\n/, 1)[0] ?? "";
  const counts = { ",": 0, ";": 0, "\t": 0 };
  for (const ch of first) if (ch in counts) counts[ch as keyof typeof counts]++;
  const delim = (Object.entries(counts).sort((a, b) => b[1] - a[1])[0][0] as string) || ",";
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = "";
  let quoted = false;
  for (let i = 0; i < clean.length; i++) {
    const ch = clean[i];
    if (quoted) {
      if (ch === '"' && clean[i + 1] === '"') {
        cell += '"';
        i++;
      } else if (ch === '"') quoted = false;
      else cell += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === delim) {
      row.push(cell);
      cell = "";
    } else if (ch === "\n" || ch === "\r") {
      if (ch === "\r" && clean[i + 1] === "\n") i++;
      row.push(cell);
      cell = "";
      if (row.some((c) => c.trim() !== "")) rows.push(row);
      row = [];
    } else cell += ch;
  }
  row.push(cell);
  if (row.some((c) => c.trim() !== "")) rows.push(row);
  return rows;
}

const isNum = (s: string) => s.trim() !== "" && Number.isFinite(Number(s.trim().replace(",", ".")));
const ISO_DATE = /^\d{4}-\d{2}-\d{2}([ T]\d{2}:\d{2}(:\d{2})?)?$/;
const DMY_DATE = /^(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})$/;
const isDate = (s: string) => ISO_DATE.test(s.trim()) || DMY_DATE.test(s.trim());
const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;
const toIso = (s: string) => {
  const m = DMY_DATE.exec(s.trim());
  return m ? `${m[3]}-${m[2].padStart(2, "0")}-${m[1].padStart(2, "0")}` : s.trim();
};

/**
 * Lee un CSV en el navegador con la misma forma de respuesta que la API real, incluidos los avisos
 * (`warnings`): uno por tipo de conversión y columna, en español.
 */
export async function mockParse(file: File): Promise<S["ParsedFile"]> {
  if (/\.xlsx?$/i.test(file.name))
    throw new MockHttpError(
      "En modo de ejemplo solo se leen archivos CSV; los Excel (.xlsx) los lee la API real. Guarda la hoja como CSV o espera a la integración.",
      422,
      "mock_unsupported",
    );
  const table = splitCsv(await file.text());
  if (table.length < 2) throw new MockHttpError("El archivo no tiene filas de datos.");
  const header = table[0].map((h, i) => h.trim() || `columna_${i + 1}`);
  const raw = table.slice(1).map((r) => header.map((_, i) => r[i] ?? ""));
  const body = raw.map((r) => r.map((c) => c.trim()));
  const warnings: string[] = [];
  const columns: S["ColumnInfo"][] = header.map((name, c) => {
    const col = `Columna '${name}'`;
    const cells = body.map((r) => r[c]).filter((x) => x !== "");
    if (cells.length === 0) return { name, kind: "empty", missing: body.length };
    const blanks = body.length - cells.length;
    const trimmedCells = raw.filter((r) => r[c].trim() !== "" && r[c] !== r[c].trim()).length;
    if (trimmedCells) warnings.push(`${col}: ${plural(trimmedCells, "celda con espacios", "celdas con espacios")} al inicio o al final, recortados.`);
    const nums = cells.filter(isNum).length;
    if (nums / cells.length >= 0.8) {
      const commas = cells.filter((x) => /^-?\d+,\d+$/.test(x.replace(/\s/g, ""))).length;
      const bad = cells.filter((x) => !isNum(x));
      if (commas) warnings.push(`${col}: ${plural(commas, "valor con coma decimal convertido", "valores con coma decimal convertidos")} a punto.`);
      if (bad.length) {
        const ex = [...new Set(bad)].slice(0, 3).map((e) => `"${e}"`).join(", ");
        warnings.push(`${col}: ${plural(bad.length, "texto no numérico tratado", "textos no numéricos tratados")} como faltante (por ejemplo ${ex}).`);
      }
      if (blanks) warnings.push(`${col}: ${plural(blanks, "celda vacía registrada", "celdas vacías registradas")} como faltante.`);
      return { name, kind: "numeric", missing: body.length - nums };
    }
    if (cells.filter(isDate).length / cells.length >= 0.8) {
      const dmy = cells.filter((x) => DMY_DATE.test(x)).length;
      if (dmy) warnings.push(`${col}: ${plural(dmy, "fecha en formato día/mes/año normalizada", "fechas en formato día/mes/año normalizadas")} a ISO (AAAA-MM-DD).`);
      if (blanks) warnings.push(`${col}: ${plural(blanks, "celda vacía registrada", "celdas vacías registradas")} como faltante.`);
      return { name, kind: "datetime", missing: body.length - cells.length };
    }
    if (blanks) warnings.push(`${col}: ${plural(blanks, "valor de texto vacío registrado", "valores de texto vacíos registrados")} como faltante.`);
    return { name, kind: "text", missing: blanks };
  });
  const rows = body.map((r) =>
    r.map((cell, c) => {
      if (cell === "") return null;
      if (columns[c].kind === "numeric") return isNum(cell) ? Number(cell.replace(",", ".")) : null;
      if (columns[c].kind === "datetime") return isDate(cell) ? toIso(cell) : cell;
      return cell;
    }),
  );
  return { filename: file.name, sheets: [{ name: "CSV", columns, rows, warnings }] };
}

export function describe(all: number[]): S["Descriptive"] {
  const sorted = [...all].sort((a, b) => a - b);
  return {
    count: all.length,
    mean: mean(all),
    std: std(all),
    min: sorted[0],
    q1: quantile(sorted, 0.25),
    median: quantile(sorted, 0.5),
    q3: quantile(sorted, 0.75),
    max: sorted[sorted.length - 1],
    skewness: skewness(all),
    kurtosis: excessKurtosis(all),
  };
}

export function mockSummary(req: S["SummaryRequest"]): S["SummaryResponse"] {
  const subs = req.subgroups.filter((s) => s.length > 0);
  if (subs.length === 0) throw new MockHttpError("No hay subgrupos para resumir.");
  const labels = req.labels ?? req.subgroups.map((_, i) => String(i + 1));
  const summaries: S["SubgroupSummary"][] = req.subgroups.map((s, i) => ({
    label: labels[i] ?? String(i + 1),
    n: s.length,
    mean: s.length ? mean(s) : 0,
    range: s.length > 1 ? Math.max(...s) - Math.min(...s) : null,
    std: s.length > 1 ? std(s) : null,
    min: s.length ? Math.min(...s) : 0,
    max: s.length ? Math.max(...s) : 0,
  }));
  const all = req.subgroups.flat();
  const overall = describe(all);
  const iqr = overall.q3 - overall.q1;
  const lo = overall.q1 - 1.5 * iqr;
  const hi = overall.q3 + 1.5 * iqr;
  const outliers: S["OutlierFlag"][] = [];
  req.subgroups.forEach((s, i) =>
    s.forEach((v, pos) => {
      if (v < lo || v > hi)
        outliers.push({
          subgroup_index: i,
          position: pos,
          value: v,
          reason: `Fuera de [${fmt(lo, 2)}; ${fmt(hi, 2)}] (criterio 1,5·IQR)`,
        });
    }),
  );
  return {
    subgroups: summaries,
    overall,
    constant_size: new Set(req.subgroups.map((s) => s.length)).size === 1,
    outliers,
  };
}

export function mockAttributeSummary(req: S["AttributeSummaryRequest"]): S["AttributeSummaryResponse"] {
  const counts = req.counts;
  if (counts.length === 0) throw new MockHttpError("No hay subgrupos para resumir.");
  const sizes = req.sizes ?? null;
  const labels = req.labels ?? counts.map((_, i) => String(i + 1));
  const rows: S["AttributeSummaryResponse"]["rows"] = counts.map((count, i) => {
    const size = sizes ? sizes[i] : null;
    return { label: labels[i] ?? String(i + 1), count, size, rate: size ? count / size : null };
  });
  const totalCount = counts.reduce((a, b) => a + b, 0);
  const totalSize = sizes ? sizes.reduce((a, b) => a + b, 0) : null;
  const warnings: string[] = [];
  if (sizes && counts.some((c, i) => c > sizes[i])) warnings.push("Hay subgrupos con un conteo mayor que el tamaño de muestra.");
  return {
    rows,
    subgroups: counts.length,
    total_count: totalCount,
    total_size: totalSize,
    overall_rate: totalSize ? totalCount / totalSize : null,
    mean_count: totalCount / counts.length,
    min_size: sizes ? Math.min(...sizes) : null,
    max_size: sizes ? Math.max(...sizes) : null,
    constant_size: sizes ? new Set(sizes).size === 1 : null,
    warnings,
  };
}

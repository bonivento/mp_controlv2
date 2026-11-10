// Formación de subgrupos racionales a partir de una hoja leída por la API (módulo 1).
// Es reorganización de datos, no estadística: agrupar filas según la regla elegida.

import type { components } from "./api-types";
import type { AttributeRow, VariableRow } from "./db-provisional";

type Sheet = components["schemas"]["ParsedSheet"];

export interface VariableConfig {
  layout: "long" | "wide";
  /** long: columna con el valor medido. */
  valueColumn?: string;
  /** wide: columnas con las observaciones de cada subgrupo (una fila = un subgrupo). */
  valueColumns?: string[];
  method: "column" | "fixed_size" | "time";
  /** Columna que identifica el subgrupo (long) o su etiqueta (wide). */
  groupColumn?: string;
  size?: number;
  timeColumn?: string;
  timeUnit?: "hour" | "day" | "week" | "month";
}

export interface Built<T> {
  rows: T[];
  warnings: string[];
  /** Observaciones o filas descartadas por celdas vacías o no numéricas. */
  missing: number;
}

const colIndex = (sheet: Sheet, name?: string) => (name ? sheet.columns.findIndex((c) => c.name === name) : -1);
const num = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);

function bucketKey(raw: unknown, unit: NonNullable<VariableConfig["timeUnit"]>): string | null {
  if (typeof raw !== "string") return null;
  const d = new Date(raw.trim().replace(" ", "T"));
  if (Number.isNaN(d.getTime())) return null;
  const p = (x: number) => String(x).padStart(2, "0");
  const day = `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
  if (unit === "hour") return `${day} ${p(d.getHours())}:00`;
  if (unit === "day") return day;
  if (unit === "month") return `${d.getFullYear()}-${p(d.getMonth() + 1)}`;
  const monday = new Date(d);
  monday.setDate(d.getDate() - ((d.getDay() + 6) % 7));
  return `Semana de ${monday.getFullYear()}-${p(monday.getMonth() + 1)}-${p(monday.getDate())}`;
}

export function buildVariableSubgroups(sheet: Sheet, cfg: VariableConfig): Built<VariableRow> {
  const warnings: string[] = [];
  let missing = 0;
  const rows: VariableRow[] = [];

  if (cfg.layout === "wide") {
    const cols = (cfg.valueColumns ?? []).map((c) => colIndex(sheet, c)).filter((i) => i >= 0);
    if (!cols.length) return { rows, warnings: ["Elige las columnas con las observaciones de cada subgrupo."], missing };
    const lab = colIndex(sheet, cfg.groupColumn);
    sheet.rows.forEach((r, k) => {
      const vals = cols.map((i) => num(r[i]));
      const good = vals.filter((v): v is number => v != null);
      missing += vals.length - good.length;
      if (good.length === 0) return;
      rows.push({ label: lab >= 0 && r[lab] != null ? String(r[lab]) : String(k + 1), values: good });
    });
  } else {
    const vi = colIndex(sheet, cfg.valueColumn);
    if (vi < 0) return { rows, warnings: ["Elige la columna con el valor medido."], missing };
    if (cfg.method === "fixed_size") {
      const size = Math.max(1, Math.floor(cfg.size ?? 1));
      const vals: number[] = [];
      sheet.rows.forEach((r) => {
        const v = num(r[vi]);
        if (v == null) missing++;
        else vals.push(v);
      });
      for (let i = 0; i + size <= vals.length; i += size) rows.push({ label: String(rows.length + 1), values: vals.slice(i, i + size) });
      const rest = vals.length % size;
      if (rest) warnings.push(`Las últimas ${rest} observaciones no completan un subgrupo de ${size} y se dejaron fuera.`);
    } else {
      const gi = cfg.method === "time" ? colIndex(sheet, cfg.timeColumn) : colIndex(sheet, cfg.groupColumn);
      if (gi < 0) return { rows, warnings: [cfg.method === "time" ? "Elige la columna de fecha y hora." : "Elige la columna que identifica el subgrupo."], missing };
      const groups = new Map<string, number[]>();
      sheet.rows.forEach((r) => {
        const key = cfg.method === "time" ? bucketKey(r[gi], cfg.timeUnit ?? "day") : r[gi] == null ? null : String(r[gi]);
        const v = num(r[vi]);
        if (v == null) {
          missing++;
          return;
        }
        if (key == null) {
          warnings.push("Hay filas sin valor en la columna de agrupación; se dejaron fuera.");
          return;
        }
        groups.set(key, [...(groups.get(key) ?? []), v]);
      });
      groups.forEach((values, label) => rows.push({ label, values }));
    }
  }
  if (missing) warnings.push(`${missing} celda(s) vacías o no numéricas se omitieron.`);
  return { rows, warnings: [...new Set(warnings)], missing };
}

export function buildAttributeRows(
  sheet: Sheet,
  cfg: { countColumn?: string; sizeColumn?: string; constantSize?: number | null; labelColumn?: string; counting: "defectives" | "defects" },
): Built<AttributeRow> {
  const warnings: string[] = [];
  const ci = colIndex(sheet, cfg.countColumn);
  if (ci < 0) return { rows: [], warnings: ["Elige la columna con el conteo."], missing: 0 };
  const si = colIndex(sheet, cfg.sizeColumn);
  const li = colIndex(sheet, cfg.labelColumn);
  const rows: AttributeRow[] = [];
  let missing = 0;
  sheet.rows.forEach((r, k) => {
    const count = num(r[ci]);
    const size = si >= 0 ? num(r[si]) : (cfg.constantSize ?? null);
    if (count == null || size == null) {
      missing++;
      return;
    }
    rows.push({ label: li >= 0 && r[li] != null ? String(r[li]) : String(k + 1), count, size });
  });
  if (si < 0 && cfg.constantSize == null && cfg.counting === "defectives")
    warnings.push("Indica la columna del tamaño de muestra o un tamaño constante.");
  if (missing) warnings.push(`${missing} fila(s) con celdas vacías se omitieron.`);
  return { rows, warnings, missing };
}

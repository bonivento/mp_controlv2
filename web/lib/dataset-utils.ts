// Conversión entre conjuntos de datos guardados y las peticiones a la API.
// Aquí solo se reordena información; no hay estadística.

import type { Dataset } from "./db";
import { isAttributeRow, isVariableRow } from "./db";

export const isVariableDataset = (d: Dataset) => d.rows.length > 0 && isVariableRow(d.rows[0]);
export const isAttributeDataset = (d: Dataset) => d.rows.length > 0 && isAttributeRow(d.rows[0]);

export function variableSubgroups(d: Dataset) {
  const rows = d.rows.filter(isVariableRow);
  return { subgroups: rows.map((r) => r.values), labels: rows.map((r) => r.label) };
}

export function attributeArrays(d: Dataset) {
  const rows = d.rows.filter(isAttributeRow);
  return { counts: rows.map((r) => r.count), sizes: rows.map((r) => r.size), labels: rows.map((r) => r.label) };
}

/** Observaciones individuales en el orden de captura (para supuestos y capacidad). */
export const flatValues = (d: Dataset) => variableSubgroups(d).subgroups.flat();

export const sizeLabel = (d: Dataset) => {
  if (isVariableDataset(d)) {
    const sizes = new Set(variableSubgroups(d).subgroups.map((s) => s.length));
    return sizes.size === 1 ? `n = ${[...sizes][0]}` : "n variable";
  }
  return "atributos";
};

export const datasetOptionLabel = (d: Dataset) =>
  `${d.name} · Fase ${d.phase} · ${d.rows.length} subgrupos · ${sizeLabel(d)}`;

export interface SizeIssue {
  /** Tamaño de subgrupo que más se repite (si hay empate, el mayor). */
  predominant: number;
  /** Subgrupos con otro tamaño. */
  items: { index: number; label: string; n: number }[];
}

/** Subgrupos cuyo tamaño difiere del predominante. Solo cuenta filas; no es estadística. */
export function sizeIssues(rows: { label: string; values: number[] }[]): SizeIssue | null {
  if (rows.length === 0) return null;
  const freq = new Map<number, number>();
  rows.forEach((r) => freq.set(r.values.length, (freq.get(r.values.length) ?? 0) + 1));
  if (freq.size === 1) return null;
  const predominant = [...freq.entries()].sort((a, b) => b[1] - a[1] || b[0] - a[0])[0][0];
  const items = rows
    .map((r, index) => ({ index, label: r.label, n: r.values.length }))
    .filter((x) => x.n !== predominant);
  return { predominant, items };
}

/** "3 (n = 4), 7 (n = 4) y 2 más" */
export function sizeIssueList(issue: SizeIssue, max = 8): string {
  const shown = issue.items.slice(0, max).map((x) => `${x.label} (n = ${x.n})`);
  const rest = issue.items.length - shown.length;
  return rest > 0 ? `${shown.join(", ")} y ${rest} más` : shown.join(", ");
}

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

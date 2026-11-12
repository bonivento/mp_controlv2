// Depuración de Fase I: qué subgrupos quedaron fuera al congelar los límites de un conjunto de
// datos y con qué causa. Solo reorganiza información guardada; no hay estadística.

import type { Analysis, ControlLimitsRow, Dataset } from "./db";
import { isVariableRow } from "./db";

const VARIABLE_CHARTS = ["xbar_r", "xbar_s", "i_mr"] as const;

export interface Depuration {
  /** Límites congelados vigentes de este conjunto de datos. */
  limits: ControlLimitsRow;
  total: number;
  kept: number;
  excluded: { index: number; label: string; cause: string }[];
  keptSubgroups: number[][];
  keptLabels: string[];
  totalObservations: number;
  keptObservations: number;
}

/**
 * Límites vigentes del estudio que se congelaron con ESTE conjunto de datos (variables).
 * Si hay varios tipos de gráfico, prefiere el que corresponde al tamaño de subgrupo.
 */
export function findDepuration(dataset: Dataset | undefined, limits: ControlLimitsRow[]): Depuration | null {
  if (!dataset) return null;
  const rows = dataset.rows.filter(isVariableRow);
  if (rows.length === 0) return null;
  const mine = limits.filter((l) => l.dataset_id === dataset.id && (VARIABLE_CHARTS as readonly string[]).includes(l.chart_type));
  if (mine.length === 0) return null;
  const sizes = new Set(rows.map((r) => r.values.length));
  const preferred = sizes.size === 1 && sizes.has(1) ? "i_mr" : rows[0].values.length > 10 ? "xbar_s" : "xbar_r";
  const lim = mine.find((l) => l.chart_type === preferred) ?? mine[0];

  const exIdx = new Map<number, { label: string; cause: string }>();
  for (const e of lim.limits.excluded ?? []) {
    if (e.index >= 0 && e.index < rows.length) exIdx.set(e.index, { label: e.label ?? rows[e.index].label, cause: e.cause });
  }
  const keptRows = rows.filter((_, i) => !exIdx.has(i));
  return {
    limits: lim,
    total: rows.length,
    kept: keptRows.length,
    excluded: [...exIdx.entries()].sort((a, b) => a[0] - b[0]).map(([index, v]) => ({ index, ...v })),
    keptSubgroups: keptRows.map((r) => r.values),
    keptLabels: keptRows.map((r) => r.label),
    totalObservations: rows.reduce((a, r) => a + r.values.length, 0),
    keptObservations: keptRows.reduce((a, r) => a + r.values.length, 0),
  };
}

/** "24 de 25 subgrupos; se excluyó el 12 por: cambio de lote". */
export function describeDepuration(d: Depuration): string {
  const head = `${d.kept} de ${d.total} subgrupos`;
  if (d.excluded.length === 0) return `${head}; sin exclusiones`;
  if (d.excluded.length === 1) return `${head}; se excluyó el ${d.excluded[0].label} por: ${d.excluded[0].cause}`;
  return `${head}; se excluyeron ${d.excluded.map((e) => `el ${e.label} por: ${e.cause}`).join("; ")}`;
}

const idxOf = (x: unknown): number[] =>
  Array.isArray(x) ? x.map((e) => (e as { index?: number })?.index).filter((i): i is number => typeof i === "number") : [];

/**
 * Último análisis de control guardado que corresponde a los datos analizados: mismo conjunto, misma
 * fase y, en Fase I, las mismas exclusiones. Si no hay ninguno devuelve undefined (nunca se supone).
 */
export function matchingControlAnalysis(analyses: Analysis[], dataset: Dataset | undefined, excludedIndices: number[]): Analysis | undefined {
  if (!dataset) return undefined;
  const want = [...new Set(excludedIndices)].sort((a, b) => a - b).join(",");
  return [...analyses]
    .sort((a, b) => a.created_at.localeCompare(b.created_at))
    .reverse()
    .find((a) => {
      if (a.module !== "variables" || a.dataset_id !== dataset.id) return false;
      const phase = (a.result as { phase?: string }).phase ?? (a.params as { phase?: string }).phase;
      if (phase !== dataset.phase) return false;
      if (typeof (a.result as { in_control?: unknown }).in_control !== "boolean") return false;
      if (dataset.phase === "II") return true;
      const have = [...new Set(idxOf((a.params as { excluded?: unknown }).excluded))].sort((x, y) => x - y).join(",");
      return have === want;
    });
}

/** Último análisis de supuestos guardado sobre este conjunto con el mismo número de observaciones. */
export function matchingAssumptions(analyses: Analysis[], dataset: Dataset | undefined, nObservations: number): Analysis | undefined {
  if (!dataset) return undefined;
  return [...analyses]
    .sort((a, b) => a.created_at.localeCompare(b.created_at))
    .reverse()
    .find((a) => {
      if (a.module !== "assumptions" || a.dataset_id !== dataset.id) return false;
      if (typeof (a.result as { is_normal?: unknown }).is_normal !== "boolean") return false;
      const v = (a.params as { values?: unknown }).values;
      return Array.isArray(v) && v.length === nObservations;
    });
}

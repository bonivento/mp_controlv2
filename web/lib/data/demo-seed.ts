// Datos de ejemplo SINTÉTICOS para el modo de demostración. Se generan con una
// semilla fija (siempre los mismos) y los estudios llevan is_synthetic = true y
// "(SINTÉTICO)" en el nombre, como exige CLAUDE.md.

import type { AttributeRow, DatasetInput, StudyInput, VariableRow } from "../db";

function mulberry32(seed: number) {
  let a = seed;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function normal(rand: () => number) {
  const u = Math.max(rand(), 1e-12);
  const v = rand();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}

const round2 = (x: number) => Math.round(x * 100) / 100;

function variableRows(
  rand: () => number,
  count: number,
  n: number,
  mu: number,
  sigma: number,
  shiftAt: (i: number) => number,
  offset = 0,
): VariableRow[] {
  return Array.from({ length: count }, (_, i) => ({
    label: String(offset + i + 1),
    values: Array.from({ length: n }, () => round2(mu + shiftAt(i) + sigma * normal(rand))),
  }));
}

function attributeRows(
  rand: () => number,
  count: number,
  p: (i: number) => number,
  offset = 0,
): AttributeRow[] {
  return Array.from({ length: count }, (_, i) => {
    const size = 80 + Math.floor(rand() * 41);
    let defective = 0;
    for (let k = 0; k < size; k++) if (rand() < p(i)) defective++;
    return { label: String(offset + i + 1), count: defective, size };
  });
}

export interface SeedStudy {
  study: StudyInput;
  datasets: Omit<DatasetInput, "study_id">[];
}

export function buildSeed(): SeedStudy[] {
  const r1 = mulberry32(20261109);
  const r2 = mulberry32(777);
  const now = new Date().toISOString();
  const logLine = { action: "Carga", detail: "Datos sintéticos generados para la demostración", at: now };

  return [
    {
      study: {
        name: "Llenado de botellas 500 mL (SINTÉTICO)",
        company: "Embotelladora Ejemplo S.A. (ficticia)",
        process: "Llenado de botellas",
        product: "Agua 500 mL",
        characteristic: "Volumen de llenado",
        unit: "mL",
        data_type: "variable",
        lsl: 495,
        usl: 505,
        target: 500,
        notes: "Caso de ejemplo con datos sintéticos. Sustituir por los datos de la empresa real.",
        is_synthetic: true,
      },
      datasets: [
        {
          name: "Fase I sintética (25 subgrupos de 5)",
          phase: "I",
          source_file: "sintetico_demo_fase1.csv",
          subgrouping: {
            method: "column",
            layout: "wide",
            column: "subgrupo",
            value_columns: ["x1", "x2", "x3", "x4", "x5"],
            justification:
              "Cinco botellas consecutivas de la misma cabeza de llenado cada hora: la variación dentro del subgrupo es solo la de corto plazo.",
          },
          rows: variableRows(r1, 25, 5, 500, 1.5, (i) => (i === 13 ? 4.5 : 0)),
          cleaning_log: [logLine],
        },
        {
          name: "Fase II sintética (20 subgrupos de 5, con desplazamiento)",
          phase: "II",
          source_file: "sintetico_demo_fase2.csv",
          subgrouping: {
            method: "column",
            layout: "wide",
            column: "subgrupo",
            value_columns: ["x1", "x2", "x3", "x4", "x5"],
            justification: "Mismo criterio de subgrupo que en la Fase I.",
          },
          rows: variableRows(r1, 20, 5, 500, 1.5, (i) => (i >= 10 ? 2 : 0), 25),
          cleaning_log: [logLine],
        },
      ],
    },
    {
      study: {
        name: "Soldadura de tarjetas (SINTÉTICO)",
        company: "Electrónica Ejemplo Ltda. (ficticia)",
        process: "Soldadura por ola",
        product: "Tarjeta de control",
        characteristic: "Tarjetas defectuosas",
        unit: "unidades",
        data_type: "attribute",
        lsl: null,
        usl: null,
        target: null,
        notes: "Caso de ejemplo con datos sintéticos. Tamaño de muestra variable (80 a 120).",
        is_synthetic: true,
      },
      datasets: [
        {
          name: "Fase I sintética (25 lotes)",
          phase: "I",
          source_file: "sintetico_demo_p_fase1.csv",
          subgrouping: {
            method: "column",
            layout: "attribute",
            count_column: "defectuosos",
            size_column: "tamano_muestra",
            counting: "defectives",
            justification: "Cada lote inspeccionado en el turno es un subgrupo; se cuentan tarjetas defectuosas.",
          },
          rows: attributeRows(r2, 25, (i) => (i === 8 ? 0.15 : 0.05)),
          cleaning_log: [logLine],
        },
        {
          name: "Fase II sintética (15 lotes)",
          phase: "II",
          source_file: "sintetico_demo_p_fase2.csv",
          subgrouping: {
            method: "column",
            layout: "attribute",
            count_column: "defectuosos",
            size_column: "tamano_muestra",
            counting: "defectives",
            justification: "Mismo criterio que en la Fase I.",
          },
          rows: attributeRows(r2, 15, (i) => (i >= 10 ? 0.1 : 0.05), 25),
          cleaning_log: [logLine],
        },
      ],
    },
  ];
}

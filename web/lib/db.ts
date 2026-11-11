// Tipos de las tablas de Supabase. Las columnas simples salen de
// lib/database-types.ts (generado desde el proyecto real); aquí solo se
// afinan las columnas jsonb y los textos con valores permitidos, que la base
// valida con restricciones CHECK pero que Postgres tipa como `Json` o `string`.
// Para cambiar el esquema: migración en supabase/ y regenerar database-types.ts.

import type { components } from "./api-types";
import type { Tables } from "./database-types";

type S = components["schemas"];

export type DataType = "variable" | "attribute";
export type Phase = "I" | "II";
export type ChartType = S["FrozenLimits"]["chart_type"];
export type AnalysisModule = S["ReportSection"]["module"];

export interface Subgrouping {
  /** "column": cada valor de la columna identifica un subgrupo (o, en formato ancho, cada fila). */
  method: "column" | "fixed_size" | "time";
  layout?: "long" | "wide" | "attribute";
  column?: string;
  value_columns?: string[];
  size?: number;
  time_column?: string;
  time_unit?: "hour" | "day" | "week" | "month";
  count_column?: string;
  size_column?: string;
  counting?: "defectives" | "defects";
  justification: string;
}

export interface VariableRow {
  label: string;
  values: number[];
}
export interface AttributeRow {
  label: string;
  count: number;
  size: number;
}
export type DatasetRow = VariableRow | AttributeRow;

export interface CleaningEntry {
  action: string;
  detail: string;
  at: string;
}

// --- Filas leídas ---------------------------------------------------------------
export type Study = Omit<Tables<"studies">, "data_type"> & { data_type: DataType };
export type Dataset = Omit<Tables<"datasets">, "phase" | "subgrouping" | "rows" | "cleaning_log"> & {
  phase: Phase;
  subgrouping: Subgrouping | Record<string, never>;
  rows: DatasetRow[];
  cleaning_log: CleaningEntry[];
};
export type ControlLimitsRow = Omit<Tables<"control_limits">, "chart_type" | "limits"> & {
  chart_type: ChartType;
  limits: S["FrozenLimits"];
};
export type Analysis = Omit<Tables<"analyses">, "module" | "params" | "result"> & {
  module: AnalysisModule;
  params: Record<string, unknown>;
  result: Record<string, unknown>;
};
export type SamplingPlan = Omit<Tables<"sampling_plans">, "plan_type" | "params" | "result"> & {
  plan_type: "single" | "double";
  params: Record<string, unknown>;
  result: Record<string, unknown>;
};

// --- Entradas (user_id lo pone la base con auth.uid(); nunca se envía) ------------
export type StudyInput = Omit<Study, "id" | "user_id" | "created_at" | "updated_at">;
export type DatasetInput = Omit<Dataset, "id" | "user_id" | "created_at">;
export type ControlLimitsInput = Pick<ControlLimitsRow, "study_id" | "dataset_id" | "chart_type" | "limits">;
export type AnalysisInput = Omit<Analysis, "id" | "user_id" | "created_at">;
export type SamplingPlanInput = Omit<SamplingPlan, "id" | "user_id" | "created_at">;

export function isVariableRow(r: DatasetRow): r is VariableRow {
  return "values" in r;
}
export function isAttributeRow(r: DatasetRow): r is AttributeRow {
  return "count" in r;
}

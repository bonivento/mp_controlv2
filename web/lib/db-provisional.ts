// Tipos PROVISIONALES de las tablas, escritos a mano desde
// supabase/migrations/20261109000000_esquema_inicial.sql.
// Cuando `supabase-db` genere lib/database-types.ts, estos tipos se reemplazan
// por los generados; solo hay que cambiar los imports de este archivo.

import type { components } from "./api-types";

type S = components["schemas"];

export type DataType = "variable" | "attribute";
export type Phase = "I" | "II";
export type ChartType = S["FrozenLimits"]["chart_type"];
export type AnalysisModule = S["ReportSection"]["module"];

export interface Study {
  id: string;
  user_id: string;
  name: string;
  company: string | null;
  process: string | null;
  product: string | null;
  characteristic: string | null;
  unit: string | null;
  data_type: DataType;
  lsl: number | null;
  usl: number | null;
  target: number | null;
  notes: string | null;
  is_synthetic: boolean;
  created_at: string;
  updated_at: string;
}
export type StudyInput = Omit<Study, "id" | "user_id" | "created_at" | "updated_at">;

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

export interface Dataset {
  id: string;
  user_id: string;
  study_id: string;
  name: string;
  phase: Phase;
  source_file: string | null;
  subgrouping: Subgrouping | Record<string, never>;
  rows: DatasetRow[];
  cleaning_log: CleaningEntry[];
  created_at: string;
}
export type DatasetInput = Omit<Dataset, "id" | "user_id" | "created_at">;

export interface ControlLimitsRow {
  id: string;
  user_id: string;
  study_id: string;
  dataset_id: string | null;
  chart_type: ChartType;
  limits: S["FrozenLimits"];
  is_active: boolean;
  created_at: string;
}
export type ControlLimitsInput = Pick<ControlLimitsRow, "study_id" | "dataset_id" | "chart_type" | "limits">;

export interface Analysis {
  id: string;
  user_id: string;
  study_id: string;
  dataset_id: string | null;
  module: AnalysisModule;
  title: string;
  params: Record<string, unknown>;
  result: Record<string, unknown>;
  in_report: boolean;
  created_at: string;
}
export type AnalysisInput = Omit<Analysis, "id" | "user_id" | "created_at">;

export interface SamplingPlan {
  id: string;
  user_id: string;
  study_id: string;
  name: string;
  plan_type: "single" | "double";
  params: Record<string, unknown>;
  result: Record<string, unknown>;
  created_at: string;
}
export type SamplingPlanInput = Omit<SamplingPlan, "id" | "user_id" | "created_at">;

export function isVariableRow(r: DatasetRow): r is VariableRow {
  return "values" in r;
}
export function isAttributeRow(r: DatasetRow): r is AttributeRow {
  return "count" in r;
}

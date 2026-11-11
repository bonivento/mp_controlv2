// Rótulos en español compartidos por las pantallas y el reporte.

import type { AnalysisModule } from "./db";

export const CHART_TYPE_LABEL: Record<string, string> = {
  xbar_r: "X-barra y R",
  xbar_s: "X-barra y S",
  i_mr: "Individuales y rango móvil (I-MR)",
  p: "p (fracción defectuosa)",
  np: "np (número de defectuosos)",
  c: "c (defectos por unidad de inspección)",
  u: "u (defectos por unidad)",
};

export const PARAM_LABEL: Record<string, string> = {
  mu: "Media del proceso (μ)",
  sigma: "Desviación estándar del proceso (σ)",
  p_bar: "Fracción defectuosa media (p̄)",
  c_bar: "Defectos medios (c̄)",
  u_bar: "Defectos por unidad medios (ū)",
  r_bar: "Rango medio de los subgrupos (R̄)",
  s_bar: "Desviación estándar media de los subgrupos (S̄)",
  mr_bar: "Rango móvil medio (MR̄)",
};

export const SIGMA_METHOD_LABEL: Record<string, string> = {
  rbar_d2: "R-barra / d2",
  sbar_c4: "S-barra / c4",
  mrbar_d2: "Rango móvil medio / d2",
  frozen_limits: "Límites congelados de Fase I",
};

export const MODULE_LABEL: Record<AnalysisModule, string> = {
  data: "Datos",
  variables: "Gráficos de control por variables",
  attributes: "Gráficos de control por atributos",
  assumptions: "Validación de supuestos",
  capability: "Capacidad del proceso",
  design: "Diseño de gráficos de control",
  sampling: "Muestreo de aceptación",
};

/** Orden de los módulos en el reporte. */
export const MODULE_ORDER: AnalysisModule[] = ["data", "variables", "attributes", "assumptions", "capability", "design", "sampling"];

export const fmtDateTime = (s: string) => new Date(s).toLocaleString("es-CO", { dateStyle: "medium", timeStyle: "short" });
export const slug = (s: string) =>
  s
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[^A-Za-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 60);

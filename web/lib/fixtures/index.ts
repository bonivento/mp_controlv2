// Respuestas de ejemplo con la forma exacta del contrato (lib/api-types.ts).
// Solo las usa lib/api.ts cuando NEXT_PUBLIC_API_MOCK=1.

import type { components } from "../api-types";
import { mockAssumptions, mockCapability } from "./analysis";
import { mockAttributesChart, mockRecommend, mockVariablesChart } from "./charts";
import { mockAttributeSummary, mockParse, mockSummary } from "./data";
import { mockArl, mockCompare } from "./design";
import { MockHttpError, delay } from "./engine";
import { mockDoubleEvaluate, mockSingleDesign, mockSingleEvaluate } from "./sampling";

type S = components["schemas"];

async function respond<T>(fn: () => T): Promise<T> {
  await delay();
  return fn();
}

export { MockHttpError };

export const mockApi = {
  async parseFile(file: File): Promise<S["ParsedFile"]> {
    await delay(200);
    return mockParse(file);
  },
  summary: (r: S["SummaryRequest"]) => respond(() => mockSummary(r)),
  attributeSummary: (r: S["AttributeSummaryRequest"]) => respond(() => mockAttributeSummary(r)),
  variablesChart: (r: S["VariablesChartRequest"]) => respond(() => mockVariablesChart(r)),
  attributesChart: (r: S["AttributesChartRequest"]) => respond(() => mockAttributesChart(r)),
  recommend: (r: S["RecommendRequest"]) => respond(() => mockRecommend(r)),
  assumptions: (r: S["AssumptionsRequest"]) => respond(() => mockAssumptions(r)),
  capability: (r: S["CapabilityRequest"]) => respond(() => mockCapability(r)),
  arl: (r: S["ArlRequest"]) => respond(() => mockArl(r)),
  compare: (r: S["CompareRequest"]) => respond(() => mockCompare(r)),
  singleDesign: (r: S["SingleDesignRequest"]) => respond(() => mockSingleDesign(r)),
  singleEvaluate: (r: S["SingleEvaluateRequest"]) => respond(() => mockSingleEvaluate(r)),
  doubleEvaluate: (r: S["DoubleEvaluateRequest"]) => respond(() => mockDoubleEvaluate(r)),
  async excelReport(r: S["ExcelReportRequest"]): Promise<Blob> {
    await delay();
    const lines = ["Reporte de ejemplo (CSV): la API real entrega un .xlsx", `Estudio;${r.study.name}`, "Módulo;Título;Resumen"];
    for (const s of r.sections) {
      const interp = (s.result as { interpretation?: { summary?: string } }).interpretation;
      lines.push(`${s.module};${s.title};${interp?.summary ?? ""}`);
    }
    return new Blob(["﻿" + lines.join("\n")], { type: "text/csv;charset=utf-8" });
  },
};

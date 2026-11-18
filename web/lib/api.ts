// Único cliente tipado de la API de cálculo. Llama a /api/* en el mismo origen
// (un rewrite de next.config.ts lo envía a API_URL) con el JWT de la sesión.
// Con NEXT_PUBLIC_API_MOCK=1 devuelve respuestas de ejemplo de lib/fixtures/.
// Las pantallas usan solo este objeto: apagar el modo de ejemplo no las cambia.

import type { components } from "./api-types";
import { API_MOCK } from "./env";
import { getStore } from "./data";
import { MockHttpError, mockApi } from "./fixtures";

type S = components["schemas"];

export const MAX_UPLOAD_BYTES = 4 * 1024 * 1024;

/** Error de la API con el `detail` en español listo para mostrar. */
export class ApiError extends Error {
  status: number;
  code?: string;
  constructor(message: string, status: number, code?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

export function detailOf(body: unknown, status: number): { detail: string; code?: string } {
  if (body && typeof body === "object") {
    const b = body as { detail?: unknown; code?: string };
    if (typeof b.detail === "string") return { detail: b.detail, code: b.code };
    if (Array.isArray(b.detail)) {
      // Error de validación de FastAPI (422 con lista de problemas).
      const parts = (b.detail as { loc?: (string | number)[]; msg?: string }[]).map(
        (d) => `${d.loc ? d.loc.filter((x) => x !== "body").join(".") + ": " : ""}${d.msg ?? "dato inválido"}`,
      );
      return { detail: parts.join("; "), code: b.code };
    }
  }
  if (status === 401) return { detail: "Tu sesión expiró. Inicia sesión de nuevo." };
  if (status === 501) return { detail: "Esta función de la API todavía no está implementada." };
  return { detail: `La API respondió con un error (${status}).` };
}

export async function authHeaders(): Promise<Record<string, string>> {
  const token = await getStore().auth.getAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request(path: string, init: RequestInit): Promise<Response> {
  let res: Response;
  try {
    res = await fetch(path, { ...init, headers: { ...(await authHeaders()), ...(init.headers ?? {}) } });
  } catch {
    throw new ApiError("No se pudo contactar a la API de cálculo. Revisa tu conexión e inténtalo de nuevo.", 0, "network");
  }
  if (!res.ok) {
    const body: unknown = await res.json().catch(() => null);
    const { detail, code } = detailOf(body, res.status);
    throw new ApiError(detail, res.status, code);
  }
  return res;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await request(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return (await res.json()) as T;
}

/** En modo de ejemplo los errores del motor se convierten en ApiError. */
async function viaMock<T>(fn: () => Promise<T>): Promise<T> {
  try {
    return await fn();
  } catch (e) {
    if (e instanceof MockHttpError) throw new ApiError(e.message, e.status, e.code);
    throw e;
  }
}

function route<Req, Res>(path: string, mock: (r: Req) => Promise<Res>) {
  return (r: Req): Promise<Res> => (API_MOCK ? viaMock(() => mock(r)) : post<Res>(path, r));
}

export const api = {
  /** Módulo 1: lee un CSV o XLSX y devuelve sus hojas, columnas y filas. */
  parseFile(file: File): Promise<S["ParsedFile"]> {
    // La API acepta hasta 4 MB (límite de cuerpo de Vercel): se valida antes de subir.
    if (file.size > MAX_UPLOAD_BYTES)
      return Promise.reject(
        new ApiError(`El archivo pesa ${(file.size / 1024 / 1024).toFixed(1).replace(".", ",")} MB y el límite es 4 MB. Reduce las filas o guarda solo las columnas necesarias.`, 413, "file_too_large"),
      );
    if (API_MOCK) return viaMock(() => mockApi.parseFile(file));
    const form = new FormData();
    form.append("file", file);
    return request("/api/data/parse", { method: "POST", body: form }).then((r) => r.json() as Promise<S["ParsedFile"]>);
  },
  summary: route<S["SummaryRequest"], S["SummaryResponse"]>("/api/data/summary", mockApi.summary),
  /** Módulo 1, datos por atributos: totales, tasa global y avisos por subgrupo. */
  attributeSummary: route<S["AttributeSummaryRequest"], S["AttributeSummaryResponse"]>(
    "/api/data/summary/attributes",
    mockApi.attributeSummary,
  ),
  variablesChart: route<S["VariablesChartRequest"], S["ChartResponse"]>("/api/charts/variables", mockApi.variablesChart),
  attributesChart: route<S["AttributesChartRequest"], S["ChartResponse"]>("/api/charts/attributes", mockApi.attributesChart),
  recommendAttributes: route<S["RecommendRequest"], S["RecommendResponse"]>("/api/charts/attributes/recommend", mockApi.recommend),
  assumptions: route<S["AssumptionsRequest"], S["AssumptionsResponse"]>("/api/assumptions", mockApi.assumptions),
  capability: route<S["CapabilityRequest"], S["CapabilityResponse"]>("/api/capability", mockApi.capability),
  arl: route<S["ArlRequest"], S["ArlResponse"]>("/api/design/arl", mockApi.arl),
  compareDesigns: route<S["CompareRequest"], S["CompareResponse"]>("/api/design/compare", mockApi.compare),
  singleDesign: route<S["SingleDesignRequest"], S["SinglePlanResponse"]>("/api/sampling/single/design", mockApi.singleDesign),
  singleEvaluate: route<S["SingleEvaluateRequest"], S["SinglePlanResponse"]>("/api/sampling/single/evaluate", mockApi.singleEvaluate),
  doubleEvaluate: route<S["DoubleEvaluateRequest"], S["DoublePlanResponse"]>("/api/sampling/double/evaluate", mockApi.doubleEvaluate),
  /** Módulo 8: archivo .xlsx con las secciones del reporte. */
  excelReport(req: S["ExcelReportRequest"]): Promise<Blob> {
    if (API_MOCK) return viaMock(() => mockApi.excelReport(req));
    return request("/api/reports/excel", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
    }).then((r) => r.blob());
  },
};

export type { S as ApiSchemas };

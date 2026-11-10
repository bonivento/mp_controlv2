import type { components } from "../api-types";

export type S = components["schemas"];

export const MOCK_NOTICE =
  "Respuesta de ejemplo (modo NEXT_PUBLIC_API_MOCK): los números se calcularon en el navegador solo para revisar la interfaz; no provienen de la API de cálculo.";

export function interp(summary: string, findings: string[] = [], warnings: string[] = []): S["Interpretation"] {
  return { summary, findings, warnings: [MOCK_NOTICE, ...warnings] };
}

export const fmt = (x: number | null | undefined, d = 3) =>
  x == null || !Number.isFinite(x) ? "—" : x.toFixed(d).replace(".", ",");

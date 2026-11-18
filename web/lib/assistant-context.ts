// Reducción del contexto de pantalla que viaja al asistente. Funciones puras (sin React,
// sin red) para poder probarlas con Node.
//
// Reglas:
// - Se conservan límites, parámetros, índices, reglas violadas, interpretación y advertencias.
// - Las series largas se recortan: de un gráfico de control se envía el recuento de puntos,
//   los primeros y últimos y los puntos con señal; de las curvas, una muestra equiespaciada.
// - Nunca viajan las filas del conjunto de datos: las matrices (subgrupos x observaciones) y
//   las listas de filas {label, values} se sustituyen por su tamaño.
// - Aquí no hay estadística: solo se eligen y cuentan elementos. Los números salen de la API.
// - Todo se mantiene por debajo de ASSISTANT_VIEW_TARGET_BYTES (el backend rechaza 60 KB).

import {
  ASSISTANT_CONTEXT_TARGET_BYTES,
  ASSISTANT_VIEW_TARGET_BYTES,
  type AssistantContext,
  type AssistantScreen,
  type AssistantStudy,
} from "./assistant-types";

type Json = null | boolean | number | string | Json[] | { [k: string]: Json };
type Obj = Record<string, unknown>;

export interface ReduceLimits {
  /** Arreglos de hasta este largo se conservan completos (elemento a elemento reducido). */
  arrayMax: number;
  /** Elementos de la muestra equiespaciada de un arreglo largo. */
  sample: number;
  /** Largo máximo de un texto. */
  strMax: number;
  /** Profundidad máxima de anidación. */
  depth: number;
  /** Claves máximas por objeto. */
  keys: number;
  /** Violaciones / puntos con señal que se listan en un gráfico. */
  signals: number;
}

/** Niveles de recorte, de más a menos holgado: se usa el primero que cabe en el presupuesto. */
export const REDUCE_LEVELS: ReduceLimits[] = [
  { arrayMax: 30, sample: 9, strMax: 800, depth: 9, keys: 60, signals: 40 },
  { arrayMax: 16, sample: 7, strMax: 400, depth: 8, keys: 50, signals: 25 },
  { arrayMax: 10, sample: 5, strMax: 220, depth: 7, keys: 40, signals: 12 },
  { arrayMax: 6, sample: 3, strMax: 120, depth: 6, keys: 30, signals: 6 },
];

const isObj = (v: unknown): v is Obj => typeof v === "object" && v !== null && !Array.isArray(v);
const isNum = (v: unknown): v is number => typeof v === "number";

function clip(s: string, max: number): string {
  if (s.length <= max) return s;
  let end = max - 1;
  const c = s.charCodeAt(end - 1);
  if (c >= 0xd800 && c <= 0xdbff) end -= 1;
  return `${s.slice(0, end)}…`;
}

/** Bytes UTF-8 del JSON, que es lo que mide el backend. */
export function jsonBytes(v: unknown): number {
  const s = JSON.stringify(v);
  return s === undefined ? 0 : new TextEncoder().encode(s).length;
}

/** n posiciones equiespaciadas de 0..len-1, incluyendo la primera y la última. */
function spread(len: number, n: number): number[] {
  if (len <= n) return Array.from({ length: len }, (_, i) => i);
  const out = new Set<number>();
  for (let i = 0; i < n; i++) out.add(Math.round((i * (len - 1)) / (n - 1)));
  return [...out];
}

/** ¿Es un panel de gráfico de control (ChartSeries)? */
function isSeries(o: Obj): boolean {
  return Array.isArray(o.values) && Array.isArray(o.ucl) && Array.isArray(o.lcl) && Array.isArray(o.center) && Array.isArray(o.labels);
}

/** Un arreglo que es constante se reduce a su valor; si varía, a su primer y último valor. */
function limitLine(a: unknown[]): Json {
  const nums = a.map((x) => (isNum(x) && Number.isFinite(x) ? x : null));
  if (nums.length === 0) return null;
  const first = nums[0];
  if (nums.every((x) => x === first)) return first;
  return { variable: true, first, last: nums[nums.length - 1] };
}

/**
 * Panel de gráfico de control compacto: recuento de puntos, límites (constantes o primero/último),
 * reglas, excluidos, violaciones, los puntos con señal con su valor y los extremos de la serie.
 */
export function shapeSeries(s: Obj, lim: ReduceLimits): Json {
  const values = s.values as unknown[];
  const labels = (s.labels as unknown[]).map(String);
  const indices = Array.isArray(s.indices) ? (s.indices as unknown[]) : values.map((_, i) => i);
  const point = (k: number): Json => ({ index: isNum(indices[k]) ? (indices[k] as number) : k, label: clip(labels[k] ?? "", 40), value: isNum(values[k]) && Number.isFinite(values[k] as number) ? (values[k] as number) : null });
  const violations = Array.isArray(s.violations) ? (s.violations as Obj[]) : [];
  const signalIdx = [...new Set(violations.map((v) => v.index).filter(isNum))];
  const posOf = new Map<number, number>();
  indices.forEach((ix, k) => {
    if (isNum(ix)) posOf.set(ix, k);
  });
  const signalPoints = signalIdx
    .slice(0, lim.signals)
    .map((ix) => posOf.get(ix))
    .filter((k): k is number => k !== undefined)
    .map(point);
  const edge = Math.min(5, Math.floor(values.length / 2));
  const out: { [k: string]: Json } = {
    name: String(s.name ?? ""),
    title: clip(String(s.title ?? ""), 120),
    n_points: values.length,
    center: limitLine(s.center as unknown[]),
    ucl: limitLine(s.ucl as unknown[]),
    lcl: limitLine(s.lcl as unknown[]),
    rules_applied: reduceNode(s.rules_applied, lim, 0) as Json,
    rules_skipped: reduceNode(s.rules_skipped, lim, 0) as Json,
    excluded_subgroups: reduceNode(s.excluded, lim, 0) as Json,
    n_violations: violations.length,
    violations: violations.slice(0, lim.signals).map((v) => reduceNode(v, lim, 0) as Json),
    signal_points: signalPoints,
    first_points: values.length <= 2 * edge ? [] : Array.from({ length: edge }, (_, k) => point(k)),
    last_points: values.length <= 2 * edge ? [] : Array.from({ length: edge }, (_, k) => point(values.length - edge + k)),
  };
  if (violations.length > lim.signals) out.violations_note = `Se listan ${lim.signals} de ${violations.length} violaciones.`;
  return out;
}

/** ¿Es el bloque `interpretation` de la API (resumen, hallazgos, advertencias)? */
function isInterpretation(o: Obj): boolean {
  return typeof o.summary === "string" && Array.isArray(o.findings) && Array.isArray(o.warnings);
}

/**
 * La interpretación se conserva entera mientras quepa: resumen y advertencias completos y los
 * primeros hallazgos (con el total, por si hay cientos, como en un gráfico con muchas señales).
 */
export function shapeInterpretation(o: Obj, lim: ReduceLimits): Json {
  const text = (x: unknown) => clip(String(x), lim.strMax);
  const findings = (o.findings as unknown[]).map(text);
  const warnings = (o.warnings as unknown[]).map(text);
  const out: { [k: string]: Json } = { summary: text(o.summary), findings: findings.slice(0, lim.signals), warnings: warnings.slice(0, lim.signals) };
  if (findings.length > lim.signals) out.findings_total = findings.length;
  if (warnings.length > lim.signals) out.warnings_total = warnings.length;
  return out;
}

/** Arreglo de arreglos (matriz de observaciones): nunca se envía su contenido. */
function isMatrix(a: unknown[]): boolean {
  return a.length > 0 && a.every((r) => Array.isArray(r));
}
/** Lista de filas crudas del conjunto de datos: {label, values: number[]}. */
function isRawRows(a: unknown[]): boolean {
  return a.length > 0 && a.every((r) => isObj(r) && Array.isArray(r.values) && (r.values as unknown[]).every(isNum) && "label" in r);
}

/** Reduce recursivamente un valor; devuelve JSON válido (sin undefined, NaN ni infinitos). */
export function reduceNode(v: unknown, lim: ReduceLimits, depth: number): Json | undefined {
  if (v === null) return null;
  switch (typeof v) {
    case "undefined":
    case "function":
    case "symbol":
      return undefined;
    case "boolean":
      return v;
    case "number":
      return Number.isFinite(v) ? v : null;
    case "bigint":
      return Number(v);
    case "string":
      return clip(v, lim.strMax);
  }
  if (depth > lim.depth) return "[omitido: demasiado anidado]";
  if (Array.isArray(v)) {
    if (isMatrix(v)) {
      const lengths = [...new Set(v.map((r) => (r as unknown[]).length))].slice(0, 5);
      return { n_filas: v.length, largos_de_fila: lengths, nota: "Observaciones no incluidas" };
    }
    if (isRawRows(v)) return { n_filas: v.length, nota: "Filas de datos no incluidas" };
    if (v.length <= lim.arrayMax) return v.map((x) => reduceNode(x, lim, depth + 1) ?? null);
    const pick = spread(v.length, lim.sample);
    return { n: v.length, muestra_equiespaciada: pick.map((i) => reduceNode(v[i], lim, depth + 1) ?? null) };
  }
  const o = v as Obj;
  if (isSeries(o)) return shapeSeries(o, lim);
  if (isInterpretation(o)) return shapeInterpretation(o, lim);
  const entries = Object.entries(o).filter(([, x]) => x !== undefined);
  const out: { [k: string]: Json } = {};
  for (const [k, x] of entries.slice(0, lim.keys)) {
    const r = reduceNode(x, lim, depth + 1);
    if (r !== undefined) out[k] = r;
  }
  if (entries.length > lim.keys) out._claves_omitidas = entries.length - lim.keys;
  return out;
}

export interface FittedView {
  view: Record<string, unknown>;
  bytes: number;
  /** Índice del nivel de recorte usado (0 = el más holgado); -1 si hubo que quitar claves. */
  level: number;
}

/** Reduce el `view` hasta que cabe en el presupuesto. */
export function fitView(view: Record<string, unknown>, budget = ASSISTANT_VIEW_TARGET_BYTES): FittedView {
  for (let level = 0; level < REDUCE_LEVELS.length; level++) {
    const r = reduceNode(view, REDUCE_LEVELS[level], 0) as Record<string, Json>;
    const bytes = jsonBytes(r);
    if (bytes <= budget) return { view: r, bytes, level };
  }
  // Último recurso: se quitan las claves más pesadas hasta que quepa.
  const r = reduceNode(view, REDUCE_LEVELS[REDUCE_LEVELS.length - 1], 0) as Record<string, Json>;
  const dropped: string[] = [];
  const keys = Object.keys(r).sort((a, b) => jsonBytes(r[b]) - jsonBytes(r[a]));
  for (const k of keys) {
    if (jsonBytes(r) + 120 <= budget) break;
    delete r[k];
    dropped.push(k);
  }
  r._omitido_por_tamano = dropped;
  return { view: r, bytes: jsonBytes(r), level: -1 };
}

/**
 * Arma el contexto completo que se envía. El backend mide el contexto entero (ficha, vista,
 * conjuntos y límites) y responde 422 por encima de 60 KB, así que el presupuesto de la vista es
 * lo que queda del objetivo total una vez descontado todo lo demás (y nunca más de 40 KB).
 */
export function fitContext(parts: {
  screen: AssistantScreen;
  study?: AssistantStudy;
  view?: Record<string, unknown>;
  datasets?: Record<string, unknown>[];
  frozen_limits?: Record<string, unknown>[];
}): { context: AssistantContext; viewBytes: number; totalBytes: number } {
  const context: AssistantContext = { screen: parts.screen };
  if (parts.study && Object.keys(parts.study).length > 0) context.study = parts.study;
  if (parts.datasets?.length) context.datasets = parts.datasets;
  if (parts.frozen_limits?.length) context.frozen_limits = parts.frozen_limits;
  const withoutView = () => jsonBytes(context) + 40; // + clave "view"
  // Si lo que no es la vista ya ocupa demasiado, se recortan los resúmenes antes que el resultado.
  if (withoutView() > ASSISTANT_CONTEXT_TARGET_BYTES - 8_000) {
    if (context.datasets) context.datasets = context.datasets.slice(0, 8);
    if (context.frozen_limits) context.frozen_limits = context.frozen_limits.slice(0, 5);
  }
  let viewBytes = 0;
  if (parts.view && Object.keys(parts.view).length > 0) {
    const budget = Math.max(2_000, Math.min(ASSISTANT_VIEW_TARGET_BYTES, ASSISTANT_CONTEXT_TARGET_BYTES - withoutView()));
    const fitted = fitView(parts.view, budget);
    context.view = fitted.view;
    viewBytes = fitted.bytes;
  }
  return { context, viewBytes, totalBytes: jsonBytes(context) };
}

/** Ficha del estudio en el formato del contrato (sin nulos; textos acotados). */
export function studyToContext(s: {
  name?: string | null;
  company?: string | null;
  process?: string | null;
  product?: string | null;
  characteristic?: string | null;
  unit?: string | null;
  data_type?: string | null;
  lsl?: number | null;
  usl?: number | null;
  target?: number | null;
  is_synthetic?: boolean | null;
  notes?: string | null;
}): AssistantStudy {
  const out: AssistantStudy = {};
  const txt = (v: string | null | undefined, max: number) => (v ? clip(v, max) : undefined);
  const set = <K extends keyof AssistantStudy>(k: K, v: AssistantStudy[K] | undefined) => {
    if (v !== undefined && v !== null) out[k] = v;
  };
  set("name", txt(s.name, 200));
  set("company", txt(s.company, 200));
  set("process", txt(s.process, 300));
  set("product", txt(s.product, 300));
  set("characteristic", txt(s.characteristic, 300));
  set("unit", txt(s.unit, 40));
  if (s.data_type === "variable" || s.data_type === "attribute") out.data_type = s.data_type;
  set("lsl", isNum(s.lsl) ? s.lsl : undefined);
  set("usl", isNum(s.usl) ? s.usl : undefined);
  set("target", isNum(s.target) ? s.target : undefined);
  if (typeof s.is_synthetic === "boolean") out.synthetic = s.is_synthetic;
  set("notes", txt(s.notes, 2000));
  return out;
}

const SCREEN_TITLE: Record<AssistantScreen, string> = {
  studies: "Estudios",
  study: "Resumen del estudio",
  data: "Datos",
  variables: "Variables",
  attributes: "Atributos",
  assumptions: "Supuestos",
  capability: "Capacidad",
  design: "Diseño",
  sampling: "Muestreo",
  report: "Reporte",
};
export const screenTitle = (s: AssistantScreen) => SCREEN_TITLE[s];

export interface SuggestionState {
  /** Ya hay un resultado calculado en pantalla. */
  hasResult?: boolean;
  /** Pantalla sin datos todavía (p. ej. Datos sin conjuntos guardados). */
  empty?: boolean;
}

/** Sugerencias iniciales según la pantalla y su estado. */
export function suggestionsFor(screen: AssistantScreen, st: SuggestionState = {}): string[] {
  const what = "¿Qué estoy viendo?";
  const interpret = "Interpreta estos resultados";
  const samples = "¿Qué muestras debo tomar?";
  const next = "¿Qué hago ahora?";
  switch (screen) {
    case "studies":
      return [what, "¿Cómo empiezo un estudio nuevo?", samples];
    case "data":
      return st.empty ? ["¿Cómo organizo mis subgrupos?", what, samples] : [what, "¿Cómo organizo mis subgrupos?", next];
    case "sampling":
      return st.hasResult ? ["¿Qué plan me conviene?", interpret, what, next] : ["¿Qué plan me conviene?", what, next];
    case "design":
      return st.hasResult ? [what, interpret, samples, next] : [what, samples, next];
    case "report":
      return [what, "Resume el reporte", "¿Qué falta por analizar?"];
    case "study":
      return [what, next, samples];
    default:
      return st.hasResult ? [what, interpret, samples, next] : [what, samples, next];
  }
}

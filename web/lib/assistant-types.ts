// Tipos del asistente con IA: reflejan a mano api/app/schemas/assistant.py.
//
// PENDIENTE: cuando se regenere `lib/api-types.ts` con `npm run gen:api` estos tipos
// deben sustituirse por los generados (components["schemas"]["AssistantRequest"], etc.).
// Los eventos del flujo SSE no están en OpenAPI (es `text/event-stream`), así que
// `AssistantEvent` seguirá siendo propio. Este archivo no importa nada para que los
// módulos puros que lo usan puedan probarse con Node sin el empaquetador.

export type AssistantScreen =
  | "studies"
  | "study"
  | "data"
  | "variables"
  | "attributes"
  | "assumptions"
  | "capability"
  | "design"
  | "sampling"
  | "report";

export interface AssistantStatus {
  enabled: boolean;
  available: boolean;
  reason?: string | null;
  guests_allowed: boolean;
}

export interface AssistantMessage {
  role: "user" | "assistant";
  /** 1 a 6000 caracteres. */
  content: string;
}

export interface AssistantStudy {
  name?: string;
  company?: string;
  process?: string;
  product?: string;
  characteristic?: string;
  unit?: string;
  data_type?: "variable" | "attribute";
  lsl?: number;
  usl?: number;
  target?: number;
  synthetic?: boolean;
  notes?: string;
}

export interface AssistantContext {
  screen: AssistantScreen;
  study?: AssistantStudy;
  /** JSON libre; el backend responde 422 si supera ~60 KB serializado. */
  view?: Record<string, unknown>;
  /** Hasta 20 resúmenes de conjuntos de datos (nunca filas). */
  datasets?: Record<string, unknown>[];
  /** Hasta 10 límites de Fase I congelados. */
  frozen_limits?: Record<string, unknown>[];
}

export interface AssistantRequest {
  /** De 1 a 30 mensajes. */
  messages: AssistantMessage[];
  context: AssistantContext;
}

/** Eventos del flujo `text/event-stream` de POST /api/assistant/chat. */
export type AssistantEvent =
  | { type: "delta"; text: string }
  | { type: "tool"; name: string; label: string }
  | { type: "done"; stop_reason: string }
  | { type: "error"; detail: string; code: string };

/** Límites del contrato. */
export const ASSISTANT_MAX_MESSAGES = 30;
export const ASSISTANT_MAX_CHARS = 6000;
export const ASSISTANT_MAX_DATASETS = 20;
export const ASSISTANT_MAX_FROZEN = 10;
/**
 * El backend mide el contexto completo (ficha + vista + conjuntos + límites) y responde 422 por
 * encima de 60 KB. El cliente apunta bastante por debajo: 50 KB en total y 40 KB para la vista.
 */
export const ASSISTANT_CONTEXT_LIMIT_BYTES = 60_000;
export const ASSISTANT_CONTEXT_TARGET_BYTES = 50_000;
export const ASSISTANT_VIEW_TARGET_BYTES = 40_000;

// Cliente del asistente con IA (guía asistida). Habla con /api/assistant/* en el mismo
// origen, con el mismo JWT que lib/api.ts. Contrato: api/app/schemas/assistant.py.
//
// - getAssistantStatus(): GET /api/assistant/status.
// - streamChat(): POST /api/assistant/chat como flujo de eventos (generador asíncrono).
//   Los errores previos al flujo (401/403/422/503) se lanzan como ApiError con el `detail`
//   que llega; los errores a mitad de flujo llegan como evento `error`.
// - Con NEXT_PUBLIC_API_MOCK=1 un simulador local emite un texto de ejemplo por trozos y
//   lo advierte como respuesta de ejemplo (igual que los demás mocks de la web).

import { ApiError, authHeaders, detailOf } from "./api";
import { API_MOCK } from "./env";
import { SseParser, decodeEvent } from "./assistant-sse";
import type { AssistantEvent, AssistantRequest, AssistantStatus } from "./assistant-types";

export * from "./assistant-types";
export { prepareHistory } from "./assistant-sse";

const NETWORK_MSG = "No se pudo contactar a la API de cálculo. Revisa tu conexión e inténtalo de nuevo.";

export const isAbort = (e: unknown) => e instanceof DOMException && e.name === "AbortError";

async function failFrom(res: Response): Promise<never> {
  const body: unknown = await res.json().catch(() => null);
  const { detail, code } = detailOf(body, res.status);
  throw new ApiError(detail, res.status, code);
}

/** Estado del asistente para esta sesión. 503 llega como ApiError (no configurado). */
export async function getAssistantStatus(signal?: AbortSignal): Promise<AssistantStatus> {
  if (API_MOCK) return { enabled: true, available: true, reason: null, guests_allowed: true };
  let res: Response;
  try {
    res = await fetch("/api/assistant/status", { headers: await authHeaders(), signal });
  } catch (e) {
    if (isAbort(e)) throw e;
    throw new ApiError(NETWORK_MSG, 0, "network");
  }
  if (!res.ok) return failFrom(res);
  const b = (await res.json()) as Partial<AssistantStatus>;
  return {
    enabled: !!b.enabled,
    available: !!b.available,
    reason: b.reason ?? null,
    guests_allowed: !!b.guests_allowed,
  };
}

/**
 * Envía la conversación y entrega los eventos conforme llegan. Termina tras `done` o `error`.
 * Si el flujo se corta sin ninguno de los dos, emite un `error` propio (code "stream_interrupted").
 * Cancelar con `signal` hace que se lance un AbortError (úsese `isAbort`).
 */
export async function* streamChat(req: AssistantRequest, signal?: AbortSignal): AsyncGenerator<AssistantEvent> {
  if (API_MOCK) {
    yield* mockStream(req, signal);
    return;
  }
  let res: Response;
  try {
    res = await fetch("/api/assistant/chat", {
      method: "POST",
      headers: { ...(await authHeaders()), "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify(req),
      signal,
    });
  } catch (e) {
    if (isAbort(e)) throw e;
    throw new ApiError(NETWORK_MSG, 0, "network");
  }
  if (!res.ok) return failFrom(res);
  if (!res.body) throw new ApiError("Este navegador no permite leer la respuesta en flujo.", res.status, "no_stream");
  if (!(res.headers.get("content-type") ?? "").includes("text/event-stream"))
    throw new ApiError("La API respondió algo distinto de un flujo de eventos. Inténtalo de nuevo.", res.status, "bad_content_type");

  const reader = res.body.getReader();
  const decoder = new TextDecoder("utf-8");
  const parser = new SseParser();
  let finished = false;
  try {
    for (;;) {
      const { done, value } = await reader.read();
      const msgs = done ? [...parser.push(decoder.decode()), ...parser.flush()] : parser.push(decoder.decode(value, { stream: true }));
      for (const m of msgs) {
        const ev = decodeEvent(m);
        if (!ev) continue;
        yield ev;
        if (ev.type === "done" || ev.type === "error") {
          finished = true;
          return;
        }
      }
      if (done) break;
    }
  } catch (e) {
    if (isAbort(e)) throw e;
    if (!finished) {
      yield { type: "error", detail: "La conexión se interrumpió antes de terminar la respuesta.", code: "stream_interrupted" };
      return;
    }
    throw e;
  } finally {
    reader.cancel().catch(() => {});
  }
  if (!finished) yield { type: "error", detail: "La respuesta terminó antes de tiempo. Inténtalo de nuevo.", code: "stream_interrupted" };
}

// --- Simulador (NEXT_PUBLIC_API_MOCK=1) ----------------------------------------------------

function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) return reject(new DOMException("Cancelado", "AbortError"));
    const t = setTimeout(() => {
      signal?.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    const onAbort = () => {
      clearTimeout(t);
      reject(new DOMException("Cancelado", "AbortError"));
    };
    signal?.addEventListener("abort", onAbort, { once: true });
  });
}

const SCREEN_NAME: Record<string, string> = {
  studies: "lista de estudios",
  study: "resumen del estudio",
  data: "Datos",
  variables: "Variables",
  attributes: "Atributos",
  assumptions: "Supuestos",
  capability: "Capacidad",
  design: "Diseño",
  sampling: "Muestreo",
  report: "Reporte",
};

/**
 * Texto de ejemplo. Incluye lo que la pantalla envió (pantalla, claves del contexto y su tamaño)
 * para poder comprobar a simple vista qué viaja al asistente real. Si el último mensaje contiene
 * «simular error» el flujo falla a mitad de camino, para probar el reintento.
 */
function mockText(req: AssistantRequest): string {
  const last = [...req.messages].reverse().find((m) => m.role === "user")?.content ?? "";
  const ctx = req.context;
  const viewKeys = ctx.view ? Object.keys(ctx.view) : [];
  const bytes = ctx.view ? new TextEncoder().encode(JSON.stringify(ctx.view)).length : 0;
  return [
    "**Respuesta de ejemplo.** El asistente no está conectado (modo de ejemplo): este texto no analiza tus datos y no debe usarse para decidir nada.",
    "",
    `Pregunta recibida: «${last.slice(0, 160)}»`,
    "",
    `Lo que me llegó de la pantalla **${SCREEN_NAME[ctx.screen] ?? ctx.screen}**:`,
    "",
    `- Estudio: ${ctx.study?.name ?? "ninguno"}${ctx.study?.data_type ? ` (${ctx.study.data_type === "variable" ? "variables" : "atributos"})` : ""}`,
    `- Contexto de la vista: ${viewKeys.length ? viewKeys.map((k) => `\`${k}\``).join(", ") : "vacío"} (${bytes} bytes)`,
    `- Conjuntos de datos: ${ctx.datasets?.length ?? 0}; límites congelados: ${ctx.frozen_limits?.length ?? 0}`,
    `- Mensajes en el historial: ${req.messages.length}`,
    "",
    "| Qué hace el asistente real | Cómo |",
    "|---|---|",
    "| Explica la pantalla | Con el contexto de arriba |",
    "| Interpreta resultados | Sin recalcular: usa los de la app |",
    "| Sugiere muestras | Con herramientas de cálculo |",
    "",
    "Los cálculos oficiales son siempre los de la aplicación.",
  ].join("\n");
}

async function* mockStream(req: AssistantRequest, signal?: AbortSignal): AsyncGenerator<AssistantEvent> {
  const last = [...req.messages].reverse().find((m) => m.role === "user")?.content ?? "";
  const fail = /simular error/i.test(last);
  yield { type: "tool", name: "revisar_contexto", label: "las cifras de esta pantalla…" };
  await sleep(700, signal);
  const text = mockText(req);
  const stop = fail ? Math.floor(text.length / 3) : text.length;
  for (let i = 0; i < stop; i += 9) {
    await sleep(28, signal);
    yield { type: "delta", text: text.slice(i, Math.min(i + 9, stop)) };
  }
  if (fail) {
    yield { type: "error", detail: "Error simulado a mitad de la respuesta (modo de ejemplo).", code: "mock_error" };
    return;
  }
  yield { type: "done", stop_reason: "end_turn" };
}

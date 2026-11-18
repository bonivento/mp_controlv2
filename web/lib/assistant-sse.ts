// Piezas puras del cliente del asistente: analizador de Server-Sent Events y recorte del
// historial. Sin dependencias de React ni de la red, para poder probarlas con Node.

import {
  ASSISTANT_MAX_CHARS,
  ASSISTANT_MAX_MESSAGES,
  type AssistantEvent,
  type AssistantMessage,
} from "./assistant-types";

export interface SseMessage {
  /** Campo `event:`; "message" si el evento no lo trae. */
  event: string;
  /** Líneas `data:` unidas con "\n". */
  data: string;
}

/**
 * Analizador incremental de SSE (WHATWG HTML, "Server-sent events").
 * - Los trozos pueden cortar el flujo en cualquier punto: en medio de una línea, de un
 *   carácter multibyte (eso lo resuelve TextDecoder con `stream: true` antes de llegar aquí)
 *   o entre el \r y el \n de un fin de línea CRLF.
 * - Un evento termina con una línea en blanco; varias líneas `data:` se unen con "\n".
 * - Se ignoran los comentarios (":..."), `id:` y `retry:`.
 */
export class SseParser {
  private buf = "";
  private event = "";
  private data: string[] = [];
  private hasData = false;

  /** Añade un trozo de texto y devuelve los eventos que quedaron completos. */
  push(chunk: string): SseMessage[] {
    this.buf += chunk;
    const out: SseMessage[] = [];
    const re = /\r\n|\n|\r/g;
    let start = 0;
    for (;;) {
      re.lastIndex = start;
      const m = re.exec(this.buf);
      if (!m) break;
      // Un \r al final del búfer puede ser la primera mitad de un \r\n: se espera al siguiente trozo.
      if (m[0] === "\r" && m.index + 1 === this.buf.length) break;
      const ev = this.line(this.buf.slice(start, m.index));
      if (ev) out.push(ev);
      start = m.index + m[0].length;
    }
    this.buf = this.buf.slice(start);
    return out;
  }

  /** Fin del flujo: procesa lo que quede y entrega el último evento aunque falte la línea en blanco. */
  flush(): SseMessage[] {
    const out: SseMessage[] = [];
    if (this.buf !== "") {
      const ev = this.line(this.buf.replace(/\r$/, ""));
      if (ev) out.push(ev);
      this.buf = "";
    }
    const last = this.dispatch();
    if (last) out.push(last);
    return out;
  }

  private line(line: string): SseMessage | null {
    if (line === "") return this.dispatch();
    if (line.startsWith(":")) return null;
    const i = line.indexOf(":");
    const field = i === -1 ? line : line.slice(0, i);
    let value = i === -1 ? "" : line.slice(i + 1);
    if (value.startsWith(" ")) value = value.slice(1);
    if (field === "event") this.event = value;
    else if (field === "data") {
      this.data.push(value);
      this.hasData = true;
    }
    return null;
  }

  private dispatch(): SseMessage | null {
    const msg = this.hasData ? { event: this.event || "message", data: this.data.join("\n") } : null;
    this.event = "";
    this.data = [];
    this.hasData = false;
    return msg;
  }
}

/** Traduce un evento SSE al evento tipado del contrato; null si es desconocido o está mal formado. */
export function decodeEvent(msg: SseMessage): AssistantEvent | null {
  let body: unknown;
  try {
    body = JSON.parse(msg.data);
  } catch {
    return null;
  }
  if (!body || typeof body !== "object") return null;
  const b = body as Record<string, unknown>;
  const str = (v: unknown, d = "") => (typeof v === "string" ? v : d);
  switch (msg.event) {
    case "delta":
      return typeof b.text === "string" ? { type: "delta", text: b.text } : null;
    case "tool":
      return { type: "tool", name: str(b.name), label: str(b.label) || str(b.name) };
    case "done":
      return { type: "done", stop_reason: str(b.stop_reason, "end_turn") };
    case "error":
      return { type: "error", detail: str(b.detail, "El asistente no pudo responder."), code: str(b.code, "error") };
    default:
      return null; // evento desconocido: se ignora para no romper con versiones nuevas del backend
  }
}

/** Corta sin dejar a medias un par sustituto (emoji), que rompería la codificación JSON. */
function cut(text: string, max: number): string {
  if (text.length <= max) return text;
  let end = max - 1;
  const code = text.charCodeAt(end - 1);
  if (code >= 0xd800 && code <= 0xdbff) end -= 1;
  return `${text.slice(0, end)}…`;
}

/**
 * Historial que se envía: sin mensajes vacíos, cada uno de hasta 6000 caracteres, como mucho
 * los 30 más recientes y empezando por un mensaje del usuario (los más antiguos se descartan).
 */
export function prepareHistory(messages: AssistantMessage[]): AssistantMessage[] {
  const clean = messages
    .filter((m) => m.content.trim() !== "")
    .map((m) => ({ role: m.role, content: cut(m.content, ASSISTANT_MAX_CHARS) }));
  const tail = clean.slice(-ASSISTANT_MAX_MESSAGES);
  while (tail.length > 0 && tail[0].role !== "user") tail.shift();
  return tail;
}

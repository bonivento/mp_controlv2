// Markdown básico del asistente -> árbol de bloques. Es un analizador propio y mínimo para no
// añadir dependencias: la salida es un árbol de datos que components/assistant/Markdown.tsx
// pinta con elementos de React. El texto del modelo nunca se inserta como HTML: cualquier
// etiqueta que escriba el modelo se muestra literal.
//
// Soporta: párrafos (un salto de línea simple es un salto), títulos (# a ######), listas con viñetas
// y numeradas (con anidación por sangría), citas (>), bloques de código con ```, regla horizontal,
// tablas con barras (|), y en línea: **negrita**, *cursiva*, `código` y [texto](https://enlace).
// Los enlaces solo se aceptan con http, https o mailto.

export type Inline =
  | { t: "text"; text: string }
  | { t: "br" }
  | { t: "strong"; children: Inline[] }
  | { t: "em"; children: Inline[] }
  | { t: "code"; text: string }
  | { t: "link"; href: string; children: Inline[] };

export interface ListItem {
  inline: Inline[];
  children: Block[];
}

export type Align = "left" | "center" | "right" | null;

export type Block =
  | { t: "p"; inline: Inline[] }
  | { t: "heading"; level: number; inline: Inline[] }
  | { t: "list"; ordered: boolean; start: number; items: ListItem[] }
  | { t: "code"; lang: string; text: string }
  | { t: "quote"; blocks: Block[] }
  | { t: "hr" }
  | { t: "table"; header: Inline[][]; align: Align[]; rows: Inline[][][] };

const ESCAPABLE = "\\`*_{}[]()#+-.!|>~<";

/** Solo enlaces seguros; cualquier otro esquema (javascript:, data:…) deja el texto sin enlace. */
export function safeHref(raw: string): string | null {
  const href = raw.trim();
  if (/^https?:\/\/[^\s]+$/i.test(href) || /^mailto:[^\s]+$/i.test(href)) return href;
  return null;
}

// --- En línea -----------------------------------------------------------------------------

const isWord = (c: string | undefined) => !!c && /[\p{L}\p{N}]/u.test(c);
const isSpace = (c: string | undefined) => c === undefined || /\s/.test(c);

function pushText(out: Inline[], text: string) {
  if (!text) return;
  const parts = text.split("\n");
  parts.forEach((p, i) => {
    if (i > 0) out.push({ t: "br" });
    if (p) {
      const last = out[out.length - 1];
      if (last && last.t === "text") last.text += p;
      else out.push({ t: "text", text: p });
    }
  });
}

/** Cierre de `**`/`*` a partir de `from`: la primera ocurrencia válida (no precedida de espacio). */
function findClose(s: string, marker: string, from: number): number {
  let i = from;
  for (;;) {
    i = s.indexOf(marker, i);
    if (i === -1) return -1;
    if (s[i - 1] === "\\") {
      i += 1;
      continue;
    }
    if (marker.length === 1 && s[i + 1] === marker) {
      // Un "**" dentro de una cursiva simple: se salta el par completo.
      i += 2;
      continue;
    }
    if (!isSpace(s[i - 1]) && i > from) return i;
    i += marker.length;
  }
}

export function parseInline(s: string): Inline[] {
  const out: Inline[] = [];
  let buf = "";
  const flush = () => {
    pushText(out, buf);
    buf = "";
  };
  let i = 0;
  while (i < s.length) {
    const c = s[i];
    // Escape: \* -> *
    if (c === "\\" && i + 1 < s.length && ESCAPABLE.includes(s[i + 1])) {
      buf += s[i + 1];
      i += 2;
      continue;
    }
    // Código en línea: `x` o ``x``
    if (c === "`") {
      let n = 1;
      while (s[i + n] === "`") n++;
      const fence = "`".repeat(n);
      const end = s.indexOf(fence, i + n);
      if (end !== -1 && s[end + n] !== "`") {
        flush();
        let code = s.slice(i + n, end).replace(/\n/g, " ");
        if (code.length > 2 && code.startsWith(" ") && code.endsWith(" ")) code = code.slice(1, -1);
        out.push({ t: "code", text: code });
        i = end + n;
        continue;
      }
      buf += fence;
      i += n;
      continue;
    }
    // Negrita: **x** (y __x__ entre palabras)
    if ((c === "*" || c === "_") && s[i + 1] === c && !isSpace(s[i + 2])) {
      const marker = c + c;
      const end = findClose(s, marker, i + 2);
      if (end !== -1 && (c === "*" || (!isWord(s[i - 1]) && !isWord(s[end + 2])))) {
        flush();
        out.push({ t: "strong", children: parseInline(s.slice(i + 2, end)) });
        i = end + 2;
        continue;
      }
    }
    // Cursiva: *x* o _x_ (el guion bajo solo en límites de palabra, para no romper snake_case)
    if ((c === "*" || c === "_") && s[i + 1] !== c && !isSpace(s[i + 1])) {
      const end = findClose(s, c, i + 1);
      if (end !== -1 && (c === "*" || (!isWord(s[i - 1]) && !isWord(s[end + 1])))) {
        flush();
        out.push({ t: "em", children: parseInline(s.slice(i + 1, end)) });
        i = end + 1;
        continue;
      }
    }
    // Enlace: [texto](url)
    if (c === "[") {
      const close = s.indexOf("]", i + 1);
      if (close !== -1 && s[close + 1] === "(") {
        const end = s.indexOf(")", close + 2);
        if (end !== -1) {
          const label = s.slice(i + 1, close);
          const href = safeHref(s.slice(close + 2, end));
          flush();
          if (href && label.trim()) out.push({ t: "link", href, children: parseInline(label) });
          else pushText(out, label);
          i = end + 1;
          continue;
        }
      }
    }
    buf += c;
    i += 1;
  }
  flush();
  return out;
}

// --- Bloques ------------------------------------------------------------------------------

const RE_FENCE = /^\s{0,3}(`{3,}|~{3,})\s*([^\s`]*)\s*$/;
const RE_HR = /^\s{0,3}([-*_])(?:\s*\1){2,}\s*$/;
const RE_HEADING = /^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$/;
const RE_LIST = /^(\s*)([-*+]|\d{1,9}[.)])\s+(.*)$/;
const RE_QUOTE = /^\s{0,3}>\s?(.*)$/;
const RE_TABLE_SEP = /^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$/;

const indentOf = (line: string) => line.length - line.trimStart().length;

function splitRow(line: string): string[] {
  let t = line.trim();
  if (t.startsWith("|")) t = t.slice(1);
  if (t.endsWith("|") && !t.endsWith("\\|")) t = t.slice(0, -1);
  const cells: string[] = [];
  let cur = "";
  for (let i = 0; i < t.length; i++) {
    if (t[i] === "\\" && t[i + 1] === "|") {
      cur += "|";
      i++;
    } else if (t[i] === "|") {
      cells.push(cur.trim());
      cur = "";
    } else cur += t[i];
  }
  cells.push(cur.trim());
  return cells;
}

function startsBlock(line: string, next: string | undefined): boolean {
  if (RE_FENCE.test(line) || RE_HR.test(line) || RE_HEADING.test(line) || RE_QUOTE.test(line)) return true;
  // Como en CommonMark: una viñeta o una lista numerada que empieza en 1 interrumpen un párrafo.
  const li = RE_LIST.exec(line);
  if (li && (!/\d/.test(li[2]) || /^1[.)]$/.test(li[2]))) return true;
  return line.includes("|") && next !== undefined && RE_TABLE_SEP.test(next) && next.includes("-");
}

export function parseMarkdown(src: string): Block[] {
  return parseLines(src.replace(/\r\n?/g, "\n").split("\n"));
}

function parseLines(lines: string[]): Block[] {
  const blocks: Block[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (line.trim() === "") {
      i++;
      continue;
    }
    // Bloque de código (sin cierre: llega hasta el final, útil mientras se recibe en flujo)
    const fence = RE_FENCE.exec(line);
    if (fence) {
      const mark = fence[1];
      const body: string[] = [];
      i++;
      const closes = (l: string) => {
        const t = l.trim();
        return t.length >= mark.length && t === mark[0].repeat(t.length);
      };
      while (i < lines.length && !closes(lines[i])) {
        body.push(lines[i]);
        i++;
      }
      i++; // línea de cierre
      blocks.push({ t: "code", lang: fence[2], text: body.join("\n") });
      continue;
    }
    if (RE_HR.test(line)) {
      blocks.push({ t: "hr" });
      i++;
      continue;
    }
    const h = RE_HEADING.exec(line);
    if (h) {
      blocks.push({ t: "heading", level: h[1].length, inline: parseInline(h[2]) });
      i++;
      continue;
    }
    // Tabla
    if (line.includes("|") && i + 1 < lines.length && RE_TABLE_SEP.test(lines[i + 1]) && lines[i + 1].includes("-")) {
      const header = splitRow(line);
      const sep = splitRow(lines[i + 1]);
      if (sep.length === header.length || sep.length > 0) {
        const align: Align[] = header.map((_, k) => {
          const c = sep[k] ?? "";
          const l = c.startsWith(":");
          const r = c.endsWith(":");
          return l && r ? "center" : r ? "right" : l ? "left" : null;
        });
        i += 2;
        const rows: Inline[][][] = [];
        while (i < lines.length && lines[i].trim() !== "" && lines[i].includes("|")) {
          const cells = splitRow(lines[i]);
          rows.push(header.map((_, k) => parseInline(cells[k] ?? "")));
          i++;
        }
        blocks.push({ t: "table", header: header.map((c) => parseInline(c)), align, rows });
        continue;
      }
    }
    // Cita
    if (RE_QUOTE.test(line)) {
      const inner: string[] = [];
      while (i < lines.length && RE_QUOTE.test(lines[i])) {
        inner.push(RE_QUOTE.exec(lines[i])![1]);
        i++;
      }
      blocks.push({ t: "quote", blocks: parseLines(inner) });
      continue;
    }
    // Lista
    const li = RE_LIST.exec(line);
    if (li) {
      const baseIndent = li[1].length;
      const ordered = /\d/.test(li[2]);
      const items: ListItem[] = [];
      const start = ordered ? parseInt(li[2], 10) : 1;
      while (i < lines.length) {
        const m = RE_LIST.exec(lines[i]);
        if (!m || m[1].length !== baseIndent || /\d/.test(m[2]) !== ordered) break;
        const rest: string[] = [];
        i++;
        // Líneas siguientes: sangradas más que la viñeta (anidadas o continuación) y los blancos entre ellas.
        while (i < lines.length) {
          const l = lines[i];
          if (l.trim() === "") {
            let j = i;
            while (j < lines.length && lines[j].trim() === "") j++;
            if (j < lines.length && indentOf(lines[j]) > baseIndent) {
              rest.push("");
              i++;
              continue;
            }
            break;
          }
          if (indentOf(l) > baseIndent) {
            rest.push(l);
            i++;
            continue;
          }
          break;
        }
        const minIndent = rest.filter((r) => r.trim() !== "").reduce((a, r) => Math.min(a, indentOf(r)), Infinity);
        const children = parseLines(rest.map((r) => (r.trim() === "" ? "" : r.slice(Number.isFinite(minIndent) ? minIndent : 0))));
        items.push({ inline: parseInline(m[3]), children });
        // Un salto en blanco entre elementos del mismo nivel no corta la lista.
        let j = i;
        while (j < lines.length && lines[j].trim() === "") j++;
        if (j > i && j < lines.length) {
          const nx = RE_LIST.exec(lines[j]);
          if (nx && nx[1].length === baseIndent && /\d/.test(nx[2]) === ordered) i = j;
        }
      }
      blocks.push({ t: "list", ordered, start, items });
      continue;
    }
    // Párrafo: hasta una línea en blanco o el comienzo de otro bloque
    const para: string[] = [line];
    i++;
    while (i < lines.length && lines[i].trim() !== "" && !startsBlock(lines[i], lines[i + 1])) {
      para.push(lines[i]);
      i++;
    }
    blocks.push({ t: "p", inline: parseInline(para.map((p) => p.trim()).join("\n")) });
  }
  return blocks;
}

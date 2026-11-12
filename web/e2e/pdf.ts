import zlib from "node:zlib";

/**
 * Lector mínimo de PDFs generados por Chromium (Skia): cuenta páginas y extrae el texto.
 * No depende de librerías externas: descomprime los flujos Flate, lee los mapas ToUnicode de cada
 * fuente y traduce los glifos de los operadores Tj/TJ. Solo sirve para comprobar contenido en pruebas.
 */
export interface PdfInfo {
  pages: number;
  text: string;
}

interface Obj {
  dict: string;
  stream?: Buffer;
}

function parseObjects(buf: Buffer): Map<number, Obj> {
  const latin = buf.toString("latin1");
  const objs = new Map<number, Obj>();
  const re = /(\d+) 0 obj\b/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(latin))) {
    const start = m.index + m[0].length;
    const end = latin.indexOf("endobj", start);
    if (end < 0) break;
    const body = latin.slice(start, end);
    const sIdx = body.indexOf("stream");
    let dict = body;
    let stream: Buffer | undefined;
    if (sIdx >= 0) {
      dict = body.slice(0, sIdx);
      let from = start + sIdx + "stream".length;
      if (latin[from] === "\r") from++;
      if (latin[from] === "\n") from++;
      const to = latin.lastIndexOf("endstream", end);
      let raw = buf.subarray(from, to);
      if (/FlateDecode/.test(dict)) {
        try {
          raw = zlib.inflateSync(raw);
        } catch {
          raw = Buffer.alloc(0);
        }
      }
      stream = raw;
    }
    objs.set(Number(m[1]), { dict, stream });
    re.lastIndex = end;
  }
  return objs;
}

/** Mapa glifo -> texto de un CMap ToUnicode. */
function parseCMap(cmap: string): Map<number, string> {
  const map = new Map<number, string>();
  const u = (hex: string) => {
    let s = "";
    for (let i = 0; i < hex.length; i += 4) s += String.fromCharCode(parseInt(hex.slice(i, i + 4), 16));
    return s;
  };
  for (const blk of cmap.matchAll(/beginbfchar([\s\S]*?)endbfchar/g))
    for (const r of blk[1].matchAll(/<([0-9a-fA-F]+)>\s*<([0-9a-fA-F]+)>/g)) map.set(parseInt(r[1], 16), u(r[2]));
  for (const blk of cmap.matchAll(/beginbfrange([\s\S]*?)endbfrange/g))
    for (const r of blk[1].matchAll(/<([0-9a-fA-F]+)>\s*<([0-9a-fA-F]+)>\s*(?:<([0-9a-fA-F]+)>|\[([^\]]*)\])/g)) {
      const lo = parseInt(r[1], 16);
      const hi = parseInt(r[2], 16);
      if (r[3]) {
        const base = u(r[3]);
        for (let g = lo; g <= hi; g++) map.set(g, base.slice(0, -1) + String.fromCharCode(base.charCodeAt(base.length - 1) + (g - lo)));
      } else {
        const items = [...r[4].matchAll(/<([0-9a-fA-F]+)>/g)].map((x) => u(x[1]));
        items.forEach((t, i) => map.set(lo + i, t));
      }
    }
  return map;
}

export function readPdf(buf: Buffer): PdfInfo {
  const objs = parseObjects(buf);
  const pages = [...objs.values()].filter((o) => /\/Type\s*\/Page\b(?!s)/.test(o.dict)).length;

  // Fuentes: nombre de recurso (/F4) -> mapa ToUnicode.
  const fontByName = new Map<string, Map<number, string>>();
  for (const o of objs.values()) {
    for (const f of o.dict.matchAll(/\/(F\d+)\s+(\d+) 0 R/g)) {
      const font = objs.get(Number(f[2]));
      const tu = font?.dict.match(/\/ToUnicode\s+(\d+) 0 R/);
      const cm = tu ? objs.get(Number(tu[1]))?.stream : undefined;
      if (cm) fontByName.set(f[1], parseCMap(cm.toString("latin1")));
    }
  }

  let text = "";
  for (const o of objs.values()) {
    if (!o.stream || !/BT/.test(o.stream.toString("latin1", 0, 4000) + "BT")) continue;
    const c = o.stream.toString("latin1");
    if (!/\bBT\b/.test(c)) continue;
    let cur: Map<number, string> | undefined;
    const tokens = c.matchAll(/\/(F\d+)\s+[\d.]+\s+Tf|\[((?:[^\]\\]|\\.)*)\]\s*TJ|<([0-9a-fA-F]+)>\s*Tj|\bET\b/g);
    for (const t of tokens) {
      if (t[1]) cur = fontByName.get(t[1]);
      else if (t[0] === "ET") text += "\n";
      else {
        const hexes = t[2] != null ? [...t[2].matchAll(/<([0-9a-fA-F]+)>|(-?\d+(?:\.\d+)?)/g)] : [[t[0], t[3]]];
        for (const h of hexes) {
          const hex = (h as RegExpMatchArray)[1] ?? (t[2] == null ? (h as string[])[1] : undefined);
          if (hex) {
            for (let i = 0; i < hex.length; i += 4) text += cur?.get(parseInt(hex.slice(i, i + 4), 16)) ?? "";
          } else if (t[2] != null && Number((h as RegExpMatchArray)[2]) < -200) text += " ";
        }
      }
    }
  }
  return { pages, text };
}

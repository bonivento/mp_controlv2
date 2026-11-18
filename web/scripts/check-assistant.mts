// Comprobaciones a mano de las piezas puras del asistente (analizador SSE, historial y reducción
// del contexto). Ejecutar con:  npm run check:assistant
import assert from "node:assert/strict";
import { SseParser, decodeEvent, prepareHistory } from "../lib/assistant-sse";
import { REDUCE_LEVELS, fitContext, fitView, jsonBytes, reduceNode, studyToContext, suggestionsFor } from "../lib/assistant-context";
import { mockVariablesChart, mockAttributesChart } from "../lib/fixtures/charts";
import { mockAssumptions, mockCapability } from "../lib/fixtures/analysis";
import { mockArl, mockCompare } from "../lib/fixtures/design";
import { mockDoubleEvaluate, mockSingleDesign } from "../lib/fixtures/sampling";
import { mockSummary } from "../lib/fixtures/data";
import { rng } from "../lib/fixtures/engine";
import { parseInline, parseMarkdown, safeHref, type Block, type Inline } from "../lib/assistant-markdown";

let passed = 0;
const ok = (name: string, fn: () => void) => {
  fn();
  passed++;
  console.log(`ok  ${name}`);
};

// ---------------------------------------------------------------- SSE
const STREAM =
  'event: tool\ndata: {"name":"x","label":"Calculando…"}\n\n' +
  'event: delta\ndata: {"text":"Hola, "}\n\n' +
  ': comentario de keep-alive\n\n' +
  'event: delta\ndata: {"text":"mundo ñ 😀"}\n\n' +
  'event: done\ndata: {"stop_reason":"end_turn"}\n\n';

function parseAll(chunks: string[]) {
  const p = new SseParser();
  const out = chunks.flatMap((c) => p.push(c));
  return [...out, ...p.flush()].map(decodeEvent);
}
const EXPECTED = parseAll([STREAM]);

ok("SSE: flujo completo en un solo trozo", () => {
  assert.deepEqual(EXPECTED.map((e) => e?.type), ["tool", "delta", "delta", "done"]);
  assert.equal((EXPECTED[2] as { text: string }).text, "mundo ñ 😀");
});
ok("SSE: partido en trozos de 1 carácter", () => {
  assert.deepEqual(parseAll([...STREAM]), EXPECTED);
});
ok("SSE: 500 particiones aleatorias dan el mismo resultado", () => {
  const r = rng(7);
  for (let k = 0; k < 500; k++) {
    const chunks: string[] = [];
    let i = 0;
    while (i < STREAM.length) {
      const n = 1 + Math.floor(r() * 25);
      chunks.push(STREAM.slice(i, i + n));
      i += n;
    }
    assert.deepEqual(parseAll(chunks), EXPECTED);
  }
});
ok("SSE: fines de línea CRLF y CR, también partidos entre \\r y \\n", () => {
  const crlf = STREAM.replace(/\n/g, "\r\n");
  assert.deepEqual(parseAll([crlf]), EXPECTED);
  assert.deepEqual(parseAll([...crlf]), EXPECTED);
  const cr = STREAM.replace(/\n/g, "\r");
  assert.deepEqual(parseAll([cr]), EXPECTED);
  assert.deepEqual(parseAll([...cr]), EXPECTED);
});
ok("SSE: varias líneas data: se unen con salto de línea (JSON válido en varias líneas)", () => {
  const msg = 'event: delta\ndata: {"text":\ndata: "dos líneas"}\n\n';
  assert.deepEqual(parseAll([msg]), [{ type: "delta", text: "dos líneas" }]);
  assert.deepEqual(parseAll([...msg]), [{ type: "delta", text: "dos líneas" }]);
  const p = new SseParser();
  assert.deepEqual(p.push("data: a\ndata: b\ndata:\ndata: d\n\n"), [{ event: "message", data: "a\nb\n\nd" }]);
});
ok("SSE: 'data:' sin espacio, 'data' sin dos puntos, campos id/retry ignorados", () => {
  const p = new SseParser();
  assert.deepEqual(p.push('id: 5\nretry: 100\nevent:delta\ndata:{"text":"x"}\n\n'), [{ event: "delta", data: '{"text":"x"}' }]);
  assert.deepEqual(p.push("data\n\n"), [{ event: "message", data: "" }]);
});
ok("SSE: evento final sin línea en blanco se entrega al cerrar (flush)", () => {
  assert.deepEqual(parseAll(['event: done\ndata: {"stop_reason":"max_tokens"}']), [{ type: "done", stop_reason: "max_tokens" }]);
});
ok("SSE: eventos desconocidos o con JSON roto se ignoran sin lanzar", () => {
  assert.deepEqual(parseAll(['event: ping\ndata: {}\n\nevent: delta\ndata: {roto\n\nevent: delta\ndata: {"text":"ok"}\n\n']), [null, null, { type: "delta", text: "ok" }]);
});
ok("SSE: error a mitad de flujo conserva detail y code", () => {
  assert.deepEqual(parseAll(['event: error\ndata: {"detail":"Se agotó el cupo.","code":"quota"}\n\n']), [{ type: "error", detail: "Se agotó el cupo.", code: "quota" }]);
});

// ---------------------------------------------------------------- historial
ok("historial: recorta a 30, empieza por usuario, trunca a 6000 y quita vacíos", () => {
  const msgs = Array.from({ length: 41 }, (_, i) => ({ role: (i % 2 === 0 ? "user" : "assistant") as "user" | "assistant", content: `m${i}` }));
  const h = prepareHistory(msgs);
  assert.ok(h.length <= 30);
  assert.equal(h[0].role, "user");
  assert.equal(h[h.length - 1].content, "m40");
  const long = prepareHistory([{ role: "user", content: "a".repeat(9000) }, { role: "assistant", content: "  " }]);
  assert.equal(long.length, 1);
  assert.equal(long[0].content.length, 6000);
  const emoji = prepareHistory([{ role: "user", content: "x".repeat(5998) + "😀😀" }]);
  assert.ok(emoji[0].content.length <= 6000);
  assert.ok(!/[\ud800-\udbff]…$/.test(emoji[0].content), "no deja un par sustituto a medias");
});

// ---------------------------------------------------------------- reducción
const r = rng(42);
const normal = () => {
  let s = 0;
  for (let i = 0; i < 12; i++) s += r();
  return s - 6;
};
const ALL_RULES = ["WE1", "WE2", "WE3", "WE4", "N1", "N2", "N3", "N4", "N5", "N6", "N7", "N8"] as const;

// Casos grandes: lo peor que puede producir la API con datos reales (el límite de subgrupos
// de la API es mucho menor que estos; se usa un margen de varias veces).
const subgroups = Array.from({ length: 600 }, (_, i) => Array.from({ length: 5 }, () => 10 + normal() * (i > 300 ? 2.5 : 1) + (i % 40 === 0 ? 4 : 0)));
const xbarR = mockVariablesChart({ chart_type: "xbar_r", phase: "I", subgroups, labels: subgroups.map((_, i) => `S${i + 1}`), excluded: [], limits: null, limit_width: 3, rules: { enabled: [...ALL_RULES] } });
const imr = mockVariablesChart({ chart_type: "i_mr", phase: "I", subgroups: Array.from({ length: 3000 }, (_, i) => [50 + normal() * (1 + i / 1500)]), labels: null, excluded: [], limits: null, limit_width: 3, rules: { enabled: [...ALL_RULES] } } as never);
const counts = Array.from({ length: 1500 }, () => Math.round(20 + normal() * 6));
const pChart = mockAttributesChart({ chart_type: "p", phase: "I", counts, sizes: counts.map(() => 200 + Math.round(r() * 50)), labels: counts.map((_, i) => `L${i + 1}`), excluded: [], limits: null, limit_width: 3, rules: { enabled: [...ALL_RULES] } } as never);
const values = Array.from({ length: 5000 }, () => 100 + normal());
const assumptions = mockAssumptions({ values, alpha: 0.05 });
const capability = mockCapability({ subgroups: subgroups.slice(0, 200), lsl: 6, usl: 14, target: 10, confidence: 0.95, is_stable: false, is_normal: false } as never);
const arl = mockArl({ chart: "xbar", n: 5, limit_width: 3, sampling_interval: 1, shifts: [0.25, 0.5, 0.75, 1, 1.25, 1.5, 1.75, 2, 2.5, 3], rules: { enabled: ["WE1", "WE2", "WE3", "WE4"] }, max_runs: 200, max_length: 5000, seed: 1 } as never);
const compare = mockCompare({ n_values: [3, 5, 7, 10], limit_widths: [2.5, 3], sampling_intervals: [0.5, 1, 2], shift: 1 } as never);
const single = mockSingleDesign({ aql: 0.01, alpha: 0.05, ltpd: 0.06, beta: 0.1, lot_size: 2000, distribution: "binomial" } as never);
const double = mockDoubleEvaluate({ n1: 50, c1: 1, r1: 4, n2: 100, c2: 4, lot_size: 2000, aql: 0.01, ltpd: 0.06 } as never);
const summary = mockSummary({ subgroups, labels: subgroups.map((_, i) => `S${i + 1}`) } as never);

const cases: [string, Record<string, unknown>][] = [
  ["Variables X-barra/R, 600 subgrupos, 12 reglas", { parameters: { phase: "I", chartType: "xbar_r", subgroups }, result: xbarR }],
  ["Variables I-MR, 3000 puntos, 12 reglas", { parameters: { phase: "I", chartType: "i_mr" }, result: imr }],
  ["Atributos p, 1500 puntos, 12 reglas", { parameters: { phase: "II" }, result: pChart }],
  ["Supuestos, 5000 observaciones", { request: { values, alpha: 0.05 }, result: assumptions }],
  ["Capacidad, 200 subgrupos", { request: { subgroups: subgroups.slice(0, 200), lsl: 6, usl: 14 }, result: capability }],
  ["Diseño: ARL + comparador", { arl, compare }],
  ["Muestreo: plan simple + doble", { single, double }],
  ["Datos: resumen de 600 subgrupos", { summary }],
];

for (const [name, view] of cases) {
  const raw = jsonBytes(view);
  const t0 = performance.now();
  const f = fitView(view);
  const ms = performance.now() - t0;
  ok(`contexto: ${name}: ${raw} B -> ${f.bytes} B (nivel ${f.level}, ${ms.toFixed(0)} ms)`, () => {
    assert.ok(f.bytes <= 40_000, `excede 40 KB: ${f.bytes}`);
    assert.ok(f.bytes < 60_000);
    assert.equal(f.bytes, jsonBytes(f.view));
    const s = JSON.stringify(f.view);
    assert.ok(!/NaN|Infinity/.test(s));
  });
}

ok("contexto: un gráfico conserva límites, parámetros, violaciones, interpretación y puntos con señal", () => {
  const f = fitView({ result: xbarR });
  const res = f.view.result as Record<string, unknown>;
  assert.deepEqual(Object.keys(res).sort(), Object.keys(xbarR).sort());
  assert.deepEqual((res.limits as { params: unknown }).params, xbarR.limits.params);
  const it = res.interpretation as { summary: string; findings: string[]; warnings: string[]; findings_total?: number };
  assert.equal(it.summary, xbarR.interpretation.summary);
  assert.deepEqual(it.warnings, xbarR.interpretation.warnings);
  assert.deepEqual(it.findings, xbarR.interpretation.findings.slice(0, it.findings.length));
  assert.equal(it.findings_total, xbarR.interpretation.findings.length);
  const small = fitView({ interpretation: capability.interpretation }).view.interpretation;
  assert.deepEqual(small, capability.interpretation, "una interpretación corta viaja idéntica");
  assert.equal(res.in_control, xbarR.in_control);
  const c0 = (res.charts as Record<string, unknown>[])[0];
  assert.equal(c0.n_points, xbarR.charts[0].values.length);
  assert.equal(c0.n_violations, xbarR.charts[0].violations.length);
  const sig = c0.signal_points as { index: number; value: number }[];
  assert.ok(sig.length > 0);
  const real = xbarR.charts[0];
  for (const p of sig) assert.equal(p.value, real.values[real.indices.indexOf(p.index)]);
  assert.ok(!("values" in c0), "la serie larga no viaja entera");
});
ok("contexto: el panel del rango móvil (índices desplazados) apunta al valor correcto", () => {
  const mr = imr.charts[1];
  const f = fitView({ result: imr });
  const c1 = ((f.view.result as { charts: Record<string, unknown>[] }).charts)[1];
  for (const p of c1.signal_points as { index: number; value: number }[]) assert.equal(p.value, mr.values[mr.indices.indexOf(p.index)]);
});
ok("contexto: las filas crudas y las matrices de observaciones nunca viajan", () => {
  const f = fitView({ parameters: { subgroups }, rows: subgroups.map((v, i) => ({ label: `S${i}`, values: v })), request: { values: [1, 2, 3] } });
  const s = JSON.stringify(f.view);
  const sample = subgroups[7][2].toString().slice(0, 8);
  assert.ok(!s.includes(sample), "aparece una observación cruda");
  assert.deepEqual((f.view.parameters as { subgroups: unknown }).subgroups, { n_filas: 600, largos_de_fila: [5], nota: "Observaciones no incluidas" });
  assert.deepEqual(f.view.rows, { n_filas: 600, nota: "Filas de datos no incluidas" });
});
ok("contexto: caso patológico (textos de 1 MB, anidamiento profundo, miles de claves) cabe en 40 KB", () => {
  let deep: Record<string, unknown> = { x: "fin" };
  for (let i = 0; i < 200; i++) deep = { d: deep };
  const wide = Object.fromEntries(Array.from({ length: 5000 }, (_, i) => [`k${i}`, "z".repeat(5000)]));
  const f = fitView({ texto: "t".repeat(1_000_000), deep, wide, n: NaN, inf: Infinity, nulo: undefined });
  assert.ok(f.bytes <= 40_000, `${f.bytes}`);
  assert.ok(!/NaN|Infinity/.test(JSON.stringify(f.view)));
});
ok("contexto: sin presupuesto posible se descartan claves y se avisa", () => {
  const f = fitView({ a: "x".repeat(10_000), b: "y".repeat(10_000) }, 500);
  assert.ok(f.level === -1 || f.bytes <= 500);
  assert.ok(f.bytes <= 500 + 200);
});
ok("contexto completo: el peor caso (20 conjuntos, 10 límites con causas, ficha larga, vista enorme) queda bajo 50 KB", () => {
  const datasets = Array.from({ length: 20 }, (_, i) => ({ name: `Conjunto ${i}`.padEnd(120, "x"), phase: "I", kind: "variable", n_subgroups: 500, subgroup_size: "n = 5", source_file: "a".repeat(120), subgrouping: { method: "column", layout: "wide", column: "c", value_columns: Array.from({ length: 12 }, (_, k) => `x${k}`), justification: "j".repeat(200) }, cleaning_entries: 40, saved_at: "2026-01-01T00:00:00Z" }));
  const frozen = Array.from({ length: 10 }, () => ({ chart_type: "xbar_r", from_dataset: "d".repeat(120), frozen_at: "2026-01-01T00:00:00Z", params: { mu: 1, sigma: 2, r_bar: 3 }, points_used: 100, limit_width: 3, excluded: Array.from({ length: 8 }, (_, k) => ({ index: k, label: String(k), cause: "c".repeat(120) })), n_excluded: 30 }));
  const study = studyToContext({ name: "n".repeat(300), company: "c".repeat(300), process: "p".repeat(400), product: "q".repeat(400), characteristic: "x".repeat(400), unit: "u".repeat(60), data_type: "variable", lsl: 1, usl: 2, target: 1.5, is_synthetic: true, notes: "z".repeat(3000) });
  const t0 = performance.now();
  const f = fitContext({ screen: "variables", study, datasets, frozen_limits: frozen, view: { result: xbarR, otro: imr, mas: assumptions, x: "t".repeat(500_000) } });
  console.log(`      (peor caso: ${f.totalBytes} B en total, vista ${f.viewBytes} B, ${(performance.now() - t0).toFixed(0)} ms)`);
  assert.ok(f.totalBytes <= 50_000, `${f.totalBytes}`);
  assert.equal(f.totalBytes, jsonBytes(f.context));
  const normal = fitContext({ screen: "variables", study, view: { resultado: xbarR } });
  assert.ok(normal.totalBytes < 25_000);
  assert.deepEqual(fitContext({ screen: "studies" }).context, { screen: "studies" });
});
ok("contexto: los niveles de recorte son estrictamente decrecientes", () => {
  for (let i = 1; i < REDUCE_LEVELS.length; i++) assert.ok(REDUCE_LEVELS[i].arrayMax < REDUCE_LEVELS[i - 1].arrayMax);
  assert.equal(reduceNode(undefined, REDUCE_LEVELS[0], 0), undefined);
});
ok("estudio: sin nulos, textos acotados, tipos del contrato", () => {
  const s = studyToContext({ name: "n".repeat(500), company: null, lsl: 1, usl: null, data_type: "variable", is_synthetic: true, notes: "x".repeat(5000) });
  assert.equal(s.name!.length, 200);
  assert.equal(s.notes!.length, 2000);
  assert.ok(!("company" in s) && !("usl" in s));
  assert.equal(s.synthetic, true);
});
ok("sugerencias: dependen de la pantalla y del estado", () => {
  assert.equal(suggestionsFor("data", { empty: true })[0], "¿Cómo organizo mis subgrupos?");
  assert.equal(suggestionsFor("sampling")[0], "¿Qué plan me conviene?");
  assert.ok(suggestionsFor("variables", { hasResult: true }).includes("Interpreta estos resultados"));
  assert.ok(!suggestionsFor("variables", { hasResult: false }).includes("Interpreta estos resultados"));
});

// ---------------------------------------------------------------- Markdown
const plain = (il: Inline[]): string => il.map((x) => (x.t === "text" ? x.text : x.t === "br" ? "\n" : x.t === "code" ? x.text : plain(x.children))).join("");
ok("markdown: párrafos, negrita, cursiva y código en línea", () => {
  const b = parseMarkdown("Hola **mundo** con *énfasis* y `x_bar` listo.\n\nSegundo párrafo.");
  assert.equal(b.length, 2);
  const p = b[0] as Extract<Block, { t: "p" }>;
  assert.deepEqual(p.inline.map((x) => x.t), ["text", "strong", "text", "em", "text", "code", "text"]);
  assert.equal(plain(p.inline), "Hola mundo con énfasis y x_bar listo.");
});
ok("markdown: asteriscos sueltos y snake_case no se interpretan", () => {
  assert.equal(plain(parseInline("2 * 3 * 4 y mi_variable_larga")), "2 * 3 * 4 y mi_variable_larga");
  assert.deepEqual(parseInline("**sin cerrar").map((x) => x.t), ["text"]);
});
ok("markdown: listas con viñetas, numeradas y anidadas", () => {
  const b = parseMarkdown("- uno\n- dos\n  - dos.a\n  - dos.b\n- tres\n\n1. a\n2. b");
  assert.equal(b.length, 2);
  const l = b[0] as Extract<Block, { t: "list" }>;
  assert.equal(l.items.length, 3);
  assert.equal(l.ordered, false);
  const sub = l.items[1].children[0] as Extract<Block, { t: "list" }>;
  assert.equal(sub.t, "list");
  assert.equal(sub.items.length, 2);
  assert.equal((b[1] as Extract<Block, { t: "list" }>).ordered, true);
});
ok("markdown: una viñeta interrumpe un párrafo y los saltos simples se conservan", () => {
  const b = parseMarkdown("Intro\nsegunda línea\n- item");
  assert.deepEqual(b.map((x) => x.t), ["p", "list"]);
  assert.equal(plain((b[0] as Extract<Block, { t: "p" }>).inline), "Intro\nsegunda línea");
});
ok("markdown: tabla con alineación y celdas con formato", () => {
  const b = parseMarkdown("| Índice | Valor |\n|:--|--:|\n| **Cpk** | 1,33 |\n| Cp | 1,50 |\n\ntexto");
  const t = b[0] as Extract<Block, { t: "table" }>;
  assert.equal(t.t, "table");
  assert.deepEqual(t.align, ["left", "right"]);
  assert.equal(t.rows.length, 2);
  assert.equal(t.rows[0][0][0].t, "strong");
  assert.equal(b[1].t, "p");
});
ok("markdown: bloque de código (también sin cerrar, como llega en flujo), títulos y citas", () => {
  const b = parseMarkdown("## Título\n\n> cita\n\n```py\nx = 1\n```\n\n```\nsin cierre");
  assert.deepEqual(b.map((x) => x.t), ["heading", "quote", "code", "code"]);
  assert.equal((b[2] as Extract<Block, { t: "code" }>).text, "x = 1");
  assert.equal((b[3] as Extract<Block, { t: "code" }>).text, "sin cierre");
});
ok("markdown: SEGURIDAD: el HTML del modelo queda como texto y los enlaces peligrosos pierden el enlace", () => {
  const evil = '<img src=x onerror=alert(1)> <script>alert(1)</script> [clic](javascript:alert(1)) [ok](https://example.com/a?b=1) [d](data:text/html,x) [m](mailto:a@b.co)';
  const il = parseInline(evil);
  const links = il.filter((x): x is Extract<Inline, { t: "link" }> => x.t === "link").map((x) => x.href);
  assert.deepEqual(links, ["https://example.com/a?b=1", "mailto:a@b.co"]);
  assert.ok(plain(il).includes("<script>alert(1)</script>"), "la etiqueta se muestra literal");
  assert.ok(plain(il).includes("clic"));
  assert.equal(safeHref("JavaScript:alert(1)"), null);
  assert.equal(safeHref("//evil.com"), null);
  assert.equal(safeHref("https://a.b/c"), "https://a.b/c");
  // Ningún nodo del árbol lleva HTML: solo los tipos conocidos.
  const known = new Set(["text", "br", "strong", "em", "code", "link"]);
  const walk = (n: Inline[]) => n.forEach((x) => { assert.ok(known.has(x.t)); if ("children" in x) walk(x.children); });
  walk(il);
});
ok("markdown: robusto ante entradas raras (no lanza, termina)", () => {
  const r2 = rng(3);
  const alphabet = ["*", "_", "`", "[", "]", "(", ")", "|", "-", ">", "#", "\n", " ", "a", "1.", "```", "\\", "~"];
  for (let k = 0; k < 3000; k++) {
    let src = "";
    const n = Math.floor(r2() * 60);
    for (let j = 0; j < n; j++) src += alphabet[Math.floor(r2() * alphabet.length)];
    parseMarkdown(src);
  }
  parseMarkdown("*".repeat(20000));
  parseMarkdown("[".repeat(5000) + "](".repeat(5000));
  parseMarkdown("- a\n".repeat(3000));
});

console.log(`\n${passed} comprobaciones correctas`);

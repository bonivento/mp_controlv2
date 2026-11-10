// Módulo 6 en modo de ejemplo: ARL0, ARL1, ATS y curvas OC.
// Exacto para Shewhart con la regla 1; simulación acotada si hay reglas adicionales.

import { fmt, interp, type S } from "./common";
import { MockHttpError, binomPmf, cdfFrom, gauss, mean, normCdf, poissonPmf, rng, std } from "./engine";
import { ruleFires, type RuleId } from "./rules";

type Row = S["ArlRow"];
const pt = (x: number, y: number): S["CurvePoint"] => ({ x, y });
const arlOf = (beta: number) => (beta >= 1 ? 1e9 : 1 / (1 - beta));

/** Probabilidad de que un punto caiga DENTRO de los límites (no señal). */
function inControlProb(req: S["ArlRequest"], L: number): { at: (s: number) => number; alpha: number; grid: number[] } {
  const n = req.chart === "xbar" ? req.n : 1;
  if (req.chart === "xbar" || req.chart === "individuals") {
    const f = (d: number) => normCdf(L - d * Math.sqrt(n)) - normCdf(-L - d * Math.sqrt(n));
    return { at: f, alpha: 1 - f(0), grid: Array.from({ length: 41 }, (_, i) => i * 0.1) };
  }
  if (req.chart === "p") {
    const p0 = req.p0;
    if (p0 == null || !(p0 > 0 && p0 < 1)) throw new MockHttpError("El gráfico p necesita p0 entre 0 y 1.");
    const half = L * Math.sqrt((p0 * (1 - p0)) / req.n);
    const ucl = req.n * (p0 + half);
    const lcl = req.n * (p0 - half);
    const f = (p: number) => cdfFrom((k) => binomPmf(k, req.n, p), ucl) - (lcl > 0 ? cdfFrom((k) => binomPmf(k, req.n, p), lcl) : 0);
    const top = Math.min(0.99, p0 * 4);
    return { at: f, alpha: 1 - f(p0), grid: Array.from({ length: 31 }, (_, i) => p0 + ((top - p0) * i) / 30) };
  }
  const c0 = req.c0;
  if (c0 == null || !(c0 > 0)) throw new MockHttpError("El gráfico c necesita c0 positivo.");
  const half = L * Math.sqrt(c0);
  const ucl = c0 + half;
  const lcl = c0 - half;
  const f = (c: number) => cdfFrom((k) => poissonPmf(k, c), ucl) - (lcl > 0 ? cdfFrom((k) => poissonPmf(k, c), lcl) : 0);
  return { at: f, alpha: 1 - f(c0), grid: Array.from({ length: 31 }, (_, i) => c0 + ((c0 * 3) * i) / 30) };
}

function defaultShifts(req: S["ArlRequest"]): number[] {
  if (req.chart === "p") return req.p1 ?? [1.25, 1.5, 2, 3].map((k) => Math.min(0.99, (req.p0 ?? 0.05) * k));
  if (req.chart === "c") return req.c1 ?? [1.25, 1.5, 2, 3].map((k) => (req.c0 ?? 5) * k);
  return req.shifts;
}

/** Longitud de corrida simulada (xbar/individuales, desplazamiento en sigmas del estadístico). */
function simulateRun(rand: () => number, shiftSigma: number, rules: RuleId[], L: number, maxLen: number) {
  const z: number[] = [];
  for (let i = 0; i < maxLen; i++) {
    z.push(shiftSigma + gauss(rand));
    for (const r of rules) {
      const fires = r === "WE1" || r === "N1" ? Math.abs(z[i]) > L : ruleFires(r, z, i);
      if (fires) return i + 1;
    }
  }
  return maxLen;
}

export function mockArl(req: S["ArlRequest"]): S["ArlResponse"] {
  const L = req.limit_width ?? 3;
  const h = req.sampling_interval ?? 1;
  const n = req.chart === "xbar" || req.chart === "p" ? req.n : 1;
  if (!(L > 0) || !(h > 0) || !(n >= 1)) throw new MockHttpError("n, L y h deben ser positivos.");
  const enabled = (req.rules?.enabled ?? ["WE1"]) as RuleId[];
  const extra = enabled.some((r) => r !== "WE1" && r !== "N1");
  const { at, alpha, grid } = inControlProb(req, L);
  const shifts = defaultShifts(req);
  const sampling_load = n / h;

  if (extra && (req.chart === "xbar" || req.chart === "individuals")) {
    const runs = Math.min(req.max_runs ?? 5000, 400);
    const maxLen = Math.min(req.max_length ?? 20000, 4000);
    const sd = Math.sqrt(n);
    const sim = (delta: number, seed: number, count = runs) => {
      const rand = rng(seed);
      const lens = Array.from({ length: count }, () => simulateRun(rand, delta * sd, enabled, L, maxLen));
      return { arl: mean(lens), se: std(lens) / Math.sqrt(count) };
    };
    const base = sim(0, (req.seed ?? 12345) + 1);
    const rows: Row[] = shifts.map((d, i) => {
      const r = sim(d, (req.seed ?? 12345) + 10 + i);
      return { shift: d, beta: null, arl1: r.arl, ats1: r.arl * h, units_to_detect: r.arl * n, std_error: r.se };
    });
    const curveShifts = Array.from({ length: 13 }, (_, i) => i * 0.25);
    return {
      method: "simulation",
      alpha: null,
      arl0: base.arl,
      ats0: base.arl * h,
      sampling_load,
      rows,
      oc_curve: grid.map((d) => pt(d, at(d))),
      arl_curve: curveShifts.map((d, i) => pt(d, sim(d, (req.seed ?? 12345) + 100 + i, 120).arl)),
      interpretation: interp(
        `Con las reglas ${enabled.join(", ")} el ARL0 simulado es ${fmt(base.arl, 1)} muestras (≈ ${fmt(base.arl * h, 1)} horas entre falsas alarmas).`,
        [
          `Simulación con ${runs} corridas por punto y semilla ${req.seed ?? 12345}: el error estándar aparece en cada fila.`,
          "La curva OC mostrada es la exacta de Shewhart con la regla 1 sola, como referencia.",
        ],
        ["Cada regla adicional reduce el ARL0 (más falsas alarmas) y reduce el ARL1 (detecta antes)."],
      ),
    };
  }

  const rows: Row[] = shifts.map((s) => {
    const beta = at(s);
    const arl1 = arlOf(beta);
    return { shift: s, beta, arl1, ats1: arl1 * h, units_to_detect: arl1 * n };
  });
  const arl0 = 1 / alpha;
  const first = rows[0];
  return {
    method: "exact",
    alpha,
    arl0,
    ats0: arl0 * h,
    sampling_load,
    rows,
    oc_curve: grid.map((s) => pt(s, at(s))),
    arl_curve: grid.map((s) => pt(s, arlOf(at(s)))),
    interpretation: interp(
      `Con L = ${L} y n = ${n}, el gráfico da una falsa alarma cada ${fmt(arl0, 1)} muestras en promedio (ARL0), es decir cada ${fmt(arl0 * h, 1)} horas (ATS0).`,
      [
        `α = ${fmt(alpha, 5)} por muestra; carga muestral n/h = ${fmt(sampling_load, 2)} unidades por hora.`,
        first ? `Ante un desplazamiento de ${fmt(first.shift, 2)}, tarda ${fmt(first.arl1, 1)} muestras (${fmt(first.ats1, 1)} horas, ${fmt(first.units_to_detect, 0)} unidades) en detectarlo.` : "",
        ...(extra ? ["Se pidieron reglas adicionales, pero este gráfico solo las admite por simulación en xbar e individuales; se calculó con la regla 1."] : []),
      ].filter(Boolean),
    ),
  };
}

export function mockCompare(req: S["CompareRequest"]): S["CompareResponse"] {
  if (!req.n_values.length) throw new MockHttpError("Indica al menos un tamaño de muestra.");
  const rows: S["CompareRow"][] = [];
  for (const n of req.n_values)
    for (const L of req.limit_widths ?? [3])
      for (const h of req.sampling_intervals ?? [1]) {
        const f = (d: number) => normCdf(L - d * Math.sqrt(n)) - normCdf(-L - d * Math.sqrt(n));
        const arl0 = 1 / (1 - f(0));
        const arl1 = arlOf(f(req.shift));
        rows.push({ n, limit_width: L, sampling_interval: h, arl0, ats0: arl0 * h, arl1, ats1: arl1 * h, sampling_load: n / h });
      }
  const fastest = rows.reduce((a, b) => (b.ats1 < a.ats1 ? b : a));
  const cheapest = rows.reduce((a, b) => (b.sampling_load < a.sampling_load ? b : a));
  return {
    shift: req.shift,
    rows,
    interpretation: interp(
      `Se compararon ${rows.length} diseños para detectar un desplazamiento de ${fmt(req.shift, 2)} sigmas.`,
      [
        `El de menor ATS1 es n = ${fastest.n}, L = ${fastest.limit_width}, h = ${fastest.sampling_interval} (${fmt(fastest.ats1, 2)} horas), con carga de ${fmt(fastest.sampling_load, 2)} unidades por hora.`,
        `El de menor carga muestral es n = ${cheapest.n}, h = ${cheapest.sampling_interval} (${fmt(cheapest.sampling_load, 2)} u/h), con ATS1 de ${fmt(cheapest.ats1, 2)} horas.`,
      ],
      ["Un ATS1 menor casi siempre cuesta más inspección: pondera la carga muestral antes de decidir."],
    ),
  };
}

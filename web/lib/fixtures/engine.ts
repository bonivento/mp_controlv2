// MOTOR DE EJEMPLO. Solo se usa con NEXT_PUBLIC_API_MOCK=1 para que las pantallas
// respondan con números coherentes con los datos cargados mientras la API real
// no existe (responde 501). La aplicación NUNCA importa este archivo fuera de
// lib/fixtures/: en la Ola 2 se apaga el modo de ejemplo y todo viene de /api/*.
// Las fórmulas son las de Montgomery (Introduction to Statistical Quality
// Control), pero la validación estadística la hace la API, no este archivo.

export class MockHttpError extends Error {
  status: number;
  code: string;
  constructor(detail: string, status = 422, code = "invalid_input") {
    super(detail);
    this.status = status;
    this.code = code;
  }
}

export const sum = (a: number[]) => a.reduce((s, x) => s + x, 0);
export const mean = (a: number[]) => sum(a) / a.length;
export function std(a: number[]) {
  if (a.length < 2) return 0;
  const m = mean(a);
  return Math.sqrt(sum(a.map((x) => (x - m) ** 2)) / (a.length - 1));
}
export function quantile(sorted: number[], q: number) {
  const pos = (sorted.length - 1) * q;
  const lo = Math.floor(pos);
  const hi = Math.ceil(pos);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (pos - lo);
}
export function skewness(a: number[]) {
  const n = a.length;
  if (n < 3) return null;
  const m = mean(a);
  const m2 = sum(a.map((x) => (x - m) ** 2)) / n;
  const m3 = sum(a.map((x) => (x - m) ** 3)) / n;
  return m2 === 0 ? null : m3 / m2 ** 1.5;
}
export function excessKurtosis(a: number[]) {
  const n = a.length;
  if (n < 4) return null;
  const m = mean(a);
  const m2 = sum(a.map((x) => (x - m) ** 2)) / n;
  const m4 = sum(a.map((x) => (x - m) ** 4)) / n;
  return m2 === 0 ? null : m4 / m2 ** 2 - 3;
}

/** Φ(x), algoritmo de doble precisión de West (2005) basado en Hart (1968). */
export function normCdf(x: number) {
  const xa = Math.abs(x);
  let c: number;
  if (xa > 37) c = 0;
  else {
    const e = Math.exp((-xa * xa) / 2);
    if (xa < 7.07106781186547) {
      let b = 3.52624965998911e-2 * xa + 0.700383064443688;
      b = b * xa + 6.37396220353165;
      b = b * xa + 33.912866078383;
      b = b * xa + 112.079291497871;
      b = b * xa + 221.213596169931;
      b = b * xa + 220.206867912376;
      c = e * b;
      b = 8.83883476483184e-2 * xa + 1.75566716318264;
      b = b * xa + 16.064177579207;
      b = b * xa + 86.7807322029461;
      b = b * xa + 296.564248779674;
      b = b * xa + 637.333633378831;
      b = b * xa + 793.826512519948;
      b = b * xa + 440.413735824752;
      c = c / b;
    } else {
      let b = xa + 0.65;
      b = xa + 4 / b;
      b = xa + 3 / b;
      b = xa + 2 / b;
      b = xa + 1 / b;
      c = e / b / 2.506628274631;
    }
  }
  return x > 0 ? 1 - c : c;
}
export const normPdf = (x: number) => Math.exp(-0.5 * x * x) / Math.sqrt(2 * Math.PI);

/** Φ⁻¹(p): algoritmo de Acklam con un paso de refinamiento. */
export function normInv(p: number) {
  if (p <= 0) return -Infinity;
  if (p >= 1) return Infinity;
  const a = [-3.969683028665376e1, 2.209460984245205e2, -2.759285104469687e2, 1.38357751867269e2, -3.066479806614716e1, 2.506628277459239];
  const b = [-5.447609879822406e1, 1.615858368580409e2, -1.556989798598866e2, 6.680131188771972e1, -1.328068155288572e1];
  const c = [-7.784894002430293e-3, -3.223964580411365e-1, -2.400758277161838, -2.549732539343734, 4.374664141464968, 2.938163982698783];
  const d = [7.784695709041462e-3, 3.224671290700398e-1, 2.445134137142996, 3.754408661907416];
  let x: number;
  if (p < 0.02425) {
    const q = Math.sqrt(-2 * Math.log(p));
    x = (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1);
  } else if (p > 1 - 0.02425) {
    const q = Math.sqrt(-2 * Math.log(1 - p));
    x = -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1);
  } else {
    const q = p - 0.5;
    const r = q * q;
    x = ((((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q) / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1);
  }
  const e = normCdf(x) - p;
  const u = e * Math.sqrt(2 * Math.PI) * Math.exp((x * x) / 2);
  return x - u / (1 + (x * u) / 2);
}

export function lgamma(z: number): number {
  const g = 7;
  const coef = [0.99999999999980993, 676.5203681218851, -1259.1392167224028, 771.32342877765313, -176.61502916214059, 12.507343278686905, -0.13857109526572012, 9.9843695780195716e-6, 1.5056327351493116e-7];
  if (z < 0.5) return Math.log(Math.PI / Math.sin(Math.PI * z)) - lgamma(1 - z);
  z -= 1;
  let x = coef[0];
  for (let i = 1; i < g + 2; i++) x += coef[i] / (z + i);
  const t = z + g + 0.5;
  return 0.5 * Math.log(2 * Math.PI) + (z + 0.5) * Math.log(t) - t + Math.log(x);
}

/** Gamma incompleta regularizada P(a, x). */
export function gammaP(a: number, x: number): number {
  if (x <= 0) return 0;
  if (x < a + 1) {
    let ap = a;
    let del = 1 / a;
    let s = del;
    for (let n = 0; n < 500; n++) {
      ap += 1;
      del *= x / ap;
      s += del;
      if (Math.abs(del) < Math.abs(s) * 1e-14) break;
    }
    return s * Math.exp(-x + a * Math.log(x) - lgamma(a));
  }
  let b = x + 1 - a;
  let c = 1 / 1e-300;
  let d = 1 / b;
  let h = d;
  for (let i = 1; i < 500; i++) {
    const an = -i * (i - a);
    b += 2;
    d = an * d + b;
    if (Math.abs(d) < 1e-300) d = 1e-300;
    c = b + an / c;
    if (Math.abs(c) < 1e-300) c = 1e-300;
    d = 1 / d;
    const del = d * c;
    h *= del;
    if (Math.abs(del - 1) < 1e-14) break;
  }
  return 1 - Math.exp(-x + a * Math.log(x) - lgamma(a)) * h;
}
export const chi2Sf = (x: number, df: number) => 1 - gammaP(df / 2, x / 2);
export function chi2Inv(p: number, df: number) {
  let lo = 0;
  let hi = Math.max(10, df * 5 + 50);
  for (let i = 0; i < 200; i++) {
    const mid = (lo + hi) / 2;
    if (gammaP(df / 2, mid / 2) < p) lo = mid;
    else hi = mid;
  }
  return (lo + hi) / 2;
}

// --- Distribuciones discretas ------------------------------------------------
const lchoose = (n: number, k: number) => lgamma(n + 1) - lgamma(k + 1) - lgamma(n - k + 1);

export function binomPmf(k: number, n: number, p: number) {
  if (k < 0 || k > n) return 0;
  if (p <= 0) return k === 0 ? 1 : 0;
  if (p >= 1) return k === n ? 1 : 0;
  return Math.exp(lchoose(n, k) + k * Math.log(p) + (n - k) * Math.log(1 - p));
}
export function poissonPmf(k: number, lambda: number) {
  if (k < 0) return 0;
  if (lambda <= 0) return k === 0 ? 1 : 0;
  return Math.exp(k * Math.log(lambda) - lambda - lgamma(k + 1));
}
export function hyperPmf(k: number, bigN: number, bigK: number, n: number) {
  if (k < 0 || k > n || k > bigK || n - k > bigN - bigK) return 0;
  return Math.exp(lchoose(bigK, k) + lchoose(bigN - bigK, n - k) - lchoose(bigN, n));
}
export function cdfFrom(pmf: (k: number) => number, upTo: number) {
  let s = 0;
  for (let k = 0; k <= Math.floor(upTo); k++) s += pmf(k);
  return Math.min(1, s);
}

/** Generador pseudoaleatorio con semilla (mulberry32). */
export function rng(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
export function gauss(rand: () => number) {
  return Math.sqrt(-2 * Math.log(Math.max(rand(), 1e-300))) * Math.cos(2 * Math.PI * rand());
}

export const round = (x: number, d = 6) => {
  const f = 10 ** d;
  return Math.round(x * f) / f;
};
/** Nunca NaN ni infinito en una respuesta (regla 7 de CLAUDE.md). */
export const finite = (x: number): number => (Number.isFinite(x) ? x : 0);
export const delay = (ms = 350) => new Promise<void>((r) => setTimeout(r, ms));

export const CONSTANTS: Record<number, { d2: number; d3: number; c4: number }> = {
  2: { d2: 1.128, d3: 0.853, c4: 0.7979 },
  3: { d2: 1.693, d3: 0.888, c4: 0.8862 },
  4: { d2: 2.059, d3: 0.88, c4: 0.9213 },
  5: { d2: 2.326, d3: 0.864, c4: 0.94 },
  6: { d2: 2.534, d3: 0.848, c4: 0.9515 },
  7: { d2: 2.704, d3: 0.833, c4: 0.9594 },
  8: { d2: 2.847, d3: 0.82, c4: 0.965 },
  9: { d2: 2.97, d3: 0.808, c4: 0.9693 },
  10: { d2: 3.078, d3: 0.797, c4: 0.9727 },
};
export function constantsFor(n: number) {
  const c = CONSTANTS[n];
  if (!c) throw new MockHttpError("En modo de ejemplo solo hay constantes para subgrupos de 2 a 10 observaciones.");
  return c;
}

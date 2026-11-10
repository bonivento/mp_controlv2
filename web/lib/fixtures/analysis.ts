// Módulos 4 y 5 en modo de ejemplo: supuestos y capacidad.

import { describe } from "./data";
import { fmt, interp, type S } from "./common";
import { MockHttpError, chi2Inv, chi2Sf, constantsFor, mean, normCdf, normInv, normPdf, std, sum } from "./engine";

function histogramOf(values: number[], bins?: number | null, curveStd?: number, curveMean?: number): S["Histogram"] {
  const n = values.length;
  const k = Math.max(2, bins ?? Math.ceil(Math.log2(n) + 1));
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const w = (hi - lo || 1) / k;
  const edges = Array.from({ length: k + 1 }, (_, i) => lo + i * w);
  const counts = Array<number>(k).fill(0);
  for (const v of values) counts[Math.min(k - 1, Math.floor((v - lo) / w))]++;
  const m = curveMean ?? mean(values);
  const s = curveStd ?? std(values);
  const steps = 60;
  const x0 = lo - w;
  const x1 = hi + w;
  const normal_curve_x = Array.from({ length: steps + 1 }, (_, i) => x0 + ((x1 - x0) * i) / steps);
  const normal_curve_y = normal_curve_x.map((x) => (s > 0 ? (n * w * normPdf((x - m) / s)) / s : 0));
  return { edges, counts, normal_curve_x, normal_curve_y };
}

export function mockAssumptions(req: S["AssumptionsRequest"]): S["AssumptionsResponse"] {
  const x = req.values;
  const n = x.length;
  if (n < 8) throw new MockHttpError("Se necesitan al menos 8 observaciones para validar supuestos.");
  const alpha = req.alpha ?? 0.05;
  const m = mean(x);
  const s = std(x);
  if (s === 0) throw new MockHttpError("Todas las observaciones son iguales: no hay variación que analizar.");
  const sorted = [...x].sort((a, b) => a - b);

  // Prueba tipo Shapiro-Wilk: aproximación de Shapiro-Francia con p de Royston (1993).
  const scores = sorted.map((_, i) => normInv((i + 1 - 0.375) / (n + 0.25)));
  const ms = mean(scores);
  const num = sum(sorted.map((v, i) => (v - m) * (scores[i] - ms))) ** 2;
  const den = sum(sorted.map((v) => (v - m) ** 2)) * sum(scores.map((q) => (q - ms) ** 2));
  const w = num / den;
  const u = Math.log(n);
  const v = Math.log(u);
  const pSW = 1 - normCdf((Math.log(1 - w) - (-1.2725 + 1.0521 * (v - u))) / (1.0308 - 0.26758 * (v + 2 / u)));

  // Anderson-Darling con corrección de muestra pequeña (D'Agostino y Stephens, 1986).
  const F = sorted.map((y) => Math.min(1 - 1e-12, Math.max(1e-12, normCdf((y - m) / s))));
  const a2 = -n - sum(F.map((f, i) => ((2 * (i + 1) - 1) / n) * (Math.log(f) + Math.log(1 - F[n - 1 - i]))));
  const a = a2 * (1 + 0.75 / n + 2.25 / (n * n));
  const pAD =
    a >= 0.6
      ? Math.exp(1.2937 - 5.709 * a + 0.0186 * a * a)
      : a >= 0.34
        ? Math.exp(0.9177 - 4.279 * a - 1.38 * a * a)
        : a >= 0.2
          ? 1 - Math.exp(-8.318 + 42.796 * a - 59.938 * a * a)
          : 1 - Math.exp(-13.436 + 101.14 * a - 223.73 * a * a);
  const crit: Record<string, number> = { "0.1": 0.631, "0.05": 0.752, "0.025": 0.873, "0.01": 1.035 };

  const verdict = (name: string, p: number, what: string) =>
    p < alpha
      ? `Se rechaza H0 (p = ${fmt(p, 4)} < ${alpha}): hay evidencia de que ${what} no se cumple.`
      : `No se rechaza H0 (p = ${fmt(p, 4)} ≥ ${alpha}): no hay evidencia contra ${what}. (${name})`;

  const normality: S["TestResult"][] = [
    {
      name: "Shapiro-Wilk (aprox. de ejemplo)",
      null_hypothesis: "Los datos provienen de una distribución normal",
      statistic: w,
      p_value: Math.max(0, Math.min(1, pSW)),
      critical_value: null,
      reject: pSW < alpha,
      conclusion: verdict("normalidad", pSW, "la normalidad"),
    },
    {
      name: "Anderson-Darling",
      null_hypothesis: "Los datos provienen de una distribución normal",
      statistic: a,
      p_value: Math.max(0, Math.min(1, pAD)),
      critical_value: crit[String(alpha)] ?? null,
      reject: pAD < alpha,
      conclusion: verdict("normalidad", pAD, "la normalidad"),
    },
  ];

  // Autocorrelación.
  const maxLag = Math.max(1, Math.min(req.max_lag ?? Math.min(20, Math.floor(n / 4)), n - 2));
  const c0 = sum(x.map((v) => (v - m) ** 2));
  const acf = Array.from({ length: maxLag }, (_, i) => {
    const k = i + 1;
    let c = 0;
    for (let t = 0; t + k < n; t++) c += (x[t] - m) * (x[t + k] - m);
    return c / c0;
  });
  const band = normInv(1 - alpha / 2) / Math.sqrt(n);
  const lags = acf.map((_, i) => i + 1);
  const significant = lags.filter((_, i) => Math.abs(acf[i]) > band);

  const lbLag = Math.max(1, Math.min(10, maxLag));
  const q = n * (n + 2) * sum(acf.slice(0, lbLag).map((r, i) => (r * r) / (n - (i + 1))));
  const pLB = chi2Sf(q, lbLag);

  const med = [...x].sort((p, r) => p - r)[Math.floor(n / 2)];
  const signs = x.filter((v) => v !== med).map((v) => v > med);
  const n1 = signs.filter(Boolean).length;
  const n2 = signs.length - n1;
  let runs = signs.length ? 1 : 0;
  for (let i = 1; i < signs.length; i++) if (signs[i] !== signs[i - 1]) runs++;
  const nn = n1 + n2;
  const mu = nn > 0 ? (2 * n1 * n2) / nn + 1 : 0;
  const vr = nn > 1 ? (2 * n1 * n2 * (2 * n1 * n2 - nn)) / (nn * nn * (nn - 1)) : 0;
  const zr = vr > 0 ? (runs - mu) / Math.sqrt(vr) : 0;
  const pRuns = 2 * (1 - normCdf(Math.abs(zr)));

  const independence: S["TestResult"][] = [
    {
      name: `Ljung-Box (${lbLag} rezagos)`,
      null_hypothesis: "No hay autocorrelación en los primeros rezagos",
      statistic: q,
      p_value: pLB,
      critical_value: null,
      reject: pLB < alpha,
      conclusion: verdict("independencia", pLB, "la independencia"),
    },
    {
      name: "Prueba de rachas (mediana)",
      null_hypothesis: "La secuencia de valores por encima y por debajo de la mediana es aleatoria",
      statistic: zr,
      p_value: pRuns,
      critical_value: null,
      reject: pRuns < alpha,
      conclusion: verdict("aleatoriedad", pRuns, "la aleatoriedad"),
    },
  ];
  const isNormal = !normality.some((t) => t.reject);
  const isIndependent = !independence.some((t) => t.reject);

  const warnings: string[] = [];
  if (!isNormal) warnings.push("Hay evidencia de no normalidad: los límites y los índices de capacidad basados en la normal pueden engañar.");
  if (!isIndependent) warnings.push("Hay evidencia de autocorrelación: los límites de control serán más estrechos de lo debido y habrá falsas alarmas.");
  if (n < 30) warnings.push("Con menos de 30 observaciones las pruebas tienen poca potencia.");

  return {
    descriptive: describe(x),
    normality,
    is_normal: isNormal,
    qq: sorted.map((obs, i) => ({ theoretical: normInv((i + 0.5) / n), observed: obs })),
    histogram: histogramOf(x, req.histogram_bins),
    autocorrelation: { lags, values: acf, band, significant_lags: significant },
    independence,
    is_independent: isIndependent,
    interpretation: interp(
      isNormal && isIndependent
        ? "Los datos son compatibles con normalidad e independencia: los supuestos de las cartas de Shewhart y de los índices de capacidad se sostienen."
        : `Se incumple ${!isNormal ? "la normalidad" : ""}${!isNormal && !isIndependent ? " y " : ""}${!isIndependent ? "la independencia" : ""}: interpreta con cautela las cartas y la capacidad.`,
      [
        ...normality.map((t) => `${t.name}: estadístico ${fmt(t.statistic, 4)}, p = ${fmt(t.p_value, 4)}.`),
        ...independence.map((t) => `${t.name}: estadístico ${fmt(t.statistic, 3)}, p = ${fmt(t.p_value, 4)}.`),
        significant.length ? `Autocorrelación significativa en los rezagos ${significant.join(", ")}.` : "Ningún rezago de la autocorrelación sale de la banda.",
      ],
      warnings,
    ),
  };
}

// ----------------------------------------------------------------------------
type Idx = S["IndexValue"];
const none: Idx = { value: null, lower: null, upper: null };

export function mockCapability(req: S["CapabilityRequest"]): S["CapabilityResponse"] {
  const { lsl, usl, target } = req;
  if (lsl == null && usl == null) throw new MockHttpError("Se necesita al menos una especificación (LSL o USL).");
  if (lsl != null && usl != null && lsl >= usl) throw new MockHttpError("El LSL debe ser menor que el USL.");
  const sub = req.subgroups.filter((s) => s.length > 0);
  const all = sub.flat();
  const n = all.length;
  if (n < 10) throw new MockHttpError("Se necesitan al menos 10 observaciones para estimar la capacidad.");
  const mu = mean(all);
  const sigmaO = std(all);
  if (sigmaO === 0) throw new MockHttpError("Todas las observaciones son iguales.");

  const individual = sub.every((s) => s.length === 1);
  let method = req.sigma_method ?? (individual ? "mrbar_d2" : "rbar_d2");
  if (individual) method = "mrbar_d2";
  let sigmaW: number;
  let usedMethod: S["CapabilityResponse"]["sigma_method"] = method;
  if (req.limits && req.limits.params.sigma > 0) {
    sigmaW = req.limits.params.sigma;
    usedMethod = "frozen_limits";
  } else if (method === "mrbar_d2") {
    const seq = individual ? all : sub.map(mean);
    const mrs = seq.slice(1).map((v, i) => Math.abs(v - seq[i]));
    sigmaW = mean(mrs) / 1.128;
  } else if (method === "sbar_c4") {
    sigmaW = mean(sub.map((s) => std(s) / constantsFor(s.length).c4));
  } else {
    sigmaW = mean(sub.map((s) => (Math.max(...s) - Math.min(...s)) / constantsFor(s.length).d2));
  }
  if (!(sigmaW > 0)) throw new MockHttpError("No se pudo estimar sigma dentro de los subgrupos.");

  const conf = req.confidence ?? 0.95;
  const z = normInv(1 - (1 - conf) / 2);
  const ciK = (v: number): Idx => {
    const se = Math.sqrt(1 / (9 * n) + (v * v) / (2 * (n - 1)));
    return { value: v, lower: v - z * se, upper: v + z * se };
  };
  const ciCp = (v: number): Idx => ({
    value: v,
    lower: v * Math.sqrt(chi2Inv((1 - conf) / 2, n - 1) / (n - 1)),
    upper: v * Math.sqrt(chi2Inv(1 - (1 - conf) / 2, n - 1) / (n - 1)),
  });
  const set = (sigma: number) => {
    const cp = lsl != null && usl != null ? (usl - lsl) / (6 * sigma) : null;
    const cpl = lsl != null ? (mu - lsl) / (3 * sigma) : null;
    const cpu = usl != null ? (usl - mu) / (3 * sigma) : null;
    const cpk = Math.min(...[cpl, cpu].filter((v): v is number => v != null));
    return {
      cp: cp == null ? none : ciCp(cp),
      cpl: cpl == null ? none : ciK(cpl),
      cpu: cpu == null ? none : ciK(cpu),
      cpk: ciK(cpk),
    };
  };
  const within = set(sigmaW);
  const overall = set(sigmaO);
  const cpm: Idx =
    target != null && lsl != null && usl != null
      ? { value: (usl - lsl) / (6 * Math.sqrt(sigmaO ** 2 + (mu - target) ** 2)), lower: null, upper: null }
      : none;

  const nc = (below: number | null, above: number | null): S["NonConforming"] => {
    const total = (below ?? 0) + (above ?? 0);
    return { below_lsl: below, above_usl: above, total, ppm: total * 1e6 };
  };
  const expected = (s: number) =>
    nc(lsl != null ? normCdf((lsl - mu) / s) : null, usl != null ? 1 - normCdf((usl - mu) / s) : null);
  const observed = nc(
    lsl != null ? all.filter((v) => v < lsl).length / n : null,
    usl != null ? all.filter((v) => v > usl).length / n : null,
  );

  const cpk = within.cpk.value ?? 0;
  const verdict: S["CapabilityResponse"]["verdict"] = cpk < 1 ? "inadequate" : cpk < 1.33 ? "marginal" : cpk < 1.67 ? "adequate" : "excellent";
  const verdictText = { inadequate: "inadecuada", marginal: "marginal", adequate: "adecuada", excellent: "excelente" }[verdict];

  const warnings: string[] = [];
  if (req.is_stable === false) warnings.push("El proceso no es estable (Fase I): los índices describen un proceso que cambia y no predicen su desempeño futuro.");
  if (req.is_stable == null) warnings.push("No se verificó la estabilidad del proceso; confirma la Fase I antes de usar estos índices.");
  if (req.is_normal === false) warnings.push("Los datos no son normales: la fracción no conforme esperada (modelo normal) puede estar sesgada; compárala con la observada.");
  if (req.is_normal == null) warnings.push("No se verificó la normalidad (módulo 4).");
  if (target == null) warnings.push("Sin objetivo (target) no se calcula Cpm.");
  if (n < 50) warnings.push(`Con ${n} observaciones los intervalos de confianza son anchos.`);

  const findings = [
    `Media ${fmt(mu)}; sigma dentro ${fmt(sigmaW, 4)}; sigma global ${fmt(sigmaO, 4)}.`,
    `Cpk = ${fmt(within.cpk.value, 2)} (IC ${fmt(within.cpk.lower, 2)} a ${fmt(within.cpk.upper, 2)}); Ppk = ${fmt(overall.cpk.value, 2)}.`,
    `Fracción no conforme: esperada ${fmt(expected(sigmaW).total * 1e6, 0)} PPM (sigma dentro), observada ${fmt(observed.ppm, 0)} PPM.`,
  ];
  if (within.cp.value != null && cpk < within.cp.value * 0.9)
    findings.push("Cpk es notablemente menor que Cp: el proceso está descentrado respecto a las especificaciones.");

  return {
    n,
    mean: mu,
    sigma_within: sigmaW,
    sigma_overall: sigmaO,
    sigma_method: usedMethod,
    cp: within.cp,
    cpl: within.cpl,
    cpu: within.cpu,
    cpk: within.cpk,
    pp: overall.cp,
    ppl: overall.cpl,
    ppu: overall.cpu,
    ppk: overall.cpk,
    cpm,
    expected_within: expected(sigmaW),
    expected_overall: expected(sigmaO),
    observed,
    histogram: histogramOf(all, null, sigmaO, mu),
    verdict,
    interpretation: interp(`Capacidad ${verdictText} (Cpk = ${fmt(cpk, 2)}).`, findings, warnings),
  };
}

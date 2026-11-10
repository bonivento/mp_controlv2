// Módulo 7 en modo de ejemplo: planes de muestreo de aceptación.

import { fmt, interp, type S } from "./common";
import { MockHttpError, binomPmf, cdfFrom, hyperPmf, poissonPmf } from "./engine";

type Dist = "binomial" | "poisson" | "hypergeometric";
const pt = (x: number, y: number): S["CurvePoint"] => ({ x, y });

function pa(dist: Dist, n: number, c: number, p: number, lot?: number | null): number {
  if (dist === "poisson") return cdfFrom((k) => poissonPmf(k, n * p), c);
  if (dist === "hypergeometric") {
    if (!lot) throw new MockHttpError("La distribución hipergeométrica necesita el tamaño del lote.");
    const bad = Math.round(lot * p);
    return cdfFrom((k) => hyperPmf(k, lot, bad, n), c);
  }
  return cdfFrom((k) => binomPmf(k, n, p), c);
}

function singleResponse(
  dist: Dist,
  n: number,
  c: number,
  lot: number | null | undefined,
  aql: number | null | undefined,
  ltpd: number | null | undefined,
): S["SinglePlanResponse"] {
  const pmax = Math.min(1, Math.max(ltpd ? ltpd * 2.5 : 0, aql ? aql * 8 : 0, (c + 1) / n * 2.2, 0.05));
  const grid = Array.from({ length: 61 }, (_, i) => (pmax * i) / 60);
  const oc = grid.map((p) => pt(p, pa(dist, n, c, p, lot)));
  const aoq = oc.map((o) => pt(o.x, lot ? (o.x * o.y * (lot - n)) / lot : o.x * o.y));
  const best = aoq.reduce((a, b) => (b.y > a.y ? b : a));
  const alphaA = aql != null ? 1 - pa(dist, n, c, aql, lot) : null;
  const betaA = ltpd != null ? pa(dist, n, c, ltpd, lot) : null;
  const findings = [
    `Se inspeccionan n = ${n} unidades del lote y se acepta si hay ${c} o menos defectuosas.`,
    alphaA != null ? `Riesgo del productor real: α = ${fmt(alphaA, 4)} (probabilidad de rechazar un lote con calidad AQL = ${fmt(aql, 4)}).` : "",
    betaA != null ? `Riesgo del consumidor real: β = ${fmt(betaA, 4)} (probabilidad de aceptar un lote con calidad LTPD = ${fmt(ltpd, 4)}).` : "",
    `Peor calidad promedio de salida (AOQL) = ${fmt(best.y, 4)}, cuando los lotes entran con ${fmt(best.x, 4)} de defectuosos.`,
  ].filter(Boolean);
  return {
    n,
    c,
    distribution: dist,
    alpha_actual: alphaA,
    beta_actual: betaA,
    oc_curve: oc,
    aoq_curve: aoq,
    aoql: best.y,
    aoql_at: best.x,
    ati_curve: lot ? oc.map((o) => pt(o.x, n + (1 - o.y) * (lot - n))) : null,
    interpretation: interp(`Plan simple n = ${n}, c = ${c}.`, findings, lot ? [] : ["Sin tamaño de lote no se calcula la inspección total promedio (ATI)."]),
  };
}

export function mockSingleDesign(req: S["SingleDesignRequest"]): S["SinglePlanResponse"] {
  const { aql, ltpd } = req;
  const alpha = req.alpha ?? 0.05;
  const beta = req.beta ?? 0.1;
  const dist = req.distribution ?? "binomial";
  if (!(aql > 0 && ltpd > aql && ltpd < 1)) throw new MockHttpError("Debe cumplirse 0 < AQL < LTPD < 1.");
  if (dist === "hypergeometric" && !req.lot_size) throw new MockHttpError("La distribución hipergeométrica necesita el tamaño del lote.");
  const maxN = req.lot_size ?? 20000;
  for (let c = 0; c <= 200; c++) {
    let lo = c + 1;
    let hi = maxN;
    if (pa(dist, hi, c, ltpd, req.lot_size) > beta) continue;
    while (lo < hi) {
      const mid = Math.floor((lo + hi) / 2);
      if (pa(dist, mid, c, ltpd, req.lot_size) <= beta) hi = mid;
      else lo = mid + 1;
    }
    if (pa(dist, lo, c, aql, req.lot_size) >= 1 - alpha) return singleResponse(dist, lo, c, req.lot_size, aql, ltpd);
  }
  throw new MockHttpError("No se encontró un plan que cumpla los cuatro puntos (AQL, α, LTPD, β). Relaja los riesgos o separa más AQL y LTPD.");
}

export function mockSingleEvaluate(req: S["SingleEvaluateRequest"]): S["SinglePlanResponse"] {
  if (!(req.n >= 1) || !(req.c >= 0) || req.c >= req.n) throw new MockHttpError("Debe cumplirse 0 ≤ c < n.");
  if (req.lot_size && req.n > req.lot_size) throw new MockHttpError("La muestra no puede superar el tamaño del lote.");
  return singleResponse(req.distribution ?? "binomial", req.n, req.c, req.lot_size, req.aql, req.ltpd);
}

export function mockDoubleEvaluate(req: S["DoubleEvaluateRequest"]): S["DoublePlanResponse"] {
  const { n1, c1, r1, n2, c2 } = req;
  if (![n1, n2].every((v) => v >= 1) || c1 < 0 || c2 < c1) throw new MockHttpError("Debe cumplirse n1, n2 ≥ 1 y 0 ≤ c1 ≤ c2.");
  if (r1 <= c1 + 1 && r1 !== c2 + 1) throw new MockHttpError("r1 debe ser mayor que c1 + 1 o igual a c2 + 1.");
  const lot = req.lot_size;
  const stats = (p: number) => {
    const first = cdfFrom((k) => binomPmf(k, n1, p), c1);
    let second = 0;
    let goOn = 0;
    for (let d1 = c1 + 1; d1 < r1; d1++) {
      const pd = binomPmf(d1, n1, p);
      goOn += pd;
      second += pd * cdfFrom((k) => binomPmf(k, n2, p), c2 - d1);
    }
    return { first, pa: first + second, asn: n1 + n2 * goOn };
  };
  const pmax = Math.min(1, Math.max(req.ltpd ? req.ltpd * 2.5 : 0, req.aql ? req.aql * 8 : 0, ((c2 + 1) / (n1 + n2)) * 2.5, 0.05));
  const grid = Array.from({ length: 61 }, (_, i) => (pmax * i) / 60);
  const all = grid.map((p) => ({ p, ...stats(p) }));
  const aoq = all.map((a) => pt(a.p, lot ? (a.p * a.pa * (lot - a.asn)) / lot : a.p * a.pa));
  const best = aoq.reduce((a, b) => (b.y > a.y ? b : a));
  const alphaA = req.aql != null ? 1 - stats(req.aql).pa : null;
  const betaA = req.ltpd != null ? stats(req.ltpd).pa : null;
  return {
    oc_curve: all.map((a) => pt(a.p, a.pa)),
    asn_curve: all.map((a) => pt(a.p, a.asn)),
    first_sample_accept_curve: all.map((a) => pt(a.p, a.first)),
    alpha_actual: alphaA,
    beta_actual: betaA,
    aoq_curve: aoq,
    aoql: best.y,
    ati_curve: lot ? all.map((a) => pt(a.p, a.asn + (1 - a.pa) * (lot - a.asn))) : null,
    interpretation: interp(
      `Plan doble: primera muestra n1 = ${n1} (aceptar si ≤ ${c1}, rechazar si ≥ ${r1}); segunda n2 = ${n2} (aceptar si el total ≤ ${c2}).`,
      [
        alphaA != null ? `α real = ${fmt(alphaA, 4)}.` : "",
        betaA != null ? `β real = ${fmt(betaA, 4)}.` : "",
        `AOQL ≈ ${fmt(best.y, 4)}.`,
        `El tamaño de muestra promedio (ASN) máximo es ${fmt(Math.max(...all.map((a) => a.asn)), 1)} unidades.`,
      ].filter(Boolean),
      lot ? [] : ["Sin tamaño de lote no se calcula ATI."],
    ),
  };
}

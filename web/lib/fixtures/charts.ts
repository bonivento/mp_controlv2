// Módulos 2 y 3 en modo de ejemplo: gráficos de control de variables y atributos.
// Fase I estima parámetros sin los puntos excluidos; Fase II usa los congelados.

import { fmt, interp, type S } from "./common";
import { MockHttpError, constantsFor, mean, std, sum } from "./engine";
import { ONLY_BEYOND_LIMITS, RULE_TEXT, ruleFires, type RuleId } from "./rules";

type Series = S["ChartSeries"];
const DEFAULT_RULES: RuleId[] = ["WE1"];
const POSITION_RULES: RuleId[] = ["WE4", "N2", "N3", "N4"];

function checkExcluded(excluded: S["ExcludedPoint"][], count: number) {
  for (const e of excluded) {
    if (!e.cause || e.cause.trim().length < 3)
      throw new MockHttpError("Cada punto excluido necesita su causa asignable (obligatoria).");
    if (e.index < 0 || e.index >= count) throw new MockHttpError(`El punto excluido ${e.index} no existe.`);
  }
}

/** Señales de un panel. `fullRules`: paneles de localización con límites simétricos. */
function violationsFor(
  panel: Pick<Series, "labels" | "values" | "center" | "ucl" | "lcl">,
  enabled: RuleId[],
  limitWidth: number,
  fullRules: boolean,
  indexMap: (i: number) => number = (i) => i,
): S["RuleViolation"][] {
  const out: S["RuleViolation"][] = [];
  const z = panel.values.map((v, i) => {
    const sigma = (panel.ucl[i] - panel.center[i]) / limitWidth;
    return sigma > 0 ? (v - panel.center[i]) / sigma : 0;
  });
  panel.values.forEach((v, i) => {
    for (const rule of enabled) {
      const isLimitRule = ONLY_BEYOND_LIMITS.includes(rule);
      if (!fullRules && !isLimitRule && !POSITION_RULES.includes(rule)) continue;
      const fires = isLimitRule ? v > panel.ucl[i] || v < panel.lcl[i] : ruleFires(rule, z, i);
      if (fires)
        out.push({
          rule,
          index: indexMap(i),
          description: `${RULE_TEXT[rule]} (subgrupo ${panel.labels[i]})`,
        });
    }
  });
  return out;
}

/** Reglas que se evalúan en un panel y las que se omiten (con el motivo), como la API real. */
function splitRules(enabled: RuleId[], fullRules: boolean): Pick<Series, "rules_applied" | "rules_skipped"> {
  const ok = (r: RuleId) => fullRules || ONLY_BEYOND_LIMITS.includes(r) || POSITION_RULES.includes(r);
  return {
    rules_applied: enabled.filter(ok),
    rules_skipped: enabled
      .filter((r) => !ok(r))
      .map((rule) => ({
        rule,
        reason: "Las reglas de zonas suponen límites simétricos y la distribución de este estadístico no lo es.",
      })),
  };
}

function buildResponse(args: {
  chartType: string;
  phase: "I" | "II";
  charts: Series[];
  limits: S["FrozenLimits"];
  excluded: S["ExcludedPoint"][];
  labels: string[];
  firstPanelIsMain: boolean;
}): S["ChartResponse"] {
  const excludedSet = new Set(args.excluded.map((e) => e.index));
  const signals = new Set<number>();
  for (const c of args.charts) for (const v of c.violations) if (!excludedSet.has(v.index)) signals.add(v.index);
  const oocPoints = [...signals].sort((a, b) => a - b);
  const inControl = oocPoints.length === 0;
  const n = args.labels.length;
  const label = (i: number) => args.labels[i] ?? String(i + 1);
  const findings: string[] = [];
  for (const i of oocPoints) {
    const rules = new Set<string>();
    args.charts.forEach((c) => c.violations.filter((v) => v.index === i).forEach((v) => rules.add(v.rule)));
    findings.push(`Subgrupo ${label(i)}: señal de ${[...rules].join(", ")}.`);
  }
  if (args.excluded.length)
    findings.push(
      `Puntos excluidos del cálculo de límites: ${args.excluded
        .map((e) => `${e.label ?? label(e.index)} (${e.cause})`)
        .join("; ")}.`,
    );
  let summary: string;
  const warnings: string[] = [];
  if (args.phase === "I") {
    summary = inControl
      ? `Fase I: con ${args.limits.points_used} de ${n} subgrupos el proceso no muestra señales; los límites son razonables para congelarlos.`
      : `Fase I: ${oocPoints.length} subgrupo(s) con señal. Investiga la causa asignable de cada uno, exclúyelo si la encuentras y revisa de nuevo antes de congelar.`;
    if (!inControl) warnings.push("Con señales sin explicar, los límites de prueba todavía no son confiables.");
    if (args.limits.points_used < 20)
      warnings.push(`Solo ${args.limits.points_used} subgrupos en el cálculo: se recomiendan 20 a 25 como mínimo.`);
  } else {
    summary = inControl
      ? `Fase II: ${n} subgrupos monitoreados contra los límites congelados; el proceso se mantiene bajo control.`
      : `Fase II: ${oocPoints.length} de ${n} subgrupos señalan un cambio respecto a los límites congelados.`;
    findings.unshift("Los límites no se recalcularon: son los congelados en la Fase I.");
  }
  return {
    chart_type: args.chartType,
    phase: args.phase,
    charts: args.charts,
    limits: args.limits,
    in_control: inControl,
    out_of_control_points: oocPoints,
    interpretation: interp(summary, findings, warnings),
  };
}

// ----------------------------------------------------------------------------
export function mockVariablesChart(req: S["VariablesChartRequest"]): S["ChartResponse"] {
  const sub = req.subgroups;
  if (sub.length < 2) throw new MockHttpError("Se necesitan al menos 2 subgrupos para un gráfico de control.");
  const labels = req.labels ?? sub.map((_, i) => String(i + 1));
  const L = req.limit_width ?? 3;
  const enabled = (req.rules?.enabled ?? DEFAULT_RULES) as RuleId[];
  const isI = req.chart_type === "i_mr";
  const sizes = new Set(sub.map((s) => s.length));
  if (isI && (sizes.size !== 1 || !sizes.has(1))) throw new MockHttpError("El gráfico I-MR necesita observaciones individuales (subgrupos de tamaño 1).");
  if (!isI && (sizes.size !== 1 || sizes.has(1))) throw new MockHttpError("X-barra necesita subgrupos de tamaño constante y mayor que 1.");
  const n = isI ? 1 : sub[0].length;
  const phase = req.phase;
  const excluded = phase === "I" ? req.excluded ?? [] : [];
  checkExcluded(excluded, sub.length);
  const exSet = new Set(excluded.map((e) => e.index));
  const used = sub.map((_, i) => i).filter((i) => !exSet.has(i));
  if (phase === "II" && !req.limits) throw new MockHttpError("La Fase II necesita los límites congelados de la Fase I.");
  if (used.length < 2) throw new MockHttpError("Quedan menos de 2 subgrupos en el cálculo.");

  const means = sub.map(mean);
  const method: S["FrozenLimits"]["sigma_method"] =
    req.chart_type === "xbar_r" ? "rbar_d2" : req.chart_type === "xbar_s" ? "sbar_c4" : "mrbar_d2";

  // Parámetros del proceso: estimados (Fase I) o congelados (Fase II).
  let mu: number;
  let sigma: number;
  if (phase === "II") {
    mu = req.limits!.params.mu;
    sigma = req.limits!.params.sigma;
    if (!(sigma > 0)) throw new MockHttpError("Los límites congelados no traen sigma válido.");
  } else {
    mu = mean(used.map((i) => means[i]));
    if (req.chart_type === "xbar_r") {
      const rbar = mean(used.map((i) => Math.max(...sub[i]) - Math.min(...sub[i])));
      sigma = rbar / constantsFor(n).d2;
    } else if (req.chart_type === "xbar_s") {
      sigma = mean(used.map((i) => std(sub[i]))) / constantsFor(n).c4;
    } else {
      const mrs: number[] = [];
      for (let i = 1; i < sub.length; i++) if (!exSet.has(i) && !exSet.has(i - 1)) mrs.push(Math.abs(sub[i][0] - sub[i - 1][0]));
      if (!mrs.length) throw new MockHttpError("No quedan rangos móviles para estimar sigma.");
      sigma = mean(mrs) / 1.128;
    }
  }
  const k = sub.length;
  const rep = (x: number) => Array<number>(k).fill(x);
  const { d2, d3, c4 } = isI ? { d2: 1.128, d3: 0.853, c4: 1 } : constantsFor(n);
  const half = (L * sigma) / Math.sqrt(n);

  const main: Series = {
    name: isI ? "i" : "xbar",
    title: isI ? "Gráfico de individuales (I)" : "Gráfico X-barra",
    labels,
    values: means,
    center: rep(mu),
    ucl: rep(mu + half),
    lcl: rep(mu - half),
    violations: [],
    excluded: [...exSet].sort((a, b) => a - b),
    indices: labels.map((_, i) => i),
    rules_applied: enabled,
    rules_skipped: [],
  };
  main.violations = violationsFor(main, enabled, L, true);

  let second: Series;
  if (req.chart_type === "xbar_r") {
    const r = sub.map((s) => Math.max(...s) - Math.min(...s));
    second = {
      name: "r",
      title: "Gráfico R (rango)",
      labels,
      values: r,
      center: rep(d2 * sigma),
      ucl: rep(d2 * sigma + L * d3 * sigma),
      lcl: rep(Math.max(0, d2 * sigma - L * d3 * sigma)),
      violations: [],
      excluded: main.excluded,
      indices: main.indices,
      rules_applied: enabled,
      rules_skipped: [],
    };
  } else if (req.chart_type === "xbar_s") {
    const s = sub.map(std);
    const w = L * sigma * Math.sqrt(1 - c4 * c4);
    second = {
      name: "s",
      title: "Gráfico S (desviación estándar)",
      labels,
      values: s,
      center: rep(c4 * sigma),
      ucl: rep(c4 * sigma + w),
      lcl: rep(Math.max(0, c4 * sigma - w)),
      violations: [],
      excluded: main.excluded,
      indices: main.indices,
      rules_applied: enabled,
      rules_skipped: [],
    };
  } else {
    const mr = sub.slice(1).map((s, i) => Math.abs(s[0] - sub[i][0]));
    const m = mr.length;
    second = {
      name: "mr",
      title: "Gráfico de rangos móviles (MR)",
      labels: labels.slice(1),
      values: mr,
      center: Array<number>(m).fill(d2 * sigma),
      ucl: Array<number>(m).fill(d2 * sigma + L * d3 * sigma),
      lcl: Array<number>(m).fill(Math.max(0, d2 * sigma - L * d3 * sigma)),
      violations: [],
      // Como la API real: MR_k (subgrupo k+1) queda fuera si el subgrupo k o el k+1 está excluido.
      // Los índices de `excluded` son de subgrupo, nunca de posición en `values`.
      excluded: mr.map((_, j) => j + 1).filter((g) => exSet.has(g) || exSet.has(g - 1)),
      indices: mr.map((_, j) => j + 1),
      rules_applied: enabled,
      rules_skipped: [],
    };
  }
  Object.assign(second, splitRules(enabled, false));
  second.violations = violationsFor(second, enabled, L, false, req.chart_type === "i_mr" ? (j) => j + 1 : (j) => j);

  const limits: S["FrozenLimits"] =
    phase === "II"
      ? req.limits!
      : {
          chart_type: req.chart_type,
          subgroup_size: n,
          sigma_method: method,
          params: { mu, sigma },
          points_used: used.length,
          excluded,
          limit_width: L,
        };
  const resp = buildResponse({
    chartType: req.chart_type,
    phase,
    charts: [main, second],
    limits,
    excluded,
    labels,
    firstPanelIsMain: true,
  });
  if (phase === "I")
    resp.interpretation.findings.unshift(
      `Parámetros estimados: media del proceso ${fmt(mu)}, sigma ${fmt(sigma)} (método ${method === "rbar_d2" ? "R-barra/d2" : method === "sbar_c4" ? "S-barra/c4" : "MR-barra/d2"}).`,
    );
  return resp;
}

// ----------------------------------------------------------------------------
export function mockAttributesChart(req: S["AttributesChartRequest"]): S["ChartResponse"] {
  const counts = req.counts;
  if (counts.length < 2) throw new MockHttpError("Se necesitan al menos 2 subgrupos.");
  if (counts.some((c) => c < 0)) throw new MockHttpError("Los conteos no pueden ser negativos.");
  const L = req.limit_width ?? 3;
  const type = req.chart_type;
  const needsSizes = type !== "c";
  const sizes = req.sizes ?? [];
  if (needsSizes && sizes.length !== counts.length) throw new MockHttpError("Falta el tamaño de muestra de cada subgrupo.");
  if (needsSizes && sizes.some((s) => !(s > 0))) throw new MockHttpError("Los tamaños de muestra deben ser positivos.");
  if (type === "np" && new Set(sizes).size !== 1) throw new MockHttpError("El gráfico np exige tamaño de muestra constante; usa p.");
  if ((type === "p" || type === "np") && counts.some((c, i) => c > sizes[i]))
    throw new MockHttpError("Hay subgrupos con más defectuosos que unidades inspeccionadas.");
  const labels = req.labels ?? counts.map((_, i) => String(i + 1));
  const phase = req.phase;
  const excluded = phase === "I" ? req.excluded ?? [] : [];
  checkExcluded(excluded, counts.length);
  const exSet = new Set(excluded.map((e) => e.index));
  const used = counts.map((_, i) => i).filter((i) => !exSet.has(i));
  if (phase === "II" && !req.limits) throw new MockHttpError("La Fase II necesita los límites congelados de la Fase I.");
  if (used.length < 2) throw new MockHttpError("Quedan menos de 2 subgrupos en el cálculo.");
  const enabled = (req.rules?.enabled ?? DEFAULT_RULES) as RuleId[];

  const key = type === "p" || type === "np" ? "p_bar" : type === "c" ? "c_bar" : "u_bar";
  let bar: number;
  if (phase === "II") {
    bar = req.limits!.params[key];
    if (!(bar >= 0)) throw new MockHttpError("Los límites congelados no coinciden con este tipo de gráfico.");
  } else if (type === "p" || type === "np" || type === "u") {
    bar = sum(used.map((i) => counts[i])) / sum(used.map((i) => sizes[i]));
  } else bar = mean(used.map((i) => counts[i]));

  let values: number[];
  let center: number[];
  let half: number[];
  const cap = (x: number) => x;
  switch (type) {
    case "p":
      values = counts.map((c, i) => c / sizes[i]);
      center = counts.map(() => bar);
      half = sizes.map((n) => L * Math.sqrt((bar * (1 - bar)) / n));
      break;
    case "np":
      values = counts;
      center = counts.map(() => sizes[0] * bar);
      half = counts.map(() => L * Math.sqrt(sizes[0] * bar * (1 - bar)));
      break;
    case "c":
      values = counts;
      center = counts.map(() => bar);
      half = counts.map(() => L * Math.sqrt(bar));
      break;
    default:
      values = counts.map((c, i) => c / sizes[i]);
      center = counts.map(() => bar);
      half = sizes.map((n) => L * Math.sqrt(bar / n));
  }
  const upperCap = type === "p" ? 1 : Infinity;
  const panel: Series = {
    name: type,
    title: { p: "Gráfico p (fracción defectuosa)", np: "Gráfico np (número de defectuosos)", c: "Gráfico c (defectos por unidad de inspección)", u: "Gráfico u (defectos por unidad)" }[type],
    labels,
    values,
    center,
    ucl: center.map((c, i) => Math.min(upperCap, cap(c + half[i]))),
    lcl: center.map((c, i) => Math.max(0, c - half[i])),
    violations: [],
    excluded: [...exSet].sort((a, b) => a - b),
    indices: labels.map((_, i) => i),
    rules_applied: enabled,
    rules_skipped: [],
  };
  Object.assign(panel, splitRules(enabled, false));
  panel.violations = violationsFor(panel, enabled, L, false);

  const limits: S["FrozenLimits"] =
    phase === "II"
      ? req.limits!
      : {
          chart_type: type,
          subgroup_size: new Set(sizes).size === 1 && needsSizes ? sizes[0] : null,
          sigma_method: null,
          params: { [key]: bar },
          points_used: used.length,
          excluded,
          limit_width: L,
        };
  const resp = buildResponse({ chartType: type, phase, charts: [panel], limits, excluded, labels, firstPanelIsMain: true });
  if (phase === "I") resp.interpretation.findings.unshift(`Parámetro estimado: ${key.replace("_", "-")} = ${fmt(bar, 4)}.`);
  if (type !== "c" && new Set(sizes).size > 1)
    resp.interpretation.findings.push("El tamaño de muestra varía: los límites cambian de un subgrupo a otro.");
  return resp;
}

export function mockRecommend(req: S["RecommendRequest"]): S["RecommendResponse"] {
  const defectives = req.counting === "defectives";
  const defects = req.counting === "defects";
  if (!defectives && !defects) throw new MockHttpError("`counting` debe ser 'defectives' o 'defects'.");
  if (defectives)
    return req.constant_size
      ? {
          chart_type: "np",
          alternatives: ["p"],
          justification:
            "Cuentas unidades no conformes (cada unidad es conforme o no) con tamaño de muestra constante: el gráfico np muestra directamente el número de defectuosos. El gráfico p equivale y es preferible si quieres ver fracciones.",
        }
      : {
          chart_type: "p",
          alternatives: [],
          justification:
            "Cuentas unidades no conformes y el tamaño de muestra cambia: el gráfico p trabaja con la fracción defectuosa y ajusta los límites a cada n. El np exige n constante y no es adecuado aquí.",
        };
  return req.constant_size
    ? {
        chart_type: "c",
        alternatives: ["u"],
        justification:
          "Cuentas no conformidades (defectos) y cada subgrupo inspecciona la misma cantidad de producto: el gráfico c (distribución de Poisson) es el adecuado. El u equivale por unidad.",
      }
    : {
        chart_type: "u",
        alternatives: [],
        justification:
          "Cuentas no conformidades y la cantidad inspeccionada por subgrupo varía: el gráfico u normaliza por unidad de inspección y ajusta los límites a cada tamaño.",
      };
}

"use client";

// Convierte un análisis guardado (analyses.result, tal como lo devolvió la API) en
// las tablas y figuras de su sección del reporte. No calcula estadística: ordena y
// da formato a lo que ya trae el resultado. Cada función devuelve bloques sin
// número; la numeración correlativa la asigna ReportDocument.

import type { ReactNode } from "react";
import { ControlChart } from "@/components/charts/ControlChart";
import { AcfChart, CurveChart, HistogramChart, QQChart, TradeoffChart } from "@/components/charts/StatCharts";
import { Badge, fmtNum, numEs } from "@/components/ui";
import type { components } from "@/lib/api-types";
import type { Analysis, Dataset, Study } from "@/lib/db";
import { CHART_TYPE_LABEL, PARAM_LABEL, SIGMA_METHOD_LABEL, fmtDateTime, slug } from "@/lib/labels";
import { KeyValueTable, RTable, type Block } from "./apa";

type S = components["schemas"];

export interface SectionCtx {
  study: Study;
  analysis: Analysis;
  dataset: Dataset | null;
}

const pct = (x: number | null | undefined, d = 2) => (x == null ? "—" : `${fmtNum(x * 100, d)} %`);
const num = (x: number | null | undefined, d = 3) => fmtNum(x, d);
const isRecord = (x: unknown): x is Record<string, unknown> => !!x && typeof x === "object" && !Array.isArray(x);

function fileBase(ctx: SectionCtx, key: string) {
  return `${slug(ctx.study.name)}-${slug(ctx.analysis.title)}-${key}`;
}

// --- Datos (módulo 1) -------------------------------------------------------------
function dataBlocks(ctx: SectionCtx): Block[] {
  const r = ctx.analysis.result;
  const blocks: Block[] = [];
  if ("outliers" in r) {
    const v = r as unknown as S["SummaryResponse"];
    const o = v.overall;
    blocks.push({
      kind: "table",
      title: "Estadística descriptiva de todas las observaciones",
      note: "Calculada por la API con todas las observaciones juntas, sin distinguir subgrupos. La curtosis es el exceso respecto a la normal.",
      node: (
        <KeyValueTable
          caption="Estadística descriptiva global"
          head={["Estadístico", "Valor"]}
          rows={[
            ["Observaciones", String(o.count)],
            ["Subgrupos", String(v.subgroups.length)],
            ["Tamaño de subgrupo", v.constant_size ? "Constante" : "Variable"],
            ["Media", num(o.mean, 4)],
            ["Desviación estándar", num(o.std, 4)],
            ["Mínimo", num(o.min, 3)],
            ["Primer cuartil (Q1)", num(o.q1, 3)],
            ["Mediana", num(o.median, 3)],
            ["Tercer cuartil (Q3)", num(o.q3, 3)],
            ["Máximo", num(o.max, 3)],
            ["Asimetría", num(o.skewness, 3)],
            ["Curtosis (exceso)", num(o.kurtosis, 3)],
          ]}
        />
      ),
    });
    const MAX = 80;
    blocks.push({
      kind: "table",
      title: "Resumen por subgrupo",
      note: v.subgroups.length > MAX ? `Se muestran los primeros ${MAX} de ${v.subgroups.length} subgrupos; el Excel trae todos.` : undefined,
      node: (
        <RTable
          caption="Resumen por subgrupo"
          columns={["Subgrupo", "n", "Media", "Rango", "Desv. est.", "Mín.", "Máx."]}
          rows={v.subgroups.slice(0, MAX).map((s) => [s.label, String(s.n), num(s.mean, 3), num(s.range, 3), num(s.std, 3), num(s.min, 2), num(s.max, 2)])}
        />
      ),
    });
    if (v.outliers.length > 0)
      blocks.push({
        kind: "table",
        title: "Observaciones atípicas marcadas",
        note: "Criterio 1,5·IQR. Los atípicos no se eliminan en silencio: la decisión sobre cada uno queda en la bitácora de limpieza.",
        node: (
          <RTable
            caption="Observaciones atípicas"
            numeric={false}
            columns={["Subgrupo", "Posición", "Valor", "Motivo"]}
            rows={v.outliers.map((x) => [v.subgroups[x.subgroup_index]?.label ?? String(x.subgroup_index + 1), String(x.position + 1), num(x.value, 2), x.reason])}
          />
        ),
      });
  } else if ("total_count" in r) {
    const v = r as unknown as S["AttributeSummaryResponse"];
    blocks.push({
      kind: "table",
      title: "Resumen global de los datos por atributos",
      node: (
        <KeyValueTable
          caption="Resumen global de atributos"
          rows={[
            ["Subgrupos", String(v.subgroups)],
            ["Conteo total", num(v.total_count, 0)],
            ["Unidades inspeccionadas", v.total_size == null ? "—" : num(v.total_size, 0)],
            ["Tasa global", v.overall_rate == null ? "—" : num(v.overall_rate, 4)],
            ["Conteo medio por subgrupo", num(v.mean_count, 3)],
            ["Tamaño de muestra", v.constant_size == null ? "—" : v.constant_size ? "Constante" : `Variable (de ${num(v.min_size, 0)} a ${num(v.max_size, 0)})`],
          ]}
        />
      ),
    });
    const MAX = 80;
    blocks.push({
      kind: "table",
      title: "Resumen por subgrupo",
      note: v.rows.length > MAX ? `Se muestran los primeros ${MAX} de ${v.rows.length} subgrupos.` : undefined,
      node: (
        <RTable
          caption="Resumen de atributos por subgrupo"
          columns={["Subgrupo", "Conteo", "Tamaño de muestra", "Tasa"]}
          rows={v.rows.slice(0, MAX).map((x) => [x.label, num(x.count, 0), x.size == null ? "—" : num(x.size, 0), x.rate == null ? "—" : num(x.rate, 4)])}
        />
      ),
    });
  }
  const log = ctx.dataset?.cleaning_log ?? [];
  if (log.length > 0)
    blocks.push({
      kind: "table",
      title: "Bitácora de limpieza del conjunto de datos",
      note: ctx.dataset && "justification" in ctx.dataset.subgrouping ? `Justificación del subgrupo racional: ${ctx.dataset.subgrouping.justification}` : undefined,
      node: (
        <RTable
          caption="Bitácora de limpieza"
          numeric={false}
          columns={["Acción", "Detalle", "Fecha"]}
          rows={log.map((l) => [l.action, l.detail, fmtDateTime(l.at)])}
        />
      ),
    });
  return blocks;
}

// --- Gráficos de control (módulos 2 y 3) ---------------------------------------------
function limitCell(values: number[]) {
  const first = values[0];
  return values.every((v) => v === first) ? num(first, 4) : "Varía con n (ver figura)";
}

function chartBlocks(ctx: SectionCtx): Block[] {
  const r = ctx.analysis.result as unknown as S["ChartResponse"];
  const isI = r.phase === "I";
  const faseText = isI ? "Fase I, límites de prueba" : "Fase II, límites congelados";
  const blocks: Block[] = [];

  r.charts.forEach((c) =>
    blocks.push({
      kind: "figure",
      title: `${c.title}. ${faseText}`,
      note: isI
        ? "Rombo con la regla: punto con señal. Cruz: punto excluido del cálculo por causa asignable. Línea discontinua: límites de prueba, que se recalculan al excluir puntos."
        : "Rombo con la regla: punto con señal. Línea continua: límites congelados en la Fase I; no se recalcularon con estos datos.",
      node: <ControlChart series={c} phase={r.phase} fileName={fileBase(ctx, c.name)} />,
    }),
  );

  const L = r.limits;
  const paramRows: [string, ReactNode][] = [
    ["Tipo de gráfico", CHART_TYPE_LABEL[L.chart_type] ?? L.chart_type],
    ["Fase", isI ? "I (estimación de límites)" : "II (monitoreo con límites congelados)"],
    ...Object.entries(L.params).map(([k, v]) => [PARAM_LABEL[k] ?? k, num(v, 4)] as [string, ReactNode]),
    ["Ancho de los límites (L, en sigmas)", num(L.limit_width, 1)],
    ["Subgrupos usados en los límites", String(L.points_used)],
  ];
  if (L.subgroup_size != null) paramRows.push(["Tamaño de subgrupo", String(L.subgroup_size)]);
  if (L.sigma_method) paramRows.push(["Estimador de σ", SIGMA_METHOD_LABEL[L.sigma_method] ?? L.sigma_method]);
  blocks.push({
    kind: "table",
    title: isI ? "Parámetros del proceso estimados en Fase I" : "Parámetros congelados usados en Fase II",
    note: isI ? undefined : "Estos parámetros vienen de la Fase I y no se recalcularon.",
    node: <KeyValueTable caption="Parámetros del proceso" rows={paramRows} />,
  });
  blocks.push({
    kind: "table",
    title: "Límites de control por gráfico",
    note: "LCI = límite de control inferior; LCS = límite de control superior.",
    node: (
      <RTable
        caption="Límites de control"
        columns={["Gráfico", "LCI", "Línea central", "LCS"]}
        rows={r.charts.map((c) => [c.title, limitCell(c.lcl), limitCell(c.center), limitCell(c.ucl)])}
      />
    ),
  });

  const labels = r.charts[0]?.labels ?? [];
  const sig = r.charts.flatMap((c) => c.violations.map((v) => ({ panel: c.title, v })));
  if (sig.length > 0)
    blocks.push({
      kind: "table",
      title: "Señales detectadas",
      note: "Cada fila es una regla de corrida que se cumplió; un mismo subgrupo puede aparecer en varios gráficos.",
      node: (
        <RTable
          caption="Señales detectadas"
          numeric={false}
          columns={["Subgrupo", "Gráfico", "Regla", "Descripción"]}
          rows={sig
            .sort((a, b) => a.v.index - b.v.index)
            .map(({ panel, v }) => [labels[v.index] ?? String(v.index + 1), panel, v.rule, v.description])}
        />
      ),
    });
  if (isI && L.excluded.length > 0)
    blocks.push({
      kind: "table",
      title: "Puntos excluidos del cálculo de límites",
      note: "Cada exclusión exige una causa asignable documentada.",
      node: (
        <RTable
          caption="Puntos excluidos"
          numeric={false}
          columns={["Subgrupo", "Causa asignable"]}
          rows={L.excluded.map((e) => [e.label ?? labels[e.index] ?? String(e.index + 1), e.cause])}
        />
      ),
    });
  return blocks;
}

// --- Supuestos (módulo 4) -------------------------------------------------------------
function testsTable(tests: S["TestResult"][], caption: string): ReactNode {
  return (
    <RTable
      caption={caption}
      columns={["Prueba", "Estadístico", "Valor p", "Valor crítico", "Decisión"]}
      rows={tests.map((t) => [
        t.name,
        num(t.statistic, 4),
        num(t.p_value, 4),
        num(t.critical_value, 3),
        t.reject ? <Badge key="d" tone="error">× Se rechaza H0</Badge> : <Badge key="d" tone="ok">✓ No se rechaza H0</Badge>,
      ])}
    />
  );
}

function assumptionBlocks(ctx: SectionCtx): Block[] {
  const r = ctx.analysis.result as unknown as S["AssumptionsResponse"];
  const unit = ctx.study.unit ?? "Valor";
  const alpha = isRecord(ctx.analysis.params) && typeof ctx.analysis.params.alpha === "number" ? ctx.analysis.params.alpha : null;
  const noteA = alpha != null ? `Nivel de significancia α = ${num(alpha, 2)}.` : undefined;
  const d = r.descriptive;
  return [
    {
      kind: "table",
      title: "Pruebas de normalidad",
      note: `${noteA ?? ""} H0: los datos provienen de una distribución normal. ${r.normality.map((t) => `${t.name}: ${t.conclusion}`).join(" ")}`.trim(),
      node: testsTable(r.normality, "Pruebas de normalidad"),
    },
    {
      kind: "figure",
      title: "Gráfico cuantil-cuantil (Q-Q) normal",
      note: "Si los puntos siguen la recta de referencia, los datos se ajustan a la distribución normal.",
      node: <QQChart points={r.qq} title="Gráfico Q-Q normal" fileName={fileBase(ctx, "qq")} />,
    },
    {
      kind: "figure",
      title: "Histograma con la curva normal ajustada",
      node: <HistogramChart histogram={r.histogram} title="Histograma con curva normal" xTitle={unit} fileName={fileBase(ctx, "histograma")} />,
    },
    {
      kind: "table",
      title: "Pruebas de independencia",
      note: r.independence.map((t) => `${t.name}: ${t.conclusion}`).join(" "),
      node: testsTable(r.independence, "Pruebas de independencia"),
    },
    {
      kind: "figure",
      title: "Función de autocorrelación (ACF) con bandas de significancia",
      note: `Barras rayadas: rezagos fuera de la banda ±${num(r.autocorrelation.band, 3)}. Rezagos significativos: ${r.autocorrelation.significant_lags.join(", ") || "ninguno"}.`,
      node: <AcfChart acf={r.autocorrelation} title="Función de autocorrelación (ACF)" fileName={fileBase(ctx, "acf")} />,
    },
    {
      kind: "table",
      title: "Estadística descriptiva de las observaciones",
      node: (
        <KeyValueTable
          caption="Estadística descriptiva"
          rows={[
            ["n", String(d.count)],
            ["Media", num(d.mean, 4)],
            ["Desviación estándar", num(d.std, 4)],
            ["Mínimo", num(d.min, 3)],
            ["Q1", num(d.q1, 3)],
            ["Mediana", num(d.median, 3)],
            ["Q3", num(d.q3, 3)],
            ["Máximo", num(d.max, 3)],
            ["Asimetría", num(d.skewness, 3)],
            ["Curtosis (exceso)", num(d.kurtosis, 3)],
          ]}
        />
      ),
    },
  ];
}

// --- Capacidad (módulo 5) ---------------------------------------------------------------
const INDEX_ROWS: [keyof S["CapabilityResponse"], string][] = [
  ["cp", "Cp"],
  ["cpl", "Cpl"],
  ["cpu", "Cpu"],
  ["cpk", "Cpk"],
  ["pp", "Pp"],
  ["ppl", "Ppl"],
  ["ppu", "Ppu"],
  ["ppk", "Ppk"],
  ["cpm", "Cpm"],
];
const VERDICT: Record<string, string> = {
  inadequate: "Inadecuada (Cpk < 1)",
  marginal: "Marginal (1 ≤ Cpk < 1,33)",
  adequate: "Adecuada (1,33 ≤ Cpk < 1,67)",
  excellent: "Excelente (Cpk ≥ 1,67)",
};

/** Qué datos entraron al cálculo: subgrupos retenidos y, si hay límites congelados, sus exclusiones. */
function capabilityData(p: Partial<S["CapabilityRequest"]>): string {
  const n = p.subgroups?.length;
  if (n == null) return "—";
  const ex = p.limits?.excluded ?? [];
  if (!p.limits) return `${n} (σ estimada con estos subgrupos)`;
  const excl = ex.length ? `excluidos al congelar: ${ex.map((e) => `${e.label ?? e.index + 1} (${e.cause})`).join("; ")}` : "sin exclusiones al congelar";
  return `${n}; σ de Fase I (límites congelados; ${excl})`;
}

function capabilityBlocks(ctx: SectionCtx): Block[] {
  const r = ctx.analysis.result as unknown as S["CapabilityResponse"];
  const p = ctx.analysis.params as Partial<S["CapabilityRequest"]>;
  const conf = Math.round((p.confidence ?? 0.95) * 100);
  const xTitle = ctx.study.unit ? `${ctx.study.characteristic ?? "Valor"} (${ctx.study.unit})` : (ctx.study.characteristic ?? "Valor");
  const nc: [string, S["NonConforming"]][] = [
    ["Esperada, variación dentro del subgrupo (normal)", r.expected_within],
    ["Esperada, variación total (normal)", r.expected_overall],
    ["Observada (conteo directo)", r.observed],
  ];
  return [
    {
      kind: "table",
      title: "Condiciones del estudio de capacidad",
      note: "Los índices solo son interpretables si el proceso es estable y, para el modelo normal, si los datos son normales.",
      node: (
        <KeyValueTable
          caption="Condiciones del estudio de capacidad"
          rows={[
            ["Observaciones (n)", String(r.n)],
            ["Subgrupos usados", capabilityData(p)],
            ["Media", num(r.mean, 4)],
            ["σ dentro del subgrupo", num(r.sigma_within, 4)],
            ["σ total", num(r.sigma_overall, 4)],
            ["Estimador de σ", SIGMA_METHOD_LABEL[r.sigma_method] ?? r.sigma_method],
            ["LSL / USL / objetivo", `${numEs(p.lsl)} / ${numEs(p.usl)} / ${numEs(p.target)}`],
            ["Proceso estable", p.is_stable == null ? "No verificado" : p.is_stable ? "Sí" : "No"],
            ["Datos normales", p.is_normal == null ? "No verificado" : p.is_normal ? "Sí" : "No"],
            ["Veredicto de capacidad", VERDICT[r.verdict] ?? r.verdict],
          ]}
        />
      ),
    },
    {
      kind: "figure",
      title: "Histograma de los datos con las especificaciones",
      note: "Líneas de LSL y USL (continuas) y objetivo (discontinua); la curva es la normal ajustada.",
      node: (
        <HistogramChart
          histogram={r.histogram}
          title="Histograma con especificaciones"
          xTitle={xTitle}
          specs={{ lsl: p.lsl, usl: p.usl, target: p.target }}
          fileName={fileBase(ctx, "histograma")}
        />
      ),
    },
    {
      kind: "table",
      title: `Índices de capacidad con intervalos de confianza del ${conf} %`,
      note: "«—» significa que el índice no aplica con las especificaciones dadas.",
      node: (
        <RTable
          caption="Índices de capacidad"
          columns={["Índice", "Valor", "IC inferior", "IC superior"]}
          rows={INDEX_ROWS.map(([k, name]) => {
            const v = r[k] as S["IndexValue"];
            return [name, num(v.value, 3), num(v.lower, 3), num(v.upper, 3)];
          })}
        />
      ),
    },
    {
      kind: "table",
      title: "Fracción no conforme esperada y observada",
      note: "PPM = partes por millón. La esperada supone distribución normal; la observada es el conteo directo en los datos.",
      node: (
        <RTable
          caption="Fracción no conforme"
          columns={["Fuente", "Bajo el LSL", "Sobre el USL", "Total", "PPM"]}
          rows={nc.map(([name, v]) => [name, pct(v.below_lsl, 4), pct(v.above_usl, 4), pct(v.total, 4), num(v.ppm, 1)])}
        />
      ),
    },
  ];
}

// --- Diseño (módulo 6) -------------------------------------------------------------------
const CHART_NAME: Record<string, string> = { xbar: "X-barra", individuals: "Individuales (I)", p: "p", c: "c" };

function designBlocks(ctx: SectionCtx): Block[] {
  const raw = ctx.analysis.result;
  if ("arl_curve" in raw) {
    const a = raw as unknown as S["ArlResponse"];
    const p = ctx.analysis.params as Partial<S["ArlRequest"]>;
    const shiftTitle = p.chart === "p" ? "p1" : p.chart === "c" ? "c1" : "Desplazamiento δ (σ)";
    const sim = a.method === "simulation";
    const blocks: Block[] = [
      {
        kind: "table",
        title: "Diseño evaluado y su desempeño en control",
        node: (
          <KeyValueTable
            caption="Diseño evaluado"
            rows={[
              ["Tipo de gráfico", CHART_NAME[p.chart ?? ""] ?? String(p.chart ?? "—")],
              ["Tamaño de muestra n", String(p.n ?? "—")],
              ["Ancho de límites L (sigmas)", num(p.limit_width, 2)],
              ["Intervalo de muestreo h (horas)", num(p.sampling_interval, 2)],
              ["Reglas de corrida", (p.rules?.enabled ?? ["WE1"]).join(", ")],
              ["Método", sim ? "Simulación" : "Cálculo exacto"],
              ["α por muestra", a.alpha == null ? "—" : num(a.alpha, 5)],
              ["ARL0", `${num(a.arl0, 1)}${a.arl0_std_error != null ? ` (± ${num(a.arl0_std_error, 1)} error estándar)` : ""}`],
              ["ATS0 (horas)", num(a.ats0, 1)],
              ["Carga muestral n/h (unidades por hora)", num(a.sampling_load, 2)],
            ]}
          />
        ),
      },
      {
        kind: "table",
        title: "ARL1 y ATS1 según el tamaño del cambio",
        note: sim ? "Valores por simulación; el error estándar indica su precisión." : "Valores calculados de forma exacta.",
        node: (
          <RTable
            caption="ARL1 y ATS1"
            columns={[shiftTitle, "β", "ARL1", "ATS1 (h)", "Unidades hasta detectar", ...(sim ? ["Error estándar"] : [])]}
            rows={a.rows.map((x) => [num(x.shift, 3), num(x.beta, 4), num(x.arl1, 2), num(x.ats1, 2), num(x.units_to_detect, 1), ...(sim ? [num(x.std_error, 2)] : [])])}
          />
        ),
      },
      {
        kind: "figure",
        title: "Curva característica de operación (OC) del gráfico",
        note: sim ? "En simulación, la curva corresponde a la regla de un punto fuera de límites sola, como referencia." : undefined,
        node: (
          <CurveChart
            title="Curva característica de operación (OC)"
            fileName={fileBase(ctx, "oc")}
            series={[{ name: "β (prob. de no detectar)", points: a.oc_curve }]}
            xTitle={shiftTitle}
            yTitle="β"
            yRange={[0, 1.02]}
          />
        ),
      },
      {
        kind: "figure",
        title: "ARL según el tamaño del cambio",
        node: (
          <CurveChart title="ARL según el tamaño del cambio" fileName={fileBase(ctx, "arl")} series={[{ name: "ARL", points: a.arl_curve }]} xTitle={shiftTitle} yTitle="ARL (muestras)" logY />
        ),
      },
    ];
    return blocks;
  }
  const c = raw as unknown as S["CompareResponse"];
  return [
    {
      kind: "table",
      title: `Comparación de diseños para detectar un desplazamiento de ${num(c.shift, 2)} σ`,
      note: "Carga muestral = n/h, unidades inspeccionadas por hora: conecta el diseño con el costo de muestreo.",
      node: (
        <RTable
          caption="Comparación de diseños"
          columns={["n", "L", "h (h)", "ARL0", "ATS0 (h)", "ARL1", "ATS1 (h)", "Carga n/h"]}
          rows={c.rows.map((r) => [String(r.n), num(r.limit_width, 2), num(r.sampling_interval, 2), num(r.arl0, 1), num(r.ats0, 1), num(r.arl1, 2), num(r.ats1, 2), num(r.sampling_load, 2)])}
        />
      ),
    },
    {
      kind: "figure",
      title: "Detección frente a carga de inspección",
      note: "Cada punto es un diseño: a la izquierda inspecciona menos; abajo detecta antes.",
      node: <TradeoffChart rows={c.rows} title="Detección frente a carga de inspección" fileName={fileBase(ctx, "comparador")} />,
    },
  ];
}

// --- Muestreo (módulo 7) -------------------------------------------------------------------
function samplingBlocks(ctx: SectionCtx): Block[] {
  const raw = ctx.analysis.result;
  const params = ctx.analysis.params as Record<string, number | string | null | undefined | { n: number; c: number }>;
  const vlines = [
    typeof params.aql === "number" ? { x: params.aql, label: "AQL" } : null,
    typeof params.ltpd === "number" ? { x: params.ltpd, label: "LTPD" } : null,
  ].filter(Boolean) as { x: number; label: string }[];
  const xP = "Fracción defectuosa del lote (p)";
  const base = fileBase(ctx, "");
  const lot = typeof params.lot_size === "number" ? String(params.lot_size) : "No indicado";

  if ("asn_curve" in raw) {
    const r = raw as unknown as S["DoublePlanResponse"];
    return [
      {
        kind: "table",
        title: "Plan de muestreo doble evaluado",
        note: "Se acepta con la primera muestra si d1 ≤ c1 y se rechaza si d1 ≥ r1; en otro caso se toma la segunda y se acepta si d1 + d2 ≤ c2.",
        node: (
          <KeyValueTable
            caption="Plan doble"
            rows={[
              ["Primera muestra: n1, c1, r1", `${params.n1}, ${params.c1}, ${params.r1}`],
              ["Segunda muestra: n2, c2", `${params.n2}, ${params.c2}`],
              ["Tamaño del lote N", lot],
              ["AQL / LTPD", `${typeof params.aql === "number" ? pct(params.aql) : "—"} / ${typeof params.ltpd === "number" ? pct(params.ltpd) : "—"}`],
              ["Riesgo del productor α real", pct(r.alpha_actual)],
              ["Riesgo del consumidor β real", pct(r.beta_actual)],
              ["AOQL", `${pct(r.aoql, 3)}${r.aoql_at != null ? ` en p = ${pct(r.aoql_at)}` : ""}`],
            ]}
          />
        ),
      },
      {
        kind: "figure",
        title: "Curva OC del plan doble",
        node: (
          <CurveChart
            title="Curva OC del plan doble"
            fileName={`${base}oc`}
            series={[
              { name: "Pa total", points: r.oc_curve },
              { name: "Aceptar con la 1.ª muestra", points: r.first_sample_accept_curve, dash: "dash" },
            ]}
            xTitle={xP}
            yTitle="Probabilidad de aceptación"
            yRange={[0, 1.02]}
            vlines={vlines}
          />
        ),
      },
      {
        kind: "figure",
        title: "Tamaño de muestra promedio (ASN)",
        node: <CurveChart title="Tamaño de muestra promedio (ASN)" fileName={`${base}asn`} series={[{ name: "ASN", points: r.asn_curve }]} xTitle={xP} yTitle="Unidades inspeccionadas por lote" vlines={vlines} />,
      },
      {
        kind: "figure",
        title: "Calidad promedio de salida (AOQ)",
        node: <CurveChart title="Calidad promedio de salida (AOQ)" fileName={`${base}aoq`} series={[{ name: "AOQ", points: r.aoq_curve }]} xTitle="Fracción defectuosa de entrada (p)" yTitle="AOQ" vlines={vlines} />,
      },
      ...(r.ati_curve
        ? [
            {
              kind: "figure",
              title: "Inspección total promedio (ATI)",
              node: <CurveChart title="Inspección total promedio (ATI)" fileName={`${base}ati`} series={[{ name: "ATI", points: r.ati_curve }]} xTitle={xP} yTitle="Unidades inspeccionadas por lote" />,
            } satisfies Block,
          ]
        : []),
    ];
  }
  const r = raw as unknown as S["SinglePlanResponse"];
  const ref = params.reference_plan && typeof params.reference_plan === "object" ? (params.reference_plan as { n: number; c: number }) : null;
  return [
    {
      kind: "table",
      title: "Plan de muestreo simple por atributos",
      note: ref ? `Plan de referencia para comparar: n = ${ref.n}, c = ${ref.c}.` : "Se acepta el lote si la muestra tiene c o menos defectuosos.",
      node: (
        <KeyValueTable
          caption="Plan simple"
          rows={[
            ["Tamaño de muestra n", String(r.n)],
            ["Número de aceptación c", String(r.c)],
            ["Distribución", r.distribution === "binomial" ? "Binomial" : r.distribution === "poisson" ? "Poisson" : "Hipergeométrica"],
            ["Tamaño del lote N", lot],
            ["AQL / α objetivo", `${typeof params.aql === "number" ? pct(params.aql) : "—"} / ${typeof params.alpha === "number" ? pct(params.alpha, 1) : "—"}`],
            ["LTPD / β objetivo", `${typeof params.ltpd === "number" ? pct(params.ltpd) : "—"} / ${typeof params.beta === "number" ? pct(params.beta, 1) : "—"}`],
            ["Riesgo del productor α real", pct(r.alpha_actual)],
            ["Riesgo del consumidor β real", pct(r.beta_actual)],
            ["AOQL", `${pct(r.aoql, 3)} en p = ${pct(r.aoql_at)}`],
          ]}
        />
      ),
    },
    {
      kind: "figure",
      title: "Curva OC: probabilidad de aceptar el lote",
      node: <CurveChart title="Curva OC" fileName={`${base}oc`} series={[{ name: "Pa", points: r.oc_curve }]} xTitle={xP} yTitle="Probabilidad de aceptación (Pa)" yRange={[0, 1.02]} vlines={vlines} />,
    },
    {
      kind: "figure",
      title: "Calidad promedio de salida (AOQ)",
      node: <CurveChart title="Calidad promedio de salida (AOQ)" fileName={`${base}aoq`} series={[{ name: "AOQ", points: r.aoq_curve }]} xTitle="Fracción defectuosa de entrada (p)" yTitle="AOQ" vlines={vlines} />,
    },
    ...(r.ati_curve
      ? [
          {
            kind: "figure",
            title: "Inspección total promedio (ATI)",
            node: <CurveChart title="Inspección total promedio (ATI)" fileName={`${base}ati`} series={[{ name: "ATI", points: r.ati_curve }]} xTitle={xP} yTitle="Unidades inspeccionadas por lote" />,
          } satisfies Block,
        ]
      : []),
  ];
}

export function buildBlocks(ctx: SectionCtx): Block[] {
  switch (ctx.analysis.module) {
    case "data":
      return dataBlocks(ctx);
    case "variables":
    case "attributes":
      return chartBlocks(ctx);
    case "assumptions":
      return assumptionBlocks(ctx);
    case "capability":
      return capabilityBlocks(ctx);
    case "design":
      return designBlocks(ctx);
    case "sampling":
      return samplingBlocks(ctx);
  }
}

/** Línea breve con los parámetros que definen el análisis (bajo el título de la sección). */
export function paramsLine(ctx: SectionCtx): string | null {
  const { analysis, dataset } = ctx;
  const p = analysis.params as Record<string, unknown>;
  const parts: string[] = [];
  if (dataset) parts.push(`Conjunto de datos: ${dataset.name} (Fase ${dataset.phase}, ${dataset.rows.length} subgrupos)`);
  if (analysis.module === "variables" || analysis.module === "attributes") {
    if (typeof p.chart_type === "string") parts.push(`Gráfico ${CHART_TYPE_LABEL[p.chart_type] ?? p.chart_type}`);
    if (typeof p.limit_width === "number") parts.push(`L = ${numEs(p.limit_width)}`);
    const rules = (p.rules as { enabled?: string[] } | undefined)?.enabled;
    if (rules?.length) parts.push(`Reglas: ${rules.join(", ")}`);
  }
  return parts.length ? parts.join(" · ") : null;
}

"use client";

import type { Data, Layout, Shape } from "plotly.js";
import type { components } from "@/lib/api-types";
import { fmtNum, numEs } from "@/components/ui";
import { PlotlyChart } from "./PlotlyChart";
import { useChartTheme } from "./theme";

type S = components["schemas"];

function axis(t: ReturnType<typeof useChartTheme>, title: string, extra: object = {}) {
  return { title: { text: title }, gridcolor: t.grid, linecolor: t.grid, zerolinecolor: t.grid, tickfont: { color: t.muted }, automargin: true, ...extra };
}

/** Histograma con la curva normal ajustada y, opcionalmente, las especificaciones. */
export function HistogramChart({
  histogram,
  title,
  fileName,
  xTitle,
  specs,
  curveName = "Normal ajustada",
}: {
  histogram: S["Histogram"];
  title: string;
  fileName: string;
  xTitle: string;
  specs?: { lsl?: number | null; usl?: number | null; target?: number | null };
  curveName?: string;
}) {
  const t = useChartTheme();
  const { edges, counts } = histogram;
  const centers = counts.map((_, i) => (edges[i] + edges[i + 1]) / 2);
  const widths = counts.map((_, i) => edges[i + 1] - edges[i]);
  const data: Data[] = [
    {
      type: "bar",
      x: centers,
      y: counts,
      width: widths,
      name: "Frecuencia observada",
      marker: { color: t.series[0], opacity: 0.8, line: { color: t.surface, width: 1.5 } },
      hovertemplate: "Entre %{customdata[0]:,.3f} y %{customdata[1]:,.3f}<br>Frecuencia %{y}<extra></extra>",
      customdata: counts.map((_, i) => [edges[i], edges[i + 1]]),
    },
    {
      type: "scatter",
      mode: "lines",
      x: histogram.normal_curve_x,
      y: histogram.normal_curve_y,
      name: curveName,
      line: { color: t.series[1], width: 2 },
      hoverinfo: "skip",
    },
  ];
  const shapes: Partial<Shape>[] = [];
  const annotations: Partial<Layout>["annotations"] = [];
  const xs = [...edges, ...histogram.normal_curve_x];
  const add = (v: number | null | undefined, text: string, dash: "solid" | "dash" | "dot") => {
    if (v == null) return;
    xs.push(v);
    shapes.push({ type: "line", xref: "x", yref: "paper", x0: v, x1: v, y0: 0, y1: 1, line: { color: t.spec, width: 2, dash } });
    annotations.push({ x: v, xref: "x", y: 1, yref: "paper", text: `${text} ${numEs(v)}`, showarrow: false, yanchor: "bottom", font: { size: 11, color: t.spec } });
  };
  add(specs?.lsl, "LSL", "solid");
  add(specs?.usl, "USL", "solid");
  add(specs?.target, "Objetivo", "dash");
  const pad = (Math.max(...xs) - Math.min(...xs)) * 0.04;
  return (
    <PlotlyChart
      title={title}
      description={`${title}. ${counts.length} clases; la curva normal se ajusta a los datos.`}
      data={data}
      fileName={fileName}
      layout={{
        shapes,
        annotations,
        bargap: 0,
        xaxis: axis(t, xTitle, { range: [Math.min(...xs) - pad, Math.max(...xs) + pad] }),
        yaxis: axis(t, "Frecuencia"),
        margin: { l: 60, r: 24, t: 56, b: 70 },
      }}
      table={{
        columns: ["Desde", "Hasta", "Frecuencia"],
        rows: counts.map((c, i) => [edges[i], edges[i + 1], c]),
      }}
    />
  );
}

export function QQChart({ points, title, fileName }: { points: S["QQPoint"][]; title: string; fileName: string }) {
  const t = useChartTheme();
  const n = points.length;
  const a = points[Math.floor(n * 0.25)];
  const b = points[Math.min(n - 1, Math.floor(n * 0.75))];
  // Recta de referencia por el primer y tercer cuartil (solo geometría de la figura).
  const slope = b.theoretical !== a.theoretical ? (b.observed - a.observed) / (b.theoretical - a.theoretical) : 0;
  const x0 = points[0].theoretical;
  const x1 = points[n - 1].theoretical;
  const line = (x: number) => a.observed + slope * (x - a.theoretical);
  return (
    <PlotlyChart
      title={title}
      description="Gráfico cuantil-cuantil: si los puntos siguen la recta, los datos se ajustan a la normal."
      fileName={fileName}
      data={[
        { type: "scatter", mode: "lines", x: [x0, x1], y: [line(x0), line(x1)], name: "Referencia normal", line: { color: t.series[1], width: 2 }, hoverinfo: "skip" },
        {
          type: "scatter",
          mode: "markers",
          x: points.map((p) => p.theoretical),
          y: points.map((p) => p.observed),
          name: "Observaciones",
          marker: { color: t.series[0], size: 6, line: { color: t.surface, width: 1 } },
          hovertemplate: "Teórico %{x:,.3f}<br>Observado %{y:,.3f}<extra></extra>",
        },
      ]}
      layout={{ xaxis: axis(t, "Cuantiles teóricos (normal estándar)"), yaxis: axis(t, "Cuantiles observados"), margin: { l: 64, r: 24, t: 56, b: 70 } }}
      table={{ columns: ["Teórico", "Observado"], rows: points.map((p) => [p.theoretical, p.observed]) }}
    />
  );
}

export function AcfChart({ acf, title, fileName }: { acf: S["Autocorrelation"]; title: string; fileName: string }) {
  const t = useChartTheme();
  const sig = new Set(acf.significant_lags);
  const lo = acf.lags[0] - 0.5;
  const hi = acf.lags[acf.lags.length - 1] + 0.5;
  return (
    <PlotlyChart
      title={title}
      description={`Autocorrelación por rezago con bandas de significancia ±${fmtNum(acf.band, 3)}. Rezagos significativos: ${acf.significant_lags.join(", ") || "ninguno"}.`}
      fileName={fileName}
      data={[
        {
          type: "bar",
          x: acf.lags,
          y: acf.values,
          name: "Autocorrelación",
          marker: {
            color: acf.lags.map((l) => (sig.has(l) ? t.signal : t.series[0])),
            pattern: { shape: acf.lags.map((l) => (sig.has(l) ? "/" : "")) as never, fgcolor: t.surface, size: 6 },
          },
          hovertemplate: "Rezago %{x}<br>r = %{y:,.3f}<extra></extra>",
        },
        { type: "scatter", mode: "markers", x: [null], y: [null], name: "Fuera de la banda (rayado)", marker: { color: t.signal, symbol: "square", size: 10 } },
      ]}
      layout={{
        shapes: [acf.band, -acf.band].map((y) => ({ type: "line", xref: "x", yref: "y", x0: lo, x1: hi, y0: y, y1: y, line: { color: t.limit, width: 1.5, dash: "dash" } })),
        xaxis: axis(t, "Rezago", { dtick: 1, range: [lo, hi] }),
        yaxis: axis(t, "Autocorrelación", { range: [-1, 1] }),
        margin: { l: 64, r: 24, t: 56, b: 70 },
      }}
      table={{
        columns: ["Rezago", "Autocorrelación", "Significativo"],
        rows: acf.lags.map((l, i) => [String(l), acf.values[i], sig.has(l) ? "Sí" : "No"]),
      }}
    />
  );
}

export interface CurveSeries {
  name: string;
  points: S["CurvePoint"][];
  dash?: "solid" | "dash" | "dot";
}

/** Curvas (OC, ARL, AOQ, ATI, ASN): una o varias series sobre el mismo eje. */
export function CurveChart({
  series,
  title,
  fileName,
  xTitle,
  yTitle,
  yRange,
  vlines,
  xRange,
  logY,
}: {
  series: CurveSeries[];
  title: string;
  fileName: string;
  xTitle: string;
  yTitle: string;
  yRange?: [number, number];
  xRange?: [number, number];
  vlines?: { x: number; label: string }[];
  logY?: boolean;
}) {
  const t = useChartTheme();
  const data: Data[] = series.map((s, i) => ({
    type: "scatter",
    mode: "lines",
    name: s.name,
    x: s.points.map((p) => p.x),
    y: s.points.map((p) => p.y),
    line: { color: t.series[i % t.series.length], width: 2.5, dash: s.dash ?? (i % 2 ? "dash" : "solid") },
    hovertemplate: `${xTitle}: %{x:,.4f}<br>${yTitle}: %{y:,.4f}<extra>${s.name}</extra>`,
  }));
  return (
    <PlotlyChart
      title={title}
      description={`${title}. Eje x: ${xTitle}; eje y: ${yTitle}.`}
      fileName={fileName}
      data={data}
      layout={{
        shapes: (vlines ?? []).map((v) => ({ type: "line", xref: "x", yref: "paper", x0: v.x, x1: v.x, y0: 0, y1: 1, line: { color: t.muted, width: 1, dash: "dot" } })),
        annotations: (vlines ?? []).map((v) => ({ x: v.x, xref: "x", y: 1, yref: "paper", text: v.label, showarrow: false, yanchor: "bottom", font: { size: 11, color: t.muted } })),
        xaxis: axis(t, xTitle, xRange ? { range: xRange } : {}),
        yaxis: axis(t, yTitle, { ...(yRange ? { range: yRange } : {}), ...(logY ? { type: "log" } : {}) }),
        margin: { l: 64, r: 24, t: 56, b: 80 },
      }}
      table={{
        columns: [xTitle, ...series.map((s) => s.name)],
        rows: series[0].points.map((p, i) => [p.x, ...series.map((s) => s.points[i]?.y ?? null)]),
      }}
    />
  );
}

/** Compromiso entre rapidez de detección (ATS1) y carga muestral (n/h) de varios diseños. */
export function TradeoffChart({ rows, title, fileName }: { rows: S["CompareRow"][]; title: string; fileName: string }) {
  const t = useChartTheme();
  const text = rows.map((r) => `n=${r.n}, L=${numEs(r.limit_width)}, h=${numEs(r.sampling_interval)}`);
  return (
    <PlotlyChart
      title={title}
      description="Cada punto es un diseño: a la izquierda inspecciona menos, abajo detecta antes."
      fileName={fileName}
      data={[
        {
          type: "scatter",
          mode: rows.length <= 8 ? "text+markers" : "markers",
          x: rows.map((r) => r.sampling_load),
          y: rows.map((r) => r.ats1),
          text,
          textposition: "top center",
          textfont: { size: 10, color: t.muted },
          name: "Diseños",
          marker: { color: t.series[0], size: 10, line: { color: t.surface, width: 2 } },
          hovertemplate: "%{text}<br>Carga %{x:,.2f} u/h<br>ATS1 %{y:,.2f} h<extra></extra>",
        },
      ]}
      layout={{
        xaxis: axis(t, "Carga muestral n/h (unidades por hora)"),
        yaxis: axis(t, "ATS1 (horas hasta detectar)"),
        showlegend: false,
        margin: { l: 64, r: 24, t: 56, b: 60 },
      }}
      table={{
        columns: ["n", "L", "h", "Carga n/h", "ATS1"],
        rows: rows.map((r) => [r.n, r.limit_width, r.sampling_interval, r.sampling_load, r.ats1]),
      }}
    />
  );
}

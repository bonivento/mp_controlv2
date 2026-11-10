"use client";

import type { Annotation, Data, Layout } from "plotly.js";
import type { components } from "@/lib/api-types";
import { PlotlyChart, type PlotClick } from "./PlotlyChart";
import { useChartTheme } from "./theme";

type Series = components["schemas"]["ChartSeries"];

const fmt = (x: number, d = 4) => x.toLocaleString("es-CO", { minimumFractionDigits: 0, maximumFractionDigits: d });

/**
 * Gráfico de control común a todos los tipos (X-barra, R, S, I, MR, p, np, c, u).
 * Muestra línea central, límites, puntos con señal (rombo rojo con la regla escrita)
 * y puntos excluidos (cruz gris), de modo que el color no es lo único que distingue.
 * No calcula nada: dibuja lo que entrega la API.
 */
export function ControlChart({
  series,
  phase,
  onPointClick,
  clickableIndices,
  fileName,
  titleSuffix,
}: {
  series: Series;
  phase: "I" | "II";
  /** Recibe el índice del subgrupo (base 0) al hacer clic en un punto permitido. */
  onPointClick?: (index: number) => void;
  /** Índices en los que el clic hace algo (p. ej. puntos con señal en Fase I). */
  clickableIndices?: number[];
  fileName: string;
  titleSuffix?: string;
}) {
  const t = useChartTheme();
  const n = series.values.length;
  const idx = Array.from({ length: n }, (_, i) => i);
  const excluded = new Set(series.excluded);
  const signalRules = new Map<number, string[]>();
  for (const v of series.violations) {
    if (excluded.has(v.index) && series.name !== "mr") continue;
    signalRules.set(v.index, [...(signalRules.get(v.index) ?? []), v.rule]);
  }
  // En MR el índice de la señal es el del subgrupo (posición + 1); se traduce al punto del panel.
  const offset = series.name === "mr" ? 1 : 0;
  const panelSignals = new Map<number, string[]>();
  signalRules.forEach((rules, i) => panelSignals.set(i - offset, rules));
  const sigIdx = idx.filter((i) => panelSignals.has(i) && !excluded.has(i));
  const exIdx = idx.filter((i) => excluded.has(i));

  const varying = new Set(series.ucl.map((x) => x.toFixed(9))).size > 1;
  const shape = varying ? "hv" : "linear";
  const limitDash = phase === "I" ? "dash" : "solid";
  const limitWidth = phase === "I" ? 1.5 : 2.2;
  const limitName = phase === "I" ? "Límites de prueba" : "Límites congelados";
  const lastI = n - 1;
  const clickable = new Set(clickableIndices ?? []);

  const common = { x: series.labels, type: "scatter" as const };
  const data: Data[] = [
    {
      ...common,
      y: series.ucl,
      mode: "lines",
      name: limitName,
      line: { color: t.limit, width: limitWidth, dash: limitDash, shape },
      hovertemplate: "LCS %{y:,.4f}<extra></extra>",
    },
    {
      ...common,
      y: series.lcl,
      mode: "lines",
      name: "LCI",
      showlegend: false,
      line: { color: t.limit, width: limitWidth, dash: limitDash, shape },
      hovertemplate: "LCI %{y:,.4f}<extra></extra>",
    },
    {
      ...common,
      y: series.center,
      mode: "lines",
      name: "Línea central",
      line: { color: t.muted, width: 1, shape },
      hovertemplate: "LC %{y:,.4f}<extra></extra>",
    },
    {
      ...common,
      y: series.values,
      customdata: idx,
      mode: "lines+markers",
      name: "Valor del subgrupo",
      line: { color: t.series[0], width: 1.5 },
      marker: { color: t.series[0], size: 7, line: { color: t.surface, width: 1.5 } },
      hovertemplate: "Subgrupo %{x}<br>Valor %{y:,.4f}<extra></extra>",
    },
  ];
  if (sigIdx.length)
    data.push({
      x: sigIdx.map((i) => series.labels[i]),
      y: sigIdx.map((i) => series.values[i]),
      customdata: sigIdx,
      type: "scatter",
      mode: "text+markers",
      name: "Fuera de control (señal)",
      text: sigIdx.map((i) => panelSignals.get(i)!.join(", ")),
      textposition: sigIdx.map((i) => (series.values[i] >= series.center[i] ? "top center" : "bottom center")),
      textfont: { color: t.signal, size: 11 },
      marker: { symbol: "diamond", size: 12, color: t.signal, line: { color: t.surface, width: 2 } },
      hovertemplate: sigIdx.map((i) => `Subgrupo %{x}<br>Valor %{y:,.4f}<br>Señal: ${panelSignals.get(i)!.join(", ")}<extra></extra>`),
    });
  if (exIdx.length)
    data.push({
      x: exIdx.map((i) => series.labels[i]),
      y: exIdx.map((i) => series.values[i]),
      customdata: exIdx,
      type: "scatter",
      mode: "markers",
      name: "Excluido (causa asignable)",
      marker: { symbol: "x-open", size: 13, color: t.excluded, line: { color: t.excluded, width: 2.5 } },
      hovertemplate: "Subgrupo %{x}<br>Valor %{y:,.4f}<br>Excluido del cálculo de límites<extra></extra>",
    });

  const label = (text: string, y: number): Partial<Annotation> => ({
    x: 1,
    xref: "paper",
    y,
    yref: "y",
    xanchor: "left",
    text,
    showarrow: false,
    font: { size: 11, color: t.muted },
  });
  const layout: Partial<Layout> = {
    annotations: [
      label(`LCS ${fmt(series.ucl[lastI])}`, series.ucl[lastI]),
      label(`LC ${fmt(series.center[lastI])}`, series.center[lastI]),
      label(`LCI ${fmt(series.lcl[lastI])}`, series.lcl[lastI]),
    ],
    xaxis: { type: "category", title: { text: "Subgrupo" }, gridcolor: t.grid, linecolor: t.grid, tickfont: { color: t.muted }, automargin: true },
    yaxis: { gridcolor: t.grid, linecolor: t.grid, tickfont: { color: t.muted }, automargin: true, tickformat: ",.4~f" },
    margin: { l: 64, r: 96, t: 48, b: 70 },
  };

  const faseText = phase === "I" ? "Fase I · límites de prueba" : "Fase II · límites congelados";
  const sigText = sigIdx.length
    ? `${sigIdx.length} punto(s) con señal: ${sigIdx.map((i) => series.labels[i]).join(", ")}.`
    : "Sin puntos con señal.";

  return (
    <PlotlyChart
      title={`${series.title} — ${faseText}${titleSuffix ? ` ${titleSuffix}` : ""}`}
      description={`${series.title}, ${faseText}. ${sigText}${exIdx.length ? ` ${exIdx.length} punto(s) excluido(s).` : ""}`}
      data={data}
      layout={layout}
      fileName={fileName}
      height={360}
      onPointClick={
        onPointClick
          ? (p: PlotClick) => {
              const i = typeof p.customdata === "number" ? p.customdata : null;
              if (i != null && clickable.has(i + offset)) onPointClick(i + offset);
            }
          : undefined
      }
      table={{
        columns: ["Subgrupo", "Valor", "LCI", "Línea central", "LCS", "Estado"],
        rows: idx.map((i) => [
          series.labels[i],
          series.values[i],
          series.lcl[i],
          series.center[i],
          series.ucl[i],
          excluded.has(i) ? "Excluido" : panelSignals.has(i) ? `Señal ${panelSignals.get(i)!.join(", ")}` : "En control",
        ]),
      }}
    />
  );
}

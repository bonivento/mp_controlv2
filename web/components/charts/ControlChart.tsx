"use client";

import type { Annotation, Data, Layout } from "plotly.js";
import type { components } from "@/lib/api-types";
import { PlotlyChart, type PlotClick } from "./PlotlyChart";
import { useChartTheme, useNarrow } from "./theme";

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
  const narrow = useNarrow();
  // Todos los índices de la API (violations, excluded, indices) son de SUBGRUPO. Cada
  // elemento de `values` se ubica con `indices`; así el panel MR, que empieza en el
  // segundo subgrupo, queda alineado sin suponer ningún desplazamiento.
  const n = series.values.length;
  const pos = Array.from({ length: n }, (_, k) => k);
  const subOf = (k: number) => series.indices[k] ?? k;
  const excluded = new Set(series.excluded);
  const rulesBySub = new Map<number, string[]>();
  for (const v of series.violations) {
    if (excluded.has(v.index)) continue;
    rulesBySub.set(v.index, [...(rulesBySub.get(v.index) ?? []), v.rule]);
  }
  const sigPos = pos.filter((k) => rulesBySub.has(subOf(k)));
  const exPos = pos.filter((k) => excluded.has(subOf(k)));
  const rulesAt = (k: number) => rulesBySub.get(subOf(k)) ?? [];
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
      customdata: pos.map(subOf),
      mode: "lines+markers",
      name: "Valor del subgrupo",
      line: { color: t.series[0], width: 1.5 },
      marker: { color: t.series[0], size: 7, line: { color: t.surface, width: 1.5 } },
      hovertemplate: "Subgrupo %{x}<br>Valor %{y:,.4f}<extra></extra>",
    },
  ];
  if (sigPos.length)
    data.push({
      x: sigPos.map((k) => series.labels[k]),
      y: sigPos.map((k) => series.values[k]),
      customdata: sigPos.map(subOf),
      type: "scatter",
      mode: "text+markers",
      name: "Fuera de control (señal)",
      text: sigPos.map((k) => rulesAt(k).join(", ")),
      textposition: sigPos.map((k) => (series.values[k] >= series.center[k] ? "top center" : "bottom center")),
      textfont: { color: t.signal, size: 11 },
      marker: { symbol: "diamond", size: 12, color: t.signal, line: { color: t.surface, width: 2 } },
      hovertemplate: sigPos.map((k) => `Subgrupo %{x}<br>Valor %{y:,.4f}<br>Señal: ${rulesAt(k).join(", ")}<extra></extra>`),
    });
  if (exPos.length)
    data.push({
      x: exPos.map((k) => series.labels[k]),
      y: exPos.map((k) => series.values[k]),
      customdata: exPos.map(subOf),
      type: "scatter",
      mode: "markers",
      name: "Excluido (causa asignable)",
      marker: { symbol: "x-open", size: 13, color: t.excluded, line: { color: t.excluded, width: 2.5 } },
      hovertemplate: "Subgrupo %{x}<br>Valor %{y:,.4f}<br>Excluido del cálculo de límites<extra></extra>",
    });

  const yAll = [...series.values, ...series.ucl, ...series.lcl].filter((v) => Number.isFinite(v));
  const yLo = Math.min(...yAll);
  const yHi = Math.max(...yAll);
  const yPad = (yHi - yLo || Math.abs(yHi) || 1) * 0.14;
  const yRange: [number, number] = [yLo - yPad, yHi + yPad];

  // En escritorio los valores de los límites se rotulan a la derecha; en móvil no hay ancho
  // para eso y van en la nota bajo la figura.
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
    annotations: narrow
      ? []
      : [
      label(`LCS ${fmt(series.ucl[lastI])}`, series.ucl[lastI]),
      label(`LC ${fmt(series.center[lastI])}`, series.center[lastI]),
      label(`LCI ${fmt(series.lcl[lastI])}`, series.lcl[lastI]),
        ],
    xaxis: { type: "category", title: { text: "Subgrupo" }, gridcolor: t.grid, linecolor: t.grid, tickfont: { color: t.muted }, automargin: true },
    // Holgura arriba y abajo para que los rótulos de las señales no queden contra el borde (solo geometría).
    yaxis: { gridcolor: t.grid, linecolor: t.grid, tickfont: { color: t.muted }, automargin: true, tickformat: ",.4~f", range: yRange },
    margin: narrow ? { l: 48, r: 10, t: 40, b: 96 } : { l: 64, r: 96, t: 48, b: 70 },
    ...(narrow ? { legend: { orientation: "h" as const, y: -0.3, x: 0, font: { size: 10, color: t.muted } } } : {}),
  };

  const faseText = phase === "I" ? "Fase I · límites de prueba" : "Fase II · límites congelados";
  const sigText = sigPos.length
    ? `${sigPos.length} punto(s) con señal: ${sigPos.map((k) => series.labels[k]).join(", ")}.`
    : "Sin puntos con señal.";

  const skipped = series.rules_skipped;
  const note = (
    <>
      {narrow && (
        <p className="num">
          LCS {fmt(series.ucl[lastI])} · LC {fmt(series.center[lastI])} · LCI {fmt(series.lcl[lastI])}
        </p>
      )}
      <p>
        Reglas evaluadas: {series.rules_applied.length ? series.rules_applied.join(", ") : "ninguna"}.
      </p>
      {skipped.length > 0 && (
        <>
          <p className="mt-0.5">Reglas pedidas que no se evaluaron en este gráfico:</p>
          <ul className="list-disc pl-5" aria-label="Reglas no evaluadas en este gráfico">
            {skipped.map((r) => (
              <li key={r.rule}>
                <strong>{r.rule}:</strong> {r.reason.replace(new RegExp(`^${r.rule} no se aplica: `), "")}
              </li>
            ))}
          </ul>
        </>
      )}
    </>
  );

  return (
    <PlotlyChart
      title={`${series.title} — ${faseText}${titleSuffix ? ` ${titleSuffix}` : ""}`}
      description={`${series.title}, ${faseText}. ${sigText}${exPos.length ? ` ${exPos.length} punto(s) excluido(s).` : ""}`}
      data={data}
      layout={layout}
      fileName={fileName}
      height={360}
      note={note}
      onPointClick={
        onPointClick
          ? (p: PlotClick) => {
              const i = typeof p.customdata === "number" ? p.customdata : null;
              if (i != null && clickable.has(i)) onPointClick(i);
            }
          : undefined
      }
      table={{
        columns: ["Subgrupo", "Valor", "LCI", "Línea central", "LCS", "Estado"],
        rows: pos.map((k) => [
          series.labels[k],
          series.values[k],
          series.lcl[k],
          series.center[k],
          series.ucl[k],
          excluded.has(subOf(k)) ? "Excluido" : rulesBySub.has(subOf(k)) ? `Señal ${rulesAt(k).join(", ")}` : "En control",
        ]),
      }}
    />
  );
}

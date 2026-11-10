"use client";

import dynamic from "next/dynamic";
import { useCallback, useId, useRef, useState } from "react";
import type { Config, Data, Layout } from "plotly.js";
import { Button, Table, Td, Th } from "@/components/ui";
import { useChartTheme } from "./theme";

const Plot = dynamic(() => import("./plotly-plot").then((m) => m.Plot), {
  ssr: false,
  loading: () => (
    <div role="status" className="flex h-64 items-center justify-center text-sm text-muted">
      Cargando gráfico…
    </div>
  ),
});

export interface DataTable {
  columns: string[];
  rows: (string | number | null)[][];
}

export interface PlotClick {
  curveNumber: number;
  pointNumber: number;
  customdata?: unknown;
}

/**
 * Envoltura común de Plotly: tema claro/oscuro, título dentro de la figura (sale en el
 * PNG), descarga en PNG, y una tabla de datos como alternativa accesible al gráfico.
 */
export function PlotlyChart({
  title,
  description,
  data,
  layout,
  height = 380,
  fileName,
  table,
  onPointClick,
  footer,
}: {
  title: string;
  /** Texto alternativo breve de lo que muestra la figura. */
  description?: string;
  data: Data[];
  layout?: Partial<Layout>;
  height?: number;
  fileName: string;
  table?: DataTable;
  onPointClick?: (p: PlotClick) => void;
  footer?: React.ReactNode;
}) {
  const t = useChartTheme();
  const gd = useRef<HTMLElement | null>(null);
  const [showTable, setShowTable] = useState(false);
  const [exporting, setExporting] = useState(false);
  const tableId = useId();

  const fullLayout: Partial<Layout> = {
    title: { text: title, x: 0, xanchor: "left", font: { size: 14, color: t.ink } },
    paper_bgcolor: t.surface,
    plot_bgcolor: t.surface,
    font: { family: "Geist, system-ui, sans-serif", size: 12, color: t.ink },
    margin: { l: 60, r: 80, t: 48, b: 56 },
    separators: ",.",
    hovermode: "closest",
    legend: { orientation: "h", y: -0.22, x: 0, font: { size: 11, color: t.muted } },
    xaxis: { gridcolor: t.grid, linecolor: t.grid, zerolinecolor: t.grid, tickfont: { color: t.muted }, automargin: true },
    yaxis: { gridcolor: t.grid, linecolor: t.grid, zerolinecolor: t.grid, tickfont: { color: t.muted }, automargin: true },
    ...layout,
  };
  const config: Partial<Config> = {
    displaylogo: false,
    responsive: true,
    displayModeBar: "hover",
    modeBarButtonsToRemove: ["lasso2d", "select2d", "toImage"],
  };

  const download = useCallback(async () => {
    if (!gd.current) return;
    setExporting(true);
    try {
      const { plotly } = await import("./plotly-plot");
      await plotly.downloadImage(gd.current, { format: "png", filename: fileName, width: 1200, height: Math.max(500, height * 1.4), scale: 2 });
    } finally {
      setExporting(false);
    }
  }, [fileName, height]);

  return (
    <figure className="print-break m-0" aria-label={description ?? title}>
      <div className="rounded-md border border-line">
        <Plot
          data={data}
          layout={fullLayout}
          config={config}
          style={{ width: "100%", height }}
          useResizeHandler
          onInitialized={(_f, g) => {
            gd.current = g;
          }}
          onUpdate={(_f, g) => {
            gd.current = g;
          }}
          onClick={(e: { points: PlotClick[] }) => {
            const p = e.points?.[0];
            if (p && onPointClick) onPointClick(p);
          }}
        />
      </div>
      {description && <p className="sr-only">{description}</p>}
      <figcaption className="no-print mt-2 flex flex-wrap items-center gap-2">
        <Button onClick={download} loading={exporting} aria-label={`Descargar PNG: ${title}`}>
          Descargar PNG
        </Button>
        {table && (
          <Button onClick={() => setShowTable((v) => !v)} aria-expanded={showTable} aria-controls={tableId}>
            {showTable ? "Ocultar tabla de datos" : "Ver tabla de datos"}
          </Button>
        )}
        {footer}
      </figcaption>
      {table && showTable && (
        <div id={tableId} className="mt-2 max-h-72 overflow-auto">
          <Table caption={`Datos de: ${title}`}>
            <thead>
              <tr>
                {table.columns.map((c) => (
                  <Th key={c}>{c}</Th>
                ))}
              </tr>
            </thead>
            <tbody>
              {table.rows.map((r, i) => (
                <tr key={i}>
                  {r.map((c, j) => (
                    <Td key={j}>{typeof c === "number" ? c.toLocaleString("es-CO", { maximumFractionDigits: 4 }) : (c ?? "—")}</Td>
                  ))}
                </tr>
              ))}
            </tbody>
          </Table>
        </div>
      )}
    </figure>
  );
}

"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useId, useRef, useState } from "react";
import type { Config, Data, Layout } from "plotly.js";
import { Button, Table, Td, Th } from "@/components/ui";
import { useChartMode, useChartTheme, useNarrow } from "./theme";

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
  note,
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
  /** Texto bajo la figura que también sale al imprimir (reglas evaluadas, nota APA…). */
  note?: React.ReactNode;
}) {
  const t = useChartTheme();
  const { titleInFigure: titleWanted } = useChartMode();
  // En móvil el título largo no cabe dentro de la figura: va como texto que se ajusta, encima.
  const narrow = useNarrow();
  const titleInFigure = titleWanted && !narrow;
  const gd = useRef<HTMLElement | null>(null);
  const [showTable, setShowTable] = useState(false);
  const [exporting, setExporting] = useState(false);
  const tableId = useId();

  const titleLayout = { text: title, x: 0, xanchor: "left" as const, font: { size: 14, color: t.ink } };
  const fullLayout: Partial<Layout> = {
    ...(titleInFigure ? { title: titleLayout } : {}),
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
  // Sin título dentro de la figura (reporte) el margen superior se reduce; el PNG lo recupera.
  if (!titleInFigure) fullLayout.margin = { ...fullLayout.margin, t: Math.min(fullLayout.margin?.t ?? 30, 32) };
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
      const g = gd.current as unknown as { data: Data[]; layout: Partial<Layout> };
      const h = Math.max(500, Math.round(height * 1.4));
      // El PNG siempre lleva su título dentro de la figura, aunque en pantalla no se vea.
      const figure = {
        data: g.data,
        layout: { ...g.layout, title: titleLayout, margin: { ...g.layout.margin, t: 56 }, width: 1200, height: h },
      };
      const url = await plotly.toImage(figure, { format: "png", width: 1200, height: h, scale: 2 });
      const link = document.createElement("a");
      link.href = url;
      link.download = `${fileName}.png`;
      link.click();
    } finally {
      setExporting(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fileName, height, title, t.ink]);

  // Al imprimir el contenedor cambia de ancho: se pide a Plotly que redibuje a la medida de la página.
  useEffect(() => {
    const fit = () => {
      const g = gd.current;
      if (!g) return;
      void import("./plotly-plot").then(({ plotly }) => plotly.Plots.resize(g));
    };
    window.addEventListener("beforeprint", fit);
    window.addEventListener("afterprint", fit);
    return () => {
      window.removeEventListener("beforeprint", fit);
      window.removeEventListener("afterprint", fit);
    };
  }, []);

  return (
    <figure className="print-break m-0" aria-label={description ?? title}>
      {titleWanted && narrow && <p className="mb-1 text-sm font-medium">{title}</p>}
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
      {note && <div className="mt-1.5 text-xs text-muted">{note}</div>}
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

"use client";

import { Component, type ReactNode } from "react";
import { ChartModeContext } from "@/components/charts/theme";
import { Alert, fmtNum } from "@/components/ui";
import type { components } from "@/lib/api-types";
import type { Analysis, Dataset, Study } from "@/lib/db";
import { MODULE_LABEL, fmtDateTime } from "@/lib/labels";
import { ApaFigure, ApaTable, type Block } from "./apa";
import { buildBlocks, paramsLine, type SectionCtx } from "./blocks";

type Interp = components["schemas"]["Interpretation"];

/** Un fallo al dibujar un análisis no debe llevarse el reporte entero. */
class SectionBoundary extends Component<{ title: string; children: ReactNode }, { error: string | null }> {
  state = { error: null as string | null };
  static getDerivedStateFromError(e: unknown) {
    return { error: e instanceof Error ? e.message : "Error desconocido" };
  }
  render() {
    if (this.state.error)
      return (
        <Alert tone="error" title={`No se pudo dibujar «${this.props.title}»`}>
          El resultado guardado no tiene la forma esperada ({this.state.error}). Vuelve a ejecutar el análisis y guárdalo de nuevo.
        </Alert>
      );
    return this.props.children;
  }
}

interface Section {
  ctx: SectionCtx;
  number: number;
  blocks: { block: Block; number: number }[];
}

/** Numera correlativamente tablas y figuras (APA: cada tipo con su propia cuenta). */
function numberSections(items: SectionCtx[]): { sections: Section[]; error: string | null } {
  let t = 0;
  let f = 0;
  const failed: string[] = [];
  const sections = items.map((ctx, i): Section => {
    let blocks: Block[] = [];
    try {
      blocks = buildBlocks(ctx);
    } catch {
      failed.push(ctx.analysis.title);
    }
    return { ctx, number: i + 1, blocks: blocks.map((block) => ({ block, number: block.kind === "table" ? ++t : ++f })) };
  });
  return { sections, error: failed.length ? `No se pudieron leer: ${failed.join("; ")}.` : null };
}

function InterpretationText({ interp }: { interp?: Interp }) {
  if (!interp) return <p className="text-sm">Este análisis no trae interpretación.</p>;
  return (
    <div className="text-sm">
      <p className="font-medium">{interp.summary}</p>
      {interp.findings.length > 0 && (
        <ul className="mt-2 list-disc space-y-1 pl-5">
          {interp.findings.map((f, k) => (
            <li key={k}>{f}</li>
          ))}
        </ul>
      )}
      {interp.warnings.length > 0 && (
        <div className="report-warnings mt-2">
          <p className="font-semibold">Advertencias</p>
          <ul className="list-disc space-y-1 pl-5">
            {interp.warnings.map((w, k) => (
              <li key={k}>{w}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

/**
 * Pie de página repetido en cada hoja impresa, con las cajas de margen de @page
 * (Chrome y Edge). Donde no se soportan simplemente no sale; por eso la marca de
 * «datos sintéticos» también va en cada sección.
 */
function PageFooterStyle({ text }: { text: string }) {
  const css = `@media print { @page { @bottom-center { content: ${JSON.stringify(text)}; font-size: 8pt; color: #333; } } }`.replace(/</g, "\\3C ");
  return <style dangerouslySetInnerHTML={{ __html: css }} />;
}

const studyRows = (s: Study): [string, string][] => [
  ["Empresa", s.company ?? "—"],
  ["Proceso", s.process ?? "—"],
  ["Producto", s.product ?? "—"],
  ["Característica de calidad", s.characteristic ?? "—"],
  ["Unidad de medida", s.unit ?? "—"],
  ["Tipo de dato", s.data_type === "variable" ? "Variable (medición continua)" : "Atributo (conteo)"],
  ["Límite inferior de especificación (LSL)", s.lsl != null ? fmtNum(s.lsl, 3) : "—"],
  ["Límite superior de especificación (USL)", s.usl != null ? fmtNum(s.usl, 3) : "—"],
  ["Valor objetivo", s.target != null ? fmtNum(s.target, 3) : "—"],
];

/**
 * Documento del reporte (módulo 8). Reúne los análisis marcados con `in_report`
 * tal como se guardaron: no vuelve a calcular nada. Siempre en tema claro para
 * que el PDF y los PNG salgan igual sin importar el modo del sistema.
 */
export function ReportDocument({ study, analyses, datasets }: { study: Study; analyses: Analysis[]; datasets: Dataset[] }) {
  const items: SectionCtx[] = analyses.map((analysis) => ({
    study,
    analysis,
    dataset: datasets.find((d) => d.id === analysis.dataset_id) ?? null,
  }));
  const { sections, error } = numberSections(items);
  const allBlocks = sections.flatMap((s) => s.blocks);
  const generated = fmtDateTime(new Date().toISOString());

  return (
    <ChartModeContext value={{ forceLight: true, titleInFigure: false }}>
      <article className="report-sheet" aria-label={`Reporte del estudio ${study.name}`}>
        {study.is_synthetic && (
          <div className="report-synthetic" role="note">
            <strong>Datos sintéticos.</strong> Este reporte se generó con datos de ejemplo creados para probar el software; no provienen de una empresa real
            y sus conclusiones no describen ningún proceso verdadero.
          </div>
        )}

        <header className="report-cover">
          <p className="text-xs uppercase tracking-widest">Control estadístico de procesos</p>
          <h1 className="mt-1 text-2xl font-bold">Reporte del estudio: {study.name}</h1>
          <p className="mt-1 text-sm">
            Generado el {generated} · {sections.length} análisis
          </p>
          <h2 className="mb-2 mt-5 text-base font-semibold">Datos del estudio</h2>
          <dl className="report-dl text-sm">
            {studyRows(study).map(([k, v]) => (
              <div key={k}>
                <dt>{k}</dt>
                <dd>{v}</dd>
              </div>
            ))}
            {study.notes && (
              <div>
                <dt>Notas</dt>
                <dd>{study.notes}</dd>
              </div>
            )}
          </dl>

          <h2 className="mb-1 mt-5 text-base font-semibold">Contenido</h2>
          <ol className="list-decimal pl-5 text-sm">
            {sections.map((s) => (
              <li key={s.ctx.analysis.id}>
                <a href={`#analisis-${s.number}`}>{s.ctx.analysis.title}</a> <span className="text-xs">({MODULE_LABEL[s.ctx.analysis.module]})</span>
              </li>
            ))}
          </ol>
          {allBlocks.length > 0 && (
            <>
              <h2 className="mb-1 mt-4 text-base font-semibold">Lista de tablas y figuras</h2>
              <ul className="report-list text-sm">
                {allBlocks.map(({ block, number }) => (
                  <li key={`${block.kind}-${number}`}>
                    {block.kind === "table" ? "Tabla" : "Figura"} {number}. {block.title}
                  </li>
                ))}
              </ul>
            </>
          )}
          {error && <Alert tone="warn" className="no-print mt-3">{error}</Alert>}
        </header>

        {sections.map((s) => {
          const a = s.ctx.analysis;
          const line = paramsLine(s.ctx);
          const interp = (a.result as { interpretation?: Interp }).interpretation;
          return (
            <section key={a.id} id={`analisis-${s.number}`} className="report-section" aria-labelledby={`h-${a.id}`}>
              <h2 id={`h-${a.id}`} className="text-lg font-bold">
                {s.number}. {a.title}
              </h2>
              <p className="mb-1 text-xs">
                {MODULE_LABEL[a.module]} · guardado el {fmtDateTime(a.created_at)}
                {study.is_synthetic ? " · Datos sintéticos" : ""}
              </p>
              {line && <p className="mb-3 text-xs">{line}</p>}
              <SectionBoundary title={a.title}>
                {s.blocks.map(({ block, number }) =>
                  block.kind === "table" ? <ApaTable key={`t${number}`} number={number} block={block} /> : <ApaFigure key={`f${number}`} number={number} block={block} />,
                )}
              </SectionBoundary>
              <h3 className="mb-1 mt-4 text-sm font-bold">Interpretación</h3>
              <InterpretationText interp={interp} />
            </section>
          );
        })}

        {sections.length > 1 && (
          <section className="report-section" aria-labelledby="h-conclusiones">
            <h2 id="h-conclusiones" className="text-lg font-bold">
              Conclusiones preliminares
            </h2>
            <p className="mb-2 text-xs">Resumen de la interpretación automática de cada análisis; son un punto de partida, no sustituyen el juicio del ingeniero.</p>
            <ol className="list-decimal space-y-1.5 pl-5 text-sm">
              {sections.map((s) => (
                <li key={s.ctx.analysis.id}>
                  <strong>{s.ctx.analysis.title}.</strong> {(s.ctx.analysis.result as { interpretation?: Interp }).interpretation?.summary ?? "Sin interpretación."}
                </li>
              ))}
            </ol>
          </section>
        )}

        <PageFooterStyle text={`${study.name}${study.is_synthetic ? " · DATOS SINTÉTICOS" : ""}`} />
      </article>
    </ChartModeContext>
  );
}


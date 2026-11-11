"use client";

// Piezas de presentación del reporte al estilo APA (7.ª ed.): el número va en
// negrita y el título en cursiva sobre la tabla o figura; la nota, debajo.
// Solo dan formato; no calculan nada.

import type { ReactNode } from "react";

export type Cell = ReactNode;

export interface Block {
  kind: "table" | "figure";
  title: string;
  /** Texto de la nota general (sin el rótulo «Nota.», que se añade solo). */
  note?: ReactNode;
  node: ReactNode;
}

export function ApaCaption({ label, number, title }: { label: "Tabla" | "Figura"; number: number; title: string }) {
  return (
    <div className="mb-1.5 break-after-avoid">
      <p className="text-sm font-bold">
        {label} {number}
      </p>
      <p className="text-sm italic">{title}</p>
    </div>
  );
}

export function ApaNote({ children }: { children: ReactNode }) {
  return (
    <p className="mt-1.5 text-xs">
      <em>Nota.</em> {children}
    </p>
  );
}

/** Tabla con solo reglas horizontales (sin rejilla vertical), como pide APA. */
export function RTable({
  columns,
  rows,
  caption,
  numeric = true,
}: {
  columns: string[];
  rows: Cell[][];
  caption: string;
  /** Alinea a la derecha las columnas distintas de la primera. */
  numeric?: boolean;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="apa-table num w-full text-sm">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr>
            {columns.map((c, j) => (
              <th key={j} scope="col" className={numeric && j > 0 ? "text-right" : "text-left"}>
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              {r.map((c, j) => (
                <td key={j} className={numeric && j > 0 ? "text-right" : "text-left"}>
                  {c}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Lista de pares «rótulo, valor» como tabla de dos columnas. */
export function KeyValueTable({ rows, caption, head = ["Concepto", "Valor"] }: { rows: [string, Cell][]; caption: string; head?: [string, string] }) {
  return <RTable columns={head} rows={rows} caption={caption} />;
}

export function ApaTable({ number, block }: { number: number; block: Block }) {
  return (
    <div className="report-block mb-5">
      <ApaCaption label="Tabla" number={number} title={block.title} />
      {block.node}
      {block.note && <ApaNote>{block.note}</ApaNote>}
    </div>
  );
}

export function ApaFigure({ number, block }: { number: number; block: Block }) {
  return (
    <div className="report-block report-figure mb-5">
      <ApaCaption label="Figura" number={number} title={block.title} />
      {block.node}
      {block.note && <ApaNote>{block.note}</ApaNote>}
    </div>
  );
}

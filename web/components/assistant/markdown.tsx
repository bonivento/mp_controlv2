"use client";

import { Fragment, memo, type ReactNode } from "react";
import { parseMarkdown, type Block, type Inline } from "@/lib/assistant-markdown";

// Pinta el árbol de lib/assistant-markdown.ts con elementos de React. Nada del texto del modelo
// se inserta como HTML: React escapa todo lo que se pasa como hijo.

function renderInline(nodes: Inline[]): ReactNode {
  return nodes.map((n, i) => {
    switch (n.t) {
      case "text":
        return <Fragment key={i}>{n.text}</Fragment>;
      case "br":
        return <br key={i} />;
      case "strong":
        return <strong key={i}>{renderInline(n.children)}</strong>;
      case "em":
        return <em key={i}>{renderInline(n.children)}</em>;
      case "code":
        return (
          <code key={i} className="rounded bg-surface px-1 py-0.5 font-mono text-[0.85em] [overflow-wrap:anywhere]">
            {n.text}
          </code>
        );
      case "link":
        return (
          <a key={i} href={n.href} target="_blank" rel="noopener noreferrer nofollow" className="text-brand-text underline underline-offset-2">
            {renderInline(n.children)}
          </a>
        );
    }
  });
}

const ALIGN = { left: "text-left", center: "text-center", right: "text-right" } as const;

function renderBlocks(blocks: Block[]): ReactNode {
  return blocks.map((b, i) => {
    switch (b.t) {
      case "p":
        return <p key={i}>{renderInline(b.inline)}</p>;
      case "heading":
        // Se pintan como énfasis y no como encabezados de la página: el panel no debe alterar el esquema de títulos.
        return (
          <p key={i} className="font-semibold">
            {renderInline(b.inline)}
          </p>
        );
      case "list": {
        const items = b.items.map((it, k) => (
          <li key={k}>
            {renderInline(it.inline)}
            {it.children.length > 0 && <div className="mt-1 flex flex-col gap-1">{renderBlocks(it.children)}</div>}
          </li>
        ));
        return b.ordered ? (
          <ol key={i} start={b.start} className="list-decimal space-y-1 pl-5">
            {items}
          </ol>
        ) : (
          <ul key={i} className="list-disc space-y-1 pl-5">
            {items}
          </ul>
        );
      }
      case "code":
        return (
          <pre key={i} tabIndex={0} aria-label="Bloque de código" className="overflow-x-auto rounded-md bg-surface p-2.5 font-mono text-xs leading-relaxed">
            <code>{b.text}</code>
          </pre>
        );
      case "quote":
        return (
          <blockquote key={i} className="flex flex-col gap-1 border-l-[3px] border-accent pl-3 text-muted">
            {renderBlocks(b.blocks)}
          </blockquote>
        );
      case "hr":
        return <hr key={i} className="border-line" />;
      case "table":
        return (
          <div key={i} tabIndex={0} role="region" aria-label="Tabla (desplazable)" className="overflow-x-auto rounded-md border border-line">
            <table className="w-full border-collapse text-left text-xs">
              <thead className="bg-surface">
                <tr>
                  {b.header.map((h, k) => (
                    <th key={k} scope="col" className={`border-b border-line px-2 py-1.5 font-semibold ${b.align[k] ? ALIGN[b.align[k]!] : ""}`}>
                      {renderInline(h)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {b.rows.map((r, k) => (
                  <tr key={k} className="border-t border-line first:border-t-0">
                    {r.map((c, j) => (
                      <td key={j} className={`px-2 py-1.5 align-top ${b.align[j] ? ALIGN[b.align[j]!] : ""}`}>
                        {renderInline(c)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
    }
  });
}

/** Texto del asistente con Markdown básico, sin HTML del modelo. */
export const Markdown = memo(function Markdown({ text }: { text: string }) {
  return <div className="flex flex-col gap-2 text-sm leading-relaxed [overflow-wrap:anywhere]">{renderBlocks(parseMarkdown(text))}</div>;
});

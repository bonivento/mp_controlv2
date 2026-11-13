"use client";

import { useEffect, useRef, useState } from "react";
import { MAX_COLS, MAX_ROWS, filledRows, isBlock, pasteBlock, parsePasted, type Draft } from "@/lib/manual-table";
import { Alert, Button } from "../ui";

const cellCls =
  "block w-full min-w-[5.5rem] border-0 bg-transparent px-2 py-1.5 text-sm text-ink focus:relative focus:z-10 focus:outline-2 focus:-outline-offset-2 focus:outline-focus";

/**
 * Tabla editable para escribir o pegar datos. El borrador vive en el padre (así no se pierde al
 * cambiar de pestaña). Teclado: Tab/Mayús+Tab entre celdas, Enter y flecha abajo bajan, Mayús+Enter
 * y flecha arriba suben; Enter en la última fila agrega una fila nueva.
 */
export function ManualTable({
  draft,
  onChange,
  onReset,
  onUse,
  busy,
}: {
  draft: Draft;
  onChange: (d: Draft) => void;
  onReset: () => void;
  onUse: () => void;
  busy: boolean;
}) {
  const wrap = useRef<HTMLDivElement>(null);
  const focusAfter = useRef<[number, number] | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const rows = draft.cells.length;
  const cols = draft.headers.length;

  useEffect(() => {
    const target = focusAfter.current;
    if (!target) return;
    focusAfter.current = null;
    wrap.current?.querySelector<HTMLInputElement>(`[data-cell="${target[0]}-${target[1]}"]`)?.focus();
  });

  const setHeader = (j: number, v: string) => onChange({ ...draft, headers: draft.headers.map((h, k) => (k === j ? v : h)) });
  const setCell = (i: number, j: number, v: string) =>
    onChange({ ...draft, cells: draft.cells.map((r, k) => (k === i ? r.map((c, l) => (l === j ? v : c)) : r)) });

  function addRow() {
    if (rows >= MAX_ROWS) return setNotice(`El máximo en esta tabla es ${MAX_ROWS} filas. Para más datos sube un archivo.`);
    onChange({ ...draft, cells: [...draft.cells, draft.headers.map(() => "")] });
    focusAfter.current = [rows, 0];
  }
  function addColumn() {
    if (cols >= MAX_COLS) return setNotice(`El máximo en esta tabla es ${MAX_COLS} columnas.`);
    onChange({ headers: [...draft.headers, `columna_${cols + 1}`], cells: draft.cells.map((r) => [...r, ""]) });
    focusAfter.current = [-1, cols];
  }
  const removeRow = (i: number) =>
    onChange({ ...draft, cells: draft.cells.length > 1 ? draft.cells.filter((_, k) => k !== i) : [draft.headers.map(() => "")] });
  const removeColumn = (j: number) =>
    cols > 1 && onChange({ headers: draft.headers.filter((_, k) => k !== j), cells: draft.cells.map((r) => r.filter((_, k) => k !== j)) });

  function move(i: number, j: number, di: number) {
    const next = i + di;
    if (next >= rows) {
      if (rows >= MAX_ROWS) return;
      onChange({ ...draft, cells: [...draft.cells, draft.headers.map(() => "")] });
      focusAfter.current = [rows, j];
    } else if (next >= -1) wrap.current?.querySelector<HTMLInputElement>(`[data-cell="${next}-${j}"]`)?.focus();
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>, i: number, j: number) {
    if (e.key === "Enter" || e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      move(i, j, e.key === "ArrowUp" || (e.key === "Enter" && e.shiftKey) ? -1 : 1);
    }
  }

  function onPaste(e: React.ClipboardEvent<HTMLInputElement>, i: number, j: number) {
    const text = e.clipboardData.getData("text");
    if (!isBlock(text)) return; // un solo valor: pegado normal
    e.preventDefault();
    const r = pasteBlock(draft, i, j, parsePasted(text));
    onChange(r.draft);
    setNotice(
      r.truncated
        ? `Se pegó el bloque recortado: la tabla admite hasta ${MAX_ROWS} filas y ${MAX_COLS} columnas.`
        : "Bloque pegado a partir de la celda activa.",
    );
  }

  const used = filledRows(draft).length;
  const input = (i: number, j: number, value: string, label: string, onVal: (v: string) => void, extra = "") => (
    <input
      data-cell={`${i}-${j}`}
      aria-label={label}
      value={value}
      autoComplete="off"
      spellCheck={false}
      className={`${cellCls} ${extra}`}
      onChange={(e) => onVal(e.target.value)}
      onKeyDown={(e) => onKeyDown(e, i, j)}
      onPaste={(e) => onPaste(e, i, j)}
    />
  );

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-muted">
        Escribe los datos o pégalos desde Excel o Google Sheets (se reparten desde la celda activa y se crean las filas y
        columnas que falten). Se acepta la coma decimal. Pega con el encabezado sobre un nombre de columna para reemplazarlos.
        Enter baja a la celda de abajo.
      </p>
      <div ref={wrap} className="max-h-[26rem] overflow-auto rounded-md border border-line" tabIndex={-1}>
        <table className="w-full border-collapse text-sm">
          <caption className="sr-only">Tabla editable de datos: la primera fila son los nombres de las columnas</caption>
          <thead className="sticky top-0 z-20 bg-surface-2">
            <tr>
              <th scope="col" className="w-10 border-b border-r border-line px-1 text-xs font-medium text-muted">
                <span className="sr-only">Fila</span>
              </th>
              {draft.headers.map((h, j) => (
                <th key={j} scope="col" className="border-b border-r border-line p-0 text-left font-semibold">
                  <div className="flex items-center">
                    {input(-1, j, h, `Nombre de la columna ${j + 1}`, (v) => setHeader(j, v), "font-semibold")}
                    <button
                      type="button"
                      onClick={() => removeColumn(j)}
                      disabled={cols <= 1}
                      aria-label={`Quitar la columna ${j + 1}${h ? ` (${h})` : ""}`}
                      title="Quitar columna"
                      className="mr-1 flex size-6 shrink-0 items-center justify-center rounded text-muted hover:bg-line disabled:opacity-30"
                    >
                      <span aria-hidden>×</span>
                    </button>
                  </div>
                </th>
              ))}
              <th className="w-0 border-b border-line" />
            </tr>
          </thead>
          <tbody>
            {draft.cells.map((r, i) => (
              <tr key={i} className="odd:bg-surface even:bg-surface-2/40">
                <th scope="row" className="border-b border-r border-line px-1 text-center text-xs font-normal text-muted">
                  {i + 1}
                </th>
                {r.map((c, j) => (
                  <td key={j} className="border-b border-r border-line p-0">
                    {input(i, j, c, `Fila ${i + 1}, ${draft.headers[j] || `columna ${j + 1}`}`, (v) => setCell(i, j, v))}
                  </td>
                ))}
                <td className="border-b border-line px-1">
                  <button
                    type="button"
                    onClick={() => removeRow(i)}
                    aria-label={`Quitar la fila ${i + 1}`}
                    title="Quitar fila"
                    className="flex size-6 items-center justify-center rounded text-muted hover:bg-line"
                  >
                    <span aria-hidden>×</span>
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {notice && (
        <p role="status" className="text-xs text-muted">
          {notice}
        </p>
      )}
      <div className="flex flex-wrap items-center gap-2">
        <Button onClick={addRow}>Agregar fila</Button>
        <Button onClick={addColumn}>Agregar columna</Button>
        <Button variant="ghost" onClick={onReset}>
          Restablecer tabla
        </Button>
        <span className="text-xs text-muted" aria-live="polite">
          {used} {used === 1 ? "fila con datos" : "filas con datos"}; las filas vacías no se envían.
        </span>
      </div>
      {used === 0 && <Alert tone="info">Escribe o pega al menos una fila de datos para continuar.</Alert>}
      <div>
        <Button variant="primary" onClick={onUse} loading={busy} disabled={used === 0}>
          Usar estos datos
        </Button>
      </div>
    </div>
  );
}

"use client";

// Botón «Asistente» de la cabecera y panel de conversación. En escritorio el panel es una columna
// a la derecha; en móvil, una hoja a pantalla completa. Es un <dialog> modal nativo: la página
// queda inerte detrás, Esc lo cierra y el foco vuelve al botón.

import { useEffect, useId, useRef, useState } from "react";
import { API_MOCK } from "@/lib/env";
import { UpgradeDialog } from "../guest";
import { Alert, Button, Loading } from "../ui";
import { useAssistant, type ChatMessage } from "./assistant-provider";
import { Markdown } from "./markdown";

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), summary, [tabindex]:not([tabindex="-1"])';

/** Icono propio: burbuja de conversación con la línea de un gráfico de control entre dos límites. */
export function AssistantIcon({ size = 18 }: { size?: number }) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" aria-hidden focusable="false">
      <path d="M4 5.5h16a1.5 1.5 0 0 1 1.5 1.5v9a1.5 1.5 0 0 1-1.5 1.5h-8l-4.5 3.5V17.5H4A1.5 1.5 0 0 1 2.5 16V7A1.5 1.5 0 0 1 4 5.5Z" strokeWidth="1.8" />
      <path d="M6 9h12M6 15h12" strokeWidth="1" strokeDasharray="1.6 2" opacity="0.7" />
      <path d="M6 12.2l3-1.6 2.6 1.6L15 9.4" strokeWidth="1.8" />
      <circle cx="17.2" cy="9" r="1.1" fill="currentColor" stroke="none" />
    </svg>
  );
}

/** Botón persistente de la cabecera. */
export function AssistantButton() {
  const { open, openPanel } = useAssistant();
  return (
    <button
      type="button"
      onClick={openPanel}
      aria-haspopup="dialog"
      aria-expanded={open}
      className="no-print inline-flex min-h-10 items-center justify-center gap-2 rounded-md border border-transparent bg-accent px-3.5 py-2 text-sm font-semibold text-accent-ink transition-colors hover:bg-accent-strong"
    >
      <AssistantIcon />
      Asistente
    </button>
  );
}

/** «Calculando…» con la etiqueta de la herramienta que llegó en el evento `tool`. */
const toolText = (label: string) => (/^calcul/i.test(label.trim()) ? label.trim() : `Calculando: ${label.trim()}`);

function Bubble({ m, last, onRetry }: { m: ChatMessage; last: boolean; onRetry: () => void }) {
  if (m.role === "user") {
    return (
      <li className="flex justify-end">
        <div className="max-w-[88%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-brand px-3.5 py-2 text-sm text-brand-ink [overflow-wrap:anywhere]">
          <span className="sr-only">Tú: </span>
          {m.content}
        </div>
      </li>
    );
  }
  const streaming = m.state === "streaming";
  return (
    <li className="flex justify-start">
      <div className="w-full max-w-[96%] rounded-2xl rounded-bl-sm border border-line bg-surface-2 px-3.5 py-2.5 text-ink" aria-busy={streaming || undefined}>
        <span className="sr-only">Asistente: </span>
        {m.content && <Markdown text={m.content} />}
        {streaming && (
          <p className="flex items-center gap-2 text-xs text-muted" aria-hidden={m.content ? true : undefined}>
            <span className="size-3.5 shrink-0 animate-spin rounded-full border-2 border-brand-text border-t-transparent motion-reduce:animate-none" aria-hidden />
            {m.tool ? toolText(m.tool) : m.content ? "Escribiendo…" : "Pensando…"}
          </p>
        )}
        {m.state === "stopped" && <p className="mt-1.5 text-xs text-muted">{m.content ? "Respuesta detenida." : "Detuviste la respuesta antes de que empezara."}</p>}
        {m.truncated && <p className="mt-1.5 text-xs text-muted">La respuesta se cortó por su longitud. Pide que continúe.</p>}
        {m.state === "error" && (
          <div className="mt-2 flex flex-col gap-2">
            <Alert tone="error" title="El asistente no pudo responder">
              {m.error}
            </Alert>
            {last && (
              <div>
                <Button onClick={onRetry}>Reintentar</Button>
              </div>
            )}
          </div>
        )}
      </div>
    </li>
  );
}

/** Preguntas sugeridas según la pantalla: en lista al empezar y en fila compacta durante la conversación. */
function SuggestionList({ items, onPick, compact }: { items: string[]; onPick: (s: string) => void; compact?: boolean }) {
  return (
    <ul aria-label="Preguntas sugeridas" className={compact ? "-mx-1 mb-2 flex gap-1.5 overflow-x-auto px-1 pb-1" : "flex flex-col gap-2"}>
      {items.map((t) => (
        <li key={t} className="shrink-0">
          <button
            type="button"
            onClick={() => onPick(t)}
            className={
              compact
                ? "min-h-9 whitespace-nowrap rounded-full border border-line bg-background px-3 py-1 text-xs font-medium hover:border-brand-text hover:bg-brand-soft"
                : "min-h-10 w-full rounded-lg border border-line bg-surface px-3 py-2 text-left text-sm font-medium hover:border-brand-text hover:bg-brand-soft"
            }
          >
            {t}
          </button>
        </li>
      ))}
    </ul>
  );
}

function PanelBody({ draft, setDraft, onUpgrade }: { draft: string; setDraft: (s: string) => void; onUpgrade: () => void }) {
  const a = useAssistant();
  const listRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const titleId = useId();
  const nearBottom = useRef(true);
  const ok = a.service.kind === "ok";
  const last = a.messages[a.messages.length - 1];

  // Se sigue la respuesta en curso salvo que quien lee haya subido a releer algo.
  const lastContent = last?.content.length ?? 0;
  useEffect(() => {
    const el = listRef.current;
    if (el && nearBottom.current) el.scrollTop = el.scrollHeight;
  }, [a.messages.length, lastContent, last?.state]);

  // Al abrir: en escritorio el cursor va a la pregunta; en móvil, al título (para no abrir el teclado).
  useEffect(() => {
    const wide = window.matchMedia("(min-width: 640px)").matches;
    if (ok && wide) inputRef.current?.focus();
    else document.getElementById(titleId)?.focus();
  }, [ok, titleId]);

  function submit(text: string) {
    if (!text.trim() || a.busy) return;
    a.send(text);
    setDraft("");
    nearBottom.current = true;
  }

  const announce = a.busy ? (last?.tool ? toolText(last.tool) : "El asistente está escribiendo la respuesta") : "";

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="on-brand flex items-center justify-between gap-2 border-b-[3px] border-accent bg-header px-4 py-2.5 text-white">
        <h2 id={titleId} tabIndex={-1} className="flex items-center gap-2 text-base font-semibold outline-none">
          <AssistantIcon size={20} />
          Asistente con IA
        </h2>
        <div className="flex items-center gap-2">
          {a.messages.length > 0 && (
            <Button variant="onBrand" className="min-h-9 px-2.5 text-xs" onClick={a.reset}>
              Nueva conversación
            </Button>
          )}
          <Button variant="onBrand" className="min-h-9 px-2.5" onClick={a.closePanel} aria-label="Cerrar asistente">
            <span aria-hidden className="text-lg leading-none">×</span>
          </Button>
        </div>
      </header>

      <div className="border-b border-line bg-surface px-4 py-2 text-xs">
        <p>
          <span className="text-muted">Viendo: </span>
          <strong className="font-semibold">{a.snapshot.label}</strong>
          {a.snapshot.studyName && <span className="text-muted"> · {a.snapshot.studyName}</span>}
        </p>
        <details className="mt-0.5">
          <summary className="cursor-pointer text-brand-text underline-offset-2 hover:underline">¿Qué se envía al asistente?</summary>
          <p className="mt-1 text-muted">
            {a.describeContext().length > 0 ? `Se envía ${a.describeContext().join(", ")}.` : "No se envía contexto de esta pantalla."} Nunca se envían las filas de tus datos.
          </p>
        </details>
      </div>

      {API_MOCK && (
        <p className="border-b border-warn/40 bg-warn-soft px-4 py-1.5 text-xs">
          <strong>Modo de ejemplo.</strong> Las respuestas son simuladas y no analizan tus datos.
        </p>
      )}

      <div
        ref={listRef}
        onScroll={(e) => {
          const el = e.currentTarget;
          nearBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
        }}
        className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 py-3"
      >
        {a.service.kind === "loading" && <Loading label="Comprobando el asistente…" />}

        {a.service.kind === "unconfigured" && (
          <Alert tone="warn" title="El asistente no está configurado">
            Falta la clave del servicio de IA en el servidor. Quien administra la aplicación debe añadirla. El resto de Sigmalena funciona con normalidad.
            <div className="mt-2">
              <Button onClick={a.retryService}>Volver a comprobar</Button>
            </div>
          </Alert>
        )}

        {a.service.kind === "guest" && (
          <Alert tone="info" title="El asistente es solo para cuentas">
            {a.service.message}
            <div className="mt-2">
              <Button variant="primary" onClick={onUpgrade}>
                Crear cuenta para conservar mis datos
              </Button>
            </div>
          </Alert>
        )}

        {a.service.kind === "unavailable" && (
          <Alert tone="warn" title="El asistente no está disponible">
            {a.service.message}
          </Alert>
        )}

        {a.service.kind === "error" && (
          <Alert tone="error" title="No se pudo comprobar el asistente">
            {a.service.message}
            <div className="mt-2">
              <Button onClick={a.retryService}>Reintentar</Button>
            </div>
          </Alert>
        )}

        {ok && a.messages.length === 0 && (
          <div className="flex flex-col gap-3">
            <p className="text-sm">
              Te explico qué estás viendo, interpreto los resultados y te oriento sobre qué muestras tomar. Pregunta lo que necesites o empieza con una sugerencia:
            </p>
            <SuggestionList items={a.suggestions} onPick={submit} />
          </div>
        )}

        {ok && a.messages.length > 0 && (
          <ol role="log" aria-label="Conversación con el asistente" aria-live="polite" aria-relevant="additions text" className="flex flex-col gap-3">
            {a.messages.map((m, i) => (
              <Bubble key={m.id} m={m} last={i === a.messages.length - 1} onRetry={a.retry} />
            ))}
          </ol>
        )}
        <p role="status" className="sr-only">
          {announce}
        </p>
      </div>

      {ok && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            submit(draft);
          }}
          className="border-t border-line bg-surface px-4 py-3"
        >
          {a.messages.length > 0 && !a.busy && <SuggestionList items={a.suggestions} onPick={submit} compact />}
          <label htmlFor={`${titleId}-q`} className="sr-only">
            Tu pregunta al asistente
          </label>
          <div className="flex items-end gap-2">
            <textarea
              ref={inputRef}
              id={`${titleId}-q`}
              rows={2}
              maxLength={6000}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                  e.preventDefault();
                  submit(draft);
                }
              }}
              placeholder="Escribe tu pregunta…"
              className="max-h-40 min-h-[2.75rem] w-full resize-none rounded-md border border-line bg-background px-3 py-2 text-sm text-ink placeholder:text-muted/80"
            />
            {a.busy ? (
              <Button onClick={a.stop} className="shrink-0">
                Detener
              </Button>
            ) : (
              <Button type="submit" variant="primary" disabled={!draft.trim()} className="shrink-0">
                Enviar
              </Button>
            )}
          </div>
          <p className="mt-1 hidden text-xs text-muted sm:block">Intro envía; Mayús+Intro añade una línea.</p>
        </form>
      )}

      <p className="border-t border-line bg-surface-2 px-4 py-2 text-xs text-muted">
        Ayuda generada por IA: puede equivocarse. Los cálculos oficiales son los de la aplicación.
      </p>
    </div>
  );
}

/** Panel lateral (escritorio) u hoja a pantalla completa (móvil). */
export function AssistantPanel() {
  const a = useAssistant();
  const ref = useRef<HTMLDialogElement>(null);
  const [draft, setDraft] = useState("");
  const [upgrade, setUpgrade] = useState(false);
  const opener = useRef<HTMLElement | null>(null);

  const { open, closePanel } = a;
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) {
      opener.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      d.showModal();
    }
    if (!open && d.open) {
      d.close();
      // El navegador ya devuelve el foco; esto cubre los que no lo hacen.
      if (opener.current && opener.current.isConnected) opener.current.focus();
    }
  }, [open]);

  // El <dialog> deja inerte la página, pero Tab podría saltar a la barra del navegador: se atrapa.
  function trapTab(e: React.KeyboardEvent<HTMLDialogElement>) {
    if (e.key !== "Tab") return;
    const d = ref.current;
    if (!d) return;
    const items = [...d.querySelectorAll<HTMLElement>(FOCUSABLE)].filter((el) => el.getClientRects().length > 0);
    if (items.length === 0) return;
    const first = items[0];
    const lastEl = items[items.length - 1];
    const active = document.activeElement as HTMLElement | null;
    const inside = !!active && d.contains(active) && active !== d;
    // Un elemento enfocable solo por programa (el título) no está en `items`: se compara su posición.
    const idx = active ? items.indexOf(active) : -1;
    const before = (a: Element, b: Element) => !!(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);
    if (e.shiftKey && (!inside || idx === 0 || (idx === -1 && active && before(active, first)))) {
      e.preventDefault();
      lastEl.focus();
    } else if (!e.shiftKey && (!inside || idx === items.length - 1 || (idx === -1 && active && before(lastEl, active)))) {
      e.preventDefault();
      first.focus();
    }
  }

  return (
    <>
      <dialog
        ref={ref}
        aria-label="Asistente con IA"
        onClose={closePanel}
        onKeyDown={trapTab}
        onClick={(e) => {
          if (e.target === e.currentTarget) closePanel(); // clic en el fondo
        }}
        className="assistant-panel no-print"
      >
        {open && <PanelBody draft={draft} setDraft={setDraft} onUpgrade={() => setUpgrade(true)} />}
      </dialog>
      {a.user.isGuest && <UpgradeDialog open={upgrade} onClose={() => setUpgrade(false)} />}
    </>
  );
}

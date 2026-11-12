"use client";

import {
  useEffect,
  useId,
  useRef,
  useState,
  type ButtonHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
} from "react";

export const errMsg = (e: unknown) => (e instanceof Error ? e.message : "Ocurrió un error inesperado.");

// --- Botones -------------------------------------------------------------------
type Variant = "primary" | "secondary" | "danger" | "ghost";
const variants: Record<Variant, string> = {
  primary: "bg-brand text-brand-ink hover:bg-brand-strong border-transparent",
  secondary: "bg-surface text-ink hover:bg-surface-2 border-line",
  danger: "bg-danger text-white hover:opacity-90 border-transparent",
  ghost: "bg-transparent text-ink hover:bg-surface-2 border-transparent",
};

export function Button({
  variant = "secondary",
  loading,
  className = "",
  children,
  disabled,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; loading?: boolean }) {
  return (
    <button
      type="button"
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={`inline-flex min-h-10 items-center justify-center gap-2 rounded-md border px-3.5 py-2 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${variants[variant]} ${className}`}
      {...rest}
    >
      {loading && <span className="size-4 animate-spin rounded-full border-2 border-current border-t-transparent" aria-hidden />}
      {children}
    </button>
  );
}

// --- Campos --------------------------------------------------------------------
const inputCls =
  "w-full min-h-10 rounded-md border border-line bg-surface px-3 py-2 text-sm text-ink placeholder:text-muted/70 disabled:opacity-60";

function FieldShell({
  id,
  label,
  hint,
  error,
  children,
  className = "",
}: {
  id: string;
  label: string;
  hint?: string;
  error?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={`flex flex-col gap-1 ${className}`}>
      <label htmlFor={id} className="text-sm font-medium">
        {label}
      </label>
      {children}
      {hint && !error && (
        <p id={`${id}-hint`} className="text-xs text-muted">
          {hint}
        </p>
      )}
      {error && (
        <p id={`${id}-err`} role="alert" className="text-xs text-danger">
          {error}
        </p>
      )}
    </div>
  );
}

interface BaseField {
  label: string;
  hint?: string;
  error?: string;
  className?: string;
}

export function TextField({
  label,
  hint,
  error,
  className,
  ...rest
}: BaseField & Omit<React.InputHTMLAttributes<HTMLInputElement>, "className">) {
  const id = useId();
  return (
    <FieldShell id={id} label={label} hint={hint} error={error} className={className}>
      <input
        id={id}
        className={inputCls}
        aria-invalid={!!error || undefined}
        aria-describedby={error ? `${id}-err` : hint ? `${id}-hint` : undefined}
        {...rest}
      />
    </FieldShell>
  );
}

/** Campo numérico que conserva lo que se escribe ("0." o "-") hasta que sea un número. */
export function NumberField({
  label,
  hint,
  error,
  className,
  value,
  onChange,
  placeholder,
  disabled,
  required,
  step,
}: BaseField & {
  value: number | null;
  onChange: (v: number | null) => void;
  placeholder?: string;
  disabled?: boolean;
  required?: boolean;
  step?: string;
}) {
  const id = useId();
  const [text, setText] = useState(value == null ? "" : numEs(value));
  // Se conserva lo que el usuario escribe ("0." o "-") mientras coincida con el valor; si el valor
  // cambia desde fuera se muestra el nuevo.
  const parsed = text.trim() === "" ? null : Number(text.replace(",", "."));
  const shown = parsed === value || (value == null && Number.isNaN(parsed)) ? text : value == null ? "" : numEs(value);
  return (
    <FieldShell id={id} label={label} hint={hint} error={error} className={className}>
      <input
        id={id}
        inputMode="decimal"
        className={`${inputCls} num`}
        value={shown}
        placeholder={placeholder}
        disabled={disabled}
        required={required}
        step={step}
        aria-invalid={!!error || undefined}
        aria-describedby={error ? `${id}-err` : hint ? `${id}-hint` : undefined}
        onChange={(e) => {
          setText(e.target.value);
          const t = e.target.value.trim().replace(",", ".");
          if (t === "") onChange(null);
          else if (Number.isFinite(Number(t))) onChange(Number(t));
        }}
      />
    </FieldShell>
  );
}

export function SelectField({
  label,
  hint,
  error,
  className,
  children,
  ...rest
}: BaseField & Omit<SelectHTMLAttributes<HTMLSelectElement>, "className">) {
  const id = useId();
  return (
    <FieldShell id={id} label={label} hint={hint} error={error} className={className}>
      <select id={id} className={inputCls} aria-describedby={hint ? `${id}-hint` : undefined} {...rest}>
        {children}
      </select>
    </FieldShell>
  );
}

export function TextAreaField({
  label,
  hint,
  error,
  className,
  ...rest
}: BaseField & Omit<React.TextareaHTMLAttributes<HTMLTextAreaElement>, "className">) {
  const id = useId();
  return (
    <FieldShell id={id} label={label} hint={hint} error={error} className={className}>
      <textarea
        id={id}
        rows={3}
        className={inputCls}
        aria-invalid={!!error || undefined}
        aria-describedby={error ? `${id}-err` : hint ? `${id}-hint` : undefined}
        {...rest}
      />
    </FieldShell>
  );
}

export function CheckField({
  label,
  hint,
  checked,
  onChange,
  disabled,
}: {
  label: ReactNode;
  hint?: string;
  checked: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
}) {
  const id = useId();
  return (
    <div className="flex items-start gap-2">
      <input
        id={id}
        type="checkbox"
        className="mt-1 size-4 accent-[var(--brand)]"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
      />
      <label htmlFor={id} className="text-sm">
        {label}
        {hint && <span className="block text-xs text-muted">{hint}</span>}
      </label>
    </div>
  );
}

// --- Contenedores y avisos ------------------------------------------------------
export function Card({
  title,
  actions,
  children,
  className = "",
  id,
}: {
  title?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  id?: string;
}) {
  return (
    <section id={id} className={`rounded-lg border border-line bg-surface p-4 shadow-sm sm:p-5 ${className}`}>
      {(title || actions) && (
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          {title && <h2 className="text-base font-semibold">{title}</h2>}
          {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
        </div>
      )}
      {children}
    </section>
  );
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1 max-w-3xl text-sm text-muted">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

const tones = {
  info: { cls: "border-brand/40 bg-brand-soft text-ink", icon: "i", label: "Información" },
  warn: { cls: "border-warn/50 bg-warn-soft text-ink", icon: "!", label: "Advertencia" },
  error: { cls: "border-danger/50 bg-danger-soft text-ink", icon: "×", label: "Error" },
  ok: { cls: "border-ok/50 bg-ok-soft text-ink", icon: "✓", label: "Correcto" },
};

export function Alert({
  tone = "info",
  title,
  children,
  className = "",
}: {
  tone?: keyof typeof tones;
  title?: string;
  children?: ReactNode;
  className?: string;
}) {
  const t = tones[tone];
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={`flex gap-3 rounded-md border p-3 text-sm ${t.cls} ${className}`}
    >
      <span
        aria-hidden
        className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full border border-current text-xs font-bold"
      >
        {t.icon}
      </span>
      <div className="min-w-0">
        <span className="sr-only">{t.label}: </span>
        {title && <p className="font-semibold">{title}</p>}
        {children && <div className={title ? "mt-0.5" : ""}>{children}</div>}
      </div>
    </div>
  );
}

export function Loading({ label = "Cargando…" }: { label?: string }) {
  return (
    <div role="status" className="flex items-center gap-3 p-6 text-sm text-muted">
      <span className="size-5 animate-spin rounded-full border-2 border-brand border-t-transparent" aria-hidden />
      {label}
    </div>
  );
}

export function EmptyState({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed border-line bg-surface p-8 text-center">
      <p className="font-semibold">{title}</p>
      {children && <div className="mx-auto mt-1 max-w-xl text-sm text-muted">{children}</div>}
      {action && <div className="mt-4 flex justify-center">{action}</div>}
    </div>
  );
}

export function Badge({ tone = "info", children }: { tone?: "info" | "ok" | "warn" | "error" | "neutral"; children: ReactNode }) {
  const cls = {
    info: "bg-brand-soft text-ink border-brand/40",
    ok: "bg-ok-soft text-ink border-ok/50",
    warn: "bg-warn-soft text-ink border-warn/50",
    error: "bg-danger-soft text-ink border-danger/50",
    neutral: "bg-surface-2 text-ink border-line",
  }[tone];
  return <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${cls}`}>{children}</span>;
}

// --- Diálogo modal accesible (elemento <dialog> nativo) --------------------------
const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function Modal({
  open,
  title,
  onClose,
  children,
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);

  // El <dialog> nativo deja el resto de la página inerte, pero Tab puede saltar a la barra del
  // navegador. Se atrapa: Tab desde el último elemento vuelve al primero y Mayús+Tab al revés.
  function trapTab(e: React.KeyboardEvent<HTMLDialogElement>) {
    if (e.key !== "Tab") return;
    const d = ref.current;
    if (!d) return;
    const items = [...d.querySelectorAll<HTMLElement>(FOCUSABLE)].filter((el) => !el.hasAttribute("hidden") && el.getClientRects().length > 0);
    if (items.length === 0) {
      e.preventDefault();
      return;
    }
    const first = items[0];
    const last = items[items.length - 1];
    const active = document.activeElement as HTMLElement | null;
    const inside = !!active && d.contains(active) && active !== d;
    if (e.shiftKey && (!inside || active === first)) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && (!inside || active === last)) {
      e.preventDefault();
      first.focus();
    }
  }
  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      onClose={onClose}
      onCancel={onClose}
      onKeyDown={trapTab}
      className="m-auto w-[min(32rem,calc(100vw-2rem))] rounded-lg border border-line bg-surface p-0 text-ink shadow-xl backdrop:bg-black/50"
    >
      {open && (
        <div className="p-5">
          <h2 id={titleId} className="mb-3 text-lg font-semibold">
            {title}
          </h2>
          {children}
        </div>
      )}
    </dialog>
  );
}

/** Confirmación de acciones destructivas. */
export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = "Eliminar",
  busy,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  message: ReactNode;
  confirmLabel?: string;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <Modal open={open} title={title} onClose={onCancel}>
      <div className="text-sm text-muted">{message}</div>
      <div className="mt-5 flex justify-end gap-2">
        <Button onClick={onCancel}>Cancelar</Button>
        <Button variant="danger" onClick={onConfirm} loading={busy}>
          {confirmLabel}
        </Button>
      </div>
    </Modal>
  );
}

// --- Tablas -----------------------------------------------------------------------
export function Table({ caption, children, className = "" }: { caption?: string; children: ReactNode; className?: string }) {
  // El contenedor desplaza en horizontal solo si hace falta (móvil); en pantallas anchas la
  // tabla ocupa el ancho disponible y las celdas de texto largo se ajustan en varias líneas.
  return (
    <div className={`overflow-x-auto rounded-md border border-line ${className}`}>
      <table className="num w-full border-collapse text-sm">
        {caption && <caption className="sr-only">{caption}</caption>}
        {children}
      </table>
    </div>
  );
}
export const Th = ({ children, className = "" }: { children?: ReactNode; className?: string }) => (
  <th scope="col" className={`whitespace-nowrap border-b border-line bg-surface-2 px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-muted ${className}`}>
    {children}
  </th>
);
export const Td = ({ children, className = "" }: { children?: ReactNode; className?: string }) => (
  <td className={`border-b border-line px-3 py-2 align-top ${className}`}>{children}</td>
);

/** Formato numérico con coma decimal; null se muestra como raya. */
export function fmtNum(x: number | null | undefined, d = 3) {
  if (x == null || !Number.isFinite(x)) return "—";
  return x.toLocaleString("es-CO", { minimumFractionDigits: d, maximumFractionDigits: d });
}

/** Número tal como viene (sin fijar decimales) pero con coma decimal: 2.5 → "2,5". */
export function numEs(x: number | null | undefined) {
  if (x == null || !Number.isFinite(x)) return "—";
  return String(x).replace(".", ",");
}

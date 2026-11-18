"use client";

// Estado del asistente con IA: registro de lo que el usuario ve en cada pantalla, estado del
// servicio y conversaciones (en memoria, una por estudio, mientras dure la sesión de navegación).
// Las pantallas solo conocen `useAssistantScreen`; el panel usa `useAssistant`.

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from "react";
import { ApiError } from "@/lib/api";
import {
  ASSISTANT_MAX_DATASETS,
  ASSISTANT_MAX_FROZEN,
  getAssistantStatus,
  isAbort,
  prepareHistory,
  streamChat,
  type AssistantContext,
  type AssistantMessage,
  type AssistantScreen,
  type AssistantStatus,
  type AssistantStudy,
} from "@/lib/assistant";
import { fitContext, screenTitle, suggestionsFor } from "@/lib/assistant-context";
import { getStore, type AppUser } from "@/lib/data";
import { sizeLabel } from "@/lib/dataset-utils";
import type { ControlLimitsRow, Dataset } from "@/lib/db";

// --- Registro de pantalla ---------------------------------------------------------------------

/** Lo que una pantalla (o una parte de ella) declara que el usuario está viendo. */
export interface ScreenRegistration {
  /** Solo la página del módulo la declara. */
  screen?: AssistantScreen;
  /** «Variables · Fase I · X-barra y R»: se muestra al usuario en el panel. */
  label?: string;
  /** Estudio abierto (lo declara el marco del estudio). */
  studyId?: string;
  study?: AssistantStudy;
  /**
   * Parámetros elegidos y resultado del módulo, tal como los tiene la pantalla. Se reducen
   * antes de enviarse (lib/assistant-context.ts); varias partes de una pantalla pueden aportar
   * claves distintas y se unen.
   */
  view?: Record<string, unknown>;
  /** Hay un resultado calculado en pantalla (afina las sugerencias). */
  hasResult?: boolean;
  /** La pantalla todavía no tiene datos que mostrar. */
  empty?: boolean;
}

interface Snapshot {
  screen: AssistantScreen;
  label: string;
  studyId: string | null;
  studyName: string | null;
  hasResult: boolean;
  empty: boolean;
}

class Registry {
  private regs = new Map<string, ScreenRegistration>();
  private listeners = new Set<() => void>();
  private snap: Snapshot = { screen: "studies", label: screenTitle("studies"), studyId: null, studyName: null, hasResult: false, empty: false };

  set(id: string, reg: ScreenRegistration) {
    this.regs.set(id, reg);
    this.refresh();
  }
  delete(id: string) {
    if (this.regs.delete(id)) this.refresh();
  }
  subscribe = (fn: () => void) => {
    this.listeners.add(fn);
    return () => {
      this.listeners.delete(fn);
    };
  };
  getSnapshot = () => this.snap;

  /** Une las declaraciones: lo escalar viene de quien lo declare; `view` se une clave a clave. */
  merged() {
    let screen: AssistantScreen | undefined;
    let label: string | undefined;
    let studyId: string | undefined;
    let study: AssistantStudy | undefined;
    let hasResult = false;
    let empty = false;
    const view: Record<string, unknown> = {};
    for (const r of this.regs.values()) {
      screen = r.screen ?? screen;
      label = r.label ?? label;
      studyId = r.studyId ?? studyId;
      study = r.study ?? study;
      hasResult = hasResult || !!r.hasResult;
      empty = empty || !!r.empty;
      if (r.view) Object.assign(view, r.view);
    }
    const resolved: AssistantScreen = screen ?? (studyId ? "study" : "studies");
    return { screen: resolved, label: label ?? screenTitle(resolved), studyId, study, hasResult, empty, view };
  }

  private refresh() {
    const m = this.merged();
    const next: Snapshot = {
      screen: m.screen,
      label: m.label,
      studyId: m.studyId ?? null,
      studyName: m.study?.name ?? null,
      hasResult: m.hasResult,
      empty: m.empty,
    };
    const s = this.snap;
    if (next.screen === s.screen && next.label === s.label && next.studyId === s.studyId && next.studyName === s.studyName && next.hasResult === s.hasResult && next.empty === s.empty) return;
    this.snap = next;
    this.listeners.forEach((l) => l());
  }
}

const RegistryContext = createContext<Registry | null>(null);

/**
 * Declara lo que la pantalla muestra. Llamar en cada render con el estado actual (es barato:
 * solo guarda una referencia); al desmontar se retira solo. Debe llamarse antes de cualquier
 * `return` anticipado del componente.
 */
export function useAssistantScreen(reg: ScreenRegistration) {
  const registry = useContext(RegistryContext);
  const id = useId();
  useEffect(() => {
    registry?.set(id, reg);
  });
  useEffect(() => () => registry?.delete(id), [registry, id]);
}

// --- Estado del servicio ------------------------------------------------------------------------

export type ServiceState =
  | { kind: "loading" }
  | { kind: "ok" }
  | { kind: "unconfigured"; message: string }
  | { kind: "guest"; message: string }
  | { kind: "unavailable"; message: string }
  | { kind: "error"; message: string };

function fromStatus(s: AssistantStatus, user: AppUser): ServiceState {
  if (!s.enabled) return { kind: "unconfigured", message: "El asistente no está configurado." };
  if (s.available) return { kind: "ok" };
  if (user.isGuest && !s.guests_allowed)
    return { kind: "guest", message: s.reason || "El asistente no está disponible para sesiones de invitado." };
  return { kind: "unavailable", message: s.reason || "El asistente no está disponible para tu cuenta." };
}

function fromError(e: unknown, user: AppUser): ServiceState {
  const message = e instanceof Error ? e.message : "No se pudo consultar el asistente.";
  if (e instanceof ApiError) {
    if (e.status === 503) return { kind: "unconfigured", message: "El asistente no está configurado." };
    if (e.status === 403) return user.isGuest ? { kind: "guest", message } : { kind: "unavailable", message };
    if (e.status === 401 || e.status === 404 || e.status === 501) return { kind: "unavailable", message: e.status === 401 ? message : "El asistente no está disponible en esta versión de la API." };
  }
  return { kind: "error", message };
}

// --- Conversación -------------------------------------------------------------------------------

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  /** Solo asistente. */
  state?: "streaming" | "done" | "stopped" | "error";
  error?: string;
  /** Etiqueta de la herramienta en curso («calculando…»). */
  tool?: string | null;
  /** La respuesta se cortó por longitud. */
  truncated?: boolean;
}

const GLOBAL_KEY = "global";
const NO_MESSAGES: ChatMessage[] = [];

interface AssistantApi {
  open: boolean;
  openPanel: () => void;
  closePanel: () => void;
  service: ServiceState;
  retryService: () => void;
  user: AppUser;
  snapshot: Snapshot;
  suggestions: string[];
  messages: ChatMessage[];
  busy: boolean;
  send: (text: string) => void;
  stop: () => void;
  retry: () => void;
  reset: () => void;
  /** Qué se enviará (para el aviso del panel). */
  describeContext: () => string[];
}

const AssistantContextValue = createContext<AssistantApi | null>(null);

export function useAssistant(): AssistantApi {
  const c = useContext(AssistantContextValue);
  if (!c) throw new Error("useAssistant debe usarse dentro de AssistantProvider");
  return c;
}

// --- Resúmenes de apoyo (nunca filas) --------------------------------------------------------

const clip = (s: string | undefined, n: number) => (s && s.length > n ? `${s.slice(0, n - 1)}…` : s);

function datasetsForAssistant(datasets: Dataset[]): Record<string, unknown>[] {
  return [...datasets]
    .sort((a, b) => b.created_at.localeCompare(a.created_at))
    .slice(0, ASSISTANT_MAX_DATASETS)
    .map((d) => {
      const sg = d.subgrouping as Partial<{
        method: string;
        layout: string;
        column: string;
        value_columns: string[];
        size: number;
        time_column: string;
        time_unit: string;
        count_column: string;
        size_column: string;
        counting: string;
        justification: string;
      }>;
      return {
        name: clip(d.name, 120),
        phase: d.phase,
        kind: d.rows.length > 0 && "values" in d.rows[0] ? "variable" : "attribute",
        n_subgroups: d.rows.length,
        subgroup_size: sizeLabel(d),
        source_file: clip(d.source_file ?? undefined, 120) ?? null,
        subgrouping: {
          method: sg.method,
          layout: sg.layout,
          column: sg.column,
          value_columns: sg.value_columns?.slice(0, 12),
          size: sg.size,
          time_unit: sg.time_unit,
          counting: sg.counting,
          justification: clip(sg.justification, 200),
        },
        cleaning_entries: d.cleaning_log.length,
        saved_at: d.created_at,
      };
    });
}

function frozenForAssistant(limits: ControlLimitsRow[], datasets: Dataset[]): Record<string, unknown>[] {
  return limits.slice(0, ASSISTANT_MAX_FROZEN).map((l) => ({
    chart_type: l.chart_type,
    from_dataset: datasets.find((d) => d.id === l.dataset_id)?.name ?? null,
    frozen_at: l.created_at,
    subgroup_size: l.limits.subgroup_size ?? null,
    sigma_method: l.limits.sigma_method ?? null,
    params: l.limits.params,
    points_used: l.limits.points_used,
    limit_width: l.limits.limit_width,
    excluded: l.limits.excluded.slice(0, 8).map((e) => ({ index: e.index, label: e.label ?? null, cause: clip(e.cause, 120) })),
    n_excluded: l.limits.excluded.length,
  }));
}

// --- Proveedor ----------------------------------------------------------------------------------

export function AssistantProvider({ user, children }: { user: AppUser; children: ReactNode }) {
  const [registry] = useState(() => new Registry());
  const snapshot = useSyncExternalStore(registry.subscribe, registry.getSnapshot, registry.getSnapshot);
  const [open, setOpen] = useState(false);
  const [statusRes, setStatusRes] = useState<{ key: string; value: ServiceState } | null>(null);
  const [nonce, setNonce] = useState(0);
  const [convs, setConvs] = useState<Record<string, ChatMessage[]>>({});
  const streams = useRef(new Map<string, AbortController>());
  const seq = useRef(0);
  const nextId = () => `m${++seq.current}`;

  // El estado del servicio se consulta al abrir el panel (no al cargar la app) y se vuelve a
  // consultar si cambia la sesión (p. ej. un invitado que crea su cuenta).
  const statusKey = `${user.id}|${user.isGuest}|${nonce}`;
  useEffect(() => {
    if (!open || statusRes?.key === statusKey) return;
    const ac = new AbortController();
    getAssistantStatus(ac.signal).then(
      (s) => setStatusRes({ key: statusKey, value: fromStatus(s, user) }),
      (e) => {
        if (!isAbort(e)) setStatusRes({ key: statusKey, value: fromError(e, user) });
      },
    );
    return () => ac.abort();
  }, [open, statusKey, statusRes?.key, user]);
  const service = useMemo<ServiceState>(() => (statusRes?.key === statusKey ? statusRes.value : { kind: "loading" }), [statusRes, statusKey]);

  const serviceKind = service.kind;
  const openPanel = useCallback(() => {
    setOpen(true);
    if (serviceKind === "error") setNonce((n) => n + 1); // un fallo de red previo se reintenta al abrir
  }, [serviceKind]);
  const closePanel = useCallback(() => setOpen(false), []);
  const retryService = useCallback(() => setNonce((n) => n + 1), []);

  const key = snapshot.studyId ?? GLOBAL_KEY;
  const messages = convs[key] ?? NO_MESSAGES;
  const busy = messages.some((m) => m.state === "streaming");

  const patch = useCallback((k: string, id: string, fn: (m: ChatMessage) => ChatMessage) => {
    setConvs((c) => ({ ...c, [k]: (c[k] ?? []).map((m) => (m.id === id ? fn(m) : m)) }));
  }, []);

  /** Arma el contexto de la pantalla en este momento (se llama justo antes de cada envío). */
  const buildContext = useCallback(async (): Promise<AssistantContext> => {
    const m = registry.merged();
    let datasets: Record<string, unknown>[] | undefined;
    let frozen: Record<string, unknown>[] | undefined;
    if (m.studyId) {
      try {
        const s = getStore();
        const [ds, limits] = await Promise.all([s.datasets.list(m.studyId), s.controlLimits.listActive(m.studyId)]);
        datasets = datasetsForAssistant(ds);
        frozen = frozenForAssistant(limits, ds);
      } catch {
        // Sin esos resúmenes el asistente igual puede responder con lo que hay en pantalla.
      }
    }
    return fitContext({ screen: m.screen, study: m.study, view: m.view, datasets, frozen_limits: frozen }).context;
  }, [registry]);

  /** Pide la respuesta del asistente para `history` y la va escribiendo en el mensaje `asstId`. */
  const run = useCallback(
    async (k: string, asstId: string, history: AssistantMessage[]) => {
      const ac = new AbortController();
      streams.current.set(k, ac);
      try {
        const context = await buildContext();
        for await (const ev of streamChat({ messages: prepareHistory(history), context }, ac.signal)) {
          if (ev.type === "delta") patch(k, asstId, (m) => ({ ...m, content: m.content + ev.text, tool: null }));
          else if (ev.type === "tool") patch(k, asstId, (m) => ({ ...m, tool: ev.label || ev.name }));
          else if (ev.type === "done") patch(k, asstId, (m) => ({ ...m, state: "done", tool: null, truncated: ev.stop_reason === "max_tokens" }));
          else if (ev.type === "error") patch(k, asstId, (m) => ({ ...m, state: "error", tool: null, error: ev.detail }));
        }
      } catch (e) {
        if (ac.signal.aborted || isAbort(e)) {
          patch(k, asstId, (m) => ({ ...m, state: "stopped", tool: null }));
        } else {
          // Errores previos al flujo (401/403/422/503): se muestra el `detail` de la API en el mensaje.
          patch(k, asstId, (m) => ({ ...m, state: "error", tool: null, error: e instanceof Error ? e.message : "No se pudo obtener la respuesta." }));
        }
      } finally {
        if (streams.current.get(k) === ac) streams.current.delete(k);
        // Por si el flujo terminó sin `done` ni `error` (no debería): no se deja «escribiendo».
        patch(k, asstId, (m) => (m.state === "streaming" ? { ...m, state: "done", tool: null } : m));
      }
    },
    [buildContext, patch],
  );

  const send = useCallback(
    (text: string) => {
      const t = text.trim();
      if (!t || streams.current.has(key)) return;
      const userMsg: ChatMessage = { id: nextId(), role: "user", content: t };
      const asst: ChatMessage = { id: nextId(), role: "assistant", content: "", state: "streaming" };
      const history = [...(convs[key] ?? []), userMsg];
      setConvs((c) => ({ ...c, [key]: [...(c[key] ?? []), userMsg, asst] }));
      void run(key, asst.id, history);
    },
    [convs, key, run],
  );

  const retry = useCallback(() => {
    const list = convs[key] ?? [];
    const last = list[list.length - 1];
    if (!last || last.role !== "assistant" || last.state !== "error" || streams.current.has(key)) return;
    const history = list.slice(0, -1);
    const asst: ChatMessage = { id: nextId(), role: "assistant", content: "", state: "streaming" };
    setConvs((c) => ({ ...c, [key]: [...history, asst] }));
    void run(key, asst.id, history);
  }, [convs, key, run]);

  const stop = useCallback(() => streams.current.get(key)?.abort(), [key]);

  const reset = useCallback(() => {
    streams.current.get(key)?.abort();
    setConvs((c) => ({ ...c, [key]: [] }));
  }, [key]);

  // Al salir de la aplicación se cortan los flujos abiertos.
  useEffect(() => {
    const all = streams.current;
    return () => all.forEach((a) => a.abort());
  }, []);

  const describeContext = useCallback(() => {
    const m = registry.merged();
    const out: string[] = [];
    if (m.study) out.push("la ficha del estudio");
    if (Object.keys(m.view).length > 0) out.push(m.hasResult ? "los parámetros y el resultado de esta pantalla (resumido)" : "los parámetros de esta pantalla");
    if (m.studyId) out.push("un resumen de tus conjuntos de datos y límites congelados");
    return out;
  }, [registry]);

  const suggestions = useMemo(() => suggestionsFor(snapshot.screen, { hasResult: snapshot.hasResult, empty: snapshot.empty }), [snapshot]);

  const api = useMemo<AssistantApi>(
    () => ({ open, openPanel, closePanel, service, retryService, user, snapshot, suggestions, messages, busy, send, stop, retry, reset, describeContext }),
    [open, openPanel, closePanel, service, retryService, user, snapshot, suggestions, messages, busy, send, stop, retry, reset, describeContext],
  );

  return (
    <RegistryContext value={registry}>
      <AssistantContextValue value={api}>{children}</AssistantContextValue>
    </RegistryContext>
  );
}

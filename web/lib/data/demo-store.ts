// Modo de demostración: sesión y tablas en localStorage del navegador, detrás de
// la misma interfaz DataStore que Supabase. Las contraseñas se guardan en claro
// SOLO porque esto es una demostración local; nunca se usa en producción.

import type {
  Analysis,
  ControlLimitsRow,
  Dataset,
  SamplingPlan,
  Study,
} from "../db";
import { buildSeed } from "./demo-seed";
import type { AppUser, DataStore } from "./types";

export const DEMO_EMAIL = "demo@cep.local";
export const DEMO_PASSWORD = "demo1234";

interface DemoUser extends AppUser {
  password: string;
}
interface DemoDB {
  users: DemoUser[];
  session: string | null;
  seeded: string[];
  studies: Study[];
  datasets: Dataset[];
  control_limits: ControlLimitsRow[];
  analyses: Analysis[];
  sampling_plans: SamplingPlan[];
}

const KEY = "cep-demo-v1";
const empty = (): DemoDB => ({
  users: [],
  session: null,
  seeded: [],
  studies: [],
  datasets: [],
  control_limits: [],
  analyses: [],
  sampling_plans: [],
});

let memory: DemoDB | null = null;
const listeners = new Set<(u: AppUser | null) => void>();

function load(): DemoDB {
  if (memory) return memory;
  try {
    const raw = window.localStorage.getItem(KEY);
    memory = raw ? { ...empty(), ...(JSON.parse(raw) as DemoDB) } : empty();
  } catch {
    memory = empty();
  }
  return memory;
}

function save() {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(memory));
  } catch {
    // Sin localStorage (modo privado, cuota): la demostración sigue en memoria.
  }
}

const uid = () => crypto.randomUUID();
const stamp = () => new Date().toISOString();

function currentUserId(): string {
  const id = load().session;
  if (!id) throw new Error("Tu sesión expiró. Inicia sesión de nuevo.");
  return id;
}

function publicUser(u: DemoUser | undefined): AppUser | null {
  return u ? { id: u.id, email: u.email } : null;
}

function notify() {
  const db = load();
  const user = publicUser(db.users.find((u) => u.id === db.session));
  listeners.forEach((l) => l(user));
}

function seedFor(userId: string) {
  const db = load();
  if (db.seeded.includes(userId)) return;
  db.seeded.push(userId);
  for (const s of buildSeed()) {
    const study: Study = { ...s.study, id: uid(), user_id: userId, created_at: stamp(), updated_at: stamp() };
    db.studies.push(study);
    for (const d of s.datasets) {
      db.datasets.push({ ...d, id: uid(), user_id: userId, study_id: study.id, created_at: stamp() });
    }
  }
  save();
}

const mine = <T extends { user_id: string }>(rows: T[]) => {
  const id = currentUserId();
  return rows.filter((r) => r.user_id === id);
};

export function createDemoStore(): DataStore {
  return {
    mode: "demo",
    auth: {
      async getUser() {
        const db = load();
        return publicUser(db.users.find((u) => u.id === db.session));
      },
      async signUp(email, password) {
        const db = load();
        const mail = email.trim().toLowerCase();
        if (db.users.some((u) => u.email === mail)) throw new Error("Ya existe una cuenta con ese correo.");
        const user: DemoUser = { id: uid(), email: mail, password };
        db.users.push(user);
        db.session = user.id;
        save();
        seedFor(user.id);
        notify();
        return { user: publicUser(user), needsConfirmation: false };
      },
      async signIn(email, password) {
        const db = load();
        const mail = email.trim().toLowerCase();
        let user = db.users.find((u) => u.email === mail);
        if (!user && mail === DEMO_EMAIL && password === DEMO_PASSWORD) {
          user = { id: uid(), email: mail, password };
          db.users.push(user);
        }
        if (!user || user.password !== password) throw new Error("Correo o contraseña incorrectos.");
        db.session = user.id;
        save();
        seedFor(user.id);
        notify();
        return publicUser(user)!;
      },
      async signOut() {
        load().session = null;
        save();
        notify();
      },
      onChange(cb) {
        listeners.add(cb);
        return () => listeners.delete(cb);
      },
      async getAccessToken() {
        return load().session ? "demo-token" : null;
      },
    },
    studies: {
      async list() {
        return mine(load().studies).sort((a, b) => b.created_at.localeCompare(a.created_at));
      },
      async get(id) {
        return mine(load().studies).find((s) => s.id === id) ?? null;
      },
      async create(input) {
        const study: Study = { ...input, id: uid(), user_id: currentUserId(), created_at: stamp(), updated_at: stamp() };
        if (study.lsl != null && study.usl != null && study.lsl >= study.usl)
          throw new Error("El límite inferior (LSL) debe ser menor que el superior (USL).");
        load().studies.push(study);
        save();
        return study;
      },
      async update(id, patch) {
        const study = mine(load().studies).find((s) => s.id === id);
        if (!study) throw new Error("Estudio no encontrado.");
        const next = { ...study, ...patch };
        if (next.lsl != null && next.usl != null && next.lsl >= next.usl)
          throw new Error("El límite inferior (LSL) debe ser menor que el superior (USL).");
        Object.assign(study, patch, { updated_at: stamp() });
        save();
        return study;
      },
      async remove(id) {
        const db = load();
        db.studies = db.studies.filter((s) => s.id !== id || s.user_id !== currentUserId());
        // Borrado en cascada, como en la base de datos real.
        db.datasets = db.datasets.filter((d) => d.study_id !== id);
        db.control_limits = db.control_limits.filter((d) => d.study_id !== id);
        db.analyses = db.analyses.filter((d) => d.study_id !== id);
        db.sampling_plans = db.sampling_plans.filter((d) => d.study_id !== id);
        save();
      },
    },
    datasets: {
      async list(studyId) {
        return mine(load().datasets)
          .filter((d) => d.study_id === studyId)
          .sort((a, b) => a.created_at.localeCompare(b.created_at));
      },
      async get(id) {
        return mine(load().datasets).find((d) => d.id === id) ?? null;
      },
      async create(input) {
        const row: Dataset = { ...input, id: uid(), user_id: currentUserId(), created_at: stamp() };
        load().datasets.push(row);
        save();
        return row;
      },
      async remove(id) {
        const db = load();
        db.datasets = db.datasets.filter((d) => d.id !== id || d.user_id !== currentUserId());
        db.control_limits.forEach((c) => {
          if (c.dataset_id === id) c.dataset_id = null;
        });
        db.analyses.forEach((c) => {
          if (c.dataset_id === id) c.dataset_id = null;
        });
        save();
      },
    },
    controlLimits: {
      async listActive(studyId) {
        return mine(load().control_limits).filter((c) => c.study_id === studyId && c.is_active);
      },
      async freeze(input) {
        const db = load();
        const user = currentUserId();
        db.control_limits.forEach((c) => {
          if (c.user_id === user && c.study_id === input.study_id && c.chart_type === input.chart_type) c.is_active = false;
        });
        const row: ControlLimitsRow = { ...input, id: uid(), user_id: user, is_active: true, created_at: stamp() };
        db.control_limits.push(row);
        save();
        return row;
      },
    },
    analyses: {
      async list(studyId) {
        return mine(load().analyses)
          .filter((a) => a.study_id === studyId)
          .sort((a, b) => a.created_at.localeCompare(b.created_at));
      },
      async create(input) {
        const row: Analysis = { ...input, id: uid(), user_id: currentUserId(), created_at: stamp() };
        load().analyses.push(row);
        save();
        return row;
      },
      async setInReport(id, inReport) {
        const a = mine(load().analyses).find((x) => x.id === id);
        if (a) a.in_report = inReport;
        save();
      },
      async remove(id) {
        const db = load();
        db.analyses = db.analyses.filter((a) => a.id !== id || a.user_id !== currentUserId());
        save();
      },
    },
    samplingPlans: {
      async list(studyId) {
        return mine(load().sampling_plans)
          .filter((p) => p.study_id === studyId)
          .sort((a, b) => a.created_at.localeCompare(b.created_at));
      },
      async create(input) {
        const row: SamplingPlan = { ...input, id: uid(), user_id: currentUserId(), created_at: stamp() };
        load().sampling_plans.push(row);
        save();
        return row;
      },
      async remove(id) {
        const db = load();
        db.sampling_plans = db.sampling_plans.filter((p) => p.id !== id || p.user_id !== currentUserId());
        save();
      },
    },
  };
}

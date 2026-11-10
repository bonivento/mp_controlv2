// Implementación real: supabase-js con la clave pública y el JWT del usuario.
// Las tablas tienen RLS (user_id = auth.uid()); user_id lo pone la base por
// defecto, por eso nunca se envía desde aquí.

import { createBrowserClient } from "@supabase/ssr";
import type { SupabaseClient, User } from "@supabase/supabase-js";
import { SUPABASE_ANON_KEY, SUPABASE_URL } from "../env";
import type {
  Analysis,
  ControlLimitsRow,
  Dataset,
  SamplingPlan,
  Study,
} from "../db-provisional";
import type { AppUser, DataStore } from "./types";

let client: SupabaseClient | null = null;

export function getSupabase(): SupabaseClient {
  if (!client) client = createBrowserClient(SUPABASE_URL, SUPABASE_ANON_KEY);
  return client;
}

function toUser(u: User | null | undefined): AppUser | null {
  return u ? { id: u.id, email: u.email ?? "" } : null;
}

function fail(error: { message: string } | null, fallback: string): never {
  throw new Error(error?.message ? `${fallback}: ${error.message}` : fallback);
}

export function createSupabaseStore(): DataStore {
  const sb = getSupabase();

  return {
    mode: "supabase",
    auth: {
      async getUser() {
        const { data } = await sb.auth.getSession();
        return toUser(data.session?.user);
      },
      async signUp(email, password) {
        const { data, error } = await sb.auth.signUp({ email, password });
        if (error) fail(error, "No se pudo crear la cuenta");
        return { user: toUser(data.session?.user), needsConfirmation: !data.session };
      },
      async signIn(email, password) {
        const { data, error } = await sb.auth.signInWithPassword({ email, password });
        if (error || !data.user) fail(error, "No se pudo iniciar sesión");
        return toUser(data.user)!;
      },
      async signOut() {
        const { error } = await sb.auth.signOut();
        if (error) fail(error, "No se pudo cerrar la sesión");
      },
      onChange(cb) {
        const { data } = sb.auth.onAuthStateChange((_e, session) => cb(toUser(session?.user)));
        return () => data.subscription.unsubscribe();
      },
      async getAccessToken() {
        const { data } = await sb.auth.getSession();
        return data.session?.access_token ?? null;
      },
    },
    studies: {
      async list() {
        const { data, error } = await sb.from("studies").select("*").order("created_at", { ascending: false });
        if (error) fail(error, "No se pudieron leer los estudios");
        return data as Study[];
      },
      async get(id) {
        const { data, error } = await sb.from("studies").select("*").eq("id", id).maybeSingle();
        if (error) fail(error, "No se pudo leer el estudio");
        return data as Study | null;
      },
      async create(input) {
        const { data, error } = await sb.from("studies").insert(input).select().single();
        if (error) fail(error, "No se pudo crear el estudio");
        return data as Study;
      },
      async update(id, patch) {
        const { data, error } = await sb.from("studies").update(patch).eq("id", id).select().single();
        if (error) fail(error, "No se pudo guardar el estudio");
        return data as Study;
      },
      async remove(id) {
        const { error } = await sb.from("studies").delete().eq("id", id);
        if (error) fail(error, "No se pudo eliminar el estudio");
      },
    },
    datasets: {
      async list(studyId) {
        const { data, error } = await sb.from("datasets").select("*").eq("study_id", studyId).order("created_at");
        if (error) fail(error, "No se pudieron leer los conjuntos de datos");
        return data as Dataset[];
      },
      async get(id) {
        const { data, error } = await sb.from("datasets").select("*").eq("id", id).maybeSingle();
        if (error) fail(error, "No se pudo leer el conjunto de datos");
        return data as Dataset | null;
      },
      async create(input) {
        const { data, error } = await sb.from("datasets").insert(input).select().single();
        if (error) fail(error, "No se pudo guardar el conjunto de datos");
        return data as Dataset;
      },
      async remove(id) {
        const { error } = await sb.from("datasets").delete().eq("id", id);
        if (error) fail(error, "No se pudo eliminar el conjunto de datos");
      },
    },
    controlLimits: {
      async listActive(studyId) {
        const { data, error } = await sb
          .from("control_limits")
          .select("*")
          .eq("study_id", studyId)
          .eq("is_active", true);
        if (error) fail(error, "No se pudieron leer los límites congelados");
        return data as ControlLimitsRow[];
      },
      async freeze(input) {
        // Solo puede haber un juego vigente por estudio y tipo (índice único parcial).
        const off = await sb
          .from("control_limits")
          .update({ is_active: false })
          .eq("study_id", input.study_id)
          .eq("chart_type", input.chart_type)
          .eq("is_active", true);
        if (off.error) fail(off.error, "No se pudieron reemplazar los límites vigentes");
        const { data, error } = await sb.from("control_limits").insert({ ...input, is_active: true }).select().single();
        if (error) fail(error, "No se pudieron congelar los límites");
        return data as ControlLimitsRow;
      },
    },
    analyses: {
      async list(studyId) {
        const { data, error } = await sb.from("analyses").select("*").eq("study_id", studyId).order("created_at");
        if (error) fail(error, "No se pudieron leer los análisis");
        return data as Analysis[];
      },
      async create(input) {
        const { data, error } = await sb.from("analyses").insert(input).select().single();
        if (error) fail(error, "No se pudo guardar el análisis");
        return data as Analysis;
      },
      async setInReport(id, inReport) {
        const { error } = await sb.from("analyses").update({ in_report: inReport }).eq("id", id);
        if (error) fail(error, "No se pudo actualizar el análisis");
      },
      async remove(id) {
        const { error } = await sb.from("analyses").delete().eq("id", id);
        if (error) fail(error, "No se pudo eliminar el análisis");
      },
    },
    samplingPlans: {
      async list(studyId) {
        const { data, error } = await sb.from("sampling_plans").select("*").eq("study_id", studyId).order("created_at");
        if (error) fail(error, "No se pudieron leer los planes de muestreo");
        return data as SamplingPlan[];
      },
      async create(input) {
        const { data, error } = await sb.from("sampling_plans").insert(input).select().single();
        if (error) fail(error, "No se pudo guardar el plan");
        return data as SamplingPlan;
      },
      async remove(id) {
        const { error } = await sb.from("sampling_plans").delete().eq("id", id);
        if (error) fail(error, "No se pudo eliminar el plan");
      },
    },
  };
}

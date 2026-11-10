import { DEMO_MODE, SUPABASE_READY } from "../env";
import { createDemoStore } from "./demo-store";
import { createSupabaseStore } from "./supabase-store";
import type { DataStore } from "./types";

let store: DataStore | null = null;

/** Almacén de datos y sesión según el entorno. Solo se usa en el navegador. */
export function getStore(): DataStore {
  if (!store) {
    if (SUPABASE_READY) store = createSupabaseStore();
    else if (DEMO_MODE) store = createDemoStore();
    else throw new Error("Falta configurar Supabase o el modo de demostración (ver web/.env.example).");
  }
  return store;
}

export type { AppUser, DataStore } from "./types";

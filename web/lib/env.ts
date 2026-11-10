// Lectura central de las variables de entorno públicas. Next las sustituye al
// compilar, por eso cada una se referencia con su nombre literal.

export const DEMO_MODE = process.env.NEXT_PUBLIC_DEMO_MODE === "1";
export const API_MOCK = process.env.NEXT_PUBLIC_API_MOCK === "1";
export const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
export const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";

/** Hay credenciales de Supabase y no se pidió el modo de demostración. */
export const SUPABASE_READY = !DEMO_MODE && SUPABASE_URL !== "" && SUPABASE_ANON_KEY !== "";

/** Sin demostración ni Supabase la aplicación no puede guardar nada. */
export const NOT_CONFIGURED = !DEMO_MODE && !SUPABASE_READY;

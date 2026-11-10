// Corre migraciones + stub + pruebas en PGlite (Postgres en WASM), sin Docker.
// Uso:  node supabase/tests/run-local.mjs   (requiere `npm i @electric-sql/pglite` en un directorio
// que Node resuelva, p. ej. NODE_PATH=<dir>/node_modules)
import { PGlite } from "@electric-sql/pglite";
import { pgcrypto } from "@electric-sql/pglite/contrib/pgcrypto";
import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const db = new PGlite({ extensions: { pgcrypto } });
db.onNotice?.((n) => console.log("  " + n.message));
const run = (f) => db.exec(readFileSync(f, "utf8"));
const withSeed = process.argv.includes("--seed");

await db.exec("create schema if not exists extensions; create extension if not exists pgcrypto with schema extensions;");
await run(join(root, "tests/00_stub_supabase.sql"));
for (const m of readdirSync(join(root, "migrations")).sort()) {
  console.log("migración", m);
  await run(join(root, "migrations", m));
}
if (withSeed) {
  await run(join(root, "seed.sql"));
  console.log("seed ok:", (await db.query("select count(*)::int n from public.studies where is_synthetic")).rows[0]);
}
await run(join(root, "tests/aislamiento.sql"));
console.log("TODAS LAS PRUEBAS PASARON");

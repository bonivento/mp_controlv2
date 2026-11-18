// Cargador mínimo para ejecutar módulos .ts del proyecto con Node (sin empaquetador):
// resuelve especificadores relativos sin extensión y el alias "@/". Solo para scripts de prueba.
import { existsSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

export async function resolve(specifier, context, next) {
  let target = null;
  if (specifier.startsWith("@/")) target = path.join(root, specifier.slice(2));
  else if ((specifier.startsWith("./") || specifier.startsWith("../")) && context.parentURL) target = path.resolve(path.dirname(fileURLToPath(context.parentURL)), specifier);
  if (target && !path.extname(target)) {
    for (const ext of [".ts", "/index.ts"]) {
      if (existsSync(target + ext)) return next(pathToFileURL(target + ext).href, context);
    }
  }
  return next(specifier, context);
}

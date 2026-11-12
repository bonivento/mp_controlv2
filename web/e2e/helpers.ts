import { expect, type Page, type BrowserContext } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

export const ROOT = path.resolve(__dirname, "../..");
export const EJEMPLOS = path.join(ROOT, "data", "ejemplos");
export const CAPTURAS = path.join(ROOT, "docs", "capturas");
export const AUTH_DIR = path.join(__dirname, ".auth");
const STATE_FILE = path.join(AUTH_DIR, "state.json");

export const PASSWORD = "E2e-Prueba-2026!";

export interface E2EState {
  stamp: string;
  userA: { email: string; password: string };
  userB: { email: string; password: string };
  studyVar?: { id: string; name: string };
  studyAttr?: { id: string; name: string };
  studyIso?: { id: string; name: string };
  createdStudies: string[];
}

export function readState(): E2EState | null {
  try {
    return JSON.parse(fs.readFileSync(STATE_FILE, "utf8"));
  } catch {
    return null;
  }
}
export function writeState(s: E2EState) {
  fs.mkdirSync(AUTH_DIR, { recursive: true });
  fs.writeFileSync(STATE_FILE, JSON.stringify(s, null, 2));
}
export function updateState(patch: Partial<E2EState>) {
  const s = readState();
  if (!s) throw new Error("Falta e2e/.auth/state.json: corre primero 01-sesion.spec.ts");
  writeState({ ...s, ...patch });
  return { ...s, ...patch } as E2EState;
}
export function trackStudy(name: string) {
  const s = readState()!;
  writeState({ ...s, createdStudies: [...s.createdStudies, name] });
}
export const authFile = (u: "a" | "b") => path.join(AUTH_DIR, `user-${u}.json`);

/** Captura de pantalla de escritorio para el manual de usuario. */
export async function shot(page: Page, name: string, fullPage = true) {
  fs.mkdirSync(CAPTURAS, { recursive: true });
  await page.waitForTimeout(600); // deja terminar animaciones de Plotly
  await page.screenshot({ path: path.join(CAPTURAS, name), fullPage });
}

export async function signIn(page: Page, email: string, password: string) {
  await page.goto("/login");
  await page.getByLabel("Correo electrónico").fill(email);
  await page.getByLabel("Contraseña").fill(password);
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page).toHaveURL(/\/estudios$/);
}

export async function saveAuth(context: BrowserContext, u: "a" | "b") {
  fs.mkdirSync(AUTH_DIR, { recursive: true });
  await context.storageState({ path: authFile(u) });
}

export async function createStudy(
  page: Page,
  o: { name: string; type?: "variable" | "attribute"; lsl?: number; usl?: number; target?: number; synthetic?: boolean },
) {
  await page.goto("/estudios/nuevo");
  await page.getByLabel("Nombre del estudio *").fill(o.name);
  await page.getByLabel("Empresa", { exact: true }).fill("Empresa sintética E2E");
  await page.getByLabel("Proceso", { exact: true }).fill("Llenado de envases de 500 g");
  await page.getByLabel("Característica de calidad", { exact: true }).fill("Peso neto");
  await page.getByLabel("Unidad de medida", { exact: true }).fill("g");
  if (o.type === "attribute") await page.getByLabel("Tipo de dato", { exact: true }).selectOption("attribute");
  else {
    if (o.lsl != null) await page.getByLabel("LSL (límite inferior)", { exact: true }).fill(String(o.lsl));
    if (o.usl != null) await page.getByLabel("USL (límite superior)", { exact: true }).fill(String(o.usl));
    if (o.target != null) await page.getByLabel("Objetivo", { exact: true }).fill(String(o.target));
  }
  if (o.synthetic !== false) await page.getByRole("checkbox", { name: /^Datos sintéticos/ }).check();
  await page.getByRole("button", { name: "Crear estudio" }).click();
  await expect(page).toHaveURL(/\/estudios\/[0-9a-f-]{36}$/);
  const id = page.url().split("/").pop()!;
  trackStudy(o.name);
  return id;
}

/**
 * Carga un archivo en el módulo Datos. Las columnas se detectan solas (x1..xn o la
 * columna `subgrupo`); `config` ajusta lo que haga falta. Devuelve cuando el conjunto quedó guardado.
 */
export async function uploadDataset(
  page: Page,
  studyId: string,
  o: {
    file: string; // nombre dentro de data/ejemplos (con extensión) o ruta absoluta
    phase: "I" | "II";
    justification?: string;
    config?: (page: Page) => Promise<void>;
    expectSaved?: boolean;
  },
) {
  await page.goto(`/estudios/${studyId}/datos`);
  const file = path.isAbsolute(o.file) ? o.file : path.join(EJEMPLOS, o.file);
  await page.getByLabel("Archivo CSV o Excel (.xlsx)").setInputFiles(file);
  await expect(page.getByRole("table", { name: "Columnas detectadas en la hoja" })).toBeVisible();
  if (o.config) await o.config(page);
  await page
    .getByLabel("Justificación del subgrupo racional (obligatoria)")
    .fill(o.justification ?? "Observaciones consecutivas de la misma línea y turno, tomadas en condiciones similares.");
  await expect(page.getByRole("heading", { name: "3. Resumen y limpieza" })).toBeVisible();
  await page.getByRole("radio", { name: new RegExp(`^Fase ${o.phase}:`) }).check();
  if (o.expectSaved === false) return;
  await page.getByRole("button", { name: "Guardar conjunto de datos" }).click();
  await expect(page.getByText("Conjunto de datos guardado")).toBeVisible();
}

/** Lee un CSV simple (separador coma, sin comillas) como matriz de texto. */
export function readCsv(name: string): { header: string[]; rows: string[][] } {
  const text = fs.readFileSync(path.join(EJEMPLOS, name), "utf8").trim().split(/\r?\n/);
  const header = text[0].split(",");
  return { header, rows: text.slice(1).map((l) => l.split(",")) };
}

/** Media de los promedios de cada subgrupo (columnas x1..xn) y R-barra de un CSV ancho. */
export function xbarStats(name: string, exclude: number[] = []) {
  const { header, rows } = readCsv(name);
  const xi = header.map((h, i) => (/^x\d+$/.test(h) ? i : -1)).filter((i) => i >= 0);
  const si = header.indexOf("subgrupo");
  const kept = rows.filter((r) => !exclude.includes(Number(r[si])));
  const means = kept.map((r) => xi.reduce((a, i) => a + Number(r[i]), 0) / xi.length);
  const ranges = kept.map((r) => {
    const v = xi.map((i) => Number(r[i]));
    return Math.max(...v) - Math.min(...v);
  });
  const grand = means.reduce((a, b) => a + b, 0) / means.length;
  const rbar = ranges.reduce((a, b) => a + b, 0) / ranges.length;
  return { grand, rbar, count: kept.length, n: xi.length };
}

/** Número en formato es-CO ("1.234,56" o "498,34") a number. */
export function num(text: string): number {
  return Number(text.replace(/\s/g, "").replace(/\./g, "").replace(",", "."));
}

/** Línea CSV con campos entre comillas ("500,8"). */
function splitCsvLine(line: string): string[] {
  const out: string[] = [];
  let cur = "";
  let q = false;
  for (const ch of line) {
    if (ch === '"') q = !q;
    else if (ch === "," && !q) {
      out.push(cur);
      cur = "";
    } else cur += ch;
  }
  out.push(cur);
  return out;
}

/**
 * Media general y R-barra de sintetico_sucio.csv con el tratamiento que pide el README: coma decimal
 * leída como punto, celdas vacías o "N/D" fuera, y los subgrupos indicados retirados.
 */
export function xbarStatsSucio(exclude: number[]) {
  const lines = fs.readFileSync(path.join(EJEMPLOS, "sintetico_sucio.csv"), "utf8").trim().split(/\r?\n/).slice(1);
  const kept = lines
    .map(splitCsvLine)
    .filter((r) => !exclude.includes(Number(r[2])))
    .map((r) => r.slice(3).map((v) => Number(v.replace(",", "."))));
  expect(kept.every((v) => v.length === 5 && v.every((x) => Number.isFinite(x)))).toBe(true);
  const means = kept.map((v) => v.reduce((a, b) => a + b, 0) / 5);
  const rbar = kept.map((v) => Math.max(...v) - Math.min(...v)).reduce((a, b) => a + b, 0) / kept.length;
  return { grand: means.reduce((a, b) => a + b, 0) / means.length, rbar, count: kept.length };
}

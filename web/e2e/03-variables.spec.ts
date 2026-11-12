import { test, expect, type Page, type Response } from "@playwright/test";
import fs from "node:fs";
import { execFileSync } from "node:child_process";
import path from "node:path";
import { ROOT, authFile, createStudy, num, readState, shot, updateState, uploadDataset, xbarStats } from "./helpers";

// Recorrido 3: flujo completo por variables con sintetico_fase1 y sintetico_fase2.
test.describe.configure({ mode: "serial" });
test.use({ storageState: authFile("a") });

const name = `E2E variables ${Date.now().toString(36)}`;
let studyId = "";
const D2_N5 = 2.326; // Montgomery, Apéndice VI

/** Espera la respuesta de la API de gráficos que dispara `action` y la devuelve ya leída. */
async function chartApi(page: Page, action: () => Promise<unknown>, match: (body: Record<string, unknown>) => boolean = () => true) {
  const [res] = await Promise.all([
    page.waitForResponse((r: Response) => {
      if (!r.url().includes("/api/charts/variables") || r.request().method() !== "POST") return false;
      try {
        return match(JSON.parse(r.request().postData() ?? "{}"));
      } catch {
        return false;
      }
    }),
    action(),
  ]);
  expect(res.status()).toBe(200);
  return (await res.json()) as {
    in_control: boolean;
    out_of_control_points: number[];
    limits: { params: Record<string, number>; points_used: number };
    charts: { name: string; center: number[]; ucl: number[]; lcl: number[]; labels: string[] }[];
    interpretation: { summary: string; findings: string[]; warnings: string[] };
  };
}

/** D5: los textos de la API usan coma decimal ("501,982"), igual que la interfaz. */
const sinPuntoDecimal = (i: { summary: string; findings: string[]; warnings: string[] }) =>
  expect([i.summary, ...i.findings, ...i.warnings].join(" ")).not.toMatch(/\d\.\d/);

const param = (page: Page, label: string) =>
  page.locator("dt", { hasText: label }).locator("xpath=following-sibling::dd").first();

async function goVariables(page: Page) {
  await page.goto(`/estudios/${studyId}/variables`);
  await expect(page.getByRole("tablist", { name: "Fase del análisis" })).toBeVisible();
}

test("R3.1 crear el estudio y cargar Fase I y Fase II", async ({ page }) => {
  studyId = await createStudy(page, { name, lsl: 495, usl: 505, target: 500 });
  updateState({ studyVar: { id: studyId, name } });

  await uploadDataset(page, studyId, {
    file: "sintetico_fase1.csv",
    phase: "I",
    expectSaved: false,
    justification: "Cinco envases consecutivos de la misma línea de llenado y del mismo turno forman un subgrupo.",
  });
  // Lo que ve el usuario antes de guardar: columnas detectadas, formato ancho x1..x5, resumen.
  const cols = page.getByRole("table", { name: "Columnas detectadas en la hoja" });
  for (const c of ["fecha", "turno", "subgrupo", "x1", "x5"]) await expect(cols.getByRole("cell", { name: c, exact: true })).toBeVisible();
  await expect(page.getByLabel("Formato de los datos")).toHaveValue("wide");
  await expect(page.getByRole("heading", { name: "Estadística descriptiva global" })).toBeVisible();
  await expect(page.getByRole("table", { name: "Resumen por subgrupo" }).locator("tbody tr")).toHaveCount(25);
  await shot(page, "03-datos-carga.png");
  await page.getByRole("button", { name: "Guardar conjunto de datos" }).click();
  await expect(page.getByText("Conjunto de datos guardado")).toBeVisible();

  await uploadDataset(page, studyId, { file: "sintetico_fase2.csv", phase: "II" });
  const tabla = page.getByRole("table", { name: "Conjuntos de datos guardados" });
  await expect(tabla.getByRole("row", { name: /sintetico_fase1.*Fase I.*25/ })).toBeVisible();
  await expect(tabla.getByRole("row", { name: /sintetico_fase2.*Fase II.*15/ })).toBeVisible();
});

test("R3.2 Fase I: límites de prueba, señal en el subgrupo 12 y línea central correcta", async ({ page }) => {
  studyId = readState()!.studyVar!.id;
  const all = xbarStats("sintetico_fase1.csv");
  const api = await chartApi(page, () => goVariables(page), (b) => b.phase === "I");

  await expect(page.getByText("FASE I — límites de prueba")).toBeVisible();
  sinPuntoDecimal(api.interpretation);
  await expect(page.getByText("◆ 1 punto(s) con señal")).toBeVisible();
  await expect(page.getByText("25 subgrupos usados en los límites")).toBeVisible();
  const sig = page.getByRole("table", { name: "Puntos con señal" });
  await expect(sig.locator("tbody tr")).toHaveCount(1);
  await expect(sig.locator("tbody tr").first().getByRole("cell").first()).toHaveText("12");

  // Valores, no solo presencia: la línea central de la pantalla = la de la API = la media del CSV.
  const xbar = api.charts[0];
  expect(xbar.center[0]).toBeCloseTo(all.grand, 6);
  await expect(param(page, "Media del proceso (μ)")).toHaveText(new RegExp(all.grand.toFixed(4).replace(".", ",")));
  expect(num((await param(page, "Rango medio de los subgrupos (R̄)").innerText()))).toBeCloseTo(all.rbar, 3);
  // Límites 3σ con A2 (n = 5): mu ± 0,577 R̄
  expect(xbar.ucl[0]).toBeCloseTo(all.grand + 0.577 * all.rbar, 2);
  expect(xbar.lcl[0]).toBeCloseTo(all.grand - 0.577 * all.rbar, 2);

  // La tabla de datos del gráfico muestra la misma línea central.
  await page.getByRole("button", { name: "Ver tabla de datos" }).first().click();
  const t = page.getByRole("table", { name: /^Datos de: .*X-barra/ });
  await expect(t).toBeVisible();
  await expect(t.locator("tbody tr").first().getByRole("cell").nth(3)).toHaveText(all.grand.toLocaleString("es-CO", { maximumFractionDigits: 4 }));
  await expect(t.locator("tbody tr").nth(11).getByRole("cell").nth(5)).toContainText("Señal");
  await page.getByRole("button", { name: "Ocultar tabla de datos" }).first().click();
  await shot(page, "04-variables-fase1.png");
});

test("R3.3 excluir el subgrupo 12 con causa, recalcular y congelar", async ({ page }) => {
  studyId = readState()!.studyVar!.id;
  await goVariables(page);
  await expect(page.getByText("◆ 1 punto(s) con señal")).toBeVisible();

  // Sin causa no se puede excluir.
  await page.getByRole("button", { name: "Excluir con causa…" }).click();
  await page.getByRole("button", { name: "Excluir y recalcular" }).click();
  await expect(page.getByText("La causa asignable es obligatoria")).toBeVisible();

  await page.getByLabel("Causa asignable (obligatoria)").fill("Boquilla obstruida en la llenadora, limpiada y verificada.");
  const api = await chartApi(page, () => page.getByRole("button", { name: "Excluir y recalcular" }).click(), (b) => Array.isArray(b.excluded) && b.excluded.length === 1);

  const kept = xbarStats("sintetico_fase1.csv", [12]);
  expect(kept.count).toBe(24);
  await expect(page.getByText("24 subgrupos usados en los límites")).toBeVisible();
  await expect(page.getByText("✓ Proceso bajo control")).toBeVisible();
  expect(api.charts[0].center[0]).toBeCloseTo(kept.grand, 6);
  expect(api.limits.params.r_bar).toBeCloseTo(kept.rbar, 6);
  // Valores esperados del README: límites ~498,1 y ~501,7 al excluir el subgrupo 12.
  expect(api.charts[0].lcl[0]).toBeGreaterThan(497.9);
  expect(api.charts[0].lcl[0]).toBeLessThan(498.4);
  expect(api.charts[0].ucl[0]).toBeGreaterThan(501.4);
  expect(api.charts[0].ucl[0]).toBeLessThan(501.9);
  await expect(param(page, "Media del proceso (μ)")).toHaveText(new RegExp(kept.grand.toFixed(4).replace(".", ",")));
  const ex = page.getByRole("table", { name: "Puntos excluidos con su causa asignable" });
  await expect(ex.getByRole("cell", { name: "Boquilla obstruida en la llenadora, limpiada y verificada." })).toBeVisible();
  await shot(page, "05-variables-excluir.png");

  // Congelar
  await page.getByRole("button", { name: "Congelar límites" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Congelar", exact: true }).click();
  await expect(page.getByText(/Ya puedes pasar a la Fase II/)).toBeVisible();
  await expect(page.getByText(/Hay límites vigentes congelados/)).toBeVisible();

  // Guardar el análisis de Fase I (lo usa Capacidad para saber si el proceso es estable).
  await page.getByRole("button", { name: "Guardar análisis" }).click();
  await page.getByRole("button", { name: "Confirmar y guardar" }).click();
  await expect(page.getByText(/Análisis «.*» guardado/)).toBeVisible();
});

test("R3.4 Fase II contra los límites congelados: 11 de 15 con señal y sin recalcular", async ({ page }) => {
  studyId = readState()!.studyVar!.id;
  const kept = xbarStats("sintetico_fase1.csv", [12]);
  await goVariables(page);
  const api = await chartApi(page, () => page.getByRole("tab", { name: /^Fase II/ }).click(), (b) => b.phase === "II");

  await expect(page.getByText(/FASE II — límites congelados el/)).toBeVisible();
  await expect(page.getByText("Los límites no se recalculan", { exact: true })).toBeVisible();
  await expect(page.getByText("◆ 11 punto(s) con señal")).toBeVisible();
  const sig = page.getByRole("table", { name: "Puntos con señal" });
  const labels = await sig.locator("tbody tr").evaluateAll((rows) => rows.map((r) => r.querySelector("td")!.textContent!.trim()));
  expect(labels).toEqual(["26", "28", "30", "31", "32", "33", "34", "35", "36", "38", "39"]);
  // Sin botón de excluir en Fase II
  await expect(page.getByRole("button", { name: "Excluir con causa…" })).toHaveCount(0);

  // Los límites son los congelados (24 subgrupos de Fase I), no los de los datos de Fase II.
  expect(api.charts[0].center[0]).toBeCloseTo(kept.grand, 6);
  expect(api.limits.points_used).toBe(24);
  const fase2 = xbarStats("sintetico_fase2.csv");
  expect(Math.abs(api.charts[0].center[0] - fase2.grand)).toBeGreaterThan(1); // la media de Fase II es otra
  await expect(page.getByText("24 subgrupos usados en los límites")).toBeVisible();
  await shot(page, "06-variables-fase2.png");

  await page.getByRole("button", { name: "Guardar análisis" }).click();
  await page.getByRole("button", { name: "Confirmar y guardar" }).click();
  await expect(page.getByText(/Análisis «.*» guardado/)).toBeVisible();
});

test("R3.5 supuestos", async ({ page }) => {
  studyId = readState()!.studyVar!.id;
  await page.goto(`/estudios/${studyId}/supuestos`);
  await page.getByLabel("Conjunto de datos").selectOption({ label: /sintetico_fase1/ as unknown as string }).catch(async () => {
    await page.getByLabel("Conjunto de datos").selectOption({ index: 0 });
  });
  const [resA] = await Promise.all([
    page.waitForResponse((r) => r.url().includes("/api/assumptions") && r.request().method() === "POST"),
    page.getByRole("button", { name: "Validar supuestos" }).click(),
  ]);
  sinPuntoDecimal(((await resA.json()) as { interpretation: { summary: string; findings: string[]; warnings: string[] } }).interpretation);
  await expect(page.getByRole("heading", { name: "Pruebas de normalidad" })).toBeVisible();
  await expect(page.getByRole("table", { name: "Pruebas de normalidad" }).locator("tbody tr").first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "Pruebas de independencia" })).toBeVisible();
  await expect(page.getByText("Gráfico Q-Q normal").first()).toBeVisible();
  await expect.poll(() => page.locator(".js-plotly-plot").count()).toBeGreaterThanOrEqual(3); // Q-Q, histograma y ACF dibujados
  await expect(page.getByText(/Normalidad: se sostiene|Normalidad: no se sostiene/)).toBeVisible();
  // D1: con límites congelados y el subgrupo 12 excluido, por defecto solo cuentan los 24 subgrupos retenidos
  // (24 x 5 = 120 observaciones) y la pantalla lo dice. "Usar todas las observaciones" devuelve las 125.
  const desc = page.locator("dt", { hasText: /^n$/ }).locator("xpath=following-sibling::dd");
  await expect(desc).toHaveText("120");
  // El texto aparece en "Datos que se usarán" y, tras calcular, en el encabezado de resultados.
  await expect(page.getByText(/120 de 125 observaciones, de 24 de 25 subgrupos; se excluyó el 12 por: Boquilla obstruida/).first()).toBeVisible();
  await shot(page, "08-supuestos.png");
  await page.getByRole("checkbox", { name: "Usar todas las observaciones" }).check();
  await expect(page.getByText(/125 observaciones \(todas; se incluyen los subgrupos excluidos en Fase I: 12\)/).first()).toBeVisible();
  await page.getByRole("button", { name: "Validar supuestos" }).click();
  await expect(desc).toHaveText("125");
  await page.getByRole("checkbox", { name: "Usar todas las observaciones" }).uncheck();
  await page.getByRole("button", { name: "Validar supuestos" }).click();
  await expect(desc).toHaveText("120");
  await page.getByRole("button", { name: "Guardar análisis" }).click();
  await page.getByRole("button", { name: "Confirmar y guardar" }).click();
  await expect(page.getByText(/Análisis «.*» guardado/)).toBeVisible();
});

test("R3.6 capacidad (D1): usa los 24 subgrupos retenidos y la sigma de Fase I, y lo dice", async ({ page }) => {
  studyId = readState()!.studyVar!.id;
  await page.goto(`/estudios/${studyId}/capacidad`);
  await page.getByLabel("Conjunto de datos").selectOption({ index: 0 });
  const dsName = await page.getByLabel("Conjunto de datos").locator("option:checked").innerText();
  expect(dsName).toContain("Fase I");
  // Antes de calcular, la pantalla dice qué datos usará.
  await expect(page.getByText(/24 de 25 subgrupos; se excluyó el 12 por: Boquilla obstruida.*; sigma de Fase I/).first()).toBeVisible();
  const [res] = await Promise.all([
    page.waitForResponse((r) => r.url().includes("/api/capability") && r.request().method() === "POST"),
    page.getByRole("button", { name: "Calcular capacidad" }).click(),
  ]);
  const api = (await res.json()) as { sigma_within: number; cp: { value: number; lower: number; upper: number }; cpk: { value: number; lower: number; upper: number }; interpretation: { summary: string; findings: string[]; warnings: string[] } };
  const idx = page.getByRole("table", { name: /Índices de capacidad/ });
  await expect(idx).toBeVisible();
  const cell = async (n: string, c = 1) => num(await idx.getByRole("row", { name: new RegExp(`^${n} `) }).getByRole("cell").nth(c).innerText());

  // Esperado independiente a partir del CSV: sigma = R-barra/d2 con los 24 subgrupos retenidos (sin el 12).
  const s = xbarStats("sintetico_fase1.csv", [12]);
  expect(s.count).toBe(24);
  const sigma = s.rbar / D2_N5;
  expect(sigma).toBeCloseTo(1.295, 3); // referencia entregada con la corrección de D1
  const lsl = 495, usl = 505;
  const cp = (usl - lsl) / (6 * sigma);
  const cpl = (s.grand - lsl) / (3 * sigma);
  const cpu = (usl - s.grand) / (3 * sigma);
  sinPuntoDecimal(api.interpretation);
  expect(api.sigma_within).toBeCloseTo(sigma, 4);
  expect(await cell("Cp")).toBeCloseTo(cp, 2);
  expect(await cell("Cpl")).toBeCloseTo(cpl, 2);
  expect(await cell("Cpu")).toBeCloseTo(cpu, 2);
  expect(await cell("Cpk")).toBeCloseTo(Math.min(cpl, cpu), 2);
  expect(await cell("Cp")).toBeCloseTo(1.287, 3);
  expect(await cell("Cpk")).toBeCloseTo(1.238, 3);
  // Intervalos con grados de libertad efectivos (referencia entregada): Cp 1,096 a 1,478; Cpk 1,044 a 1,431.
  expect(await cell("Cp", 2)).toBeCloseTo(1.096, 2);
  expect(await cell("Cp", 3)).toBeCloseTo(1.478, 2);
  expect(await cell("Cpk", 2)).toBeCloseTo(1.044, 2);
  expect(await cell("Cpk", 3)).toBeCloseTo(1.431, 2);
  // Pantalla = API
  expect(api.cp.value).toBeCloseTo(await cell("Cp"), 3);
  expect(api.cpk.upper).toBeCloseTo(await cell("Cpk", 3), 3);
  await expect(page.getByRole("table", { name: "Fracción no conforme esperada y observada" }).locator("tbody tr")).toHaveCount(3);
  await expect(page.getByText(/Capacidad Marginal/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "Interpretación" })).toBeVisible();
  // Con el análisis de control y el de supuestos guardados para estos mismos datos, no pide "guardarlos".
  await expect(page.getByText(/no hay un análisis de control guardado para estos mismos datos/)).toHaveCount(0);
  await shot(page, "09-capacidad.png");
  await page.getByRole("button", { name: "Guardar análisis" }).click();
  await page.getByRole("button", { name: "Confirmar y guardar" }).click();
  await expect(page.getByText(/Análisis «.*» guardado/)).toBeVisible();

  // "Calcular con todos los subgrupos": el subgrupo 12 vuelve a entrar y la sigma sube (el valor viejo, D1).
  await page.getByRole("checkbox", { name: "Calcular con todos los subgrupos" }).check();
  await expect(page.getByText(/25 de 25 subgrupos \(todos, sin la depuración de Fase I: se incluyen el 12\)/).first()).toBeVisible();
  await page.getByRole("button", { name: "Calcular capacidad" }).click();
  const all = xbarStats("sintetico_fase1.csv");
  const sigmaAll = all.rbar / D2_N5;
  expect(sigmaAll).toBeGreaterThan(sigma);
  await expect.poll(async () => await cell("Cpk")).toBeCloseTo(Math.min((all.grand - lsl) / (3 * sigmaAll), (usl - all.grand) / (3 * sigmaAll)), 2);
  expect(await cell("Cp")).toBeLessThan(cp);
});

test("R3.7 diseño de gráficos: ARL0, ARL1 y ATS", async ({ page }) => {
  studyId = readState()!.studyVar!.id;
  await page.goto(`/estudios/${studyId}/diseno`);
  await page.getByRole("button", { name: "Calcular", exact: true }).click();
  const card = (k: string) => page.locator("p", { hasText: new RegExp(`^${k}$`) }).locator("xpath=following-sibling::p[1]");
  // X-barra n=5, L=3, solo regla 1: ARL0 = 1/0,0027 = 370,4; ATS0 = 370,4 h con h = 1.
  expect(num(await card("ARL0").innerText())).toBeCloseTo(370.4, 1);
  expect(num((await card("ATS0").innerText()).replace(" h", ""))).toBeCloseTo(370.4, 1);
  const rows = page.getByRole("table", { name: "ARL1 y ATS1 por desplazamiento" }).locator("tbody tr");
  const row15 = rows.filter({ has: page.getByRole("cell", { name: "1,500", exact: true }) });
  // ARL1 en 1,5 σ con n = 5: β = Φ(3 - 1,5·√5) - Φ(-3 - 1,5·√5) = 0,3617 -> ARL1 = 1,567
  expect(num(await row15.getByRole("cell").nth(2).innerText())).toBeCloseTo(1.57, 1);
  await expect(page.getByRole("heading", { name: "Interpretación" })).toBeVisible();
  await shot(page, "10-diseno-arl.png");
  await page.getByRole("button", { name: "Guardar análisis" }).first().click();
  await page.getByRole("button", { name: "Confirmar y guardar" }).click();
  await expect(page.getByText(/Análisis «.*» guardado/)).toBeVisible();
});

test("R3.8 reporte y descarga del Excel", async ({ page }) => {
  studyId = readState()!.studyVar!.id;
  await page.goto(`/estudios/${studyId}/reporte`);
  const lista = page.getByRole("table", { name: "Análisis guardados" });
  await expect(lista).toBeVisible();
  const n = await lista.locator("tbody tr").count();
  expect(n).toBeGreaterThanOrEqual(5);
  for (const t of [/Gráficos de control por variables/, /Validación de supuestos/, /Capacidad del proceso/, /Diseño de gráficos/])
    await expect(lista.getByRole("cell", { name: t }).first()).toBeVisible();
  await expect(page.getByText(readState()!.studyVar!.name).first()).toBeVisible();
  await shot(page, "12-reporte.png");

  const [download] = await Promise.all([page.waitForEvent("download"), page.getByRole("button", { name: "Exportar a Excel" }).click()]);
  expect(download.suggestedFilename()).toMatch(/^reporte-.*\.xlsx$/);
  const file = path.join(__dirname, ".results", "reporte.xlsx");
  fs.mkdirSync(path.dirname(file), { recursive: true });
  await download.saveAs(file);
  const buf = fs.readFileSync(file);
  expect(buf.subarray(0, 2).toString()).toBe("PK"); // un .xlsx es un zip
  // Se abre con openpyxl (el de la API) y trae hojas con datos.
  const py = path.join(ROOT, "api", ".venv", "bin", "python");
  const out = execFileSync(py, ["-I", "-c", "import sys,openpyxl;wb=openpyxl.load_workbook(sys.argv[1]);print('|'.join(f'{ws.title}:{ws.max_row}' for ws in wb))", file]).toString().trim();
  expect(out.split("|").length).toBeGreaterThanOrEqual(2);
  test.info().annotations.push({ type: "excel", description: out });
});

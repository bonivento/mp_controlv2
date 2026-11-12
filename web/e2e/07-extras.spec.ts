import { test, expect, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { PASSWORD, authFile, createStudy, num, readState, shot, signIn, uploadDataset, xbarStats } from "./helpers";
import { readPdf } from "./pdf";

// Recorrido 8 (cobertura adicional): comparador de diseños, carga de XLSX hasta el final,
// flujo principal en pantalla de teléfono (390 px) e impresión del reporte a PDF.
test.describe.configure({ mode: "serial" });
test.use({ storageState: authFile("a") });

// Función de distribución normal estándar (Numerical Recipes, erfcc; error relativo < 1,2e-7).
function phi(x: number): number {
  const z = Math.abs(x) / Math.SQRT2;
  const t = 1 / (1 + 0.5 * z);
  const r =
    t *
    Math.exp(
      -z * z - 1.26551223 + t * (1.00002368 + t * (0.37409196 + t * (0.09678418 + t * (-0.18628806 + t * (0.27886807 + t * (-1.13520398 + t * (1.48851587 + t * (-0.82215223 + t * 0.17087277)))))))),
    );
  return x >= 0 ? 1 - r / 2 : r / 2;
}
/** ARL0 y ARL1 del gráfico X-barra con la regla 1 (un punto fuera de L sigmas) para un desplazamiento de delta sigmas. */
function arl(n: number, L: number, delta: number) {
  const arl0 = 1 / (2 * (1 - phi(L)));
  const beta = phi(L - delta * Math.sqrt(n)) - phi(-L - delta * Math.sqrt(n));
  return { arl0, arl1: 1 / (1 - beta) };
}

test("R8.1 comparador de diseños: 24 alternativas contra ARL0, ARL1, ATS y carga calculados aparte", async ({ page }) => {
  const id = readState()!.studyVar!.id;
  await page.goto(`/estudios/${id}/diseno`);
  await expect(page.getByText("Sin comparación todavía")).toBeVisible();
  // Por defecto: n = 3, 5, 7, 10; L = 2,5 y 3; h = 0,5, 1 y 2 horas; desplazamiento de 1 sigma.
  await page.getByRole("button", { name: "Comparar", exact: true }).click();
  const tabla = page.getByRole("table", { name: "Comparación de diseños" });
  await expect(tabla).toBeVisible();
  await expect(page.getByText("Diseños para detectar un desplazamiento de 1,00 σ")).toBeVisible();
  const rows = await tabla.locator("tbody tr").evaluateAll((trs) => trs.map((r) => [...r.querySelectorAll("td")].map((c) => c.textContent!.trim())));
  expect(rows).toHaveLength(24);
  const seen = new Set<string>();
  for (const r of rows) {
    const [n, L, h, arl0, ats0, arl1, ats1, load] = r.map(num);
    const e = arl(n, L, 1);
    seen.add(`${n}|${L}|${h}`);
    expect(arl0, `ARL0 n=${n} L=${L}`).toBeCloseTo(e.arl0, 0);
    expect(Math.abs(arl0 - e.arl0)).toBeLessThan(0.06); // la pantalla muestra un decimal
    expect(Math.abs(arl1 - e.arl1)).toBeLessThan(0.006); // y dos decimales
    expect(Math.abs(ats0 - e.arl0 * h)).toBeLessThan(0.06 * Math.max(h, 1) + 0.06);
    expect(Math.abs(ats1 - e.arl1 * h)).toBeLessThan(0.006 * h + 0.006);
    expect(load).toBeCloseTo(n / h, 1);
  }
  expect(seen.size).toBe(24); // todas las combinaciones, sin repetir
  // Valor conocido: n = 5, L = 3, h = 1 -> ARL0 = 370,4; ARL1(1σ) = 1/(1 - 0,0...) con el mismo cálculo
  const r531 = rows.find((r) => num(r[0]) === 5 && num(r[1]) === 3 && num(r[2]) === 1)!;
  expect(num(r531[3])).toBeCloseTo(370.4, 1);
  expect(num(r531[7])).toBeCloseTo(5, 2);
  await expect.poll(() => page.locator(".js-plotly-plot").count()).toBeGreaterThanOrEqual(1);
  await expect(page.getByText("Detección frente a carga de inspección").first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "Interpretación" }).last()).toBeVisible();

  // Cambiar las listas: 2 n x 1 L x 1 h = 2 filas, con otro desplazamiento.
  await page.getByLabel("Tamaños de muestra n").fill("4, 8");
  await page.getByLabel("Anchos L").fill("3");
  await page.getByLabel("Intervalos h (horas)").fill("1");
  await page.getByLabel("Desplazamiento a detectar (σ)").fill("2");
  await page.getByRole("button", { name: "Comparar", exact: true }).click();
  await expect(page.getByText("Diseños para detectar un desplazamiento de 2,00 σ")).toBeVisible();
  const rows2 = await tabla.locator("tbody tr").evaluateAll((trs) => trs.map((r) => [...r.querySelectorAll("td")].map((c) => c.textContent!.trim())));
  expect(rows2).toHaveLength(2);
  for (const r of rows2) expect(Math.abs(num(r[5]) - arl(num(r[0]), 3, 2).arl1)).toBeLessThan(0.006);
  expect(num(rows2[1][5])).toBeLessThan(num(rows2[0][5])); // más n detecta antes

  // Una lista inválida no calcula y lo explica.
  await page.getByLabel("Tamaños de muestra n").fill("cuatro");
  await page.getByRole("button", { name: "Comparar", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: /n|lista|número/i }).first()).toBeVisible();
  await shot(page, "10b-diseno-comparador.png");
});

test("R8.2 carga de un XLSX hasta el final: guardar, listar y graficar con la misma línea central", async ({ page }) => {
  const name = `E2E xlsx ${Date.now().toString(36)}`;
  const id = await createStudy(page, { name, lsl: 495, usl: 505, target: 500 });
  await uploadDataset(page, id, {
    file: "sintetico_fase1.xlsx",
    phase: "I",
    expectSaved: false,
    justification: "Cinco envases consecutivos de la misma línea de llenado y del mismo turno forman un subgrupo.",
  });
  // Columnas y formato detectados igual que con el CSV.
  const cols = page.getByRole("table", { name: "Columnas detectadas en la hoja" });
  for (const c of ["fecha", "turno", "subgrupo", "x1", "x5"]) await expect(cols.getByRole("cell", { name: c, exact: true })).toBeVisible();
  await expect(page.getByLabel("Formato de los datos")).toHaveValue("wide");
  await expect(page.getByRole("table", { name: "Resumen por subgrupo" }).locator("tbody tr")).toHaveCount(25);
  await page.getByRole("button", { name: "Guardar conjunto de datos" }).click();
  await expect(page.getByText("Conjunto de datos guardado")).toBeVisible();
  const tabla = page.getByRole("table", { name: "Conjuntos de datos guardados" });
  await expect(tabla.getByRole("row", { name: /sintetico_fase1.*Fase I.*25.*sintetico_fase1\.xlsx/ })).toBeVisible();

  // Se recarga la página (los datos vienen de la base, no de la memoria) y se grafica.
  const [res] = await Promise.all([
    page.waitForResponse((r) => r.url().includes("/api/charts/variables") && r.request().method() === "POST"),
    page.goto(`/estudios/${id}/variables`),
  ]);
  expect(res.status()).toBe(200);
  const api = (await res.json()) as { charts: { center: number[] }[]; out_of_control_points: number[] };
  const csv = xbarStats("sintetico_fase1.csv"); // mismo archivo en CSV: misma línea central
  expect(api.charts[0].center[0]).toBeCloseTo(csv.grand, 6);
  await expect(page.getByText("25 subgrupos usados en los límites")).toBeVisible();
  await expect(page.getByText("◆ 1 punto(s) con señal")).toBeVisible();
});

// ---------------------------------------------------------------------------------------------
// Móvil (390 px): se evita el desborde horizontal de la página y se recorre el flujo principal.
// ---------------------------------------------------------------------------------------------
async function sinDesborde(page: Page, donde: string) {
  const m = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth, iw: window.innerWidth }));
  expect(m.sw, `${donde}: la página se desborda horizontalmente (${m.sw} > ${m.cw})`).toBeLessThanOrEqual(m.iw + 1);
}

test("R8.3 flujo principal en un teléfono de 390 px de ancho", async ({ browser }) => {
  const st = readState()!;
  // Contexto limpio (sin la sesión guardada): el inicio de sesión también se prueba en el teléfono.
  const ctx = await browser.newContext({
    storageState: { cookies: [], origins: [] },
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 2,
    isMobile: true,
    hasTouch: true,
    locale: "es-CO",
    acceptDownloads: true,
  });
  const page = await ctx.newPage();
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  try {
    // Inicio de sesión
    await page.goto("/login");
    await sinDesborde(page, "login");
    await signIn(page, st.userA.email, st.userA.password || PASSWORD);
    await sinDesborde(page, "lista de estudios");

    // Crear estudio
    const name = `E2E móvil ${Date.now().toString(36)}`;
    await page.goto("/estudios/nuevo");
    await sinDesborde(page, "estudio nuevo");
    const id = await createStudy(page, { name, lsl: 495, usl: 505, target: 500 });
    await sinDesborde(page, "inicio del estudio");

    // Cargar archivo y guardar (Fase I)
    await uploadDataset(page, id, { file: "sintetico_fase1.csv", phase: "I", expectSaved: false });
    await sinDesborde(page, "datos (carga)");
    await page.getByRole("button", { name: "Guardar conjunto de datos" }).click();
    await expect(page.getByText("Conjunto de datos guardado")).toBeVisible();
    await sinDesborde(page, "datos (guardado)");

    // Gráficos: la señal del subgrupo 12 y el gráfico dentro de la pantalla
    await page.goto(`/estudios/${id}/variables`);
    await expect(page.getByText("◆ 1 punto(s) con señal")).toBeVisible();
    await expect.poll(() => page.locator(".js-plotly-plot").count()).toBeGreaterThanOrEqual(2);
    const anchos = await page.locator(".js-plotly-plot").evaluateAll((els) => els.map((e) => e.getBoundingClientRect().right));
    for (const r of anchos) expect(r).toBeLessThanOrEqual(391);
    await sinDesborde(page, "variables Fase I");
    await page.locator(".js-plotly-plot").first().scrollIntoViewIfNeeded();
    await shot(page, "13-movil-variables.png", false);

    // Excluir con causa desde el teléfono: el diálogo cabe en la pantalla
    await page.getByRole("button", { name: "Excluir con causa…" }).click();
    const dlg = page.getByRole("dialog");
    await expect(dlg).toBeVisible();
    const box = await dlg.boundingBox();
    expect(box!.x).toBeGreaterThanOrEqual(-1);
    expect(box!.x + box!.width).toBeLessThanOrEqual(391);
    await page.getByLabel("Causa asignable (obligatoria)").fill("Boquilla obstruida en la llenadora, limpiada y verificada.");
    await page.getByRole("button", { name: "Excluir y recalcular" }).click();
    await expect(page.getByText("24 subgrupos usados en los límites")).toBeVisible();
    await expect(page.getByText("✓ Proceso bajo control")).toBeVisible();
    await sinDesborde(page, "variables tras excluir");

    // Capacidad y reporte se leen sin desborde
    await page.goto(`/estudios/${id}/capacidad`);
    await page.getByRole("button", { name: "Calcular capacidad" }).click();
    await expect(page.getByRole("table", { name: /Índices de capacidad/ })).toBeVisible();
    await sinDesborde(page, "capacidad");
    await page.goto(`/estudios/${id}/reporte`);
    await expect(page.getByRole("heading", { name: "Reporte", exact: true })).toBeVisible();
    await sinDesborde(page, "reporte");
    expect(errors).toEqual([]);
  } finally {
    await ctx.close();
  }
});

// ---------------------------------------------------------------------------------------------
// Impresión del reporte a PDF.
// ---------------------------------------------------------------------------------------------
test("R8.4 el reporte se imprime a PDF con páginas, el título del estudio y sus tablas", async ({ page }) => {
  const st = readState()!;
  const id = st.studyVar!.id;
  await page.goto(`/estudios/${id}/reporte`);
  await expect(page.getByRole("table", { name: "Análisis guardados" })).toBeVisible();
  await expect(page.getByText(st.studyVar!.name).first()).toBeVisible();
  await expect.poll(() => page.locator(".js-plotly-plot").count(), { timeout: 30_000 }).toBeGreaterThanOrEqual(3);
  await page.waitForTimeout(1500); // deja terminar el dibujo de las figuras
  // El botón de imprimir abre el diálogo del navegador: aquí se verifica que existe y está activo.
  await expect(page.getByRole("button", { name: "Imprimir / guardar PDF" })).toBeEnabled();

  const buf = await page.pdf({ format: "A4", printBackground: true, margin: { top: "15mm", bottom: "15mm", left: "12mm", right: "12mm" } });
  const file = path.join(__dirname, ".results", "reporte.pdf");
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, buf);
  expect(buf.subarray(0, 5).toString()).toBe("%PDF-");
  const pdf = readPdf(buf);
  test.info().annotations.push({ type: "pdf", description: `${pdf.pages} páginas, ${pdf.text.length} caracteres de texto` });
  expect(pdf.pages).toBeGreaterThanOrEqual(2);
  const flat = pdf.text.replace(/\s+/g, " ");
  expect(flat).toContain(st.studyVar!.name);
  // La parte interactiva (tabla de análisis guardados, botones) no se imprime.
  expect(flat).not.toContain("Exportar a Excel");
  expect(flat).not.toContain("Imprimir / guardar PDF");
  // El documento sí trae sus tablas numeradas.
  expect(flat).toMatch(/Tabla 1/);
});

// ---------------------------------------------------------------------------------------------
// Reglas de corrida en paneles asimétricos (R, S, MR y atributos con límite truncado).
// ---------------------------------------------------------------------------------------------
async function advertencias(page: Page, accion: () => Promise<unknown>) {
  const [res] = await Promise.all([
    page.waitForResponse((r) => /\/api\/charts\/(variables|attributes)$/.test(new URL(r.url()).pathname) && r.request().method() === "POST" && r.status() === 200),
    accion(),
  ]);
  const body = (await res.json()) as { interpretation: { warnings: string[]; findings: string[] } };
  return body.interpretation.warnings;
}

test("R8.5 reglas de racha: advertencia por panel asimétrico y en MR solo el punto fuera de límites", async ({ page }) => {
  const id = await createStudy(page, { name: `E2E reglas ${Date.now().toString(36)}`, lsl: 495, usl: 505 });
  await uploadDataset(page, id, { file: "sintetico_i_mr.csv", phase: "I", justification: "Observaciones individuales consecutivas del mismo proceso." });
  const w0 = await advertencias(page, () => page.goto(`/estudios/${id}/variables`));
  await expect(page.getByLabel("Tipo de gráfico")).toHaveValue("i_mr");
  // Solo el punto fuera de límites: no hay nada que advertir sobre rachas.
  expect(w0.join(" ")).not.toMatch(/asim[eé]trico|rangos m[oó]viles solo se eval[uú]a/);
  const w = await advertencias(page, () => page.getByRole("button", { name: "Nelson" }).click());
  test.info().annotations.push({ type: "advertencias I-MR con Nelson", description: w.join(" | ") });
  expect(w.join(" ")).toMatch(/rangos m[oó]viles solo se eval[uú]a el punto fuera de l[ií]mites/);
  await expect(page.getByText(/rangos m[oó]viles solo se eval[uú]a el punto fuera de l[ií]mites/).first()).toBeVisible();
  // Las advertencias de la API usan coma decimal (D5).
  expect(w.join(" ")).not.toMatch(/\d\.\d/);
});

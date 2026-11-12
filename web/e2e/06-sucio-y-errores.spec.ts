import { test, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { authFile, createStudy, shot, uploadDataset, xbarStatsSucio, EJEMPLOS } from "./helpers";

// Recorridos 6 y 7: archivo sucio y casos de error.
test.describe.configure({ mode: "serial" });
test.use({ storageState: authFile("a") });

let sucioId = "";
let errId = "";
const tmp = path.join(__dirname, ".results", "tmp");

test("R6.1 sintetico_sucio: avisa (D3), detecta subgrupos incompletos (D2), deja limpiar y calcular", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  sucioId = await createStudy(page, { name: `E2E sucio ${Date.now().toString(36)}`, lsl: 495, usl: 505 });
  await page.goto(`/estudios/${sucioId}/datos`);
  await page.getByLabel("Archivo CSV o Excel (.xlsx)").setInputFiles(path.join(EJEMPLOS, "sintetico_sucio.csv"));
  await expect(page.getByRole("table", { name: "Columnas detectadas en la hoja" })).toBeVisible();

  // D3: los avisos de la API al leer el archivo se muestran uno a uno (8 para este archivo).
  const avisos = page.getByRole("alert").or(page.getByRole("status")).filter({ hasText: /Avisos al leer el archivo \(\d+\)/ });
  await expect(avisos).toBeVisible();
  await expect(avisos).toContainText("Avisos al leer el archivo (8)");
  await expect(avisos.locator("li")).toHaveCount(8);
  const textoAvisos = await avisos.locator("li").allInnerTexts();
  test.info().annotations.push({ type: "avisos", description: textoAvisos.join(" | ") });
  // Lo que el README de data/ejemplos pide avisar: celdas vacías, N/D, comas decimales, fecha d/m/a y turno vacío.
  const todos = textoAvisos.join(" ");
  expect(todos).toMatch(/vac[ií]as|no num[eé]ric/i);
  expect(todos).toMatch(/coma/i);
  expect(todos).toMatch(/fecha|d[ií]a\/mes/i);
  expect(todos).toMatch(/turno/i);

  await page.getByLabel("Justificación del subgrupo racional (obligatoria)").fill("Cinco envases consecutivos de la misma línea y turno.");

  // D2: subgrupos incompletos (3, 7 y 11), separados de los atípicos.
  await expect(page.getByRole("heading", { name: "Subgrupos incompletos (3)" })).toBeVisible();
  const tinc = page.getByRole("table", { name: "Subgrupos con tamaño distinto del predominante" });
  const filas = await tinc.locator("tbody tr").evaluateAll((rows) => rows.map((r) => [...r.querySelectorAll("td")].slice(0, 3).map((c) => c.textContent!.trim()).join("/")));
  expect(filas).toEqual(["3/4/1", "7/4/1", "11/4/1"]);
  await expect(page.getByText("El tamaño predominante es n = 5")).toBeVisible();
  await expect(page.getByRole("button", { name: "Retirar todos…" })).toBeVisible();

  // El valor absurdo 5050 se marca como atípico y no se borra en silencio.
  const atip = page.getByRole("table", { name: "Observaciones atípicas" });
  await expect(atip).toBeVisible();
  await expect(atip.getByRole("row", { name: /^9 / })).toContainText("5.050");
  // D4: el texto largo de "Motivo" se ajusta en varias líneas y no se corta por el borde de la tabla.
  const sinCortes = await atip.evaluate((t) => {
    const caja = t.closest("div")!;
    const celdas = [...t.querySelectorAll("td")];
    return { desborda: caja.scrollWidth > caja.clientWidth + 1, cortadas: celdas.filter((c) => c.scrollWidth > c.clientWidth + 1).length };
  });
  expect(sinCortes).toEqual({ desborda: false, cortadas: 0 });
  await shot(page, "03b-datos-sucio.png");

  // Retirar un subgrupo incompleto exige justificación.
  await page.getByRole("button", { name: "Retirar el subgrupo 3" }).click();
  await page.getByRole("button", { name: "Retirar y registrar" }).click();
  await expect(page.getByText("Escribe la justificación (al menos 5 caracteres).")).toBeVisible();
  await page.getByLabel("Justificación (obligatoria)").fill("Falta una medición por falla del instrumento.");
  await page.getByRole("button", { name: "Retirar y registrar" }).click();
  await expect(page.getByRole("heading", { name: "Subgrupos incompletos (2)" })).toBeVisible();
  // Retirar todos los que quedan (7 y 11).
  await page.getByRole("button", { name: "Retirar todos…" }).click();
  await page.getByLabel("Justificación (obligatoria)").fill("Mediciones faltantes o no legibles (vacía y N/D).");
  await page.getByRole("button", { name: "Retirar y registrar" }).click();
  await expect(page.getByRole("heading", { name: /Subgrupos incompletos/ })).toHaveCount(0);
  // Quedan 17 subgrupos y todos con n = 5.
  const resumen = page.getByRole("table", { name: "Resumen por subgrupo" });
  await expect(resumen.locator("tbody tr")).toHaveCount(17);

  // Decide retirar el subgrupo atípico con justificación.
  await atip.getByRole("row", { name: /^9 / }).getByRole("button", { name: "Decidir…" }).click();
  await page.getByRole("radio", { name: /Retirar el subgrupo completo/ }).check();
  await page.getByRole("button", { name: "Registrar decisión" }).click();
  await expect(page.getByText("Escribe la justificación")).toBeVisible();
  await page.getByLabel("Justificación (obligatoria)").fill("Decimal mal capturado: 5050 por 505,0.");
  await page.getByRole("button", { name: "Registrar decisión" }).click();
  await expect(page.getByRole("heading", { name: "Bitácora de limpieza (de esta carga)" })).toBeVisible();
  await expect(resumen.locator("tbody tr")).toHaveCount(16);
  await page.getByRole("button", { name: "Guardar conjunto de datos" }).click();
  await expect(page.getByText("Conjunto de datos guardado")).toBeVisible();

  // La bitácora guardada trae la carga, los avisos de la API (D3), los subgrupos retirados y las justificaciones.
  await page.getByRole("button", { name: "Ver resumen" }).click();
  const log = page.getByRole("table", { name: "Bitácora de limpieza" });
  await expect(log).toContainText("Subgrupo retirado");
  await expect(log).toContainText("Decimal mal capturado");
  await expect(log).toContainText("Falta una medición por falla del instrumento");
  await expect(log).toContainText("Mediciones faltantes o no legibles");
  await expect(log).toContainText("Limpieza");
  for (const w of textoAvisos) await expect(log).toContainText(w.slice(0, 40));
  expect(errors).toEqual([]);

  // D2: ahora X-barra/R calcula con los 16 subgrupos de n = 5 y la línea central coincide con el CSV.
  const ref = xbarStatsSucio([3, 7, 9, 11]);
  expect(ref.count).toBe(16);
  const [res] = await Promise.all([
    page.waitForResponse((r) => r.url().includes("/api/charts/variables") && r.request().method() === "POST"),
    page.goto(`/estudios/${sucioId}/variables`),
  ]);
  expect(res.status()).toBe(200);
  const api = (await res.json()) as { charts: { center: number[] }[]; limits: { params: Record<string, number>; points_used: number } };
  await expect(page.getByText("X-barra necesita subgrupos del mismo tamaño")).toHaveCount(0);
  await expect(page.getByText("16 subgrupos usados en los límites")).toBeVisible();
  expect(api.limits.points_used).toBe(16);
  expect(api.charts[0].center[0]).toBeCloseTo(ref.grand, 6);
  expect(api.limits.params.r_bar).toBeCloseTo(ref.rbar, 6);
  await expect(page.getByRole("heading", { name: "Gráficos de control por variables" })).toBeVisible();
  expect(errors).toEqual([]);
});

test("R7.1 formato no admitido y archivo vacío: mensaje claro, sin caída", async ({ page }) => {
  errId = await createStudy(page, { name: `E2E errores ${Date.now().toString(36)}` }); // sin especificaciones
  fs.mkdirSync(tmp, { recursive: true });
  const txt = path.join(tmp, "datos.pdf");
  fs.writeFileSync(txt, "%PDF-1.4 esto no es una tabla");
  await page.goto(`/estudios/${errId}/datos`);
  await page.getByLabel("Archivo CSV o Excel (.xlsx)").setInputFiles(txt);
  await expect(page.getByText("No se pudo leer el archivo")).toBeVisible();
  await expect(page.getByRole("button", { name: "Guardar conjunto de datos" })).toHaveCount(0);
  const empty = path.join(tmp, "vacio.csv");
  fs.writeFileSync(empty, "");
  await page.getByLabel("Archivo CSV o Excel (.xlsx)").setInputFiles(empty);
  await expect(page.getByText("No se pudo leer el archivo")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Datos", exact: true })).toBeVisible();
});

test("R7.2 Fase II sin límites congelados no calcula y lo explica", async ({ page }) => {
  await uploadDataset(page, errId, { file: "sintetico_fase2.csv", phase: "II" });
  await page.goto(`/estudios/${errId}/variables`);
  await page.getByRole("tab", { name: /^Fase II/ }).click();
  await expect(page.getByText("FASE II — faltan límites congelados")).toBeVisible();
  await expect(page.getByText("Sin límites congelados para este gráfico")).toBeVisible();
  await expect(page.locator(".js-plotly-plot")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Guardar análisis" })).toHaveCount(0);
});

test("R7.3 capacidad sin especificaciones: avisa y no deja calcular", async ({ page }) => {
  await uploadDataset(page, errId, { file: "sintetico_fase1.csv", phase: "I" });
  await page.goto(`/estudios/${errId}/capacidad`);
  await expect(page.getByText("Indica al menos una especificación (LSL o USL).")).toBeVisible();
  await expect(page.getByRole("button", { name: "Calcular capacidad" })).toBeDisabled();
  // Al escribir un USL se habilita
  await page.getByLabel("USL (límite superior)").fill("505");
  await expect(page.getByRole("button", { name: "Calcular capacidad" })).toBeEnabled();
  const [res] = await Promise.all([
    page.waitForResponse((r) => r.url().includes("/api/capability") && r.request().method() === "POST"),
    page.getByRole("button", { name: "Calcular capacidad" }).click(),
  ]);
  const api = (await res.json()) as { interpretation: { summary: string; findings: string[]; warnings: string[] } };
  await expect(page.getByRole("table", { name: /Índices de capacidad/ })).toBeVisible();
  // Con solo USL, Cp/Cpl no aplican (—)
  const row = page.getByRole("table", { name: /Índices de capacidad/ }).getByRole("row", { name: /^Cpl / });
  await expect(row.getByRole("cell").nth(1)).toHaveText("—");
  // Sin análisis guardados para estos datos: la pantalla avisa en «Antes de interpretar estos índices» y la API,
  // al no recibir estabilidad ni normalidad, lo repite en sus advertencias. Los textos usan coma decimal (D5).
  await expect(page.getByText(/No se verificó la estabilidad: no hay un análisis de control guardado para estos mismos datos/)).toBeVisible();
  const adv = api.interpretation.warnings.join(" ");
  expect(adv).toMatch(/No se informó si el proceso está en control estadístico/);
  const todo = [api.interpretation.summary, ...api.interpretation.findings, ...api.interpretation.warnings].join(" ");
  expect(todo).not.toMatch(/\d\.\d/);
});

test("R7.4 datos mínimos: un solo subgrupo no se puede guardar", async ({ page }) => {
  const f = path.join(tmp, "uno.csv");
  fs.mkdirSync(tmp, { recursive: true });
  fs.writeFileSync(f, "subgrupo,x1,x2,x3\n1,500,501,499\n");
  await uploadDataset(page, errId, { file: f, phase: "I", expectSaved: false }).catch(() => {});
  await page.goto(`/estudios/${errId}/datos`);
  await page.getByLabel("Archivo CSV o Excel (.xlsx)").setInputFiles(f);
  await page.getByLabel("Justificación del subgrupo racional (obligatoria)").fill("Prueba con un solo subgrupo.");
  await page.getByRole("button", { name: "Guardar conjunto de datos" }).click();
  await expect(page.getByText("Se necesitan al menos 2 subgrupos para guardar.")).toBeVisible();
});

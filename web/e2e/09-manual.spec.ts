import { test, expect, type Page } from "@playwright/test";
import { authFile, createStudy, shot } from "./helpers";

// Recorrido 10: ingreso manual de datos (pestaña «Escribir o pegar datos»).
test.describe.configure({ mode: "serial" });
test.use({ storageState: authFile("a") });

const stamp = Date.now().toString(36);
let varId = "";
let attrId = "";

const es = (x: number) => String(x).replace(".", ","); // 500.2 -> "500,2"
/** Valor determinista del subgrupo i (1..15), posición j (0..4): 500 + k/5 con k en -5..5. */
const val = (i: number, j: number) => 500 + (((i * 7 + j * 3) % 11) - 5) / 5;
const rowOf = (i: number) => [0, 1, 2, 3, 4].map((j) => val(i, j));

/** Pega `text` en la celda con aria-label `label` con un evento de pegado real (como Excel). */
async function paste(page: Page, label: string, text: string) {
  await page.getByLabel(label, { exact: true }).evaluate((el, t) => {
    const dt = new DataTransfer();
    dt.setData("text/plain", t);
    el.dispatchEvent(new ClipboardEvent("paste", { clipboardData: dt, bubbles: true, cancelable: true }));
  }, text);
}

async function manualTab(page: Page, id: string) {
  await page.goto(`/estudios/${id}/datos`);
  await page.getByRole("tab", { name: "Escribir o pegar datos" }).click();
  await expect(page.getByRole("table", { name: /Tabla editable de datos/ })).toBeVisible();
}

async function useAndSave(page: Page, justification: string) {
  await page.getByRole("button", { name: "Usar estos datos" }).click();
  await expect(page.getByRole("table", { name: "Columnas detectadas en la hoja" })).toBeVisible();
  await page.getByLabel("Justificación del subgrupo racional (obligatoria)").fill(justification);
  await page.getByRole("radio", { name: /^Fase I:/ }).check();
}

test("R10.1 escribir con teclado, pegar un bloque con tabuladores y coma decimal, renombrar y conservar el borrador", async ({ page }) => {
  varId = await createStudy(page, { name: `E2E manual ${stamp}`, lsl: 495, usl: 505, target: 500 });
  await manualTab(page, varId);
  await expect(page.getByLabel("Nombre de la columna 2")).toHaveValue("x1");
  await expect(page.getByText("0 filas con datos")).toBeVisible();
  await expect(page.getByRole("button", { name: "Usar estos datos" })).toBeDisabled();

  // Teclado: fila 1 con Tab entre celdas; coma decimal tal cual.
  await page.getByLabel("Fila 1, subgrupo", { exact: true }).click();
  const row1 = [String(1), ...rowOf(1).map(es)];
  for (let k = 0; k < row1.length; k++) {
    await page.keyboard.type(row1[k]);
    if (k < row1.length - 1) await page.keyboard.press("Tab");
  }
  await expect(page.getByLabel("Fila 1, x5")).toHaveValue(es(val(1, 4)));
  // Enter baja a la celda de abajo.
  await page.getByLabel("Fila 1, x1").focus();
  await page.keyboard.press("Enter");
  await expect(page.getByLabel("Fila 2, x1")).toBeFocused();
  await expect(page.getByText("1 fila con datos")).toBeVisible();

  // Pegado: 14 subgrupos (2..15) x 7 columnas desde Fila 2, subgrupo. Excede las 10 filas y
  // las 6 columnas del borrador: crea 5 filas y la columna_7 (temperatura, de relleno).
  const block = Array.from({ length: 14 }, (_, k) => {
    const i = k + 2;
    return [String(i), ...rowOf(i).map(es), es(20 + (i % 3) / 2)].join("\t");
  }).join("\r\n") + "\r\n";
  await paste(page, "Fila 2, subgrupo", block);
  await expect(page.getByText("Bloque pegado a partir de la celda activa.")).toBeVisible();
  await expect(page.getByLabel("Nombre de la columna 7")).toHaveValue("columna_7");
  await expect(page.getByLabel("Fila 15, x3")).toHaveValue(es(val(15, 2)));
  await expect(page.getByLabel("Fila 2, x1")).toHaveValue(es(val(2, 0)));
  await expect(page.getByLabel("Fila 15, columna_7")).toHaveValue(es(20 + (15 % 3) / 2));
  await expect(page.getByText("15 filas con datos")).toBeVisible();

  // Renombrar columna.
  await page.getByLabel("Nombre de la columna 7").fill("temperatura");
  await expect(page.getByLabel("Fila 3, temperatura")).toBeVisible();

  // El borrador sobrevive al cambiar de pestaña.
  await page.getByRole("tab", { name: "Subir archivo" }).click();
  await expect(page.getByLabel("Archivo CSV o Excel (.xlsx)")).toBeVisible();
  await page.getByRole("tab", { name: "Escribir o pegar datos" }).click();
  await expect(page.getByLabel("Nombre de la columna 7")).toHaveValue("temperatura");
  await expect(page.getByLabel("Fila 15, x3")).toHaveValue(es(val(15, 2)));
  await expect(page.getByText("15 filas con datos")).toBeVisible();
  await shot(page, "15-ingreso-manual.png");
});

test("R10.2 «Usar estos datos», guardar como Fase I y comprobar la línea central y los límites", async ({ page }) => {
  await manualTab(page, varId);
  // La página se recargó: el borrador vuelve vacío. Se pega todo con el encabezado (reemplaza nombres).
  const header = ["subgrupo", "x1", "x2", "x3", "x4", "x5", "temperatura"].join("\t");
  const lines = Array.from({ length: 15 }, (_, k) => {
    const i = k + 1;
    return [String(i), ...rowOf(i).map(es), es(20 + (i % 3) / 2)].join("\t");
  });
  await paste(page, "Nombre de la columna 1", [header, ...lines].join("\n"));
  await expect(page.getByText("15 filas con datos")).toBeVisible();

  await useAndSave(page, "Cinco mediciones consecutivas de la misma línea y turno forman un subgrupo.");
  await expect(page.getByText("Datos en uso:")).toContainText("tabla escrita en la página");
  await expect(page.getByLabel("Formato de los datos")).toHaveValue("wide");
  await expect(page.getByRole("table", { name: "Resumen por subgrupo" }).locator("tbody tr")).toHaveCount(15);
  // La coma decimal se convirtió y quedó avisada como al leer un archivo.
  await expect(page.getByText(/Avisos al leer el archivo/)).toBeVisible();
  await expect(page.getByText(/coma decimal/i).first()).toBeVisible();
  await page.getByRole("button", { name: "Guardar conjunto de datos" }).click();
  await expect(page.getByText("Conjunto de datos guardado")).toBeVisible();
  const tabla = page.getByRole("table", { name: "Conjuntos de datos guardados" });
  await expect(tabla.getByRole("row", { name: /Ingreso manual.*Fase I.*15/ })).toBeVisible();

  // Valores calculados aparte, con las mismas tolerancias que R3.2.
  const rows = Array.from({ length: 15 }, (_, k) => rowOf(k + 1));
  const means = rows.map((r) => r.reduce((a, b) => a + b, 0) / 5);
  const grand = means.reduce((a, b) => a + b, 0) / 15;
  const rbar = rows.map((r) => Math.max(...r) - Math.min(...r)).reduce((a, b) => a + b, 0) / 15;
  const [res] = await Promise.all([
    page.waitForResponse((r) => r.url().includes("/api/charts/variables") && r.request().method() === "POST" && r.status() === 200),
    page.goto(`/estudios/${varId}/variables`),
  ]);
  const api = await res.json();
  const x = api.charts[0];
  expect(x.center[0]).toBeCloseTo(grand, 6);
  expect(api.limits.params.r_bar).toBeCloseTo(rbar, 6);
  expect(x.ucl[0]).toBeCloseTo(grand + 0.577 * rbar, 2);
  expect(x.lcl[0]).toBeCloseTo(grand - 0.577 * rbar, 2);
  expect(api.limits.points_used).toBe(15);
  await expect(page.getByText("FASE I — límites de prueba")).toBeVisible();
  await expect(page.getByText("15 subgrupos usados en los límites")).toBeVisible();
  await expect(page.locator("dt", { hasText: "Media del proceso (μ)" }).locator("xpath=following-sibling::dd").first()).toContainText(
    grand.toFixed(4).replace(".", ","),
  );
});

test("R10.3 atributos: tabla manual con separador de miles (1.000,0) y gráfico p con la tasa correcta", async ({ page }) => {
  attrId = await createStudy(page, { name: `E2E manual atributos ${stamp}`, type: "attribute" });
  await manualTab(page, attrId);
  await expect(page.getByLabel("Nombre de la columna 3")).toHaveValue("defectuosos");
  const n = ["100", "120", "1.000,0", "90", "110", "100", "95", "105"];
  const d = [4, 6, 48, 5, 5, 4, 5, 6];
  const nVal = [100, 120, 1000, 90, 110, 100, 95, 105];
  await paste(page, "Fila 1, muestra", n.map((v, k) => [k + 1, v, d[k]].join("\t")).join("\n"));
  await expect(page.getByText("8 filas con datos")).toBeVisible();
  await useAndSave(page, "Cada muestra es el lote inspeccionado en un turno.");
  await expect(page.getByLabel("Columna del conteo")).toHaveValue("defectuosos");
  await expect(page.getByLabel("Columna del tamaño de muestra")).toHaveValue("inspeccionados");
  await expect(page.getByText(/separador de miles/i).first()).toBeVisible();
  await page.getByRole("button", { name: "Guardar conjunto de datos" }).click();
  await expect(page.getByText("Conjunto de datos guardado")).toBeVisible();

  const pbar = d.reduce((a, b) => a + b, 0) / nVal.reduce((a, b) => a + b, 0);
  await page.goto(`/estudios/${attrId}/atributos`);
  const [res] = await Promise.all([
    page.waitForResponse((r) => new URL(r.url()).pathname === "/api/charts/attributes" && r.request().method() === "POST" && r.status() === 200),
    page.getByLabel("Tipo de gráfico").selectOption("p"),
  ]);
  const api = await res.json();
  // Si 1.000,0 se hubiera leído como 1 o descartado, p-barra sería otra.
  expect(api.charts[0].center[0]).toBeCloseTo(pbar, 6);
});

import { test, expect } from "@playwright/test";
import { authFile, num, readState, shot } from "./helpers";

// Recorrido 5: muestreo de aceptación, diseñar y evaluar un plan (valores contra cálculo binomial propio).
test.describe.configure({ mode: "serial" });
test.use({ storageState: authFile("a") });

const binom = (n: number, k: number, p: number) => {
  let c = 1;
  for (let i = 1; i <= k; i++) c = (c * (n - k + i)) / i;
  return c * p ** k * (1 - p) ** (n - k);
};
const pa = (n: number, c: number, p: number) => Array.from({ length: c + 1 }, (_, k) => binom(n, k, p)).reduce((a, b) => a + b, 0);

/** Plan simple mínimo (n, luego c) con Pa(AQL) >= 1-α y Pa(LTPD) <= β. */
function design(aql: number, alpha: number, ltpd: number, beta: number) {
  for (let n = 1; n < 2000; n++)
    for (let c = 0; c < n; c++) if (pa(n, c, aql) >= 1 - alpha && pa(n, c, ltpd) <= beta) return { n, c };
  throw new Error("sin plan");
}

const card = (page: import("@playwright/test").Page, k: string) => page.locator("p", { hasText: new RegExp(`^${k}$`) }).locator("xpath=following-sibling::p[1]");

test("R5.1 diseñar un plan simple (AQL 1 %, LTPD 6 %, α 5 %, β 10 %) y guardarlo", async ({ page }) => {
  const id = readState()!.studyVar!.id;
  await page.goto(`/estudios/${id}/muestreo`);
  await page.getByRole("button", { name: "Diseñar plan", exact: true }).click();
  await expect(page.getByText("Tamaño de muestra n", { exact: true })).toBeVisible();
  const exp = design(0.01, 0.05, 0.06, 0.1);
  expect(Number(await card(page, "Tamaño de muestra n").innerText())).toBe(exp.n);
  expect(Number(await card(page, "Número de aceptación c").innerText())).toBe(exp.c);
  const alphaReal = (1 - pa(exp.n, exp.c, 0.01)) * 100;
  const betaReal = pa(exp.n, exp.c, 0.06) * 100;
  expect(num((await card(page, "Riesgo del productor α real").innerText()).replace(" %", ""))).toBeCloseTo(alphaReal, 1);
  expect(num((await card(page, "Riesgo del consumidor β real").innerText()).replace(" %", ""))).toBeCloseTo(betaReal, 1);
  expect(alphaReal).toBeLessThanOrEqual(5);
  expect(betaReal).toBeLessThanOrEqual(10);
  await expect(page.getByText("Curva OC: probabilidad de aceptar el lote").first()).toBeVisible();
  await expect.poll(() => page.locator(".js-plotly-plot").count()).toBeGreaterThanOrEqual(3);
  await shot(page, "11-muestreo.png");
  await page.getByRole("button", { name: "Guardar plan y análisis" }).click();
  await expect(page.getByText(/guardado y añadido al reporte/)).toBeVisible();
  await expect(page.getByRole("table", { name: "Planes de muestreo guardados" }).getByRole("cell", { name: /Plan simple/ }).first()).toBeVisible();
});

test("R5.2 evaluar un plan existente (n = 80, c = 2)", async ({ page }) => {
  const id = readState()!.studyVar!.id;
  await page.goto(`/estudios/${id}/muestreo`);
  await page.getByRole("tab", { name: "Evaluar plan simple" }).click();
  await page.getByRole("button", { name: "Evaluar plan", exact: true }).click();
  await expect(page.getByText("Riesgo del productor α real", { exact: true })).toBeVisible();
  expect(num((await card(page, "Riesgo del productor α real").innerText()).replace(" %", ""))).toBeCloseTo((1 - pa(80, 2, 0.01)) * 100, 1);
  expect(num((await card(page, "Riesgo del consumidor β real").innerText()).replace(" %", ""))).toBeCloseTo(pa(80, 2, 0.06) * 100, 1);
});

test("R5.3 validaciones: AQL mayor que LTPD y c >= n", async ({ page }) => {
  const id = readState()!.studyVar!.id;
  await page.goto(`/estudios/${id}/muestreo`);
  await page.getByLabel("AQL (fracción defectuosa aceptable)").fill("0,08");
  await page.getByRole("button", { name: "Diseñar plan", exact: true }).click();
  await expect(page.getByText("El AQL debe ser menor que el LTPD.")).toBeVisible();
  await page.getByRole("tab", { name: "Evaluar plan simple" }).click();
  await page.getByLabel("c (número de aceptación)").fill("90");
  await page.getByRole("button", { name: "Evaluar plan", exact: true }).click();
  await expect(page.getByText("c debe ser menor que n.")).toBeVisible();
});

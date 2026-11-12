import { test, expect } from "@playwright/test";
import { authFile, createStudy, readState, shot, updateState, uploadDataset } from "./helpers";

// Recorrido 4: gráficos por atributos con tamaño de muestra variable y asistente de selección.
test.describe.configure({ mode: "serial" });
test.use({ storageState: authFile("a") });

test("R4.1 estudio por atributos y carga de sintetico_p_n_variable", async ({ page }) => {
  const name = `E2E atributos ${Date.now().toString(36)}`;
  const id = await createStudy(page, { name, type: "attribute" });
  updateState({ studyAttr: { id, name } });
  await uploadDataset(page, id, { file: "sintetico_p_n_variable.csv", phase: "I", expectSaved: false, justification: "Cada muestra es el lote inspeccionado en un turno; el tamaño cambia según la producción." });
  await expect(page.getByLabel("Columna del conteo")).toHaveValue("defectuosos");
  await expect(page.getByLabel("Columna del tamaño de muestra")).toHaveValue("tamano_muestra");
  await expect(page.getByRole("table", { name: "Resumen de atributos por subgrupo" }).locator("tbody tr")).toHaveCount(30);
  await page.getByRole("button", { name: "Guardar conjunto de datos" }).click();
  await expect(page.getByText("Conjunto de datos guardado")).toBeVisible();
});

test("R4.2 el asistente recomienda p para tamaño variable y el gráfico marca las muestras 8 y 20", async ({ page }) => {
  const id = readState()!.studyAttr!.id;
  const apiRes = page.waitForResponse((r) => new URL(r.url()).pathname === "/api/charts/attributes" && r.request().method() === "POST" && r.status() === 200);
  await page.goto(`/estudios/${id}/atributos`);
  await expect(page.getByRole("heading", { name: "Asistente: ¿qué gráfico necesito?" })).toBeVisible();
  await page.getByRole("radio", { name: /No, cambia de un subgrupo a otro/ }).check();
  await page.getByRole("radio", { name: /Unidades defectuosas/ }).check();
  await page.getByRole("button", { name: "Recomendar gráfico" }).click();
  await expect(page.getByText("Gráfico recomendado: p (fracción defectuosa)")).toBeVisible();
  // Con tamaño constante y defectuosas recomienda np; con defectos y tamaño variable, u.
  await page.getByRole("radio", { name: /Sí, siempre inspecciono lo mismo/ }).check();
  await page.getByRole("button", { name: "Recomendar gráfico" }).click();
  await expect(page.getByText(/Gráfico recomendado: np/)).toBeVisible();
  await page.getByRole("radio", { name: /Defectos: varios por unidad/ }).check();
  await page.getByRole("radio", { name: /No, cambia/ }).check();
  await page.getByRole("button", { name: "Recomendar gráfico" }).click();
  await expect(page.getByText(/Gráfico recomendado: u/)).toBeVisible();
  // Vuelve a la recomendación correcta para estos datos y la usa.
  await page.getByRole("radio", { name: /Unidades defectuosas/ }).check();
  await page.getByRole("button", { name: "Recomendar gráfico" }).click();
  await expect(page.getByText("Gráfico recomendado: p (fracción defectuosa)")).toBeVisible();

  await page.getByRole("button", { name: "Usar p", exact: true }).click();
  const api = await (await apiRes).json();
  await expect(page.getByLabel("Tipo de gráfico")).toHaveValue("p");
  await expect(page.getByText("◆ 2 punto(s) con señal")).toBeVisible();
  const sig = page.getByRole("table", { name: "Puntos con señal" });
  const labels = await sig.locator("tbody tr").evaluateAll((rows) => rows.map((r) => r.querySelector("td")!.textContent!.trim()));
  expect(labels).toEqual(["8", "20"]);

  // Límites variables: cambian muestra a muestra (más anchos con n chico) y p-barra ~ 0,048.
  const c = api.charts[0];
  expect(new Set(c.ucl.map((x: number) => x.toFixed(6))).size).toBeGreaterThan(5);
  expect(c.center[0]).toBeGreaterThan(0.046);
  expect(c.center[0]).toBeLessThan(0.05);
  const sizes: number[] = readSizes();
  const iMin = sizes.indexOf(Math.min(...sizes));
  const iMax = sizes.indexOf(Math.max(...sizes));
  expect(c.ucl[iMin] - c.center[iMin]).toBeGreaterThan(c.ucl[iMax] - c.center[iMax]);
  await expect(page.locator("dt", { hasText: "Fracción defectuosa media (p̄)" }).locator("xpath=following-sibling::dd")).toContainText("0,04");
  await shot(page, "07-atributos.png");

  await page.getByRole("button", { name: "Guardar análisis" }).click();
  await page.getByRole("button", { name: "Confirmar y guardar" }).click();
  await expect(page.getByText(/Análisis «.*» guardado/)).toBeVisible();
});

test("R4.4 gráfico p con LCI truncado en 0: las reglas de racha traen una advertencia", async ({ page }) => {
  const id = readState()!.studyAttr!.id;
  await page.goto(`/estudios/${id}/atributos`);
  await page.getByLabel("Tipo de gráfico").selectOption("p");
  await expect(page.getByText("◆ 2 punto(s) con señal")).toBeVisible();
  const [res] = await Promise.all([
    page.waitForResponse((r) => new URL(r.url()).pathname === "/api/charts/attributes" && r.request().method() === "POST" && r.status() === 200),
    page.getByRole("button", { name: "Western Electric" }).click(),
  ]);
  const body = (await res.json()) as { interpretation: { warnings: string[] }; charts: { lcl: number[] }[] };
  expect(Math.min(...body.charts[0].lcl)).toBe(0); // p-barra ~ 0,048 con n ~ 100: el límite inferior se trunca en 0
  const w = body.interpretation.warnings.join(" ");
  // En conteos la advertencia no afirma "mayor": la tasa es distinta de la nominal (validación, H19).
  expect(w).toMatch(/regla WE4 se aplicó aunque el gráfico es de conteos con límites asimétricos/);
  expect(w).toMatch(/distinta de la nominal/);
  expect(w).not.toMatch(/\d\.\d/); // textos de la API con coma decimal (D5)
  // En pantalla: qué reglas se evaluaron y cuáles no (WE2 y WE3 necesitan zonas simétricas).
  await expect(page.getByText("Reglas evaluadas: WE1, WE4.")).toBeVisible();
  const noEval = page.getByRole("list", { name: "Reglas no evaluadas en este gráfico" });
  await expect(noEval.getByRole("listitem")).toHaveCount(2);
  await expect(noEval).toContainText("WE2:");
  await expect(noEval).toContainText("WE3:");
});

test("R4.3 np con tamaños variables se rechaza con un aviso claro", async ({ page }) => {
  const id = readState()!.studyAttr!.id;
  await page.goto(`/estudios/${id}/atributos`);
  await page.getByLabel("Tipo de gráfico").selectOption("np");
  await expect(page.getByText("El gráfico np exige tamaño de muestra constante")).toBeVisible();
});

import fs from "node:fs";
import path from "node:path";
import { EJEMPLOS } from "./helpers";
function readSizes(): number[] {
  const lines = fs.readFileSync(path.join(EJEMPLOS, "sintetico_p_n_variable.csv"), "utf8").trim().split(/\r?\n/).slice(1);
  return lines.map((l) => Number(l.split(",")[4]));
}

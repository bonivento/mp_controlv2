import { test, expect, type BrowserContext, type Page } from "@playwright/test";
import { PASSWORD, authFile, createStudy, guestFile, shot, uploadDataset, xbarStats } from "./helpers";
import fs from "node:fs";

// Recorrido 9: modo invitado (inicio anónimo de Supabase).
// Cada corrida crea UN solo invitado (no se puede borrar sin clave de servicio): todos los pasos
// comparten un contexto. La sesión se guarda en e2e/.auth/user-g.json para que 99-limpieza borre
// el estudio al final. Tras convertirlo en cuenta, el mismo usuario queda como e2e-g-<sello>@example.com.
test.describe.configure({ mode: "serial" });

const stamp = Date.now().toString(36);
const email = `e2e-g-${stamp}@example.com`;
const studyName = `E2E invitado ${stamp}`;
let ctx: BrowserContext;
let page: Page;
let studyId = "";

test.beforeAll(async ({ browser }) => {
  fs.rmSync(guestFile, { force: true });
  ctx = await browser.newContext();
  page = await ctx.newPage();
});
test.afterAll(async () => {
  await ctx?.close();
});

const save = () => ctx.storageState({ path: guestFile });

test("R9.1 «Continuar como invitado» entra con cabecera «Invitado» y aviso persistente", async () => {
  await page.goto("/login");
  await expect(page.getByRole("heading", { name: "Sigmalena" })).toBeVisible();
  await page.getByRole("button", { name: "Continuar como invitado" }).click();
  await expect(page).toHaveURL(/\/estudios$/, { timeout: 60_000 });
  const header = page.getByRole("banner");
  await expect(header.getByText("Invitado", { exact: true })).toBeVisible();
  const note = page.getByRole("note");
  await expect(note).toContainText("Sesión de invitado");
  await expect(note.getByRole("button", { name: "Crear cuenta para conservar mis datos" })).toBeVisible();
  await save();
  // El aviso persiste al recargar y al cambiar de pantalla.
  await page.reload();
  await expect(page.getByRole("note")).toContainText("Sesión de invitado");
  await page.goto("/estudios/nuevo");
  await expect(page.getByRole("note")).toContainText("Sesión de invitado");
});

test("R9.2 el invitado crea un estudio y la API real (con su sesión) calcula el gráfico", async () => {
  studyId = await createStudy(page, { name: studyName, lsl: 495, usl: 505, target: 500 });
  await uploadDataset(page, studyId, { file: "sintetico_fase1.csv", phase: "I" });
  const [res] = await Promise.all([
    page.waitForResponse((r) => r.url().includes("/api/charts/variables") && r.request().method() === "POST"),
    page.goto(`/estudios/${studyId}/variables`),
  ]);
  expect(res.status()).toBe(200);
  const api = await res.json();
  const all = xbarStats("sintetico_fase1.csv");
  expect(api.charts[0].center[0]).toBeCloseTo(all.grand, 6);
  expect(api.charts[0].ucl[0]).toBeCloseTo(all.grand + 0.577 * all.rbar, 2);
  await expect(page.getByText("FASE I — límites de prueba")).toBeVisible();
  await expect(page.getByText("◆ 1 punto(s) con señal")).toBeVisible();
  await expect(page.locator("dt", { hasText: "Media del proceso (μ)" }).locator("xpath=following-sibling::dd").first()).toContainText(
    all.grand.toFixed(4).replace(".", ","),
  );
  await save();
});

test("R9.3 cancelar el cierre de sesión mantiene la sesión y los datos", async () => {
  await page.goto("/estudios");
  await expect(page.getByRole("link", { name: studyName, exact: true })).toBeVisible();
  await shot(page, "14-invitado.png", false);
  await page.getByRole("button", { name: "Cerrar sesión" }).click();
  const dlg = page.getByRole("dialog");
  await expect(dlg).toContainText("¿Cerrar la sesión de invitado?");
  await expect(dlg).toContainText("perderás el acceso");
  await dlg.getByRole("button", { name: "Cancelar" }).click();
  await expect(dlg).toBeHidden();
  await expect(page).toHaveURL(/\/estudios$/);
  await expect(page.getByRole("banner").getByText("Invitado", { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("link", { name: studyName, exact: true })).toBeVisible();
});

test("R9.4 convertir en cuenta conserva el estudio y quita el aviso", async () => {
  await page.goto("/estudios");
  await page.getByRole("note").getByRole("button", { name: "Crear cuenta para conservar mis datos" }).click();
  const dlg = page.getByRole("dialog");
  // Validaciones del formulario
  await dlg.getByLabel("Correo electrónico").fill("no-es-correo");
  await dlg.getByLabel("Contraseña").fill(PASSWORD);
  await dlg.getByRole("button", { name: "Crear cuenta" }).click();
  await expect(dlg.getByText("correo electrónico válido")).toBeVisible();
  await dlg.getByLabel("Correo electrónico").fill(email);
  await dlg.getByLabel("Contraseña").fill("123");
  await dlg.getByRole("button", { name: "Crear cuenta" }).click();
  await expect(dlg.getByText("al menos 6 caracteres")).toBeVisible();
  await dlg.getByLabel("Contraseña").fill(PASSWORD);
  await dlg.getByRole("button", { name: "Crear cuenta" }).click();
  await expect(page.getByRole("dialog")).toBeHidden({ timeout: 60_000 });
  await expect(page.getByRole("banner").getByText(email)).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("note")).toHaveCount(0);
  await expect(page.getByRole("link", { name: studyName, exact: true })).toBeVisible();
  await save();
  fs.writeFileSync(guestFile.replace(".json", ".creds.json"), JSON.stringify({ email, password: PASSWORD }));
  // Sigue ahí tras recargar y los datos siguen alimentando el gráfico.
  await page.reload();
  await expect(page.getByRole("banner").getByText(email)).toBeVisible();
  await expect(page.getByRole("link", { name: studyName, exact: true })).toBeVisible();
  await save();
  await page.goto(`/estudios/${studyId}/datos`);
  await expect(page.getByRole("table", { name: "Conjuntos de datos guardados" }).getByRole("row", { name: /sintetico_fase1.*Fase I.*25/ })).toBeVisible();
});

test("R9.5 aislamiento: el usuario A no ve el estudio del invitado", async ({ browser }) => {
  const ctxA = await browser.newContext({ storageState: authFile("a") });
  const pa = await ctxA.newPage();
  await pa.goto("/estudios");
  await expect(pa.getByRole("heading", { name: "Estudios", exact: true })).toBeVisible();
  await expect(pa.getByText("Cargando estudios")).toBeHidden();
  await expect(pa.getByText(studyName)).toHaveCount(0);
  await pa.goto(`/estudios/${studyId}`);
  await expect(pa.getByText("Estudio no encontrado")).toBeVisible();
  await ctxA.close();
});

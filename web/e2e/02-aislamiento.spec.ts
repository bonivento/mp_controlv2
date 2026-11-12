import { test, expect } from "@playwright/test";
import { authFile, createStudy, readState, shot, updateState } from "./helpers";

// Recorrido 2: el usuario B no ve ni abre el estudio del usuario A (RLS en Supabase).
test.describe.configure({ mode: "serial" });

const name = `E2E aislamiento ${Date.now().toString(36)}`;
let studyId = "";

test("R2.1 A crea un estudio y lo ve en su lista", async ({ browser }) => {
  const ctx = await browser.newContext({ storageState: authFile("a") });
  const page = await ctx.newPage();
  studyId = await createStudy(page, { name, lsl: 495, usl: 505, target: 500 });
  updateState({ studyIso: { id: studyId, name } });
  await page.goto("/estudios");
  await expect(page.getByRole("link", { name, exact: true })).toBeVisible();
  await shot(page, "02-estudios.png");
  await ctx.close();
});

test("R2.2 B no ve el estudio de A en su lista", async ({ browser }) => {
  const ctx = await browser.newContext({ storageState: authFile("b") });
  const page = await ctx.newPage();
  await page.goto("/estudios");
  await expect(page.getByRole("heading", { name: "Estudios", exact: true })).toBeVisible();
  await expect(page.getByText(readState()!.userB.email)).toBeVisible(); // es la sesión de B
  await expect(page.getByText("Cargando estudios")).toBeHidden();
  await expect(page.getByText(name)).toHaveCount(0);
  await ctx.close();
});

test("R2.3 B no puede abrir el estudio de A por URL directa ni sus módulos", async ({ browser }) => {
  const ctx = await browser.newContext({ storageState: authFile("b") });
  const page = await ctx.newPage();
  for (const sub of ["", "/datos", "/variables", "/reporte"]) {
    await page.goto(`/estudios/${studyId}${sub}`);
    await expect(page.getByText("Estudio no encontrado")).toBeVisible();
    await expect(page.getByText(name)).toHaveCount(0);
  }
  await ctx.close();
});

test("R2.4 B crea su propio estudio y A no lo ve", async ({ browser }) => {
  const nameB = `E2E aislamiento B ${Date.now().toString(36)}`;
  const ctxB = await browser.newContext({ storageState: authFile("b") });
  const pageB = await ctxB.newPage();
  await createStudy(pageB, { name: nameB });
  await pageB.goto("/estudios");
  await expect(pageB.getByRole("link", { name: nameB, exact: true })).toBeVisible();
  await expect(pageB.getByText(name)).toHaveCount(0);
  await ctxB.close();

  const ctxA = await browser.newContext({ storageState: authFile("a") });
  const pageA = await ctxA.newPage();
  await pageA.goto("/estudios");
  await expect(pageA.getByRole("link", { name, exact: true })).toBeVisible();
  await expect(pageA.getByText(nameB)).toHaveCount(0);
  await ctxA.close();
});

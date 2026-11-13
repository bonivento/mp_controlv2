import { test, expect } from "@playwright/test";
import { PASSWORD, authFile, readState, saveAuth, shot, signIn, writeState } from "./helpers";
import fs from "node:fs";

// Recorrido 1: registro, inicio y cierre de sesión; ruta protegida sin sesión.
// Los usuarios A y B se crean una sola vez (no se pueden borrar sin clave de servicio) y se
// reutilizan en las corridas siguientes (e2e/.auth/state.json).
test.describe.configure({ mode: "serial" });

const stamp = Date.now().toString(36);
const fresh = !readState() || !fs.existsSync(authFile("a")) || !fs.existsSync(authFile("b"));
const state = fresh
  ? {
      stamp,
      userA: { email: `e2e-a-${stamp}@example.com`, password: PASSWORD },
      userB: { email: `e2e-b-${stamp}@example.com`, password: PASSWORD },
      createdStudies: [] as string[],
    }
  : readState()!;

test("R1.1 una ruta protegida sin sesión redirige a /login", async ({ page }) => {
  await page.goto("/estudios");
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole("heading", { name: "Sigmalena" })).toBeVisible();
  await page.goto("/estudios/00000000-0000-0000-0000-000000000000/variables");
  await expect(page).toHaveURL(/\/login$/);
  await shot(page, "01-login.png");
});

test("R1.2 contraseña corta y credenciales erróneas muestran un error", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Correo electrónico").fill("nadie-e2e@example.com");
  await page.getByLabel("Contraseña").fill("123");
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page.getByText("al menos 6 caracteres")).toBeVisible();
  await page.getByLabel("Contraseña").fill("clave-incorrecta-1");
  await page.getByRole("button", { name: "Entrar" }).click();
  // Supabase puede tardar en responder (el botón queda en "Entrar…" mientras tanto): se espera más.
  await expect(page.getByRole("alert").filter({ hasText: /./ }).first()).toBeVisible({ timeout: 60_000 });
  await expect(page).toHaveURL(/\/login$/);
});

test("R1.3 registro de usuario A, cierre de sesión y nuevo inicio", async ({ page, context }) => {
  test.skip(!fresh, "Los usuarios ya existen (state.json): se reutilizan en lugar de crear otros.");
  writeState(state);
  await page.goto("/login");
  await page.getByRole("tab", { name: "Crear cuenta" }).click();
  await page.getByLabel("Correo electrónico").fill(state.userA.email);
  await page.getByLabel("Contraseña").fill(state.userA.password);
  await page.getByRole("button", { name: "Crear cuenta" }).click();
  await expect(page).toHaveURL(/\/estudios$/, { timeout: 30_000 });
  await expect(page.getByText(state.userA.email)).toBeVisible();
  await page.getByRole("button", { name: "Cerrar sesión" }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.goto("/estudios");
  await expect(page).toHaveURL(/\/login$/); // tras cerrar sesión ya no entra
  await signIn(page, state.userA.email, state.userA.password);
  await expect(page.getByText(state.userA.email)).toBeVisible();
  await saveAuth(context, "a");
});

test("R1.4 inicio y cierre de sesión con un usuario existente (A)", async ({ page, context }) => {
  writeState(state);
  await signIn(page, state.userA.email, state.userA.password);
  await expect(page.getByRole("heading", { name: "Estudios" })).toBeVisible();
  await expect(page.getByText(state.userA.email)).toBeVisible();
  await page.reload();
  await expect(page.getByText(state.userA.email)).toBeVisible(); // la sesión sobrevive a recargar
  await page.getByRole("button", { name: "Cerrar sesión" }).click();
  await expect(page).toHaveURL(/\/login$/);
  // Cerrar sesión revoca todas las sesiones del usuario (alcance global de Supabase), así que
  // la sesión que usarán los demás recorridos se guarda DESPUÉS de cerrar.
  await signIn(page, state.userA.email, state.userA.password);
  await saveAuth(context, "a");
});

test("R1.5 registro del usuario B", async ({ page, context }) => {
  test.skip(!fresh, "El usuario B ya existe: se reutiliza.");
  await page.goto("/login");
  await page.getByRole("tab", { name: "Crear cuenta" }).click();
  await page.getByLabel("Correo electrónico").fill(state.userB.email);
  await page.getByLabel("Contraseña").fill(state.userB.password);
  await page.getByRole("button", { name: "Crear cuenta" }).click();
  await expect(page).toHaveURL(/\/estudios$/, { timeout: 30_000 });
  await saveAuth(context, "b");
});

test("R1.6 inicio de sesión del usuario B existente", async ({ page, context }) => {
  // La sesión guardada vale solo para el dominio en que se creó: al cambiar de BASE_URL
  // (local o producción) B debe iniciar sesión otra vez, igual que A en R1.4.
  test.skip(fresh, "B acaba de registrarse: su sesión ya está guardada.");
  await signIn(page, state.userB.email, state.userB.password);
  await expect(page.getByText(state.userB.email)).toBeVisible();
  await saveAuth(context, "b");
});

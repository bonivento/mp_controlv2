import { test, expect } from "@playwright/test";
import fs from "node:fs";
import { authFile, guestFile, readState, signIn } from "./helpers";

// Borra todos los estudios que crearon las pruebas (ambos usuarios). Los usuarios no se pueden
// borrar sin clave de servicio: quedan registrados en e2e/.auth/state.json.
test.describe.configure({ mode: "serial" });

for (const u of ["a", "b", "g"] as const) {
  test(`limpieza: estudios E2E del usuario ${u === "g" ? "invitado/convertido" : u.toUpperCase()}`, async ({ browser }) => {
    test.skip(!!process.env.E2E_KEEP, "E2E_KEEP=1 conserva los estudios.");
    const file = u === "g" ? guestFile : authFile(u);
    test.skip(!fs.existsSync(file), "No hay sesión de invitado guardada (08-invitado no corrió).");
    const ctx = await browser.newContext({ storageState: file });
    const page = await ctx.newPage();
    await page.goto("/estudios");
    if (u === "g" && /\/login/.test(page.url())) {
      // La sesión guardada caducó: si el invitado ya era cuenta, se entra con sus credenciales.
      const credsFile = guestFile.replace(".json", ".creds.json");
      test.skip(!fs.existsSync(credsFile), "Invitado sin conversión y sin sesión vigente: no se puede limpiar.");
      const c = JSON.parse(fs.readFileSync(credsFile, "utf8"));
      await signIn(page, c.email, c.password);
    }
    await expect(page.getByRole("heading", { name: "Estudios", exact: true })).toBeVisible();
    await expect(page.getByText("Cargando estudios")).toBeHidden();
    const own = page.getByRole("button", { name: /^Eliminar E2E / });
    let guard = 0;
    while ((await own.count()) > 0 && guard++ < 40) {
      await own.first().click();
      await page.getByRole("dialog").getByRole("button", { name: /^Eliminar/ }).click();
      await expect(page.getByRole("dialog")).toBeHidden();
      await page.waitForTimeout(300);
    }
    await expect(own).toHaveCount(0);
    expect(readState()).not.toBeNull();
    await ctx.close();
  });
}

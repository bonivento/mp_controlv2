import { test, expect } from "@playwright/test";
import { authFile, readState, shot } from "./helpers";

// Recorrido 11: asistente con IA. Hace UNA conversación real con el modelo (cuesta unos
// centavos por corrida) sobre el estudio de variables que dejó el recorrido 3. Si la API no
// tiene credencial de IA configurada, el recorrido comprueba el aviso y omite la conversación.
test.use({ storageState: authFile("a") });

test("R11.1 el asistente recibe el contexto de Variables y responde en flujo con cifras de la pantalla", async ({ page }) => {
  const study = readState()!.studyVar!;
  await page.goto(`/estudios/${study.id}/variables`);
  await expect(page.getByText(/Gráfico X-barra/).first()).toBeVisible({ timeout: 60_000 });

  // El estado del servicio se consulta al abrir el panel.
  const statusResp = page.waitForResponse((r) => r.url().includes("/api/assistant/status"));
  await page.getByRole("button", { name: "Asistente", exact: true }).click();
  const status = await (await statusResp).json();
  const panel = page.getByRole("dialog", { name: "Asistente con IA" });
  await expect(panel).toBeVisible();

  if (!status.enabled) {
    await expect(panel.getByText("El asistente no está configurado")).toBeVisible();
    test.skip(true, "La API no tiene ANTHROPIC_API_KEY: no se prueba la conversación real.");
  }

  await expect(panel.getByText(/Viendo:.*Variables/)).toBeVisible();
  const chatReq = page.waitForRequest((r) => r.url().includes("/api/assistant/chat") && r.method() === "POST");
  const chatResp = page.waitForResponse((r) => r.url().includes("/api/assistant/chat"));
  await panel.getByRole("button", { name: "Interpreta estos resultados" }).click();

  // La web envía la pantalla, la ficha del estudio y el resultado reducido; nunca las filas.
  const body = (await chatReq).postDataJSON();
  expect(body.context.screen).toBe("variables");
  expect(body.context.study.name).toBe(study.name);
  expect(JSON.stringify(body.context).length).toBeLessThan(60_000);
  expect(JSON.stringify(body.context.view)).toContain("ucl");

  const resp = await chatResp;
  expect(resp.status()).toBe(200);
  expect(resp.headers()["content-type"]).toContain("text/event-stream");

  // Mientras responde se puede detener; al terminar vuelve «Enviar».
  const log = panel.getByRole("log", { name: "Conversación con el asistente" });
  await expect(panel.getByRole("button", { name: "Enviar" })).toBeVisible({ timeout: 150_000 });
  await expect(panel.getByRole("alert")).toHaveCount(0);
  const answer = (await log.innerText()).replace(/\s+/g, " ");
  expect(answer.length).toBeGreaterThan(200);
  // Habla de lo que hay en pantalla: gráfico, fase y al menos una cifra con coma decimal.
  expect(answer).toMatch(/X-barra|X̄/);
  expect(answer).toMatch(/Fase I/);
  expect(answer).toMatch(/\d,\d/);
  await shot(page, "16-asistente.png", false);

  // Esc cierra el panel y la conversación se conserva al volver a abrirlo.
  await page.keyboard.press("Escape");
  await expect(panel).toBeHidden();
  await page.getByRole("button", { name: "Asistente", exact: true }).click();
  await expect(log).toContainText("Interpreta estos resultados");
});

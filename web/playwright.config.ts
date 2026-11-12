import { defineConfig, devices } from "@playwright/test";

/**
 * Pruebas de extremo a extremo del software CEP.
 *
 * Variables de entorno:
 *   BASE_URL         URL de la web a probar. Si se define (p. ej. producción) NO se levantan servidores.
 *   E2E_WEB_PORT     Puerto de la web local (3030 por defecto).
 *   E2E_API_PORT     Puerto de la API local (8030 por defecto).
 *   E2E_WEB_DIR      Carpeta desde la que se corre `next dev` (por defecto, esta carpeta). Útil si
 *                    ya hay otro `next dev` en web/ (Next 16 solo permite uno por carpeta).
 *   E2E_API_DIR      Carpeta de la API (../api por defecto).
 */
const webPort = process.env.E2E_WEB_PORT ?? "3030";
const apiPort = process.env.E2E_API_PORT ?? "8030";
const baseURL = process.env.BASE_URL ?? `http://localhost:${webPort}`;
const local = !process.env.BASE_URL;

export default defineConfig({
  testDir: "./e2e",
  outputDir: "./e2e/.results",
  // Los recorridos comparten estudios y usuarios: van en orden y de uno en uno.
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 180_000,
  expect: { timeout: 20_000 },
  reporter: [["list"], ["html", { open: "never", outputFolder: "e2e/.report" }]],
  use: {
    baseURL,
    locale: "es-CO",
    viewport: { width: 1440, height: 900 },
    acceptDownloads: true,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } }],
  webServer: local
    ? [
        {
          // API con la autenticación activa (camino real).
          command: `.venv/bin/uvicorn main:app --port ${apiPort}`,
          cwd: process.env.E2E_API_DIR ?? "../api",
          url: `http://localhost:${apiPort}/api/health`,
          reuseExistingServer: true,
          timeout: 180_000,
        },
        {
          command: `npx next dev -p ${webPort}`,
          cwd: process.env.E2E_WEB_DIR ?? ".",
          env: { API_URL: `http://localhost:${apiPort}` },
          url: `http://localhost:${webPort}/login`,
          reuseExistingServer: true,
          timeout: 240_000,
        },
      ]
    : undefined,
});

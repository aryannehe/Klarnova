import { defineConfig, devices } from "@playwright/test";
import path from "node:path";

const isCI = !!process.env.CI;
const FRONTEND_PORT = Number(process.env.E2E_FRONTEND_PORT ?? 3000);
const BACKEND_PORT = Number(process.env.E2E_BACKEND_PORT ?? 8000);

const FRONTEND_URL = process.env.E2E_BASE_URL ?? `http://localhost:${FRONTEND_PORT}`;
const BACKEND_URL = process.env.E2E_API_URL ?? `http://localhost:${BACKEND_PORT}`;

// A throwaway SQLite database keeps the E2E run isolated from any dev data.
const DB_PATH = path
  .resolve(__dirname, "..", "test-reports", "e2e.db")
  .replace(/\\/g, "/");
const DATABASE_URL = `sqlite+aiosqlite:///${DB_PATH}`;

const webhookToken = process.env.ALERTMANAGER_WEBHOOK_TOKEN ?? "e2e-token";

const isWindows = process.platform === "win32";
const python = isWindows
  ? ".venv\\Scripts\\python.exe"
  : ".venv/bin/python";

const backendBoot =
  `${python} ../scripts/e2e_bootstrap.py && ` +
  `${python} -m uvicorn app.main:app --host 127.0.0.1 --port ${BACKEND_PORT}`;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  forbidOnly: isCI,
  retries: isCI ? 2 : 0,
  timeout: 90_000,
  expect: { timeout: 15_000 },

  reporter: [
    ["list"],
    ["html", { open: "never", outputFolder: "../test-reports/playwright-html" }],
    [
      path.join(__dirname, "e2e", "reporters", "csv-reporter.ts"),
      { outputFile: path.join(__dirname, "..", "test-reports", "e2e-results.csv") },
    ],
  ],

  globalSetup: path.join(__dirname, "e2e", "global-setup.ts"),

  use: {
    baseURL: FRONTEND_URL,
    trace: "on-first-retry",
    video: "on",
    screenshot: "only-on-failure",
  },

  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],

  webServer: [
    {
      command: backendBoot,
      cwd: path.resolve(__dirname, "..", "backend"),
      url: `${BACKEND_URL}/health`,
      reuseExistingServer: !isCI,
      timeout: 180_000,
      env: {
        DATABASE_URL,
        ALERTMANAGER_WEBHOOK_TOKEN: webhookToken,
        JWT_SECRET: process.env.JWT_SECRET ?? "e2e-secret",
        KB_AUTO_INGEST: "false",
        KUBE_IN_CLUSTER: "false",
        LLM_PROVIDER: process.env.LLM_PROVIDER ?? "ollama",
        // Keep the post-remediation cluster health poll short so approval
        // decisions resolve quickly against synthetic (non-existent) resources.
        REMEDIATION_HEALTH_TIMEOUT: "2",
        REMEDIATION_HEALTH_INTERVAL: "0.5",
      },
    },
    {
      command: `npm run dev -- -p ${FRONTEND_PORT}`,
      cwd: __dirname,
      url: FRONTEND_URL,
      reuseExistingServer: !isCI,
      timeout: 180_000,
      env: {
        NEXT_PUBLIC_API_BASE: BACKEND_URL,
      },
    },
  ],
});

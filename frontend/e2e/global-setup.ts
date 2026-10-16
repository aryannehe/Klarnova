import { request } from "@playwright/test";

import { API_URL } from "./helpers/config";

/**
 * Fail fast with a helpful message if the backend is not reachable. Playwright
 * starts the backend via webServer, but the health endpoint may need a moment.
 */
export default async function globalSetup(): Promise<void> {
  const ctx = await request.newContext();
  const deadline = Date.now() + 60_000;
  let lastError = "";
  try {
    while (Date.now() < deadline) {
      try {
        const res = await ctx.get(`${API_URL}/health`, { timeout: 5000 });
        if (res.ok()) return;
        lastError = `status ${res.status()}`;
      } catch (err) {
        lastError = err instanceof Error ? err.message : String(err);
      }
      await new Promise((r) => setTimeout(r, 1000));
    }
    throw new Error(`backend not reachable at ${API_URL} (${lastError})`);
  } finally {
    await ctx.dispose();
  }
}

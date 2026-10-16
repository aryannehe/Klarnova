import { expect, type Page } from "@playwright/test";

/** Sign in through the real login form and wait for the dashboard. */
export async function loginViaUI(
  page: Page,
  username: string,
  password: string
): Promise<void> {
  await page.goto("/login");
  // The very first request can race the freshly-started backend (the UI shows
  // "Cannot reach backend"); retry a couple of times before giving up.
  for (let attempt = 0; ; attempt++) {
    await page.getByLabel("Username").fill(username);
    await page.getByLabel("Password").fill(password);
    await page.getByRole("button", { name: /sign in/i }).click();
    try {
      await expect(page).toHaveURL(/\/incidents/, { timeout: 15_000 });
      break;
    } catch (e) {
      if (attempt >= 2) throw e;
      await page.waitForTimeout(2_000);
      await page.goto("/login");
    }
  }
  await expect(page.getByRole("heading", { name: "Incidents" })).toBeVisible();
}

/** Set the auth token directly in localStorage (skips the login round-trip). */
export async function seedToken(page: Page, token: string): Promise<void> {
  await page.addInitScript((t) => {
    window.localStorage.setItem("klarnova_token", t);
  }, token);
}
